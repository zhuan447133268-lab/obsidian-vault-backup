---
date: '2026-08-13'
tags:
  - lab-exam
  - bug-fix
  - 交接文档
---
# 2026-08-13 教师班级统计按考试范围过滤 —— 会话交接

**状态**：代码已修复并 push 到 `main`，等测试环境部署验证。  
**commit**：`2196f9c`

## 问题

教师 PC 端：班级创建考试时指定了部分参考学生，但班级统计筛选该考试后，列表展示了班级全部学生，未做过滤。

## 根因

`server/src/modules/statistics/statistics.service.ts` 的 `getTeacherStatistics` 中：

- 学生查询 `studentWhere` 只按教师管理的班级过滤。
- 当传入 `examId` 时，试卷查询会按考试过滤，但学生查询没有按考试实际组卷范围过滤。
- 结果：列表展示了班级全部学生，而不是这场考试已生成试卷的学生。

## 修复方案

当传入 `examId` 时，先查询该考试下所有 `paper.studentId`，将学生查询范围限制在这些学生 ID 内：

- 班级 50 人，考试只给 30 人组卷 → 统计只显示 30 人。
- 不传 `examId` → 保持原逻辑，显示班级全部学生。
- 考试无试卷 → 直接返回空列表。

## 修改文件

- `server/src/modules/statistics/statistics.service.ts`
- `server/src/modules/statistics/statistics.service.spec.ts`（新增 3 个单元测试）

## 验证结果

- `npx jest src/modules/statistics/statistics.service.spec.ts`：3/3 通过。
- `npx tsc --noEmit`：零报错。
- `npm run build`：构建成功。

## 测试环境部署后验证步骤

1. 用账号 `BN100009258` / 密码 `zxcvbnm123` 登录教师端。
2. 创建一场考试，在详情页"选择参考学生"时只勾选班级中的部分学生。
3. 生成试卷并发布考试。
4. 进入"班级统计"，筛选该考试。
5. **期望**：列表只显示第 2 步勾选的学生，未勾选的学生不出现。
6. 清除考试筛选，**期望**：列表恢复显示班级全部学生。
7. 关闭考试后再次筛选该考试，**期望**：仍只显示该考试范围内的学生。

## 相关记录

- [[lab-exam-student-retake-400-fix-2026-08-13]]
- [[lab-exam-deploy-checklist]]
