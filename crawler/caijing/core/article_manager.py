import os
import shutil
from datetime import datetime, timedelta
import logging
from typing import Set

class ArticleManager:
    """文章管理器，负责文章的存储和清理"""
    
    def __init__(self, base_dir: str, retention_days: int):
        self.base_dir = base_dir
        self.retention_days = retention_days
        self.logger = logging.getLogger(__name__)
        
    def cleanup_old_articles(self) -> int:
        """
        清理过期文章
        
        Returns:
            int: 清理的文章数量
        """
        try:
            cleanup_count = 0
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # 遍历文章目录
            for date_dir in os.listdir(self.base_dir):
                try:
                    # 解析目录名中的日期
                    dir_date = datetime.strptime(date_dir, '%Y-%m-%d')
                    
                    # 如果目录日期早于截止日期，删除整个目录
                    if dir_date < cutoff_date:
                        dir_path = os.path.join(self.base_dir, date_dir)
                        article_count = sum(len(files) for _, _, files in os.walk(dir_path))
                        shutil.rmtree(dir_path)
                        cleanup_count += article_count
                        self.logger.info(f"已清理过期目录: {date_dir}, 文章数: {article_count}")
                        
                except ValueError:
                    # 跳过非日期格式的目录名
                    continue
                except Exception as e:
                    self.logger.error(f"清理目录出错 {date_dir}: {str(e)}")
                    
            return cleanup_count
            
        except Exception as e:
            self.logger.error(f"清理文章出错: {str(e)}")
            return 0
            
    def get_article_dates(self) -> Set[str]:
        """获取所有文章日期"""
        dates = set()
        try:
            for item in os.listdir(self.base_dir):
                if os.path.isdir(os.path.join(self.base_dir, item)):
                    try:
                        # 验证是否为有效日期格式
                        datetime.strptime(item, '%Y-%m-%d')
                        dates.add(item)
                    except ValueError:
                        continue
        except Exception as e:
            self.logger.error(f"获取文章日期出错: {str(e)}")
        return dates
       
    def cleanup_invalid_directories(self):
        """清理非日期格式的目录"""
        try:
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path):
                    try:
                        # 检查是否为有效的日期格式 (YYYY-MM-DD)
                        datetime.strptime(item, '%Y-%m-%d')
                    except ValueError:
                        # 如果不是有效的日期格式，删除该目录
                        self.logger.info(f"删除非日期目录: {item}")
                        shutil.rmtree(item_path)
                        
        except Exception as e:
            self.logger.error(f"清理非日期目录时出错: {str(e)}")