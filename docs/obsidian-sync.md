# Obsidian → TaskArchive 每日同步（第一阶段）

## 原理
Obsidian 文件只存在于你的电脑上，GitHub Actions 无法直接访问。本地程序扫描指定目录，生成审核清单；只有加入 `approved_paths` 的 Markdown 才能发布到公开 GitHub 仓库 `data/knowledge.json`。不会自动删除线上文档，也不会修改 Obsidian 原文件。

## 隐私与筛选规则（2026-11-13 更新）

- Vault 为 `D:\\obidian\\Tsing`。**不扫描整个 Vault**，只扫描 `TaskArchive公开/` 文件夹。
- 任何文件名、路径或正文出现 vivo、维沃、日记、待办、会议纪要、工作日志、保密、内部资料、凭据等规则，直接拦截；支持自定义排除正则。
- **即使已经批准过，内容一旦变化，原批准自动失效。** 审核时复制清单中该文件的 `hash` 到 `approved_hashes`，再次执行才可发布。
- 过滤器无法识别所有公司信息和私人信息；审核仍然必需。不要将敏感笔记放进公开候选文件夹。
- 同步只发布被明确批准的文件，不会读取、上传或修改 Vault 其他内容，也不自动删除线上文件。

## 初始化（Windows）

1. 本地 `git pull --ff-only origin main` 获取程序。
2. 在 `D:\\obidian\\Tsing` 新建 `TaskArchive公开` 文件夹，只放已脱敏的长期知识笔记。
3. 在 PowerShell 设置本次终端环境变量：`$env:OBSIDIAN_VAULT_PATH='D:\\obidian\\Tsing'`。也可在本机配置 `vault_path`，但不要把本机绝对路径提交到公开仓库。
4. 在 TaskArchive 仓库运行 `python scripts/sync_obsidian.py`，打开本地 `.obsidian-sync-review.json` 检查正文及排除结果。
5. 只把同意公开的 `path` 和对应 `hash` 逐一填入 `obsidian-sync.json` 的 `approved_hashes`；内容变化需重新审核。
6. 运行 `python scripts/sync_obsidian.py --publish --push`，需要本机 GitHub 推送权限。网站随后通过 GitHub Actions 更新。

## 每日定时（macOS）
在终端运行：
```sh
chmod +x scripts/install_obsidian_schedule.sh
./scripts/install_obsidian_schedule.sh
```
默认每天 09:00（电脑本地时间）执行。macOS 的 launchd 任务需要电脑开机并允许执行；睡眠期间不会保证准点运行。安装脚本生成的定时任务默认执行**预览**，不会未经审核自动公开笔记。审核并确认同步范围后，可在生成的 LaunchAgent plist 中把脚本参数改为 `--publish --push`。

## 每日定时（Windows）

运行 `powershell -ExecutionPolicy Bypass -File scripts/install_obsidian_windows.ps1`，会在当前 Windows 账户下创建每天 09:00 的**本地预览任务**。程序不会自动发布未审核笔记。需电脑开机、Vault 可访问。

## 当前边界
- 支持新增/修改检测、稳定文档 ID、已有文档保留、公开路径白名单、GitHub 发布。
- 第一阶段不执行 AI 语义去重或自动跨文档合并；不会声称已实现智能融合。
- 原始 Markdown 中的图片、Obsidian 内链、附件不会自动上传；可能无法在网页中正常显示。
- `obsidian-sync.json` 不应存放真实本机路径后提交给他人；建议使用环境变量 `OBSIDIAN_VAULT_PATH`，并在本地保持配置文件未提交。
- 自动化运行依赖本机开机、可访问 GitHub、Git 凭据可用。
