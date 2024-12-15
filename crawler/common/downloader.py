import httpx
import asyncio
import anyio
from typing import Optional
from urllib.parse import urlparse
import logging
import random

class DownloaderError(Exception):
    """下载器异常基类"""
    pass

class NetworkError(DownloaderError):
    """网络相关错误"""
    pass

class SSLError(NetworkError):
    """SSL证书错误"""
    pass

class Downloader:
    """下载器类,处理HTTP请求"""
    
    def __init__(
            self, 
            retry_times: int, 
            retry_interval: int,
            timeout: int,
            headers: dict):
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self.session: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)
        
        # 添加连接池限制和超时设置
        self.limits = httpx.Limits(
            max_keepalive_connections=10,  # 减少保持连接数
            max_connections=50,            # 减少最大连接数
            keepalive_expiry=30.0          # 增加连接保持时间
        )
        
        self.timeout = httpx.Timeout(
            connect=timeout,    # 连接超时增加到10秒
            read=timeout,       # 读取超时增加到30秒
            write=timeout,      # 写入超时增加到30秒
            pool=timeout        # 连接池等待超时增加到10秒
        )
        
        # 添加DNS缓存
        self.dns_cache = {}
        
        # 添加自定义headers
        self.default_headers = headers
        
    def _get_ip_from_domain(self, domain: str) -> Optional[str]:
        """从域名获取IP地址"""
        import socket
        try:
            if domain in self.dns_cache:
                return self.dns_cache[domain]
            
            ip = socket.gethostbyname(domain)
            self.dns_cache[domain] = ip
            return ip
        except Exception as e:
            self.logger.debug(f"DNS解析失败 {domain}: {str(e)}")
            return None
            
    async def get_session(self) -> httpx.AsyncClient:
        """获取或创建HTTP会话"""
        if not self.session or self.session.is_closed:
            self.session = httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                headers=self.default_headers,
                follow_redirects=True,
                verify=False,      # 禁用 SSL 验证
                http2=False,       # 禁用 HTTP/2，使用 HTTP/1.1
                trust_env=False,   # 不使用环境变量的代理设置
                transport=httpx.AsyncHTTPTransport(
                    retries=1,     # 传输层重试
                    verify=False,
                    http2=False
                )
            )
        return self.session
        
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.is_closed:
            await self.session.aclose()
            self.session = None
            
    def _validate_url(self, url: str) -> bool:
        """验证URL格式是否有效"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
            
    async def get(self, url: str, **kwargs) -> Optional[httpx.Response]:
        """发送GET请求"""
        last_error = None
        
        # 验证URL格式
        if not self._validate_url(url):
            error_msg = f"无效的URL格式: {url}"
            self.logger.error(error_msg)
            raise NetworkError(error_msg)
            
        # 解析域名
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # 尝试DNS解析
        if not self._get_ip_from_domain(domain):
            error_msg = f"DNS解析失败: {domain}"
            self.logger.error(error_msg)
            raise NetworkError(error_msg)
        
        # 增加随机延迟的范围
        await asyncio.sleep(random.uniform(1.0, 3.0))  # 增加延迟时间
        
        for attempt in range(self.retry_times):
            try:
                # 确保每次重试都使用新的会话
                if self.session:
                    await self.close()
                
                session = await self.get_session()
                
                # 添加额外的headers
                headers = kwargs.pop('headers', {})
                headers.update({
                    'Host': domain,
                    'Referer': f"{parsed.scheme}://{domain}/"
                })
                
                response = await session.get(
                    url, 
                    headers={**self.default_headers, **headers},
                    **kwargs
                )
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException as e:
                error_msg = f"连接超时 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP错误 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except (httpx.ReadError, httpx.WriteError) as e:
                error_msg = f"传输错误 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except (anyio.ClosedResourceError, httpx.LocalProtocolError) as e:
                error_msg = f"协议错误 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except httpx.ConnectError as e:
                error_msg = f"连接错误 (尝试 {attempt + 1}/{self.retry_times}): {url} - {str(e)}"
                self.logger.warning(error_msg)
                last_error = NetworkError(error_msg)
                
            except Exception as e:
                error_msg = f"未知错误 (尝试 {attempt + 1}/{self.retry_times}): {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                last_error = DownloaderError(error_msg)
                
            finally:
                # 每次请求后关闭会话
                await self.close()
            
            # 在重试前使用指数退避，并增加随机因子
            if attempt < self.retry_times - 1:
                delay = self.retry_interval * (2 ** attempt) + random.uniform(0.1, 1.0)
                await asyncio.sleep(delay)
        
        # 所有重试都失败了，抛出最后一个错误
        if last_error:
            raise last_error
            
        return None