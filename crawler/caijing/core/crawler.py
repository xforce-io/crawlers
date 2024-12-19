import asyncio
from crawler.config.settings import CACHE_DIR, DOWNLOADER_CONFIG, ROBOTS_CACHE_DIR
import httpx
from selectolax.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from collections import deque
import os
import re
import logging
from datetime import datetime
from typing import Set, Dict, List, Optional, Tuple
from ..config.site_configs import SiteConfig
from ...common.robots_parser import RobotsParser
from ...common.cache_manager import CacheManager
from ...common.article import Article
from ...common.downloader import Downloader, DownloaderError, NetworkError, SSLError
from .parser import ArticleParser
import time
from contextlib import asynccontextmanager
from .article_manager import ArticleManager
from ..config.settings import ARTICLE_RETENTION_DAYS, ARTICLE_CLEANUP_ENABLED

class MultiSiteCrawler:
    def __init__(
            self, 
            site_configs: Dict[str, SiteConfig], 
            max_articles: int, 
            max_per_site: int, 
            save_dir: str,
            concurrent_tasks: int):
        """
        初始化爬虫
        
        :param site_configs: 网站��置列表
        :param max_articles: 最大保存文章数
        :param max_per_site: 每个站点的最大文章数
        :param save_dir: 文章保存目录
        :param concurrent_tasks: 每个站点的并发任务数
        """
        # 只使用启用的站点配置
        self.site_configs = [config for config in site_configs.values() if config.enabled]
        self.max_articles = max_articles
        self.max_per_site = max_per_site
        self.save_dir = save_dir
        
        # 只创建主保存目录
        os.makedirs(save_dir, exist_ok=True)
        
        # 为每个站点创建独立的URL队列
        self.url_queues: Dict[str, deque] = {
            config.domain: deque([config.start_url]) for config in self.site_configs
        }
        self.visited_urls: Dict[str, Set[str]] = {
            config.domain: set() for config in self.site_configs
        }
        self.saved_articles_count: Dict[str, int] = {
            config.domain: 0 for config in self.site_configs
        }
        self.total_articles = 0
        
        # 设置请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        # 创建日志目录
        log_dir = "log"
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志
        log_file = os.path.join(log_dir, "crawler.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # 同时输出到控制台
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 添加错误URL记录
        self.error_urls: Dict[str, Set[str]] = {
            config.domain: set() for config in self.site_configs
        }
        
        # 添加robots解析器
        self.robots_parser = RobotsParser(cache_dir=ROBOTS_CACHE_DIR)
        
        # 添加缓存管理器
        self.cache_manager = CacheManager(cache_dir=CACHE_DIR)
        
        # 为每个域名初始化缓存
        for config in self.site_configs:
            self.cache_manager.init_domain(config.domain)
            
        # 新增配置
        self.concurrent_tasks = concurrent_tasks
        self.downloader = Downloader(
            **DOWNLOADER_CONFIG)
        self.parser = ArticleParser()
        
        # 添加限流控制
        self.rate_limiters: Dict[str, asyncio.Semaphore] = {
            config.domain: asyncio.Semaphore(concurrent_tasks)
            for config in self.site_configs
        }
        
        # 添加统计信息
        self.stats = {
            config.domain: {
                'start_time': None,
                'end_time': None,
                'success_count': 0,
                'error_count': 0,
                'skip_count': 0
            } for config in self.site_configs
        }
        
        self.article_manager = ArticleManager(
            base_dir=save_dir, 
            retention_days=ARTICLE_RETENTION_DAYS)
        
        # 清理非日期目录
        self.article_manager.cleanup_invalid_directories()
        
        # 如果启用了自动清理，在初始化时清理过期文章
        if ARTICLE_CLEANUP_ENABLED:
            cleaned_count = self.article_manager.cleanup_old_articles()
            if cleaned_count > 0:
                self.logger.info(f"已清理 {cleaned_count} 篇过期文章")
        
    @asynccontextmanager
    async def get_session(self):
        """获取复用的 HTTP 会话"""
        session = await self.downloader.get_session()
        try:
            yield session
        finally:
            if session and not session.is_closed:
                await session.aclose()

    async def init_robots_rules(self):
        """初始化所有站点的robots规则"""
        # 收集所有需要检查的域名
        domains = set()
        for config in self.site_configs:
            if config.domains:
                domains.update(config.domains)
            else:
                domains.add(config.domain)
        
        # 初始化robots规则
        await self.robots_parser.init_robots_rules(list(domains))
        
    def is_valid_url(self, url: str, current_domain: str) -> bool:
        """检查URL是否有效且属于当前域名"""
        try:
            parsed = urlparse(url)
            
            # 首先检查robots.txt规则
            if not self.robots_parser.is_url_allowed(url, parsed.netloc):
                self.logger.debug(f"URL被robots.txt禁止访问: {url}")
                return False
            
            # 针对同花顺的特殊检查
            if '10jqka.com.cn' in current_domain:
                allowed_domains = [
                    'news.10jqka.com.cn',
                    'stock.10jqka.com.cn',
                ]
                if parsed.netloc not in allowed_domains:
                    return False
                if not re.match(r'.*/\d{8}/c\d+\.s?html$', url):
                    return False
                return True
            
            # 针对财经网的特殊检查
            if 'caijing.com.cn' in current_domain:
                allowed_domains = [
                    'finance.caijing.com.cn',
                    'economy.caijing.com.cn'
                ]
                if parsed.netloc not in allowed_domains:
                    return False
                    
            # 针对财新网的特殊检查
            if 'caixin.com' in current_domain:
                allowed_domains = [
                    'economy.caixin.com',
                    'finance.caixin.com'
                ]
                if parsed.netloc not in allowed_domains:
                    return False
                # 根据robots.txt规则排除特定URL
                if ('?' in url or  # 排除所有带参数的URL
                    '100923808' in url):  # 排除特定模式
                    return False
                    
            # 针对澎湃新闻的特殊检查
            if 'thepaper.cn' in current_domain:
                allowed_domains = [
                    'www.thepaper.cn'
                ]
                if parsed.netloc not in allowed_domains:
                    return False
                # 检查是否是文章页面
                if 'newsDetail_forward_' in url:
                    # 提取文章ID并验证
                    if not re.search(r'newsDetail_forward_\d+', url):
                        return False
                # 检查是否是允许的频道页面
                elif 'channel_25951' not in url:
                    return False
                    
            # 其他站点的检查
            elif current_domain not in parsed.netloc:
                return False
                
            # 通用检查
            if parsed.scheme not in ['http', 'https']:
                return False
            if any(ext in url for ext in ['.jpg', '.png', '.pdf', '.zip']):
                return False
            
            # 修改日期提取逻辑，持多种日期格式
            date_patterns = [
                r'/(\d{4})(\d{2})(\d{2})/',  # 匹配 /20240322/
                r'/(\d{4})-(\d{2})-(\d{2})/'  # 匹配 /2024-03-22/
            ]
            
            for pattern in date_patterns:
                if date_match := re.search(pattern, url):
                    year, month, day = map(int, date_match.groups())
                    article_date = datetime(year, month, day)
                    current_date = datetime.now()
                    delta = current_date - article_date
                    
                    # 如果文章日期超过3个月，返回False
                    if delta.days > 90:  # 90��约等于3个月
                        return False
                    break  # 找到日期后退出循环
            
            return True
        except Exception as e:
            self.logger.error(f"URL验证出错: {str(e)}")
            return False

    def get_site_config(self, url: str) -> SiteConfig:
        """获取URL对应的网站配置"""
        for config in self.site_configs:
            if config.domain in url:
                return config
        return None

    def clean_filename(self, title: str) -> str:
        """清理文件名，移除非法字符"""
        return re.sub(r'[\\/*?:"<>|]', '', title)

    def parse_article(self, html: HTMLParser, config: SiteConfig, url: str) -> Optional[Article]:
        """解析文章内容和元信息"""
        try:
            # 1. 检查缓存
            if self.cache_manager.is_cached(url, config.domain):
                self.logger.debug(f"文章已存在于缓存中: {url}")
                return None
            
            # 2. 使用ArticleParser解析
            parser = ArticleParser()
            article = parser.parse_article(html, config, url)
            
            if not article:
                self.logger.error(f"文章解析失败: {url}")
                return None
            
            # 3. 检查文章日期
            if not Article.is_within_retention_period(article.publish_date, ARTICLE_RETENTION_DAYS):
                self.logger.warning(f"文章日期超出保留期限: {url}, 日期: {article.publish_date}")
                return None
            
            # 4. 检查文章内容
            if len(article.summary) < 50:
                self.logger.error(f"文章内容过短或无效: {url}, 长度: {len(article.summary)}")
                return None
            
            # 5. 检查是否达到限制
            if (self.saved_articles_count[config.domain] >= self.max_per_site or
                self.total_articles >= self.max_articles):
                self.logger.info(f"已达文章数量限制: {url}")
                return None
            
            # 6. 检查今日文章数
            if self.get_today_article_count(config.domain) >= config.max_articles_per_day:
                self.logger.info(f"{config.domain} 今日文章数已达上限")
                return None
            
            self.logger.info(f"成功解析文章: {article.title}")
            return article
        
        except Exception as e:
            self.logger.error(f"解析文章出错 {url}: {str(e)}", exc_info=True)
            self.error_urls[config.domain].add(url)
            return None

    async def save_article(self, article: Article, config: SiteConfig):
        """保存文章到文件"""
        try:
            if not article:
                return

            # 构建保存路径: data/news_articles/YYYY-MM-DD/domain.com/
            date_dir = os.path.join(self.save_dir, article.publish_date.strftime('%Y-%m-%d'))
            domain_dir = os.path.join(date_dir, config.domain)
            
            try:
                # 先创建日期目录，再创建域名目录
                os.makedirs(domain_dir, exist_ok=True)
            except Exception as e:
                self.logger.error(f"创建保存目录失败: {domain_dir}, 错误: {str(e)}")
                return
            
            # 清理文件名
            title = self.clean_filename(article.title)
            if not title:
                title = f"article_{hash(article.url)}"
            
            # 构建文件路径
            file_path = os.path.join(domain_dir, f"{title}.txt")
            
            # 如果文件已存在，检查是否是相同的URL
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if f"来源：{article.url}" in content:
                            self.logger.debug(f"文件已存在且URL相同，跳过: {file_path}")
                            return
                except Exception as e:
                    self.logger.error(f"读取已存在文件失败: {file_path}, 错误: {str(e)}")
                    return
            
            # 写入文件
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    self.logger.info(f"写入文件: {file_path}")
                    f.write(article.to_text())
            except Exception as e:
                self.logger.error(f"写入文件失败: {file_path}, 错误: {str(e)}")
                return
            
            # 更新计数器
            self.saved_articles_count[config.domain] += 1
            self.total_articles += 1
            
            # 添加到缓存
            self.cache_manager.add_to_cache(article.url, config.domain)
            
            self.logger.info(f"保存文章成功: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存文章失败 {article.url if article else 'unknown'}: {str(e)}")

    def is_article_page(self, url: str, config: SiteConfig) -> bool:
        """判断是否是文章页面"""
        try:
            # 使用正则表达式匹配URL模式
            pattern = config.article_pattern
            if not pattern.startswith('^'):
                pattern = f".*{pattern}"
            if not pattern.endswith('$'):
                pattern = f"{pattern}.*"
            
            return bool(re.match(pattern, url))
        except Exception as e:
            self.logger.error(f"检查文章页面时出错: {str(e)}")
            return False

    def extract_date(self, url: str, html: HTMLParser, config: SiteConfig) -> str:
        """提取文章日期"""
        try:
            # 1. 从URL中提取日期
            if match := re.search(r'/(\d{4})(\d{2})(\d{2})/', url):
                year, month, day = match.groups()
                if (1900 <= int(year) <= 2100 and 
                    1 <= int(month) <= 12 and 
                    1 <= int(day) <= 31):
                    return f"{year}-{month}-{day}"
            
            # 2. 从页面元素中提取日期
            for selector in config.date_selectors:
                if date_elem := html.css_first(selector):
                    text = date_elem.text()
                    if match := re.search(r'(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})', text):
                        year, month, day = match.groups()
                        if (1900 <= int(year) <= 2100 and 
                            1 <= int(month) <= 12 and 
                            1 <= int(day) <= 31):
                            return f"{year}-{int(month):02d}-{int(day):02d}"
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"日期提取出错: {str(e)}, URL: {url}")
            return ""

    def is_article_within_days(self, date_str: str, days: int = 7) -> bool:
        """检查文章日期是否在指定天数内"""
        try:
            article_date = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now()
            delta = today - article_date
            return delta.days <= days
        except Exception as e:
            self.logger.error(f"日期检查出错: {str(e)}")
            return False

    async def fetch_url(self, url: str, domain: str) -> Tuple[str, List[str]]:
        """获取页面内容和链接"""
        async with self.rate_limiters[domain]:
            try:
                # 修改为直接使用 downloader 的 get 方法
                response = await self.downloader.get(url)
                if not response:
                    raise NetworkError(f"Failed to get response from {url}")
                
                # 处理编码
                content = (response.content.decode('gbk') 
                          if '10jqka.com.cn' in url 
                          else response.text)
                
                # 解析页面
                html = HTMLParser(content)
                
                # 提取链接
                links = self._extract_links(html, url, domain)
                
                # 处理文章
                if self.is_article_page(url, self.get_site_config(url)):
                    await self._process_article(html, url, domain)
                
                return url, links
                    
            except (NetworkError, SSLError) as e:
                self.logger.warning(f"{e.__class__.__name__}: {str(e)}")
                self.error_urls[domain].add(url)
                self.stats[domain]['error_count'] += 1
                return url, []
                
            except DownloaderError as e:
                self.logger.error(f"下载错误: {str(e)}", exc_info=True)
                self.error_urls[domain].add(url)
                self.stats[domain]['error_count'] += 1
                return url, []
                
            except Exception as e:
                self.logger.error(f"抓取页面失败 {url}: {str(e)}", exc_info=True)
                self.error_urls[domain].add(url)
                self.stats[domain]['error_count'] += 1
                return url, []

    async def _process_article(self, html: HTMLParser, url: str, domain: str):
        """处理文章页面"""
        config = self.get_site_config(url)
        article = self.parse_article(html, config, url)
        
        if article:
            await self.save_article(article, config)
            self.stats[domain]['success_count'] += 1
        else:
            self.stats[domain]['skip_count'] += 1

    def _extract_links(self, html: HTMLParser, base_url: str, domain: str) -> List[str]:
        """提取并过滤页面链接"""
        links = []
        try:
            for a in html.css('a[href]'):
                try:
                    # 获取 href 属性，如果不存在则跳过
                    href = a.attributes.get('href')
                    if not href:
                        continue
                    
                    href = href.strip()
                    if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                        continue
                    
                    # 构建完整URL
                    absolute_url = urljoin(base_url, href)
                    if self.is_valid_url(absolute_url, domain):
                        links.append(absolute_url)
                    
                except Exception as e:
                    self.logger.debug(f"处理单个链接出错 {base_url} -> {href if href else 'unknown'}: {str(e)}")
                    continue
                
        except Exception as e:
            self.logger.error(f"提取链接出错 {base_url}: {str(e)}", exc_info=True)
        
        return links

    def get_today_article_count(self, domain: str) -> int:
        """获取当天的文章数量"""
        today = datetime.now().strftime('%Y-%m-%d')
        today_dir = os.path.join(self.save_dir, today, domain)
        
        try:
            if os.path.exists(today_dir):
                return len([f for f in os.listdir(today_dir) 
                          if f.endswith('.txt')])
        except Exception as e:
            self.logger.error(f"统计今日文章数出错: {str(e)}")
        return 0

    async def crawl_site(self, config: SiteConfig):
        """爬取单个站点"""
        domain = config.domain
        self.stats[domain]['start_time'] = time.time()
        
        try:
            tasks = []
            while (self.url_queues[domain] and 
                   self.total_articles < self.max_articles and  # 检查总数限制
                   self.saved_articles_count[domain] < self.max_per_site):  # 检查单站点限制
                
                # 创建新任务直到达到并发限制
                while (len(tasks) < self.concurrent_tasks and 
                       self.url_queues[domain]):
                    url = self.url_queues[domain].popleft()
                    if url not in self.visited_urls[domain]:
                        self.visited_urls[domain].add(url)
                        task = asyncio.create_task(self.fetch_url(url, domain))
                        tasks.append(task)
                
                if not tasks:
                    break
                    
                # 等待任务完成
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 处理完成的任务
                for task in done:
                    try:
                        url, new_links = await task
                        # 检查是否已达到限制
                        if (self.total_articles >= self.max_articles or 
                            self.saved_articles_count[domain] >= self.max_per_site):
                            # 取消所有待处理的任务
                            for pending_task in pending:
                                pending_task.cancel()
                            return  # 直接返回，结束爬取
                            
                        if new_links:
                            self.url_queues[domain].extend(new_links)
                    except Exception as e:
                        self.logger.error(f"处理任务结果出错: {str(e)}", exc_info=True)
                    tasks.remove(task)
                
                tasks = list(pending)
                
        except Exception as e:
            self.logger.error(f"站点爬取出错 {domain}: {str(e)}", exc_info=True)
            
        finally:
            self.stats[domain]['end_time'] = time.time()
            await self._print_site_stats(domain)

    async def _print_site_stats(self, domain: str):
        """输出站点爬取统计信息"""
        stats = self.stats[domain]
        duration = stats['end_time'] - stats['start_time']
        
        self.logger.info(f"\n=== {domain} 爬取报告 ===")
        self.logger.info(f"耗时: {duration:.2f} 秒")
        self.logger.info(f"成功文章: {stats['success_count']}")
        self.logger.info(f"失败次数: {stats['error_count']}")
        self.logger.info(f"跳过文章: {stats['skip_count']}")
        self.logger.info(f"访问URL数: {len(self.visited_urls[domain])}")
        self.logger.info(f"错误URL数: {len(self.error_urls[domain])}")
        
        if len(self.visited_urls[domain]) > 0:
            error_rate = (len(self.error_urls[domain]) / 
                         len(self.visited_urls[domain]) * 100)
            self.logger.info(f"错误率: {error_rate:.2f}%")

    async def crawl(self):
        """并行爬取所有站点"""
        await self.init_robots_rules()
        
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            tasks = []
            for config in self.site_configs:
                task = asyncio.create_task(self.crawl_site(config))
                tasks.append(task)
            
            try:
                # 等待所有任务完成或直到达到总数限制
                while tasks:
                    done, pending = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # 处理完成的任务
                    for task in done:
                        try:
                            await task
                        except Exception as e:
                            self.logger.error(f"任务执行出错: {str(e)}", exc_info=True)
                        tasks.remove(task)
                    
                    # 如果达到总数限制，取消剩余任务并退出
                    if self.total_articles >= self.max_articles:
                        self.logger.info(f"已达到总文章限制 {self.max_articles}，停止爬取")
                        for task in pending:
                            task.cancel()
                        break
                    
                    tasks = list(pending)
                    
            except Exception as e:
                self.logger.error(f"爬取过程出错: {str(e)}", exc_info=True)
                # 取消所有未完成的任务
                for task in tasks:
                    if not task.done():
                        task.cancel()