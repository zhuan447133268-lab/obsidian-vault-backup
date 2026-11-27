---
date: 2026-11-26
source: haydenschmitty/floorplan (GitHub, MIT, v0.11.0)
type: 技能卡
tags: [AI工具, 代码可视化, 架构地图, 项目交接, 健康检查, floorplan]
---

# floorplan：把代码库变成可交互的架构地图

## 一句话定义

**不是流程图 skill，是「代码库架构地图」skill。** 扫描一个项目的代码，标出每个模块/文件/接口，用大白话命名，画出依赖和真实调用关系，产出一个自包含、离线可开的 `floorplan/index.html`。附带健康检查（明文密钥、无鉴权接口、超大文件、没人用的文件）。

> 仓库：`https://github.com/haydenschmitty/floorplan`（MIT，零 npm 依赖，Node 18+）
> 本次脚本暂存位置：`C:/Users/dfjq/AppData/Local/Temp/floorplan-inspect/skills/floorplan`（临时目录，重启可能清掉；要用先重新 clone）
> 本机跑通版本：2026-11-24，产出实验室准入考试项目地图，219/219 文件 + 80/80 接口描述齐全

## 它适合 / 不适合什么

- ✅ 适合：项目汇报展示系统全貌、新人 onboarding、接手陌生大项目、交接盘点、找跨模块的调用链。
- ✅ 适合：AI 生成的大项目——"它跑起来了但我不知道怎么拼起来的"，这个地图就是补这块的。
- ✅ 附带价值：Health 检查真能挖出风险（明文密码、无鉴权接口、超大文件），比手工翻快。
- ❌ **不适合：生成流程图/时序图/技术路线图。** 那是 [[mermaid-diagram__skillhub]]、[[diagram-design 科研技术图示技能]]、[[nsfc-roadmap NSFC 纵向技术路线图]] 的活。
- ❌ 不适合：找功能 bug。它做的是静态结构分析 + 模式匹配，不跑测试、不查逻辑错误。
- ⚠️ 健康检查是 "a check, not an audit"，不是安全审计；误报常见（如 Vue 动态路由加载的文件会被误判"没人用"）。

## 关键判断：WorkBuddy 里怎么定位它

**结论：它是代码库架构地图，不是流程图。** 汇报场景它展示系统真实结构，比手画的框图硬；但要做业务流程/汇报导图，走已有的 mermaid-diagram 或 diagram-design，别拿它凑。

**别"借鉴重造"。** floorplan 本身就是一个 SKILL.md + 脚本包（54 文件、3MB），核心价值在扫描器（十几种语言、跨仓库请求-路由匹配）和 ELK 布局引擎。要复用，正确动作是**直接搬脚本改路径**，不是重新设计。手动跑通的流程见下。

## 在 WorkBuddy 里怎么用（已跑通的完整流程）

脚本可以脱离 Claude Code / Codex，直接用 node 调用。`FLOORPLAN_AGENT=none` 支持无 agent session 场景。

```
# 0. 拿脚本（临时目录被清就重跑）
git clone --depth 1 https://github.com/haydenschmitty/floorplan <临时目录>
S=<临时目录>/skills/floorplan          # 下文用 S 代指脚本目录
R=<目标项目根目录>                      # 如 D:/01-项目/2026准入题库-main

# 1. 扫描：只读，写 floorplan/.cache/scan.json，打印摘要（repos/代码树/入口/调用匹配/外部服务）
node $S/scripts/scan.mjs $R

# 2. 读规范：references/schema.md（architecture.json 格式）、choosing-boundaries.md（切分原则）
#    然后读项目 README、入口文件、docker-compose，决定 3–9 个顶层节点

# 3. 写 floorplan/architecture.json
#    节点 paths 用 glob 覆盖 >90% 文件；顶层 3–9 个，大模块下 3–12 个子节点
#    外部依赖用 kind=external 节点（packages/hosts 挂上去自动连线）
#    写 1–3 条 flows + 3–8 站 tour（白话）

# 4. 构建校验，看到 assignment 未分配 <10%、无 warning 为止
node $S/scripts/build.mjs $R

# 5. 生成描述工作表（每个模块一个 worksheet + 一个待填 JSON 骨架）
node $S/scripts/describe.mjs $R

# 6. 填 floorplan/descriptions/<key>.json 的 name + description
#    >150 文件时按模块分组交并行子代理，每组只改自己的 JSON，key 一个不能动
#    受众 everyone：中文白话，动词开头，说代码现在真做的事，占位就写"目前只…"，禁写密钥值
#    规范见 $S/references/writing-descriptions.md（重点 "Plain language" / "Say what it does today"）

# 7. 标最近改动：node $S/scripts/recent.mjs $R → 写 floorplan/recent-work.json → 再 build
# 8. 展示：直接 present_files 打开 floorplan/index.html
```

**验收标准（本次实测）**：`ASSIGNMENT 219 files, 1 unassigned (0.5%)` / `DESCRIPTIONS files 219/219 · routes 80/80` / `LINKS 356` / 构建无 warning。

**注意**：
- `floorplan/` 自带 `.gitignore`，不碰项目 tracked 文件。
- `graph.json` 和 `index.html` 是生成的，别手改。
- 只匹配 `code` 类文件。docs/config/asset 要上图，在 `architecture.json` 加 `"include": ["code", "docs", "config"]`。
- 多副本 git 项目先核分支再动手——同一 remote 可能有多个 worktree，选错白干。

## WorkBuddy 里的硬限制：Ask bar 问答废了

地图里的 Ask bar 问答依赖 `claude -p` 或 `codex exec` 子进程读真实代码。WorkBuddy 没有对等的无头 CLI，所以：

- ✅ 能用的：静态地图、点选追踪、Screens、Flows、Health、导出单 HTML、最近改动高亮。
- ❌ 不能用的：Ask bar 直接问答、地图内 "Fix with Claude/Codex"。
- 替代：要问就在对话里问，把地图当索引用，效果一样。

真要移植成常驻 Skill（用户 2026-11-24 评估后选"先不做"）：把 54 个文件搬进 skill 目录 → 改 SKILL.md 里 `${CLAUDE_SKILL_DIR}` 路径变量 → 砍掉 Ask bar 相关段 → 跑一次验收。成本低，但先确认用得够频繁再做。

## 实战记录：实验室准入考试项目（2026-11-24）

项目：`D:/01-项目/2026准入题库-main`（分支 `feat/cas-auth`，同 remote 另有一份 `2026准入题库` 是 `feat/exam-platform`）。
产出：`D:/01-项目/2026准入题库-main/floorplan/index.html`（2.3MB 单文件）。

**架构**：Vue 3 前端（管理端电脑 + 学生手机端）→ NestJS 主服务器（登录/师生/组织/题库/考试/学生答题/证书/统计）→ MySQL + Redis；登录接学校 CAS 统一身份认证。

**地图顺带挖出的隐患（不是功能 bug）**：

| 类别 | 发现 |
|---|---|
| Health 高危 3 项 | 明文密码写在 `server/verify_users_enhance.js`、`server/verify_change_password.js`、`server/src/modules/users/users.service.ts`（地图只标文件+行号，未读取值） |
| 超大文件 4 个 | 统计 / 学生答题 / 账号维护 / 考试服务，均 1500 行以上，AI 改动易出错 |
| "没人用" 提示 7 个 | 3 个页面请求封装 + 2 个学院管理页面 + 2 个学校管理页面——Vue 动态路由常误报，需人工核实 |
| 进行中改动 14 卡 | CAS 统一登录接入（未提交）+ 师生账号编辑删除（11-17 已提交） |

**经验**：健康检查比地图本身值钱。但区分清楚——挖出的是安全隐患 + 维护负担 + 待核实提示，不是功能 bug；找 bug 还得靠测试和人工走查。

## 相关

- [[Skill库 MOC]]
- [[mermaid-diagram__skillhub 流程图技能]] — 流程/时序/用户旅程，跟本卡互补
- [[diagram-design 科研技术图示技能]] — 科研图示 39 种，自包含 HTML+SVG
- [[保存对话并提取可沉淀内容]] — 本卡按四层知识库规则沉淀
