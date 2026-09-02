# 2026-09-01 正式环境「题库[JUDGE]可用题目不足」根因定案：正式库题库数据导入错位（非代码 bug）

> 用户复现：正式环境 100029018（电气电子智能工程学院学院管理员）给班级学员生成试卷报错——`题库[JUDGE]可用题目不足（含学院过滤及去重后），需要 10 道，实际 1 道`。

## 结论一句话

**不是组卷代码 bug，是正式库题库数据整体导入错位**：2001 道题（SINGLE 800 / JUDGE 800 / MULTIPLE 401）的 `content`（题干）列被写成了**每题最后一个选项的文本**。判断题选项恒为 [A正确, B错误] → 800 道判断题 content 全部是「错误」→ 组卷按题干去重后仅剩 1 道 → 1401 报错。

## 排查证据链（正式环境实测，admin/oceg2026 登录）

1. **复现**：admin 对 03289e87 学生触发 `POST /api/exams/:id/papers/batch-generate`，job 返回 failed，error 与用户报错一字不差（`需要 10 道，实际 1 道`）。
2. **理论可用数**：`/api/questions` 统计 DQ 学院（e02020fe-…）判断题 = 专业 100 + 通用安全 100 = 200 道，全部 `enabled=true`；考试 paperConfig.collegeId 正确指向正式库 DQ UUID。理论与报错矛盾。
3. **数据真相**：
   - JUDGE 800 道 content **100% 全为「错误」**（8 个学院源各 100 道均匀分布）。
   - SINGLE 800 道 content 逐题 = 该题最后一个选项文本（示例：content「短时间操作」= 该题 D 选项；抽样 500 道匹配率 100/100）。
   - MULTIPLE 401 道同理错位，但因每题末选项各不相同，去重后仍 ≥5 道，故此前只有判断题暴雷。
   - 全部题目 `createdAt` 完全同一时刻 `2026-08-28T15:06:48.400Z`（SQL 批量导入特征），id 与 08-31 版 `02_question_data.sql` 完全不同。
4. **同源性验证**：正式库 DQ 单选题与源 xlsx `电气电子智能工程学院-实验室安全准入考试题库.xlsx` 逐题选项指纹完全一致（抽查 5 道全部命中）→ 同一批源数据，正确题干预案就在 xlsx / 08-31 SQL 里，只是 08-28 那次导入把「题干」列读错。
5. **代码无罪**：`exam.service.ts` / `student-exam.service.ts` 的 `selectQuestionsForPaper` 过滤（OR: GENERAL_SAFETY + PROFESSIONAL@collegeId，enabled=true，usedContents 去重）逻辑正确——测试库同代码正常。报错是数据层的直接结果。

## 修复方案（已生成，未执行）

- **不用改代码**。
- 08-31 版 `D:\claude-work\lab-exam\02_question_data.sql`（2001 道、题干正确）college_id 用的是脚本自建 UUID，**不能直接用于正式库**（正式库学院 UUID 是另一套，直接执行会把专业题挂到不存在的学院）。
- 已生成 **`D:\claude-work\lab-exam\03_fix_questions_prod.sql`**：依据 02 版正确题目，把 college_id 全部映射为正式库 8 个学院真实 UUID（DQ→e02020fe、GS→e5b8ef13、JY→2a0e30dc、QC→e345b222、YS→561a67e7、ZN→5faa2eda、XX→929ea2be、TS→8141d8bd），`DELETE FROM questions` 后重插 2001 道，新 id。
- **校验已做**：解析 2001 行全成功；college_id 分布 8 学院各 250~251 + NULL 250；无旧 UUID 残留；模拟组卷 DQ 判断题唯一题干 = 100 专业 + 100 通用安全 = 200 道（≥10 充足）。
- 正式库当前 1 个草稿考试、0 份试卷（papers total=0），paper_questions 用快照不依赖 questions 外键，**重建题库无副作用**。

## 待办

- [ ] 运维在正式库**备份后**执行 `03_fix_questions_prod.sql`（或管理端重新上传 8 份 xlsx 等效）。
- [ ] 执行后我回归：100029018 班级生成试卷不再报 1401；单选题题干显示恢复正常；抽查判断题题干正确。

## 关联

- 08-28 同批数据错位也影响**测试库**（2069 道同样 content 错位，因判断题 content 不同源未暴露），测试库如需彻底修复可另行评估。
- 相关：[[lab-exam-2026-09-01-cert-back-nav-fix]]（同日正式环境排查）、[[session-handoff-lab-exam-prod-import-sql-regenerated-2026-08-28]]（08-28 导入 SQL 重生成背景）