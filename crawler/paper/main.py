import asyncio
import logging
import os
from crawler.paper.paper_crawler import PaperCrawler
from crawler.paper.config.sites import SITES
from crawler.paper.config.settings import LOGGING, ENABLED_SITES, LOG_DIR
import logging.config

async def main():
    """主函数"""
    try:
        # 创建日志目录
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # 配置日志
        logging.config.dictConfig(LOGGING)
        logger = logging.getLogger(__name__)
        
        logger.info("开始爬取论文...")
        
        # 为启用的站点创建爬虫实例并运行
        tasks = []
        for site_name in ENABLED_SITES:
            if site_name in SITES:
                logger.info(f"开始爬取 {site_name}")
                crawler = PaperCrawler(SITES[site_name])
                task = asyncio.create_task(crawler.crawl())
                tasks.append(task)
            else:
                logger.warning(f"未知的站点配置: {site_name}")
        
        if not tasks:
            logger.warning("没有启用任何站点")
            return
            
        # 等待所有爬虫完成
        await asyncio.gather(*tasks)
        
        logger.info("爬取完成")
        
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 