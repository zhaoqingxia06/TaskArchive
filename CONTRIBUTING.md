# 写入 TaskArchive

每次更新前读取 AGENTS.md、ARCHIVE_RULES.md 和本文最新版本。新增、导入、同步、编辑或合并任何知识库内容时，还须读取并遵循最新的 KNOWLEDGE_RULES.md。

## 当前网站结构

公开页面已使用 v2 四级视图：动态大类别、项目介绍与时间跨度、归并后的需求、带来源与时间的关联消息。站点继续通过 `python3 scripts/build.py` 构建；该命令先校验所有旧平台快照，再生成同一入口的 v2 页面与 dist 发布目录。不要手写 index.html。

## 平台来源

- 既有 `data/codex.json`、`data/contributions/zcode.json`、`data/contributions/chatgpt.json` 保留原样，由原采集平台维护。v1 快照可继续进入构建，新增内容在语义复核前不自动塞进旧需求。
- 新接入使用 `data/organized_sources/<platform-client>.json`（schema_version=2）。格式为 source、client、coverage、conversations；每个会话有 id、messages；消息有 id、role=user、text、sent_at、attachments。sent_at 使用带时区 ISO 8601、日期或 null。原平台 ID 不可获取时明确使用本地归档 ID，不能假称是真实 ID。
- 只更新自己平台的文件，复用共享类别和项目，禁止覆盖其他来源。source 区分平台，client 区分网页与桌面。
- 旧 ChatGPT 文件是历史整理稿，公开界面明确标“非逐字原文、时间未核验”；不使用其中构造的时刻作为原文发送时间。以后取得真实导出时按原消息 ID 关联替换，保留追溯关系。

## 语义目录

`data/organized_catalog.json` 保存 categories、projects、requirements。每个项目含 id、category_id、name、description、aliases。每条需求含稳定 id、project_id、summary、来源引用、evidence_sha256；摘要必须由 LLM 阅读上下文后归并。

- `legacy_selectors` 引用旧快照 task_id 和归一化消息 indices；不要更改已选消息的顺序或内容。新增消息用新的显式选择或更新索引并复核。
- `message_refs` 用于 v2 原文，取 `json.dumps([source,conversation_id,message_id],ensure_ascii=False,separators=(',',':'))`。
- 相同目标的追问与修复合并；一条聊天可拆多个需求，不同聊天可合并。新原文未关联时显示待整理数量，不自动关键词分类。
- evidence_sha256 的规范见 scripts/archive_v2.py 的 fingerprint；重新阅读证据后更新，禁止静默接受变化。没有可靠证据不标已验收。
- 修改目录前获取最新分支；并行冲突时重新合并，不能强推。

## 构建与验证

运行 `python3 -m unittest discover -s scripts -p 'test_*.py'` 和 `python3 scripts/build.py`，检查统计、引用、来源覆盖及页面；提交变化的数据、脚本和生成的根 index.html。dist 由工作流重建发布，不单独提交。

GitHub Actions 只重建已接入的数据，不能读取用户私有聊天。定时采集必须由拥有实际历史权限的平台任务运行。站点最近同步与项目最近进展分开；只用有效原文计算项目日期。
