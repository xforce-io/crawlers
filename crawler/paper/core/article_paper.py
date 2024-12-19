from datetime import datetime
import logging
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from crawler.common.article import Article
import re

class ArticlePaper(Article):
    """论文文章基类"""
    
    def __init__(self, url: str = "", html: str = "", config: dict = None):
        """初始化论文对象"""
        super().__init__(url, html, config)
        self.source: str = None
        self.authors: List[str] = []
        self.pdf_url: str = None
        self.paper_id: str = None
        self.comments: str = None
        self.subjects: str = None
    
    def _parse(self):
        """实现父类的抽象方法
        
        论文类主要通过 parse_item 方法解析单个条目，
        这里实现一个空的 _parse 方法以满足抽象类的要求
        """
        pass
    
    def parse_item(self, item: BeautifulSoup) -> Optional['ArticlePaper']:
        """解析单个论文条目，子类必须实现此方法"""
        raise NotImplementedError
    
    def _is_valid(self) -> bool:
        """验证解析结果是否有效"""
        return bool(self.title and self.url)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        base_dict = super().to_dict() if hasattr(super(), 'to_dict') else {}
        paper_dict = {
            'source': self.source,
            'authors': self.authors,
            'pdf_url': self.pdf_url,
            'paper_id': self.paper_id,
            'comments': self.comments,
            'subjects': self.subjects
        }
        return {**base_dict, **paper_dict}
    
    def to_text(self) -> str:
        """转换为文本格式"""
        text_parts = [
            f"标题：{self.title}",
            f"作者：{', '.join(self.authors) if self.authors else '未知'}",
            f"发布日期：{self.publish_date.strftime('%Y-%m-%d') if self.publish_date else '未知'}"
        ]
        
        if self.pdf_url:
            text_parts.append(f"下载地址：{self.pdf_url}")
        if self.summary:
            text_parts.append(f"摘要：{self.summary}")
        if self.comments:
            text_parts.append(f"备注：{self.comments}")
        if self.subjects:
            text_parts.append(f"主题：{self.subjects}")
            
        return '\n'.join(text_parts)

class ArxivPaper(ArticlePaper):
    """Arxiv论文解析器"""
    
    def __init__(self, url: str = "", html: str = "", config: dict = None):
        super().__init__(url, html, config)
        self.source = 'arxiv'
        self.downloader = None  # 将在parse_item时设置
    
    async def parse_item(self, item: BeautifulSoup, downloader) -> Optional['ArxivPaper']:
        """解析arxiv论文条目"""
        try:
            self.downloader = downloader
            # 提取标题
            if title_div := item.find('div', class_='list-title'):
                self.title = title_div.text.replace('Title:', '').strip()
            
            # 提取作者
            if authors_div := item.find('div', class_='list-authors'):
                self.authors = [a.text.strip() for a in authors_div.find_all('a')]
            
            # 提取链接
            if dt := item.find_previous_sibling('dt'):
                if abs_link := dt.find('a', href=True, title='Abstract'):
                    self.url = f"https://arxiv.org{abs_link['href']}"
                    self.paper_id = abs_link['id']
                
                if pdf_link := dt.find('a', title='Download PDF'):
                    self.pdf_url = f"https://arxiv.org{pdf_link['href']}"
            
            # 提取评论信息
            if comments_div := item.find('div', class_='list-comments'):
                self.comments = comments_div.text.replace('Comments:', '').strip()
            
            # 提取主题领域
            if subjects_div := item.find('div', class_='list-subjects'):
                self.subjects = subjects_div.text.replace('Subjects:', '').strip()
            
            # 获取详细信息
            if self.url:
                await self._fetch_details()
            
            return self if self._is_valid() else None
            
        except Exception as e:
            logging.error(f"解析Arxiv论文失败: {str(e)}", exc_info=True)
            return None
    
    async def _fetch_details(self):
        """获取论文详细信息"""
        try:
            if not self.downloader:
                logging.error("下载器未初始化")
                return
            
            response = await self.downloader.get(self.url)
            if not response:
                logging.error(f"获取论文详情失败: {self.url}")
                return
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取摘要
            if abstract_div := soup.find('blockquote', class_='abstract'):
                self.summary = abstract_div.text.replace('Abstract:', '').strip()
            
            # 提取发布日期
            if date_span := soup.find('div', class_='submission-history'):
                date_text = date_span.text
                # 提取第一次提交的日期
                if match := re.search(r'\[v1\]\s+(\w+,\s+\d+\s+\w+\s+\d{4})', date_text):
                    date_str = match.group(1)
                    try:
                        self.publish_date = datetime.strptime(date_str, '%a, %d %b %Y')
                    except ValueError:
                        logging.error(f"日期解析失败: {date_str}")
            
            # 提取其他可能的元数据
            if meta_div := soup.find('div', class_='metatable'):
                # 处理DOI等信息
                pass
                
        except Exception as e:
            logging.error(f"获取论文详情失败: {str(e)}", exc_info=True)

class HuggingFacePaper(ArticlePaper):
    """HuggingFace论文解析器"""
    
    def __init__(self, url: str = "", html: str = "", config: dict = None):
        super().__init__(url, html, config)
        self.source = 'huggingface'
    
    def parse_item(self, item: BeautifulSoup) -> Optional['HuggingFacePaper']:
        """解析 HuggingFace 论文条目"""
        try:
            # 提取标题和URL
            if title_elem := item.select_one('h3 a.line-clamp-3'):
                self.title = title_elem.text.strip()
                if url := title_elem.get('href'):
                    self.url = f"https://huggingface.co{url}" if not url.startswith('http') else url
            
            # 提取摘要
            for selector in ['p.text-gray-700', 'div.pb-8.pr-4.md\\:pr-16 p', 'div.pb-8 p']:
                if abstract_elem := item.select_one(selector):
                    self.summary = abstract_elem.text.strip()
                    break
            
            # 提取作者
            if author_elem := item.select_one('div.author-info'):
                self.authors = [a.text.strip() for a in author_elem.select('a')]
            
            # 提取PDF链接
            if pdf_elem := item.select_one('a[href$=".pdf"]'):
                self.pdf_url = pdf_elem['href']
            
            return self if self._is_valid() else None
            
        except Exception as e:
            logging.error(f"解析HuggingFace论文失败: {str(e)}", exc_info=True)
            return None

class PaperWithCodePaper(ArticlePaper):
    """PapersWithCode论文解析器"""
    
    def __init__(self, url: str = "", html: str = "", config: dict = None):
        super().__init__(url, html, config)
        self.source = 'paperswithcode'
    
    def parse_item(self, item: BeautifulSoup) -> Optional['PaperWithCodePaper']:
        """解析 PapersWithCode 论文条目"""
        try:
            # 提取标题和URL
            if title_elem := item.select_one('h1, div.paper-title'):
                self.title = title_elem.text.strip()
                if url_elem := title_elem.find_parent('a'):
                    url = url_elem['href']
                    self.url = f"https://paperswithcode.com{url}" if not url.startswith('http') else url
            
            # 提取日期
            if date_elem := item.select_one('span.author-span'):
                date_text = date_elem.text.strip()
                for fmt in ['%d %b %Y', '%d %B %Y']:
                    try:
                        self.publish_date = datetime.strptime(date_text, fmt)
                        break
                    except ValueError:
                        continue
            
            # 提取作者
            if authors_elem := item.select('div.author-name'):
                self.authors = [author.text.strip() for author in authors_elem]
            
            # 提取摘要
            if abstract_elem := item.select_one('div.paper-abstract'):
                self.summary = abstract_elem.text.strip()
            
            # 提取PDF链接
            if pdf_elem := item.select_one('a[href*="arxiv.org/pdf"]'):
                self.pdf_url = pdf_elem['href']
            
            return self if self._is_valid() else None
            
        except Exception as e:
            logging.error(f"解析PapersWithCode论文失败: {str(e)}", exc_info=True)
            return None