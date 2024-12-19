import logging
import random
import asyncio
import httpx
from typing import Optional, Dict
from urllib.parse import urlparse

class NetworkError(Exception):
    """网络错误"""
    pass

class Downloader:
    """异步下载器"""
    
    def __init__(self, retry_times: int = 3, retry_interval: int = 1, timeout: int = 10, **kwargs):
        """初始化下载器
        
        Args:
            retry_times: 重试次数
            retry_interval: 重试间隔（秒）
            timeout: 超时时间（秒）
            **kwargs: 其他配置参数（将被忽略）
        """
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)
        
        # 默认请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # 连接池配置
        self.limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=50,
            keepalive_expiry=30.0
        )
        
        # 超时配置
        self.timeout_config = httpx.Timeout(
            connect=timeout,
            read=timeout,
            write=timeout,
            pool=timeout
        )
    
    async def get_session(self) -> httpx.AsyncClient:
        """获取或创建会话"""
        if self.session is None or self.session.is_closed:
            self.session = httpx.AsyncClient(
                limits=self.limits,
                timeout=self.timeout_config,
                follow_redirects=True
            )
        return self.session
    
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.is_closed:
            await self.session.aclose()
            self.session = None
    
    async def get(self, url: str, **kwargs) -> Optional[httpx.Response]:
        """发送GET请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            Optional[httpx.Response]: 响应对象，失败返回None
            
        Raises:
            NetworkError: 网络相关错误
        """
        headers = {**self.headers}  # 复制默认headers
        
        # 添加域名相关的headers
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain:
            headers.update({
                'Host': domain,
                'Referer': f"{parsed.scheme}://{domain}/"
            })
        
        last_error = None
        for attempt in range(self.retry_times):
            try:
                session = await self.get_session()
                response = await session.get(url, headers=headers, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException as e:
                error_msg = f"连接超时 (尝试 {attempt + 1}/{self.retry_times}): {url}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP错误 {e.response.status_code} (尝试 {attempt + 1}/{self.retry_times}): {url}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except Exception as e:
                error_msg = f"请求失败 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.error(error_msg)
                last_error = NetworkError(error_msg)
            
            finally:
                await self.close()
            
            # 重试延迟（指数退避 + 随机因子）
            if attempt < self.retry_times - 1:
                delay = self.retry_interval * (2 ** attempt) + random.uniform(0.1, 1.0)
                await asyncio.sleep(delay)
        
        if last_error:
            raise last_error
        return None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()