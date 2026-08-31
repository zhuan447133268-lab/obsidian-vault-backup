---
name: lab-exam-2026-08-31-production-issues-fixed
description: 2026-08-31 线上问题排查：admin 登录不跳转、学校管理员初始密码、试卷重复题，已修复并 push
type: project
date: 2026-08-31
---

# 2026-08-31 线上问题排查与修复汇总

**时间**：2026-08-31
**仓库**：`D:\2026准入题库` → `https://git.oceghome.com/aiproject/lab-exam.git`
**会话目的**：结合 Desktop 排查汇报、代码与 Obsidian 记录，定位并修复正式环境问题

---

## 一、admin 登录成功但不跳转

### 根因
- 正式环境后端为 `cookie` 认证模式，但线上前端产物是按 `bearer` 模式构建的。
- `web/src/api/request.ts:62-73`：只有 `AUTH_MODE === 'cookie'` 时才给请求头加 `X-CSRF-Token`。
- 前端登录接口本身不校验 CSRF，能返回“登录成功”；但后续 `/me` 等接口因缺少 `X-CSRF-Token` 被后端 403，路由守卫拿不到用户信息，页面卡在登录页。

### 代码状态
- 仓库代码已支持双模式，无需改业务代码。
- `web/.env.production` 默认是 `bearer`，生产构建时必须显式注入 `VITE_AUTH_MODE=cookie` 或放 `.env.production.local`。

### 修复动作
- 未改代码；已在排查汇报中给出方案 A（构建注入，先救活）和方案 B（测试环境统一 cookie，根治）。
- 部署后验收：admin 能正常跳转；学生考试流程无 1404 弹窗。

---

## 二、学生交卷后弹「没有进行中的考试」

### 根因
- 交卷成功后，前端事件上报（心跳/焦点/切屏）仍继续，后端发现试卷已是终态，返回 1404。

### 代码状态
- 已修复并在远程 main（`51a780b`）。
- `server/src/modules/student-exam/student-exam.service.ts:420-429`：终态试卷事件上报静默忽略。
- `web/src/views/student/exam-paper.vue:153,283,298,305,345,350,504`：`submitted` 标志位阻止交卷后所有事件上报。

### 修复动作
- 无需再改代码；正式环境部署最新 main 即可。

---

## 三、学校管理员账号 BN100005453 / IME000290 用 123456 登录失败

### 根因
- `D:\claude-work\lab-exam\generate_import_sql.py` 把学校管理员也用了 `ADMIN_PASSWORD_HASH`，导致他俩密码变成了 admin 强密码 `Gb$d!a$X8&eTbij4`，而不是预期的 `123456`。
- 业务规则应为：**只有系统管理员 `admin` 用强密码，其他所有人（含学校管理员）初始密码 123456 并强制改密**。

### 修复动作
1. 修正 `generate_import_sql.py`：学校管理员改用 `DEFAULT_PASSWORD` 生成的 hash，`need_change_password = 1`。
2. 重新生成 `D:\claude-work\lab-exam\01_user_data.sql`、`02_question_data.sql`。
3. 给出正式环境立即修复 SQL（UPDATE 两个学校管理员密码为 123456 hash）。

### 验证
- bcrypt 验证新 SQL 中学校管理员的 hash 与 `123456` 匹配。
- admin 强密码未受影响。

---

## 四、BN100009258 试卷出现重复题

### 根因
- `server/src/modules/exam/exam.service.ts:808-871` 和 `server/src/modules/student-exam/student-exam.service.ts:954-1009` 的 `selectQuestionsForPaper` 在抽题时 **没有去重**。
- 单选题池子同时包含 `GENERAL_SAFETY` 和该学院 `PROFESSIONAL` 题目；若同一题干在两处都存在，就可能同时被抽中。

### 修复动作
1. 在两个 service 的 `selectQuestionsForPaper` 中增加**逐题去重**：用 `usedIds` + `usedContents` 集合，已经选过的题（按 id 或题干）不再入选。
2. 错误提示更新为“含学院过滤及去重后”。
3. 新增单测复现该场景：`server/src/modules/exam/exam.service.spec.ts`。
4. 代码修复已 push 到 main：
   ```text
   commit 0676156
   fix(exam): 组卷时跨分类/跨题库去重，避免同一题干重复出现
   ```
5. 单测文件按用户偏好保留在本地工作区，未 push。

### 验证
```bash
npx jest --runInBand
# Test Suites: 10 passed, 10 total
# Tests:       93 passed, 93 total
```

### 测试环境实测（2026-08-31 补充，已确认生效）

已在 https://lab-exam-test.oceghome.com 用真实 API 触发组卷验证（commit 0676156 已部署测试环境）。

**对比证据**（同一考试 d052f0c6「测试」、同一考生 2302220248 张凯悦、同一 paper_config）：

| 试卷 | 生成时间 | 题数 | 唯一题干数 | 结果 |
|---|---|---|---|---|
| 5f4b1c20（修复前） | 01:44（部署前） | 25 | 24 | ❌ 有跨分类重复 |
| ad729d1b（修复后） | 本次实测触发 | 25 | 25 | ✅ 无重复 |

旧卷重复题即典型场景：「造成触电事故的直接因素是（ ）」同时命中 GENERAL_EDU（qid 14dfb82e）与 GENERAL_SAFETY（qid 76e006a4）各一题。新卷同配全 25 题唯一。

**实测过程**：管理端 regenerate 需管理账号（密码不可用）→ 改为临时延后考试 end_time → 学生调 `POST /student-exams/:id/start` 重考 → 服务端走修复后 `selectQuestionsForPaper` 组新卷 → 查 `paper_questions` 无重复 → **验证后已恢复**（end_time 还原、验证卷删除、used_count 还原 7/10）。

**遗留提醒**：
- `student-exam.service.spec.ts` 未补去重单测（与 exam.service 同一套去重实现，仅 exam.service.spec.ts 有覆盖），建议补齐防分叉。

---

## 五、附带修复：导入脚本题干被选项覆盖

### 根因
- `generate_import_sql.py` 的选项循环里复用了变量名 `content`，把题干 `content` 覆盖成了最后一个选项的内容。

### 修复动作
- 修改变量名为 `option_content`。
- 重新生成 `01_user_data.sql`、`02_question_data.sql`，新 SQL 题干正确。

---

## 六、待新 session 继续处理

1. **部署后端**：正式环境拉取 main 最新代码并重启服务（含 `0676156` 去重修复）。
2. **重新生成 BN100009258 试卷**：0676156 只对部署后新生成试卷生效；正式环境部署完成后，测试人员在管理端对 BN100009258（及同样有重复的旧卷）点“重新生成试卷”。测试环境已实测修复生效，验证卷已清理不留痕。
3. **admin 登录不跳转**：按方案 A 或 B 处理正式环境前端构建（`VITE_AUTH_MODE=cookie`）。
4. **学校管理员密码**：如需让沈老师/陈冰冰用 123456 登录，执行给出的 UPDATE SQL。
5. **验证**：
   - admin 登录正常跳转；
   - 学生交卷无 1404；
   - BN100009258 试卷无重复题（管理端重新生成后验证）——测试环境同逻辑已实测通过；
   - 多抽几份不同学生试卷抽查去重效果。

---

## 关联

- [[lab-exam-deploy-checklist]]
- [[session-handoff-lab-exam-prod-import-sql-regenerated-2026-08-28]]
- [[生产环境数据库导入清单]]
