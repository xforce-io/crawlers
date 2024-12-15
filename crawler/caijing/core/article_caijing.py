from crawler.common.article import Article, ArticleExtractor
from datetime import datetime
import logging
from bs4 import BeautifulSoup

class ArticleCaijing(Article):
    """财经文章类"""
    
    def _parse(self):
        """解析财经文章"""
        try:
            # 直接使用 self.html_parser
            self.title = ArticleExtractor.extract_title(self.html_parser, self.config)
            
            self.publish_date = ArticleExtractor.extract_publish_date(self.html_parser, self.config, self.url)
            
            self.source = self.url  # 从URL提取域名
            
            author = ArticleExtractor.extract_author(self.html_parser, self.config)
            self.authors = [author] if author else []
            
            # 提取正文内容作为摘要
            self.summary = ArticleExtractor.extract_content(self.html_parser, self.config)
            
        except Exception as e:
            logging.error(f"解析财经文章失败: {str(e)}")
    
    def to_text(self) -> str:
        """转换为文本格式"""
        text_parts = [
            f"标题：{self.title}",
            f"发布日期：{self.publish_date.strftime('%Y-%m-%d') if self.publish_date else '未知'}",
            f"来源：{self.source}",
            f"网站：{self.url.split('/')[2]}"
        ]
        
        if self.authors:
            text_parts.append(f"作者：{', '.join(self.authors)}")
        
        text_parts.extend(["", "正文：", self.summary])
        
        return "\n".join(text_parts) 