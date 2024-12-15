import aiofiles
import os
import asyncio
from typing import Dict, List, Optional, Set
import httpx
import logging
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from datetime import datetime, timedelta
import json

class RobotsParser:
    """Robots.txt 解析器"""
    
    def __init__(self, cache_dir: str):
        self.robots_rules: Dict[str, RobotFileParser] = {}
        self.cache_dir = cache_dir
        self.logger = logging.getLogger(__name__)
        self.failed_domains: Set[str] = set()  # 记录获取失败的域名
        self.cache_file = os.path.join(cache_dir, "robots_cache.json")
        self.cache_ttl = timedelta(days=7)  # 缓存有效期7天
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 加载缓存的失败记录
        self._load_failed_domains()
    
    def _load_failed_domains(self):
        """加载缓存的失败域名记录"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    # 检查缓存是否过期
                    for domain, timestamp in cache_data.items():
                        cache_time = datetime.fromtimestamp(timestamp)
                        if datetime.now() - cache_time < self.cache_ttl:
                            self.failed_domains.add(domain)
                        
        except Exception as e:
            self.logger.warning(f"加载robots缓存失败: {str(e)}")
    
    def _save_failed_domains(self):
        """保存失败域名记录到缓存"""
        try:
            cache_data = {
                domain: datetime.now().timestamp()
                for domain in self.failed_domains
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
                
        except Exception as e:
            self.logger.warning(f"保存robots缓存失败: {str(e)}")
    
    async def init_robots_rules(self, domains: List[str], timeout: float = 5.0):
        """初始化robots规则"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            tasks = []
            for domain in domains:
                if domain not in self.failed_domains:  # 跳过已知失败的域名
                    tasks.append(self._fetch_robots(client, domain))
            
            if tasks:  # 只在有任务时才等待
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # 保存失败记录
        self._save_failed_domains()
    
    async def _fetch_robots(self, client: httpx.AsyncClient, domain: str):
        """获取单个域名的robots.txt"""
        try:
            robots_url = f"https://{domain}/robots.txt"
            response = await client.get(robots_url)
            
            if response.status_code == 200:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
                self.robots_rules[domain] = parser
                self.logger.info(f"成功获取 robots.txt: {domain}")
            else:
                self.logger.warning(f"获取 robots.txt 失败 {domain}: HTTP {response.status_code}")
                self.failed_domains.add(domain)
                
        except Exception as e:
            self.logger.warning(f"获取 robots.txt 出错 {domain}: {str(e)}")
            self.failed_domains.add(domain)
    
    def is_url_allowed(self, url: str, domain: str) -> bool:
        """检查URL是否允许访问"""
        if domain in self.failed_domains:  # 对于失败的域名，默认允许访问
            return True
            
        parser = self.robots_rules.get(domain)
        if not parser:  # 如果没有规则，也默认允许
            return True
            
        return parser.can_fetch("*", url)