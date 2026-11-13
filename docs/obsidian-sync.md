# Obsidian → TaskArchive 每日同步（第一阶段）

## 原理
Obsidian 文件只存在于你的电脑上，GitHub Actions 无法直接访问。本地程序扫描指定目录，生成审核清单；只有加入 `approved_paths` 的 Markdown 才能发布到公开 GitHub 仓库 `data/knowledge.json`。不会自动删除线上文档，也不会修改 Obsidian 原文件。

## 初始化
1. 克隆仓库或拉取最新版本：`git pull --ff-only origin main`。
2. 编辑根目录 `obsidian-sync.json`，把 `vault_path` 改为你的 Obsidian Vault **绝对路径**。默认仅扫描 `TaskArchive公开/` 下的 Markdown；把准备公开的笔记复制或移动到这个文件夹。不要把 Vault 全盘设为公开。
3. 首次预览：`python3 scripts/sync_obsidian.py`。查看本机生成的 `.obsidian-sync-review.json`，其中含正文，**不要提交到 GitHub**。
4. 审核后把允许公开的相对路径写入 `approved_paths`，例如 `TaskArchive公开/产品方法论/用户洞察.md`。
5. 运行 `python3 scripts/sync_obsidian.py --publish --push`。需要电脑本机已配置 GitHub Git 推送权限，GitHub Actions 随后构建网站。

## 每日定时（macOS）
在终端运行：
```sh
chmod +x scripts/install_obsidian_schedule.sh
./scripts/install_obsidian_schedule.sh
```
默认每天 09:00（电脑本地时间）执行。macOS 的 launchd 任务需要电脑开机并允许执行；睡眠期间不会保证准点运行。安装脚本生成的定时任务默认执行**预览**，不会未经审核自动公开笔记。审核并确认同步范围后，可在生成的 LaunchAgent plist 中把脚本参数改为 `--publish --push`。

## 每日定时（Windows）
使用“任务计划程序”创建每日 09:00 任务，程序为 `python`，参数为 `scripts/sync_obsidian.py`，起始目录为 TaskArchive 仓库根目录。自动发布需要追加 `--publish --push`，并事先配置 Git 推送权限。

## 当前边界
- 支持新增/修改检测、稳定文档 ID、已有文档保留、公开路径白名单、GitHub 发布。
- 第一阶段不执行 AI 语义去重或自动跨文档合并；不会声称已实现智能融合。
- 原始 Markdown 中的图片、Obsidian 内链、附件不会自动上传；可能无法在网页中正常显示。
- `obsidian-sync.json` 不应存放真实本机路径后提交给他人；建议使用环境变量 `OBSIDIAN_VAULT_PATH`，并在本地保持配置文件未提交。
- 自动化运行依赖本机开机、可访问 GitHub、Git 凭据可用。
