---
title: WebRetriever Challenge 2026 — 主索引
tags:
  - project
  - webretriever
  - competition
date: '2026-08-17'
status: active
---

# WebRetriever Challenge 2026 — 主索引

> 本笔记为 WebRetriever 挑战赛的唯一主文档。后续所有相关信息、配置变更、测试结果、bug 修复均追加于此，新 session 从这里接续。

> **🏷️ 新 session 先读**（2026-08-25 起）：
> - 现状与全部上下文 → [[session-handoff-webretriever-to-claude-2026-08-25]]（代码已 push f4c7836、aixforge 网关、3/5 答对 0 假成功、唯一待办=窗口内 @WR-EvalBot 提交 + 确认额度）
> - 上一份交接（修复过程细节） → [[session-handoff-webretriever-to-zcode-2026-08-24]]

---

## 1. 项目基本信息

| 项 | 内容 |
|---|---|
| 比赛 | 2026 WebRetriever Challenge |
| 团队 | 林木木 |
| GitHub 仓库 | `hhhhhhalf/WR-001`（Private） |
| 仓库本地路径 | `D:\claude-work\WR-001` |
| 历史代码参考 | `D:\claude-work\webretriever`（7 月底 DOM 方案） |
| 提交群 | WR-001 林木木 |
| 评测 Bot | @WR-EvalBot |

---

## 2. 关键配置

### 2.1 模型 API
- **服务商**：0x7e.vip 网关
- **域名**：`api.0x7e.vip`
- **模型**：`kimi-k2.6`
- **调用方式**：第三方网关调用 / Gateway
- **仓库配置文件**：`WR-001/config.json`

### 2.2 Agent 方案
- **主方案**：DOM 文本方案（`use_dom: true`）
- **备选方案**：视觉方案（截图 + UI-TARS 动作空间）
- **核心文件**：
  - `src/agent/agent.py`：模型交互 + 动作解析
  - `src/agent/main.py`：多进程调度 + 结果保存
  - `src/agent/prompts.py`：Prompt 模板
  - `src/agent/web_controller.py`：浏览器操控
  - `src/agent/dom_extractor.py`：DOM 元素提取

### 2.3 环境
- **Python**：3.10（`environment.yml` 声明）
- **核心依赖**：`playwright`, `openai`, `numpy`, `opencv-python`, `Pillow`, `requests`

---

## 3. 当前状态

### 3.1 已完成功能
- [x] 仓库克隆与初始化
- [x] `config.json` 配置 Kimi K2.6
- [x] `environment.yml` 命名
- [x] DOM Agent 代码从旧仓库迁移
- [x] `main.py` 自动读取 `config.json`
- [x] 模型输出解析鲁棒性增强：
  - 支持无 `Action:` 前缀的 `finished(...)`
  - 纯答案文本自动包装为 `finished(content='...')`
  - 多个 Thought/Action 混在一起时提取第一个合法调用
- [x] 白名单表单提交（`api.0x7e.vip` / 第三方网关调用）
- [x] 第一次代码提交（commit `b15dcce`）
- [x] 解析鲁棒性修复提交（commit `918fe0a`）
- [x] 沙箱 CDP 连接标签页清理修复（commit `0e47a1b`）：连接后保留至少一个标签页，避免浏览器被回收
- [x] agent_answer/result.json 空值兜底修复（commit `fe60d92`）：增强 API 超时重试、多层答案兜底、异常时仍保存结果
- [x] capture.json 空请求记录修复（commit `7ee3cc9`）：context 级请求监听 + 空记录兜底 + 异常时仍保存 capture.json

### 3.2 本地验证结果

#### 测试 1：iPad Air 3 屏幕更换指南
- **任务文件**：`D:\claude-work\webretriever\data\task0_only.json`
- **状态**：`SUCCESS`
- **步数**：2 步
- **agent_answer**：已打开 iPad Air 3 屏幕更换指南 URL
- **结论**：✅ 流程完全跑通，输出格式正确

#### 测试 2：猫眼票房与世界银行（example_tasks 2 题）
- **任务文件**：`WR-001/data/example_tasks.json`
- **状态**：均生成非空 result.json 与 capture.json
- **capture.json 请求数**：猫眼 21 个，世界银行 10 个
- **结论**：✅ 输出保存逻辑正常，capture.json 不再为空

### 3.3 待跟进
- [ ] 第四次官方冒烟测试结果（基于 commit `7ee3cc9`）
- [ ] 若再次失败，按 Bot 返回的具体错误继续修
- [ ] 若通过，评估是否需要优化答案准确率（prompt、DOM 提取、视觉 fallback）

---

## 4. 操作速查

### 4.1 本地单任务测试
```bash
cd D:\claude-work\WR-001
# 启动 Chrome CDP（手动或脚本）
# 然后：
python src/agent/main.py --input data/example_tasks.json --output test_results --cdp_url http://localhost:9222
```

### 4.2 提交官方冒烟测试
在专属提交群发送：
```
@WR-EvalBot 提交代码
```

### 4.3 查询进度
```
@WR-EvalBot 验证过了吗
@WR-EvalBot 环境好了吗
```

---

## 5. 已知问题与坑

1. **模型输出格式不稳定**
   - 表现：有时省略 `Action:`、有时把多个 Action 和答案文本混在一起、有时只输出答案
   - 修复：已加多层兜底解析
2. **猫眼票房类 SPA 页面**
   - DOM 可交互元素抽取困难，模型容易放弃或幻觉
   - 后续可考虑：视觉方案 fallback、针对 SPA 的页面文本摘要优化
3. **Windows 本地 fcntl**
   - 代码已做兼容：`try: import fcntl except ImportError: fcntl = None`
   - 官方 Linux 环境不受影响

---

## 6. 变更日志

### 2026-08-17 第一次提交与修复
- 配置 Kimi K2.6，启用 DOM 方案
- 迁移旧仓库 DOM Agent 代码
- 提交 commit `b15dcce`
- 官方冒烟测试未通过：agent_answer 为空
- 修复模型输出解析鲁棒性
- 提交 commit `918fe0a`，重新触发官方冒烟测试
- 官方冒烟测试未通过：连接沙箱后清空标签页导致浏览器关闭
- 修复 `web_controller.py`：`init_playwright_context` 与 `reset_browser_state` 清理标签页时保留最后一个，避免沙箱 CDP 连接断开
- 提交 commit `0e47a1b`，重新触发官方冒烟测试
- 官方冒烟测试未通过：3 道题中 1 道缺少有效输出（结果为空）
- 修复 `agent.py` 与 `main.py`：API 超时/重试增强、agent_answer 多层兜底、异常时仍保存 result.json
- 提交 commit `fe60d92`，重新触发官方冒烟测试

### 2026-08-17 第二次官方冒烟测试结果
- 状态：3 道题中 1 道缺少有效输出（结果为空）
- commit：`0e47a1b`

### 2026-08-17 第三次官方冒烟测试结果
- 状态：环境安装失败
- commit：`fe60d92`
- 原因：conda 软件包网络拉取失败，属临时性网络波动，非代码问题
- 建议：几分钟后重新 @WR-EvalBot 发送「提交代码」再跑

### 2026-08-17 第四次修复：capture.json 空请求记录
- 官方反馈：环境安装成功，但 3 道题中仍有 1 道缺少有效输出，根因为该题 `capture.json` 的请求记录为空
- 修复 `src/agent/main.py`：
  - 请求监听从 page 级别迁移到 context 级别，避免新打开页面漏抓
  - `reset_browser_state` 仅在重建 context 时重新绑定监听器，防止重复监听
  - 无 xhr/fetch 请求时写入当前页面 URL 作为兜底记录
  - 任务异常时仍保存 capture.json 兜底记录
- 本地验证：`example_tasks.json` 两题均生成非空 result.json 与 capture.json
- 提交 commit `7ee3cc9`，已 push 到 `main`
- 下一步：重新 @WR-EvalBot 发送「提交代码」跑官方冒烟测试

## 7. 关联记忆

- [[webretriever-dom-progress-2026-07-31]] — 7 月底 DOM 方案进度
- [[WebRetriever挑战赛参赛评估]] — 比赛整体评估
- [[WebRetriever挑战赛2026-07-28会话交接]] — 历史 bug 修复记录
- [[webretriever-smoke-test-page-cleanup-fix-2026-08-17]] — 本次冒烟测试修复记忆

---

## 8. 待确认/待决策

- 若官方冒烟测试通过，是否继续优化答案准确率？
- 是否需要在 config.json 中保留视觉方案切换开关？
- 是否需要针对常见网站类型（电商、数据、百科）做特化策略？

---

*最后更新：2026-08-17*


---

## 9. 代码复盘（2026-08-17）

已整理完整代码复盘文档：

- [[WebRetriever代码复盘-2026-08-17]] — 仓库架构、关键文件、模型配置、已修复 bug、技术债务、后续优化方向、正式提交计划

核心结论：
- 当前代码（commit `7ee3cc9`）已通过官方冒烟测试，基础链路稳定。
- 主要风险：iFixit 硬编码兜底、DOM 对 SPA/自定义组件识别有限、视觉方案未验证。
- 8 月 27 日正式提交前建议做 10-20 题批量本地测试，重点看答案准确率。

---

*最后更新：2026-08-17*

---

## 10. 正式比赛规则对齐（2026-08-24 读取官方 FAQ）

已读取桌面 `WebRetriever - Official FAQ.md`（实际为 RTF 格式），提取关键规则并与本索引对齐如下。

### 10.1 赛程与提交（新增/确认）

| 项 | 内容 |
|---|---|
| 正式评测窗口 | 8月27日 10:00 — 9月2日 23:59（北京时间） |
| 每日正式评测次数 | 1 次，00:00 刷新 |
| 提交时间认定 | 在专属提交群 @WR-EvalBot 发起「正式评测」的时间 |
| 全量题数 | 每次 100 题，所有队伍同一套题 |
| 冒烟测试要求 | 8月27日前至少通过一次；每次代码改动后、发起正式评测前需重新通过 |
| 冒烟测试通过标志 | Bot 回复「冒烟测试通过，环境就绪！可以发起评测了」或「代码验证通过，环境就绪！可以发起评测了」 |
| 赛中分数 | 仅反馈「答案准确性得分」，不含轨迹分 |
| 最终分数 | 人工复核：轨迹正确性 + 答案正确性 |
| 每日排名公布 | 每天 12:00 在队长群匿名公布当前累积排名第一的分数 |

> **2026-08-25 确认补充**：
> - **官方冒烟测试：✅ 已通过**（2026-08-25，Bot 回复确认）。规则：每次代码改动后、发起正式评测前需重新过冒烟。
> - 基线校准：官方 15 题样本（`protocol3_sample15.json`）= 100 题池切片；本地基线 **3/15 = 20%**（3/5 仅对 sample5 子集成立，不可外推；构成偏表格/深链型约 20-40%，偏筛选门户型更低）。
> - 策略：每日 1 次（00:00 刷新）× 窗口约 7 天 ≈ 7 次机会、取最优；**8/27 当天先提交一轮锁定有效提交（含荣誉证书）**，后续按官方分数反馈决定是否再迭代。
> - **2026-08-25 已发 `@WR-EvalBot 提交代码`**（冒烟 ✅ 通过）；待 8/27 10:00 通道打开后在群内发起「正式评测」——**提交时间以发起「正式评测」的动作为准**（10.1 表格）。

### 10.2 沙箱与运行环境（新增/确认）

- 沙箱：腾讯云，分辨率 1920×1080
- 每题从干净浏览器状态开始（无 cookie/localStorage）
- 可开多 tab，弹窗不拦截
- **禁止 bash / curl 等命令行工具**
- 可在 conda 环境自定义依赖（包括 JDK）
- 下载文件通过 Playwright 存到代码目录，磁盘空间无限制
- OpenAI 官方 API 可直接在 `config.json` 配置；其他算法服务域名需填表加白名单

### 10.3 规则限制（需重点检查）

| 项 | 规则 |
|---|---|
| max steps | ≤ 100 步，超过直接判失败 |
| 单步定义 | 基于当前页面预测并执行一个动作 = 1 步 |
| 总评测时长 | ≤ 4 小时 |
| 单次模型调用 | ≤ 3 分钟 |
| 并发要求 | 模型需支持 8 进程并发 |
| 搜索引擎 | **禁止外部搜索引擎**，只能用网站内搜索 |
| CDP | 直接 CDP 不合规，必须基于 Playwright 创建 CDP session |
| PDF 任务 | 可下载后用 coding agent 处理，整体算 1 步 |
| 登录任务 | 尽量避免；如出现需登录则为网页变化 |
| 验证码/风控 | 可能出现，需 Agent 自行处理 |

### 10.4 模型版本限制（重要）

必须使用 OpenAI 兼容格式 API。允许的最高版本：

- OpenAI — GPT-5.4
- Anthropic — Claude 4.6
- Google — Gemini 3.1
- xAI — Grok 4.3
- 智谱 AI — GLM-5V-Turbo
- Moonshot — **Kimi-K2.6** ✅（当前配置一致）
- 阿里云 — Qwen3.7

未列厂商只能用 **2026 年 7 月 16 日前**发布的模型。严禁套壳/中转绕限制。

> 当前 `config.json` 使用 `kimi-k2.6`，符合版本限制。多模型混用允许，但每个模型都要合规。

### 10.5 评分标准（与已知规则一致）

与 [[WebRetriever 协议 III 最终评测规则已确认]] 一致：

- 采用 Protocol III（导航 + 取数）
- **必须同时满足**：导航到目标页面 + 提取正确字段
- 导航对但答案错 = 失败
- 答案对但导航错 = 失败
- `agent_answer` 为**纯文本**，多字段用 `\n` 或空格分隔
- 语义一致即可，数字以目标页面值为准，中英文/简繁体等价
- 排名：综合评分高 → 总步数少 → 总时长短；评测窗口内可多次提交、**取最优成绩**
- **最终得分 = 通过任务数 ÷ 总任务数**（比例分）（2026-08-25 官方说明）
- **所有提交有效结果的队伍均获荣誉证书**（不要求得高分，2026-08-25 官方说明）
- 正式评测环境：官方云端沙箱、**CDP URL 自动传入**（不需自建浏览器）；模型资源选手自备、**需公网可访问**（aixforge 为公网 HTTPS，✅ 已验证；0x7e.vip 同性质此前 OK）

### 10.6 冒烟测试常见失败原因（官方清单）

| # | 原因 | 解决方案 |
|---|---|---|
| 1 | 提供 CDP_URL 后无法连接沙箱 | 保留比赛模板仓库中浏览器连接兼容逻辑 |
| 2 | 个别任务 `capture.json` 未正常捕获网络请求 | 检查网络请求捕获逻辑 |
| 3 | 连接沙箱后清空标签页导致浏览器关闭 | **不要清空所有标签页** |
| 4 | 模型调用失败 | 检查 API Key 配置和网络连通性 |
| 5 | 执行过程中无响应导致超时 | 检查模型调用是否有超时重试机制 |

> 其中第 3、2 项与我们已修复的 commit `0e47a1b`、`7ee3cc9` 对应，需确保修复逻辑在后续提交中保留。

### 10.7 与当前代码/状态的对齐结论

| 维度 | 当前状态 | 是否对齐 | 备注 |
|---|---|---|---|
| 模型版本 | `kimi-k2.6` | ✅ | 在允许列表内 |
| CDP 使用 | 基于 Playwright 创建 context 和 page | ✅ | 未直接操作 CDP，符合规则 |
| 标签页清理 | 保留最后一个标签页 | ✅ | 已修复 |
| capture.json | context 级监听 + 兜底 | ✅ | 已修复 |
| 超时重试 | agent.py 中已增强 | ✅ | 需确认单次调用 < 3 分钟 |
| 外部搜索 | 未使用 | ✅ | Agent 只操作目标页面 |
| 多 tab/弹窗 | 默认未主动管理 | ⚠️ | 若题目触发弹窗，需补充处理 |
| 视觉方案 | 未验证 | ⚠️ | 如需启用，模型版本需再确认 |
| 100 步限制 | `total_steps = 100`，并赋值 `agent.max_trajectory_length = 100` | ✅ | `src/agent/main.py:570-572` |
| 8 进程并发 | Worker 数 = `len(CDP_URLS)`，每个 worker 独立进程+独立模型 client | ✅ | 并发数由官方 CDP URL 数量决定；若提供 8 个则天然 8 并发 |
| 模型调用超时 | `timeout=120` 秒（2 分钟），小于规则上限 3 分钟 | ✅ | `src/agent/agent.py:697`（视觉）、`:840`（DOM） |
| 模型重试 | 视觉 `try_times=3`、DOM `try_times=5`，异常后指数退避 1s/2s/4s（视觉）、1s/2s/4s/8s/8s（DOM） | ✅ | `src/agent/agent.py:706-710`、`:848-852`，2026-08-24 修改 |
| viewport | 默认值改为 `1920×1080`，launch 模式与沙箱一致 | ✅ | `src/agent/web_controller.py:43-44`、`:82`，2026-08-24 修改 |

### 10.8 待确认/待决策

- [x] 当前 `main.py` 的 `max_steps` 具体设置为多少？是否 ≤ 100？→ 已确认：`total_steps = 100`
- [x] 模型网关 `api.0x7e.vip` 是否已加入官方白名单？→ 已确认：已加入
- [x] 8 进程并发下模型调用是否稳定？是否需要限流/队列？→ 已确认：Worker 数 = CDP_URL 数，模型调用 timeout=120s 并加指数退避
- [x] 是否需要在 Agent 中加入弹窗/新 tab 的默认处理逻辑？→ 已确认：`main.py:668-678` 已有新标签页检测与切换
- [ ] 正式提交前是否做 10-20 题批量本地测试，重点验证答案准确率与步数？

### 10.9 2026-08-24 代码调整

- **viewport 默认值改为 1920×1080**：`src/agent/web_controller.py:43-44`、`src/agent/web_controller.py:82`（launch 模式）
  - 原因：与官方沙箱分辨率一致，减少环境差异
  - 风险：截图文件变大；视觉方案 token 增加（当前主方案为 DOM，影响小）
- **模型重试加指数退避**：`src/agent/agent.py:706-710`（视觉）、`src/agent/agent.py:848-852`（DOM）
  - 视觉：1s → 2s → 4s
  - DOM：1s → 2s → 4s → 8s → 8s
  - 原因：避免 429/网络抖动时瞬间耗尽重试次数
- **语法检查**：`python -m py_compile src/agent/agent.py src/agent/web_controller.py src/agent/main.py` 通过
- **提交与推送**：commit `6304f7e`，已 push 到 `main`
  - `chore: viewport统一1920x1080; 模型重试加指数退避`
  - 改动文件：`src/agent/agent.py`、`src/agent/web_controller.py`

---

*本章节追加于 2026-08-24*

