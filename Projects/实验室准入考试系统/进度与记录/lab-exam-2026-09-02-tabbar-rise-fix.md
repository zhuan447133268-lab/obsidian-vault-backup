# lab-exam 学生端底部导航栏"下滑后上跑"修复

- 日期：2026-09-02
- 状态：✅ 已修复并上线，测试环境（lab-exam-test.oceghome.com）实测通过
- 关联：[[lab-exam-2026-09-01-teacher-mobile-adaptive]]（同为移动端自适应链路）

## 现象

学生端（MobileLayout + van-tabbar）登录后，页面下滑（滚动）时底部导航栏会"往上跑"——不贴底、跟随内容滚动。用户在正式环境真机验证仍复现；此前该 bug 因"桌面 IAB 未复现"挂起（见上一轮排查记录）。

## 根因（定案）

**不是滚动容器问题，是 72a3eb6 引入的 PC 居中规则在手机上错误生效。**

`web/src/styles/global.less:130-137`（commit 72a3eb6「学生端移动端自适应——PC 上限宽居中成手机样式」）：

```less
/* 学生端 fixed 元素（导航栏/底部栏）PC 上同步居中限宽，避免满屏拉伸 */
.van-nav-bar--fixed,
.van-tabbar--fixed,
.exam-paper-page .bottom-actions {
  max-width: 480px;
  left: 50%;
  transform: translateX(-50%);
}
```

该规则**没有媒体查询**，本意只针对 PC（>480px）居中，但手机（<480px）下：
- `max-width: 480px` 不生效（视口比 480 窄，元素撑满全宽）；
- **`left: 50% + transform: translateX(-50%)` 依然生效** → `position: fixed` 元素在手机上残留 `transform`。

**fixed 元素带 `transform`（非 none）正是移动端浏览器（iOS Safari / 微信 WebView / Android Chrome）滚动时导航栏跳动、上跑、跟随内容滚动的经典根因**：transform 使 fixed 元素脱离视口锚定（包含块计算改变/合成层行为异常），滚动过程中浏览器按 transform 后的位置重排，表现即为"下滑时导航栏往上跑"。

实测证据（Playwright，390×844 iPhone UA + isMobile）：
- **修复前**：`.van-tabbar--fixed` 计算样式 `left: 195px`（=390×50%）、`transform: matrix(1,0,0,1,-195,0)`（=translateX(-195px)）——与上一轮桌面观察到的 `matrix(1,0,0,1,-191,0)` 残留吻合；
- **修复后**：`left: 0`、`transform: none`、`position: fixed; bottom: 0`，滚动到底 `scrollY=2810` 时 tabbar 底边 = 视口高 844，**gap=0 贴底**。

## 修复

`web/src/styles/global.less:130-137` 改为仅 PC 生效，手机上恢复 Vant 默认（`left:0`、无 transform 贴底）：

```less
/* 学生端 fixed 元素（导航栏/底部栏）PC 上同步居中限宽，避免满屏拉伸 */
/* 仅 PC（宽度>480px）生效：fixed 元素带 transform 在手机浏览器滚动时会跳动/上跑（移动端经典 bug），手机上保持 vant 默认 left:0 贴底 */
@media (min-width: 481px) {
  .van-nav-bar--fixed,
  .van-tabbar--fixed,
  .exam-paper-page .bottom-actions {
    max-width: 480px;
    left: 50%;
    transform: translateX(-50%);
  }
}
```

同样受影响的还有 `.van-nav-bar--fixed`（顶部导航栏）与 `.exam-paper-page .bottom-actions`（答题页底部操作栏）——一并修复（同规则同一根因）。

## 验证

- ✅ 构建通过（vite build / vue-tsc）
- ✅ 产物 CSS：`@media (width>=481px){.van-tabbar--fixed{…translate(-50%)}}` 仅限宽屏
- ✅ Playwright 端到端（390×844 iPhone UA + isMobile，40 条假数据滚动到底）：
  - 修复前 `transform: matrix(1,0,0,1,-195,0)` / `left:195px`
  - 修复后 `transform: none` / `left:0` / 滚动到底 `bottom=844=viewportH, gap=0` 贴底
- ✅ **测试环境实测（2026-09-02，IAB 390×844 手机视口，真实账号张凯悦已考列表）**：
  - 刷新前旧产物残留 `transform: matrix(1,0,0,1,-191,0)` / `left:191px` / `max-width:480px` —— 即 bug 根因样式，旧页面未刷新导致
  - 刷新加载新产物后：`transform: none` / `left:0` / `max-width:none`，滚动到底 `gapBottom=0`（tabbar 底边=视口高 844）贴底
  - 产物 CSS 扫描：居中限宽规则已在 `@media (width >= 481px)` 内（手机不匹配）；无媒体查询的直接规则只有 vant 默认 `position:fixed;bottom:0;left:0`
  - PC 回归（1024×768）：`max-width:480px` + `matrix(-240)`=translateX(-50%) 居中仍生效，无回归
- 截图：`gui-test-screenshots/2026-09-02-tabbar-sticky-fix/test-env-mobile-top/bottom/pc-1024.png`

## 待办

- [x] 运维发布后真机回归（学生端下滑到底 tabbar 贴底不再上跑；证书/结果/我的 tab 同样检查）——测试环境 IAB 实测通过
- [x] PC 宽屏回归（居中限宽样式不回归）——1024 实测通过
- [ ] 真机（微信 WebView / iOS Safari）最终确认
- [ ] 答题页（exam-paper）bottom-actions 一并验证