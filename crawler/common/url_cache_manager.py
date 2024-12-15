import json
import os
from typing import Dict, List, Set
import logging

class URLCacheManager:
    """URL缓存管理器,用于防止重复爬取"""
    
    def __init__(self, cache_file: str):
        """初始化缓存管理器
        
        Args:
            cache_file: 缓存文件路径,如 'data/cache/url_cache.json'
        """
        self.cache_file = cache_file
        self.cache: Dict[str, Set[str]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 将JSON中的列表转换为集合
                    self.cache = {
                        domain: set(urls) for domain, urls in data.items()
                    }
                logging.info(f"已加载URL缓存: {self.cache_file}")
            except Exception as e:
                logging.error(f"加载缓存文件失败: {str(e)}")
                self.cache = {}
        else:
            self.cache = {}
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            # 将集合转换为列表以便JSON序列化
            data = {
                domain: list(urls) for domain, urls in self.cache.items()
            }
            # 确保缓存目录存在
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"已保存URL缓存: {self.cache_file}")
        except Exception as e:
            logging.error(f"保存缓存文件失败: {str(e)}")
    
    def add_url(self, domain: str, url: str):
        """添加URL到缓存
        
        Args:
            domain: 网站域名
            url: 要缓存的URL
        """
        if domain not in self.cache:
            self.cache[domain] = set()
        self.cache[domain].add(url)
        self.save_cache()
    
    def has_url(self, domain: str, url: str) -> bool:
        """检查URL是否已经在缓存中
        
        Args:
            domain: 网站域名
            url: 要检查的URL
            
        Returns:
            bool: URL是否已存在于缓存
        """
        return domain in self.cache and url in self.cache[domain] 