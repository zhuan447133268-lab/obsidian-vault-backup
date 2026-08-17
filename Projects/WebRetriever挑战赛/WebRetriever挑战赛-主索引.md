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

### 3.2 本地验证结果

#### 测试 1：iPad Air 3 屏幕更换指南
- **任务文件**：`D:\claude-work\webretriever\data\task0_only.json`
- **状态**：`SUCCESS`
- **步数**：2 步
- **agent_answer**：已打开 iPad Air 3 屏幕更换指南 URL
- **结论**：✅ 流程完全跑通，输出格式正确

#### 测试 2：猫眼票房（example_tasks 第 1 题）
- **任务文件**：`WR-001/data/example_tasks.json`
- **状态**：`FAIL_AGENT_GIVEUP` / 有时 `SUCCESS`
- **结论**：代码流程正常，但模型对该 SPA 页面导航能力弱，答案偏幻觉。非工程阻塞，属于模型/策略优化范畴。

### 3.3 待跟进
- [ ] 第二次官方冒烟测试结果（基于 commit `918fe0a`）
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

---

## 7. 关联记忆

- [[webretriever-dom-progress-2026-07-31]] — 7 月底 DOM 方案进度
- [[WebRetriever挑战赛参赛评估]] — 比赛整体评估
- [[WebRetriever挑战赛2026-07-28会话交接]] — 历史 bug 修复记录

---

## 8. 待确认/待决策

- 若官方冒烟测试通过，是否继续优化答案准确率？
- 是否需要在 config.json 中保留视觉方案切换开关？
- 是否需要针对常见网站类型（电商、数据、百科）做特化策略？

---

*最后更新：2026-08-17*
