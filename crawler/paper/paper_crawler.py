import os
import logging
import platform
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from crawler.common.downloader import Downloader
from crawler.paper.config.settings import STORAGE_CONFIG, CRAWL_LIMITS
from crawler.config.settings import DOWNLOADER_CONFIG
from crawler.common.url_cache_manager import URLCacheManager
from datetime import datetime
from crawler.paper.core.article_paper import (
    ArticlePaper, ArxivPaper, HuggingFacePaper, PaperWithCodePaper
)
import json

class PaperCrawlerConfig:
    """论文爬虫配置类"""
    def __init__(self):
        # 各个渠道的启用状态
        self.enabled_sources = {}
        
        # 各个渠道的具体配置
        self.source_configs = {
            'arxiv': {
                'start_url': 'https://arxiv.org/list/cs.AI/recent?skip=0&show=50',
                'max_pages': 10,
                'page_size': 50
            },
            'huggingface': {
                'start_url': 'https://huggingface.co/papers',
                'max_pages': 10,
                'page_size': 20
            },
            'paperswithcode': {
                'start_url': 'https://paperswithcode.com/latest',
                'max_pages': 10,
                'page_size': 20
            }
        }

class PageCount:
    """页面计数器"""
    def __init__(self):
        self.count = 0
        
    def add(self):
        self.count += 1

    def need_more(self) -> bool:
        return self.count < CRAWL_LIMITS['max_pages_per_source']

    def get(self) -> int:
        return self.count

class PaperCrawler:
    """论文爬虫基类"""
    
    def __init__(self, config: Optional[PaperCrawlerConfig] = None):
        self.config = config or PaperCrawlerConfig()
        self.papers: List[ArticlePaper] = []
        self.crawlers = self._init_crawlers()
        self.downloader = Downloader(**DOWNLOADER_CONFIG)
        self.page_count = PageCount()
        self.url_cache = URLCacheManager('data/cache/url_cache.json')
        
        # 确保存储目录存在
        os.makedirs(STORAGE_CONFIG['base_dir'], exist_ok=True)
        
    def _init_crawlers(self) -> Dict[str, ArticlePaper]:
        """初始化各个渠道的爬虫"""
        crawlers = {}
        crawler_classes = {
            'arxiv': ArxivPaper,
            'huggingface': HuggingFacePaper,
            'paperswithcode': PaperWithCodePaper
        }
        
        for source, enabled in self.config.enabled_sources.items():
            if enabled and source in crawler_classes:
                crawlers[source] = crawler_classes[source]()
                
        return crawlers
    
    async def crawl(self):
        """开始爬取所有启用的渠道"""
        try:
            crawl_methods = {
                'arxiv': self.crawl_arxiv,
                'huggingface': self.crawl_huggingface,
                'paperswithcode': self.crawl_paperswithcode
            }
            
            for source, enabled in self.config.enabled_sources.items():
                if enabled and source in crawl_methods:
                    try:
                        await crawl_methods[source]()
                    except Exception as e:
                        logging.error(f"爬取 {source} 失败: {str(e)}", exc_info=True)
                        
        except Exception as e:
            logging.error(f"爬取过程出错: {str(e)}", exc_info=True)
        finally:
            await self.downloader.close()
            logging.info(f"共爬取 {self.page_count.get()} 个页面")
            
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """获取页面内容并解析"""
        try:
            response = await self.downloader.get(url)
            if response and hasattr(response, 'text'):
                return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"获取页面失败 {url}: {str(e)}")
        return None
    
    def _get_save_path(self, paper: ArticlePaper) -> str:
        """获取文章保存路径"""
        # 使用日期和来源创建子目录
        date_str = datetime.now().strftime('%Y-%m-%d')
        source_dir = os.path.join(STORAGE_CONFIG['base_dir'], paper.source, date_str)
        os.makedirs(source_dir, exist_ok=True)
        
        # 使用论文ID或标题作为文件名
        filename = f"{paper.paper_id or paper.title[:50]}.txt"
        # 替换文件名中的非法字符
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        
        return os.path.join(source_dir, filename)
    
    def save_paper(self, paper: ArticlePaper):
        """保存论文信息"""
        try:
            save_path = self._get_save_path(paper)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(paper.to_text())
            logging.info(f"保存论文成功: {save_path}")
        except Exception as e:
            logging.error(f"保存论文失败: {str(e)}", exc_info=True)

    async def crawl_arxiv(self):
        """抓取 arxiv 论文"""
        source_config = self.config.source_configs['arxiv']
        base_url = source_config['start_url']
        
        for page in range(source_config['max_pages']):
            skip = page * source_config['page_size']
            url = base_url.replace('skip=0', f'skip={skip}')
            
            if soup := await self._fetch_page(url):
                items = soup.find_all('dd')
                for item in items:
                    if paper := await self.crawlers['arxiv'].parse_item(item, self.downloader):
                        self.papers.append(paper)
                        self.save_paper(paper)
                        self.page_count.add()
                        
                if not self.page_count.need_more():
                    break

    async def crawl_huggingface(self):
        """抓取 HuggingFace 论文"""
        source_config = self.config.source_configs['huggingface']
        base_url = source_config['start_url']
        
        for page in range(source_config['max_pages']):
            url = f"{base_url}?page={page+1}"
            
            if soup := await self._fetch_page(url):
                items = soup.select('div.paper-card')
                for item in items:
                    if paper := self.crawlers['huggingface'].parse_item(item):
                        self.papers.append(paper)
                        self.save_paper(paper)
                        self.page_count.add()
                        
                if not self.page_count.need_more():
                    break

    async def crawl_paperswithcode(self):
        """抓取 PapersWithCode 论文"""
        source_config = self.config.source_configs['paperswithcode']
        base_url = source_config['start_url']
        
        for page in range(source_config['max_pages']):
            url = f"{base_url}?page={page+1}"
            
            if soup := await self._fetch_page(url):
                items = soup.select('div.paper-item')
                for item in items:
                    if paper := self.crawlers['paperswithcode'].parse_item(item):
                        self.papers.append(paper)
                        self.save_paper(paper)
                        self.page_count.add()
                        
                if not self.page_count.need_more():
                    break

class StopCrawling(Exception):
    """达到爬取限制时抛出的异常"""
    pass