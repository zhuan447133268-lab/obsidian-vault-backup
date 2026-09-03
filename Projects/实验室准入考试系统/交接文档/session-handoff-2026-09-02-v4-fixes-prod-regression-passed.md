# 交接：09-02 四修复 + 题库重建 SQL 正式环境回归已完成

- 日期：2026-09-02
- 状态：🟢 **正式环境回归完成**（本交接后的 session 已验证闭环）
- 项目：实验室准入考试系统（lab-exam）
- 关联：[[session-handoff-2026-09-02-v4-fixes-prod-deployed-regression]]（前置交接，本份是其回归执行结果）、[[lab-exam-2026-09-01-prod-judge-data-corrupt]]、[[session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit]]

## 一、结论速览

| 项 | 结果 |
|---|---|
| 部署指纹 | ✅ 正式 `index-CYN9JZn7.js` ≠ 09-01 `index-SV2mKqn8.js`,新构建已上线 |
| 正式/测试同构建 | ✅ 主 JS MD5 完全一致（`2a6d50c0…`）,CertificateCard CSS 亦一致 → 测试环境行为闭环即正式行为 |
| 题库重建 SQL 生效 | ✅ 判断题 754 道**全部唯一**、`badContent=0`;单选/多选 4 选项结构正常 |
| 组卷不再 1401 | ✅ 教师端 100029018/oceg2026 对 23电子一班「测试考试」生成试卷 **39/39 全部成功,`failedCount:0, error:null`** |
| 新卷判断题题干 | ✅ 完整命题文本(如「传感器实验室中激光类设备的安全使用?」「西门子S7-1200/1500 PLC的PROFINET通信电缆应使用()」),不再全是「错误」 |
| 四修复产物特征 | ✅ CSS 行为嗅探 4 特征全命中(见下) |
| admin 登录 | ✅ admin/oceg2026 → `/school-admin` 正常(cookie 构建链路 OK) |
| 详情页保存图片 | ✅ 导出 PNG **1074×1908,ratio 0.5629 ≈ 9/16 竖版** |
| 学生端 UI 触屏回归 | ⚠️ 正式库**全部学生 needChangePassword=true**(08-28 导入后无人改过密),无法 UI 登录学生端;以「同构建产物一致 + 测试环境触屏闭环」作为行为证据(详见五) |

## 二、账面清单逐条验证记录

**1. 四修复行为验证(正式产物层)**
- 部署指纹:`index-CYN9JZn7.js`,与测试环境相同(同一构建批量部署)
- CSS 行为嗅探硬证据(交接文档经验:别搜主入口 JS 字符串):
  1. `6ac5cf7` 列表回顶 → 正式 CSS `.mobile-layout{height:100vh;overflow:hidden}` + `@supports` 分支 `height:100dvh`;`.mobile-content{-webkit-overflow-scrolling:touch;overflow:hidden auto;flex:1}` ✅
  2. `f493105` tabbar 上跑 → less 编译后 `@media (width>=481px){.van-nav-bar--fixed,.van-tabbar--fixed,.exam-paper-page .bottom-actions{left:50%;transform:translateX(-50%)}}`(注意 less 把 min-width:481px 编译成 `width>=481px` 语法,搜字符串要按这个形态)<font color="gray">→ 手机上不再有 transform 污染,默认 vant left:0 贴底</font> ✅
  3. `443122d` tab 还原 / `f4f50c4` 证书返回 → 纯 JS 行为,同构建产物下与测试环境一致(测试环境三链路回归已全过) ✅
- **四修复内容特征全部在正式产物命中** + **正式=测试字节级一致** → 四修复正式生效判定成立

**2. 题库/组卷(SQL 生效验证)**
- 判断题 total=754,分页拉全 754 条,`uniqueContents=754`,`badContentCount=0`(修复前:去重后仅剩 1 道题干「错误」)
- 单选/多选抽样:题干正常、每道 4 个选项(如多选「机房供电系统包括?」4 选项、单选「新能源汽车电池包装车后,必须进行的检测是()」4 选项)
- 组卷实弹:教师端 100029018/oceg2026 → `/teacher/exams/10d8e158-…`(测试考试,23电子一班,草稿) → 「选择参考学生」勾选 →「生成试卷(已选 39 人)」 → POST `/papers/batch-generate` 201 jobId → 轮询 `status:running→done, completed:39/39, failedCount:0, error:null` → 试卷列表 39 份 DRAFT 全部生成 ✅ **不再 1401**
- 抽查新卷内容(faca7112,学生张雪晴):25 题,判断/单选/多选题干均完整正常 ✅

**3. 详情页保存图片目检**
- 测试环境(同构建)张凯悦 zxcvbnm123 登录 → 证书列表 → 查看证书 → 卡片 `358×636 ratio 0.5625` → 点「保存图片」真实下载 PNG → **1074×1908 ratio 0.5629 ≈ 9/16 竖版** ✅
- 正式产物 CertificateCard chunk CSS 含 `aspect-ratio:9/16`(定稿特征,勿移除)✅

**4. admin 登录**
- admin/oceg2026 → `/school-admin`,菜单 11 项正常(首页/学院信息/专业管理/班级管理/学校管理员/学院管理员/师生管理/教师分班管理/题库管理/证书导出/全校统计)✅

## 三、账号备忘(双端密码不同)

- 学生:测试 `2302220248 / zxcvbnm123`(她自己改的密);正式 `2302220248 / 123456`(**正式仍是初始密码未改,登录被强制跳改密页——见五**)
- admin:`admin / oceg2026`(用户 09-01 自改,Gb$d!a$X8&eTbij4 已失效非 bug)✅ 实测可用
- 教师/学院管理员:`100029018 / oceg2026`(本次新用;属电气电子智能工程学院,TEACHER+COLLEGE_ADMIN)✅ 实测可用

## 四、遗留/待办(不含本次回归)

- [ ] `fix-school-admin-password.sql` 仍**待用户拍板**(正式库学校管理员 BN100005453/IME000290 仍是旧强密码态)
- [ ] 正式库有真实考试后:交卷/证书/切屏强制交卷(e627ab8)+1404 上报(51a780b)端到端(测试环境均已过,此待办不变)
- [ ] 正式库学生端 UI 触屏回归:待任意学生完成首次改密后,用其账号重跑 verify-mobile-scroll(改 BASE 正式),补 UI 级证据(本次以产物+同构建闭环佐证)
- [x] **6a789c4 iOS 聚焦放大修复**:✅ 已闭环到正式——测试环境 09-02 部署实测通过(见「七」)；**正式环境 2026-09-03 10:47 发版回归通过**（指纹 CYN9JZn7→SVt7NSZO 与测试同构建、主 JS MD5 双环境一致、viewport 禁缩放+16px 真触屏实测 PASS、admin/oceg2026 登录正常；截图 `gui-test-screenshots/2026-09-03-prod-regression/`）；**仅剩测试老师手机真机复测**
- [ ] **导航栏上跑复测(测试 09-02 再报)**:代码两处修复(f493105 transform 限 PC + 6ac5cf7 滚动收容器)均在测试/正式双环境产物确认生效,Chromium 8 宽度/超长内容逐帧 178 样本/PC 520-760/WebKit iOS 内核/iPad 触屏**全部零漂移无法复现**;待测试老师提供设备型号+浏览器+简要步骤或录屏定向(重点:是否为真机橡皮筋 overscroll 系统行为、是否微信内测、是否吃旧缓存)

## 五、坑与经验(本次新收)

1. **正式库全部学生 `needChangePassword=true`**(08-28 导入,初始密码 123456 从未改密),登录导航守卫强制去 `/change-password`——学生端 UI 触屏回归在正式环境**无法用现有账号执行**;不能替真实用户改密。判断线上修复的三级证据:①部署指纹变化 ②CSS 行为嗅探(有效) ③真实 UI 操作(本次被数据态挡住,以 ①②+同构建闭环代替)
2. **less 编译媒体查询语法**:global.less 的 `@media (min-width:481px)` 在产物 CSS 里成为 `@media (width>=481px)`——搜索线上 CSS 里媒体查询要用编译后形态,否则误判"未修复"
3. 组卷接口链:`POST /exams/:id/papers/batch-generate` → jobId → `GET /exams/:id/papers/generate-progress?jobId=` 轮询(异步任务,不可当作同步返回)
4. 前端登录态存 **sessionStorage**(不是 localStorage;键 `csrf_token`)— 用 Playwright 页面内 fetch 调 API 需在页面上下文读 `sessionStorage.getItem('csrf_token')` 并带 `X-CSRF-Token` 头,否则 1004
5. 正式/测试双环境**同构建同指纹**,正式产物可信度 = 测试环境行为闭环 + CSS 特征命中,两者结合可放心下结论

## 六、设备与证据

- 截图:正式回归全程证据在 `D:\2026准入题库\gui-test-screenshots\2026-09-02-v4-prod-regression\`(admin 登录/教师端/生成试卷/题库抽查/证书详情 9:16/保存图片导出 PNG)
- 脚本(临时,已清理示例如下,均在 Temp):probe-*.mjs 系列 + verify-mobile-scroll.mjs(触屏回归基准脚本,改 BASE 与 STUDENT 即可复用)

## 七、iOS 聚焦放大修复(6a789c4,测试新增反馈)

- **反馈原文**:学生端刚进登录页正常,点击输入框后页面放大;点击登录跳转首页后仍放大,部分内容展示不全
- **定性**:✅ 是 bug(ios Safari 聚焦 <16px 输入框自动缩放 viewport + 全局 viewport 未禁缩放)
- **根因**:全局 `index.html` viewport 只有 `width=device-width, initial-scale=1.0`,无 `maximum-scale/user-scalable=no`;登录框 el-input 字号 14px(<16px 阈值)→ Safari 聚焦自动放大;SPA 路由切换不重置缩放态 → 首页残留放大
- **修复(仅 2 文件,已推 main,commit 6a789c4)**:
  1. `web/index.html`:viewport 加 `maximum-scale=1.0, minimum-scale=1.0, user-scalable=no, viewport-fit=cover`(与线上 exam-paper 内 禁止缩放 一致成为全局)
  2. `web/src/views/login/index.vue`:登录卡内 `:deep(.el-input__inner){font-size:16px}` 双保险
- **验证**(Playwright chromium mobile + touch 模拟):聚焦后 `visualViewport.scale=1`(不放大)、输入字号 16px、页面无横向溢出;构建产物内 viewport meta 与 `login-*.css` 16px 规则均在
- **验证-测试环境实测**(2026-09-02,`https://lab-exam-test.oceghome.com`,iPhone 390×844 触屏模拟,账号 2302220248/zxcvbnm123):登录页聚焦前后 `vvScale=1`(不放大)✅;账号/密码框聚焦 `inputFont=16px` ✅;真实登录跳转 `/student` 后 `vvScale=1` 无残留放大 ✅;首页 `scrollWidth=390=clientWidth` 无横向溢出 ✅;部署指纹:线上 index.html viewport 已含 `maximum-scale=1.0, user-scalable=no`,入口 JS `index-SVt7NSZO.js`(新构建)。截图 `D:\2026准入题库\gui-test-screenshots\2026-09-02-focus-zoom-test-env\`
- **已知坑**:Vite 懒加载分包,登录页 scoped 样式在 `login-*.css`(不在主入口);验证聚焦放大要用真触屏语义(Playwright `isMobile+hasTouch`),桌面模拟测不出
- **测试老师话术**(简短版):已修复并提交,登录页聚焦不再放大、跳转首页也不残留放大,待部署后请在手机上复测