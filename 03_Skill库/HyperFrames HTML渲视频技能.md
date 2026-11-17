---
date: 2026-11-17
source: 公众号文章研读 + 本机机制等价复现（CDP 逐帧寻址渲 MP4，未安装 HyperFrames 本体）
url: https://github.com/heygen-com/hyperframes
type: 技能卡
tags: [AI工具, 视频生成, HTML渲视频, HyperFrames, 确定性渲染, CDP, Chrome, FFmpeg, 逐帧寻址, 避坑, Apache-2.0]
---

# HyperFrames HTML渲视频技能（确定性 / 逐帧寻址）

## 一句话定义

写 HTML/CSS + 可寻址动画 → 逐帧寻址渲成确定性 MP4。核心不是"网页转视频"，而是**同输入必出同片子**：渲染器暂停动画、跳到精确时刻抓帧，不靠墙钟播放。改字=改源文件再渲一次，不回时间线重做。

## 重要边界（先读，别搞混）

- **官方 HyperFrames**：HeyGen 开源框架，Apache-2.0，仓库 `heygen-com/hyperframes`，需 Node.js 22+ / FFmpeg，README 称带 9 个 Agent skills。**本机未安装、未实测。**
- **本机已跑通的方案**：机制等价的自写实现——Node 22 原生 WebSocket 直连 Chrome DevTools Protocol，逐帧 `seek(t)` + `Page.captureScreenshot` → FFmpeg。**本文的可调用命令都指这套**，产物在 `D:\03-个人文档\学习空间\hyperframes-demo\`。
- 别对外说"我用过 HyperFrames 官方包"——没有。说的是"用同一套确定性机制自己渲过"。

## 环境（已实测定版）

- **Node**：v22.22.2（原生全局 `WebSocket` + `fetch`，**不需要装 puppeteer / playwright / 任何 npm 包**）
- **Chrome**：157.0.8103.52，路径 `C:\Program Files\Google\Chrome\Application\chrome.exe`
- **FFmpeg**：在 PATH 中可用（N-126575-g17e6ed9dc0）
- **关键实现**：CDP 直连，不用第三方库；`--headless=new` 起浏览器，`--remote-debugging-port=<PORT>`

## 渲染命令（本机定版）

```bash
cd "D:/03-个人文档/学习空间/hyperframes-demo"
node render.js
```

- 输出：`out/demo.mp4`（15s / 1280×720 / 15fps / 225 帧 / ~1MB）
- **断点续传**：已有帧自动跳过；改了动画或参数必须先把 `frames/` 移走（不是删，见避坑条），否则复用到旧帧。
- 换成竖版/别时长：改 `render.js` 顶部 `W/H/FPS/SECONDS` 和 `index.html` 里 `body/#stage` 尺寸、各 scene 的 `data-b`。
- **别接管道**：Bash 里 `node render.js | head` / `| tail` 会把进程带成 SIGTERM、日志全丢。直接跑。

## index.html 写法要点（确定性合成）

- **唯一动画入口 `seek(t)`**：给定时间 t，画面被完全确定地重算。禁止 CSS `animation`/`transition`、`setTimeout`、墙钟、`Math.random()`、外链字体/图片。
- 每个 scene 带 `data-a` / `data-b` 时间窗；元素带 `data-d`（延迟）、`data-y`（起始位移）；`seek` 里算 `opacity` 和 `translateY`。
- 打字机效果用 `data-type="全文"` + `slice(0, n)`，n 由 t 算，不累积。
- **循环无缝**：末屏 `data-b` 设成比总时长早 0.4s（本例 14.6 而非 15），让首帧和末帧同为纯背景。已验证 `frames/0000.jpg` 与 `frames/0224.jpg` 完全一致。
- 暴露 `window.seek` / `FPS` / `DURATION` / `TOTAL_FRAMES`，并在初始化后写 `document.documentElement.dataset.ready='1'` 供渲染脚本等就绪。

## 关键事实 / 避坑（血坑级）

1. **Chrome 调试端口 IP 漂移（本机实测）**：同一台机器，`DevTools listening` 有时给 `127.0.0.1`，有时给 `[::1]`。硬编码任一 IP 都会 `ECONNREFUSED`。**从 Chrome stderr 的 `DevTools listening on ws://...` 正则解析真实地址**，别猜。
2. **PNG 逐帧太慢**：1280×720 PNG 约 0.4fps；换 JPEG quality 88 + 15fps 后约 12fps，225 帧 20 秒出完。中间帧用 JPEG，最终 MP4 用 libx264 无损衔接。
3. **管道杀进程**：见上，渲染命令别接 `| head` / `| tail`。
4. **frames 目录清理用 mv 不用 rm**：改参数后 `mv frames <临时目录>` 再 `mkdir frames`，别在工作区里批量删（安全规则）。
5. **官方 HyperFrames 的坑（转述官方文档，未实测）**：时间线必须暂停创建并登记到 `window.__timelines`，和根节点用同一个 id；漏掉 → 只得一帧静帧。字体/Chrome 版本会造成跨机器像素差；要严格复现用 Docker 钉住环境。

## 与现有视频资产的关系（怎么选）

| 场景 | 用谁 |
|---|---|
| 换文案反复出同款短片、要确定性可复现 | **本方案（HyperFrames 机制 / 自写 CDP）** |
| 人要在 Studio 里拖改、精修后写回 HTML | [[OpenFilm 视频技能]] |
| 数据驱动批量 / 服务端渲染 / 成熟生态 | Remotion 系（`remotion-video-toolkit`） |
| 商用授权敏感 | OpenFilm = MIT；HyperFrames 核心 = Apache-2.0；Remotion 商用需 License |

三者不互斥。本卡补的是"确定性逐帧 + 零 npm 依赖"这一格；OpenFilm 补"人肉精修闭环"；Remotion 补"规模化"。

## 产物位置

- 工程：`D:\03-个人文档\学习空间\hyperframes-demo\`（`index.html` + `render.js` + `render.log` + `frames/` + `out/`）
- 成片：`out/demo.mp4`
- 原始文章：[[2026-11-17 剪藏-HyperFrames（写HTML渲可复现短视频）]]

## 相关链接

- 官方仓库：https://github.com/heygen-com/hyperframes
- 确定性文档：https://hyperframes.heygen.com/concepts/determinism
- vs Remotion：https://hyperframes.heygen.com/guides/hyperframes-vs-remotion
- [[OpenFilm 视频技能]] / [[OpenFilm 视频智能体]]
- [[Skill库 MOC]]
