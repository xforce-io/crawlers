from crawler.caijing.core.article_caijing import ArticleCaijing
from selectolax.parser import HTMLParser
from typing import Optional, Dict
from ...common.article import Article
import logging
from functools import lru_cache

class ArticleParser:
    """文章解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    @lru_cache(maxsize=128)
    def get_domain_config(self, url: str, configs: Dict) -> Optional[dict]:
        """获取URL对应的域名配置"""
        for domain, config in configs.items():
            if domain in url:
                return config
        return None
        
    def parse_article(self, html: HTMLParser, config: dict, url: str) -> Optional[Article]:
        """
        解析文章内容
        
        Args:
            html: HTML解析器实例
            config: 站点配置
            url: 文章URL
            
        Returns:
            Optional[Article]: 解析成功返回Article实例，失败返回None
            
        Raises:
            ValueError: 参数无效时抛出
        """
        try:
            # 参数验证
            if not html or not isinstance(html, HTMLParser):
                raise ValueError("无效的HTML解析器实例")
                
            if not config:
                raise ValueError("站点配置不能为空")
                
            if not url:
                raise ValueError("URL不能为空")
                
            # 检查必要的选择器是否存在
            required_selectors = ['title_selectors', 'content_selectors']
            for selector in required_selectors:
                if not hasattr(config, selector) or not getattr(config, selector):
                    self.logger.error(f"配置缺少必要的选择器: {selector}")
                    return None
                    
            # 解析文章
            article = ArticleCaijing.from_html(html, config, url)
            
            # 验证解析结果
            if article:
                if not article.title or not article.summary:
                    self.logger.warning(f"文章解析结果不完整: {url}")
                    return None
                    
                self.logger.info(f"成功解析文章: {article.title}")
                return article
            else:
                self.logger.warning(f"文章解析失败: {url}")
                return None
                
        except ValueError as e:
            self.logger.error(f"参数错误: {str(e)}")
            return None
            
        except Exception as e:
            self.logger.error(f"解析文章时发生错误: {str(e)}", exc_info=True)
            return None