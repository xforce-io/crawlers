import unittest
from datetime import datetime, timedelta
from crawler.common.date_extractor import DateExtractor

class TestDateExtractor(unittest.TestCase):
    def setUp(self):
        self.current_year = datetime.now().year
        
    def test_extract_standard_dates(self):
        """测试标准日期格式"""
        test_cases = [
            ('2024-03-22', datetime(2024, 3, 22)),
            ('2024/03/22', datetime(2024, 3, 22)),
            ('2024年3月22日', datetime(2024, 3, 22)),
            ('2024.3.22', datetime(2024, 3, 22)),
            ('24-03-22', datetime(2024, 3, 22)),
            ('24/03/22', datetime(2024, 3, 22)),
        ]
        
        for date_str, expected in test_cases:
            with self.subTest(date_str=date_str):
                result = DateExtractor.extract_date(date_str)
                self.assertEqual(result, expected)
    
    def test_extract_english_dates(self):
        """测试英文日期格式"""
        test_cases = [
            (f'Dec 7, {self.current_year}', datetime(self.current_year, 12, 7)),
            (f'December 7, {self.current_year}', datetime(self.current_year, 12, 7)),
            (f'7 Dec {self.current_year}', datetime(self.current_year, 12, 7)),
            (f'7 December {self.current_year}', datetime(self.current_year, 12, 7)),
            ('Dec 7', datetime(self.current_year, 12, 7)),
            ('7 Dec', datetime(self.current_year, 12, 7)),
        ]
        
        for date_str, expected in test_cases:
            with self.subTest(date_str=date_str):
                result = DateExtractor.extract_date(date_str)
                self.assertEqual(result, expected)
    
    def test_extract_relative_dates(self):
        """测试相对日期"""
        now = datetime.now()
        test_cases = [
            ('5分钟前', now - timedelta(minutes=5)),
            ('2小时前', now - timedelta(hours=2)),
            ('3天前', now - timedelta(days=3)),
            ('昨天', now - timedelta(days=1)),
            ('前天', now - timedelta(days=2)),
            ('刚刚', now),
        ]
        
        for date_str, expected in test_cases:
            with self.subTest(date_str=date_str):
                result = DateExtractor.extract_date(date_str)
                # 由于时间差异,只比较日期部分
                self.assertEqual(result.date(), expected.date())
    
    def test_invalid_dates(self):
        """测试无效日期"""
        invalid_dates = [
            '',  # 空字符串
            'invalid date',  # 无效格式
            '2024-13-01',  # 无效月份
            '2024-12-32',  # 无效日期
            'Foo 7',  # 无效月份名
            '7 Foo',  # 无效月份名
        ]
        
        for date_str in invalid_dates:
            with self.subTest(date_str=date_str):
                result = DateExtractor.extract_date(date_str)
                self.assertIsNone(result)
    
    def test_date_with_prefix(self):
        """测试带前缀的日期"""
        test_cases = [
            (f'发布于 2024-03-22', datetime(2024, 3, 22)),
            (f'Published on Dec 7, {self.current_year}', datetime(self.current_year, 12, 7)),
            (f'Date: 2024/03/22', datetime(2024, 3, 22)),
        ]
        
        for date_str, expected in test_cases:
            with self.subTest(date_str=date_str):
                result = DateExtractor.extract_date(date_str)
                self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main() 