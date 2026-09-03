# lab-exam 证书列表页「下滑后回不到顶、上面内容显示不全」修复（真根因：MobileLayout 滚动容器）

- 日期：2026-09-02
- 状态：✅ 部署验证通过（Jenkins 部署 6ac5cf7 至测试环境，触屏仿真全链路实测回顶修复生效；CertificateCard 已回退，详情页 9:16 恢复）
- 关联：[[lab-exam-2026-09-02-certificate-scroll-fix]]（同日同名记录，此文件为**二次澄清后的正确版本**——用户确认 bug 在「我的证书」**列表页**，非详情页证书图片；**详情页 CertificateCard 早前改动已 git restore 回退**（用户 09-02 要求核查「是否修坏」，确认有风险：破坏 9:16 定稿+导出 PNG 比例+footer 贴底，且与列表页 bug 无关），本修复为纯 MobileLayout.vue 单文件）

## 现象（用户澄清后）

学生端「我的证书」**列表页**（`/student/certificates`，MobileLayout 下）手机上：往下滑后再往上滑**回不到顶部**，上面内容显示不全。测试真机反馈。经二次澄清，**不是**证书详情页（证书图片放大页）的问题——此前针对详情页 CertificateCard 的 aspect-ratio 修复与此无关。

## 复现（关键）：桌面模拟测不出来，必须触屏仿真

用 Playwright 独立 Chromium（`isMobile: true, hasTouch: true, iPhone UA 390×844`，CDP `Input.dispatchTouchEvent` 派发真实触摸拖拽）+ 测试环境真实学生账号（张凯悦 2302220248）：

- **证书列表页**：下滑到底（html scrollY=94）→ 上滑回顶 → **卡在 scrollY=50，回不到 0**，第一张卡 top=8（顶部被遮）——即用户反馈的现象。
- **考试列表页（已考 9 张卡）**：下滑 920 → 上滑**同样卡在 scrollY=50**——**不是证书页独有，MobileLayout 下全部页面中招**（用户只在证书页发现）。

此前用 `window.scrollTo`/桌面模拟一切正常回顶——**所以该 bug 只能靠触屏（touch 事件驱动惯性滚动 + 滚动链）复现**，桌面 IAB 无法暴露。

## 根因（定案）

**`.mobile-layout { min-height: 100vh }` 会随内容被撑破**（flex column 布局里 min-height 不限制内容超高），导致 `.mobile-content { overflow: auto }` **从未进入内部滚动**（实测 cH==sH==935，溢出量 0）：

1. 内容超高 → `.mobile-layout` 高度 = 内容高度（935px > 视口 844px）→ `.mobile-content` 一并撑到 935px，内容装得下，`overflow: auto` 永不激活；
2. 于是**滚动全部落到 html/body**（`scrollingElement=HTML`）；
3. 触屏惯性滚动时，页面既无真正内部滚动容器，又带 `van-pull-refresh`（顶部下拉拦截）+ `van-nav-bar fixed` 等 fixed 元素，**html 滚动链与触屏手势冲突** → 上滑惯量被截断、scrollTop 停在 50px 处回不到 0（A/B 实验排除 pull-refresh 后照旧卡 50，坐实是滚动容器错位本身）。

## 修复（`web/src/layouts/MobileLayout.vue`）

把滚动**收拢进 `.mobile-content` 内部容器**（这正是该布局本来的设计意图）：

1. `.mobile-layout`：`min-height: 100vh` → **`height: 100vh` + `height: 100dvh`（@supports 包裹，防构建压缩器删 100vh 兜底）+ `overflow: hidden`**——布局钉死在视口高度，不再被内容撑破；
2. `.mobile-content`：`overflow: auto` → **`overflow-y: auto; overflow-x: hidden` + `-webkit-overflow-scrolling: touch`**（iOS 惯性滚动必需）——成为唯一真滚动容器，内部滚动链正常。

溢出内容在 mobile-content 内滚动，html/body 不再滚动；fixed 的 nav-bar/tabbar 照常钉视口。

## 验证（触屏仿真全链路 + 桌面回归，测试环境真实账号）

- ✅ **证书列表页**：注入修复样式后，移动端滚动容器切换为 mobile-content（mcMax=94），下滑到底 mcY=94 → 上滑回顶 **mcY=0、首卡恢复 58px**，html 全程不滚。
- ✅ **考试列表页**：9 张卡 mcY 920→0、首卡恢复 102px，同样回顶正常。
- ✅ **PC 1024 桌面回归**：mobile-content 内部滚动正常（scrollTop 170）、数据 4 卡完整、tabbar 贴底、nav 可见，无回归。
- ✅ vue-tsc / vite build 通过；产物 CSS 确认 `.mobile-layout{height:100vh…} @supports(height:100dvh){.mobile-layout{height:100dvh}}` 双声明并存、`.mobile-content{overflow:hidden auto;-webkit-overflow-scrolling:touch}`。
- 截图：`gui-test-screenshots/2026-09-02-certificate-scroll-fix/final/`（cert-list-up/down、exam-list-finished-up/down、pc-1024，本地不推送）。

## 待办

- [x] 已推送 main（commit `6ac5cf7`，仅 MobileLayout.vue）+ Jenkins 部署测试环境
- [x] **部署后触屏回归（2026-09-02 Jenkins 部署后实测通过）**：
  - 证书列表页：mcScrollTop 94→0 回顶、首卡恢复 58px、html 全程不滚 ✅
  - 考试列表页（已考 9 卡 2349px 深）：连续上滑落点 960→415→0→0（第 3 次到顶；修复前是 html 卡 50 完全不动）✅
  - 详情页：certificate-card 366×193 → 358×636 ratio=0.563 ≈ 9/16 恢复定稿（CertificateCard 回退后）✅
  - PC 1024：mobile-content 内部滚动 170→0、window 恒 0 不滚 ✅
  - 证据截图：`gui-test-screenshots/2026-09-02-list-scroll-fix/verify/`（本地不推送）；result.json 数据落盘
- [ ] 真机（微信 WebView/iOS Safari）最终确认 + 详情页「保存图片」导出 PNG 目检（9:16 已恢复，toPng 输出随之恢复）