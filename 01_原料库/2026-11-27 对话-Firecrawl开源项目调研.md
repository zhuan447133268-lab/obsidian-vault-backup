---
date: 2026-11-27
source: GitHub 源码浅克隆（README / SELF_HOST.md / docker-compose.yaml / apps/api/src）+ 官网定价页 + WebSearch
type: 调研卡
tags: [Firecrawl, 网页抓取, 爬虫, AI Agent, MCP, LLM-ready, 知识库采集, 自托管, AGPL]
---

# Firecrawl：开源项目调研（原料库）

> 触发：用户说「firecrawl 这个项目，你去看看」，随后选「深度调研 repo」。
> 做法：浅克隆到临时目录只读源码/配置，未安装未部署，读完删除临时副本。
> 一句话结论：**别自托管，别急着付费。要用就用 Local 版，且只在批量采集时才值得。**

## 项目是什么

给 AI agent 用的网页数据 API。把网页/搜索结果/PDF 转成干净的 Markdown 或结构化 JSON 再喂给 LLM。定位是替代 Puppeteer/Playwright + Bright Data + SerpAPI + Exa 那套拼装栈。GitHub 约 21 万星。

## 三层形态（2026-11 核实，与老资料不同）

| 形态 | 是什么 | 门槛 |
|---|---|---|
| **Firecrawl Local** | Rust 单二进制，`cargo install firecrawl-local`；本机 scrape / crawl / map，用本机 Chrome 渲染 JS，PDF/Office 本地解析；无数据库/队列/容器 | 需 Rust + C 编译器（macOS `xcode-select --install`，Debian `build-essential`）；`firecrawl-local init` 可装成 MCP 到 Claude Code / Cursor / Windsurf / Gemini CLI / Codex（需 Node.js 22+）；`serve` 在 3002 端口跑 v2 API |
| **Firecrawl Cloud** | 托管 API，功能最全：Search / Scrape / Parse / Crawl / Map / Interact / Agent / Monitor / Alexandria（550+ 数据源，2.5 亿人 / 7500 万公司 / 4100 万论文） | 要 key 或走 Keyless；按 credits 计费 |
| **Self-host（`apps/api`）** | Node/TS + Playwright + Redis + RabbitMQ + NuQ Postgres + 可选 FoundationDB；API 与 workers 分离 | 6+ 容器，生产要自己做认证/TLS/备份/监控 |

**关键修正**：项目已支持 **Keyless 模式**——MCP / CLI / API 每月 1000 credits，免注册免 API key。Local 默认单页抓不下来会回退 Cloud 并标记 `"source": "firecrawl-cloud"`；设 `FIRECRAWL_CLOUD=off` 可全离线。 ⇒ 「API key 卡脖子」不成立，与 LLM key 的坑不同。

**能力边界**：Local 只有 Markdown / HTML / raw HTML / links 输出；结构化 JSON、摘要、截图、浏览器交互、Agent 只有 Cloud 有。Search 在 Local 里也是走 Cloud（keyless 额度）。

## 自托管真实代价（SELF_HOST.md + Compose 核实）

- `docker-compose.yaml` 跑 6 个服务：playwright-service、api、redis、rabbitmq、nuq-postgres、foundationdb（可选）+ foundationdb-init。
- 资源：API 容器 4CPU/8G，Playwright 容器 2CPU/4G ⇒ 至少 6CPU/12G 起步。
- **默认 API 无认证**（`USE_DB_AUTHENTICATION=false` 是 baseline）。
- Redis / RabbitMQ / NuQ Postgres **没定义持久化卷**；要扛服务替换得自己加并测备份恢复。
- 默认不暴露依赖端口；admin 路由要 `BULL_AUTH_KEY`，另有 `ADMIN_INTERNAL_PORT` 内部监听（无 key，**永不对外发布**）。
- 官方明说：Compose 是「source-aligned starting point, not a production architecture」。K8s/Helm 样例同理。

## 定价（官网，2026-09-04 生效，USD）

| 档 | 月付 | 年付折合 | credits/月 | 并发浏览器 |
|---|---|---|---|---|
| Free / Keyless | $0 | — | 1,000 | 2 |
| Hobby | $19 | $16 | 5,000 | 2 |
| Standard | $99 | $83 | 100,000 | 25 |
| Growth | $399 | $333 | 500,000 | 50 |
| Scale | $749 | $599 | 1,000,000 | 100 |

- 1 credit = 1 页（basic scrape / crawl / map）；Search 2 credits/10 结果；Interact 2 credits/浏览器分钟；JSON / Question / Highlight 格式每页 +4 credits。
- 403/404 也扣 1 credit；无结果不扣。
- 你的量级 Free 的 1000 credits 足够试。

## 许可与合规

- 主仓库 **AGPL-3.0**（网络 contagious，嵌内部系统/对外产品先过法务）；SDK 与部分 UI 组件 MIT。
- 默认尊重 robots.txt；官网免责声明：尊重网站政策是终端用户责任。

## 对你的场景判断（个人结论）

| 场景 | 判断 |
|---|---|
| 日常读网页 | **不用**。现有 WebFetch / WebSearch / 连接器够。 |
| WebRetriever Challenge（iFixit 换屏指南检索） | 只在规模化抓取、需要稳定 markdown 时才值；单次验证用不上。 |
| Obsidian / IMA 知识库批量采集 | **唯一真正对口的场景**。走 Local 或 CLI keyless，别碰自托管/付费档。 |
| 嵌入内部/对外产品 | **禁止直接上**，AGPL-3.0 先过法务。 |

**最小起步路径**：`cargo install firecrawl-local` 或 `npx -y firecrawl-cli@latest scrape <url>`，先拿 Free 额度跑几页看输出质量。

## 后续动作（待用户定）

1. 是否拿一个实际网页跑一遍 Local 版，验证 markdown 输出质量。
2. 是否把「工具调研 → 可用性判断」抽成方法卡（→ 02_概念库 候选，需确认后写）。

## 相关链接

- [[手搓夸克 候选开源项目调研]]（同类开源项目调研卡先例）
- [[Skill库 MOC]]
