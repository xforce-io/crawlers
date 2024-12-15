CONCURRENT_TASKS = 5  # 每个站点的并发任务数
RETRY_TIMES = 3      # 请求重试次数
RETRY_INTERVAL = 2   # 重试间隔(秒)
REQUEST_TIMEOUT = 30 # 请求超时时间(秒)

CACHE_DIR = "./data/cache/"
ROBOTS_CACHE_DIR = "./data/cache/robots_cache"

DOWNLOADER_CONFIG = {
    'retry_times': RETRY_TIMES,
    'retry_interval': RETRY_INTERVAL,
    'timeout': REQUEST_TIMEOUT,
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1"
    }
}

# 爬虫类型配置
CRAWLER_TYPES = {
    'papers': {
        'storage_dir': 'paper',
        'file_suffix': '.html',
        'url_patterns': {
            'paperswithcode.com': {
                'pattern': 'https://paperswithcode.com/paper/{paper_id}',
                'has_domain_subdir': True
            },
            'huggingface.co': {
                'pattern': 'https://huggingface.co/papers/{paper_id}',
                'has_domain_subdir': True
            }
        }
    },
    'caijing': {
        'storage_dir': 'caijing',
        'file_suffix': '.txt',
        'url_patterns': {
            'default': {
                'pattern': '{original_filename}',  # 具体还原规则在实现中定义
                'has_domain_subdir': False
            }
        }
    }
}