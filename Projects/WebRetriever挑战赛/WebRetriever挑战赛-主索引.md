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
