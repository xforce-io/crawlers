from dataclasses import dataclass, field
from typing import List

@dataclass
class SiteConfig:
    """网站配置"""
    name: str       # 站点名称
    start_url: str  # 起始URL
    domain: str     # 主域名
    domains: List[str] = field(default_factory=list)  # 允许的域名列表
    article_pattern: str = r'\d{8}/\d+'  # 文章URL模式
    content_selectors: List[str] = field(default_factory=list)  # 正文选择器
    date_selectors: List[str] = field(default_factory=list)    # 日期选择器
    title_selectors: List[str] = field(default_factory=list)   # 标题选择器
    exclude_patterns: List[str] = field(default_factory=list)  # 排除的URL模式
    max_articles_per_day: int = 100  # 每日文章数限制
    enabled: bool = True            # 是否启用

SITE_CONFIGS = {
    'tonghuashun': {
        'name': '同花顺财经',
        'domains': [
            'news.10jqka.com.cn',
            'stock.10jqka.com.cn',
        ],
        'start_url': "https://news.10jqka.com.cn/",
        'domain': "10jqka.com.cn",
        'article_pattern': r'\d{8}/c\d+\.s?html',
        'content_selectors': [
            '.article_content',
            '#main',
            '.main-text'
        ],
        'date_selectors': [
            '.news-date',
            '.time'
        ],
        'title_selectors': [
            'h1',
            '.main-title'
        ],
        'exclude_patterns': [
            r'/live/',
            r'/special/',
            r'/author/'
        ]
    },
    'yicai': {
        'name': '第一财经',
        'start_url': "https://www.yicai.com/news/",
        'domain': "yicai.com",
        'article_pattern': r'news/\d+\.html',
        'content_selectors': [
            '#multi-text',
            '.m-txt',
            '.article-text'
        ],
        'date_selectors': [
            '.title p',
            '.author-info',
            '.article-info'
        ],
        'title_selectors': [
            'h1',
            '.article-title'
        ]
    },
    'caijing': {
        'name': '财经网',
        'start_url': "https://caijing.com.cn/",
        'domain': "caijing.com.cn",
        'domains': [
            'finance.caijing.com.cn',
            'economy.caijing.com.cn'
        ],
        'article_pattern': r'\d{8}/\d+\.s?html',
        'content_selectors': [
            'div.article-content',
            'div.text',
            '#the_content',
            '.content'
        ],
        'date_selectors': [
            'div.article-time',
            'span.time',
            'div.info',
            '.article-info'
        ],
        'title_selectors': [
            'h1',
            '.article-title'
        ],
        'exclude_patterns': [
            r'/tools/',
            r'/special/',
            r'/author/'
        ]
    },
    'sina': {
        'name': '新浪财经',
        'start_url': "https://finance.sina.com.cn/",
        'domain': "finance.sina.com.cn",
        'article_pattern': r'doc-[a-zA-Z0-9]+\.s?html',
        'content_selectors': [
            'div.article',
            '#artibody',
            '.main-content'
        ],
        'date_selectors': [
            '.date-source',
            '.article-info',
            '.time-source'
        ],
        'title_selectors': [
            'h1',
            '.main-title'
        ]
    },
    'caixin': {
        'name': '财新网',
        'start_url': "https://www.caixin.com/",
        'domain': "caixin.com",
        'domains': [
            'economy.caixin.com',
            'finance.caixin.com'
        ],
        'article_pattern': r'\d{4}-\d{2}-\d{2}/\d+\.html',
        'content_selectors': [
            '.article-content',
            '#Main_Content_Val',
            '.text'
        ],
        'date_selectors': [
            '.article-time',
            '.time',
            '.article-info time'
        ],
        'title_selectors': [
            'h1',
            '.article-title'
        ],
        'exclude_patterns': [
            r'\?',           # 排除带参数的URL
            r'100923808',    # 根据robots.txt排除特定模式
            r'/search/',
            r'/special/',
            r'/topics/'
        ]
    },
    'thepaper': {
        'name': '澎湃新闻',
        'start_url': "https://www.thepaper.cn/channel_25951",
        'domain': "thepaper.cn",
        'domains': [
            'www.thepaper.cn'
        ],
        'article_pattern': r'newsDetail_forward_\d+',
        'content_selectors': [
            '.index_cententWrap__Jv8jK',
            '.news_txt',
            '.news_part_limit'
        ],
        'date_selectors': [
            '.index_left__LfzyH .ant-space-item span',
            '.news_about',
            '.news_about_time'
        ],
        'title_selectors': [
            '.index_title__B8mhI',
            'h1.index_title__B8mhI',
            'h1.news_title',
            '.news_title',
            'meta[property="og:title"]'
        ],
        'exclude_patterns': [
            r'/about/',
            r'/privacy/',
            r'/contact/',
            r'/search',
            r'\?',
            r'/video/',
            r'/live/'
        ]
    }
} 