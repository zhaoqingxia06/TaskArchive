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

def scan(vault, included):
    entries = {}
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
            entries[rel] = {
                "id": "obsidian-" + sha(rel)[:20],
                "path": rel,
                "hash": sha(raw),
                "title": title_of(cleaned, path),
                "body": cleaned,
            }
    return entries

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
    entries = scan(vault, included)
    previous = load(STATE, {})
    old_hashes = previous.get("hashes", {})
    changed = [v for k, v in entries.items() if old_hashes.get(k) != v["hash"]]
    removed = sorted(set(old_hashes) - set(entries))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    queue = {"generated_at": now, "vault": str(vault), "changed": changed, "missing_or_removed": removed,
             "notice": "待审核内容仅保存在本机；文件移除不会自动删除线上知识"}
    write(QUEUE, queue)
    print(f"扫描 {len(entries)} 篇；待审核新增或修改 {len(changed)} 篇；不再匹配 {len(removed)} 篇。")
    print(f"审核清单：{QUEUE}")
    if not args.publish:
        print("预览模式：没有修改 GitHub 或网站。")
        return
    approved = set(cfg.get("approved_paths", []))
    if not approved:
        sys.exit("没有已审核的 approved_paths；未发布任何文件")
    approved_changed = [e for e in changed if e["path"] in approved]
    if not approved_changed:
        print("没有已批准且发生变化的文件，跳过发布。")
        return
    if args.push:
        if git("status", "--porcelain"):
            sys.exit("工作区有未提交改动；为防止混入其他文件，本次不推送")
        git("pull", "--ff-only", "origin", "main")
    data = load(DB, {})
    if data.get("version") != 1 or not isinstance(data.get("items"), list):
        sys.exit("知识库格式不匹配")
    by_id = {x["id"]: i for i, x in enumerate(data["items"])}
    processed = {}
    for entry in approved_changed:
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
