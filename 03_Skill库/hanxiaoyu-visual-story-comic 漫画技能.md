---
date: 2026-10-15
source: 用户提供的 GitHub 仓库 https://github.com/rolfie-han/hanxiaoyu-visual-story-comic
url: https://github.com/rolfie-han/hanxiaoyu-visual-story-comic
type: 技能卡
tags: [AI工具, 漫画, 条漫, 知识漫画, 多页一致性, 图字分离, hanxiaoyu, MIT, ImageGen, 卡通]
---

# hanxiaoyu-visual-story-comic：多页连续漫画（卡通/条漫/知识漫画）技能

## 一句话定义

把一段故事 / 脚本 / 文章做成**能顺着读下去的连续漫画**，而不是生成几张彼此无关的漂亮图。核心是"先锁一致性 → 逐页生成 → 逐页校验"的多页工程层。

## 它是什么 / 能力清单

- **4 种输出模式**：`plan-only`（拆解/页数/节奏）、`prompt-only`（角色锁定+逐页提示词+叠字方案）、`generate`（先锁参考资产再逐页出图）、`delivery-pack`（计划+提示词+队列+文件清单+质检报告）。
- **三级参考图锁定**（最关键的设计）：
  - `text-lock`：只有文字描述，一致性有限，必须明说
  - `reference-lock`：后续页带入已采用参考图，一致性"中"
  - `production-lock`：参考图 + 逐页交接 + 质检 + 返修全跑，一致性"高"
  - 不许把纯文字结果描述成高一致性交付；无生图工具时标 `blocked-no-image-tool`，**禁止假装出图**。
- **8 类漂移检查**（逐页看真实图，不是查提示词）：`identity_drift` / `wardrobe_drift` / `prop_drift` / `scene_drift` / `story_order_drift` / `orientation_drift` / `text_artifact` / `extra_subject`。
- **5 种版式**：four-panel / serialized-pages / webtoon-strip / educational-comic / one-page-teaser。
- **视觉节拍八分类**、**页数由事件覆盖推导**（不套模板）、**数量锁定五步法**（图像模型数数必崩）、**文字预算**（标题≤14 / 旁白≤18 / 气泡≤16，一律后期叠加）、**返修纪律**（只修失败页，连续两次失败必须换策略，不许重复同一提示词）。
- 上游自述：纯 Markdown + 相对路径，不绑任何模型/CLI/图片服务；验证过 8 题材 / 8 张视觉设定 / 38 张连续页。附带 `PORTABLE-PROMPT.md`（给不支持 Skill 的工具直接粘贴的通用提示词，跨平台分发友好）。

## 技术栈与协议

- 形态：WorkBuddy Skill（纯 Markdown + 相对路径引用 references/ 下的规划/连续性/契约文档）。
- 作者：Hanxiaoyu（韩小羽 / Rolfie）。版本：**1.1.1**。协议：**MIT**（可商用、可改、须保留 LICENSE 与作者署名）。
- 本机安装位置：`C:/Users/dfjq/.workbuddy/skills/hanxiaoyu-visual-story-comic`（用户级，`git clone --depth 1`，62 文件，可随时删）。
- 生图依赖外部工具（本机走 ImageGen）；无生图工具时走 `prompt-only` 不出图。

## ⚠️ 适用 / 不适用（本机实测校准）

> 用户原话："这个只适合做卡通漫画，有优势，你今天做的别的，都不太满意。"

- **适用（真优势）**：卡通 / 条漫 / 知识漫画 / 可爱风·故事风叙事图。参考图锁一致性 + 逐页漂移检查 + 字幕条，这套在 cartoon 里能打。
- **不适用（已被本机证伪）**：高校**严肃**场景的视觉化——信息化纪念册条漫、算法/理论教学漫画。扁平插画那股卡通感一贴高校内容就违和，产出不被认可。
- **不要 oversell**：别把一个工具吹到它撑不住的场景（如"高校教师培训全场景有用"）。它的命门就是多页卡通叙事。

## 与本地技能分工（定位）

- **本 Skill（hanxiaoyu）**：多页规划 + 跨页一致性 + 返修队列。弱在单页画质与中文落地。
- **`linmumu` 绘本对**（`linmumu-huiben-planner` / `-director` / `-assets`，本机已有）：单页崩坏控制 + 中文叠字（`text_overlay.py`，华文行楷）。
- **结论**：互补，串联才出"可交付漫画"——hanxiaoyu 出规划与一致性，linmumu 补单页画质与中文叠字；单独一个都是半成品。
- 已删除的 `gc-minimal-hand-drawn-comic-director` / `gc-story-split-and-prompt-planner` 是 deprecated 上游汉化版，内容已并入 linmumu 对，已从技能目录移出至 `~/.workbuddy/_skill_backup/`。

## 怎么跑通 demo（本机实测）

1. **调用**：`Skill: hanxiaoyu-visual-story-comic`，参数如「出一个连续漫画 demo」。
2. **生成参考设定图**：先出角色/道具/场景/配色锚点图（reference sheet），作为后续一致性基准。
3. **逐页生成（关键）**：把参考图作为 ImageGen 的 `image1` 传入做 image-to-image（`input_fidelity=high`），逐页锁定。
4. **逐页漂移检查**：对照 8 类清单看真实生成的图，只返修失败页。

## 关键事实 / 避坑（本机实跑验证）

- **多页必须串行生成**：ImageGen 并行调用会**同秒撞名、互相覆盖**（工具不按各调用的 `output_dir` 落盘），曾导致 P1 被 P3 覆盖丢失。规则：每页单独一轮调用，或生成后立即手动改名。分目录隔离救不了。
- **ImageGen 无 16:9 档位**：最大横版 1536×1024 = 3:2，不是严格 16:9。
- **中文必须图字分离**：画面阶段保持无字，中文旁白/对白后期叠加；否则满屏错字鬼字（`text_artifact`）。
- **裸叠字在深浅分割背景必翻车**（字压深裤/跨白墙深屏半隐）→ 解法是用**半透明字幕条**（白条 + 深蓝灰字），任何背景可读、多页风格统一。本机曾写通用 `caption_bar.py` 实现该方案，但随 demo 目录删除，需要时可按此法重建。
- **AI 生图里的图表/数字是装饰性的**，不能当真实数据引用（如纪念册大屏柱状图）。
- **reference-lock 实测有效**：卡通角色（红雨衣/黄雨靴、或黑框眼镜/青色机器人）跨页零漂移；但仍会漂的是道具形态、空间方位等细节——印证"一致性是查出来的，不是许出来的"。

## 后续方向（未做 / 可挖）

1. 把它定位为"卡通/条漫/知识漫画"专用管线，配一套可复用角色模板。
2. `caption_bar.py` 字幕条工具独立沉淀（不依赖 demo 目录），供所有漫画交付复用。
3. 与 linmumu 绘本对做成"一键串联"工作流。

## 项目地址 & 安装位置

- 仓库：`https://github.com/rolfie-han/hanxiaoyu-visual-story-comic`（MIT, v1.1.1）
- 本机：`C:/Users/dfjq/.workbuddy/skills/hanxiaoyu-visual-story-comic`
- 上游文章：韩小羽《我开源了一个漫画 Skill》（微信公众号，2026-08-26）

## 相关链接

- [[多页AI漫画一致性工程纪律]]（02_概念库：漂移8项/图字分离/不假装出图方法论，与卡通无关，独立可用）
- [[四层闭环结构]]（01_原料库 / 02_概念库 / 03_Skill库 / 04_输出库）
- [[Skill库 MOC]]
