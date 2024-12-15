from crawler.common.downloader import Downloader
from crawler.common.cache_manager import CacheManager
from crawler.common.robots_parser import RobotsParser
from crawler.config.settings import CACHE_DIR, DOWNLOADER_CONFIG, ROBOTS_CACHE_DIR

class CaijingSpider:
    def __init__(self):
        self.downloader = Downloader(**DOWNLOADER_CONFIG)
        self.cache = CacheManager(cache_dir=CACHE_DIR)
        self.robots = RobotsParser(cache_dir=ROBOTS_CACHE_DIR)
        
    def crawl(self, url: str):
        if not self.robots.can_fetch(url):
            return None
            
        # 先检查缓存
        content = self.cache.get(url)
        if content:
            return content
            
        # 下载内容
        content = self.downloader.get(url)
        if content:
            self.cache.set(url, content)
        return content 