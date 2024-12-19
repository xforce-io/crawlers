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
}