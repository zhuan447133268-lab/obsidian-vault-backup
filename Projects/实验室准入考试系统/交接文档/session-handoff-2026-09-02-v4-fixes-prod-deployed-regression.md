# 交接：正式环境已部署 09-02 四修复 + 题库重建 SQL，待正式回归（新 session 先读）

- 日期：2026-09-02
- 状态：🟡 运维已完成正式部署（前端 build + 题库 SQL 都已执行/部署），**正式环境回归待本交接后的 session 执行**
- 项目：实验室准入考试系统（lab-exam）
- 关联：[[session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit]]（上一份交接）、[[lab-exam-2026-09-02-list-scroll-container-fix]]

## 一、本次正式部署内容（运维已执行）

**1. 前端 build（main 最新，构建参数 VITE_AUTH_MODE=cookie 沿用 09-01 方案——不含则正式 admin 登录不跳转）**
本次一次性带上 09-02 push 的 4 个修复（均在测试环境验证过）：

| commit | 修复内容 | 测试环境验证 |
|---|---|---|
| `f4f50c4` | 证书详情「返回」误跳证书列表（考试页/结果页查看证书后返回应回原页） | ✅ 三链路回归全过 |
| `443122d` | 返回后考试 tab 被重置待考（onTabChange 写回 ?tab= 还原所在 tab） | ✅ 回归通过 |
| `f493105` | 底部导航栏手机上滚动时"上跑"（PC 居中规则 transform 污染，限 481px+） | ✅ 实测通过 |
| `6ac5cf7` | 学生端列表页（我的证书/考试列表）下滑后上滑回不到顶（MobileLayout 滚动容器修复） | ✅ 触屏仿真实测通过 |

**2. 题库重建 SQL `D:\claude-work\lab-exam\03_fix_questions_prod.sql`（2026-09-02 10:06 生成版）**
正式库 08-28 导入时 questions.content（题干）列错位成"每题最后选项文本"→ 判断题 800 道题干全为「错误」、去重后仅剩 1 道 → 组卷 1401。SQL 删表重建 2001 道题（已校验内容 + college_id 替换正式库真实 UUID）。执行前已要求运维先备份。

## 二、正式环境回归清单（本次交接要做的活）

**前置：确认部署指纹**
- 正式首页：`https://lab-exam.oceghome.com/` 的 index-*.js 指纹应 ≠ 09-01 的 `index-SV2mKqn8.js`；新产物网页上逐项验证下述行为即可（产物 CSS 的 `.mobile-layout` 应在懒加载 chunk，勿用主入口字符串判断）。

**1. 四个修复行为验证（学生端，建议手机视口 390×844）**
- [ ] 证书列表/考试列表：下滑到底 → 上滑回顶 0（**必须触屏仿真**：Playwright `isMobile+hasTouch` + CDP `Input.dispatchTouchEvent`；桌面 window.scrollTo 测不出，会误判未修复）
- [ ] 证书详情进入后点「返回」→ 回到来源页（考试列表所在 tab），不是证书列表
- [ ] 已考 tab 切到其它 tab 再返回 → 还原到已考 tab
- [ ] 列表滚动中底部导航栏贴底不"上跑"；PC 1024 下导航栏居中正常（回归）
- [ ] admin（oceg2026）登录跳转正常（cookie 构建链路 OK）

**2. 题库/组卷问题（SQL 生效验证）**
- [ ] 管理端/教师端用 100029018 班级生成一次试卷 → 不再 1401；判断题题干为正常内容（不再全是「错误」）
- [ ] 抽查判断题库 content/options 正确性
- [ ] （可选）正式库有考试后：交卷/证书/切屏 end-to-end（此前因正式库无考试一直缺验）

**3. 详情页「保存图片」目检（收尾项）**
- [ ] 证书详情页面「保存图片」导出的 PNG 为 9:16 竖版（CertificateCard 保持 aspect-ratio 9:16 定稿——勿再移除）

## 三、账号（双端密码不同，注意别混）

- 测试环境 `https://lab-exam-test.oceghome.com/`（验证已闭环，仅回归用）：张凯悦 **2302220248 / zxcvbnm123**
- 正式环境 `https://lab-exam.oceghome.com/`：张凯悦 **2302220248 / 123456**（zxcvbnm123 是她在测试环境自己改的密码，正式仍是 123456）；admin **oceg2026**（用户本人 09-01 自改，Gb$d!a$X8&eTbij4 已失效非 bug）
- 前端登录态存本地存储——触屏验证用 Playwright 时**必须页面内表单登录**（UI 登录），API 种 cookie 后路由守卫仍跳 login；登录 POST 返回 201，判断用 `res.ok()`

## 四、遗留/待办（不属于本次回归）

- [ ] `fix-school-admin-password.sql`（学校管理员密码修复，`D:\claude-work\lab-exam\`）**待用户拍板**是否执行（正式库学校管理员仍是旧强密码态）
- [ ] 切屏强制交卷（e627ab8）+ 1404 上报（51a780b）在**正式库有真实考试后**补端到端（测试环境均已过）
- [ ] 正式库无考试数据 → 发布真实考试（建考-出题/组卷-发布）时注意先回归 100029018 班级组卷链路

## 五、坑与经验（本次会话新收）

1. 判断线上是否含某修复：**别搜主入口 JS 字符串**——scoped CSS 在懒加载 chunk；行为嗅探计算样式（`.mobile-layout` height=视口/overflow:hidden、`.mobile-content` overflowY:auto、minHeight=0）才是硬证据。
2. 触屏滚动 bug 桌面模拟测不出（window.scrollTo 一切正常），必须 CDP touch 拖拽复现/验证。
3. 详情页 CertificateCard 的 aspect-ratio 9:16 是定稿+导出依据，**不可移除**（曾误改已回退，见 [[labexam-certificate-scroll-fix]]）。

## 六、可复用验证工具（触屏回归直接用）

- 触屏验证脚本（Playwright 全局 1.61.1，CDP touch 拖拽 + UI 表单登录）：`C:\Users\dfjq\AppData\Local\Temp\verify-mobile-scroll.mjs`
- 用法：把脚本内 `BASE` 改为 `https://lab-exam.oceghome.com`（正式）；不带参数直接对当前产物验证，输出截图到 `D:\2026准入题库\gui-test-screenshots\<日期>-<场景>\verify\` + result.json
- 依赖：`D:\program files\npm-global\node_modules\playwright`（ESM 文件 URL 导入）；正式账号见第三节