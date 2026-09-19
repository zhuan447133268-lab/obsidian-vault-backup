# 2026-09-18 题库禁用后无法启用（脏数据卡校验）+ 前端 CSRF(1004) 静默自愈

> 状态：**✅ 全部闭环（2026-09-18）**——运维已执行清洗 SQL，API 独立复验：正式库脏数据 248→0（1866 总题数不变）、「安全帽」题（e242456b）启用返回 200（响应中 collegeId 已消失）；代码 `531254c`+`df072d5` 已推 main 随下次发版上正式
> 交付件：`D:\claude-work\lab-exam\05_clean_nonprofessional_college_prod.sql` + `05_clean_nonprofessional_college_prod-交付文案.md`
> 测试环境凭据变动：admin 密码 **LabTest2026! 已失效**（09-18 实测 401），测试库 hash 离线校验：admin=`oceg2026`、沈春洋/陈冰冰=`123456`

## 一、测试反馈与排查结论

测试老师反馈（正式环境、admin/oceg2026 账号）：题库管理页把题禁用后显示成功，再启用提示「启用失败」。涉及两道题：

| 题目 | 排查结论 |
|---|---|
| 「安全帽在物理力学实验中不需要佩戴」（JUDGE，e242456b） | ✅ **真 bug**，已修复并复验闭环（§二 §三 §八） |
| 「传感器与检测技术实验的安全要点？」（多选 ABCD，e53fc384） | ❌ **题目健康，是浏览器 token 互顶坑**（§四） |

排查路径：测试环境 API 全通（2069 题 0 条问题数据）→ 正式环境复现第一题（启用返回 400 `非专业题不能绑定学院`）→ API 全量扫描正式库 1866 题命中 248 条脏数据 → 第二题两个真实账号（admin、沈春洋）禁用→启用均 200 无法复现 → 定位浏览器侧。

## 二、根因：09-02 导入脚本映射错误埋的脏数据

- `generate_import_sql.py` 的 `QUESTION_FILE_MAPPING` 把「通识教育学院-题库.xlsx」映射成 `('通识教育学院', 'GENERAL_EDU')`——**通识题绑了学院**，违反后端「非专业题不能绑定学院」校验（`question.service.ts` validateCreateOrUpdate）。同表其他通用题填 None 是对的，唯独这行错了（按文件来源学院想当然绑定，未对照后端规则）
- 09-02 运维执行 `03_fix_questions_prod.sql`（DELETE+INSERT 全量快照）时，248 道脏数据进正式库；测试库非此路径导入，故测试环境 0 条、无法复现
- **为什么藏了两个多月**：列表/组卷只查不校验（组卷对通识题不按 collegeId 过滤，已核代码确认无影响）；规则只在「保存题目」时执行。禁用走 `DELETE /questions/:id`（disable() 只置 enabled=false **零校验**）永远成功；启用走 `PATCH`（update() **全量校验**）→ 撞规则 → 400。前端 catch 只弹「启用失败」不带原因
- 大白话：一个人入户时登记了不合规身份证号，平时查询不校验一直正常，一办需要重新核验的业务（启用/编辑）就被拒——错在当年录入，不在操作

## 三、修复（方案3 = 数据清洗 + 代码解锁，均已落地）

1. **数据清洗 SQL**（`05_clean_nonprofessional_college_prod.sql`，**不进 git**，交运维）：前置检查（应 248）→ 备份表 `questions_bak_20260918` → `UPDATE questions SET college_id=NULL WHERE category<>'PROFESSIONAL' AND college_id IS NOT NULL` → 回验（应 0）。交付文案含回执 5 条、回滚方案、业务回归步骤
2. **代码修复**（`531254c` 已推 main）：`update()` 里 body 只带 `enabled` 的 PATCH 视为纯状态切换，跳过 validateCreateOrUpdate、不改写其他字段；带内容字段的编辑仍全量校验。新增 2 条回归单测（脏数据仅启用成功且不碰其他字段、仅启用不校验非法答案），q4/q5 旧测语义改为「编辑内容时仍校验」；question 模块 12/12 绿、tsc 零报错
3. **导入脚本病根**（`generate_import_sql.py`，D:\claude-work 不进 git）：通识映射改 `(None, 'GENERAL_EDU')` 防再生成时重埋

**关联审核结论（用户已确认）**：「PATCH 无法解绑 collegeId（null 被 `?? existing` 吞掉）」+「编辑弹窗学院选择器不跟随分类」两问题在业务约束下（题目分类导入时定死、不改）**不成立**，不修。

## 四、「传感器」题：CSRF token 互顶坑（非题目问题）

- 该题（PROFESSIONAL 绑电气学院，数据合法）用 admin 和沈春洋两个真实账号 API 实测禁用→启用均 200；线上前端 chunk（`questions-B1hlDYG1.js`）逻辑与仓库一致
- 后端 CSRF = `HMAC(csrfSecret, JWT jti)`（`jwt-auth.guard.ts:50`），**每次登录/refresh 都轮换**；cookie 是浏览器级共享，CSRF 存在各标签页自己的 sessionStorage
- **两种失败机制均 curl 实测复现**（403 code1004 → 页面弹「启用失败」）：
  - 同浏览器第二账号登录 → 共享 cookie 被顶掉，旧标签页旧 CSRF 配新 JWT → 403
  - 同账号多标签页 → A 页 refresh 轮换 token 后，B 页旧 CSRF 失效 → 403
- 老师剧本：禁用那一刻 token 对有效；两次点击之间另一标签页 refresh/登了别的账号 → 启用撞 1004。全局 toast 闪过的「CSRF Token 缺失或错误」被「启用失败」盖住，未被发现
- **修复**（`df072d5` 已推 main）：request.ts 收到 1004 → 静默 refresh 换新 CSRF → 调 `/auth/me` 核对账号与本标签页登录快照（sessionStorage `user_account`，stores/auth 登录/fetchMe 时落）一致才重试一次（`_csrfRetried` 防循环、/auth/me 自身豁免防递归）；**身份被顶号则不重试**，清登录态跳登录页。vue-tsc 零报错、构建通过；无单测框架（仅 Playwright e2e），靠 curl 机制实测佐证

## 五、运维交付文案要点（05_clean_nonprofessional_college_prod-交付文案.md）

- 性质：数据修复 UPDATE，只动 questions 表，**不需发版/重启**
- 硬性前置：`SELECT DATABASE()` 确认 lab_exam_prod（防连测试库）→ 先备份（回执 248 行）
- 四步：前置检查（必须 248，不等就停）→ 备份 → 清洗 → 回验（必须 0）
- 回执 5 条全要截图；回滚 = JOIN 备份表还原
- 业务回归：题库页「安全帽」题（清洗前禁用）点启用应成功

## 六、环境凭据变动（09-18 实测）

- 测试环境 admin `LabTest2026!` **已失效**（401）；测试库（192.168.0.165:13306，lab_exam_rw/ZV9Se4awUevt）hash 离线校验：admin=`oceg2026`、沈春洋 BN100005453=`123456`、陈冰冰 IME000290=`123456`
- 正式环境沈春洋/陈冰冰密码 = 8-28 导入时的 admin 强密码 `Gb$d!a$X8&eTbij4`（实测可登录；fix-school-admin-password.sql 仍未执行）

## 七、闭环记录（2026-09-18）

运维执行完清洗 SQL 后，独立 API 复验（不依赖运维截图）：
1. 全量扫描 1866 题：非专业题绑学院 **0 条**（清洗前 248；总题数不变，无删增）
2. 「安全帽」题启用回归：`PATCH /api/questions/e242456b {enabled:true}` → **200**，响应中 `collegeId` 字段已消失，「非专业题不能绑定学院」不再拦截

## 八、遗留

- [x] ~~清洗 SQL 交运维执行 + 回执核验~~（09-18 完成，§七）
- [x] ~~老师回归「安全帽」题启用~~（09-18 由 API 回归通过代替，§七）
- [ ] `531254c`/`df072d5` 随下次正常发版上正式（清洗本身不等发版已生效；1004 自愈在发版前老师如遇多标签页问题仍靠刷新页面恢复）
- [ ] （知悉，低概率）导入去重键含 collegeId：清洗后旧脏行去重不命中，日后重复导入同批通识题可能产生重复题

相关概念卡：[[concept-csrf-token-pair-rotation]]；同日事故：[[lab-exam-2026-09-18-prod-500-audience-migration-missing]]；避坑 #31/#32
