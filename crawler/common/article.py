from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Callable, Pattern
from crawler.caijing.config.settings import MAX_LINES_DOWNLOADED
from crawler.common.date_extractor import DateExtractor
from selectolax.parser import HTMLParser
import re
import logging
from functools import lru_cache
import inspect

class ArticleExtractor:
    """文章提取器，包含所有静态提取方法"""
    
    # 日期相关的正则表达式
    DATE_PATTERNS: List[Tuple[Pattern, str]] = [
        (re.compile(r'(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})'), '%Y-%m-%d'),  # 2024-03-22, 2024年3月22日
        (re.compile(r'(\d{4})(\d{2})(\d{2})'), '%Y%m%d'),  # 20240322
        (re.compile(r'(\d{2})-(\d{2})\s+(\d{2}):(\d{2})'), None),  # 09-15 23:15，使用特殊处理
        (re.compile(r'(\d{2})[-/](\d{1,2})[-/](\d{1,2})'), '%y-%m-%d'),  # 24-03-22
        (re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*?\d{1,2}:\d{1,2}'), '%Y-%m-%d'),  # 2024-03-22 14:30
        (re.compile(r'([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{4})'), '%b %d %Y'),  # Nov 22, 2024
        (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})'), '%d-%m-%Y'),  # 22-11-2024
        (re.compile(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日'), '%Y-%m-%d'),  # 2024年3月22日
    ]
    
    # 相对时间模式
    RELATIVE_TIME_PATTERNS: List[Tuple[Pattern, Callable]] = [
        (re.compile(r'(\d+)\s*分钟前'), lambda m: datetime.now() - timedelta(minutes=int(m.group(1)))),
        (re.compile(r'(\d+)\s*小时前'), lambda m: datetime.now() - timedelta(hours=int(m.group(1)))),
        (re.compile(r'(\d+)\s*天前'), lambda m: datetime.now() - timedelta(days=int(m.group(1)))),
        (re.compile(r'昨天'), lambda m: datetime.now() - timedelta(days=1)),
        (re.compile(r'前天'), lambda m: datetime.now() - timedelta(days=2)),
        (re.compile(r'刚刚'), lambda m: datetime.now()),
    ]
    
    # 元数据选择器
    META_SELECTORS = {
        'title': [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'title'
        ],
        'date': [
            'meta[name="weibo:article:create_at"]',
            'meta[name="article:published_time"]',
            'meta[property="article:published_time"]',
            'meta[name="publishdate"]',
            'meta[name="pubdate"]',
            'time[datetime]'
        ]
    }
    
    # 通用选择���
    COMMON_SELECTORS = {
        'title': [
            'h1',
            '.article-title',
            '.title',
            '#title',
            'article h1',
            '.main-title'
        ],
        'date': [
            '.headerContent .ant-space-item span',  # 澎湃新闻日期选择器
            '.time',
            '.date',
            '.article-time',
            '.publish-time',
            '.article-date',
            '.news-date',
            '.post-date',
            '.entry-date',
            '.meta-date',
            'div.mb-6 div:first-child',
        ]
    }
    
    # 要跳过的元素
    SKIP_CLASSES = {'copyright', 'related', 'advertisement', 'share', 'comment'}
    SKIP_TAGS = {'script', 'style', 'iframe', 'form'}
    
    @classmethod
    @lru_cache(maxsize=128)
    def _extract_from_meta(cls, html: HTMLParser, field: str) -> str:
        """从meta标签提取内容，使用缓存提高性能"""
        for selector in cls.META_SELECTORS[field]:
            if elem := html.css_first(selector):
                content = elem.attributes.get('content', '') or elem.text()
                if content:
                    return content.strip()
        return ""
    
    @classmethod
    def extract_title(cls, html: HTMLParser, config: dict) -> str:
        """提取文章标题"""
        try:
            # 使用生成器优化提取逻辑
            extractors = (
                lambda: cls._extract_from_meta(html, 'title'),
                lambda: cls._extract_from_selectors(html, config.selectors.get('title', []) if hasattr(config, 'selectors') else []),
                lambda: cls._extract_from_selectors(html, getattr(config, 'title_selectors', [])),
                lambda: cls._extract_from_selectors(html, cls.COMMON_SELECTORS['title'])
            )
            
            for extractor in extractors:
                if title := extractor():
                    cleaned_title = cls._clean_title(title)
                    if cleaned_title:  # 确保清理后的标题不为空
                        return cleaned_title
            
            # 如果所有提取器都失败了，尝试从 og:title 获取
            if og_title := html.css_first('meta[property="og:title"]'):
                if title := og_title.attributes.get('content'):
                    return cls._clean_title(title)
            
            return ""
            
        except Exception as e:
            logging.getLogger(__name__).error(f"提取标题出错: {str(e)}", exc_info=True)
            return ""
    
    @classmethod
    def extract_publish_date(cls, html: HTMLParser, config: dict, url: str) -> str:
        """提取发布日期"""
        try:
            # 1. 从页面提取完整日期时间
            date = cls._extract_from_selectors(html, cls.COMMON_SELECTORS['date'])
            if date:
                normalized = DateExtractor.extract_date(date)
                if normalized:
                    return normalized
            
            # 2. 从meta标签提取
            date = cls._extract_from_meta(html, 'date')
            if date:
                normalized = DateExtractor.extract_date(date)
                if normalized:
                    return normalized
            
            # 3. 从配置的选择器提取(新格式)
            if hasattr(config, 'selectors'):
                selectors = getattr(config, 'selectors')
                if isinstance(selectors, dict) and 'date' in selectors:
                    date = cls._extract_from_selectors(html, [selectors['date']])
                    if date:
                        normalized = DateExtractor.extract_date(date)
                        if normalized:
                            return normalized
                    # 如果配置中指定了日期格式
                    if 'date_format' in selectors:
                        return datetime.strptime(date.strip(), selectors['date_format'])
            
            # 4. 从配置的选择器提取(旧格式)
            if hasattr(config, 'date_selectors'):
                date = cls._extract_from_selectors(html, config.date_selectors)
                if date:
                    return DateExtractor.extract_date(date)
            
            # 5. 从URL提取
            date = cls._extract_date_from_url(url)
            if date:
                return date
            
            assert False, f"提取日期失败 url: {url}"
            
        except Exception as e:
            logging.getLogger(__name__).error(f"提取日期出错: {str(e)}", exc_info=True)
            return None
    
    @classmethod
    def extract_arxiv_id(cls, html: HTMLParser) -> str:
        arxiv_link = html.css_first('a[href*="arxiv.org/abs"]')
        if arxiv_link:
            arxiv_url = arxiv_link.attributes['href']
            return arxiv_url.split('/')[-1]
        else:
            # 尝试从文本中提取
            for elem in html.css('*'):
                if text := elem.text():
                    if match := re.search(r'arXiv:\s*(\d+\.\d+)', text):
                        return match.group(1)
        return None

    @staticmethod
    def _extract_from_selectors(html: HTMLParser, selectors: List[str]) -> str:
        """从选择器���表中提取内容"""
        for selector in selectors:
            if elem := html.css_first(selector):
                text = elem.text()
                if text:
                    return text.strip()
        return ""
    
    @staticmethod
    def _clean_title(title: str) -> str:
        """
        清理标题文本
        
        Args:
            title: 原始标题文本
            
        Returns:
            str: 清理后的标题
        """
        if not title:
            return ""
        
        # 1. 基础清理
        title = re.sub(r'[\n\r\t]', ' ', title)
        title = ' '.join(title.split())  # 规范化空白字符
        
        # 2. 移除常见的网站名称后缀
        remove_patterns = [
            r'\s*[-_]\s*Papers\s+with\s+Code\s*$',
            r'\s*[-_]\s*\|\s*Papers\s+with\s+Code\s*$',
            r'\s*\|\s*Papers\s+with\s+Code\s*$',
            r'\s*[-_]\s*arXiv\s*$',
            r'\s*[-_]\s*GitHub\s*$',
            r'\s*[-_|]\s*.*?\.com\s*$',
            r'\s*[-_|]\s*.*?\.org\s*$',
        ]
        
        for pattern in remove_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # 3. 移除不合法的文件名字符
        title = re.sub(r'[<>:"/\\|?*]', '-', title)
        
        # 4. 限制标题长度，避免文件名过长
        if len(title) > 200:
            title = title[:197] + '...'
        
        return title.strip()
    
    @staticmethod
    def _extract_date_from_url(url: str) -> Optional[datetime]:
        """从URL中提取日期"""
        patterns = [
            r'/(\d{4})(\d{2})(\d{2})/',  # /20240322/
            r'/(\d{4})-(\d{2})-(\d{2})/',  # /2024-03-22/
            r'(\d{4})/(\d{1,2})/(\d{1,2})',  # 2024/3/22
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, url):
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
        return None
    
    @classmethod
    def extract_author(cls, html: HTMLParser, config: dict) -> str:
        """提取作者"""
        try:
            # 处理配置对象
            selectors = []
            if hasattr(config, 'selectors') and isinstance(config.selectors, dict):
                selectors = config.selectors.get('author', [])
            elif isinstance(config, dict):
                selectors = config.get('selectors', {}).get('author', [])
                
            if selectors:
                author = cls._extract_from_selectors(html, [selectors] if isinstance(selectors, str) else selectors)
                if author:
                    return author
            
            return ""
            
        except Exception as e:
            logging.getLogger(__name__).error(f"提取作者出错: {str(e)}", exc_info=True)
            return ""
    
    @classmethod
    def extract_category(cls, html: HTMLParser, config: dict) -> str:
        """提取文章分类"""
        try:
            # 检查配置中是否有分类选择器
            if not hasattr(config, 'category_selectors') or not config.category_selectors:
                return ""
            
            for selector in config.category_selectors:
                if elem := html.css_first(selector):
                    category = elem.text().strip()
                    # 清理分类名称
                    category = re.sub(r'[>\\/]', '-', category)
                    return category
            return ""
            
        except Exception as e:
            logging.getLogger(__name__).error(f"提取分类出错: {str(e)}", exc_info=True)
            return ""
    
    @classmethod
    def extract_content(cls, html: HTMLParser, config: dict) -> str:
        """提取文章正文"""
        try:
            # 处理配置对象
            selectors = []
            if hasattr(config, 'content_selectors'):
                selectors = config.content_selectors
            elif hasattr(config, 'selectors') and isinstance(config.selectors, dict):
                selectors = config.selectors.get('content', [])
            elif isinstance(config, dict):
                selectors = config.get('content_selectors', [])
            
            content_parts = []
            seen_content = set()
            
            if selectors:
                for selector in selectors:
                    if elements := html.css(selector):
                        for elem in elements:
                            if not cls._should_skip_element(elem):
                                text = elem.text().strip()
                                if text and text not in seen_content:
                                    seen_content.add(text)
                                    content_parts.append(text)
            
            return ArticleExtractor._clean_content("\n".join(content_parts))
            
        except Exception as e:
            logging.getLogger(__name__).error(f"提取正文出错: {str(e)}", exc_info=True)
            return ""
    
    @classmethod
    def _should_skip_element(cls, elem: HTMLParser) -> bool:
        """判断是否应该跳过个素"""
        # 跳过包含特定类名的元素
        if elem.attributes.get('class'):
            elem_classes = set(elem.attributes['class'].split())
            if elem_classes & cls.SKIP_CLASSES:
                return True
        
        # 跳过特定标签
        if elem.tag in cls.SKIP_TAGS:
            return True
        
        return False
    
    @classmethod
    def _clean_content(cls, content: str) -> str:
        """清理文章内容"""
        if not content:
            return ""
        
        # 1. 移除 JavaScript 代码块和样式
        js_patterns = [
            r'<script[\s\S]*?</script>',  # script标签及内容
            r'<style[\s\S]*?</style>',    # style标签及内容
            r'var\s+.*?;',                # 变量声明
            r'function\s*.*?{[\s\S]*?}',  # 函数定义
            r'\(sinaads\s*=.*?\);',       # 广告代码
            r'\(\s*function\s*\(\s*\)[\s\S]*?\}\s*\)\s*\(\s*\);', # 自执行函数
            r'\.[\w-]+\s*{[^}]*}',        # CSS类定义
            r'#[\w-]+\s*{[^}]*}',         # CSS ID定义
            r'//.*?(?:\n|$)',             # 单行注释
            r'/\*[\s\S]*?\*/',            # 多行注释
        ]
        
        for pattern in js_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE|re.IGNORECASE)
        
        # 2. 移除 HTML 标签和属性
        html_patterns = [
            r'<[^>]+>',                   # HTML标签
            r'&[a-zA-Z0-9]+;',           # HTML实体
            r'\.appendQr_wrap.*?(?:\n|$)', # 特定的HTML类
            r'\.mag_topad.*?(?:\n|$)',     # 广告相关类
            r'\.news_lt.*?(?:\n|$)',       # 新闻相关类
            r'\.vip-class.*?(?:\n|$)',     # VIP相关类
        ]
        
        for pattern in html_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # 3. 移除文章元信息
        meta_patterns = [
            r'\(编辑[：:]\s*.*?\)',
            r'\(记者[：:]\s*.*?\)',
            r'作者[：:]\s*.*?(?:\n|$)',
            r'来源[：:]\s*.*?(?:\n|$)',
            r'本来源.*?(?:\n|$)',
            r'原文链接.*?(?:\n|$)',
            r'关键字[：:]\s*.*?(?:\n|$)',
            r'责任编辑.*?(?:\n|$)',
            r'编辑[：:]\s*.*?(?:\n|$)',
            r'本文来源于.*?(?:\n|$)',
        ]
        
        for pattern in meta_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # 4. 移除导航和位置信息
        nav_patterns = [
            r'当前位置：.*?(?:\n|$)',
            r'返回首页.*?(?:\n|$)',
            r'举报.*?(?:\n|$)',
            r'分享到：.*?(?:\n|$)',
            r'相关专题：.*?(?:\n|$)',
            r'相关新闻：.*?(?:\n|$)',
            r'热门推荐.*?(?:\n|$)',
            r'合作伙伴.*?(?:\n|$)',
            r'友情链接.*?(?:\n|$)',
        ]
        
        for pattern in nav_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # 5. 移除广告和推广
        ad_patterns = [
            r'更多精彩内容.*?(?:\n|$)',
            r'关注.*?获取更多.*?(?:\n|$)',
            r'点击关注.*?(?:\n|$)',
            r'https?://\S+',             # URL
            r'APP专享.*?(?:\n|$)',
            r'扫描二维码.*?(?:\n|$)',
            r'海量资讯.*?(?:\n|$)',
            r'热门文章.*?(?:\n|$)',
            r'编辑推荐.*?(?:\n|$)',
        ]
        
        for pattern in ad_patterns:
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # 6. 处理段落
        paragraphs = content.split('\n')[:MAX_LINES_DOWNLOADED]
        unique_paragraphs = []
        seen_content = set()
        valid_content_found = False  # 标记是否找到有效正文内容
        empty_line_count = 0  # 连续空行计数
        
        for para in paragraphs:
            # 清理段落
            para = para.strip()
            para = re.sub(r'\s+', ' ', para)  # 合并多个空白字符
            
            # 计算连续空行
            if not para:
                empty_line_count += 1
                # 如果已经找到有效正文内容,且连续3个空行,终止处理
                if valid_content_found and empty_line_count >= 3:
                    break
                continue
            else:
                empty_line_count = 0
            
            # 跳过无效段落
            if len(para) < 2:
                continue
            
            # 跳过重复内容
            if para in seen_content:
                continue
            
            # 跳过疑似代码或样式内容
            if any(x in para.lower() for x in [
                'function', 'var ', 'document.', 'window.', 
                '{', '}', ';', 'javascript', '.css', '#',
                '@', '==', '++', '--'
            ]):
                continue
            
            # 跳过无意义的短句
            if len(para) < 10 and not re.search(r'[\u4e00-\u9fa5]', para):
                continue
            
            # 跳过纯数字或符号的行
            if re.match(r'^[\d\s!"#$%&\'()*+,-./:;<=>?@\[\]^_`{|}~。，、；：？！…—·ˉ¨〃々～‖∶＂＇｀｜〔〕〈〉《》「」『』．〖〗【】（）［］｛｝]+$', para):
                continue
            
            # 跳过导航菜单项
            if re.match(r'^[^，。！？\n]{1,10}$', para) and not re.search(r'[\u4e00-\u9fa5]{2,}', para):
                continue
            
            # 如果包含中文,标记为找到有效正文内容
            if re.search(r'[\u4e00-\u9fa5]', para):
                valid_content_found = True
            
            seen_content.add(para)
            unique_paragraphs.append(para)
        
        # 7. 重新组合内容，使用换行符分隔段落
        cleaned_text = '\n'.join(unique_paragraphs)
        
        # 8. 最后的清理
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # 移除多余的空行
        cleaned_text = re.sub(r'^\s+|\s+$', '', cleaned_text)   # 移除首尾空白
        
        return cleaned_text

class Article(ABC):
    """文章基类"""
    
    def __init__(self, url: str, html: str, config: dict = None):
        self.url = url
        # 统一使用 HTMLParser
        if isinstance(html, HTMLParser):
            self.html_parser = html
            self.html = html.html
        else:
            self.html = html
            self.html_parser = HTMLParser(html)
            
        self.config = config or {}
        
        # 基本属性
        self.title: str = ""
        self.publish_date: Optional[datetime] = None
        self.source: str = ""
        self.authors: List[str] = []
        self.summary: str = ""
        
        try:
            self.parse()
        except Exception as e:
            logging.getLogger(__name__).error(f"解析文章失败: {str(e)}")

    def parse(self):
        """解析文章，调用子类实现的_parse方法"""
        if hasattr(self, '_parse'):
            self._parse()
        else:
            raise NotImplementedError("子类必须实现_parse方法")

    @abstractmethod
    def _parse(self):
        """解析文章内容,子类必须实现此方法"""
        pass
    
    @abstractmethod
    def to_text(self) -> str:
        """将文章转换为文本格式,子类必须实现此方法"""
        pass

    @classmethod
    def from_html(cls, html: str, config: dict, url: str) -> Optional['Article']:
        """从HTML创建文章实例"""
        logger = logging.getLogger(__name__)
        try:
            # 创建文章实例
            article = cls(url=url, html=html, config=config)
            
            # 检查要字段是否解析成功
            if not article.title:
                logger.error(f"文章标题提取失败: {url}")
                return None
                
            if not article.publish_date:
                logger.warning(f"文章日期提取失败，跳过存档: {url}")
                return None
                
            if not article.summary:
                logger.error(f"文章内容提取失败: {url}")
                return None
            
            return article
            
        except Exception as e:
            logger.error(f"解析文章失败 {url}: {str(e)}", exc_info=True)
            return None
   
    def is_article_within_days(self, date_str: str, days: int = 7) -> bool:
        """检查文章日期是否在指定天数内"""
        try:
            article_date = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now()
            delta = today - article_date
            return delta.days <= days
        except ValueError:
            return False

    @staticmethod
    def is_within_retention_period(date: datetime, retention_days: int) -> bool:
        """
        检查文章是否在保留期限内
        
        Args:
            date_str: 文章日期，格式为 YYYY-MM-DD
            retention_days: 保留天数
            
        Returns:
            bool: 是否在保留期限内
        """
        today = datetime.now()
        delta = today - date
        return delta.days <= retention_days