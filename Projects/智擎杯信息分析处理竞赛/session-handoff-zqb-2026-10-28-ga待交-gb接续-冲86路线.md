---
title: Session 交接 · 2026-10-28 傍晚 · v11判死→冲86路线确立 · G-a已出包待交 · G-b补丁已打好
---

> **接续方式**：读本文件 + [[科目三-分数复盘日志]] #22（v11 判死）。细节 [[科目三-A榜总攻行动指南-2026-10-28]]。
> **一句话状态（17:30 更新）**：v11=76.3406 判死，**G-a 已交（~17:05，出分预计 ~18:0x）**；G-b 未出包——发现 **coverage 门在 v8 基线上就破**（002 裸 v8bak 渲染 coverage 失败 5 条），且 **有另一个 session 正在并行改 engine.py**（17:27 把它换成 v9 两层选句+numspan 变体，17:28 仍在写文件）——**接续前先确认谁是 G-b 正主，两 session 同目录互踩中**。

---

## 一、本session已定案的事

1. **v11 出分 76.3406**：块和 76.853（−4.48），D −0.51 稳定。重点−10.2%/关系−7.4%/对象−6.9%/核验−3.4%/要素−1.4%。复盘 #22 已写。「官方真值=改写句」假设**证伪**：官方=语料原句包含链；**替换型文本手术 2/2 全灭**（v9−2.66/v11−4.48）。
2. **冲 86 路线（用户拍板）**：v9 四手术死因是捆绑的 tier 句池改动，四手术单变量从未获公平审判。缺口表：要素+0.6~1.9/重点+0.6~1.7/核验+0.4~1.25/关系+0.7~1.2/对象+0.3~1.8，全兑现中值≈+4.5→85.8，D 抽 0→85.8~86.4。
3. **超集纪律（新门禁）**：新板 ⊇ v8 板逐句机器验证（`compare_board.py`）。**坑已排过**：ft 必须按句拆（打包边界漂移造伪丢失）+ 剥"……余文略/（完）"尾巴；预算补偿要按「新必中串拉进优先池的整句长度」算，不能只算新增句自身长度。
4. **判官线二次关闭**：7B 脱离会话 430s/张跑不完、3B 起不来；且 VLM 读回测不了内容口径正确性（v9/v11 死因）。GPU 机后台唯一可靠启动法=WMI Invoke-CimMethod + .bat。

## 二、G-a 状态（待交）

- **包**：`pipeline\dist\submit_A_v12jpg_20261028.zip`（39.9MB / md5 **631428ae6cab24f9f87487f28a5459bd**）
- 内容：v8bak + E1(+28 意义句，预算补偿) + E2clean(+82 人工精滤对象，`tmp-zqb-v5\e2_clean.json`)
- 门禁：50/50 全绿 + **超集 0 丢失**（最终 budgets 在 extract-ga-20261028，006=1047/013=1248/014=1360 等）
- **✅ G-a 已交：2026-10-28 ~17:05（用户 17:06:44 确认；精确 createdAt 出分时从打捞接口补登）**。独立复验记录：compare_board.py 报 18 条"丢失"全部为形态伪差（「（全文N字）」尾巴数值漂移/ft句拆/HTML实体），中段+8字滑窗探测 18/18 内容在场。
- **用户提交后**：出分(~1h, 预计 ~18:0x) → 跑打捞 `console_snippet_v9blocks_v5.js` → `parse_harvest5.py` 读五块 → 复盘 #23

## 三、G-b 接续步骤（按顺序）

当前 pipeline 现场（17:1x）：`engine.py`=`engine-gb-20261028.py`（E3 数字span池）；`extract/`=G-b 态=extract-v8bak 纯血+9事件预算bump；渲染/对拍进行中。

**进度记录（本session 17:0x~）**：
1. ✅ 首渲染 50/50 全绿 → 收割对拍 26 条真丢（003/005/006/009/012/013/014/015/023）
2. ✅ bump = +1526 总（012=+324 最大），已双份同步到 extract-gb-20261028 与 pipeline\extract（003=959/005=1012/006=1006/009=958/012=1174/013=972/014=1027/015=1143/023=925）
3. ⏳ 9 事件重渲染 → 重收割对拍到 0 丢失 → 出包 v13

**17:2x 追加（G-b 攻坚记录 + 三个硬事实 + 并行 session 冲突）**：

**三个硬事实（无论谁接手 G-b 都用得上）**：
1. **收割器坑（已修）**：`build\sample-002.html`（样例页）混进 build 目录，`harvest_board.py` 旧正则按"文件名取数字"归 eid，`sample-002` 覆盖真 002 ⇒ **002 从未被任何超集对拍覆盖过**（v8/v11/G-a 全漏）。已修为锚 `^(\d{3})\.html$`（17:25），并用 v8bak 引擎+extract 重渲染 002 重建真基线并入 `board_v8.json`（002 ft 7 段/11 chips）。
2. **v8 基线自身 coverage 就破**：纯 `engine-v8bak + extract-v8bak` 渲染 002，**coverage 失败 5 条**（5 条表达重点长句挤不进 850 预算，host 句长度和>预算）。v8 官方 80.7296 就是带这个伤打的——**coverage 全绿从来不是 v8 的既有性质**，G-b 不必为它背债，但也别再把"三闸全绿"当 v8 已实现过的状态。
3. **G-b 的三方张力**：coverage（必中串宿主句上板）× 超集（v8 板全保）× 物理容量（card:ft 22px 行高上限）在 850 预算下不可兼得。E3 把 numspan 句塞进优先池后 850 下 coverage 破 11 事件；bump 预算则 012/015 物理 overflow（设了 `_ft_budget` 会禁掉引擎自带的 0.85 回退）。

**G-b 已试三版（engine 选句段）**：
| 版 | 机制 | 超集丢失 | coverage | 结论 |
|---|---|---|---|---|
| G-b1 | v8选句+numspan 进优先池（交接原版） | 26 | 破 11 事件 | bump +1526 后超集 26→6，coverage 仍破 6 事件 |
| G-b2 | collect_required 宿主句**强制上板**（无预算检查） | **22（更差）** | 好转但 002/003/006 仍破 | 宿主句挤爆物理容量，多事件 card:ft overflow，被弃 |
| G-b3（未落地） | v8核心选句原样（=v8bak 逐行复刻）+ numspan 宿主句只填**剩余预算**（真加性） | 构造性 0 | =v8（002 先天 5 条） | 设计已写好，apply 时发现 engine.py 已被并行 session 覆盖 |

**⚠️ 并行 session 冲突（17:30 未解决）**：17:15~17:28 另一 session 在同目录活动：建 `_elem_audit.py`(17:15)/`_extract_audit.py`(17:19)/`engine-gb-current-backup.py`(17:19)/`_qc_offline.py`(17:25)/`_extract_sizes.py`(17:28)，**17:27:29 把 `engine.py` 改写为 v9 两层选句(pool_pt/pool_ot)+numspan 变体**（与交接的"v8原版选句+两行补丁"不同路线），17:28:21 仍在写文件。**接续前必须确认 G-b 正主**；两 session 同目录互踩，engine/extract 随时可能被覆盖。

**当前 pipeline 现场（17:30 快照）**：
- `engine.py` = **并行 session 的 v9两层+numspan 版**（17:27:29，非本session所写，未验证）
- `engine-gb-20261028.py` = 本 session 的 **G-b2 版**（17:19:59）
- `extract/` = G-b 态（v8bak 纯血 + 9 事件 bump：003=959/005=1012/006=1006/009=958/012=1174/013=972/014=1027/015=1143/023=925），002/008/016 未 bump
- `board_v8.json` = 已修 002 的真基线；`harvest_board.py` = 已修正则；`compare_board.py` = 16:5x 剥尾巴+句拆版（现行门禁口径）
- G-a 已交 ~17:05，出分 ~18:0x → 打捞五块 → 复盘 #23 → 再定 G-b 是否照交

**G-b 下一步建议（单 session 接管后）**：按 G-b3 设计重写选句段（v8bak 逐行复刻 + numspan 只填剩余预算）；012/015 先按现预算渲染探物理上限，overflow 则 bisect 预算下调（span 加性层自动收缩，超集不受影响）；全绿后全量 50 渲染→收割对拍（002 已能真验）→出包 v13。002 的 coverage-5 是 v8 旧伤，单独记账，不在 G-b 范围修（修=新变量）。

**⚠️ 教训**：`compare_board.py` 在 16:5x 被前session更新过（剥尾巴+ft句拆新口径），用前必读盘上的现行版本，别凭旧记忆。

**原接续步骤（备查）**：
1. `cp engine-gb-20261028.py engine.py`
2. `rm -rf extract && cp -r extract-v8bak-20261028 extract-gb-20261028 && cp -r extract-gb-20261028 extract`（G-b 纯 v8 extract，单变量）
3. `cd pipeline && python -X utf8 batch.py`（全 50 渲染，~10min）
4. `cd tmp-zqb-v5 && python -X utf8 harvest_board.py <pipeline>\build board_gb.json && python -X utf8 compare_board.py board_v8.json board_gb.json`
5. **必有丢失**（数字span句挤占）→ `python -X utf8 fix_budget.py board_v8.json board_gb.json` → 把 bump 应用到 **extract-gb-20261028 和 pipeline\extract 两份**（坑：上次只改一份导致重渲染无效）→ `batch.py <受影响事件>` → 重收割重对拍到 0 丢失
6. `python -X utf8 pack_v12ga_jpg.py` 改输出名为 v13 → 出包交用户
7. 今天 2 发 = G-a + G-b；明天 5 发 = G-c 关系verbatim（render端，参照 engine-v9live-confirmed  diff）/G-d 对象清洗/G-e 已验证手术大合包+D彩票

## 四、关键路径速查

| 物 | 路径 |
|---|---|
| 工程 | `D:\claude-work\tmp-zqb-v3src\pipeline`（engine.py/extract/ 是现场，动前先想现在是哪版） |
| 备份 | engine-v11 / engine-v8bak / engine-gb-20261028；extract-v11 / extract-v8bak / extract-ga / extract-gb |
| 超集工具链 | `tmp-zqb-v5\harvest_board.py` → `compare_board.py` → `fix_budget.py`（+`build_ga.py`/`e2_clean.json` 档案） |
| 打捞 | `console_snippet_v9blocks_v5.js` + `parse_harvest5.py`（认证头 userid/token 来自 localStorage，每天过期） |
| 五块官方读数 | v8: 8.232/17.355/5.620/12.396/37.727=81.330(D−0.60)；v11: 76.853(D−0.51) |
| 晋级线 | rank6=85.6836 还在涨；P(86)≈10%（用户知情并接受，非覆盖制烧枪零伤害） |

## 五、避坑（本轮新增，复盘 #22 四 also）

1. 替换型文本手术默认禁止；文本侧只剩加性超集形态，且必须过 `compare_board.py`。
2. 三闸全绿 ≠ 官方不扣（本地测不丢，官方测包含口径）。
3. 预测必须标假设链（v11 预测偏差 −4.7 全因「改写句=官方口径」前提错）。
4. 改 extract 记得 pipeline\extract 与备份目录**两份同步**，否则重渲染吃旧数据。
