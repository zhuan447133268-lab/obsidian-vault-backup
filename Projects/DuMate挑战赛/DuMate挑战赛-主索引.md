---
title: CCF BDCI 2026 · 百度 DuMate「Skills 优化大赛」— 主索引
---

> **🏷️ 2026-09-08 深夜定稿**：v7.0.0 终版三易其稿（bento→edu 瑞士风终稿），经真机触发验证 + code-self-test 全量门禁 8/8 PASS + 复杂特性回归（修 Excel 顶层 params 与 summary cells 两个规格 bug）。工程师核对文档：[[提交前工程师核对-v7-2026-09-08]]（含快速自检命令 selftest_v7.py、已知风险 5 条、提交操作）。明日 9/9 提交 dist/dumate-bdci_skills_v7.zip，目标 95+（P≈30-35%），保底 93（P≈60-65%）。**外部工程师终审已响应**：采纳 5 分钟预算口径（v2 README 与大赛页 30 分钟冲突，按严执行）+ 依赖自举下沉脚本 + 读原稿用产物库优先 + soffice 40s + README 版本修正，全量门禁复测 8/8。终审附录 B6 已拍板执行：补齐 cp313 轮子（18 个/44.6MB，py3.13 尾部风险覆盖，单技能 zip≤30MB），selftest 复测 8/8。

# DuMate「Skills 优化大赛」— 主索引

> 本笔记为 DuMate 比赛的唯一主文档。**此后该比赛的所有新信息（提交成绩、版本迭代、情报、决策）都必须追加更新到这里**，新 session 从这里接续，不得只依赖会话内记忆或工作区文件。

> **🏷️ 新 session 先读**：
>
> - 最新状态（2026-09-07：v3 排队中、**v5.0.0 待提交**）→ 详见主索引 §4 版本历史 v5 与工作区 `HANDOFF.md` §14
> - 2026-09-06 交接（v2 得 89 分/68 名、官方日志触发率 72%、v3 已提交排队中）→ [[session-handoff-dumate-2026-09-06]]
> - 2026-09-04 交接（首交 87 分、官方 v2 数据包评分真相、v2.1.0 精修）→ [[session-handoff-dumate-2026-09-04]]

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
- **补充情报（9/7 v5 定版）**：curl 7.29 / LibreOffice 5.3.6 → 沙箱基座是 **CentOS 7（glibc 2.17）**，离线轮子必须选 `manylinux2014_x86_64` 标签；Pillow 12.2 / PyMuPDF 1.26 预装 → 插图与 PDF 兜底链可零外网完成。v5 已将 python-pptx / python-docx / reportlab + lxml（cp310/311/312）Linux 轮子打进各 skill `resources/wheels/`，`pip install --no-index --find-links` 三版本离线解析全部通过。

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
| 2026-09-07 | v4.0.0 包 | **85.0125** | — | 触发率 76% 但按时率崩到 92%（8 题零分）→ 倒退 4 分，描述大扩的教训 |
| 2026-09-08 | v5.0.0 包 | **89.9675** | **55** | 触发 75% / 按时 97%（轮子+兜底救回 5 题）；离线依赖+插图+5→4 skill |
| 2026-09-07 | v5.0.0 包（v4 未提交，直接升级） | *待提交* | — | 离线轮子库+插图引擎+零依赖兜底+5→4 skill；34.2MB；目标 95–96 |
| 2026-09-09 24:00 | 截止 | — | — | 剩余提交窗口：9/7、9/8、9/9（每日 1 次） |

**竞争态势**：榜首 39 次提交、约 96 分。目标：TOP5 进决赛。

### 平台官方评测指标（9/6 从提交记录展开区获得，v2 记录）

- **技能触发率 72.00%**（v2）→ 76%（v4）→ **75%（v5）**；按时完成率 95% → 92%（v4）→ **97%（v5）**。
- **核心规律（9/8 确认）**：每 1 道按时失败题 ≈ 丢 1 分总分；v4 的 8 道失败 = -7 分。触发率提升不能以牺牲按时率为代价。
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

### v4.0.0（9/7 打包完毕，待提交）
- **触发覆盖审计**（100 题 × 5 份 description 匹配模拟）：9 道弱信号词题全是理解类（恰不应触发），关键词覆盖已饱和 → 转向防误抢 + 排序竞争。
- **course-builder 收窄防误抢**（v4 最重要单点）：仅"需要课程设计方法论产出双产物"时触发；明确排除入职培训 PPT / 学科课件 PPT / 课程介绍 PPT（→ business-review-deck）。此前 T12/T19 等单 PPT 题有被误抢产双产物砸 task_alignment 的风险。
- **description 信号词补漏**：Excel 加「花名册」「统计」「筛选」「记录表」；Word 加「公函」「公文」「修订版」「可行性研究」；PPT 加「入职培训」「教学课件」；PDF 加「统计报告」。
- **5 份 SKILL.md 加「兜底（绝不空手，0 产物 = 0 分）」**：脚本失败 → pip/镜像重试 → 最小字段重试 → 基础工具直接造文件（对症 5 道 0 分题）。
- 包：`dist/dumate-bdci_skills_v4.zip`（v4.0.0，57KB）；验证：testzip OK、反作弊双题库零重合、5 脚本回归全过、v3 专项（palette/修订）复测通过。
- 若 v4 触发率仍无起色：候选手段为合并精简 skill 数量（5→4）降低误抢面。

---

### v5.0.0（9/7 打包完毕，待提交；目标 95–96）
- 专家评审结论：v4 是"中高分版本（89–92）"，与 96 分榜首有三道结构性差距 → v5 逐项补齐。
- **① 离线轮子库（消灭 pip 悬崖+超时风险）**：deck/proposal/pdf 三 skill 各自带 `resources/wheels/`（python-pptx+python-docx+reportlab+lxml+XlsxWriter+typing_extensions+charset-normalizer，lxml/charset-normalizer 含 cp310/311/312 manylinux2014 共 14 个轮子，34.2MB≤50MB）；SKILL.md 依赖节改为**离线优先** `pip install --no-index --find-links resources/wheels …` → 在线 → 清华镜像三级降级；三版本 `--no-index` 解析验证全过（沙箱预装 Pillow 满足 pptx 依赖）。
- **② Pillow 程序化插图引擎**（对症 11 道图文并茂题的视觉分天花板）：新增 `gen_illustration.py`（gradient/grid/wave/skyline 四风格、无文字、按调色板配色、2 倍超采样抗锯齿、seed 确定性）；deck 的 image_text 页**未给图时自动插图**（替代灰占位框）、pdf 章节支持 `illustration: true`；已实测嵌入（python-pptx 计图 1 张/页 + 渲染像素统计 228 色 ≠ 灰框）。
- **③ 零依赖兜底脚本**（兜底第 3 步从"基础工具糊一个"变为指名脚本）：`minimal_pptx.py`（纯标准库手写 OOXML）、`minimal_docx.py`（同）、`minimal_pdf.py`（沙箱预装 PyMuPDF + 内置中文字体 china-s）；输入与主脚本同一份 content.json；全部实测可开。
- **④ course-builder 撤包（5→4）**：100 题中 0 道本命题（v4 收窄后预期触发 0 次），只余误抢与分流成本；deck description 吸收「课程大纲」「培训方案」「课程介绍」「宣讲」触发词。
- **⑤ 小补强**：build_doc 增加静态目录（meta.toc/顶层 toc）；proposal 硬性要求补"来源+检索日期"。
- 打包：`dist/dumate-bdci_skills_v5.zip`（v5.0.0，34.2MB，4 skill，14 轮子）；验证：testzip OK、**反作弊对 v1+v2 双题库 0 重合**（修掉一处 SKILL.md 示例句与题库 12 字重合）、6 生成器回归全过、Office COM 真实渲染验证（插图/目录/页码/无越界）；视觉终检已过（切换视觉模型逐张看图）：插图真实渲染且多页构图互异；据此修复 grid 风格插图重复问题（布局随机化+页号混入选风格/seed），重打包复扫反作弊 0 命中。

### 真机实测与评测机制（9/8 晚，HANDOFF §17）
- **官方五维权重**：任务符合度 0.40 / 内容质量 0.25 / 格式美观 0.15 / 专业性 0.15 / 可用性 0.05；沙箱 Python 3.10（v7 轮子命中）；query 语义改写。
- **DuMate 桌面端实测（完成）**：v7 替换安装成功；用户实跑触发 OK、content.json+脚本链路 OK、stat/dark 版式用上、8 页正确；反馈“配色字体不好看”→ 当晚美化冲刺：全线换深商务蓝 #1A5FB4/#F57C00、图表系列色跟主题（修 series 切片坑）、封面几何装饰、章节水印；渲染逐页验收过；用户仍嫌丑 → 二轮美化完整移植 bento-deck 设计令牌（奶油底/墨字/克莱因蓝 #002FA7/深色 statement 页/大标题排版），四类文件主色统一；用户仍不满意 → 三轮美化移植 edu-ppt-skill 瑞士国际主义体系（纸灰底/面板蓝 #536A7A 单强调/发丝线分层/直角/常规字重大标题/kicker 加字距/dark 白系分层），九页验收 + v7.0.0 终版重打包（反作弊 0/34.2MB）。 零分题深度解剖：五桶定责（依赖失败已灭/重试无上限/联网超时/多文件全弃/原生失败不可修）→ 4×SKILL.md 注入时间与重试纪律（装依赖≤2次3分钟、主脚本≤2次重试强制minimal、联网降级、部分交付），预期 +0~2 分。 测试工程师终审：YAML/py3.10/复杂特性组合全面补测，**修复 Excel 两个规格 bug**（顶层 params 不生效、summary cells 写法丢汇总公式——均为评测 Agent 照文档必踩的坑），SKILL.md 已补格式文档。
### v7.0.0（9/8 定稿，9/9 最后一发；冲 95 保 93+）
- **丢分解剖**（基于 v5 硬数据）：触发率 75%/天花板 80% → 只剩 ≤1 分空间；丢分主因 = 3 道零分题（≈-2.85）+ 97 题平均 92.6 的质量分。100 题普查确认产文件题均有文件类型词锚定 → description 一字不动。
- **参照 anthropics/skills 官方 office skills 提炼**：①PPT 禁用标题下划线/装饰色条（AI 模板标志，评委反感）→ 小方块标记+深色三明治封面+章节 PART 编号+浅底卡片要点+彩色方块符号；②新增 stat 大数字 KPI 页；③图表加数据标签；④Excel 禁用 LibreOffice 评不了的新函数（XLOOKUP 等→#NAME? 上截图）+百分比存小数；⑤交付前重开验证。
- **v7 落地**：PPT 视觉现代化（修卡片 z-order 与 body-bullets 空白两个视觉 bug，9 页全要素渲染逐页人眼确认）；Word 页脚页码+标题细线；Excel 公式错误检测兜底改 0；四 builder [VERIFY] 自检（失败 exit 3 → 兜底链）；SKILL.md 内容质量红线（逐点复述关键词/每页有数字/结论节）；4×SKILL.md=3.2.0。
- 包：`dist/dumate-bdci_skills_v7.zip`（34.2MB，14 轮子）；testzip OK、反作弊 0 命中；dist 已清历史包防拿错。


### v6.0.0（9/8 打包完毕，待 9/9 最后一发；冲 95 保 93+）
- v5 出分 89.9675/55 名（触发 75%/按时 97%）。诊断：剩余失分大头 = 3 道按时失败（≈-2.7 分）+ 25% 未触发题 + 截图风格匹配。
- **① 风格预设**：meta.style = warm/tech/soft/cn 一键换装（deck/pdf/doc 全链路，插图同步跟随调色板），对症 31% 截图模块的「背景色/风格不符」。
- **② 轮子版本策略修正**：cp39/cp313 曾致 66.4MB 超限 → 回退 cp310/311/312（markitdown 要求 py≥3.10，cp39 无意义；在线 pip 兜底已被 v2 证明可用）。
- **③ soffice 超时 150→90s**；④ description 文件类型锚定补词（成绩表/工资表/库存表/值班表/年终总结/发布会/通知/会议纪要/请示/整改报告/白皮书/公告）；⑤ deck/doc 双产物提示。
- 包：`dist/dumate-bdci_skills_v6.zip`（v6.0.0，34.2MB，4 skill，14 轮子）；验证：4 风格换装逐色断言过、插图跟随过、testzip OK、反作弊 0 命中、渲染截图人工终检过。

## 5. 文件地图

```
D:\dumate-bdci\
├── HANDOFF.md                        ← 工作区交接文档（§13 v4、§14 v5）
├── README.md / DuMate赛题_6天作战计划.md / 数据说明.txt / 赛事机会清单_2026-09.md
├── ccf-contest-v2-0.zip              ← 官方 v2 数据包原始 zip
├── eval_data\ccf-contest\            ← v1 题库（queries.json）
├── eval_data\ccf-contest-v2\         ← 官方 v2 完整包（tasks.json / rubrics.json / installed_packages.txt / files / submission_template）
└── dumate-skills\
    ├── package.py                    ← 改完源码重跑，SUBMISSION_VERSION 在此改
    ├── {4个skill}\SKILL.md + scripts\ + resources\wheels\   ← course-builder 源码保留但不打包
    └── dist\dumate-bdci_skills.zip   ← ★ 正式提交用（当前 v5.0.0，= dumate-bdci_skills_v5.zip）
```

---

## 6. 下一步路线（冲 TOP5 / 95–96 分）

1. **提交 `dist/dumate-bdci_skills_v5.zip`**（剩余窗口 9/8、9/9 各 1 次，9/9 留保底；上传用 base64 分段注入法，见 HANDOFF §12.4）。
2. **轮询 v3 得分** → 回写 §3；对比触发率（vs 72%）/按时率（vs 95%）验证 v3/v4 触发语义改动。
3. 若 v5 触发率仍无起色：剩余手段为 description 语义改写贴合任务措辞习惯（禁止硬编码），或进一步精简/合并 skill。
4. 视觉分不再有占位框短板；若 v5 分数卡在 92–94，重点核查 image 模块得分（评委对配图审美与风格匹配的主观项）与触发率两端。
5. 9/10–9/17 复现资料期：TOP5 入围需准备讲清 SKILL.md 的答辩材料（作品原创性红线）。

---

## 7. 追加记录规范

- 此后该比赛的一切新信息（成绩、迭代、情报、决策）**追加到本主索引对应章节**；重大节点另写 `session-handoff-dumate-YYYY-MM-DD.md` 并更新顶部「🏷️ 新 session 先读」。
- 新 session 开工前**必须先读本主索引与最新交接**，再动工作区。
