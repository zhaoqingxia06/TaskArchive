#!/usr/bin/env python3
"""Portable TaskArchive compiler. LLM authors the semantic catalog; this validates it."""
import argparse
import collections
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def instant(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('sent_at 必须是带时区字符串、日期或 null')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        dt.date.fromisoformat(value)
        return value
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('时间必须带时区，未知请使用 null')
    return parsed.isoformat()


def time_label(value, timezone):
    if value is None:
        return '时间未知'
    if len(value) == 10:
        return value + '（仅日期）'
    return dt.datetime.fromisoformat(value).astimezone(ZoneInfo(timezone)).strftime('%Y-%m-%d %H:%M')


def key(source, conversation, message):
    # JSON tuple encoding avoids delimiter collisions and keeps references portable.
    return json.dumps([source, str(conversation), str(message)], ensure_ascii=False, separators=(',', ':'))


def load_messages(site):
    messages = {}
    coverage = []
    for path in sorted((Path(site) / 'data/contributions').glob('*.json')):
        doc = read(path)
        source = doc['source']
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', source):
            raise ValueError('source 必须是稳定的小写标识')
        coverage.append({'source': source, 'client': doc.get('client', 'unknown'), **doc.get('coverage', {})})
        for conv in doc['conversations']:
            for m in conv['messages']:
                if m.get('role', 'user') != 'user':
                    continue
                ref = key(source, conv['id'], m['id'])
                text = m['text']
                if not isinstance(text, str) or not text.strip():
                    continue
                item = {'ref': ref, 'source': source, 'clients': [doc.get('client', 'unknown')],
                        'conversation_id': str(conv['id']), 'message_id': str(m['id']), 'text': text,
                        'sent_at': instant(m.get('sent_at')), 'attachments': m.get('attachments', []),
                        'url': conv.get('url'), 'record_kind': m.get('record_kind', 'original')}
                if ref in messages:
                    old = messages[ref]
                    if any(old[k] != item[k] for k in ('text', 'sent_at', 'attachments')):
                        raise ValueError('同一原文 ID 存在冲突：' + ref)
                    old['clients'] = sorted(set(old['clients'] + item['clients']))
                else:
                    messages[ref] = item
    return messages, coverage


def fingerprint(refs, messages):
    payload = [{k: messages[r][k] for k in ('ref', 'text', 'sent_at', 'attachments')} for r in sorted(set(refs))]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def unique(items, label):
    result = {}
    for item in items:
        if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in result:
            raise ValueError(label + ' ID 缺失或重复')
        result[item['id']] = item
    return result


def span(refs, messages):
    dates = [messages[r]['sent_at'] for r in set(refs) if messages[r]['sent_at']]
    dates.sort(key=lambda v: dt.datetime.fromisoformat(v if len(v) > 10 else v+'T00:00:00+00:00').timestamp())
    return (dates[0], dates[-1]) if dates else (None, None)


def compile_site(site):
    site = Path(site)
    config = read(site / 'archive.config.json')
    timezone = config.get('timezone', 'Asia/Shanghai')
    ZoneInfo(timezone)
    messages, coverage = load_messages(site)
    catalog = read(site / 'data/catalog.json')
    categories = unique(catalog['categories'], '类别')
    projects = unique(catalog['projects'], '项目')
    requirements = unique(catalog['requirements'], '需求')
    for p in projects.values():
        if p['category_id'] not in categories or not p['name'].strip() or not p['description'].strip():
            raise ValueError('项目缺少有效分类、名称或介绍')
    used = set()
    for req in requirements.values():
        refs = req['message_refs']
        if req['project_id'] not in projects or not req['summary'].strip() or not refs:
            raise ValueError('需求缺少项目、语义摘要或原文引用')
        if len(refs) != len(set(refs)) or any(ref not in messages for ref in refs):
            raise ValueError('需求引用缺失或重复：' + req['id'])
        if req.get('evidence_sha256') != fingerprint(refs, messages):
            raise ValueError('需求摘要需由 Agent 复核并更新证据指纹：' + req['id'])
        req['first_at'], req['last_at'] = span(refs, messages)
        if type(req.get('scheduled', False)) is not bool:
            raise ValueError('scheduled 必须是布尔值')
        if req.get('status', 'unknown') not in ('unknown', 'requested', 'in_progress', 'verified', 'cancelled'):
            raise ValueError('未知需求状态')
        if req.get('status') in ('verified', 'cancelled') and req.get('status_evidence_ref') not in refs:
            raise ValueError('验收或取消状态必须引用用户证据')
        used.update(refs)
    excluded = {x['ref']: x['reason'] for x in catalog.get('excluded_messages', [])}
    if any(r not in messages or not reason.strip() for r, reason in excluded.items()):
        raise ValueError('排除记录缺少原文或理由')
    if used & excluded.keys():
        raise ValueError('原文不能同时收录和排除')
    previous_path = site/'tasks.json'
    if previous_path.exists():
        previous_refs = set(read(previous_path).get('messages', {}))
        missing = previous_refs - used - excluded.keys()
        if missing:
            raise ValueError('已公开原文缺少去向；保留引用或记录显式排除理由：' + next(iter(missing)))
    pending = sorted(messages.keys() - used - excluded.keys())
    # Unreviewed/excluded text stays in the local source, never leaks into public HTML/JSON.
    public_messages = {r: messages[r] for r in sorted(used)}
    for p in projects.values():
        refs = [ref for req in requirements.values() if req['project_id'] == p['id'] for ref in req['message_refs']]
        p['first_at'], p['last_at'] = span(refs, messages)
    data = {'schema_version': 2, 'title': config.get('title', '任务档案'), 'timezone': timezone,
            'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'categories': list(categories.values()), 'projects': list(projects.values()),
            'requirements': list(requirements.values()), 'messages': public_messages, 'coverage': coverage,
            'stats': {'projects': sum(any(r['project_id'] == p for r in requirements.values()) for p in projects),
                      'requirements': len(requirements), 'messages': len(used),
                      'pending': len(pending), 'excluded': len(excluded)}}
    if SECRET.search(json.dumps(data, ensure_ascii=False)):
        raise ValueError('公开数据存在疑似凭据；先显式脱敏并复核摘要，原始导出保留本地')
    return data


def esc(value):
    return html.escape(str(value), quote=True).replace('\n', '&#10;').replace('\r', '&#13;').replace('\t', '&#9;')


def render(data):
    tz = data['timezone']
    messages = data['messages']
    src_labels = {'chatgpt': 'ChatGPT', 'codex': 'Codex', 'zcode': 'ZCode'}
    tabs = '<button role="tab" id="tab-all" aria-controls="archive-panel" aria-selected="true" data-category="all">全部</button>'
    sections = []
    for n, cat in enumerate(data['categories']):
        cat_projects = [p for p in data['projects'] if p['category_id'] == cat['id']]
        count = sum(r['project_id'] in [p['id'] for p in cat_projects] for r in data['requirements'])
        if not count:
            continue
        tabs += f'<button role="tab" id="tab-{n}" aria-controls="archive-panel" aria-selected="false" tabindex="-1" data-category="{esc(cat["id"])}">{esc(cat["name"])} <span>{count}</span></button>'
        groups = []
        for p in sorted(cat_projects, key=lambda p: p['last_at'] or '', reverse=True):
            reqs = [r for r in data['requirements'] if r['project_id'] == p['id']]
            if not reqs:
                continue
            rows = []
            for r in sorted(reqs, key=lambda r: r['last_at'] or '', reverse=True):
                originals = collections.OrderedDict()
                refs = sorted(r['message_refs'], key=lambda ref: messages[ref]['sent_at'] or '')
                for ref in refs:
                    m = messages[ref]
                    # Display identical original text once, preserve each timestamp and provenance.
                    group_key = (m['text'], json.dumps(m['attachments'], ensure_ascii=False, sort_keys=True))
                    originals.setdefault(group_key, []).append(m)
                bodies = []
                for records in originals.values():
                    meta = ('历史整理稿 · 非逐字原文 · 时间未经核验 · ' if records[0].get('record_kind') == 'legacy_summary' else '') + ' · '.join(time_label(m['sent_at'], tz) + ' / ' + m['source'] + ' (' + ', '.join(m['clients']) + ')' for m in records)
                    attachments = ''.join('<p class="original-meta">附件引用：'+esc(json.dumps(m['attachments'], ensure_ascii=False))+'</p>' for m in records if m['attachments'])
                    # Expanding a requirement reveals every original at once; originals are never collapsed or numbered.
                    bodies.append(f'<div class="original"><span class="original-meta">{esc(meta)}</span><pre>{esc(records[0]["text"])}</pre>{attachments}</div>')
                srcs = sorted({messages[ref]['source'] for ref in refs})
                chips = ''.join(f'<span class="badge src {esc(src)}">{esc(src_labels.get(src, src))}</span>' for src in srcs)
                search = '\n'.join([cat['name'], p['name'], p['description'], *p.get('aliases', []), r['summary'], *(messages[ref]['text'] for ref in refs)]).lower()
                mark = '<span class="badge scheduled">定时</span>' if r.get('scheduled') else ''
                note = ('<p class="requirement-notes">'+esc(r['note'])+'</p>') if r.get('note') else ''
                rows.append(f'<details class="task" data-search="{esc(search)}" data-sources="{esc(json.dumps(srcs))}"><summary class="task-row"><time>{esc(time_label(r["last_at"], tz))}</time><span class="task-title">{esc(r["summary"])}</span><span class="markers">{chips}{mark}<span class="sub-count">{len(originals)} 原文</span><span class="chevron">⌄</span></span></summary><div class="task-body">{note}{"".join(bodies)}</div></details>')
            times = '最早记录 '+time_label(p['first_at'], tz)+' · 最近进展 '+time_label(p['last_at'], tz)
            groups.append(f'<details class="group"><summary class="group-heading"><h3>{esc(p["name"])}<span class="project-chevron" aria-hidden="true">⌄</span><span class="group-count">{len(reqs)} 条需求</span></h3><p>{esc(p["description"])}</p><div class="project-times">{esc(times)}</div></summary><div class="project-body">{"".join(rows)}</div></details>')
        sections.append(f'<section class="category" data-category="{esc(cat["id"])}"><header class="category-heading"><h2>{esc(cat["name"])}</h2><span>{count} 条需求</span></header><div class="category-content">{"".join(groups)}</div></section>')
    stats = data['stats']
    labels = {'chatgpt': 'ChatGPT', 'codex': 'Codex', 'zcode': 'ZCode'}
    req_srcs = [sorted({messages[ref]['source'] for ref in r['message_refs']}) for r in data['requirements']]
    src_summary = ' / '.join(f'{labels.get(src, src)} {sum(src in rs for rs in req_srcs)}' for src in sorted({s for rs in req_srcs for s in rs}))
    source_counts = collections.Counter(m['source'] for m in messages.values())
    sources = '<button type="button" data-source="all" aria-pressed="true">全部</button>' + ''.join(
        f'<button type="button" data-source="{esc(src)}" aria-pressed="false">{esc(labels.get(src, src))} <span class="source-count">{source_counts[src]}</span></button>' for src in sorted(source_counts))
    coverage = '；'.join(c['source']+'：'+str(c.get('scope', '覆盖范围未说明')) for c in data['coverage']) or '尚未接入消息来源'
    values = {'TITLE': esc(data['title']), 'STATS': f'{stats["projects"]} 个项目 · {stats["requirements"]} 条需求 · {stats["messages"]} 条关联消息 · 来自 {src_summary}',
              'UPDATED': esc(time_label(data['generated_at'], tz)), 'TABS': tabs, 'SECTIONS': ''.join(sections), 'SOURCES': sources,
              'COVERAGE': esc(coverage+f' · 待整理 {stats["pending"]} 条'),
              'DATA': json.dumps(data, ensure_ascii=False).replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')}
    return re.sub(r'\{\{([A-Z]+)\}\}', lambda m: values[m[1]], (ROOT/'assets/site-template.html').read_text())


def init(site):
    site = Path(site)
    site.mkdir(parents=True, exist_ok=True)
    if any(site.iterdir()):
        raise ValueError('初始化目录必须为空；已有站点使用 build，不覆盖历史')
    (site/'data/contributions').mkdir(parents=True)
    write(site/'archive.config.json', {'title': '任务档案', 'timezone': 'Asia/Shanghai'})
    write(site/'data/catalog.json', {'schema_version': 2, 'categories': [], 'projects': [], 'requirements': [], 'excluded_messages': []})
    (site/'.gitignore').write_text('raw/\nprivate/\n__pycache__/\n*.pyc\n')
    # Self-contained repository build assets; no dependency on the installed skill at runtime.
    (site/'scripts').mkdir()
    shutil.copy2(__file__, site/'scripts/archive.py')
    (site/'assets').mkdir()
    shutil.copy2(ROOT/'assets/site-template.html', site/'assets/site-template.html')
    (site/'.github/workflows').mkdir(parents=True)
    shutil.copy2(ROOT/'assets/pages.yml', site/'.github/workflows/pages.yml')
    (site/'AGENTS.md').write_text('Before updating read ARCHIVE_RULES.md. Keep source IDs stable, update only your platform data, preserve all other contributions. LLM must merge requirements semantically and cite original messages. Use python3 scripts/archive.py build .; never hand-edit index.html.\n')
    shutil.copy2(ROOT/'references/organization.md', site/'ARCHIVE_RULES.md')
    (site/'README.md').write_text('# TaskArchive\n\n将用户在各 AI 平台发起的真实需求按类别、项目、需求与原文整理为可追溯的网站。\n\n站点使用统一模板；GitHub Actions 负责构建和发布。每日增量整理需另行配置具备历史读取权限的 Agent 定时任务，是否启用以实际调度结果为准。\n\n接入前阅读 ARCHIVE_RULES.md。\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'build', 'fingerprints'])
    parser.add_argument('site')
    args = parser.parse_args()
    if args.command == 'init':
        init(args.site)
        print('Initialized '+args.site)
    elif args.command == 'fingerprints':
        messages, _ = load_messages(args.site)
        catalog = read(Path(args.site)/'data/catalog.json')
        # Print candidate digests; do NOT auto-approve edited evidence or write the catalog.
        print(json.dumps({r['id']: fingerprint(r['message_refs'], messages) for r in catalog['requirements']}, ensure_ascii=False, indent=2))
    else:
        data = compile_site(args.site)
        site = Path(args.site)
        output = render(data)  # Validate everything before replacing either published artifact.
        old = read(site/'tasks.json') if (site/'tasks.json').exists() else None
        if old and {k:v for k,v in old.items() if k!='generated_at'} == {k:v for k,v in data.items() if k!='generated_at'}:
            data['generated_at'] = old['generated_at']
            output = render(data)
        write(site/'tasks.json', data)
        temp = site/'index.html.tmp'
        temp.write_text(output)
        temp.replace(site/'index.html')
        print(json.dumps(data['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
