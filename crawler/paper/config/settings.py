"""
爬虫通用设置
"""

# 基础设置
from crawler.config import settings

BASE_DIR = 'data/paper'
LOG_DIR = f'log/'

# 缓存设置
CACHE_CONFIG = {
    'enabled': True,
    'expire_time': 86400  # 24小时
}

# 并发设置
CONCURRENT_REQUESTS = 3
DOWNLOAD_DELAY = 1.0

# 输出设置
OUTPUT_CONFIG = {
    'format': 'json',
    'path': f'{BASE_DIR}/output'
}

# 日志设置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': f'{LOG_DIR}/crawler.log',
            'formatter': 'standard',
            'encoding': 'utf-8'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'detailed'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

# 爬取限制
CRAWL_LIMITS = {
    'max_pages_per_source': 150,  # 每个来源最多抓取的页数
}

# 存储设置
STORAGE_CONFIG = {
    'base_dir': 'data/papers',  # 论文存储基础目录
}

# 在settings.py中添加启用的站点配置
ENABLED_SITES = ['arxiv']  # 默认只启用paperswithcode 

# 下载器配置继承自全局配置
DOWNLOADER_CONFIG = {
    **settings.DOWNLOADER_CONFIG,
}
