---
title: CCF BDCI 2026 · 百度 DuMate「Skills 优化大赛」— 主索引
---

> **🏷️ 2026-09-04 最新状态**：首交 v1 包 **87 分 / 排名 79**；已完成 v2.1.0 精修版待 9/5 提交。官方 v2 数据包情报（真实评分模块 + 沙箱依赖）已吃透 → [[session-handoff-dumate-2026-09-04]]

# DuMate「Skills 优化大赛」— 主索引

> 本笔记为 DuMate 比赛的唯一主文档。**此后该比赛的所有新信息（提交成绩、版本迭代、情报、决策）都必须追加更新到这里**，新 session 从这里接续，不得只依赖会话内记忆或工作区文件。

> **🏷️ 新 session 先读**：
>
> - 最新交接（2026-09-04：首交 87 分、官方 v2 数据包评分真相、v2.1.0 精修、冲前 5 路线）→ [[session-handoff-dumate-2026-09-04]]

---

## 1. 项目基本信息

| 项 | 内容 |
| --- | --- |
| 比赛 | CCF BDCI 2026 · 百度 DuMate「Skills 优化大赛」（百度出题） |
| 赛题一句话 | 为百度办公智能体 DuMate 设计 Office 创作类 Skill（SKILL.md + Python 脚本），评测环境自动跑 100 道真实办公任务，LLM-as-Judge（看渲染截图+读文本）+ 规则脚本打分 |
| 参赛身份 | 用户本人，**单人参赛不组队**（已拍板，9/6 12:00 锁队无需动作） |
| 工作区 | `D:\dumate-bdci\`（与 WR-001 完全隔离） |
| 提交平台 | BDCI 竞赛平台（xir.cn），该赛题下上传 zip；**每日每队 ≤1 次，记最高分** |
| 评测数据 | `eval_data/ccf-contest/`（v1 题库）+ `eval_data/ccf-contest-v2/`（官方 v2 完整包：tasks.json / rubrics.json / installed_packages.txt / files / 官方提交模板） |

### 关键时间节点（北京时间）

| 节点 | 时间 | 状态 |
| --- | --- | --- |
| 组队锁队 | 2026/09/06 12:00 | 单人参赛，无需动作 |
| 初赛提交截止 | **2026/09/09 24:00** | 剩 9/5–9/9 共 5 次提交 |
| 复现资料 + TOP5 入围 | 09/10–09/17 | — |
| 线上决赛 / 颁奖 | 9 月下旬 / 10 月下旬 | — |

---

## 2. 评分机制（来自官方 v2 数据包，已核实）

### 2.1 真实评分结构（rubrics.json，100 题共 278 个评分模块）

- 每题 2 个模块：
  - **「交付格式与基础可用性」**（约 56 题，权重 0.2–0.35）：文件格式正确、**按 query 指定文件名落盘**、页数约束、可打开、无乱码、无公式错误、无截断/断页。
  - **内容模块或视觉模块**（其余权重 0.4–0.8 / 0.15–0.5）。
- **image 输入模块 85/278 ≈ 31%**：评委看**渲染截图**打分，明确罚：元素重叠、文字截断、渲染异常、背景色/风格不符。
- text 内容模块：要点逐项覆盖、数据准确、来源标注、逻辑自洽。
- 理解类 20 题（只要文字回答不产文件）：条款提取与解读、数据统计分析类模块权重高达 0.7；**若误产出文件会重扣**。
- 题目分布：PPT 30 / Excel 30 / Word 20 / PDF 20；生成类 70 / 理解类 20 / 理解生成类 10；30 题带输入文件。

### 2.2 评测沙箱真实依赖（installed_packages.txt）

- **有**：openpyxl 3.1.5、LibreOffice 5.3、PyMuPDF、pdftotext、Ghostscript、Pillow、markitdown、requests/curl/wget、zip/unzip。
- **没有**：python-pptx / python-docx / reportlab / matplotlib / pandas → **SKILL.md 内的 pip install 兜底是命门，不可删**。榜首 96 分证明生成链路在评测环境可用。

### 2.3 硬规则（红线）

- 提交包 `<队名>_skills.zip`：manifest.json（必填）+ skills/ 包裹，≤50MB，Skill ≤10 个；单题执行预算 30 分钟，超时/无产物/损坏 = 0 分。
- 禁止硬编码 query 字面片段 / task_id（评测时语义改写 + 静态检查）；禁第三方 Office/LLM API；禁改官方 Skill。
- 作品须原创、拒收完全 AI 生成；**用户必须能亲自讲清 SKILL.md 内容**，解释不清取消资格。
- 脚本仅可用 Python 标准库 + 官方白名单（python-docx/pptx/openpyxl/pypdf/reportlab/matplotlib/pandas 等）。

---

## 3. 当前状态与提交记录

| 日期 | 版本 | 得分 | 排名 | 备注 |
| --- | --- | --- | --- | --- |
| 2026-09-04 | v1.0.0 | **87** | **79** | 首交；Excel 静态值/无备注/页码占位/单表格等结构性缺陷 |
| 2026-09-05（计划） | v2.1.0 | 待提交 | — | 含 v2 结构升级 + v2.1 精修 |

**竞争态势**：榜首 39 次提交、约 96 分（7 月底数据公开起每日迭代）。目标：TOP5 进决赛。剩余提交：9/5–9/9 共 5 次。

---

## 4. Skill 包版本历史

### v1.0.0（9/4 首交，87 分）
- 5 个 skill：business-review-deck（PPT）/ data-report-sheet（Excel）/ proposal-doc（Word）/ pdf-doc（PDF）/ course-builder（培训材料双产物）。
- 缺陷：Excel 纯静态值（30 题约 14 题要公式/条件格式/图表/多表）；PPT 无演讲备注、页码是"—"；Word 全文仅 1 表格、无公文落款；PDF 无页码/目录/代码块。

### v2.0.0（9/4 下午，未单独提交）
- Excel 重写：真公式 + 占位符（`{@R}/{@D}/{@E}/{@S}/{@H}/{@P:key}`）、条件格式、内嵌折线/柱/饼图、多工作表、参数区、数字格式。
- PPT：演讲备注、真实页码、图片嵌入。Word：节内多表格、kv 条款、对齐段落、落款、双栏。PDF：页码、目录（multiBuild 真实页码）、代码块、折线/饼图、双语对照、公式渲染（matplotlib→矢量图）。
- 4 份 SKILL.md 加「理解类不产文件」防线 + 来源标注。

### v2.1.0（9/4 晚，待 9/5 提交）
- PPT 视觉防护：表格/要点/标题溢出自动收敛（截图分保护）；**plain 简约模式**（meta.plain=true，用于"浅色简约/无背景色"类 query）。
- Excel：`fullCalcOnLoad` + **LibreOffice 无头重算回写公式缓存值**（防 markitdown/pandas 读公式得空值；meta.recalc=false 可关）。
- 4 份 SKILL.md 新增「硬性交付要求」：文件名确切落盘、页数/字数逐项核对、风格 query 优先、模板题必填示例数据、合同修订逐条"原条款→修改后→依据"。
- 验证：双题库反作弊零重合、7 项回归全过、zip 50KB 结构合规。

---

## 5. 文件地图

```
D:\dumate-bdci\
├── HANDOFF.md                        ← 工作区交接文档（§10 提交记录/v2、§11 v2情报/v2.1）
├── README.md / DuMate赛题_6天作战计划.md / 数据说明.txt / 赛事机会清单_2026-09.md
├── ccf-contest-v2-0.zip              ← 官方 v2 数据包原始 zip
├── eval_data\ccf-contest\            ← v1 题库（queries.json）
├── eval_data\ccf-contest-v2\         ← 官方 v2 完整包（tasks.json / rubrics.json / installed_packages.txt / files / submission_template）
└── dumate-skills\
    ├── package.py                    ← 改完源码重跑，SUBMISSION_VERSION 在此改
    ├── {5个skill}\SKILL.md + scripts\ + resources\
    └── dist\dumate-bdci_skills.zip   ← ★ 正式提交用（当前 v2.1.0）
```

---

## 6. 下一步路线（冲 TOP5）

1. **9/5 提交 v2.1.0**（`dist/dumate-bdci_skills.zip`）。
2. **拿每题得分明细（per_task_scores）**——若平台可见立即发 AI 按弱题精准迭代（榜首拉开差距的核心手段）。
3. 看不到明细则按 rubrics 权重自查：Excel 公文链路 → PPT 视觉截图（可用 LibreOffice 本地渲染自检）→ 文件名/页数合规。
4. 9/8–9/9 保留冲分提交；每版源码靠 package.py 可复现、本地留档。
5. 候选优化池：简历/学习卡片类 PDF 专用版式；course-builder 教育垂直权重；PPT 风格多样化（活泼/氛围感）。

---

## 7. 追加记录规范

- 此后该比赛的一切新信息（成绩、迭代、情报、决策）**追加到本主索引对应章节**；重大节点另写 `session-handoff-dumate-YYYY-MM-DD.md` 并更新顶部「🏷️ 新 session 先读」。
- 新 session 开工前**必须先读本主索引与最新交接**，再动工作区。
