from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Pattern, Union
import re
import logging
from functools import lru_cache

class DateExtractor:
    """日期提取器,用于从文本中提取日期并标准化格式"""
    
    # 月份映射
    MONTH_MAP = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
        'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
        'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    # 更新日期模式，合并两个方法中的模式
    PATTERNS: List[Tuple[Pattern, str]] = [
        # ISO 格式
        (re.compile(r'(\d{4})-(\d{2})-(\d{2})'), '%Y-%m-%d'),  # 2024-03-22
        (re.compile(r'(\d{4})/(\d{2})/(\d{2})'), '%Y/%m/%d'),  # 2024/03/22
        
        # 中文格式
        (re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日'), '%Y年%m月%d日'),  # 2024年3月22日
        (re.compile(r'(\d{4})\.(\d{1,2})\.(\d{1,2})'), '%Y.%m.%d'),  # 2024.3.22
        
        # 英文月份格式 - 修改这些模式的顺序和处理方式
        (re.compile(r'([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})'), '%b %d %Y'),  # Dec 7, 2024 或 December 7, 2024
        (re.compile(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})'), '%d %b %Y'),  # 7 Dec 2024
        (re.compile(r'([A-Za-z]+)\s+(\d{1,2})'), '%b %d'),  # Dec 7 (当前年)
        (re.compile(r'(\d{1,2})\s+([A-Za-z]+)'), '%d %b'),  # 7 Dec (当前年)
        
        # 简写格式
        (re.compile(r'(\d{2})-(\d{2})-(\d{2})'), '%y-%m-%d'),  # 24-03-22
        (re.compile(r'(\d{2})/(\d{2})/(\d{2})'), '%y/%m/%d'),  # 24/03/22
    ]
    
    # 相对时间模式
    RELATIVE_PATTERNS = [
        (re.compile(r'(\d+)\s*分钟前'), lambda m: datetime.now() - timedelta(minutes=int(m.group(1)))),
        (re.compile(r'(\d+)\s*小时前'), lambda m: datetime.now() - timedelta(hours=int(m.group(1)))),
        (re.compile(r'(\d+)\s*天前'), lambda m: datetime.now() - timedelta(days=int(m.group(1)))),
        (re.compile(r'昨天'), lambda m: datetime.now() - timedelta(days=1)),
        (re.compile(r'前天'), lambda m: datetime.now() - timedelta(days=2)),
        (re.compile(r'刚刚'), lambda m: datetime.now()),
    ]
    
    @classmethod
    @lru_cache(maxsize=128)
    def extract_date(cls, text: str, return_str: bool = False) -> Optional[Union[datetime, str]]:
        """
        从文本中提取日期并转换为datetime对象或标准化的日期字符串
        
        Args:
            text: 要解析的日期文本
            return_str: 是否返回标准化的字符串格式(YYYY-MM-DD)
            
        Returns:
            datetime对象 或 YYYY-MM-DD格式的字符串，解析失败则返回None
        """
        if not text:
            return None
            
        # 清理文本
        text = ' '.join(text.split())
        text = re.sub(r'^(发布于|发表于|Published on|Posted on|Date:)\s*', '', text, flags=re.IGNORECASE)
        
        result = None
        
        # 1. 处理相对时间
        for pattern, time_func in cls.RELATIVE_PATTERNS:
            if match := pattern.search(text):
                try:
                    result = time_func(match)
                    break
                except (ValueError, AttributeError):
                    continue
        
        # 2. 处理标准格式
        if not result:
            for pattern, date_format in cls.PATTERNS:
                if match := pattern.search(text):
                    try:
                        parts = match.groups()
                        
                        # 处理英文月份名称
                        if re.match(r'[A-Za-z]', str(parts[0])):  # 月份在第一个位置
                            month_str = parts[0][:3].title()
                            if month_str not in cls.MONTH_MAP:
                                continue
                            month = cls.MONTH_MAP[month_str]
                            day = int(parts[1])
                            year = int(parts[2]) if len(parts) > 2 else datetime.now().year
                        elif re.match(r'[A-Za-z]', str(parts[1])):  # 月份在第二个位置
                            month_str = parts[1][:3].title()
                            if month_str not in cls.MONTH_MAP:
                                continue
                            month = cls.MONTH_MAP[month_str]
                            day = int(parts[0])
                            year = int(parts[2]) if len(parts) > 2 else datetime.now().year
                        else:  # 标准数字格式
                            year = int(parts[0])
                            month = int(parts[1])
                            day = int(parts[2])
                        
                        # 验证日期
                        if not (1 <= month <= 12 and 1 <= day <= 31):
                            continue
                            
                        # 处理两位数年份
                        if year < 100:
                            year += 2000
                        
                        result = datetime(year, month, day)
                        break
                            
                    except (ValueError, IndexError) as e:
                        logging.debug(f"解析日期失败: {str(e)}")
                        continue
        
        if result and return_str:
            return result.strftime('%Y-%m-%d')
        return result 
