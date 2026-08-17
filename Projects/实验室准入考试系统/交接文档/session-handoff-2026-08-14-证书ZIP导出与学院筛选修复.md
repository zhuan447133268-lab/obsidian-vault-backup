---
date: '2026-08-14'
tags:
  - lab-exam
  - bug-fix
  - 交接文档
status: partial
type: session
---

# 2026-08-14 证书 ZIP 导出迁移收尾 + 证书导出学院筛选失效修复 —— 会话交接

**状态**：代码均已 push `main`（`d3fceef` / `2c64e45` / `a5a81a3`）。
其中 `d3fceef`、`a5a81a3` 为**后端**改动需重新 build+部署后端才生效；
`2c64e45` 同为后端。前端无改动。

---

## 一、证书 ZIP 导出：前端化迁移收尾（commit `d3fceef` / `2c64e45`）

### 背景

- 旧实现：ZIP 导出走后端 puppeteer 无头浏览器截图 + archiver 打包
  （`certificate-image.service.ts` / `certificate-template.ts`）。
- 测试环境服务器**无法运行 chromium** → 点「导出 ZIP」后端 500。
- 此前的未提交改造：ZIP 迁移到**前端**（`html-to-image` toPng + JSZip 打包，`CertificateExportPanel.vue`），本次将其完善并收尾。

### 关键改动（`d3fceef`）

后端（收窄为 Excel-only 导出）：
- `certificate.service.ts`：`ExportCertificatesParams.format` 改可选；导出内移除 zip 分支（恒返回 Excel）；`findAdminCertificates` 增 `majorName` 并 include `major`。
- **删除死代码**：`certificate-image.service.ts`、`certificate-template.ts`；移除 `archiver`/`puppeteer` 依赖（archiver 仍为 exceljs 传递依赖）；清理 spec 中僵尸 `jest.mock`。
- `exam.service.ts`：试卷生成 job 用真实 pending 数（排除已有 DRAFT/IN_PROGRESS），completed 只对 `result.generated` 累加。

前端：
- `certificate.ts` API：`ExportCertificatesParams = AdminCertificateListParams`（无 format），移除 zip 分支，文件名 `certificates_export.xlsx`，timeout 10000。
- `CertificateExportPanel.vue`：ZIP 按钮走**前端流程**——分页拉全量（pageSize 200）→ `document.fonts.ready`（规避首张截图回退字体）→ 循环 `toPng(pixelRatio:3)` → JSZip DEFLATE level 6 → 下载 `certificates_YYYY-MM-DD.zip`；成功 toast「ZIP 导出成功」；≤500 限制，>200 二次确认。
- `CertificateCard.vue`：抽公共证书卡片（9:16 金边版，暴露 `cardRef`），学生端 `certificate-view.vue` 复用（1200×2133 截图验证 OK）。

### 排查记录：部署后「点 ZIP 却下载 Excel」

**现象**：用户反馈点「导出 ZIP」→ 弹「导出成功」→ 浏览器下载的是 Excel（`certificates_2026-08-14.xlsx`），不是 ZIP。

**根因（已实锤）**：**旧前端页面（部署前打开的浏览器 Tab）** 在点「导出 ZIP」时走的是旧代码——调后端 `export?format=zip`；新后端忽略 format 恒返回 Excel（200），旧前端又无条件弹「ZIP 导出成功」→ 现象完全吻合「成功 toast + 下载 Excel」。

**实机取证**：
- 测试环境强刷新（新前端）后点「导出 ZIP」→ 下载 `certificates_2026-08-14.zip`（2.4MB，PK 头合法，内部 10 张 PNG 均 `姓名_学号_编号.png`）✅
- 部署 chunk 静态分析确认测试环境跑的就是新前端（`CertificateExportPanel-Cofc__br.js` 含 `document.fonts.ready` + JSZip 流程）。

**加固（`2c64e45`）**：后端对 `format=zip` **显式抛 1400**「ZIP 导出已迁移至网页端，请刷新页面（Ctrl+F5）后重试」——避免残留旧页面继续静默下载错格式；新前端从不传 format，不受影响。

**给用户的答复**：硬刷新（Ctrl+F5）后 ZIP 导出即正常，代码本身没 bug。

### ZIP 导出部署后验证步骤

1. 强刷新证书导出页，筛出若干证书。
2. 点「导出 ZIP」→ 下载 `.zip`，内含 `姓名_学号_证书编号.png`。
3. 点「导出 Excel」→ 下载 `.xlsx`。
4. 旧页面（部署前开的 Tab，若有）点 ZIP → 现在会看到报错提示而不是静默下载 Excel（`2c64e45` 生效后）。

---

## 二、证书导出页「学院」筛选失效（commit `a5a81a3`）

### 现象

管理员证书导出页，选「学院=教育学院」→ 点查询，列表仍是全部学院（10 条），未过滤。

### 根因（API 直连逐参数实测定位）

`server/src/modules/certificate/certificate.service.ts` 的 `buildExportWhere()`：
处理了 `examId` → `where.examId`、`classId` → `where.student.classId`、`keyword` → `where.student.OR`，
**唯独 `collegeId` 只做了越权校验（validateExportScope），从没写入 where 条件** → 参数被静默丢弃。

实测（测试环境 direct API）：
| 参数 | 期望 | 实际 | 结论 |
|---|---|---|---|
| `collegeId`=教育学院 | 4 | 10（全量） | ❌ 被丢弃 |
| `examId`=0811 | 3 | 3 | ✅ |
| `classId`=23学前一班 | 3 | 3 | ✅ |
| `keyword`=杨烁 | 1 | 1 | ✅ |

### 修复

1. `buildExportWhere` 补 `where.exam.collegeId = params.collegeId`（与列表「学院」列取值同源：`cert.exam.college.name`，而非学员当前学院）。
2. **Excel 导出「学院」列取值源统一**：原来 `exportExcel` 取 `cert.student.college?.name`（学生所属学院），与列表显示的 `exam.college.name` 不一致；现统一为 `exam.college.name`，保证「筛 X 学院 → Excel 里学院列也是 X」。

### 验证（本地）

- 后端 build ✅、单测 37/37 ✅
- collegeId=智能科学与工程学院 → 2 条；=艺术学院 → 1 条；=教育学院（本地无）→ 0 条 ✅
- collegeId+keyword 组合 → 1 条 ✅
- Excel 导出抽查：collegeId 过滤后导出，学院列 = 智能科学与工程学院 ✅

### 测试环境部署后验证步骤

1. 证书导出页选「教育学院」→ 点查询 → 只见 4 条教育学院证书。
2. 选学院+考试交叉筛选 → 结果正确收窄。
3. 筛选 X 学院后点「导出 Excel」→ Excel 学院列与列表一致（不再出现他院数据）。

---

## 三、附：修 Bug 方法论（会话中给用户的整理，供后续会话遵守）

来源：`.agents/skills/` 下三份全局规范（systematic-debugging / verification-before-completion / test-driven-development）。

1. **先找根因再修**：稳定复现 → 查近期改动 → 追踪数据流到源头 → 单一假设最小验证；症状修复 = 失败；修 3+ 次没成 = 架构问题，停手讨论。
2. **证据先于断言**：宣称「修好/通过」前必须跑新鲜验证命令并读输出（测试 0 失败、build exit 0、原症状复现用例通过）。
3. **修 bug 也要先写失败测试**（TDD）：红→绿→重构；本会话学院筛选即用 API 直连 5 组断言当回归验证。

## 相关记录

- [[索引]]
- [[2026-08-14 手机端考试页底部按钮三等分与禁止缩放修复]]
- [[session-handoff-2026-08-14-输入框字数限制与折行自适应]]
- [[2026-08-14 教师班级关联与班级删除时进行中考试拦截]]