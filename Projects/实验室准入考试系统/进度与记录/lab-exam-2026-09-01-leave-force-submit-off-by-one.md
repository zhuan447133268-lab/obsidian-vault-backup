---
name: lab-exam-2026-09-01-leave-force-submit-off-by-one
description: 考试离开强制交卷 off-by-one：提示"3 次离开强制交卷"但第 2 次就强制交卷。根因=e78afe8 引入 +1 双重计数（事件先写入、count 已含当前次），测试环境实测铁证，已修复（去掉 +1）单测补边界
type: project
date: 2026-09-01
---

# 考试离开强制交卷提前一拍（off-by-one）排查与修复（2026-09-01）

> 用户反馈：手机和 PC 端都考试时，提示"离开三次强制交卷"，但**离开第二次就会强制交卷**。此前测试环境测过没问题，正式环境反馈有。

## 根因（代码 + git 历史双重确认）

`server/src/modules/student-exam/student-exam.service.ts` `reportEvent()`：

1. **LEAVE 事件先 `examEvent.create` 写入**（此顺序自 07-13 057f758e 起就是如此）。
2. 随后 `examEvent.count` 查询 `PAGE_HIDE + source=LEAVE`——**count 已包含当前这次**。
3. **e78afe8（2026-08-11）"切屏计数 off-by-one 修复"** 加了 `if (leaveCount + 1 >= maxLeave)`，注释"当前这次 LEAVE 也要计入"——但 count 早已含当前次，再 +1 即**双重计数**。
4. 回归点就是 e78afe8：该次提交把语义从「count 含当前次，>=maxLeave 判定」改成「再 +1」，实际触发点从 maxLeave 提前到 **maxLeave-1**（阈值 3 时第 2 次就强制交卷）。
5. 单测与实现脱节：原单测 `examEvent.count.mockResolvedValue(2)` 注释"已有 2 次，本次第 3 次"——假设 count 只数之前事件，与真实实现（count 含当前次）不符，所以单测全绿而线上行为错误。

## 测试环境实测（铁证）

考试「我要测测测测测」（98bb3da1）学生张凯悦（2302220248）：
- **修复前** 卷 `4072b07e`（07-14 IN_PROGRESS）事件序列：第 1 次 LEAVE 07:14:00.746 → 第 2 次 LEAVE 07:14:15.784 → **AUTO_SUBMIT 07:14:16.022**（score=8），总共仅 2 次 LEAVE 即强制交卷。
- 该生此前 7 张卷全是 AUTO_SUBMITTED（06:48~06:52 每 20~70 秒一张）——同一 bug 的连环受害卷。
- 模拟方式：覆写 `Document.prototype.hidden` getter 触发 `visibilitychange`（不可直接 redefine document.hidden），前端按真实链路上报 LEAVE。

## 修复后部署复验（2026-09-01 部署 e627ab8 / Jenkins）

对象：卷 `a69cced1`（张凯悦第 9 次考试）；因张凯悦该考试已考满 10 次（used_count=10），先重置测试库 student_attempts used_count=8 再开卷。

| 次数 | 接口返回 | 库事件（server_time） | 卷状态 |
|---|---|---|---|
| 第 1 次 LEAVE | leaveCount=1, forceSubmitted=false | 07:58:48.861 LEAVE | IN_PROGRESS ✅ |
| 第 2 次 LEAVE | leaveCount=2, forceSubmitted=false | 07:58:58.638 LEAVE | IN_PROGRESS ✅（修复前此处即交卷） |
| 第 3 次 LEAVE | leaveCount=3, forceSubmitted=true | 07:59:07.375 LEAVE → 07:59:07.510 AUTO_SUBMIT | AUTO_SUBMITTED（score=0）✅ |

AUTO_SUBMIT payload：`{ reason: 'switch_screen_limit', leaveCount: 3 }`。前端 UI：「已考」tab 显示「自动交卷」；结果页 0 分 / 自动交卷 / 用时 2:16 / 剩余 1 次。截图 `gui-test-screenshots/2026-09-01-leave-force-submit/01-result-after-3rd-leave.png`。

**结论：测试环境部署验证通过——第 1、2 次离开仅警告，第 3 次才强制交卷。可通知运维 build 正式环境。**

## 正式环境核查（只读）

- `POST /api/auth/login`（admin/oceg2026）code 0 → `GET /api/exams` **total=0，无考试数据**（与 08-31 结论一致）。
- 正式部署构建与测试环境同源（main 自 e78afe8 起都含该 bug），**同一代码在手机/PC 触发同样行为**——用户反馈与 bug 完全吻合；正式环境当前无考试无从实测，逻辑一致性已由测试环境实测+代码虚线覆盖。

## 修复（已本地完成，未推送）

`student-exam.service.ts` 第 468-469 行：`if (leaveCount + 1 >= maxLeave)` → **`if (leaveCount >= maxLeave)`**（count 已含当前本次，达到阈值即交卷），注释同步修正。

结果推演（maxLeave=3）：第 1 次警告"已离开 1 次"→ 第 2 次警告"已离开 2 次"→ **第 3 次才强制交卷** ✅

## 单测（已同步对齐真实语义）

- 第 3 次（count=3）→ 强制交卷，AUTO_SUBMIT payload leaveCount=3 ✓
- **新增**：第 2 次（count=2）→ 不强制交卷（off-by-one 回归保护）✓
- 第 1 次（count=1）→ 不强制交卷 ✓（原 mock 0 修正为 1）
- 全量 10 suites / 95 tests 全绿，`nest build` 通过。

## 相关

- commit：`e627ab8`（fix(student-exam): 切屏强制交卷 off-by-one，已推送 origin main）
- 记忆：[[labexam-leave-force-submit-off-by-one]]
- [[lab-exam-2026-08-31-testenv-full-recheck]]（历史 bug 复核不含此条）