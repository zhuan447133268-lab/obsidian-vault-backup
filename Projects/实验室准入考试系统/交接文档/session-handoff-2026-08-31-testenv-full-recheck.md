---
date: 2026-08-31
project: 实验室准入考试系统
type: 交接文档
status: 已完成
---

# 2026-08-31 测试环境全量复核 + UI 验收 —— 会话交接

> 对应验证记录：[[lab-exam-2026-08-31-testenv-full-recheck]]
> 截图证据：`D:\2026准入题库\gui-test-screenshots\2026-08-31-ui-verify\`（54 张）
> 前置会话：[[lab-exam-2026-08-31-production-issues-fixed]]、[[session-handoff-lab-exam-cookie-mode-2026-08-31]]

## 一、本次会话做了什么（一句话）

用户重部署测试环境后，从 Obsidian 调取全部历史 bug 修复记录，在测试环境（https://lab-exam-test.oceghome.com）逐一复核（API/DB 级 10 项）+ 委托浏览器子代理 UI 黑盒验收（12 项），**全部通过，无遗留缺陷**，测试数据已清理、账号已恢复，结果已写入 Obsidian。

## 二、验证结果全览（新 session 直接引用）

| 类别 | 项 | 结果 |
|---|---|---|
| 认证 | cookie + CSRF 统一模式（68c97ba） | ✅ 登录返回 csrfToken + Set-Cookie |
| API/DB | 学生重考 canRetake（082d471） | ✅ 时间语义 UTC，终态卷拒重考 |
| API/DB | 全校统计参与率≤100%（7942571） | ✅ 按学生最新试卷去重（7 人 vs 23 卷） |
| API/DB | 判断题启用兼容映射 | ✅ 禁用→启用闭环 |
| API/DB | 教师移除班级/删班级拦截（62b6c7c） | ✅ 1303 / 1204 / 1203 均生效 |
| API/DB | 证书学院筛选 + ZIP 前端化（a5a81a3/d3fceef） | ✅ 筛选同源；后端 zip→1400 引导；前端 CertificateExportPanel 本地打包 |
| API/DB | 判断题判分 TRUE→A（a4c94f0） | ✅ 快照 TRUE 答 A 判对 |
| API/DB | 王卓尔双角色越权（3da3697/32f7c77） | ✅ 双传 college+class 200，反例拦截 |
| API/DB | 班级年级 4 位年份（38544d0） | ✅ 221/25ab → 400，2023/2024 → 成功 |
| API/DB | 1404 事件上报静默（51a780b） | ✅ 代码指纹 + GUI 无弹窗 |
| **UI** | 教师端分享卡片/勾选保留/创建发布（6 项） | ✅ 全部 PASS |
| **UI** | 学生端窗口限制/按钮居中/禁缩放/答题交卷链路 | ✅ 全部 PASS（详见下） |
| **UI** | 管理端固定侧栏滚动/maxlength=20（2 项） | ✅ 全部 PASS |

**UI 学生端唯一疑点已闭环**：子代理 GUI 报告交卷 1403「试卷不存在或未生成」→ 复核确认是**已交卷后重复提交的正确拦截**（DB 中第一轮已 AUTO_SUBMITTED 成功）。API 完整重测：start→取卷 25 题→存答案 200→交卷 200（SUBMITTED，得分 4）→二次存/交均 1403 拦截→result 正常。**学生端进入→答题→交卷→看分链路真实可用。**

## 三、⚠️ 新 session 必读：环境事实（本次踩坑教训）

1. **双库拓扑**：测试环境后端连接的是**远程库**
   `mysql://lab_exam_rw:ZV9Se4awUevt@192.168.0.165:13306/lab_exam`
   本机 `localhost:3306/lab_exam`（root/20210406）是**无关开发库**，改了不生效（曾因此远程改密码后 API 仍 1001，浪费多轮）。
   - 已同步记录到记忆系统（labexam-testenv-db-topology）。
2. **账号登录唯一性**：同一账号串可能同时命中 student_no 与 staff_no 两行（例：2302220248 既有 TEACHER 行又有 STUDENT 行，findFirst 命中哪个不确定）→ 设测试密码前先确认唯一命中，尽量用不会撞号的新教工号。
3. **教师建考试的开始时间**：前端 date-picker 禁选过去日期；发布时若 start 早于 now-60s 会被自动顺延到 now+60s。要造「进行中」考试 → 发布后直接改库 start_time 为过去。
4. **发布前置**：DRAFT 考试必须先生成试卷（至少 1 张）才能 publish（1406「发布前必须已生成试卷」）。

## 四、本轮已清理（无需再处理）

- 两场 UI 测试考试（e0c42751「UI验证-分享卡片与勾选保留-0831」、fdddadac「UI验证-进行中考试-0831」）及全部 papers/paper_questions **已删除**，库中无残留。
- 临时密码（LabTest2026!）账号已恢复原值：admin=系统管理员、张凯悦 BN100009258（教师，need_change_password=1）、陈暄 2302220102（学生，=1）。
- admin 远程实际原密码 = LabTest2026!（哈希 CtQXn3…，恢复后实测可登录）。
- 恢复清单备份：`D:/tmp/remote_restore.json`（含各账号原 hash；python 的 /tmp 实为盘根 `D:\tmp`，bash 的 /tmp 是另一目录，勿混淆）。

## 五、索引中旧待办的本轮状态（可勾除）

- [x] canRetake 重考 400 已验证（082d471 生效）
- [x] 统计参与率去重已验证（7942571 生效，7vs23）
- [x] 判断题启用已验证
- [x] 教师班级关联删除/班级删除拦截已验证（1303/1204/1203）——「2026-08-14 教师班级关联删除未拦截进行中考试（待续）」已闭环
- [x] 证书 ZIP 前端化 + 学院筛选已验证（d3fceef 后端 zip→1400 引导 + 前端 JSZip 面板）
- [x] 手机端底部按钮三等分+禁止缩放已验证（GUI：按钮居中、user-scalable=no 有效）
- [x] 输入框字数限制（maxlength=20）与班级年级 4 位校验已验证
- [x] 2026-08-31 线上问题修复在测试环境已部署并验证（admin 登录跳转/cookie 模式/1404 静默均通过）

## 六、下一步候选（供新 session 挑选，非本次遗留缺陷）

1. **正式环境**（https://lab-exam.oceghome.com 或生产域名）同样为 cookie 模式后的同类复核（需运维确认已部署）。
2. 索引「六」仍挂着的非本次事项：测试环境交卷慢问题待排查、`college-admins.vue` 翻页验证、C+ 配色方案待验证、BN100005453/IME000290 初始密码 SQL（如需）、生产数据导入待运维执行。
3. 无新增 bug 待修。

## 七、相关链接

- 验证记录：[[lab-exam-2026-08-31-testenv-full-recheck]]
- 前置：[[lab-exam-2026-08-31-production-issues-fixed]]、[[lab-exam-cookie-mode-migration-checklist-2026-08-31]]、[[session-handoff-lab-exam-cookie-mode-2026-08-31]]
- 记忆：labexam-testenv-db-topology（双库事实）、labexam-auth-mode-mismatch、labexam-remember-files-local-only