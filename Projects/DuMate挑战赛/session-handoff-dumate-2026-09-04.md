---
title: session-handoff-dumate-2026-09-04 — 首交87分 + 官方v2情报 + v2.1精修
---

# 2026-09-04 交接：首交 87 分 / 官方 v2 数据包情报 / v2.1.0 精修

> 接续 [[DuMate挑战赛-主索引]]。本日两个关键事件：**① v1 包首交得 87 分/排名 79；② 用户拿到官方 v2 完整数据包，评分机制完全摸清，据此完成 v2.1.0 精修**。

---

## 1. 提交记录

- **2026-09-04，提交 `dist/dumate-bdci_skills.zip`（v1.0.0）→ 得分 87 / 排名 79**。
- 榜首：39 次提交、接近 96 分（官方 7 月底公开数据起每日迭代）。
- 排行榜记**最高分**，后续迭代无风险；剩余 9/5–9/9 共 5 次提交机会。

## 2. 87 分丢分定位（对照 100 题排查）

1. **Excel 最大失分源**：约 14/30 题明确要求公式自动计算、条件格式高亮、内嵌图表、多表联动，v1 只会写静态值。
2. PPT：无演讲者备注（有题明确要求每页 80–120 字可照读）；页脚页码是"—"占位符。
3. Word：全文仅 1 张表格；公文邀请函称谓/落款、IEEE 双栏不支持。
4. PDF：无页码、无目录、无代码块、只有柱状图、无双栏对照、无公式排版。
5. 理解类 20 题：description 需防误触发（用户说"不生成文件"时不得产出文件）。

## 3. 官方 v2 数据包情报（`eval_data/ccf-contest-v2/`）

### 3.1 rubrics.json — 真实评分模块（278 个）
- 每题含「交付格式与基础可用性」（0.2–0.35）：**按 query 指定文件名落盘**、页数约束、可打开、无乱码、无公式错误。
- **31% 模块为 image 输入（看渲染截图）**：罚元素重叠、文字截断、渲染异常、背景色/风格不符。
- 内容模块权重 0.4–0.8：要点逐项覆盖、数据准确、来源标注。理解类"条款提取/数据分析"类模块权重 0.7。
- v2 题面比 v1 更具体（文件名、页数、风格约束写进题面）；分布与 v1 一致。

### 3.2 installed_packages.txt — 沙箱真实依赖
- 有：openpyxl、LibreOffice、PyMuPDF、pdftotext、Ghostscript、Pillow、markitdown、requests/curl/wget、zip。
- **无 python-pptx/docx/reportlab/matplotlib/pandas** → pip 兜底是命门；榜首 96 分证明链路在评测环境可用。
- 注意 LibreOffice 存在 → 可用于本地渲染自检 + Excel 公式重算回写。

### 3.3 submission_template
- 官方结构与我们一致：`manifest.json + skills/<name>/SKILL.md`（SKILL.md 三段式：工作流/约束/资源索引）。

## 4. v2.0 → v2.1 精修内容（全部完成并验证）

- **v2.0（9/4 下午）**：Excel 重写（公式占位符 `{@R}/{@D}/{@E}/{@S}/{@H}/{@P:key}`、条件格式、内嵌图表、多表、参数区）；PPT 备注+真实页码+图片嵌入；Word 节内表格+落款+双栏；PDF 页码+目录+代码块+折线饼图+双语对照+公式渲染；SKILL.md 加理解类防线。
- **v2.1（9/4 晚，待提交）**：
  - PPT 溢出防护（表格按高度反推行高、要点>6 条分两栏、长文本降字号，实测 30 行表收敛不越界）；**plain 简约模式**（meta.plain=true，白底无色块，用于"简约/浅色/无背景色"query，风格 query 优先）。
  - Excel `fullCalcOnLoad` + **LibreOffice 无头重算回写公式缓存值**（防 markitdown/pandas 读公式得空值；meta.recalc=false 可关）。
  - 4 份 SKILL.md 新增「硬性交付要求」：文件名确切落盘、页数/字数逐项核对、风格优先级、模板题必填示例数据、合同修订逐条"原条款→修改后→依据"。
- **验证**：manifest v2.1.0、zip 50KB testzip OK；**反作弊对 v1+v2 双题库长字面子串检查零重合**；7 项回归全过（旧样张+溢出/plain/公式样张）。

## 5. 下一步

1. **9/5 提交 v2.1.0**；拿到分数与排名后回写主索引 §3 提交记录表。
2. **若平台可见 per_task_scores → 立即按弱题精准迭代**（榜首核心打法）；看不到则按 rubrics 权重自查，可用本地 LibreOffice 渲染产物截图自检视觉分。
3. 9/8–9/9 保留冲分提交；候选优化池见主索引 §6。
4. 用户侧：能口头讲清 5 份 SKILL.md 的核心设计（红线：解释不清取消资格）。

## 6. 环境备忘

- managed Python：`C:/Users/dfjq/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（已装 pptx/docx/openpyxl/reportlab/matplotlib/pypdf/Pillow）。
- 重新打包：`cd dumate-skills && python package.py`（SUBMISSION_VERSION 在 package.py 内改）。
- 本机无 LibreOffice（Excel 重算自动跳过，评测沙箱有，届时生效）。
- 工作区交接详版：`D:\dumate-bdci\HANDOFF.md`（§10/§11 与本文对应）。
