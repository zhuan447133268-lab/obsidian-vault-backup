---
date: '2026-09-01'
description: 2026-09-01 会话交接：教师端移动端自适应（e8a8967）+ 切屏强制交卷 off-by-one（e627ab8）两个修复均已测试环境验证通过，等待运维 build 正式环境；含正式环境待办、账号/库拓扑/认证模式关键事实、调试技巧速查
name: session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit
status: completed
tags:
  - lab-exam
  - session-handoff
  - mobile-adaptive
  - leave-force-submit
  - deploy
type: project
---
# 2026-09-01 会话交接：两修复已正式回归验证闭环

**时间**：2026-09-01（15:00-16:00 起）
**上一条交接**：[[session-handoff-lab-exam-cookie-mode-2026-08-31]]
**当前 main**：`e627ab8`（已推送 origin main，含下述两个修复）

---

## 一句话现状

教师端手机自适应、考试切屏强制交卷两个问题都**已修复**、测试环境验证通过、**正式环境 build 后回归验证通过**（2026-09-01 17:00 前后实测，见下方 P0）；唯一遗留为正式库无考试，切屏端到端与交卷链路待有考试后补验。

**晚间接力（追加章节见「第 3/4 个修复」）**：学生端「查看证书→返回跳错页」bug 于本日修复并推送（f4f50c4，[[lab-exam-2026-09-01-cert-back-nav-fix]]），测试环境三条链路回归全部通过；随后追加 tab 还原修复（443122d，switch tab 同步 URL），已推送、**测试环境部署后回归通过**（2026-09-01 Jenkins）。两个修复**正式环境均未部署**，待用户通知运维一并 build。

---

## 本次会话完成的修复（均已推送 origin main）

### 1. 教师端移动端自适应（commit e8a8967）✅ 测试环境已验证

- **问题**：张凯悦手机登录教师账号页面"显示不全"。根因：教师端（/teacher、/school-admin、/college-admin）挂 `AdminLayout.vue` 固定 260px 侧栏，无任何移动端适配；手机 390 视口下三页 scrollWidth 451 横向溢出、卡片被压到 38~70px；学生端有适配（global.less 限宽只覆盖学生端）。
- **修复**：`web/src/layouts/AdminLayout.vue` 加 768px 断点——侧栏变抽屉（汉堡按钮呼出 + 遮罩点击关闭 + 菜单选中自动收起），桌面不变。
- **测试环境验证**（390×844）：/teacher 首页、/teacher/classes、/teacher/statistics 三页均无横向溢出（scrollWidth 382/390/382 ≤ 390）、侧栏收起 left=-260、抽屉可开可关。截图 `gui-test-screenshots/2026-09-01-teacher-mobile/`（05-07 修复后）。

### 2. 考试切屏强制交卷 off-by-one（commit e627ab8）✅ 测试环境已验证

- **问题**：页面提示"累计 3 次离开将强制交卷"，但**第 2 次离开就强制交卷**（手机+PC 多端场景尤甚）。
- **根因**：`server/src/modules/student-exam/student-exam.service.ts` reportEvent()：LEAVE 事件**先** examEvent.create（07-13 起顺序）→ count 查询**已含当前这次** → e78afe8（08-11"切屏计数 off-by-one 修复"）又加 `leaveCount + 1 >= maxLeave` → 双重计数，实际触发点 = maxLeave-1。原单测 mock count=2"本次第 3 次"与真实实现脱节，掩盖了回归。
- **修复**：判定改 `leaveCount >= maxLeave`，注释同步；单测对齐（第 3 次 count=3 触发 / 新增第 2 次 count=2 不触发回归用例 / 第 1 次 count=1 不触发）。全量 10 suites / 95 tests 绿，nest build 通过。
- **测试环境验证**（张凯悦卷 a69cced1，接口直调 3 次 LEAVE）：第 1 次 leaveCount=1 不交卷 → 第 2 次 leaveCount=2 不交卷（**修复分水岭**）→ 第 3 次 leaveCount=3 forceSubmitted=true，AUTO_SUBMIT payload `{reason:'switch_screen_limit', leaveCount:3}`；UI 显示"自动交卷"0 分。截图 `gui-test-screenshots/2026-09-01-leave-force-submit/01-result-after-3rd-leave.png`。

### 3. 学生端「查看证书→返回跳错页」（commit f4f50c4）✅ 测试环境已验证（09-01 晚间）

- **问题**：考试页点「查看证书」→ 看完点返回 → 直接跳到证书列表页，没回到原本考试页面。
- **根因**：`web/src/views/student/certificate-view.vue` 的 onBack 写死 `router.replace('/student/certificates')`，丢失来源页（考试列表 /student、结果页 /student/exams/:id/result 均被带到证书列表；只有证书列表进来恰好等价，掩盖了 bug）。
- **修复**：onBack 改读 `window.history.state?.back`，来源是 `/student*` 站内页就用 `router.back()` 回来源；深链直达（无 back 源）才兜底 `replace('/student/certificates')`。详见 [[lab-exam-2026-09-01-cert-back-nav-fix]]。
- **测试环境回归**（390×844，张凯悦）：三条链路全过——考试列表→证书→返回落 /student ✅；结果页→证书→返回落 /student/exams/:id/result ✅；证书列表→证书→返回落 /student/certificates ✅。position 栈对称无残留。截图 `gui-test-screenshots/2026-09-01-cert-back-regression/`（link1/2/3）。
- **待确认**：f4f50c4 是否同步 build 正式环境（见 P0-4）；若正式 build，追加修复 443122d 可一并带上。

### 4. 学生端考试列表 tab 还原（commit 443122d）✅ 测试环境已验证（09-01 晚间 Jenkins 部署）

- **问题**：链路1 从「已考」tab 看证书返回后，列表 tab 重置为「待考」（用户原在已考 tab 却看到空列表）。
- **根因**：`index.vue` tab 状态只存组件内存、从不写回 URL（onTabChange 只清列表+loadData）；activeTab 初始化仅读 query.tab 默认 PENDING。从已考 tab 进证书时历史来源 URL 是 `/student`（无 `?tab=`），router.back() 带回无 tab → 组件重建 tab 归零。
- **修复**（单文件 2 行，用户答复「修，禁止动别的代码」）：onTabChange 加 `router.replace({ query: { ...route.query, tab: activeTab.value } })`——switch tab 即同步 URL（replace 不新增历史记录），证书页 router.back() 时自动落回 `?tab=FINISHED`，与 f4f50c4 配合闭环。
- **状态**：**测试环境部署后回归通过（2026-09-01 Jenkins 部署）**——已考tab切换 URL→`?tab=FINISHED`、进证书 back 带参数、返回落已考 tab（position 17→18→17）；「进行中」同步 `?tab=IN_PROGRESS`、直达 `?tab=FINISHED` 落已考；链路2/3 回归不破（18→19→18 / 19→20→19）。截图 `gui-test-screenshots/2026-09-01-cert-back-regression/`（link1-tab-restore-after-deploy、link3-back-to-cert-list-after-deploy）。

### 5. 正式环境「题库[JUDGE]可用题目不足」根因定案（09-01 深夜，详见 [[lab-exam-2026-09-01-prod-judge-data-corrupt]]）🔴 P0 待运维执行

- **现象**：正式环境 100029018（电气电子智能工程学院学院管理员）给班级学员生成试卷报错——`题库[JUDGE]可用题目不足（含学院过滤及去重后），需要 10 道，实际 1 道`。
- **根因**：**不是代码 bug**。正式库 2001 道题（SINGLE 800 / JUDGE 800 / MULTIPLE 401）是 08-28 导入的，`content`（题干）列被整体写错成**每题最后一个选项的文本**；判断题选项恒为 [A正确, B错误] → 800 道判断题 content 全部是「错误」→ 组卷按题干去重后仅剩 1 道 → 1401。正确题干在源 xlsx 与 08-31 版 `02_question_data.sql` 里都有。
- **修复**：已生成 **`D:\claude-work\lab-exam\03_fix_questions_prod.sql`**（08-31 正确题目 + college_id 映射为正式库 8 学院真实 UUID + DELETE 重插 2001 道；模拟组卷 DQ 判断题 200 道充足；正式库当前 1 草稿考试 0 试卷，重建无副作用）。**用户已拿到该文件，安排运维备份后执行**。
- **验证方式**（执行后）：100029018 班级生成试卷不再报 1401；题库管理里判断题题干显示正常；抽查单选题题干不再是选项内容。

### 6. 学生端底部导航栏「下滑后上跑」根因定案（09-02，详见 [[lab-exam-2026-09-02-tabbar-rise-fix]]）🟢 已修 + 推送 + 测试环境实测通过，待运维 build 正式

- **现象**：学生端登录后滑动页面，底部导航栏（van-tabbar）"往上跑"、不贴底。用户 09-02 真机验证正式环境仍复现（此前挂起因桌面 IAB 未复现）。
- **根因**：**不是滚动容器问题**。`web/src/styles/global.less:130-137`（commit 72a3eb6「PC 上限宽居中」）给 `.van-nav-bar--fixed`/`.van-tabbar--fixed`/`.exam-paper-page .bottom-actions` 加 `left:50%; transform: translateX(-50%)` 居中，但**没有媒体查询**——手机上（<480px）`max-width` 不生效、`left:50%+transform` 却照常作用 → **fixed 元素带 transform 在移动端浏览器滚动时跳动/上跑（经典根因）**。
- **实测证据**（Playwright 390×844 iPhone UA+isMobile）：修复前 tabbar 计算样式 `left:195px`、`transform:matrix(1,0,0,1,-195,0)`；修复后 `left:0`、`transform:none`、滚动到底 gap=0 贴底。
- **修复**（`web/src/styles/global.less`，单文件 8 行）：规则包进 `@media (min-width: 481px)`，PC 保持居中限宽、手机恢复 Vant 默认 `left:0` 无 transform。**commit f493105 已推 main（用户确认后推送）**。
- **✅ 测试环境实测通过（2026-09-02，IAB 390×844 手机视口，真实学生账号）**：
  - 刷新前旧页面残留 bug 样式（`matrix(-191)`/`left:191px`/`max-width:480px`）；刷新加载新产物后 `transform:none`/`left:0`/`max-width:none`，滚动到底 `gapBottom=0` 贴底。
  - 产物 CSS 扫描：居中规则已在 `@media (width >= 481px)` 内（手机不匹配）；无媒体查询直接规则只剩 vant 默认 `position:fixed;bottom:0;left:0`。
  - PC 1024 回归：居中限宽仍生效（matrix(-240)、maxWidth 480），无回归。
  - 截图 `gui-test-screenshots/2026-09-02-tabbar-sticky-fix/test-env-mobile-top/bottom/pc-1024.png`（本地）。
- 待办：真机（微信 WebView/iOS Safari）最终确认；答题页 bottom-actions 一并验证。

### 7. ❌ 证书详情页 CertificateCard 修复 —— **已回退撤销**（09-02 用户要求核查后定论，见「结论」）

- **现象**（此前的误定位）：学生证书详情页（`/student/certificates/:id`）手机上往下滑后再上滑，回不到顶部、上面内容显示不全。
- **历史修复**（09-02 已撤销）：移除 `.certificate-card` 的 `aspect-ratio`（高度跟随内容），`.cert-frame` 加 `overflow:hidden`。
- **09-02 用户核查结论**：用户确认真 bug 在「我的证书」**列表页**（第 8 节），详情页卡片本就正常；且该改动有**修坏风险**（破坏 9:16 定稿证书比例、保存图片导出 PNG 比例、footer 印章不再贴底）。**已 `git restore` 完整回退，不推送、不部署**。部署后实测详情页 ratio=0.563 ≈ 9/16 正常。
- ⚠️ **教训**：勿再在 CertificateCard 上移除 aspect-ratio；详情页「保存图片」导出（toPng 捕获卡片）依赖 9:16 定稿。

### 8. 「我的证书」列表页「下滑后回不到顶、上面内容显示不全」根因定案 + 修复（09-02 二次澄清，详见 [[lab-exam-2026-09-02-list-scroll-container-fix]]）✅ 已推送 + Jenkins 部署 + 触屏回归通过

- **澄清**：用户确认 bug 在「我的证书」**列表页**（`/student/certificates`，MobileLayout 下），**不是**证书详情页的图片卡片（第 7 节已回退）。
- **根因**：`.mobile-layout { min-height:100vh }` 被内容撑破 → `.mobile-content{overflow:auto}` 从未进入内部滚动（sH==cH）→ 滚动全落 html/body → 触屏惯性滚动链冲突，上滑被截断**卡在 scrollY=50 回不到顶**。
- **复现**：桌面模拟测不出（window.scrollTo 一切正常）；必须 Playwright `isMobile+hasTouch` + CDP touch 拖拽（iPhone UA 390×844，张凯悦 2302220248）——证书列表、**考试列表（9 卡）一并中招**（上滑卡 50）。
- **修复**（`web/src/layouts/MobileLayout.vue` 单文件，commit `6ac5cf7`）：mobile-layout `min-height:100vh`→`height:100vh`+`height:100dvh`(@supports 防压缩器删兜底)+`overflow:hidden`；mobile-content `overflow:auto`→`overflow-y:auto;overflow-x:hidden`+`-webkit-overflow-scrolling:touch`。滚动收拢回 mobile-content 内部。
- **部署后验证**（Jenkins 部署后触屏仿真实测，2026-09-02）：
  - 证书列表：mcScrollTop 94→0 回顶、首卡恢复 58、html 全程不滚 ✅
  - 考试列表（已考 9 卡 2349px 深）：连续上滑落点 960→415→0→0（第 3 次到顶；修复前 html 卡 50 不动）✅
  - 详情页：CertificateCard 回退后 ratio=0.563 ≈ 9/16 恢复定稿 ✅
  - PC 1024：mobile-content 内滚 170→0、window 恒 0 ✅
  - 截图 `gui-test-screenshots/2026-09-02-list-scroll-fix/verify/` + result.json（本地）。
- 待办：真机（微信 WebView/iOS Safari）最终确认 + 详情页「保存图片」导出 PNG 目检（9:16 已恢复）。

---

## 待办清单（新 session 从这里继续）

### 修复就绪、待用户确认部署（2026-09-02 新增）

1. ✅ **MobileLayout 滚动容器修复（list-scroll-fix）**：commit `6ac5cf7`（仅 MobileLayout.vue）已推送 main，Jenkins 部署测试环境。**部署后触屏回归通过**（证书列表 94→0 回顶、考试列表 2349px 深 4 次上滑回 0、详情页 9:16=0.563、PC 回归）。截图 `gui-test-screenshots/2026-09-02-list-scroll-fix/verify/`。
2. ✅ **证书详情页 CertificateCard 修改已回退撤销**（第 7 节定论：破坏 9:16 定稿/导出比例，与列表页 bug 无关；git restore 恢复原样，不推送）。
3. ⚠️ **切屏强制交卷 / tabbar 修复待真机最终确认**：f493105（tabbar）测试环境已过但真机（微信 WebView/iOS Safari）未验；切屏没有考试数据无法端到端。

### P0：正式环境 build 后回归 ✅ 已完成（2026-09-01 实测）

**正式环境已 build**：index.html 引 `index-SV2mKqn8.js`（cf. 08-31 的 index 指纹不同），bundle 含 `menu-toggle`/`mobile-mask`/`sidebar-open` 特征字符串、auth chunk 含 `X-CSRF-Token`（cookie 构建已注入）。回归结果：

1. ✅ **admin（oceg2026）登录跳转正常**：/login → /school-admin，学校管理首页渲染完整（侧栏 8 项菜单、系统管理员 SCHOOL_ADMIN、8473 学生/278 教师/2001 题概览）。cookie+CSRF 链路 OK。
2. ✅ **手机视口 390×844 教师端三页全部通过**（admin 可访问 /teacher 路由，面包屑「教师首页」）：
   - /teacher、/teacher/classes、/teacher/statistics 三页 scrollWidth ≤ clientWidth，**无横向溢出**（390/390/382 ≤ 390）。
   - 侧栏收起 left=-260 / transform translateX(-260)，「打开菜单」汉堡按钮存在，抽屉可开（sidebarLeft→0、遮罩满屏 block）、遮罩点击关闭、**菜单项点击自动收起+跳转**（师生管理 → /school-admin/users）。
   - 截图 `gui-test-screenshots/2026-09-01-prod-regression/`（01-03）。
3. ⚠️ **切屏强制交卷待补验**：接口实测 `/api/exams` total=0（正式库仍无考试），无法触发；有考试后按交接超查：第 3 次 LEAVE（leaveCount=3）才 AUTO_SUBMIT。
4. ⏳ **证书返回修复 f4f50c4**：测试环境已验（三条链路全过，见第 3 节），**正式环境未 build**，待用户确认（用户已答复会通知运维正式部署）。
5. ✅ **tab 还原 443122d**：测试环境部署后回归通过（已考tab切换同步 URL、证书返回落已考 tab、链路2/3 不破，见第 4 节）；**正式环境未部署**，待与 f4f50c4 一并 build。
6. 🔴 **正式库题库重建（03_fix_questions_prod.sql）**：见第 5 节根因——08-28 导入把 2001 道题 content 列写错（判断题全为「错误」），需运维在正式库备份后执行 `D:\claude-work\lab-exam\03_fix_questions_prod.sql`；执行后回归 100029018 班级生成试卷。

P0 全部可验项通过（除第 6 项待运维执行 SQL），唯一遗留是正式库无考试导致的切屏端到端（与 08-31 交卷 1404 同样的前提缺失）。

### P1：正式环境启用前遗留

1. **fix-school-admin-password.sql 未执行**（学校管理员账号仍是 8-28 旧 SQL 状态：密码=admin 强密码 Gb$d!a$X8&eTbij4、need_change_password=0；方案 B 新密码 hByUWawE5^6aaW / TdFQBmaRV-#cs6）——需用户拍板是否执行。
2. **正式库无考试数据**（exams total=0）——正式发布后需要创建真实考试（建考-出题-组卷-发布全链路）。
3. 正式库本轮 SQL 导入后尚未做过真实考试（交卷/证书/去重/切屏）端到端验证。

### P2：本地代码/Git 事项

1. **本地未推送**：`server/src/modules/exam/exam.service.spec.ts`（去重用例，M 状态）——测试类改动按用户约定留在本地，等指示。
2. `gui-test-screenshots/`、CLAUDE.md 只留本地**绝不推送**（受保护分支 + 用户约定；本地历史曾重写分叉，勿强推）。
3. 提交/推送业务代码需用户明示；本批 e8a8967/e627ab8/f4f50c4/443122d 是用户明确答复后推的（f4f50c4 由用户答复「推送 + 触发测试部署」；443122d 由用户答复「修」后推送）。

---

## 关键环境事实（务必先读）

| 项 | 值 |
|---|---|
| 测试环境 | https://lab-exam-test.oceghome.com/（cookie 模式，需 sessionStorage csrf_token） |
| 正式环境 | https://lab-exam.oceghome.com/（cookie 模式） |
| 测试库 | 远程 192.168.0.165:13306 lab_exam（`lab_exam_rw` / `ZV9Se4awUevt`）；**本机 localhost:3306 是无关开发库，别改错** |
| 测试环境账号 | admin / `LabTest2026!`；张凯悦 2302220248 / `zxcvbnm123`（她自己改的测试密码） |
| 正式环境 admin | admin / `oceg2026`（**用户本人 09-01 自改**，非异常） |
| 正式库用户状态 | 8-28 SQL 版本；学校管理员=admin 强密码，need_change_password=0 |
| 认证模式 | 测试/正式均 cookie；正式构建参数 `VITE_AUTH_MODE=cookie` 必须注入 |
| 登录错误码 | 1001=密码错/用户不存在；1005=锁定；限流 1000 次/5min |
| 部署链路 | push origin main → 用户手动 Jenkins 部署测试 → 验证 → 用户通知运维 build 正式 |
| 仓库 | https://git.oceghome.com/aiproject/lab-exam（main） |

---

## 验证/调试技巧速查（本次会话沉淀）

1. **IAB 浏览器**（browser-use skill，主 agent 操作）：
   - `playwright.domSnapshot()` 返回 **JSON 字符串**而非对象，先 JSON.parse 再读。
   - `tab.goto()` 在带 beforeunload 的考试页会 `ERR_ABORTED`——用页面「返回」按钮走 SPA 导航（会弹「确认离开」，点确认）。
   - 截图：`tab.screenshot()` → `writeFile(Buffer.from(png instanceof ArrayBuffer ? png : buffer))`；失败偶发可重试。
   - **`document.hidden` 是实例不可配置 own property，覆写 `Document.prototype` getter 无效**——模拟切屏要走接口直调：`POST /api/student-exams/:id/events {eventType:'LEAVE'}`（与前端 handler 同一接口），带 `X-CSRF-Token`（sessionStorage 'csrf_token'）。
2. **确认线上新代码**：查 bundle 特征字符串（如 menu-toggle/mobile-mask/sidebar-open），index hash 不同属正常（构建参数差异）。
3. **测试库写操作**（重置考试次数等）：直接 mysql 连 192.168.0.165:13306。
4. **命令行密码含特殊字符**：用临时 .cjs 脚本 + 环境变量传值（bash 双引号会展开 `$`）。

---

## 相关链接

- 详细根因/证据：[[lab-exam-2026-09-01-teacher-mobile-adaptive]]、[[lab-exam-2026-09-01-leave-force-submit-off-by-one]]、[[lab-exam-2026-09-01-admin-password]]、[[lab-exam-2026-09-01-cert-back-nav-fix]]（晚间接力：证书返回修复）
- 前一天交接：[[session-handoff-lab-exam-cookie-mode-2026-08-31]]、[[session-handoff-2026-08-31-testenv-full-recheck]]
- 记忆索引：[[labexam-teacher-mobile-adaptive-missing]]、[[labexam-leave-force-submit-off-by-one]]、[[labexam-auth-mode-mismatch]]、[[labexam-admin-password-user-changed]]、[[labexam-testenv-db-topology]]、[[labexam-prod-staffadmin-password-strong]]、[[labexam-certificate-back-nav-fix]]

## 新 session 开场白建议

> 读取 Obsidian `Projects/实验室准入考试系统/交接文档/session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit.md` 与 `索引.md`；先确认正式环境是否已 build（问用户或查 bundle 特征），未 build 则继续 P0 等待；已 build 则按 P0 回归清单逐项验证。