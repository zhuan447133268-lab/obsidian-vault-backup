---
title: 2026 飞猪 AI 旅行创新大赛 — 主索引
---

> **🏷️ 当前状态卡（2026-10-08 15:5x，最后更新）**：
>
> - **⏸️ 卡点 = 百炼账户欠费**：Managed Agent（`agent_01M4CVTF231ZZF0GHKJVW9XHQP`）报错 `Access to agent denied due to account arrears or risk control` → 百炼沙箱链路暂不可用。**用户暂未充值，正在评估是否值得投入。**
> - **✅ 已完成的（不依赖百炼的部分）**：
>   - 本机 `flyai-cli` 安装成功（npm global，v1.0.16），体验模式可用（本机 IP 实测三亚/北京搜索正常）
>   - 工具封装层 `flyai_tools.py`（6 命令封装 + 娃友好评分引擎 v1）写入 `C:\Users\dfjq\Doubao\chats\2026-10-08\new-chat-1\feizhu-trip-agent\`，本地验证通过
>   - 飞猪正式 API Key **已申请**（flyai.open.fliggy.com 控制台）；⚠️ 该 Key 曾在截图暴露，建议配置完成后轮换
>   - 百炼 Agent 已创建成功（名称：亲子遛娃旅行管家，模型未确认）
>   - 沙箱侧：`npm install -g @fly-ai/flyai-cli` ✅ / `flyai_tools.py` 下载 ✅ / 调用时被飞猪 **429 试用额度用完**（沙箱出口 IP 的体验额度耗尽，非代码问题）
> - **⏳ 待办**：
>   1. **报名**（alidocs 参赛指南「提交参赛作品」，需身份证/手机号/邮箱，仅用户可做）——**未完成**
>   2. 充值百炼 或 领取免费额度（新用户 FAQ 提过"免费千万 Tokens"，待核实是否可领）→ 恢复沙箱
>   3. 沙箱配置 `flyai config set FLYAI_API_KEY <key>` → 重测 → 接 Agent
>   4. 行程生成引擎（作息排程 + 行程单输出）——本地开发，不依赖百炼
>   5. 提交材料（GitHub issue 模板）
>
> **维护纪律**：新 session 接手前必须先读本文件；新进展追加到对应章节并同步重写本状态卡。

# 2026 飞猪 AI 旅行创新大赛 — 主索引

> 本笔记为该大赛唯一主文档。所有关键信息、进展、决策、卡点记录于此。

## 1. 比赛关键信息

| 项 | 内容 |
| --- | --- |
| 赛事 | 2026 飞猪 AI 旅行创新大赛（Agent Hackathon），飞猪 × 阿里云百炼 联合主办 |
| 赛题一句话 | 基于飞猪 flyai Skill 能力 + 阿里云百炼（CLI / OpenWork / Agent Skills），构建能真正跑通的旅行 AI 应用 |
| 官网 | https://opc.aliyun.com/feizhu |
| 参赛指南 | https://alidocs.dingtalk.com/i/nodes/QG53mjyd800agdlKHebwk4Zj86zbX04v |
| **作品提交截止** | **2026-10-25** |
| 赛程 | 09.22-10.25 线上比赛&提交 → 10.26-11.02 初评 → 11.03-11.06 终评 → 11.07-11.15 奖项公布 |
| 命题 | 预设：酒店Staycation / 目的地探索 / AI私人讲解 / 入境游助手；开放命题（不设限） |
| 评审维度 | 创新性、可行性、市场前景（基于真实旅行场景） |
| 奖励 | Token 补贴、专家带练、商业生态资源支持；优秀作品进联合 POC |
| 身份 | 个人参赛，主要提交人 GitHub ID = `zhuan447133268-lab`（用户确认本人账号） |
| 报名状态 | **未完成**（alidocs 指南内「提交参赛作品」入口） |

### 提交渠道（作品）
- **GitHub issue 提交**：https://github.com/modelstudioai/modelstudioai.github.io/issues/new?template=fliggy-ai-travel-innovation-2026.md
- 模板字段：项目名称 / 团队与奖品领取人（GitHub ID 必填 1 位，每队最多 1 份奖品）/ 旅行场景与目标用户 / 我做了什么 / **百炼使用说明（必填）** / 效果展示（≥1 张截图或视频）/ 项目链接与复现方式 / 踩坑记录（可选）
- **红线**：① 必须使用阿里云百炼；② 公开 issue 不得填手机号/收货地址等隐私；③ 不得提交 API Key/密码

## 2. 技术栈与能力边界（已核实）

### 2.1 飞猪 FlyAI（flyai-cli，@fly-ai/flyai-cli v1.0.16）
- 安装：`npm install -g @fly-ai/flyai-cli`；无需 Key 即可用体验模式（按 IP 限流，沙箱 IP 已耗尽）
- 正式 Key 配置：`flyai config set FLYAI_API_KEY "<key>"`（存 `~/.flyai/config.json`；无 get/show 子命令）
- 命令：`search-poi`（景点）/ `search-hotel`（酒店）/ `search-flight` / `search-train` / `keyword-search` / `ai-search`（语义）/ `search-marriott-package` / `search-marriott-hotel`
- 输出：单行 JSON（name/category/listRank 榜单含"亲子榜"/freePoiStatus/ticketInfo 儿童票/经纬度/图片/预订链接）
- 推广者计划：申请入驻 → 正式 API Key → 用户经 Agent 预订得佣金分成（酒店/度假类参与分佣，交通暂不参与）

### 2.2 阿里云百炼（硬性要求）
- 参赛作品**必须使用百炼**（模板原文）；调用方式枚举：百炼 API / DashScope SDK / 百炼 CLI `bl` / OpenWork
- Managed Agent：命令执行 / 文件操作 / 记忆 / MCP / Skill 挂载；可视化工作流编排可用
- **模型可选**：qwen（原生，推荐，免费额度多）｜DeepSeek（deepseek-v4-pro / v4.1-flash / v3.2 等，阿里云直供）｜Kimi（kimi-k3 / k2.6 / k2.5 等，月之暗面直供需激活）｜GLM / MiniMax
- ⚠️ 自己持有的第三方网关 Key（如 api.0x7e.vip）**不能**替代百炼——合规判定看"是否走百炼链路"

## 3. 作品方向（已定）

**亲子遛娃旅行管家**（开放命题）
- 定位：面向 0-6 岁带娃家庭的旅行 Agent——按年龄（0-1 婴儿/1-3 学步/4-6 学龄前）过滤景点/酒店，输出"作息友好"行程
- 差异化：① 娃维度过滤引擎（亲子榜信号+分类适配+儿童票+免费+避雷词，kid_friendly_score 已实现）② 带娃避雷扫描（差评关键词：台阶/没电梯/床太小/隔音差等）③ 作息排程（每日 2-3 点+午睡+雨天/娃闹觉备选）
- 备选方向（未采用）：入境游 AI 讲解（预设命题，英语优势）、跟着课本/诗词去旅行（官方举过同类例）、旅行探索游戏化、商务出行管家

## 4. 当前进展明细（2026-10-08）

| # | 事项 | 状态 |
| --- | --- | --- |
| 1 | 本机 flyai-cli 安装 + 搜索验证（三亚/北京） | ✅ 完成 |
| 2 | flyai_tools.py 封装层（6 命令 + 娃友好评分） | ✅ 完成，本地验证通过 |
| 3 | 飞猪正式 API Key 申请 | ✅ 完成（⚠️ 曾截图暴露，建议轮换） |
| 4 | 百炼 Agent 创建（亲子遛娃旅行管家） | ✅ 完成 |
| 5 | 沙箱装 flyai-cli + 下载脚本 | ✅ 完成 |
| 6 | 沙箱调用 flyai | ❌ 429 试用额度用完（沙箱 IP）→ 需正式 Key 配置 |
| 7 | 沙箱配置正式 Key + 重测 | ⏸️ 卡在百炼欠费 |
| 8 | 百炼账户 | ❌ 欠费/风控（Agent 访问被拒）→ 需充值或免费额度 |
| 9 | 大赛报名 | ⏳ 未完成（仅用户可操作） |
| 10 | 行程生成引擎 | ⏳ 待开发（本地，不依赖百炼） |

**本地开发文件**：`C:\Users\dfjq\Doubao\chats\2026-10-08\new-chat-1\feizhu-trip-agent\`（flyai_tools.py + test_score.py）

## 5. 投入决策分析（2026-10-08，用户评估中）

### 成本
- **资金**：百炼充值约 50-100 元（一次性；qwen 模型 token 单价低）。若领到新用户免费额度/大赛 token 则可为 0
- **时间**：工具层已就绪约 60%；剩余 = 行程生成引擎（本地 1-2 天）+ 沙箱接入调试（1 天）+ 示例 Demo 与材料（1-2 天）→ 合计约 5-8 个有效工作日，10-25 前充裕
- **其他**：作品须原创、AI 参与度需如实声明

### 收益（若投入）
- Token 补贴（获奖/入围后）、专家带练、商业生态资源、联合 POC 通道
- **可沉淀资产**：flyai 封装层 + 娃友好评分引擎（可复用/开源）；推广者佣金机会（作品长期可跑）
- 经验：第三段"Agent 应用型"参赛经历（此前为 Skill/多智能体/3D 管线）

### 风险与不确定点
- 竞争未知（开放报名，个人/团队均可）；评审主观（创新/可行/市场）
- 报名未完成 = 目前一切为零（先报名才谈投入）
- 百炼欠费是唯一资金门槛；沙箱 429 已有解（正式 Key 到手）
- 模板允许"视频链接"作为项目链接 → 若最终不充值，可本地跑通 + 录屏 + 视频链接提交，但**百炼链路缺失会导致不合规**（硬要求），故充值/免费额度几乎是参赛必要条件

### 建议
- 若 100 元内投入可接受 → **值得投入**（工具层已完成大半，剩工作清晰可控）
- 若暂不想花钱 → 先完成**报名**（0 成本、锁定名额），同时用本机把**行程生成引擎 + 示例行程**做出来（0 成本、作品资产沉淀），百炼等免费额度/大赛 token 或再评估
- 决策节点：**报名（立即）+ 充值（一周内）**，最迟 10-18 前恢复百炼才赶得上提交

## 6. 下一步（按优先级）

1. **[用户] 完成报名**（alidocs「提交参赛作品」，今日或明日）
2. **[用户] 百炼充值 或 查免费额度**（费用中心/额度管理；新用户 FAQ 提到"免费千万 Tokens"待核实）
3. [我] 沙箱配置正式 Key + 重测（用户充值恢复后）
4. [我] 本地开发行程生成引擎 + 三亚示例行程（不依赖百炼，可立即开始）
5. [我] Agent 系统提示词升级（接行程生成逻辑）+ 发布 Web
6. [我] 提交材料按 GitHub 模板准备（含百炼使用说明、效果展示、项目链接）

## 7. 关键链接速查

- 官网：https://opc.aliyun.com/feizhu
- 参赛指南：https://alidocs.dingtalk.com/i/nodes/QG53mjyd800agdlKHebwk4Zj86zbX04v
- 提交模板：https://github.com/modelstudioai/modelstudioai.github.io/issues/new?template=fliggy-ai-travel-innovation-2026.md
- 飞猪 AI 开放平台（Key）：https://flyai.open.fliggy.com/
- 百炼 Agent：https://bailian.console.aliyun.com/cn-beijing/managed-agent/agents/agent_01M4CVTF231ZZF0GHKJVW9XHQP
