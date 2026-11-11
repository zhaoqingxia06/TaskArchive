#!/usr/bin/env python3
"""Extract public web pages or existing video subtitles to a private import file."""
import argparse
import datetime
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

MAX_BYTES = 4_000_000

class Article(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.title, self.parts, self.images = base, '', [], []
        self.skipped, self.in_title, self.in_article, self.has_article = 0, False, 0, False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript'):
            self.skipped += 1
        if self.skipped: return
        if tag == 'title': self.in_title = True
        if tag in ('article', 'main'):
            if not self.has_article: self.parts = []; self.images = []
            self.has_article = True; self.in_article += 1
        if tag in ('p','h1','h2','h3','li','br'): self.parts.append('\n')
        if tag == 'img' and (not self.has_article or self.in_article):
            src = urljoin(self.base, attrs.get('src',''))
            if urlsplit(src).scheme in ('http','https') and attrs.get('src'):
                self.images.append({'url':src, 'alt':attrs.get('alt','')})
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript') and self.skipped:
            self.skipped -= 1; return
        if self.skipped: return
        if tag == 'title': self.in_title = False
        if tag in ('article','main') and self.in_article: self.in_article -= 1
        if tag in ('p','h1','h2','h3','li'): self.parts.append('\n')
    def handle_data(self, data):
        if self.skipped: return
        if self.in_title: self.title += data; return
        if not self.has_article or self.in_article: self.parts.append(data)

def parse_page(content, url):
    p=Article(url); p.feed(content)
    lines=[re.sub(r'\s+',' ',line).strip() for line in ''.join(p.parts).splitlines()]
    return p.title.strip(), '\n'.join(x for x in lines if x), p.images

def fetch_page(url):
    request=Request(url, headers={'User-Agent':'Mozilla/5.0 TaskArchive/1.0'})
    with urlopen(request, timeout=20) as response:
        if response.headers.get_content_type() not in ('text/html','application/xhtml+xml'):
            raise ValueError('链接未返回网页正文')
        data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES: raise ValueError('网页超过大小限制')
        encoding=response.headers.get_content_charset() or 'utf-8'
        return parse_page(data.decode(encoding, errors='replace'), response.geturl())

def video(url):
    # yt-dlp 获取字幕，不下载视频。未安装、无字幕或平台限制均保留为待补充。
    with tempfile.TemporaryDirectory() as d:
        command=['yt-dlp','--skip-download','--write-subs','--write-auto-subs','--sub-langs','zh.*,en.*,zh,en','--sub-format','vtt','--no-playlist','--print','%(title)s','-o',str(Path(d)/'captions'),url]
        try: p=subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
        except FileNotFoundError: raise ValueError('未安装 yt-dlp，无法获取视频字幕')
        except subprocess.TimeoutExpired: raise ValueError('获取视频字幕超时')
        files=sorted(Path(d).glob('captions*.vtt'))
        if not files: raise ValueError('未获取到字幕：视频可能没有字幕或平台限制访问')
        raw=files[0].read_text(encoding='utf-8', errors='replace')
        rows=[]
        for line in raw.splitlines():
            line=re.sub(r'<[^>]*>','',line).strip()
            if not line or line.startswith(('WEBVTT','Kind:','Language:','NOTE')) or '-->' in line or line.isdigit(): continue
            line=html.unescape(line)
            if not rows or line!=rows[-1]: rows.append(line)
        if not rows: raise ValueError('字幕为空或无法解析')
        return (p.stdout.strip().splitlines() or ['视频'])[0], '\n'.join(rows), []

def collect(url, topic=''):
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname: raise ValueError('请输入有效的 HTTP 或 HTTPS 链接')
    kind='视频' if u.hostname.lower() in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be') else '网页'
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    record={'id':'source-'+hashlib.sha256(url.encode()).hexdigest()[:24], 'url':url, 'type':kind,'title':url,'topic':topic,'createdAt':now,'updatedAt':now,'status':'待处理','content':'','images':[]}
    try:
        title, content, images=video(url) if kind=='视频' else fetch_page(url)
        record.update(title=title or url,content=content,images=images,status='已提取' if len(content)>=80 else '提取不完整')
        if not content: record['status']='需补充'
    except Exception as e:
        record['status']='需补充'; record['error']=str(e)
    return record

def main():
    parser=argparse.ArgumentParser(description='提取网页和 YouTube 字幕并生成资料集导入文件。')
    parser.add_argument('urls',nargs='+');parser.add_argument('--topic',default='');parser.add_argument('--output',required=True)
    args=parser.parse_args(); output=Path(args.output).expanduser().resolve(); root=Path(__file__).resolve().parents[1]
    if output.is_relative_to(root): parser.error('为避免意外提交个人资料，请将输出文件放在仓库之外')
    records=[collect(url,args.topic) for url in args.urls]
    output.parent.mkdir(parents=True,exist_ok=True)
    with open(output,'w',encoding='utf-8') as f: json.dump({'version':1,'items':records},f,ensure_ascii=False,indent=2)
    for r in records: print(f"{r['status']} · {r['title']}" + (f" · {r['error']}" if r.get('error') else ''))
    print(f'导入文件：{output}')
if __name__=='__main__': main()
