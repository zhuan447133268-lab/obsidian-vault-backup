# lab-exam 结果页「返回考试列表」被底部标签栏遮挡（safe-area 补偿）

- 日期：2026-09-03
- 状态：✅ 已修复（0d2d963）+ 本地 A/B 几何证明 + **测试环境部署回归通过**（11:54:40 上线）
- 关联：[[lab-exam-2026-09-02-tabbar-rise-fix]]、[[labexam-mobile-input-zoom-bug]]

## 测试环境部署回归（2026-09-03 11:54:40 上线，用户手动 build）

- 指纹：CSS `index-7iZYt5fS.css` → **`index-BnQBTunt.css`**
- 线上 CSS 特征命中：`.mobile-content[data-v-342d6516]{padding-bottom:50px;padding-bottom:calc(50px + env(safe-area-inset-bottom,0px));…}`（兜底行+补偿行俱在）
- 真页回归（Playwright 真触屏，2302220248 → 已考「在测试一个9.2」→ 查看结果）：滑到底后「返回考试列表」按钮底边 778 < tabbar 顶边 794，**完整可见无回归**；截图 `testenv-resultpage-bottom.png` 与老师反馈截图同页同数据，直接对比即可见修复效果
- iPhone 真机效果（env=34 → padding 84px）由本地 A/B 几何证明 + 线上 CSS 特征双重佐证；**待老师钉钉内真机复测确认**

## 现象（测试老师 09-03 反馈，附截图）

我的考试 → 查看结果 → 滑到最底部，「返回考试列表」按钮显示不完全（下半截被底部标签栏盖住）。老师环境：**iPhone + 钉钉内置浏览器**（截图可见钉丁顶栏与 AI 气泡）。

## 根因（定案，真 bug 非"优化建议"）

**van-tabbar 在 fixed 模式下 `safeAreaInsetBottom` 默认开启**（vant 4.10 `Tabbar.mjs:37`：`safeAreaInsetBottom ?? props.fixed`）→ 渲染 `van-safe-area-bottom` 类 → `padding-bottom: env(safe-area-inset-bottom)`。

- iPhone 带 Home Indicator（钉钉 WebView 尊重 env）→ **标签栏实际高度 = 50 + 34 = 84px**
- 而 `MobileLayout.vue` 的 `.mobile-content` 只预留 `padding-bottom: 50px` → **内容最后 34px 被标签栏盖住**，「返回考试列表」是结果页最后一个元素，正好被切
- **headless/安卓/桌面模拟器 env()=0**（tabbar 恒 50px）→ 模拟测试从未暴露（此前所有回归截图都正常的原因）；`padding-bottom:50px` 恰好够，纯靠巧合

## 修复（0d2d963，1 文件 3 行）

`web/src/layouts/MobileLayout.vue` `.mobile-content` 追加一行：
`padding-bottom: calc(50px + env(safe-area-inset-bottom, 0px));`
（保留前一行 `padding-bottom: 50px` 作不支持 env() 的老设备兜底；布局级修复，全部 MobileLayout 页面统一受益）

## 验证

1. **构建**：vite build 通过，dist CSS 含 `calc(50px + env(safe-area-inset-bottom,0px)` 特征
2. **本地 A/B 几何证明**（local-http + Playwright 390×844，tabbar 强制 +34px 模拟 iPhone，注入"长内容+底部返回按钮"复刻结果页形态）：
   - 旧布局（pad=50px）：按钮底边 778 > tabbar 顶边 760 → **被遮挡**（复现老师截图）
   - 新布局（pad=84px，即 iPhone 上 calc 的实际计算值）：按钮底边 744 < 760 → **完整可见**
   - 截图 `gui-test-screenshots/2026-09-03-safearea-fix/local-ab-proof.png`
3. **测试环境部署回归**：见文末补记

## 坑与经验

1. **van-tabbar fixed 默认自带安全区增高**：给 fixed 底栏做内容预留时必须用 `calc(50px + env(safe-area-inset-bottom))`，写死 50px 在 iPhone 上必被切
2. **headless 模拟器 env()=0**：safe-area 类问题在 Playwright/DevTools 模拟里天然不可见，验证只能靠 ①产物 CSS 特征 ②强制 padding 等价 A/B ③真机
3. 测试老师的截图自带环境信息（钉钉顶栏+AI 气泡）→ **问题②（导航栏上跑）的复现环境很可能也是钉钉 WebView**，等老师确认设备信息时优先问钉钉
4. 本地起 dist 服务测布局时注意：`.env.production` 会让 build 产物跑 cookie 模式（守卫读 `csrf_token`），伪造登录态两个键都要写
