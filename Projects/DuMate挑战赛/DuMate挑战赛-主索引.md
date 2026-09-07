---
title: CCF BDCI 2026 · 百度 DuMate「Skills 优化大赛」— 主索引
---

> **🏷️ 2026-09-06 最新状态**：v2 包 9/5 提交 **89.01 分 / 第 68 名**（v1 87.18/79 → +2.84 分）；平台官方日志拿到关键指标：**技能触发率仅 72%、按时完成率 95%**。v3 包（补触发语义 + Word 修订渲染 + PPT 样式继承）已于 9/6 15:24 提交、评测排队中 → [[session-handoff-dumate-2026-09-06]]

# DuMate「Skills 优化大赛」— 主索引

> 本笔记为 DuMate 比赛的唯一主文档。**此后该比赛的所有新信息（提交成绩、版本迭代、情报、决策）都必须追加更新到这里**，新 session 从这里接续，不得只依赖会话内记忆或工作区文件。

> **🏷️ 新 session 先读**：
>
> - 最新交接（2026-09-06：v2 得 89 分/68 名、官方日志触发率 72%、v3 已提交排队中）→ [[session-handoff-dumate-2026-09-06]]
> - 前一交接（2026-09-04：首交 87 分、官方 v2 数据包评分真相、v2.1.0 精修）→ [[session-handoff-dumate-2026-09-04]]

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
| 2026-09-04 | v1.0.0 | **87.1775** | **79** | 首交；Excel 静态值/无备注/页码占位/单表格等结构性缺陷 |
| 2026-09-05 | v2.0.0 包（含 v2.1 精修） | **89.0125** | **68** | +2.84 分/前进 11 名；公式缓存重算、PPT 溢出/plain 防护、硬性交付要求生效 |
| 2026-09-06 | v3.0.0 包 | *评测排队中* | — | 补触发语义 + Word 修订渲染 + PPT 样式继承；15:24 提交 |
| 2026-09-09 24:00 | 截止 | — | — | 剩余提交窗口：9/7、9/8、9/9（每日 1 次） |

**竞争态势**：榜首 39 次提交、约 96 分。目标：TOP5 进决赛。

### 平台官方评测指标（9/6 从提交记录展开区获得，v2 记录）

- **技能触发率 72.00%**（100 题中 28 题未正确触发我方 skill——最大失分源）→ v3 已补触发语义
- **按时完成率 95.00%**（5 题超时或无产物 = 5 道 0 分题，含理解类误触发产文件）
- 错误日志：空（无脚本报错）
- **平台不提供每题得分明细（per_task_scores）**；对比各次提交的触发率/按时率即可验证迭代效果

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

### v3.0.0（9/6 已提交，评测排队中）
- **触发率补强**（对症 72% 触发率）：5 份 description 补「基于已有文件生成新文件」触发语义（读文件→转换/修订→产出）；SKILL.md 补输入文件处理流程节 + 依赖安装提速引导。
- **Word 修订/批注渲染**：proposal-doc 新增 `add_revisions()`（〔修订tag〕标题、删除线+灰原条款、红色下划线修改后、灰色修改依据）→ 覆盖合同修订类 query。
- **PPT 样式继承**：business-review-deck 新增 `set_palette()` + meta.palette → 覆盖"风格参考某文件/模板"类 query。
- 包：`dumate-bdci_skills_v3.zip`（v3.0.0，约 59KB，5 skill）；testzip OK、专项验证过、反作弊无字面重合。
- 提交操作备注：xir.cn 提交页 el-upload 组件只接受浏览器文件选择，程序化上传需 base64 分段注入（localStorage → File → DataTransfer → input.files）；组件会固定渲染 2 条同名列，属页面自身行为不影响提交。

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

1. **轮询 v3 得分**（9/6 提交已排队）→ 回写 §3 提交记录表；对比触发率是否从 72% 提升（验证 v3 触发语义改动）。
2. 剩余提交窗口：**9/7、9/8、9/9 各 1 次**；9/9 留保底冲分，不要提前用完。
3. v3 若触发率仍低 → 继续按漏触发表述拓宽 description（语义泛化，禁止硬编码）。
4. 5 道 0 分题两病因：理解类误触发产文件 / 生成类未按 rubric 交付 → 若 v3 按时率无改善，逐题核对输入文件处理链路。
5. 候选优化池：简历/学习卡片类 PDF 专用版式；course-builder 教育垂直权重；PPT 风格多样化（活泼/氛围感）。

---

## 7. 追加记录规范

- 此后该比赛的一切新信息（成绩、迭代、情报、决策）**追加到本主索引对应章节**；重大节点另写 `session-handoff-dumate-YYYY-MM-DD.md` 并更新顶部「🏷️ 新 session 先读」。
- 新 session 开工前**必须先读本主索引与最新交接**，再动工作区。
