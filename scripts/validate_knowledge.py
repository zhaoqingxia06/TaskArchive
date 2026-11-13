#!/usr/bin/env python3
"""Validate public knowledge articles independently from private task archives."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "knowledge.json"
FIGURES = ROOT / "assets" / "knowledge-figures"
ALLOWED = {"AI Agent", "声音与听力", "产品方法论", "互联网与软件技术"}
PRIVATE = re.compile(r"vivo|维沃|工作待办|个人日记|内部会议纪要", re.I)
IMAGE = re.compile(r"!\[([^\]]+)\]\((\./assets/knowledge-figures/[^)]+)\)")
ERRORS = []

def fail(message):
    ERRORS.append(message)

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    items = data.get("items", [])
    ids = set()
    for item in items:
        ident = item.get("id", "")
        if not ident or ident in ids:
            fail("重复或空白文章 ID: " + ident)
        ids.add(ident)
        if item.get("category") not in ALLOWED:
            fail(ident + ": 非领域分类 " + str(item.get("category")))
        if not item.get("topic") or not item.get("title"):
            fail(ident + ": 缺少主题或标题")
        for section in item.get("sections", []):
            paragraphs = section.get("paragraphs", [])
            if not section.get("title") or not paragraphs:
                fail(ident + ": 存在空章节")
            for paragraph in paragraphs:
                for alt, src in IMAGE.findall(paragraph):
                    if not alt.strip():
                        fail(ident + ": 图片缺少替代文本")
                    if not (ROOT / src.removeprefix("./")).is_file():
                        fail(ident + ": 图片不存在 " + src)
        for field in ("title", "summary", "body", "source"):
            value = item.get(field, "")
            if PRIVATE.search(str(value)):
                fail(ident + ": 可能含内部或私人内容 " + field)
        for ref in item.get("references", []):
            if not ref.startswith("https://"):
                fail(ident + ": 来源不是 HTTPS URL")
    if ERRORS:
        print("\n".join(ERRORS), file=sys.stderr)
        sys.exit(1)
    print(f"Knowledge validation passed: {len(items)} articles, {len(set(i['category'] for i in items))} domains.")

if __name__ == "__main__":
    main()
