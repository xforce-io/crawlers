import asyncio
from crawler.caijing.config.settings import MAX_ARTICLES, MAX_PER_SITE, SAVE_DIR
from crawler.caijing.config.site_configs import SITE_CONFIGS, SiteConfig
from crawler.caijing.core.crawler import MultiSiteCrawler
import logging

from crawler.config.settings import CONCURRENT_TASKS

async def main():
    """程序入口"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,  # 改为 DEBUG 级别
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 配置要爬取的站点
    enabled_sites = {
        'tonghuashun': True,   # 启用同花顺
        'sina': True,          # 启用新浪财经
        'yicai': True,         # 启用第一财经
        'caijing': True,        # 启用财经网
        'caixin': True,        # 启用财新网
        'thepaper': True        # 启用澎湃新闻
    }
    
    # 更新站点配置的启用状态
    site_configs = {
        name: SiteConfig(**config) if isinstance(config, dict) else config
        for name, config in SITE_CONFIGS.items()
        if name in enabled_sites  # 只包含在 enabled_sites 中定义的站点
    }
    
    # 检查是否有可用的站点配置
    if not site_configs:
        raise ValueError("没有找到任何可用的站点配置，请检查 SITE_CONFIGS 是否包含已启用的站点")
    
    for site_name, enabled in enabled_sites.items():
        if site_name in site_configs:
            site_configs[site_name].enabled = enabled
    
    # 添加调试信息
    print("可用的站点配置:")
    for name, config in site_configs.items():
        print(f"站点: {name}, enabled: {config.enabled}")
        
    # 验证至少有一个启用的站点
    enabled_count = sum(1 for config in site_configs.values() if config.enabled)
    if enabled_count == 0:
        raise ValueError("没有启用任何站点，请至少启用一个站点")
    
    # 设置爬取参数
    crawler_config = {
        'max_articles': MAX_ARTICLES,      # 总文章数上限
        'max_per_site': MAX_PER_SITE,      # 每个站点的文章数上限
        'save_dir': SAVE_DIR,  # 保存目录
        "concurrent_tasks": CONCURRENT_TASKS
    }
    
    # 创建爬虫实例并开始爬取
    crawler = MultiSiteCrawler(
        site_configs=site_configs,
        **crawler_config
    )
    
    # 运行爬虫
    await crawler.crawl()

if __name__ == "__main__":
    asyncio.run(main()) 
