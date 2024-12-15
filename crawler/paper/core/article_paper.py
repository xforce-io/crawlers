from crawler.common.article import Article, ArticleExtractor
from datetime import datetime
from selectolax.parser import HTMLParser
import json
import re
import logging

class ArticlePaper(Article):
    """论文文章类"""
    
    def __init__(self, url: str, html: str, config: dict = None):
        self._arxiv_id = None  # 初始化arxiv_id
        super().__init__(url, html, config)  # 调用父类初始化
        
    def _parse(self):
        """解析论文内容"""
        if 'huggingface.co' in self.url:
            self._parse_huggingface()
        elif 'paperswithcode.com' in self.url:
            self._parse_paperswithcode()
        else:
            self._parse_generic()

    def _parse_huggingface(self):
        """解析 huggingface.co 页面"""
        self.title = ArticleExtractor.extract_title(self.html_parser, self.config)

        try:
            # 3. 如果还是没有日期，使用通用提取器
            self.publish_date = ArticleExtractor.extract_publish_date(self.html_parser, self.config, self.url)

            # 提取作者（如果之前没有提取到）
            if author := ArticleExtractor.extract_author(self.html_parser, self.config):
                self.authors = [author]
            
            # 提取摘要（如果之前没有提取到）
            if content := ArticleExtractor.extract_content(self.html_parser, self.config):
                self.summary = content
            else:
                # 尝试从特定元素提取
                abstract_selectors = [
                    'p.text-gray-700',
                    'div.pb-8.pr-4.md\\:pr-16 p',
                    'div.pb-8 p'
                ]
                
                for selector in abstract_selectors:
                    if element := self.html_parser.css_first(selector):
                        text = element.text().strip()
                        if text:
                            self.summary = text
                            break
            
            # 确保设置来源
            self.source = self.url

            self._arxiv_id = ArticleExtractor.extract_arxiv_id(self.html_parser)
                
        except Exception as e:
            logging.error(f"解析页面失败: {str(e)}", exc_info=True)
            # 设置默认值
            if not self.title:
                self.title = "未知标题"
            if not self.authors:
                self.authors = []
            if not self.summary:
                self.summary = "摘要提取失败"
            if not self.source:
                self.source = self.url

    def _parse_paperswithcode(self):
        """解析 paperswithcode.com 页面"""
        # 直接使用 self.html_parser
        self.title = ArticleExtractor.extract_title(self.html_parser, self.config) or \
                    self.html_parser.css_first('h1').text().strip()

        # 提取日期
        date_elem = self.html_parser.css_first('span.author-span')
        if date_elem:
            date_text = date_elem.text().strip()
            try:
                self.publish_date = datetime.strptime(date_text, '%d %b %Y')
            except ValueError:
                try:
                    self.publish_date = datetime.strptime(date_text, '%d %B %Y')
                except ValueError:
                    pass

        # 提取作者
        author = ArticleExtractor.extract_author(self.html_parser, self.config)
        if author:
            self.authors = [author]

        # 提取摘要/正文
        self.summary = ArticleExtractor.extract_content(self.html_parser, self.config) or \
                        self.html_parser.css_first('div.paper-abstract').text().strip()

        # 提取来源
        self.source = self.url

        # 提取arxiv ID
        self._arxiv_id = ArticleExtractor.extract_arxiv_id(self.html_parser)

    def _parse_generic(self):
        """通用解析方法"""
        # 创建 HTMLParser 对象
        html_parser = HTMLParser(self.html)
        
        # 使用 HTMLParser 对象调用提取方法
        self.title = ArticleExtractor.extract_title(html_parser, self.config)
        self.publish_date = ArticleExtractor.extract_publish_date(html_parser, self.config, self.url)
        
        author = ArticleExtractor.extract_author(html_parser, self.config)
        if author:
            self.authors = [author]
        
        self.summary = ArticleExtractor.extract_content(html_parser, self.config)
        
        # 提取来源
        self.source = self.url  # 使用完整URL作为来源
        
        # 提取arxiv_id（如果可能）
        if 'arxiv.org' in self.url:
            self._arxiv_id = self.url.split('/')[-1]

    def to_text(self) -> str:
        """转换为文本格式"""
        text_parts = [
            f"标题：{self.title}",
            f"发布日期：{self.publish_date.strftime('%Y-%m-%d') if self.publish_date else '未知'}",
            f"作者：{', '.join(self.authors)}",
        ]
        
        # 有在有arxiv_id时才添加下载地址
        if self._arxiv_id:
            text_parts.append(f"下载地址：https://arxiv.org/abs/{self._arxiv_id}")

        text_parts.append(f"摘要：{self.summary}")
            
        return '\n'.join(text_parts) 