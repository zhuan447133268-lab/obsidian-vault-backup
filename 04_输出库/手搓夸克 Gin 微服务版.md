---
type: 输出
tags: [手搓夸克, Go, Gin, 夸克网盘, PanSou, Emby, Jellyfin, AI-Agent]
created: 2026-10-21
source: D:/培训temp/quark-research/quark-go
---

# 手搓夸克 · Gin(Go) 微服务版

把「搜索(PanSou) → 转存(Quark) → 媒体库(Emby/Jellyfin)」三层用 **Go + Gin** 重写成可跑微服务，并内置 **AI 智能选片 agent**。是 [[手搓夸克 原型服务]]（Python/FastAPI 版）的 Go 重构。

## 结构
- `main.go` — Gin 路由 + 装配
- `internal/quark/` — 转存四步曲（stoken→detail→save→task）+ 移动端 mparam 切换
- `internal/pansou/` — 搜索客户端（只挑 pan.quark.cn）
- `internal/library/` — Emby/Jellyfin 刷新（`POST /Library/Refresh?api_key=`）
- `internal/agent/` — 启发式 Selector + 可插拔 LLM Selector（无 key 自动回退启发式）
- `web/index.html` — 单页前端（搜索/转存/AI/媒体库）

## 跑通验证（mock 全链路，实测）
`go build` 通过、`go vet` 干净。起 mock + Gin 后：
- `/health` → library/pansou 状态 ✅
- `/api/search` → 只回夸克链接 ✅
- `/api/save` → 转存成功（2 files）✅
- `/api/library/refresh` → 已触发 ✅
- `/api/agent` → **一次调用完成 搜索→选片→转存→刷新媒体库**（`library_refreshed:true`）✅

## 关键踩坑（血泪，已固化）
1. **翻页死循环**：夸克响应 `metadata._total` 是**顶层字段**（与 `data` 平级），非 `data.metadata`。塞错层级 → Total 恒 0 → 无限翻页卡死（save/agent 卡 1m40s+）。按顶层解析 + `page>=200` 兜底。
2. **Python mock 单线程假死**：`http.server` 单线程 + Go keep-alive 触发连接假死。改 `ThreadingHTTPServer`；且 `do_POST` 里 `q` 不共享 `do_GET` 的局部变量，要自己 `parse_qs`。
3. **端口残留**：反复起 mock 时旧进程同绑 8901，新代码不生效。`netstat -ano|grep :8901` + `taskkill //PID` 清。

## 运行
```bash
cd quark-go && go run . -port 8080
# mock 验证：python prototype/mock_apis.py 8901 后
go run . -config test-config.json   # 或 -mock http://127.0.0.1:8901
```

## 追剧自动补集（mediary-scout 增量思路）
订阅片名后，每次补集：列网盘目录解析**已存集数** → 搜索候选扫前 N 份解析集数 → **只转存含新集数的那份**（挑新增最多）→ 刷新媒体库；已追平则跳过不重复转存。
- 集数解析 `internal/agent/episodes.go`：`S02E06`/`第10集`/`EP12`/`更新至第N集`/`第1-20集`（范围展开）等
- 接口：`GET /api/watchlist`、`POST /api/watch`、`DELETE /api/watch`、`POST /api/watch/run`；`watch_interval_min>0` 开后台定时
- 列目录端点 `GET /1/clouddrive/file/sort`（`metadata._total` 又是顶层）
- **实测**：已存 E1-5、候选 E6-8 → 第一次新增 [6,7,8] 转存成功、`last_episode=8`；第二次判定「已是最新（网盘已存至 E8）」`saved=false` 不再转存 ✅
- 关键设计：补集决策**每次从网盘实列**（`ListSavePath`）而非信订阅里的 `last_episode`，删了文件会重新补；`last_episode` 仅作展示

## 多季分目录 + 媒体库缺失核对（增强）
- **多季** `season_subdir`：按季归档 `{根}/Season {NN}/`。解析 `S02E06`/`第2季`/`第10集`/`EP12`（无季归第1季），只在该季目录内比对已存。`WatchResult` 加 `season`/`target_dir`。
- **媒体库双向核对** `use_library`：`GET /Items?searchTerm=&IncludeItemTypes=Series` 定位剧 → `GET /Shows/Missing?SeriesId=&UserId=` 取缺失集 → 只补「网盘没有且媒体库也标缺失」的集；`user_id` 空则 `/Users` 取第一个。独立端点 `GET /api/library/missing?name=`。
- **实测（mock）**：补集前 missing=`S02[6,7,8]` → 补集到 `.../Season 02/`（`library_checked=true, library_missing=3, refreshed=true`）→ 二次「已追平」saved=false → 补集后 missing 归空（网盘=媒体库一致）。
- 踩坑：媒体库刷新客户端用 **POST** `/Library/Refresh`，mock 端点要放 `do_POST`（曾错放 do_GET 导致 refreshed=false）。

## Vue3 前端 + 部署上线（2026-10-21 夜）
- **前端** `../quark-web/`：Vite + Vue3 + Element Plus（暖橙主题，忌蓝灰），四面板=搜索选片 / AI 智能体（el-steps 展示 搜索→选片→转存→刷新）/ 追剧补集（订阅表 + 分目录/库核对开关 + 缺失 chips）/ 媒体库核对。`vite.config.js`：`base:'./'` + `/api` 代理 8080。
- **内嵌**：`npm run build` → dist 拷到 `quark-go/web/app` → `//go:embed all:web/app`；NoRoute + SPA fallback（`/api`、`/mock` 前缀不走前端）。`web/app/index.html` 缺失则退回旧版 `web/index.html`。33MB 单二进制前后端全包。
- **内置 mock**：`internal/mock/mock.go` 把 Python mock 的季感知状态机（SAVED/REMOTE、庆余年第二季）移植进 Go，`-demo` 旗标让夸克/PanSou/媒体库全指向自身 `/mock/*`，单端口自包含、零外部依赖；演示模式自动填假 `__uid` cookie，UI 留空即可玩。
- **部署**：「发布为应用」→ 单端口 HTTP 服务（`language=go, startCmd="go run . -demo", installCmd=""` 配 vendor）。线上=mock 演示数据。服务已改 `PORT` 环境变量 + 绑 `0.0.0.0`（发布硬性要求）。
- **踩坑（新血泪）**：
  1. gin `c.FileFromFS` 内部把 `URL.Path` 改成文件名交给 `http.FileServer`，后者对 `/index.html` 结尾路径一律 301→`./`（SPA 死循环）。解法：自写 `fsys.Open` + `http.ServeContent`。
  2. 发布沙箱上传时**排除 `dist` 目录**（当构建产物）→ embed 编译失败 `no matching files found`。内嵌目录改名 `web/app`。
  3. **gin v1.12 幽灵 MongoDB 依赖**：其 `binding` 包引 `mongo-driver/bson`，发布预检见到 mongo-driver 直接拒（external-service）。项目零 Mongo 使用，降 gin v1.10.0（API 兼容）+ x/net v0.25.0 + go 指令 1.24.0，剪干净。
  4. 发布上传可能瞬时 DNS 抽风（`EAI_AGAIN`，retryable）——原参数重试一次即过。
  5. 后台进程要用受管后台任务起；detached `&` 会被回收（curl 报 "upstream connect failed" 是进程没了，不是代理问题）。

## 真实搜索模式 + 《兰香如故》实战（2026-10-21 续）

- **切真实 PanSou**：`PANSOU_SERVER=https://so.252035.xyz ./quarkgo.exe -port 8080`（不带 `-demo`），/health 显示 `pansou:true`。
- **公共实例限流**：so.252035.xyz 对单 IP 间歇性 WAF 限流（HTTP 403 纯文本 `error code: 1003`），一成一败交替，重试 2-3 次必过；客户端已做 `res=merge` 降级重试 + 限流友好报错。
- **前端增强**（rebuild 后重新 go:embed）：`?kw=` URL 预填自动搜 + 搜索失败自动重试 3 次（退避 6s/12s + 页内限流提示）。
- **《兰香如故》实测**：76 条真实夸克结果。首选 `https://pan.quark.cn/s/4a28b01f3a91`（tg:yunpanx，2026-10-21，4K SDR HDR DV 杜比视界 DDP2.0+HiFi 中字 5GB/集 全 47 集，谭松韵/刘学义）；备用 b5f1516851dc / ba4c3276dbc5 / ed1627fda2ef / de238be677b8（WEB-4K 内封简繁）。
- 打开即搜：`http://127.0.0.1:8080/?kw=兰香如故`。线上部署版仍为 mock 演示模式。

## 授权与合规
MIT 全免。仅个人学习/管理自有内容；聚合公开分享链接，剑网2025 肃清 + ToS/版权风险，勿公开分发/商用。

## 相关链接
- [[手搓夸克 接口拆解]] — 四步曲端点与行号速查
- [[手搓夸克 原型服务]] — Python/FastAPI 原型
- [[手搓夸克 候选开源项目调研]] — 项目全景
