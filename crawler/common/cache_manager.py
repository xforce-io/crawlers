import os
import json
from datetime import datetime
from typing import Dict, Set
import logging

class CacheManager:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self.logger = logging.getLogger(__name__)
        self.url_cache: Dict[str, Set[str]] = {}  # domain -> set of cached URLs
        self.cache_file = os.path.join(cache_dir, "url_cache.json")
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 加载现有缓存
        self._load_cache()
        
    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # 将JSON中的列表转换为集合
                    self.url_cache = {
                        domain: set(urls) 
                        for domain, urls in cache_data.items()
                    }
                self.logger.info(f"已加载缓存，共 {sum(len(urls) for urls in self.url_cache.values())} 个URL")
        except Exception as e:
            self.logger.error(f"加载缓存失败: {str(e)}")
            self.url_cache = {}
            
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            # 将集合转换为列表以便JSON序列化
            cache_data = {
                domain: list(urls) 
                for domain, urls in self.url_cache.items()
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            self.logger.debug("缓存已保存到文件")
        except Exception as e:
            self.logger.error(f"保存缓存失败: {str(e)}")
            
    def init_domain(self, domain: str):
        """初始化域名的缓存"""
        if domain not in self.url_cache:
            self.url_cache[domain] = set()
            
    def is_cached(self, url: str, domain: str) -> bool:
        """检查URL是否已经缓存"""
        return url in self.url_cache.get(domain, set())
        
    def add_to_cache(self, url: str, domain: str):
        """添加URL到缓存"""
        if domain not in self.url_cache:
            self.url_cache[domain] = set()
        self.url_cache[domain].add(url)
        
        # 定期保存缓存（比如每100个URL保存一次）
        if sum(len(urls) for urls in self.url_cache.values()) % 100 == 0:
            self._save_cache()
            
    def get_cache_size(self, domain: str = None) -> int:
        """获取缓存大小"""
        if domain:
            return len(self.url_cache.get(domain, set()))
        return sum(len(urls) for urls in self.url_cache.values()) 