# 考试平台演进 · P1 · Claude Code 独立复核记录（2026-11-02）

> 本文回答 zcode 在 P1 闭环审计中提出的问题（「针对 P1 的新一轮评审在哪」）——评审此前只存在于对话与索引一行，**本文是其正式落库版本**。
> 复核对象：P1 `afe5f92` + P1.1 `6c172ee`（分支 `feat/exam-platform`）。复核方式：全部关键声明亲自验证，不转述 zcode 报告（做验分离）。

---

## 0. 结论

**P1 / P1.1 通过验收，P2 闸门解除。** zcode 对 P0 评审 §10 的闭环审计属实（12 项全部落地，其中 2 项于 `6c172ee` 补齐）；审计中发现 1 个低优先实现缺口（ioredis 折叠漏栈行，见 §3.3，非阻塞）。

---

## 1. 对 P1（`afe5f92`）的独立验证（7 项）

| # | 核验项 | 方式 | 结果 |
|---|---|---|---|
| 1 | 提交链与工作树 | `git log/status` | ✅ `9307520`→`45f472b`(P0.5)→`afe5f92`(P1)，树干净 |
| 2 | 库事实 | 直连 MySQL（非转述） | ✅ applied=10/物理=11；41/41 场 `LAB_ENTRY`+pcv=1；`question_banks` 恰 1 行；2001/2001 回填；**CRC 仍 `49371640`** |
| 3 | P1 迁移 SQL | 逐行读 | ✅ 只有允许的 7 项；回填带 `bank_id IS NULL` 守卫；`exam_type` VARCHAR(32) 非 enum |
| 4 | reconcile 迁移 SQL | 逐行读 | ✅ `IF NOT EXISTS` + prepared-statement 幂等，纯结构不动数据 |
| 5 | 迁移链自足性 | **自建空库 `lab_exam_verify_p1` 亲自重放**（已删库） | ✅ 17 表 / deploy 二次「No pending」/ 内置库名 UTF-8 无乱码 / `migrate diff` 输出空迁移 |
| 6 | 全量验收 | **亲跑 `run-acceptance.sh P1`（`afe5f92` 上）** | ✅ 失败计数 0；jest 154 passed/8 skipped；库断言 19/19 |
| 7 | P0.5 修复真实性 | 篡改 baseline.json 负向测试 | ✅ 篡改→报漂移 exit 1；还原→exit 0（注：首次被 shell 管道吞了退出码，去掉管道复测确认——审别人脚本时自己也别信管道后的 `$?`） |

## 2. 对 zcode 四处偏差的裁定：全部认可

1. `migrate dev --create-only` 非交互环境不可用 → `migrate diff`+手写目录+`deploy`，等价且更可审；
2. 账本 applied 7→8（物理 9）：Prisma 对失败行确为「标记 `rolled_back`+补插 applied」——已查 `_prisma_migrations` 实际行核实；
3. **多出 reconcile 迁移（applied=10）**：P1 最有价值的发现，迁移链从不自足（空库重放 14 表）；独立成条保持 P1 可审，处理正确；
4. `UserRoleRel` 补登记两字段：纯 datamodel 补登，链与 schema 现完全同构（diff 为空已亲证）。

另认可报告外加分项：`run-acceptance.sh` cleanup 在 Windows 杀不掉 node 子进程（冒烟会命中旧构建假绿）→ `kill_port` 修复有效，复核时 3100 端口无孤儿。

## 3. 对 P1.1（`6c172ee`）的审计

### 3.1 Q4.1 更强口径（`migrate reset --force`）— ✅ 属实
`evidence/P1-20261102/03-clean-reset.txt` 逐项核对：17 表 / applied 10 / 内置库 1 行 / 唯一索引存在 / `paper_generation_jobs` 存在 / `exam_type` 默认 LAB_ENTRY，随后 deploy 报 No pending。与我在 `lab_exam_verify_p1` 上的独立重放结论一致。

### 3.2 基线锚点刷新 — ✅ 合理
baseline.json 的 commit 锚 `45f472b→afe5f92`：数据锚与内容匹配（`6c172ee` 只改脚本，不动库事实）。

### 3.3 🟢 ioredis 折叠 — 有效但有缺口（非阻塞）
`collapse_smoke_noise()` 只匹配 `^\[ioredis\] Unhandled error event` 头行；**每个事件尾随的 2 行栈（`at internalConnectMultiple` / `at afterConnectMultiple`）没匹配，26 行仍留在 02-smoke.txt**。「13 行→1 行」的验证只数了头行。建议补丁（可并入 P2 首个 commit 或 P1.2）：

```bash
# awk 段补一行模式即可：
/^    at (internalConnectMultiple|afterConnectMultiple)/ { next }
```

更稳的写法是状态机：命中头行后跳过其后连续 `^\s+at ` 行，直到空行——栈帧行数随 ioredis 版本可能变。

### 3.4 复跑确认
**Claude Code 在 `6c172ee` 上亲跑 `run-acceptance.sh P1`**：exit 0，失败计数 0，基线未漂移（99-summary 记录的 commit 已是 `6c172ee`）。改动后的验收脚本可信。

## 4. 对 zcode 闭环审计的确认

zcode 报告的「§10 十二项评审项闭环」与其 P1 笔记偏差表逐条比对属实，其中包括诚实记录了我方评审被现实推翻的一条（§10.6.3 预测正式库 9 条 → 实际 10 条，因链不自足多一条 reconcile）。**这种「逐条认账」的报告方式正是本项目要的工程纪律，予以确认。**

## 5. 遗留小项（不阻塞 P2）

| 项 | 处置建议 |
|---|---|
| ioredis 栈行折叠补全（§3.3） | 并入 P2 首个 commit，或单独 `P1.2`（5 分钟工作量） |
| `D:\MyBrain\` 下避坑指南旧副本（09-17） | 与 Obsidian 活副本（#33）长期并存易误导，建议下次整理 MyBrain 时删旧或加「已过期」横幅 |

## 6. 关联

- 被复核记录：[[lab-exam-2026-11-02-exam-platform-p1-schema]]、[[lab-exam-2026-11-02-exam-platform-p0-baseline]]（§10 为 P0 评审原文）
- 概念卡：[[concept-prisma-migration-ledger-p3009]]
- 下一步：用户向 zcode 下发 P2 指令（平台底座服务；compat 层 P2 写；抽题唯一真相归 `question-bank.service`，旧两份标 `@deprecated`）
