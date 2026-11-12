# AI 知识库 MVP · 开发分支说明

此分支为独立开发分支，未修改线上 knowledge.html，也未部署 Worker。

## 已完成
- Cloudflare Worker 原型：POST /api/parse（公开 HTML 正文）、POST /api/verify（DeepSeek API 测试）、POST /api/analyze（解析并结构化梳理）。
- 请求时传入用户的 DeepSeek API Key；服务端不持久化、不记录密钥。
- 基础输入限制、来源白名单、HTML 清理与 Token 上限。

## 部署前必做
1. 在 Cloudflare 创建 Worker，将 worker/ai-api.js 作为入口。
2. 设置 ALLOWED_ORIGIN 为实际网站域名，例如 https://zhaoqingxia06.github.io。
3. 添加真正的用户鉴权和请求频率限制；仅依赖 CORS **不是**鉴权。
4. 配置资料和 AI 结果的持久化存储（建议 D1）；默认私有并实施访问控制。
5. 检查 URL 抓取的 SSRF 防护、跳转限制、响应体大小与 HTML 解析质量。当前仅为早期实现，**不可作为安全完成的生产服务**。
6. 接入现有 knowledge.html 的 UI（需要先定位该页面在仓库中的真实来源）。
7. 浏览器 API Key 输入组件必须明确密钥风险；建议仅保存在当前会话内存，不存 localStorage、GitHub 或公开页面。正式版可选择加密的服务端存储。
8. 通过真实网页、失败网页、错误 Key、重复链接、超长正文等用例测试后再上线。

## 后续
M1：API 配置 UI、真实网页解析、AI 结构化梳理、资料保存与目录。
M2：人工审核、知识索引检索、全局 Review、差异预览、确认写入。
M3：去重缓存、批量整合、增量更新、成本监测。

注意：目前 HTML 提取是轻量回退方案，可能把导航文字混入正文；复杂网页需更可靠的正文提取器。
