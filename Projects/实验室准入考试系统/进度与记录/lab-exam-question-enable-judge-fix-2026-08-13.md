---
name: lab-exam-question-enable-judge-fix-2026-08-13
description: 学校管理员PC端题库管理：判断题禁用后再启用失败，已修复并push
metadata: 
  node_type: memory
  type: project
  originSessionId: 79485d53-99a8-46cb-9d67-59c98547f482
  modified: 2026-08-13T01:56:13.752Z
---

**时间**：2026-08-13
**分支**：`fix/question-judge-enable`（已 fast-forward 合并到 `main` 并 push）
**修改文件**：
- `server/src/modules/question/question.service.ts`
- `server/src/modules/question/question.service.spec.ts`（新增）

**Bug 根因**：
学校管理员 PC 端题库管理点击「启用」时，前端只传 `{ enabled: true }`，后端 `QuestionService.update()` 会合并数据库中的 `options` 和 `answer` 并调 `validateCreateOrUpdate`。判断题在导入时答案被存为 `['TRUE']` / `['FALSE']`，但选项 key 是 `['A', 'B']`，导致校验 `optionKeys.includes('FALSE')` 失败，报错「答案 FALSE 不在选项中」。

**修复方案**：
在 `validateCreateOrUpdate` 中对判断题答案增加兼容映射：若答案是 `TRUE`/`FALSE` 且选项恰好两项，则映射到第一项/第二项。逻辑与 `student-exam.service.ts` 的 `normalizeJudgeAnswer` 保持一致。**仅用于校验，不修改数据库存储的 answer**。

**验证**：
- 新增 5 个单元测试用例全部通过（FALSE/TRUE/A/B 启用 + 非法答案报错）
- `npx tsc --noEmit` 零报错

**上下游影响**：
- 上游创建/导入/编辑判断题旧数据不再报此错
- 下游组卷只存 `answerSnapshot`，不受影响
- 学生考试比对已有兼容逻辑，不受影响
- ⚠️ 前端 `QuestionEditDialog.vue` 若数据库答案是 `FALSE`，编辑弹窗不会默认选中选项（未在本次修复）

**Why：** 导入逻辑与校验逻辑对判断题答案格式的约定不一致，旧数据触发了本不应失败的校验。

**How to apply：** 后续若再遇到「答案 X 不在选项中」且题型为判断题，优先检查导入/编辑/校验三方对 TRUE/FALSE 与 A/B 的约定是否一致；如需彻底根治，可考虑统一把判断题答案迁移为选项 key。
