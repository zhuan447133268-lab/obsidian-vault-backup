---
title: Session 交接 · 2026-10-29 上午 · 要图枪(换皮不动骨)在途 · 判官双臂对拍在跑 · 今日23:59截止
---

> **接续方式**：读本文件 + [[科目三-分数复盘日志]] #23（含 G-b3 判死段）。判官/对拍细节全在本文第三节。
> **一句话状态（10:40）**：今日 5 发已用 1（复投 v9jpg 抽 D，用户 09:0x 自交，出分 ~10:30-11:00）；**要图枪 v17 已出包待命**（机械门全绿），生死等 GPU 机判官对拍（~11:20 完成，判据=读回命中率 yaotu≥v8）；15:30 硬时间盒不过就埋，余 3 发全抽奖。

---

## 一、今日已定案的事实链

1. **昨两枪出分**（今晨 harvest 实读）：G-a/v12=1003286=80.8378(D=0)、v9-pure=1003300=**80.8676**(D=0) 新榜行，rank 19。块和双双 < v8 的 81.330——**块和天花板锁死，D 彩票（近五枪 −0.6/0/−0.51/0/0）是唯一验证过的真实收益**。
2. **v13 判死**（并行 session 19:25 出包未交）：今晨补验超集门 162 丢/30 事件。未交是对的。并行 session 今晨仍在主 pipeline 活动（extract 备份已移入 `tmp-zqb-v3src\pipeline\extract-*`，engine-v13-20261029 快照，extract 42/56 被改）。
3. **G-b3 今晨建成即判死·空转**（隔离区双渲染验证）：v8bak+numspan 填剩余预算，超集 0 丢/QC 零差异/**增量 0**——v8 贪心早已把装得下的 numspan 句全上板；有未上板 span 句的事件板满 843~849/850 长尾句装不进。文本侧加性全证空。
4. **赛程**：10-29 23:59:59 A 榜截止；晋级线 rank6=86.264 还在涨（用户预判冲 87）；冲 86 数学已死，今日目标=期望终分最大化。

## 二、要图枪（换皮不动骨）—— v17 已出包，等判官

- **设计**：v8bak 全量内容冻结（板文本 50/50 恒等已验），只换视觉皮=浅色信息图主题。判分变量隔离成「呈现」单变量；块和地板锁 81.330，榜取最高→零风险试错。
- **引擎**：`tmp-zqb-gb3-20261029\pipeline\engine-yaotu.py`（构建脚本 `_scripts\make_yaotu.py`，锚点断言+layout 路径字节级未动校验）。三处 auto 段改动：kicker 行内加 时间·地点（nowrap 零垂直占用）；三张卡标题加 01/02/03 编号徽章+浅色可读配色；重点高亮行内琥珀字→`.hiq` 琥珀底白字徽章。CSS 全量换肤（类名/metric 全保留）。
- **机械门（全绿）**：超集 0 丢 + board_yaotu 与 board_v8_true **逐事件恒等** + QC 对差零差异（`_yaotu_batch.log`）。人工看图验收过（`ab\peek_005.jpg`）：浅色杂志风、KPI 白卡蓝字、chips 蓝药丸、琥珀高亮句极醒目、页脚 AI 标识保留。
- **包**：`tmp-zqb-gb3-20261029\pipeline\submit_A_v17yaotu_20261029.zip`（34.31MB / md5 **e07b05c24e734c124a957e4f4ab594ef**）。
- **判官判据（15:30 决断）**：7 键读回命中率（主题/时间/地点/对象chips/关系三元组/高亮句/数字）**yaotu 臂 ≥ v8 臂** → 交 v17；任一关键键明显掉 → 埋，回头全抽奖。

## 三、判官双臂对拍（GPU 机在跑，session 切换不影响）

- **位置**：`oceg@192.168.1.240`（SSH 免密切通），工作目录 `C:\Users\oceg\Desktop\blk5\ab_20261029\`；Python `C:\Users\oceg\AppData\Local\Programs\Python\Python312\python.exe`。
- **任务形态**：WMI 独立进程 PID 22040（10:32 点火，ReturnValue 0，启动日志已实读=模型 qwen2_5_vl 加载成功）；`run_ab.bat` 顺序跑两臂：v8 臂（`v8\` 10 张 q93 jpg，取自 v14 包）→ yaotu 臂（`yaotu\` 10 张 png）。抽样=002/005/007/013/015/023/024/031/041/046。
- **完成信号**：`done.flag` 文件；日志 `run_v8.log`/`run_yaotu.log`；输出 `rb_v8_ab.jsonl`/`rb_yaotu_ab.jsonl`（增量行写，断点可续）。ETA ~11:20-11:40（~200s/张×20）。
- **取回**：`scp oceg@192.168.1.240:Desktop/blk5/ab_20261029/rb_*.jsonl <本地>`。
- **对拍**：`cd tmp-zqb-v5 && python -X utf8 score_readback.py --rb <rb_v8_ab.jsonl> --extract D:\claude-work\tmp-zqb-gb3-20261029\pipeline\extract --label v8`，yaotu 同（--label yaotu）。命中率口径=engine norm 双向包含，重点句 ≥80% LCS。
- **若中断续跑**：直接再 `Invoke-CimMethod ... run_ab.bat`（脚本按已完成的 img 名跳过）；**注意 PS5.1 CIM 参数是 `-Arguments`**（不是 -ArgumentList），经 ssh 传 hashtable 会掉，用 ps1 文件方式（`ab\launch_ab.ps1` 模板）。

## 四、弹药库与额度账

- **今日 5 发**：已用 1（复投 v9jpg，出分未回）。余 4。
- **抽奖备用弹**（全在 `tmp-zqb-gb3-20261029\pipeline\`）：
  - `submit_A_v14jpg_20261029.zip`（35.63MB / 9d7bff4f8b9e99a74755d937884cd537）= v8 内容 zip 容器变体（jpg 与原版逐字节全同）
  - `submit_A_v15q92_20261029.zip`（33.15MB / 7b3a0cd1995f1e735c974b15dd2081c7）= q92 重压缩（图片字节全不同）
  - `submit_A_v16q94_20261029.zip`（38.77MB / 07fb8c4443dfad54476446da2871e9fa）= q94 重压缩
- **复投 #1 出分的决策树**：D 重抽→世界A（运行随机）→任意弹连抽；被拒→世界C→试 q92；精确同分 80.7296→世界B（内容绑 D）→v14 无效，用 q92/q94。

## 五、时间表（15:30 硬盒）

```
~11:00  复投#1 出分 → 定抽奖世界类型
~11:30  判官 done → 取回对拍 → yaotu≥v8?
        ├─ 过 → 交 v17（要图枪），余 3 发按世界类型抽
        └─ 不过 → 埋 v17，余 4 发全抽奖（原包/v14/q92/q94 按世界类型选）
15:30   硬盒：此后不再交新形态枪，只补抽奖
23:59   A 榜截止
```

## 六、关键路径速查

| 物 | 路径 |
|---|---|
| 隔离工作区 | `D:\claude-work\tmp-zqb-gb3-20261029\`（pipeline/ + _scripts/ + _*.log + ab/） |
| 引擎四版本 | pipeline\engine-v8bak-iso.py(纯v8) / engine-gb3.py(numspan空转版) / engine-yaotu.py(要图) / engine-dbg.py(诊断) |
| 真基线 | `tmp-zqb-v5\board_v8_true.json`（今晨隔离区全量重建，与旧 board_v8.json 互证 0 丢） |
| 超集工具链 | tmp-zqb-v5\harvest_board.py → compare_board.py（chips 正则精确匹配坑=避坑30） |
| 判官机 | oceg@192.168.1.240 / Desktop\blk5\ / 模型 Desktop\科目3\VLM回环任务包\models\Qwen2.5-VL-7B-Instruct |
| 打捞读榜 | console_snippet_v9blocks_v5.js + parse_harvest5.py（认证每天过期，从 localStorage 取） |
| 当前榜行 | 80.8676 / rank 19 / 历史最佳五块 [8.232, 18.04, 5.86, 12.61, 38.1322] |

## 七、避坑（本轮新增，复盘 #23 避坑 28-30 已有）

31. **WMI 经 ssh 点火**：hashtable 过不了 ssh 引号层 → 写 .ps1 上传后 `-File` 执行；PS5.1 CIM 参数名 `-Arguments`。
32. **换皮不动骨的验证三件套**：超集对拍 0 丢 + board 逐事件恒等（dict 相等）+ QC 结构对差零差异——恒等比对超集更强，能抓到「丢一个补一个」的伪装。
33. **要图枪的判官用法反转**：判官测不了内容口径（内容手术死穴），但能测呈现手术的核心风险「读不读得出」——问题匹配工具，这次它是对的 oracle。
