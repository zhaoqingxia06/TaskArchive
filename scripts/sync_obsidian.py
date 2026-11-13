#!/usr/bin/env python3
"""Local Obsidian -> TaskArchive review-first sync. Standard library only."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "obsidian-sync.json"
QUEUE = ROOT / ".obsidian-sync-review.json"
STATE = ROOT / ".obsidian-sync-state.json"
DB = ROOT / "data/knowledge.json"

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()

def clean_md(text):
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.S)
    return text.strip()

def title_of(text, path):
    m = re.search(r"(?m)^#\s+(.+)$", text)
    return m.group(1).strip() if m else path.stem

# Fail closed: these rules are checked against path AND entire text.
# Keyword screening is a safety net, not a guarantee that content is public.
BLOCKED = [
    r"vivo", r"维沃", r"九号(?:公司|项目|产品|电动|e-bike)",
    r"(^|[/\\])(?:日记|日报|周报|待办|todo|tasks?|daily|journal|diary|会议纪要|工作记录|工作日志)([/\\]|$)",
    r"(?m)^\s*[-*]\s*\[[ xX]\]", r"(?im)\b(?:todo|to-do|action items?)\s*[:：]",
    r"(?m)^\s*(?:今日|明日|本周|下周)(?:待办|任务|工作计划|工作安排)\s*[:：]",
    r"(?i)\b(?:confidential|internal only|nda)\b",
    r"保密|机密|内部资料|客户名单|客户信息|薪资|工资条|绩效考核",
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
]
def blocked_reason(path, content, extra):
    haystack = path + "\n" + content
    for pattern in BLOCKED + list(extra):
        try:
            if re.search(pattern, haystack, flags=re.I):
                return "命中禁止公开规则"
        except re.error:
            return "排除规则无效，默认拒绝"
    return None

def scan(vault, included, extra):
    entries = {}
    excluded = []
    for pattern in included:
        for path in vault.glob(pattern):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            if any(part.startswith(".") for part in path.relative_to(vault).parts):
                continue
            rel = path.relative_to(vault).as_posix()
            raw = path.read_text(encoding="utf-8-sig")
            cleaned = clean_md(raw)
            if not cleaned:
                continue
            reason = blocked_reason(rel, raw, extra)
            if reason:
                excluded.append({"path": rel, "reason": reason})
                continue
            entries[rel] = {
                "id": "obsidian-" + sha(rel)[:20],
                "path": rel,
                "hash": sha(raw),
                "title": title_of(cleaned, path),
                "body": cleaned,
            }
    return entries, excluded

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vault", help="Override vault_path in config")
    p.add_argument("--publish", action="store_true", help="Publish reviewed files only")
    p.add_argument("--push", action="store_true", help="Commit and push after publishing")
    args = p.parse_args()
    cfg = load(CONFIG, {})
    vault_value = args.vault or os.environ.get("OBSIDIAN_VAULT_PATH") or cfg.get("vault_path")
    if not vault_value:
        sys.exit("请先配置 obsidian-sync.json 的 vault_path，或设置 OBSIDIAN_VAULT_PATH")
    vault = Path(vault_value).expanduser().resolve()
    if not vault.is_dir():
        sys.exit(f"Obsidian 文件夹不存在：{vault}")
    included = cfg.get("include", ["TaskArchive公开/**/*.md"])
    if not included:
        sys.exit("include 为空；默认拒绝扫描整个知识库")
    entries, excluded = scan(vault, included, cfg.get("extra_exclude_patterns", []))
    previous = load(STATE, {})
    old_hashes = previous.get("hashes", {})
    changed = [v for k, v in entries.items() if old_hashes.get(k) != v["hash"]]
    removed = sorted(set(old_hashes) - set(entries))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    queue = {"generated_at": now, "vault": str(vault), "changed": changed, "missing_or_removed": removed, "excluded": excluded,
             "notice": "待审核内容仅保存在本机；文件移除不会自动删除线上知识"}
    write(QUEUE, queue)
    print(f"候选 {len(entries)} 篇；拦截 {len(excluded)} 篇；待审核新增或修改 {len(changed)} 篇；不再匹配 {len(removed)} 篇。")
    print(f"审核清单：{QUEUE}")
    # Generate local knowledge review suggestions without sending Vault content to a service.
    review = ROOT / "scripts/obsidian_knowledge_review.py"
    if review.exists():
        subprocess.run([sys.executable, str(review)], cwd=ROOT, check=True)
    if not args.publish:
        print("预览模式：没有修改 GitHub 或网站。")
        return
    sys.exit("暂不支持直接发布原始笔记：请先按 KNOWLEDGE_RULES.md 和 KNOWLEDGE_REDESIGN.md 完成研究、整编、去重和公开审查，再通过知识库正常构建流程发布。候选清单保留在本机。")
    approved = cfg.get("approved_hashes", {})
    if not isinstance(approved, dict):
        sys.exit("approved_hashes 必须为路径到 SHA256 的映射")
    if not approved:
        sys.exit("没有已审核的 approved_paths；未发布任何文件")
    approved_changed = [e for e in changed if approved.get(e["path"]) == e["hash"]]
    unapproved = [e["path"] for e in changed if e["path"] in approved and approved.get(e["path"]) != e["hash"]]
    if unapproved:
        print("内容已变化，需要重新审核批准：", "、".join(unapproved))
    if not approved_changed:
        print("没有已批准且发生变化的文件，跳过发布。")
        return
    if args.push:
        dirty = git("status", "--porcelain")
        unsafe = [line for line in dirty.splitlines() if not line.endswith(" data/knowledge.json")]
        if unsafe:
            sys.exit("工作区存在其他未提交改动；本次不推送")
        git("pull", "--ff-only", "origin", "main")
    data = load(DB, {})
    if data.get("version") != 1 or not isinstance(data.get("items"), list):
        sys.exit("知识库格式不匹配")
    by_id = {x["id"]: i for i, x in enumerate(data["items"])}
    processed = {}
    for entry in approved_changed:
        # Recheck before writing, including previously approved files.
        if blocked_reason(entry["path"], entry["body"], cfg.get("extra_exclude_patterns", [])):
            print("禁止发布：", entry["path"])
            continue
        existing = data["items"][by_id[entry["id"]]] if entry["id"] in by_id else None
        if existing and existing.get("source_hash") == entry["hash"]:
            processed[entry["path"]] = entry["hash"]
            continue
        # Never overwrite editorially modified documents automatically.
        if existing and existing.get("source_hash") != old_hashes.get(entry["path"]):
            print("冲突，跳过：", entry["path"])
            continue
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        record = dict(
            id=entry["id"], category=cfg.get("category", "知识与原理"),
            topic=Path(entry["path"]).parent.name or "Obsidian 笔记",
            title=entry["title"], summary=entry["body"][:150].replace("\n", " "),
            body=entry["body"], pending="原始学习笔记；尚未完成与已有文章的 AI 语义合并",
            source="Obsidian 本地笔记：" + entry["path"], aliases="",
            createdAt=existing.get("createdAt", now) if existing else now,
            updatedAt=now, references=[], source_hash=entry["hash"])
        if existing:
            data["items"][by_id[entry["id"]]] = record
        else:
            data["items"].append(record)
        processed[entry["path"]] = entry["hash"]
    if not processed:
        print("没有安全可写入的内容。")
        return
    data["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write(DB, data)
    if args.push:
        try:
            git("add", "data/knowledge.json")
            git("commit", "-m", "knowledge: sync approved Obsidian notes")
            git("push", "origin", "main")
        except subprocess.CalledProcessError as e:
            sys.exit("Git 推送未完成：" + (e.stderr or str(e)))
    new_hashes = dict(old_hashes)
    new_hashes.update(processed)
    write(STATE, {"hashes": new_hashes, "last_success": dt.datetime.now(dt.timezone.utc).isoformat()})
    print(f"已处理 {len(processed)} 篇。" + (" GitHub 已推送。" if args.push else " 尚未推送到 GitHub。"))

if __name__ == "__main__":
    main()
