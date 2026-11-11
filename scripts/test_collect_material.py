import unittest
from unittest.mock import patch
from collect_material import collect, parse_page

class CollectTests(unittest.TestCase):
    def test_web_article_only_and_image(self):
        title, content, images=parse_page('<title>Example</title><nav>ignore</nav><article><h1>Hello</h1><p>World</p><img src="/a.png" alt="diagram"></article><footer>ignore</footer>', 'https://example.org/path')
        self.assertEqual(title,'Example'); self.assertIn('Hello',content); self.assertNotIn('ignore',content)
        self.assertEqual(images[0]['url'],'https://example.org/a.png')
    def test_error_keeps_source(self):
        with patch('collect_material.fetch_page', side_effect=ValueError('blocked')):
            item=collect('https://example.org/x')
        self.assertEqual(item['status'],'需补充');self.assertEqual(item['url'],'https://example.org/x');self.assertEqual(item['content'],'')
    def test_video_dispatch(self):
        with patch('collect_material.video',return_value=('Video','字幕'*50,[])):
            item=collect('https://youtu.be/abc')
        self.assertEqual(item['type'],'视频');self.assertEqual(item['status'],'已提取')
if __name__=='__main__': unittest.main()
