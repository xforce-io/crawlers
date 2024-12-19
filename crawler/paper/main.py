import asyncio
import logging
from crawler.paper.config.settings import ENABLED_SITES
from crawler.paper.config.sites import SITES
from crawler.paper.paper_crawler import PaperCrawler, PaperCrawlerConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    logger.info("开始爬取论文...")
    
    # 创建配置
    config = PaperCrawlerConfig()
    
    # 从 SITES 配置中读取启用状态
    enabled_sites = []
    for site_name, site_config in SITES.items():
        if site_name not in ENABLED_SITES:
            continue
        
        config.enabled_sources[site_name] = site_config['enabled']
        if site_config['enabled']:
            enabled_sites.append(site_name)
            # 更新源配置
            config.source_configs[site_name].update({
                'start_url': site_config['start_url'],
                'max_pages': site_config['max_pages'],
                'page_size': site_config['page_size']
            })
    
    if not enabled_sites:
        logger.warning("没有启用任何站点")
        return
        
    logger.info(f"已启用的站点: {', '.join(enabled_sites)}")
    
    # 创建爬虫并开始爬取
    crawler = PaperCrawler(config)
    await crawler.crawl()
    
    # 输出结果统计
    logger.info(f"爬取完成，共获取 {len(crawler.papers)} 篇论文")

if __name__ == "__main__":
    asyncio.run(main()) 