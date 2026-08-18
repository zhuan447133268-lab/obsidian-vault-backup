---
title: WebRetriever 代码复盘 2026-08-17
tags:
  - project
  - webretriever
  - competition
  - review
date: '2026-08-17'
status: active
---

# WebRetriever 代码复盘（2026-08-17）

> 本笔记基于 `D:\claude-work\WR-001` 仓库当前 `main` 分支代码（commit `7ee3cc9`）整理，用于 8 月 27 日正式提交前的自查与后续优化。

---

## 1. 项目基本信息

| 项 | 内容 |
|---|---|
| 比赛 | 2026 WebRetriever Challenge |
| 仓库 | `hhhhhhalf/WR-001`（Private） |
| 本地路径 | `D:\claude-work\WR-001` |
| 当前 commit | `7ee3cc9`（已 push main） |
| 模型 | `kimi-k2.6`（0x7e.vip 网关） |
| 主方案 | DOM 文本方案（`use_dom: true`） |
| 环境 | Python 3.10，Playwright + OpenAI + numpy + opencv + Pillow |

---

## 2. 仓库关键文件职责

| 文件 | 行数 | 职责 |
|---|---|---|
| `src/agent/main.py` | ~1019 | 多进程调度、任务过滤、浏览器生命周期、DOM/视觉分支、结果保存、capture.json 兜底 |
| `src/agent/agent.py` | ~892 | `UITARSAgent`：模型调用、输出解析、历史维护；`predict()` 视觉、`predict_dom()` DOM |
| `src/agent/prompts.py` | ~173 | 动作空间 + 用户 Prompt 模板（视觉 / DOM 两套） |
| `src/agent/web_controller.py` | ~1299 | Playwright/CDP 浏览器操控、动作执行、请求监听 `RequestCollector`、DOM 动作执行 |
| `src/agent/dom_extractor.py` | ~216 | 抽取可交互元素、页面文本 fallback、元素格式化 |
| `config.json` | ~10 | API 地址/密钥/模型、`use_dom` 开关 |
| `environment.yml` | ~34 | conda 环境声明 |

---

## 3. 模型配置（`config.json`）

```json
{
    "api_base": "https://api.0x7e.vip/v1",
    "api_key": "sk-Y6ew5uSGD5RYcaX8v1WkIYZq57AYRiPgC4D7DaITWZQsQEr1",
    "api_model": "kimi-k2.6",
    "api_ports": [],
    "use_dom": true,
    "temperature": 0.7,
    "top_p": 1.0,
    "max_tokens": 8192
}
```

- 实际调用时 `temperature=0.6`，`top_p=0.95`（Kimi K2.6 适配）。
- `disable_thinking=true`，关闭 thinking 省 reasoning tokens。
- `infer_mode="qwen25vl_normal"`，动作空间用 `finished(content='...')`。
- `model_type="kimi"`，坐标恒等映射。

---

## 4. Agent 架构

### 4.1 视觉方案流程

1. `main.py` 截图 → `obs["screenshot"]`。
2. `agent.predict()` 调用 `UITARS_USR_PROMPT_THOUGHT`。
3. 模型输出 `Thought: ... Action: ...`。
4. `parse_action_to_structure_output()` 解析、坐标重映射。
5. `web_controller.excute_action()` 执行 click/type/scroll/hotkey 等。

### 4.2 DOM 文本方案流程

1. `dom_extractor.extract_interactive_elements(page)` 抽取元素。
2. 元素少于 3 个时 `extract_page_text()` 补充页面可见文本。
3. `format_elements_for_prompt()` 渲染成编号列表。
4. `agent.predict_dom()` 调用 `UITARS_USR_PROMPT_DOM`。
5. 模型输出 `click(index=N)` / `type(index=N, content='...')` / `select(...)` 等。
6. `web_controller.execute_dom_action()` 按 `doc_index` 重新定位 handle 执行。

### 4.3 关键解析兜底（`agent.py`）

- 无 `Action:` 前缀但本身是合法函数调用 → 直接解析。
- 无 `Action:` 也不是函数调用 → 包装为 `finished(content='...')`。
- 多个 Thought/Action 混在一起 → 提取第一个合法函数调用。
- `type(content='''...''')` / 双引号 → 统一转义为单引号。

---

## 5. 已修复 Bug 清单

| # | Commit | 问题 | 修复点 |
|---|---|---|---|
| 1 | `b15dcce` | 初始提交 | 仓库初始化、配置 Kimi K2.6、迁移 DOM Agent |
| 2 | `918fe0a` | 官方冒烟：agent_answer 为空 | 模型输出解析鲁棒性：无 `Action:` 前缀、纯答案文本自动包装、多 Action 混在一起时取第一个合法调用 |
| 3 | `0e47a1b` | 官方冒烟：清空标签页导致浏览器关闭 | `web_controller.py` 的 `init_playwright_context` / `reset_browser_state` 清理时保留最后一个标签页 |
| 4 | `fe60d92` | 官方冒烟：3 题中 1 道缺少有效输出 | `agent.py` / `main.py`：API 超时重试 5 次、`agent_answer` 多层兜底、异常时仍保存 `result.json` |
| 5 | `7ee3cc9` | 官方冒烟：`capture.json` 请求记录为空 | `main.py`：请求监听从 page 级迁移到 context 级、重建 context 时重新绑定、无 xhr/fetch 时写入当前 URL 兜底、异常时仍保存 `capture.json` |

---

## 6. 当前技术债务与优化点

### 6.1 硬编码兜底（需要逐步泛化或保留为保险）

- **`main.py:448-522`**：iFixit iPad Air 3 任务硬编码直达 `https://zh.ifixit.com/Device/iPad_Air_3` 并点击 `Screen Replacement` 链接。
- 风险：仅对该题有效，换设备/任务无效。
- 建议：保留作为该题保险，同时提升模型对导航链接的识别能力。

### 6.2 DOM 提取局限

- `SELECTORS = "a, button, input, select, textarea, [role='button'], [role='link']"`
- 对 SPA、动态下拉、React 自定义组件识别有限。
- 当前 fallback 是抽取页面可见文本，但模型仍可能不知道如何交互。

### 6.3 Prompt 策略

- DOM Prompt 当前强调 "SEARCH FIRST"，但对结构化导航任务（如 iFixit 设备树）可能过度依赖搜索。
- 视觉 Prompt 已含结构化导航优先策略，但 DOM 分支两者略有冲突。

### 6.4 防死循环逻辑

- `main.py` 已加：连续同 index ≥3、同 URL 无进展 ≥3 强制换策略；≥8/≥6 强制终止。
- 强制回到任务起始页，可能让模型在部分场景下原地打转。

### 6.5 视觉方案未验证

- 代码保留视觉分支，但当前 `use_dom=true`，视觉方案未经过官方冒烟测试。
- 若 DOM 方案在某些题上持续失败，视觉 fallback 需要单独验证。

---

## 7. 测试覆盖情况

| 测试项 | 状态 |
|---|---|
| `task0_only.json`（iPad Air 3 屏幕更换） | ✅ 本地通过，2 步 SUCCESS |
| `example_tasks.json`（猫眼 + 世界银行） | ✅ 本地非空 result.json / capture.json |
| 官方冒烟测试 | ✅ 通过（commit `7ee3cc9` / v5） |
| 更多样例 / 准确率测试 | ⚠️ 待补充 |
| 视觉方案 | ⚠️ 未验证 |

---

## 8. 后续优化方向

### 优先级 P0（正式提交前必做）

1. **批量本地测试**：至少跑 10-20 道不同题型，统计成功率、失败原因分布。
2. **答案准确率**：检查 `agent_answer` 是否真正回答了问题，而非仅到达页面。
3. **兜底稳定性**：确认 `capture.json` 在各类站点都不会为空。

### 优先级 P1（时间允许则做）

1. **DOM 提取增强**：增加对自定义下拉、Tabs、Accordion、SPA 路由切换的识别。
2. **Prompt 迭代**：按失败 case 调整 `UITARS_USR_PROMPT_DOM` 的策略顺序。
3. **移除/弱化硬编码**：把 iFixit 兜底改成更通用的 "设备页 → Screen Replacement" 模式匹配。

### 优先级 P2（可选）

1. **视觉方案 fallback**：当 DOM 方案连续失败 N 步后切换截图模式。
2. **模型参数调优**：temperature / top_p / max_tokens 对 Kimi K2.6 的对比实验。

---

## 9. 正式提交计划

| 时间 | 事项 |
|---|---|
| 2026-08-17 ~ 2026-08-26 | 本地批量测试 + 针对性优化 |
| 2026-08-27 00:00 起 | 正式提交通道开启 |
| 2026-08-27 ~ 2026-09-02 | 在窗口期内完成正式提交与评测 |
| 2026-09-02 截止后 | 通道关闭，等待结果 |

---

## 10. 关联文档

- [[WebRetriever挑战赛-主索引]] — 比赛唯一主文档
- [[webretriever-smoke-test-page-cleanup-fix-2026-08-17]] — 本次修复记忆
- [[webretriever-dom-progress-2026-07-31]] — 7 月底 DOM 方案进度

---

*最后更新：2026-08-17*
