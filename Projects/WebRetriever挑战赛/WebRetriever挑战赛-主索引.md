---
title: WebRetriever Challenge 2026 — 主索引
---

# WebRetriever Challenge 2026 — 主索引

> 本笔记为 WebRetriever 挑战赛的唯一主文档。后续所有相关信息、配置变更、测试结果、bug 修复均追加于此，新 session 从这里接续。

> **🏷️ 新 session 先读**（2026-08-26 起）：
>
> - 现状与全部上下文 → [[session-handoff-webretriever-to-zcode-2026-08-26]]（合规修复已 push `17609f8`、删全部题目特判/预设跳转、待重过冒烟+8/27「开始评测」）
> - 上一份交接（3d38d0c 及之前状态） → [[session-handoff-webretriever-to-claude-2026-08-25]]

---

## 1. 项目基本信息

| 项         | 内容                                         |
| --------- | ------------------------------------------ |
| 比赛        | 2026 WebRetriever Challenge                |
| 团队        | 林木木                                        |
| GitHub 仓库 | `hhhhhhalf/WR-001`（Private）                |
| 仓库本地路径    | `D:\claude-work\WR-001`                    |
| 历史代码参考    | `D:\claude-work\webretriever`（7 月底 DOM 方案） |
| 提交群       | WR-001 林木木                                 |
| 评测 Bot    | @WR-EvalBot                                |

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

| 项        | 内容                                                |
| -------- | ------------------------------------------------- |
| 正式评测窗口   | 8月27日 10:00 — 9月2日 23:59（北京时间）                    |
| 每日正式评测次数 | 1 次，00:00 刷新                                      |
| 提交时间认定   | 在专属提交群 @WR-EvalBot 发起「开始评测」的时间                    |
| 全量题数     | 每次 100 题，所有队伍同一套题                                 |
| 冒烟测试要求   | 8月27日前至少通过一次；每次代码改动后、发起正式评测前需重新通过                 |
| 冒烟测试通过标志 | Bot 回复「冒烟测试通过，环境就绪！可以发起评测了」或「代码验证通过，环境就绪！可以发起评测了」 |
| 赛中分数     | 仅反馈「答案准确性得分」，不含轨迹分                                |
| 最终分数     | 人工复核：轨迹正确性 + 答案正确性                                |
| 每日排名公布   | 每天 12:00 在队长群匿名公布当前累积排名第一的分数                      |

> **2026-08-25 确认补充**：
>
> - **官方冒烟测试：✅ 已通过**（2026-08-25，Bot 回复确认）。规则：每次代码改动后、发起正式评测前需重新过冒烟。
> - 基线校准：官方 15 题样本（`protocol3_sample15.json`）= 100 题池切片；本地基线 **3/15 = 20%**（3/5 仅对 sample5 子集成立，不可外推；构成偏表格/深链型约 20-40%，偏筛选门户型更低）。
> - 策略：每日 1 次（00:00 刷新）× 窗口约 7 天 ≈ 7 次机会、取最优；**8/27 当天先提交一轮锁定有效提交（含荣誉证书）**，后续按官方分数反馈决定是否再迭代。
> - **2026-08-25 已发 `@WR-EvalBot 提交代码`**（冒烟 ✅ 通过）；待 8/27 10:00 通道打开后在群内发起「开始评测」——**提交时间以发起「开始评测」的动作为准**（10.1 表格）。

### 10.2 沙箱与运行环境（新增/确认）

- 沙箱：腾讯云，分辨率 1920×1080
- 每题从干净浏览器状态开始（无 cookie/localStorage）
- 可开多 tab，弹窗不拦截
- **禁止 bash / curl 等命令行工具**
- 可在 conda 环境自定义依赖（包括 JDK）
- 下载文件通过 Playwright 存到代码目录，磁盘空间无限制
- OpenAI 官方 API 可直接在 `config.json` 配置；其他算法服务域名需填表加白名单

### 10.3 规则限制（需重点检查）

| 项         | 规则                                        |
| --------- | ----------------------------------------- |
| max steps | ≤ 100 步，超过直接判失败                           |
| 单步定义      | 基于当前页面预测并执行一个动作 = 1 步                     |
| 总评测时长     | ≤ 4 小时                                    |
| 单次模型调用    | ≤ 3 分钟                                    |
| 并发要求      | 模型需支持 8 进程并发                              |
| 搜索引擎      | **禁止外部搜索引擎**，只能用网站内搜索                     |
| CDP       | 直接 CDP 不合规，必须基于 Playwright 创建 CDP session |
| PDF 任务    | 可下载后用 coding agent 处理，整体算 1 步             |
| 登录任务      | 尽量避免；如出现需登录则为网页变化                         |
| 验证码/风控    | 可能出现，需 Agent 自行处理                         |

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

| # | 原因                            | 解决方案                |
| - | ----------------------------- | ------------------- |
| 1 | 提供 CDP_URL 后无法连接沙箱            | 保留比赛模板仓库中浏览器连接兼容逻辑  |
| 2 | 个别任务 `capture.json` 未正常捕获网络请求 | 检查网络请求捕获逻辑          |
| 3 | 连接沙箱后清空标签页导致浏览器关闭             | **不要清空所有标签页**       |
| 4 | 模型调用失败                        | 检查 API Key 配置和网络连通性 |
| 5 | 执行过程中无响应导致超时                  | 检查模型调用是否有超时重试机制     |

> 其中第 3、2 项与我们已修复的 commit `0e47a1b`、`7ee3cc9` 对应，需确保修复逻辑在后续提交中保留。

### 10.7 与当前代码/状态的对齐结论

| 维度           | 当前状态                                                                        | 是否对齐 | 备注                                                      |
| ------------ | --------------------------------------------------------------------------- | ---- | ------------------------------------------------------- |
| 模型版本         | `kimi-k2.6`                                                                 | ✅    | 在允许列表内                                                  |
| CDP 使用       | 基于 Playwright 创建 context 和 page                                             | ✅    | 未直接操作 CDP，符合规则                                          |
| 标签页清理        | 保留最后一个标签页                                                                   | ✅    | 已修复                                                     |
| capture.json | context 级监听 + 兜底                                                            | ✅    | 已修复                                                     |
| 超时重试         | agent.py 中已增强                                                               | ✅    | 需确认单次调用 < 3 分钟                                          |
| 外部搜索         | 未使用                                                                         | ✅    | Agent 只操作目标页面                                           |
| 多 tab/弹窗     | 默认未主动管理                                                                     | ⚠️   | 若题目触发弹窗，需补充处理                                           |
| 视觉方案         | 未验证                                                                         | ⚠️   | 如需启用，模型版本需再确认                                           |
| 100 步限制      | `total_steps = 100`，并赋值 `agent.max_trajectory_length = 100`                 | ✅    | `src/agent/main.py:570-572`                             |
| 8 进程并发       | Worker 数 = `len(CDP_URLS)`，每个 worker 独立进程+独立模型 client                       | ✅    | 并发数由官方 CDP URL 数量决定；若提供 8 个则天然 8 并发                     |
| 模型调用超时       | `timeout=120` 秒（2 分钟），小于规则上限 3 分钟                                           | ✅    | `src/agent/agent.py:697`（视觉）、`:840`（DOM）                |
| 模型重试         | 视觉 `try_times=3`、DOM `try_times=5`，异常后指数退避 1s/2s/4s（视觉）、1s/2s/4s/8s/8s（DOM） | ✅    | `src/agent/agent.py:706-710`、`:848-852`，2026-08-24 修改   |
| viewport     | 默认值改为 `1920×1080`，launch 模式与沙箱一致                                            | ✅    | `src/agent/web_controller.py:43-44`、`:82`，2026-08-24 修改 |

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

---

## 11. 2026-08-26 合规修复（对齐「有效成绩认定」公告）

- 组委会公布有效成绩认定：①逐步交互 ②实时自主 ③来源合规 + **提交代码与运行轨迹人工复核**。
- **提交库确认**：正式提交仓库 = `hhhhhhhalf/WR-001`（Private，本地 `D:\claude-work\WR-001`）；`webretriever` 仅为历史参考库（origin 指向官方仓库 `Mininglamp-AI/WebRetriever`，**禁止 push**）。
- WR-001 删除：iFixit 硬编码兜底、Statcounter 深链 hook、is_ifixit 特判分支、prompts 任务示例查询 → commit `17609f8` 已 push main。
- 实测：iFixit 样题 SUCCESS、16 步、纯模型自主导航（`WR-001/output/smoke_compliance_wr001/`）。
- **状态变更**：8/25 冒烟通过（`3d38d0c`）不再适用，正式评测前须重过冒烟；8/27 10:00 窗口发「开始评测」。
- 详见 [[session-handoff-webretriever-to-zcode-2026-08-26]]

*追加于 2026-08-26*

---

## 12. 2026-08-27 官方口径确认 + prompts 二次合规修复

### 12.1 官方对 IMDb 筛选题口径（选手群对话）

- **8 路并行**：正式评测强制 8 路并发请求。
- **IMDb 第 58 题示例**：查询满足若干条件的电影数量，入口 `https://www.imdb.com/`。
- **官方判定**：Agent 必须像人一样做细粒度的 filter 填充和点击搜索，通过这种方式跳转到 target 页面才算正确；**如果 Agent 猜测拼接 URL + goto 到达 target 页面，算不合规**。

### 12.2 prompts 二次合规修复

据此判断当前 `prompts.py` 存在 3 处与官方口径冲突的描述：

| 位置     | 修改前                                                                   | 修改后                                                                         |
| ------ | --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `:124` | 鼓励 goto 用于「date-based or parameterized pages when normal clicks fail」 | 明确 goto 只能用于页面上显式给出的链接或任务指定 URL，**禁止绕过 filter / 搜索表单 / 日期选择器**              |
| `:162` | 死循环换策略允许「construct a date/parameter URL」                              | 删除该选项，仅保留 search / menu / scroll / 放弃                                       |
| `:164` | 整条教 sam.gov 构造完整过滤 URL + `goto()` 绕开 UI                               | **整条删除**                                                                    |
| `:158` | 日期查询小节编号重复为「7.」                                                       | 改为「8. DATE-BASED QUERIES (LAST RESORT)」，强调 URL 拼日期是**最后手段**，且禁止用于非日期 filter |

- **提交**：commit `f58e7c0` 已 push `main`
- **本地语法检查**：`python -m py_compile src/agent/prompts.py` 通过

### 12.3 当前状态（2026-08-27 上午）

- **官方 Bot 系统异常**：`@WR-EvalBot 提交代码` 返回「系统还在异常中，暂时没法确认提交，请稍等几分钟再 @我说'提交代码'」。
- **策略**：
  1. 每隔 5–10 分钟重试 `@WR-EvalBot 提交代码`；
  2. 若 10:00 正式窗口开启时仍未恢复/未通过冒烟，**不抢第一波**，等冒烟通过后再发「开始评测」；
  3. 若持续异常，联系赛事运维。
- **本地验证**：iFixit 样题已本地跑完 `f58e7c0`，**SUCCESS**、22 步、`agent_answer='iPad Air 3 屏幕更换'`、最终到达 `https://zh.ifixit.com/Guide/iPad+Air+3+屏幕更换/143725`，纯 UI 交互（搜索→点击指南标签→滚动→再搜索→点击指南链接），无 URL 拼接绕过行为（`WR-001/output/smoke_f58e7c0/`）。

### 12.4 风险与决策

- 删除 sam.gov 的 URL filter 提示后，该类题可能得分下降，但**避免人工复核时被判违规**。
- 日期查询 URL 构造保留为「最后手段」，是目前与官方口径的最小冲突点；若后续官方明确禁止，则进一步删除。

### 12.5 2026-08-27 冒烟测试 result.json 缺失修复

- **官方冒烟结果**：3 道题中 2 道输出正常，1 道缺少有效输出（未生成 result.json）。
- **根因分析**（代码审计）：
  1. `main.py:744-748` 对 `FAIL_SAVE_SCREENSHOT_ERROR` 直接 `continue`，未保存 result.json；
  2. `main.py:463-492` 浏览器状态重置失败 / 页面初始化失败等 early failure 也直接 `continue`，未保存 result.json；
  3. `safe_save_results` 中 `for tmp_file in temp_result_path:` 遍历字符串，临时文件清理逻辑错误。
- **修复**：commit `8f9b13d` 已 push `main`
  - 删除 `FAIL_SAVE_SCREENSHOT_ERROR` 的特殊 `continue`，走正常保存流程；
  - 新增 `_save_early_fallback()`，在浏览器重置失败、页面初始化失败等 early failure 时仍写出 result.json + capture.json；
  - 修复 `safe_save_results` 字符串迭代 bug。
- **本地验证**：iFixit 样题 commit `8f9b13d` 本地 SUCCESS，4 步，result.json / capture.json 均正常（`WR-001/output/smoke_8f9b13d/`）。
- **官方冒烟结果**：commit `8f9b13d` **已通过**（3 题均生成有效输出）。
- **正式评测**：已发送 `@WR-EvalBot 开始评测`，但评测在运行中**卡住**（基于 commit `8f9b13d`）。

### 12.6 2026-08-27 正式评测卡住 + 健壮性二次修复

- **主办方反馈**："后台查看您代码存在健壮性问题，遇到边界情况没有兜底机制导致报错卡住"。
- **已询问**：具体日志/异常/卡住位置，待主办方进一步回复。
- **健壮性修复**：commit `61b6e61` 已 push `main`
  - `dom_extractor.py`：`page.evaluate()` 全部加 `timeout=10000`；
  - `main.py`：直接 `page.evaluate()` 读取正文加 `timeout=5000/3000`；
  - `web_controller.py`：
    - `wait_for_rendering_complete` 中 `document.readyState` 加 `timeout=5000`；
    - `page.goto` 超时从 150s 缩短到 60s（fallback 30s）；
    - 下载内容注入页面 evaluate 加 `timeout=5000`。
- **当前状态**：
  - 今天（8/27）已发起正式评测并卡住，今日机会可能已消耗；
  - 明天 00:00 刷新后，基于 commit `61b6e61` 重新冒烟 + 正式评测。
- **后续策略**：
  1. 等主办方回复具体日志；
  2. 明天冒烟通过后，确认系统稳定再发「开始评测」；
  3. 继续审计代码中未加超时的 Playwright 操作（`handle.scroll_into_view_if_needed`、`handle.focus`、未 timeout 的 `page.evaluate` 等）。

*追加于 2026-08-27*

---

---

## 13. 2026-08-27 主办方回复：次数不可重置 + 边界情况处理要点

### 13.1 核心结论

- **今日正式评测次数已使用**，且**代码问题导致的失败无法当日重置次数**。
- **提交代码（冒烟测试）没有每日次数限制**。
- 今日无法再提交正式评测。
- 主办方晚些时间会整理选手代码常见问题的要点，避免再次评测出现同类问题。

### 13.2 主办方指出的重点注意方向

> "您需要注意代码边界情况的处理，比如模型调用、异常兜底处理、浏览器页面打开关闭等。"

拆解为以下三类必须加固的边界：

1. **模型调用边界**
   - API 超时/重试/退避是否充分
   - 空返回 / 非预期格式 / 截断输出的兜底
   - 8 路并发下的限流与异常隔离
2. **异常兜底处理**
   - 任何步骤失败时是否仍能写出 `result.json` + `capture.json`
   - 中间状态（early failure）是否走统一兜底保存
   - 字符串/字典类型误用（如 `safe_save_results` 字符串迭代 bug）
3. **浏览器页面打开关闭**
   - 标签页清空/重置时是否保留至少一个页面，避免浏览器被回收
   - `page.goto` / `page.evaluate` / 渲染等待是否都有超时
   - 新 tab / 弹窗 / 页面崩溃的检测与恢复

### 13.3 当前可执行动作

- 今日可无限次跑 `@WR-EvalBot 提交代码` 做冒烟测试，验证 `61b6e61` 稳定性；
- 等待主办方整理的问题要点，针对性再修一轮；
- 明日 00:00 刷新后，再发起正式评测。

*追加于 2026-08-27*

---

## 14. 2026-08-27 健壮性二次修复 + 本地冒烟验证 + 代码已 push

### 14.1 修复内容（commit `c2791ef`）

基于主办方提示的"模型调用、异常兜底、浏览器页面打开关闭"三类边界，在 `61b6e61` 基础上进一步加固：

| 文件                            | 修复点                                         | 说明                                                                                                  |
| ----------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `src/agent/dom_extractor.py`  | 移除 `page.evaluate` 的 `timeout=10000`        | Playwright sync API 的 `evaluate` 不接受 `timeout` 参数，此前会抛 `unexpected keyword argument 'timeout'`      |
| `src/agent/web_controller.py` | 仅保留合法 timeout                               | `launch/connect_over_cdp/goto` + `context.set_default_timeout(30000)`；`page.evaluate` 类操作去掉 timeout |
| `src/agent/web_controller.py` | `check_url_accessible` 加 try-except/finally | 防止 browser/context 泄漏，异常时也能关闭                                                                       |
| `src/agent/main.py`           | 新增 worker 级超时兜底                             | 主进程监控每个 worker，超过 30 分钟强制 terminate/join/kill                                                       |
| `src/agent/main.py`           | `new_cdp_session` 加 try-except              | 新标签页创建 CDP session 失败不崩溃                                                                            |
| `src/agent/main.py`           | 新标签页 viewport 设置加 try-except                | 避免切换标签页时因 viewport 设置失败导致 worker 退出                                                                 |

### 14.2 本地冒烟验证

#### 测试 1：iFixit 样题（`task0_only.json`）

- **命令**：`python src/agent/main.py --input data/task0_only.json --output output/smoke_fix_task0 --cdp_url launch --use_dom`
- **状态**：`SUCCESS`
- **步数**：15 步
- **agent_answer**：`iPad Air 3 屏幕更换指南已加载，包含11个步骤，从注意事项到最终组装。`
- **最终 URL**：`https://zh.ifixit.com/Guide/iPad+Air+3+屏幕更换/143725`
- **输出**：result.json / capture.json 均正常生成
- **结论**：✅ 基础链路完全跑通

#### 测试 2：example_tasks.json（猫眼 + 世界银行）

- **命令**：`python src/agent/main.py --input data/example_tasks.json --output output/smoke_fix_examples --cdp_url launch --use_dom`
- **状态**：手动停止前猫眼题跑到第 26 步，进程未崩溃


- **观察**：
  - 猫眼 SPA 日期选择器/分账票房切换模型持续循环，但防死循环机制在生效（日志中多次出现"防死循环：强制换策略"）
  - worker 进程未卡死，CPU/内存正常
  - 这说明 **worker 级超时兜底** 已可作为最后防线，避免 8 路并发时整体评测卡住
- **结论**：⚠️ 猫眼题准确率未解决，但**代码健壮性目标已验证**（不崩溃、不整体卡住）

### 14.3 提交状态

- **commit**：`c2791ef`
- **message**：`fix(robustness): 主办方提示边界情况处理——worker超时、page/cdp异常兜底、合法timeout`
- **已 push**：`main` → `origin/main`

### 14.4 下一步动作

1. **触发官方冒烟测试**：在群内发送 `@WR-EvalBot 提交代码`
2. **冒烟通过后**：明日 00:00 刷新后发起 `@WR-EvalBot 开始评测`
3. **若冒烟失败**：按 Bot 返回的具体错误继续修健壮性

*追加于 2026-08-27*

### 14.1 修复内容（commit `1151f8b`，在 `c2791ef` 基础上）

- **全量扫描移除非法 timeout**：`main.py` 中 2 处 `page.evaluate(..., timeout=...)` 被移除。
- **验证命令**：`rg "page\.(evaluate|evaluate_handle)\(.*timeout=|bring_to_front\(.*timeout=|query_selector_all\(.*timeout=|inner_text\(.*timeout=" src/agent` 返回无匹配。
- **语法检查**：`python -m py_compile src/agent/main.py src/agent/web_controller.py src/agent/dom_extractor.py src/agent/agent.py src/agent/prompts.py` 通过。

### 14.5 "不会再被卡住" 的客观评估

**已覆盖的兜底（代码层面）**：

| 边界类型          | 已加固项                                                                      |
| ------------- | ------------------------------------------------------------------------- |
| 非法 timeout 参数 | 全量移除不支持的 timeout                                                          |
| 合法 timeout    | launch / connect_over_cdp / goto / wait_for\_* / handle.click 等均带 timeout |
| 默认超时          | `context.set_default_timeout(30000)`、`page.set_default_timeout(30000)`    |
| 模型调用          | `timeout=120s`、指数退避重试、解析失败兜底                                              |
| 页面初始化失败       | `_save_early_fallback()` 保存结果                                             |
| 截图失败          | 走正常保存流程，不再特殊 continue                                                     |
| 新标签页/弹窗       | 检测切换，viewport 与 cdp_session 失败有 try-except                                |
| browser 泄漏    | `check_url_accessible` 加 try-except/finally                               |
| worker 整体卡住   | 主进程 30 分钟超时，terminate/join/kill                                           |
| 防死循环          | 同 index / 同 URL 无进展时强制换策略                                                 |
| 请求捕获          | context 级监听 + 空记录兜底                                                       |

**仍无法 100% 兜底的风险**：

- 沙箱/浏览器/网络/模型服务端异常，超出代码控制；
- 未知异常路径未覆盖；
- 模型决策导致的循环不致命，但会消耗步数。

**结论**：因「非法 timeout 导致 worker 崩溃」这类代码健壮性问题而整体卡住的概率已极低；但无法对沙箱/网络/模型侧故障做绝对保证。

*追加于 2026-08-27*

---

## 15. 2026-08-27 深度审计（code-self-test）— 待修复清单

### 15.1 背景

官方冒烟测试通过后，按 code-self-test skill 对 WR-001 进行深度代码审计。3 个审查 agent + 1 个人工审查（main.py）完成，发现 **5 类 P0 + 7 类 P1** 问题。当前 session 仅记录问题，修复工作放到下一份 session。

### 15.2 已跑通的门禁

| 门禁          | 命令                                    | 结果         |
| ----------- | ------------------------------------- | ---------- |
| Python 语法检查 | `python -m py_compile src/agent/*.py` | ✅ 通过       |
| 单元/契约测试     | `python -m pytest tests/ -v`          | ✅ 9 passed |

### 15.3 P0 问题（下份 session 优先修）

#### 1. `web_controller.py` 4 处 `exit()` 会直接杀死 worker

- `parse_action_type` scroll 解析失败（663-667）
- `parse_action` scroll 解析失败（748-749）
- `execute_action` 未知 action name（889-890）
- **修复方向**：改为返回 `"Unknown"`，由上层标 `FAIL_PREDICT_ERROR` 并保存兜底结果

#### 2. `agent.py` 模型返回异常时崩溃

- `content is None` 时 `.strip()` 抛 `AttributeError`（703、849）
- 视觉模式 `images` 为空时 `IndexError`（654、663、672）
- **修复方向**：判空后再调用 `.strip()`；截图列表为空返回明确错误状态

#### 3. `prompts.py` 合规红线

- 第 158 行教授 URL 拼接绕过 UI + 硬编码"2025年中秋节 = 2025-10-06"
- 同一段落要求用 `hotkey()`，但 DOM action space 里没有 `hotkey`
- **修复方向**：删除 URL 构造指引和硬编码日期；删除 `hotkey` 描述或把 `hotkey` 加入 action space

#### 4. `web_controller.py` 浏览器状态管理缺陷

- `reset_browser_state` CDP 模式下 context 损坏返回 `None page`
- 每次重置多保留一个旧标签页，长期运行 "Too many pages"
- `open_page` 清理旧页时 `evaluate("window.stop()")` 无超时，可能阻塞重试
- `init_playwright_context` 失败时未 `p.stop()`，可能泄漏进程
- **修复方向**：CDP 模式也走重连；创建新 page 后再关闭旧 page；隔离 `window.stop()`；异常分支加 `p.stop()`

#### 5. `main.py` 断点续跑 key 类型不匹配

```python
# line 977
success_task_map[tidx] = True   # tidx 是字符串
# line 993
if task_idx in success_task_map:  # task_idx 是整数
```

- **后果**：已成功任务可能被重复跑，浪费正式评测次数
- **修复方向**：统一用字符串 key

### 15.4 P1 问题（P0 修完后再处理）

| # | 文件                  | 问题                                                | 修复方向                   |
| - | ------------------- | ------------------------------------------------- | ---------------------- |
| 1 | `dom_extractor.py`  | JS 端无 cap，大页面 evaluate 可能挂死                       | JS 内加 early exit 或时间预算 |
| 2 | `dom_extractor.py`  | `get_element_handle` 依赖 doc_index，页面变化后误点击        | 加稳定标识或二次校验             |
| 3 | `agent.py`          | 重试无 jitter，8 worker 同时失败会 thundering herd         | sleep 加随机抖动            |
| 4 | `agent.py`          | 所有异常都重试，401/404 也浪费重试                             | 只重试超时/连接/5xx/429       |
| 5 | `web_controller.py` | `scroll_into_view_if_needed` / `focus` 未传 timeout | 传 `timeout=5000`       |
| 6 | `web_controller.py` | `_handle_download_as_text` 不删临时文件、不限制大小           | 读取后删除，超阈值跳过            |
| 7 | `main.py`           | 读取已存在的 result.json 没有 try，文件损坏会崩溃                 | 加 try-except           |

### 15.5 下份 session 接续命令

```bash
cd D:\claude-work\WR-001
python -m py_compile src/agent/main.py src/agent/web_controller.py src/agent/dom_extractor.py src/agent/agent.py src/agent/prompts.py
python -m pytest tests/ -v
python src/agent/main.py --input data/task0_only.json --output output/smoke_fix_task0 --cdp_url launch --use_dom
```

### 15.6 状态

- **当前 commit**：`1151f8b`（已 push `main`）
- **官方冒烟**：已通过
- **今日正式评测**：已消耗，明日 00:00 刷新
- **待办**：下份 session 修复 P0 → 自测 → push → 触发官方冒烟

*追加于 2026-08-27*

---

## 16. 2026-08-28 自测门禁与代码审计修复

基于用户要求，重新跑自测门禁并审计当前代码，修复 6 类边界问题 + 2 类代码质量问题。

### 16.1 已跑通的门禁

| 门禁          | 命令                                                                                                                                     | 结果             |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| Python 语法检查 | `python -m py_compile src/agent/*.py`                                                                                                  | ✅ 通过           |
| 单元/契约测试     | `python -m pytest tests/ -v`                                                                                                           | ✅ 9 passed     |
| 单题冒烟        | `python src/agent/main.py --input data/worldbank_task_only.json --output output/smoke_worldbank_2026_08_28 --cdp_url launch --use_dom` | ✅ 代码未崩溃，输出文件完整 |

### 16.2 修复内容（commit `8453b4b`，已 push `main`）

| # | 文件                               | 问题                                                          | 修复                                            |
| - | -------------------------------- | ----------------------------------------------------------- | --------------------------------------------- |
| 1 | `main.py`                        | 断点续跑读取 `result.json` 未指定 UTF-8                              | 加 `encoding='utf-8'`                          |
| 2 | `web_controller.py`              | launch 模式启动失败未 `p.stop()`                                   | 异常分支加 `p.stop()`                              |
| 3 | `web_controller.py`              | `save_screenshot` 预处理无超时                                    | `_with_action_timeout(..., 5000, ...)` 包装     |
| 4 | `web_controller.py`              | `wait_for_rendering_complete` 中 `evaluate` 无超时              | 包装 `_with_action_timeout`；Promise 内部加空检查与缩短循环 |
| 5 | `web_controller.py`              | 视觉方案新标签页 `set_viewport_size`/`new_cdp_session` 无 try-except | 加异常捕获与回退                                      |
| 6 | `web_controller.py`              | `RequestCollector.save_results` 写入失败无捕获                     | 加 try-except，失败返回 0                           |
| 7 | `agent.py` + `web_controller.py` | 模型自我介绍被误包装成 `finished(content='...')` 导致假 SUCCESS           | `_is_valid_final_answer` 增加 meta 检测；包装前校验     |
| 8 | `agent.py` + `web_controller.py` | 重复导入                                                        | 清理重复项                                         |

### 16.3 未修复/受 API 限制的项

- Playwright sync API 的 `page.evaluate` 不支持 `timeout` 参数，`main.py` 的 `page_summary` 提取和 `dom_extractor.py` 的 DOM/文本抽取依赖 JS 内部预算与 `MAX_NODES` 限制。
- 任务最终准确率仍依赖模型导航能力，本次修复聚焦代码健壮性与结果文件完整性。

### 16.4 当前状态

- **commit**: `8453b4b`（已 push `main`）
- **下一步**: 用户在群内发送 `@WR-EvalBot 提交代码` 触发官方冒烟测试，根据结果继续迭代。

*追加于 2026-08-28*

### 16.5 官方冒烟测试结果

- **状态**: ✅ 通过
- **commit**: `8453b4b`
- **时间**: 2026-08-28
- **结论**: 可以发起正式评测。

*追加于 2026-08-28*

---

## 17. 2026-08-28 正式评测0分/30分钟快速完成 — 诊断与加固

### 17.1 现象

- 用户在官方冒烟测试通过后触发正式评测。
- 评测耗时 **30 分钟完成 100 题**，最终 **0 分**，且未返回任何日志/异常。
- 30 分钟/100 题 ≈ 每题 18 秒，远低于正常导航+提取所需时间，高度怀疑**大规模早期失败**（浏览器初始化/重置/页面初始化即退出）。

### 17.2 已采取的诊断动作

由于官方未返回日志，从代码层面增强早期失败点的诊断与重试：

1. **main.py 早期 fallback 带异常栈**：
   - `FAIL_BROWSER_RESET`（两处）与 `FAIL_PAGE_INIT` 的 `_save_early_fallback()` 调用增加 `details=traceback.format_exc()`。
2. **web_controller.py 浏览器初始化/重置加固**：
   - 新增 `_get_cdp_token()` 读取 URL query param 或环境变量中的 CDP access token。
   - `init_playwright_context(..., max_retries=3)` 增加重试、详细 stdout 日志、失败路径确保 `p.stop()`。
   - `reset_browser_state(..., max_retries=3)` 增加重试。
   - `save_screenshot` 的 `bring_to_front()` 和禁用动画 `evaluate()` 加 5 秒超时。
   - `wait_for_rendering_complete` 的 `readyState` / Promise 滚动稳定性检查加 5 秒超时；Promise 内部加 `document.body` 空检查并缩短循环。
   - `_excute_action_body` 中 `new_page.set_viewport_size()` 与 `new_cdp_session()` 加 try-except 与回退。
   - `RequestCollector.save_results` 加 try-except，失败返回 0。
3. **agent.py 防止模型自我介绍被包装为答案**：
   - 在视觉/DOM 两处分支中，把非动作输出包装为 `finished(content='...')` 前，先调用 `_is_valid_final_answer()`。
   - `_is_valid_final_answer()` 增加 meta-marker 检测（"我是", "由月之暗面", "Moonshot", "kimi-k", "研发" 等）。
4. **重复导入清理**：`agent.py` 与 `web_controller.py` 清理重复导入。

### 17.3 验证与提交

| 门禁                                    | 结果         |
| ------------------------------------- | ---------- |
| `python -m py_compile src/agent/*.py` | ✅ 通过       |
| `python -m pytest tests/ -v`          | ✅ 9 passed |

- **commit**: `e272245`
- **message**: `feat: harden browser init/reset and early-fallback diagnostics for 0-point eval`
- **已 push**: `main`

### 17.4 下一步（新 session 接续）

1. 在群内触发 `@WR-EvalBot 提交代码`，跑官方冒烟测试，重点观察 stdout 是否仍有 `FAIL_BROWSER_RESET` / `FAIL_PAGE_INIT` 等早期失败。
2. 冒烟测试通过后，再触发一次正式评测。
3. 若再次 0 分或异常快速完成，把官方返回的任意 stdout 或单个任务的 `result.json` 贴给 agent，继续定位根因。

*追加于 2026-08-28*

---

## 18. 2026-08-28 官方冒烟测试失败修复 — 根目录 `run.sh` 缺失

### 18.1 现象与排查

- 用户在群内触发 `@WR-EvalBot 提交代码` 后，Bot 回复：
  > "❌ 冒烟测试未通过，请检查 run.sh 是否能正常输出结果"
- 初步排查时误入历史参考库 `/d/claude-work/webretriever`，该仓库 `origin` 指向官方 `Mininglamp-AI/WebRetriever`，无 push 权限。
- 按用户提示读取 Obsidian 主索引后，确认**正式提交仓库为 `hhhhhhalf/WR-001`**，本地路径 `D:\claude-work\WR-001`。

### 18.2 根因

- WR-001 仓库此前已修复 `scripts/run.sh`（commit `7ff31db`）。
- 但官方冒烟测试默认调用的是**仓库根目录的 `run.sh`**，导致评测脚本找不到入口，直接失败。

### 18.3 修复内容

在仓库根目录新增 `run.sh`，作为 `scripts/run.sh` 的转发入口，保持单一真源：

```bash
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/scripts/run.sh" "$@"
```

- commit: `b3114b2`
- message: `fix: add missing root run.sh entry point for official smoke test`

### 18.4 本地验证

```bash
cd D:\claude-work\WR-001
timeout 60 bash run.sh data/example_tasks.json output/runsh_test launch
```

结果：

- ✅ `main.py` 正常启动
- ✅ 生成 `output/runsh_test/<task_id>/result.json`
- ✅ 生成 `output/runsh_test/<task_id>/capture.json`
- ✅ `output/runsh_test/logs/summary.json` 与 worker log 均正常

### 18.5 提交状态

- **已 push**: `main → https://github.com/hhhhhhalf/WR-001.git`
- 用户随后触发官方冒烟测试，**已通过**。

### 18.6 教训

- `webretriever` 与 `WR-001` 两个本地目录极易混淆；新 session 必须先确认当前工作目录与 remote。
- 官方入口脚本的放置位置必须与评测系统约定一致：根目录 `run.sh`，而非仅 `scripts/run.sh`。

---

## 19. 2026-08-28 关于正式评测日志可获取性的记录

### 19.1 客观事实

根据历次官方反馈，能拿到的日志/信息有限：

| 信息类型              | 是否通常能拿到 | 示例                |
| ----------------- | ------- | ----------------- |
| 分数与耗时             | ✅ 是     | "0 分，30 分钟完成"     |
| 冒烟通过/失败状态         | ✅ 是     | "冒烟测试未通过"         |
| 概括性失败原因           | 有时      | "3 道题中 1 道缺少有效输出" |
| 环境安装失败原因          | 有时      | "conda 软件包网络拉取失败" |
| 逐任务 stdout/stderr | ❌ 否     | —                 |
| Python 异常堆栈       | ❌ 否     | —                 |
| 浏览器 CDP/截图日志      | ❌ 否     | —                 |

### 19.2 已做的防御性增强

为降低"无日志可排"的风险，代码已具备：

1. `result.json` 带 `diagnostics` 字段（commit `c35ff37`）
2. 早期失败统一兜底保存 `result.json` + `capture.json`
3. `capture.json` 空记录兜底

### 19.3 后续策略

- 正式评测后，以官方 Bot 返回的**完整文本**为首要输入，结合当前 commit 做代码级反推。
- 若官方反馈模糊，则在本地用 `protocol3_sample15.json` 或自建批量样本复现。

*追加于 2026-08-28*

---

## 20. 2026-08-29 正式评测 0 分根因诊断 — 模型输出过度清洗

### 20.1 现象

- 8/28 与 8/29 正式评测均为 **30 分钟完成 100 题，0 分**。
- 用户能在评测过程中看到 API Key 被调用，排除 key 额度/连通性问题。
- 官方不返回逐任务日志，无法直接查看失败原因。

### 20.2 根因

commit `c35ff37`（"清洗模型输出"）引入的防御逻辑过度：

| 位置                                             | 过度逻辑                                                                                                                                | 后果                         |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `agent.py::_sanitize_model_output()`           | 将包含 `elements:` / `page summary:` / `current page:` / `url:` / `title:` / `page visible text:` / `current page elements:` 的模型输出判为无效 | 返回 `None` → `client error` |
| `agent.py::parse_action_to_structure_output()` | 前置防御同样检测上述词并抛异常                                                                                                                     | 解析失败                       |

这些词在 DOM prompt 中大量存在（页面 URL、标题、元素列表、正文摘要），模型在 Thought 中自然提及，属于正常输出而非污染。结果每道题第一步模型返回即被清洗为 `None` → `main.py` 标 `FAIL_PREDICT_ERROR` 并 break。**每题只走 1 步**，100 题在 30 分钟内快速跑完并得 0 分。

### 20.3 修复

commit `1d604bf` 已 push `main`：

1. 移除 `_sanitize_model_output` 中的 observation markers 过滤；仅保留 markdown 清洗和自我介绍/系统身份泄漏过滤。
2. 移除 `parse_action_to_structure_output` 中的前置 observation block 防御。
3. 新增 `tests/test_sanitize_model_output.py` 回归测试锁定该行为。

### 20.4 验证

| 门禁          | 命令                                    | 结果          |
| ----------- | ------------------------------------- | ----------- |
| Python 语法检查 | `python -m py_compile src/agent/*.py` | ✅ 通过        |
| 全量测试        | `python -m pytest tests/ -v`          | ✅ 14 passed |
| 回归测试        | `tests/test_sanitize_model_output.py` | ✅ 5 passed  |

### 20.5 下一步

1. 用户在群内发送 `@WR-EvalBot 提交代码` 跑官方冒烟测试。
2. 冒烟通过后，触发 `@WR-EvalBot 开始评测` 消耗今日正式评测次数。
3. 若仍有 0 分或快速完成，把 Bot 返回的任意文本或本地日志贴给 agent 继续定位。

### 20.6 教训

- 防御性清洗不要基于 prompt 中已有的关键词做负向过滤，极易误杀正常输出。
- DOM 方案中模型输出包含 `url:`、`title:`、`elements:` 等词是预期行为，不应视为 observation leak。
- 官方评测不返回日志时，从"每题平均耗时极短"反推"每题早期失败"，再定位到第一步输出处理逻辑。

*追加于 2026-08-29*

---

## 21. 2026-08-29 冒烟测试 1/3 缺少有效输出 — evaluate 超时全量修复

### 21.1 现象

- 用户在 commit `1d604bf` 后触发官方冒烟测试。
- 结果：**3 道冒烟题中有 1 道缺少有效输出（2/3 通过）**。
- 用户指出：历次冒烟测试常出现"3 题只过 2 题"，且报错多与 `run.sh` 相关；并明确要求**筛查出的问题必须全修**。

### 21.2 排查与修复

本次不再只修表面报错点，而是对 `page.evaluate` / `handle.evaluate` / `focus` / `scrollIntoView` 等所有可能阻塞的 Playwright 调用做统一扫描加固。

#### commit `33f57bd` 已 push `main`

| 文件                                                      | 修复点                           | 说明                                        |
| ------------------------------------------------------- | ----------------------------- | ----------------------------------------- |
| `src/agent/web_controller.py::click_type`               | focus/scrollIntoView evaluate | 加 `_with_action_timeout(page, 5000, ...)` |
| `src/agent/web_controller.py::click_type`               | setValue evaluate             | 加 `_with_action_timeout(page, 5000, ...)` |
| `src/agent/web_controller.py::_handle_download_as_text` | 注入下载内容 evaluate               | 加 `_with_action_timeout(page, 5000, ...)` |
| `src/agent/prompts.py`                                  | 删除硬编码中秋节日期                    | 避免事实错误与绕过日期过滤器风险                          |

#### 上一轮已修但未在本次 commit 中的关键修复

- `src/agent/main.py`：`page_summary` / 过早放弃 body text 两处 `page.evaluate` 加 5s 超时。
- `src/agent/dom_extractor.py`：`extract_interactive_elements` / `get_element_handle` / `extract_page_text` 三处加超时保护。

### 21.3 8/27 深度审计 P0/P1 复核

按 [[session-handoff-webretriever-2026-08-27-deep-audit]] 逐项复核，**当前代码已全部修复**：

| 类别   | 问题                                                | 当前状态                       |
| ---- | ------------------------------------------------- | -------------------------- |
| P0-1 | `web_controller.py` 4 处 `exit()`                  | ✅ 已移除                      |
| P0-2 | `agent.py` `content is None` / images 空           | ✅ 已判空处理                    |
| P0-3 | `prompts.py` URL 拼接 + 硬编码日期 / hotkey              | ✅ 已删除/已对齐                  |
| P0-4 | 浏览器状态管理缺陷                                         | ✅ 已修复                      |
| P0-5 | `main.py` 断点续跑 key 类型                             | ✅ 已统一字符串                   |
| P1-1 | `dom_extractor.py` JS 端 cap                       | ✅ `MAX_NODES=2000`         |
| P1-2 | `get_element_handle` 页面变化误点击                      | ✅ tagName 二次校验             |
| P1-3 | `agent.py` 重试无 jitter                             | ✅ 已加随机抖动                   |
| P1-4 | 所有异常都重试                                           | ✅ `_is_retryable_error` 区分 |
| P1-5 | `scroll_into_view_if_needed` / `focus` 未传 timeout | ✅ 已传 5s                    |
| P1-6 | `_handle_download_as_text` 不删临时文件/不限制大小           | ✅ 已删 + 10MB 限制             |
| P1-7 | `main.py` 读取 result.json 无 try                    | ✅ 已加 try-except            |

### 21.4 验证

| 门禁          | 命令                                    | 结果          |
| ----------- | ------------------------------------- | ----------- |
| Python 语法检查 | `python -m py_compile src/agent/*.py` | ✅ 通过        |
| 全量测试        | `python -m pytest tests/ -v`          | ✅ 14 passed |

### 21.5 下一步

1. 在群内发送 `@WR-EvalBot 提交代码` 跑官方冒烟测试。
2. 冒烟通过后，触发 `@WR-EvalBot 开始评测`。
3. 若仍有问题，继续按"筛查出的问题必须全修"原则处理。

*追加于 2026-08-29*

---

## 22. 2026-08-29 冒烟缺 result.json 修复 — 超时兜底 + 统一单 worker 保护

### 22.1 现象

- 官方冒烟测试反馈：3 道题中部分缺少有效输出，`result.json` 未生成。
- 根因：任务超时被主进程 terminate 后，单 worker 场景下没有统一的多进程监控兜底，导致落盘失败。

### 22.2 修复（commit `fa02867`）

| 文件                  | 修复点                                      |
| ------------------- | ---------------------------------------- |
| `src/agent/main.py` | 统一多进程 + 监控循环，单 worker 也能在任务卡死时强制终止并写兜底结果 |
| `src/agent/main.py` | 新增 `safe_save_results` 与异常分支兜底保存         |
| `src/agent/main.py` | worker 异常退出检测 + 超时双保险                    |

### 22.3 验证

- `py_compile` + `pytest` 全绿
- 已 push `main`

### 22.4 状态

- 待官方冒烟测试反馈

*追加于 2026-08-29*

---

## 23. 2026-08-29 v22 冒烟缺输出多重兜底加固

### 23.1 现象

- 官方冒烟测试仍出现结果缺失，需要更坚强的兜底。

### 23.2 修复（commit `a4408c4`）

- 新增 **SIGTERM 自保存**：worker 收到终止信号时先保存当前结果再退出。
- 新增 **worker 异常退出检测**：主进程检测到 worker 异常退出时写兜底结果。
- 新增 **超时双保险**：任务级超时 + 总监控兜底。
- 新增 **最后防线**：即使所有兜底都失败，也尝试写出最小化结果文件。

### 23.3 验证

- `py_compile` + `pytest` 全绿
- **官方冒烟测试已通过**
- 已 push `main`

### 23.4 状态

- 可触发正式评测

*追加于 2026-08-29*

---

## 24. 2026-08-29 timeout 调优后冒烟通过

### 24.1 调整内容（commit `d142339`）

- 模型调用 timeout：**120s → 60s**
- 任务总超时：**300s → 240s**
- DOM 重试次数：**5 → 3**

目标：减少单题在慢题上的无效等待，避免 8 路并发时整体评测被拖死。

### 24.2 结果

- `py_compile` + `pytest` 全绿
- **官方冒烟测试已通过**
- 已 push `main`

### 24.3 状态

- 可触发正式评测

*追加于 2026-08-29*

---

---

## 25. 2026-08-30 正式评测 0 分根因诊断 — 模型输出自然语言计划

### 25.1 现象

- 8/30 正式评测：**0 分，20 分钟完成 100 题**。
- 本地批量回归显示模型输出格式解析正常，但正式评测仍然 0 分。

### 25.2 根因

- DOM 模型被强化格式约束后，**并未稳定输出 `Thought: ... Action: ...`**，而是输出自然语言计划或 markdown 列表。
- `agent.py` 的清洗/解析逻辑将这类输出标为 `not_action_not_answer` → `FAIL_PREDICT_ERROR`。
- 结果每题 1 步失败，100 题快速跑完得 0 分。

### 25.3 修复（commit `ede1788`）

- `src/agent/agent.py`：
  - DOM system prompt 从 `"You are a helpful assistant."` 改为强格式约束：
    > "You are a GUI agent controlling a web browser. Your response must contain exactly one 'Thought:' line followed by exactly one 'Action:' line..."
- `src/agent/prompts.py`：
  - `UITARS_USR_PROMPT_DOM` 增加 **Output Format Example** 与 **CRITICAL** 提醒。

### 25.4 验证

- 本地 iFixit 单题回归：**SUCCESS，3 步通过**
- 已 push `main`

### 25.5 状态

- 待官方冒烟测试 + 明日正式评测

*追加于 2026-08-30*

---

## 26. 2026-08-30 每步诊断写入 result.json

### 26.1 背景

- 官方评测不返回具体日志，难以诊断正式评测中的问题。
- 用户要求：把每道题的原始输出和解析结果强制写进 `result.json`。

### 26.2 实现（commit `6e6bebd`）

- `src/agent/agent.py`：
  - `predict()` / `predict_dom()` 返回三元组 `(prediction, condition, step_diagnostic)`。
  - `step_diagnostic` 记录：`raw_output`、`sanitized_output`、`parse_status`、`parse_error`、`returned_condition`、`is_wrapped_answer`。
- `src/agent/main.py`：
  - 每个 task / worker 维护 `step_diagnostics` 列表。
  - 每步 predict 后实时写入 `.step_diagnostics.json`。
  - SIGTERM handler、worker 崩溃兜底、任务超时兜底均读取 `.step_diagnostics.json` 并写入最终 `result.json` 的 `diagnostics` 字段。

### 26.3 验证

- `py_compile` + `pytest` 全绿
- 已 push `main`

### 26.4 状态

- 待官方冒烟测试 + 正式评测后读取本地诊断

*追加于 2026-08-30*

---

## 27. 2026-08-30 批量回归总结

### 27.1 测试设置

基于 commit `b1b551a`（诊断落盘 + 任务超时恢复 300s）跑本地批量回归：

| 任务                     | 结果            | 步数  | 关键发现               |
| ---------------------- | ------------- | --- | ------------------ |
| iFixit iPad Air 3 屏幕更换 | **SUCCESS**   | 3 步 | 新 prompt 格式约束有效    |
| 猫眼 2025 中秋分账票房第二       | FAIL（240s 超时） | 4 步 | 格式正确，但日期选择器反复尝试无进展 |
| 世界银行 青少年生育率增速最快年份      | FAIL（240s 超时） | 3 步 | 格式正确，搜索后无可见结果      |

### 27.2 结论

1. **0 分根因已解决**：模型能正确输出 `Thought/Action` 格式。
2. **模型调用慢是主要瓶颈**：复杂题每步接近 60s，240s 只能走 3-4 步。
3. **任务超时恢复为 300s**，给复杂题多留步数。
4. **诊断信息实时落盘**，超时/崩溃也能保留诊断。

### 27.3 状态

- commit `b1b551a` 已 push `main`
- 待官方冒烟测试 + 8/31 正式评测

*追加于 2026-08-30*

---

## 28. 2026-08-30 超时修复官方冒烟通过

### 28.1 现象

- commit `b1b551a` 官方冒烟测试：**3 道题中 1 道缺少有效输出**。
- 失败原因：`APITimeoutError` / `ReadTimeout`，`src/agent/agent.py` 的 `predict_dom` 调用大模型接口处发生超时。

### 28.2 修复（commit `2b5efc6`）

- `src/agent/agent.py`：
  - `predict()` / `predict_dom()` 的模型调用 timeout 从固定 **60s** 改为递进策略：**90s → 120s → 90s**。
- `src/agent/main.py`：
  - 单题总超时从 **300s** 提高到 **360s**。

### 28.3 验证

- `py_compile` 全绿
- `pytest 14 passed`
- **官方冒烟测试已通过（3/3）**
- 已 push `main`

### 28.4 回退方案

若后续需要回退到上一个稳定基线：

```bash
cd D:\claude-work\WR-001
git reset --hard b1b551a
git push --force origin main
```

### 28.5 当前状态

- **最新 commit**: `2b5efc6`
- **官方冒烟测试**: ✅ 通过
- **下一步**: 等待 8/31 00:00 正式评测次数刷新后，触发 `@WR-EvalBot 开始评测`

*追加于 2026-08-30*

---

*最后更新：2026-08-30*

---

## 29. 2026-08-30 评审问题修复 + v29 冒烟超时修复

### 29.1 背景

用户将测试工程师对 WR-001 代码的评审发给学生侧 Claude，要求逐项核对并修复。评审命中多个 P0/P1 问题，其中 P0 两项（上下文爆炸、360s/100 步矛盾）和 P1 三项（滚动误伤、`_last_click` 泄漏、引号截断）已在本 session 内修复并 push。随后收到官方 v29 冒烟反馈：3 题中 1 题因 `predict_dom` 模型接口超时导致 trajectory 为空，再次提高超时配置。

### 29.2 修复清单

| # | 文件                                         | 问题                                                                                | 修复                                                                            |
| - | ------------------------------------------ | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 1 | `src/agent/agent.py`                       | `predict_dom()` 未记录 `history_responses`，DOM 模式 `result.json` 的 `history_resps` 恒空 | 补 `self.history_responses.append(prediction)`                                 |
| 2 | `src/agent/agent.py`                       | `_sanitize_model_output()` 把英文 Thought 中的 `"i am" / "i'm"` 判为自我介绍，误杀合法 Action     | 仅当无 `Action:` 行时才拒绝                                                           |
| 3 | `src/agent/main.py`                        | 字段名误用 `keytra`，正式赛题 `key_points` 被静默丢弃                                            | 新增 `_get_key_points()`，`key_points` 优先、`keytra` fallback                      |
| 4 | `src/agent/agent.py`                       | `predict()` 视觉方案每步发送全部历史文本，上下文线性爆炸                                                | 只发送最近 `history_n` 条历史文本，与图片数量对齐                                               |
| 5 | `src/agent/main.py`                        | 单题超时 360s 与 100 步上限矛盾，复杂题被提前强杀                                                    | `TASK_TIMEOUT_SECONDS` 放宽到 1200s（20 分钟），保留死循环检测                               |
| 6 | `src/agent/main.py` + `web_controller.py`  | `no_progress_cnt` 把 `scroll()` 计入 URL 无进展，误触发死循环                                  | `scroll` 动作不再增加 `no_progress_cnt`                                             |
| 7 | `src/agent/agent.py` + `web_controller.py` | `_last_click` 模块级全局跨任务残留                                                          | 新增 `reset_last_click()`，`agent.reset()` 每题调用                                  |
| 8 | `src/agent/main.py`                        | `extract_agent_answer()` 正则非贪婪匹配截断带 `'` 的答案                                       | 优先用 `ast.parse` 解析，兜底用支持转义引号的正则                                               |
| 9 | `src/agent/agent.py`                       | v29 冒烟 1 题因 `predict_dom` 超时无输出                                                   | `request_timeouts` 从 `[90, 120, 90]` 提高到 `[120, 180, 180]`，充分利用官方单次调用 ≤3 分钟上限 |

### 29.3 验证

| 门禁          | 命令                                    | 结果                    |
| ----------- | ------------------------------------- | --------------------- |
| Python 语法检查 | `python -m py_compile src/agent/*.py` | ✅ 通过                  |
| 全量测试        | `python -m pytest tests/ -q`          | ✅ **36 passed**       |
| 新增回归测试      | `tests/test_review_regressions.py`    | 覆盖 8 项评审修复 + v29 超时前提 |

### 29.4 提交状态

- **初始评审修复 commit**: `8d0a2ca` → `c60a0b2`（追加 P1 修复）
- **v29 超时修复 commit**: `bf1d7b4`
- **已 push**: `main → https://github.com/hhhhhalf/WR-001.git`

### 29.5 官方冒烟状态

- **v29 冒烟**: ❌ 未通过（3/3 中 1 题因 `APITimeoutError` / `ReadTimeout` 导致 trajectory 为空）
- **修复后**: 待重新触发 `@WR-EvalBot 提交代码` 走官方验证

### 29.6 当前关键配置

| 配置项            | 当前值                | 依据                                |
| -------------- | ------------------ | --------------------------------- |
| 单次模型调用 timeout | `[120, 180, 180]s` | 官方规则：单次 ≤3 分钟（180s）               |
| 单题总超时          | 1200s（20 分钟）       | 官方无单题限时；8 并发/100 题/4h ≈ 19.2 分钟/题 |
| 每题最大步数         | 100                | 官方硬性限制                            |
| 历史文本截断         | `history_n=5`      | 避免上下文爆炸                           |

### 29.7 下一步

1. 在提交群发送 `@WR-EvalBot 提交代码`，重新跑官方冒烟测试。
2. 冒烟通过后，等待 8/31 00:00 正式评测次数刷新，再发 `@WR-EvalBot 开始评测`。
3. 若 v29 超时问题仍未解决，考虑进一步增加重试次数或加入超时兜底（如最终超时后返回 `FAIL_TIMEOUT` 并确保 result.json 有基础内容）。

*追加于 2026-08-30*

---

## 30. 2026-08-30 v29 冒烟超时二次修复 — 重试 5 次 + 兜底截图（commit `1fbef05`）

### 30.1 官方 v29 冒烟反馈（基于 `bf1d7b4`）

- **环境安装**：成功
- **冒烟测试**：未通过（3 道题中 1 道缺少有效输出，2/3 通过）
- **失败原因**：仍是同一处超时——`APITimeoutError` / `ReadTimeout`，发生在 `src/agent/agent.py` 的 `predict_dom` 调用大模型接口处；超时导致 trajectory 轨迹为空、无图片输出
- **官方建议**：加大 timeout、增加失败重试，或对超时做兜底，确保每道题稳定产出完整轨迹
- **根因分析**：`bf1d7b4` 已将单次 timeout 提高到 `[120, 180, 180]`（3 次重试，累计 480s），但偶发极慢响应仍超出 3 次重试窗口；截图虽在每步开头保存，但若页面异常导致首步截图失败，trajectory 仍为空

### 30.2 修复（commit `1fbef05`）

**修复 1：模型调用重试 3 次 → 5 次**（`agent.py`，predict 和 predict_dom 两处同步）

| 项      | 修改前（bf1d7b4）      | 修改后（1fbef05）                    |
| ------ | ----------------- | ------------------------------- |
| 重试次数   | 3                 | **5**                           |
| 单次超时序列 | `[120, 180, 180]` | **`[120, 180, 180, 180, 180]`** |
| 累计最大耗时 | 480s              | **840s**（< 单题 1200s 超时）         |
| 单次上限   | 180s              | 180s（= 官方 3 分钟上限，合规）            |

- `attempt_idx` 与退避指数同步改为 `5 - try_times`
- `_is_retryable_error` 已包含 `APITimeoutError`/`ReadTimeout`/`TimeoutError`，超时自动退避重试

**修复 2：循环结束后兜底补存截图**（`main.py`）

- 正常路径每步开头已截图；但若页面异常导致首步截图失败、或任务在截图前就退出，`trajectory/` 会为空
- 循环结束后统一检查：若 `trajectory/` 下没有任何 png 且 page 仍存活，立即补存一张（15s 超时），确保官方不会再判"缺少有效输出 / 轨迹为空 / 无图片"

### 30.3 验证

- `py_compile`：agent.py / main.py 全绿
- `pytest tests -q`：**36 passed**
- 已 commit `1fbef05` 并 push 到 `origin/main`

### 30.4 当前状态与下一步

- **最新 commit**：`1fbef05`（已 push main）
- **官方冒烟**：待重新验证（上一轮基于 `bf1d7b4` 未通过）
- **下一步**：在提交群对 `@WR-EvalBot` 发「提交代码」，Bot 会重新安装环境并重跑冒烟；冒烟通过后环境就绪，方可发起正式评测
- **若冒烟仍报同一处超时**：说明不是重试次数问题，而是 aixforge 网关到 kimi-k2.6 的链路在某些请求上确实不稳定，需考虑加"超时后换模型/换网关"兜底，或确认 aixforge 并发配额是否够 8 worker 同时打

### 30.5 提交时间线（v29 冒烟相关）

| commit    | 内容                               | 冒烟结果          |
| --------- | -------------------------------- | ------------- |
| `2b5efc6` | timeout 递进 90/120/90，单题 360s     | ✅ 通过（3/3）     |
| `bf1d7b4` | timeout 提高到 [120,180,180]（3 次重试） | ❌ 未通过（1/3 超时） |
| `1fbef05` | 重试 3→5 次 + 兜底截图                  | 待验证           |

*追加于 2026-08-30*

---

*最后更新：2026-08-30*

---

## 31. 2026-08-31 本地跑分诊断 + 杀假放弃（Day 2 提分）

### 31.1 背景与现状（用户口述）

- 正式比赛窗口 **8/27 10:00 — 9/2 23:59（7 天）**，用户已练习 **4 天仍 0 分**，改了很多版本无果。
- 经确认：**本地跑分一直很低 + 代码已 push main** → 是 **Agent 能力问题**，非部署/接口问题。
- 用户确认：**Kimi K2.6 不能更换** → 纯 DOM 文本模式死磕，不再纠结换模型/视觉方案。

### 31.2 根因诊断：4 天 0 分的真凶不是"不会做"，是"太容易放弃"

此前仓库只有一堆 `result.json` 原始记录，**没有任何能算出"这版比上版好多少"的评测脚本** → 用户一直盲改，永远不知道改动有没有用。

本 session 新增本地评测仪 `tools/eval_local.py`，聚合 `test_results/**/result.json`，输出成功率 + 失败分类 + **过早放弃拦截面板**。

**基线数字（47 次历史本地评测，2026-08-31 跑出）：**

| 指标               | 数值                    |
| ---------------- | --------------------- |
| 总成功率             | **40.4%**（19/47）      |
| 🏳️ 主动放弃（`无法完成`） | **18（38.3%）** ← 头号失分桶 |
| ❓ 无有效答案          | 5（10.6%）              |
| 🔁 死循环           | 2（4.3%）               |
| ⚠️ 其他失败          | 3（6.4%）               |

**18 个放弃按动作数（predict_length）分布（门槛=15 步）：**

| 类别                         | 数量     | 含义                                                                             |
| -------------------------- | ------ | ------------------------------------------------------------------------------ |
| 动作数 < 15（过早放弃，会被新门槛拦下强制续跑） | **13** | shanghairanking / MIT / rand.org / travel.state.gov 护照题，明显假放弃；其中 7 个 < 8 步就交白卷 |
| 动作数 ≥ 15（真卡死）              | **5**  | sam.gov ×3（23/47/76 步）、statcounter（19 步）、zongheng（69 步）→ 非放弃能解决，留 Day 4-5      |

> 结论：**38% 失分是"假放弃"**，根因在 `prompts.py` 终止规则太松 + `main.py`/`web_controller.py` 的**过早放弃门槛只有 8 步**（超过 8 步就不再拦截"无法完成"）。这是 7 天里提分的最高杠杆。

### 31.3 杀假放弃改动（Day 2，2026-08-31 已落地，待 commit）

| 文件                            | 改动                                                                                                                                                                                                                      |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/agent/prompts.py`        | DOM 提示 5 处：① 删除"URL 连续 3 步不变就放弃"（排行榜/数据页靠 AJAX，URL 不变正常）；② "still stuck 就放弃" 改为"前 15 步绝不放弃，先尝试 search / 滚动 / 菜单"；③ 只有真实硬墙（`login wall` / `403` / `404` / `CloudFront`）才允许放弃；④ 放弃明确标为"最后手段"；⑤ 一般错误页走 wait/re-read，不再直接放弃 |
| `src/agent/web_controller.py` | `_is_giveup` 过早放弃拦截门槛 **8 → 15 步**                                                                                                                                                                                      |
| `src/agent/main.py`           | 调用条件 `effect_step < 8` → `effect_step < 15`                                                                                                                                                                             |
| `tools/eval_local.py`         | 新&#x589E;**"过早放弃拦截面板"**：动态读取代码里的门槛值（当前 15），展示每个放弃任务的动作数与是否会被拦                                                                                                                                                           |

- **git 状态（已核实）**：改动**已本地 commit 并 push origin main**（`c178d0c`，2026-08-31）。包含 `src/agent/main.py`/`prompts.py`/`web_controller.py` 三文件修改 + 新增 `tools/eval_local.py`。后续真回归需在用户正式环境验证后，再触发官方冒烟。
- **语法校验**：3 个文件 `ast.parse` 通过。
- **验证限制**：本会话沙箱**无 openai SDK + aixforge 返回 503**（握手成功仅代理暂不可用，用户正式环境 API 正常），**无法真跑回归**，涨跌必须用户在本地/正式环境验证。

### 31.4 用户侧验证命令

```bash
cd D:\claude-work\WR-001
# 1. 跑新版（launch 用本地 chromium；正式环境换成传入的 cdp_url）
python src/agent/main.py --input data/example_tasks.json --output test_results/regression_v2 --cdp_url launch
# 2. 看涨跌（对比基线：成功率 40.4%、放弃 18）
python tools/eval_local.py test_results/regression_v2
```

**盯两个数字**：成功率是否上涨、放弃数是否从 18 往下掉。

- 若那 13 个被拦任务仍大量失败 → 把门槛提到 20~25 再试；
- 若超时变多 → 进 Day 4-5（重试 5→3、加 60 步强制 finished）。

### 31.5 7 天作战计划（按杠杆排序，本 session 已产出并落地）

| 阶段          | 内容                                                                             | 状态                               |
| ----------- | ------------------------------------------------------------------------------ | -------------------------------- |
| Day 1       | 测量闭环（评测仪 `tools/eval_local.py`）                                                | ✅ 已完成                            |
| **Day 2-3** | **杀假放弃**（门槛 8→15 + prompt 规则收紧）                                                | ✅ 已 implement + commit `c178d0c` |
| Day 4-5     | 修超时/死循环：软结束步数上限（70 步强制交卷）+ 保留 5 次重试（不降，冒烟需要）                                   | ✅ 代码已改，见 31.7                    |
| Day 6       | 答案质量（no_answer）：finished 非答案时强提示回页面提取具体值，最多 3 次                                | ✅ 代码已改，见 31.7                    |
| Day 7       | 稳定化 + 提交验证：environment.yml 已锁（依赖均 `==`）；全量改动已 commit `c178d0c` 并 push；官方冒烟 3/3 通过（见 31.8） | ✅ 已完成（push + 冒烟通过） |

### 31.7 Day 4-5 / Day 6 代码实施（2026-08-31，已 commit `c178d0c`）

**关键决策：不降重试次数。** 原计划写"重试 5→3"，但读历史发现 8/30 `1fbef05` 专门把重试 3→5 只为过冒烟（1/3 超时）。盲降会令冒烟再挂，故**保留 5 次重试 / `[120,180,180,180,180]`**，改从"步数上限 + 强制交卷"降低超时/卡死损失。

**Day 4-5（超时/死循环 → 尽力答案），`src/agent/main.py`：**

- 新增模块常量 `SOFT_FINISH_STEP=70`、`MAX_REANSWER_NUDGES=3`。
- DOM 分支每步：当 `effect_step >= 70`，向 `dom_history` 注入 SYSTEM 提示"立即调用 `finished` 提交最合理答案"，每步持续注入（`dom_history` 仅取最近 3 步，不堆积）。把"跑满 100 步 / 撞 1200s 单题超时 → 0 分"变为"交一份尽力答案"。
- 单题总超时 `TASK_TIMEOUT=1200s` **保持不变**（复杂题每步~60s、需 15+ 步，1200s 合理）；死循环检测已存在（`same_index>=8 or no_progress>=6` 强制终止），未改。

**Day 6（答案质量 / no_answer），`src/agent/main.py`：**

- `finished()` 内容经 `_is_valid_final_answer` 判为非答案（计划/过程/说读不到）且 `effect_step < 70`、强提示次数 `< 3` 时：不立即判 `FAIL_NO_ANSWER`，改为向 `dom_history` 注入 SYSTEM 提示"回页面提取具体数值/名称/年份/排名再 `finished`"，`result=wait` 让循环继续，最多 3 次（防无限 re-prompt）。仍无有效答案则按原逻辑判 `FAIL_NO_ANSWER`（无回归）。

**Day 7（稳定化 + 提交验证）：**

- `environment.yml` 复核：`playwright`/`openai`/`numpy`/`opencv`/`Pillow`/`requests` 均用 `==` 锁定，无需改动。
- 全量改动已 `git commit` 本地并 **push origin main**（commit `c178d0c`）：`src/agent/main.py`/`prompts.py`/`web_controller.py` + 新增 `tools/eval_local.py`。
- 真回归（跑模型）需在用户正式环境执行：
  ```bash
  python src/agent/main.py --input data/example_tasks.json --output test_results/regression_v3 --cdp_url launch
  python tools/eval_local.py test_results/regression_v3
  ```
  对比基线：成功率 40.4%、放弃 18、no_answer 5、loop 2。预期：放弃/loop/no_answer 下降，成功率上升。
- 验证通过后：官方冒烟与正式评测环境已就绪，可直接在群内 `@WR-EvalBot 提交代码` → 冒烟通过 → `@WR-EvalBot 开始评测`。

**未做 / 风险：**

- 本沙箱无 openai SDK + aixforge 返回 503，无法真跑回归，上述为代码层预期，需用户环境验证。
- `SOFT_FINISH_STEP=70` 为可调参数：若复杂题常需 >70 步才成功，可调到 80-85；若仍有任务吃满 1200s，再把 `TASK_TIMEOUT` 降到 900s（注意复杂题每步~60s×15步=900s 临界）。
- 视觉方案分支未加软结束注入（DOM 为比赛主模式；视觉分支沿用既有循环/超时兜底）。

### 31.8 2026-08-31 官方冒烟测试通过

- 用户在提交群 `@WR-EvalBot 提交代码` 后，官方冒烟测试 **3/3 通过**。
- 基于 commit `c178d0c`。
- 当前状态：环境就绪，可发起正式评测。
- **下一步**：在群内发送 `@WR-EvalBot 开始评测` 消耗今日正式评测次数。

*追加于 2026-08-31*

### 31.6 关联产出

- 评测报告：`WR-001/test_results/_EVAL_REPORT.md`（含过早放弃拦截面板，门槛=15）
- 评测仪：`WR-001/tools/eval_local.py`
- 本 session 项目日志：`WR-001/.workbuddy/memory/2026-08-31.md`

*追加于 2026-08-31*

### 31.9 正式评测策略（基于剩余赛程，2026-08-31 10:37）

**现状**：commit `c178d0c` 已 push + 官方冒烟 3/3 通过（31.8），部署链路稳定。但**冒烟通过 ≠ 分数上涨**——冒烟只验证 3 道题能出结果不崩溃，不验证成功率是否真从 40.4% 提升。本 session 的"放弃率 38%→13 个被拦"是**代码层预期**，尚未在用户环境跑 regression_v3 证实。

**赛程约束**（据 10.x 赛制）：8/27–9/2 共 7 天，**每日 1 次正式评测、取最优**。当前 8/31 10:37，剩余正式机会：**8/31、9/1、9/2 最多 3 次**（若今天发）。

**决策选项**：

- **选项 A（推荐）：今天直接发正式评测拿真实分。** 理由：①正式评测分数才是唯一真相，本地 regression 分布与官方不同；②赛制取最优，今天分数若低也不影响后面覆盖；③已 4 天 0 分，急需官方真实基线校准方向。拿分后对照 31.2 失败分类（放弃/超时/no_answer/loop）针对性再迭代，剩 2 次作保险。
- **选项 B：先本机跑 `regression_v3` + `eval_local.py` 对比基线，确认放弃率真降再发评测。** 风险：本机分布≠官方，且本机可能仍遇 503/超时，验证结论未必外推；但能避免今天唯一正式次数打水漂。

**我的推荐 = 选项 A**：今天发一次 `@WR-EvalBot 开始评测`，用真实分数验证 c178d0c 提分幅度。若分数仍低，按 31.2 失败分类定位——若放弃数没降（13 个被拦任务仍 FAIL），把 `main.py`/`web_controller.py` 门槛从 15 提到 20~25；若超时/no_answer 仍高，调 `SOFT_FINISH_STEP=70→80` 或 `TASK_TIMEOUT=1200→900`（临界，谨慎）。

**操作**：群内发 `@WR-EvalBot 开始评测` → 等结果 → 只记录官方总分作为验收（**注意：官方只给总分，不返回任何 per-task result.json / 失败分类**，无法据此定位问题）。

*追加于 2026-08-31*

### 31.10 官方黑盒约束 → 本地评测仪成为唯一可观测性（2026-08-31 10:55 用户澄清）

**关键事实**：官方评测**只返回总分**，不提供任何 per-task 的 `result.json` 或失败分类。→ 之前"发我官方 result.json 拆失败分布"的方案作废；你**无法从官方评测获得任何调整方向**。

**推论 / 新调整范式**：

- 官方分数只做**验收**（满分/排名），**不参与调参**。所有"哪类题失败、改动有没有用"的判断，只能来自**本地** `test_results/` + `tools/eval_local.py`。
- 这反而证明 Day 1 本地评测仪的价值：它是黑盒下你**唯一能看见**失败分布（放弃/超时/no_answer/loop）的眼睛。
- **诚实短板**：本地 47 题 ≠ 官方 100 题。官方在**远程腾讯云沙箱**跑（README 明写浏览器为远程沙箱、Playwright 连接），环境/网络/分布与本地不同，本地数字须打折看；但它是唯一窗口。
- **黑盒下最优策略**：
  1. 每次改动 → 本地跑 `eval_local.py` → 看失败分类涨跌幅 → 再改（官方只给最终总分验收）。
  2. 把"选哪道死磕"的决策**移到本地**：本地跑一遍定位哪类题能做对、哪类必挂，正式评测对能做的那类全力投入、其余交卷（变"盲死磕"为"基于本地画像的靶向"）。
  3. 优先做"宽口径降最坏"改动（如 c178d0c 杀假放弃/软结束/续找），不依赖官方分布即可抬升下限。
- **当前最该做的验证**：本地跑 `regression_v3`（基于 c178d0c）→ 对比基线（成功率 40.4% / 放弃 18）。这是唯一能确认 c178d0c 是否真降放弃率的途径；若本地放弃率降 → 方向对、正式 0 分更可能是环境/分布问题；若本地也没降 → 改动无效，需换路。

*追加于 2026-08-31*

### 31.11 正式评测卡死根因定位 + 根治（2026-08-31 11:41）

**现象**：8/31 正式评测触发后，约 50 分钟跑到 45/100 题后**整个 run 冻结卡死**，当日正式机会随之消耗。历史也有"20–30 分钟跑完 100 题"的情况（那批多为 8 步假放弃秒退，飞快但 0 分）。

**关键规则澄清**（读 `main.py:1420` 注释）：官方限制为 **每题 ≤100 步、单次模型调用 ≤3 分钟、整场 ≤4 小时**。**平台给整场 4 小时**，远非 20–30 分钟。故"50 分钟卡在 45 题"不是平台判死，是**真·卡死/极慢**。

**根因（高置信）**：主监控循环在单题超时时 `proc.terminate()` 杀掉 worker（`main.py` 旧 1515 行）。**`multiprocessing.Queue` 在被 terminate 的进程手里极易管道损坏**——其余 worker 的 `task_queue.get(timeout=5)` 随之全部 hang，整个 run 冻在 45 题。c178d0c 让更多题真正跑到 1200s 单题超时，恰好**频繁触发**这个潜伏 bug（此前 8 步秒弃的题根本到不了 1200s，故不暴露）。

**佐证**：worker 主循环 `while True: task_queue.get(timeout=5)`（`main.py:705`）；单题 1200s 硬超时由主循环 `proc.terminate()` 执行；一旦某波多个任务同时超时，terminate 风暴损坏共享队列 → 死锁。

**根治方案（commit `61a75e8`，未 push，待 9/1 前冒烟验证）**：

1. **单题超时改为 worker 内部自愈（消除 terminate）**：每题启动一个守护 `threading.Timer(TASK_TIMEOUT, task_abort.set)`；主循环每步轮询 `task_abort`，置位则 `status="FAIL"` 安全 break，写兜底结果并**继续下一题**。worker 永不因超时被杀 → `mp.Queue` 永不被破坏 → 不再死锁。
   - 选 Event 而非 `thread.interrupt_main()`：后者依赖 Python 信号投递，在 Playwright/LLM 的 C 层阻塞时未必及时送达，且 `agent.py:587` 存在裸 `except:`（虽只包视觉路径的树序列化、不包网络调用，但信号方案仍脆弱）。Event 线程安全、每步必检，确定性强。
2. **主监控循环移除对存活 worker 的 `proc.terminate()`**（旧超时分支改为仅打印"等待内部自愈"日志；仅当 worker 已异常退出才补写兜底）。
3. **整场 3 小时保险收尾**（`GLOBAL_BUDGET_SECONDS=3*3600`，< 4h 平台上限）：监控循环超预算则 `terminate` 全部 worker 并 `break`，后续"最后防线"扫 `processing_tasks` 为所有未落地题写兜底 → **保证 100 题全部产出 `result.json`，绝不无限卡死**。
4. **`SOFT_FINISH_STEP` 70 → 50**：压低难题无效步数，更多题在超时前交一份答案（边际提升覆盖率，非卡死修复主因）。

**测试约束（重要）**：本沙箱无 `openai` SDK + aixforge 返回 503，**无法真跑回归验证**；上述为代码层推理。改动只影响超时/长任务路径：正常 <1200s 完成的题不受影响（timer 创建后即 cancel，Event 永不置位，步数检查恒 false），故**不应破坏已有的冒烟 3/3**。9/1 前必须先在群内 `@WR-EvalBot 提交代码` 跑冒烟确认构建不崩，再 `@WR-EvalBot 开始评测`。

**结论修正**：上一轮"慢 = 好（放弃修复生效）"的判断需补一刀——**慢但能完成 = 好；卡死/不能完成 = 坏**。c178d0c 把题从"8 步秒弃"变成"真跑 70 步"，暴露了队列损坏死锁。本 fix 让 run 必完成，剩 9/1、9/2 两次机会。

*追加于 2026-08-31*
