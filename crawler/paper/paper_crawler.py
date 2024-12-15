import os
from crawler.common.downloader import Downloader
from crawler.paper.config.settings import STORAGE_CONFIG, CRAWL_LIMITS
from crawler.config.settings import DOWNLOADER_CONFIG
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from crawler.common.url_cache_manager import URLCacheManager
from crawler.paper.core.article_paper import ArticlePaper
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import platform
from typing import Optional

class PageCount:
    """页面计数器"""
    def __init__(self):
        self.count = 0
        
    def add(self):
        self.count += 1

    def need_more(self) -> bool:
        return self.count < CRAWL_LIMITS['max_pages_per_source']

    def get(self) -> int:
        return self.count

class PaperCrawler:
    """论文爬虫基类"""
    
    def __init__(self, site_config: dict):
        self.config = site_config
        self.downloader = Downloader(**DOWNLOADER_CONFIG)
        
        # 确保存储目录存在
        os.makedirs(STORAGE_CONFIG['base_dir'], exist_ok=True)
        
        self.page_count = PageCount()
        self.url_cache = URLCacheManager('data/cache/url_cache.json')
        
        self.driver: Optional[webdriver.Chrome] = None
        
    def _setup_chrome_driver(self) -> Optional[webdriver.Chrome]:
        """设置并返回Chrome WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # 根据操作系统设置不同的参数
            system = platform.system().lower()
            if system == 'darwin':  # macOS
                # 对于 M1/M2 Mac
                if platform.processor() == 'arm':
                    chrome_options.add_argument('--disable-gpu')
                    chrome_options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            
            # 使用 webdriver_manager 自动���理 ChromeDriver
            service = Service(ChromeDriverManager().install())
            
            # 创建driver前先检查并清理可能存在的僵尸进程
            self._cleanup_zombie_processes()
            
            # 尝试创建driver
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            
            # 设置页面加载超时
            driver.set_page_load_timeout(30)
            
            return driver
            
        except WebDriverException as e:
            logging.error(f"ChromeDriver 初始化失败: {str(e)}")
            self._cleanup_chrome_processes()
            raise
        except Exception as e:
            logging.error(f"设置 Chrome 失败: {str(e)}")
            raise
    
    def _cleanup_zombie_processes(self):
        """清理可能存在的僵尸进程"""
        try:
            if platform.system().lower() != 'windows':
                os.system('pkill -f "(chrome)?(--headless)"')
                os.system('pkill -f chromedriver')
        except Exception as e:
            logging.warning(f"清理进程失败: {str(e)}")
    
    def _cleanup_chrome_processes(self):
        """清理所有Chrome相关进程"""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            # 根据操作系统执行清理
            system = platform.system().lower()
            if system == 'windows':
                os.system('taskkill /f /im chrome.exe')
                os.system('taskkill /f /im chromedriver.exe')
            else:
                os.system('pkill -f chrome')
                os.system('pkill -f chromedriver')
        except Exception as e:
            logging.warning(f"清理Chrome进程失败: {str(e)}")
    
    async def crawl(self):
        """开始爬取"""
        try:
            current_url = self.config['start_url']
            while current_url and self.page_count.need_more():
                try:
                    await self._crawl_page(current_url)
                except StopCrawling as e:
                    logging.info(f"爬取完成: {str(e)}")
                    break
                
        except Exception as e:
            logging.error(f"爬取过程出错: {str(e)}", exc_info=True)
        finally:
            await self.downloader.close()
            logging.info(f"共爬取 {self.page_count.get()} 个页面")

    async def _crawl_page(self, source: str):
        """爬取单个列表页"""
        if self.config['domain'] == 'huggingface.co':
            await self._crawl_huggingface_page(source)
        elif self.config['domain'] == 'paperswithcode.com':
            await self._crawl_paperswithcode_page(source)

    async def _crawl_huggingface_page(self, source: str):
        """爬取HuggingFace页面"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                if not self.driver:
                    self.driver = self._setup_chrome_driver()
                
                logging.info(f"开始爬取 {source}")
                self.driver.get(source)
                
                # 等待页面加载
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "DailyPapersPage"))
                    )
                except TimeoutException:
                    logging.warning("等待页面加载超时，继续处理")
                
                # 处理当前页面的论文
                while True:
                    try:
                        # 获取当前页面论文链接
                        paper_links = self.driver.find_elements(By.CSS_SELECTOR, "h3 a.line-clamp-3")
                        for link in paper_links:
                            try:
                                paper_url = link.get_attribute("href")
                                
                                if paper_url:
                                    # 确保是完整URL
                                    if not paper_url.startswith('http'):
                                        paper_url = f"https://huggingface.co{paper_url}"
                                    
                                    logging.info(f"Found paper URL: {paper_url}")
                                    await self.crawl_paper(paper_url)
                                    
                                    if not self.page_count.need_more():
                                        logging.info("已达到爬取限制，停止爬取")
                                        return
                                        
                            except StopCrawling:
                                return  # 直接返回，不继续处理
                            except Exception as e:
                                logging.error(f"处理论文链接失败: {str(e)}", exc_info=True)
                                continue
                        
                        # 查找Previous按钮
                        try:
                            prev_btn = self.driver.find_element(
                                By.XPATH, 
                                "//a[contains(@href, '/papers?date=')]"
                            )
                            prev_url = prev_btn.get_attribute("href")
                            if prev_url:
                                logging.info(f"Moving to previous page: {prev_url}")
                                self.driver.get(prev_url)
                                # 等待新页面加载
                                WebDriverWait(self.driver, 10).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "DailyPapersPage"))
                                )
                                time.sleep(2)  # 额外等待以确保内容加载完成
                            else:
                                break
                        except Exception as e:
                            logging.error(f"获取上一页失败: {str(e)}")
                            break
                    
                    except StopCrawling:
                        return  # 直接返回，不继续处理
                    except Exception as e:
                        logging.error(f"处理页面失败: {str(e)}")
                        break
                
                return  # 成功完成爬取
                
            except WebDriverException as e:
                logging.error(f"Chrome错误 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
                self._cleanup_chrome_processes()
                self.driver = None
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                else:
                    raise
                    
            except Exception as e:
                logging.error(f"爬取页面失败: {str(e)}")
                raise
    
    async def _crawl_paperswithcode_page(self, source: str):
        """爬取PaperWithCode页面"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            
            driver.get(source)
            
            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "paper-card"))
            )

            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                # 滚动到底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 等待内容加载
                time.sleep(2)
                
                # 计算新的滚动高度
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                try:
                    # 获取当前页面所有论文
                    papers = driver.find_elements(By.CLASS_NAME, "paper-card")
                    for paper in papers:
                        try:
                            paper_url = paper.find_element(By.TAG_NAME, "a").get_attribute("href")
                            await self.crawl_paper(paper_url)
                            
                            if not self.page_count.need_more():
                                logging.info("已达到爬取限制，停止爬取")
                                return
                                
                        except StopCrawling:
                            return  # 直接返回，不继续处理
                        except Exception as e:
                            logging.error(f"处理论文链接失败: {str(e)}")
                            continue

                except StopCrawling:
                    return  # 直接返回，不继续处理
                except Exception as e:
                    logging.error(f"获取论文列表失败: {str(e)}")
                    break

                # 如果高度没有变化,说明已到底部
                if new_height == last_height:
                    break
                last_height = new_height

        except TimeoutException:
            logging.error(f"页面加载超时: {source}")
        except Exception as e:
            logging.error(f"爬取页面失败: {str(e)}")
        finally:
            driver.quit()
        
    async def crawl_paper(self, url: str):
        """爬取单个论文详情页"""
        try:
            if self.url_cache.has_url(self.config['domain'], url):
                logging.debug(f"URL已存在于缓存，跳过: {url}")
                return
            
            # 对于 huggingface.co 使用 selenium 来获取动态内容
            if 'huggingface.co' in url:
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument('--headless')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(
                        service=service,
                        options=chrome_options
                    )
                    
                    driver.get(url)
                    # 等待页面加载完成
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "title"))
                    )
                    
                    html_content = driver.page_source
                    driver.quit()
                    
                except Exception as e:
                    logging.error(f"Selenium获取页面失败 {url}: {str(e)}")
                    return
                    
            else:
                # 其他网站使用 downloader
                try:
                    response = await self.downloader.get(url)
                    if not response or not response.text:
                        logging.error(f"获取页面内容失败: {url}")
                        return
                    
                    if response.status_code != 200:
                        logging.error(f"页面请求失败 {url}, ���态码: {response.status_code}")
                        return
                        
                    html_content = response.text
                        
                except Exception as e:
                    logging.error(f"下载页面失败 {url}: {str(e)}")
                    return
            
            try:
                # 创建论文对象并解析
                article = ArticlePaper(
                    url=url, 
                    html=html_content,
                    config=self.config
                )
            except Exception as e:
                logging.error(f"解析论文失败 {url}: {str(e)}")
                return
            
            if not article.publish_date:
                logging.warning(f"无法从页面提取日期 {url}")
                return
            
            if not article.title:
                logging.warning(f"无法从页面提取标题 {url}")
                return
            
            # 创建存储目录
            try:
                date_str = article.publish_date.strftime(STORAGE_CONFIG['date_format'])
                date_dir = os.path.join(
                    STORAGE_CONFIG['base_dir'],
                    date_str,
                    self.config['domain']
                )
                os.makedirs(date_dir, exist_ok=True)
                
                # 生成文件名
                safe_title = "".join(x for x in article.title if x.isalnum() or x in (' ', '-', '_'))[:100]
                if not safe_title:  # 确保文件名不为空
                    safe_title = "untitled"
                filename = f"{safe_title}.txt"
                filepath = os.path.join(date_dir, filename)
                
                if not os.path.exists(filepath):
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(article.to_text())
                    
                    self.page_count.add()
                    logging.info(f"已保存文件: {filepath}")
                    self.url_cache.add_url(self.config['domain'], url)
                    
            except Exception as e:
                logging.error(f"保存文件失败 {url}: {str(e)}")
                return
            
        except StopCrawling:
            raise
        except Exception as e:
            logging.error(f"处理页面失败 {url}: {str(e)}", exc_info=True)

    def __del__(self):
        """析构函数，确保清理资源"""
        self._cleanup_chrome_processes()

# 添加自定义异常类
class StopCrawling(Exception):
    """达到爬取限制时抛出的异常"""
    pass