#!/usr/bin/env python3
"""Offline knowledge triage: safe candidates, topical matches, and review-only merge drafts."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
STOP=set("的 了 和 与 是 在 有 我 你 他 她 它 这 那 一个 一种 如何 什么 为什么 怎么 使用 进行 通过 可以 需要 相关 以及 内容 方法 设计 产品 知识 笔记 学习 记录 工作 系统 功能 介绍 分析 研究".split())
BLOCK=[r"vivo",r"维沃",r"(?i)\b(?:nda|confidential|internal only)\b",r"保密|机密|内部资料|会议纪要|工作日志|日报|周报|日记|待办|工资|薪资|绩效|客户信息",r"(?m)^\s*[-*]\s*\[[ xX]\]",r"(?i)\b(?:sk-[\w-]{16,}|gh[pousr]_[\w-]{20,}|github_pat_[\w-]{20,})\b"]
PATTERNS=[
("知识与原理",r"原理|定义|概念|是什么|机制|架构|算法|协议|标准|公式|基础"),
("产品方法论",r"方法论|框架|步骤|原则|策略|用户研究|调研|验证|设计方法|评估|指标|商业模式"),
("语音与 AI",r"语音|ASR|TTS|Agent|MCP|VAD|大模型|音频|智能体"),
]
def tokens(s):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}|[\u4e00-\u9fff]{2,5}",s.lower()))-STOP
def match_score(a,b):
    x,y=tokens(a),tokens(b)
    if not x or not y:return 0
    return round(len(x&y)/len(x|y),3)
def risk(text):
    return [p for p in BLOCK if re.search(p,text,re.I)]
def classify(text):
    return [name for name,pat in PATTERNS if re.search(pat,text,re.I)]
def assess(entry,existing):
    body=entry.get("body","")
    title=entry.get("title","")
    path=entry.get("path","")
    raw=path+"\n"+title+"\n"+body
    reasons=[]
    if risk(raw):reasons.append("疑似工作、私人或敏感内容")
    if len(body.strip())<90:reasons.append("知识正文过短，无法形成可复用结论")
    if not classify(raw):reasons.append("未识别出明确的知识或方法论主题")
    if re.search(r"(?m)^\s*(?:-\s*\[[ xX]\]|(?:今天|明天|本周|下周).{0,10}(?:完成|提交|开会))",raw):reasons.append("包含执行任务或待办")
    matches=sorted(({"id":x["id"],"title":x.get("title",""),"score":match_score(title+"\n"+body[:2000],x.get("title","")+"\n"+x.get("summary","")+"\n"+x.get("body","")[:2000])} for x in existing),key=lambda x:x["score"],reverse=True)[:3]
    matches=[x for x in matches if x["score"]>=0.08]
    return {"id":entry["id"],"path":path,"hash":entry["hash"],"title":title,"categories":classify(raw),"status":"blocked" if reasons else "review","reasons":reasons,"matches":matches,"suggested_action":("exclude" if reasons else "review_merge" if matches else "review_new"),"body":body if not reasons else None}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--queue",default=".obsidian-sync-review.json")
    ap.add_argument("--output",default=".obsidian-knowledge-proposals.json")
    args=ap.parse_args()
    queue=json.loads((ROOT/args.queue).read_text(encoding="utf-8"))
    db=json.loads((ROOT/"data/knowledge.json").read_text(encoding="utf-8"))
    items=[assess(e,db["items"]) for e in queue.get("changed",[])]
    result={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"notice":"仅本地审核；相似度仅用于推荐，不是 AI 语义理解；禁止自动公开","items":items,"excluded_from_scan":queue.get("excluded",[])}
    out=ROOT/args.output
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    counts=Counter(x["status"] for x in items)
    print("审核建议已生成：",out,"；候选",counts["review"],"篇；拦截",counts["blocked"],"篇")
    for x in items:
        print(x["status"],x["title"],"→",",".join(y["title"] for y in x["matches"]) or "新知识候选")
    print("没有修改或发布任何线上文档。")
if __name__=="__main__":main()
