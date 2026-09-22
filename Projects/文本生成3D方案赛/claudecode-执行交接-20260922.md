---
title: Claude Code 执行交接 —— 租机取证 / 加固臂（只测不改）/ 第八次重打 runbook（2026-09-22，ZCode 出）
---

> 出方 ZCode，2026-09-22。**先读 §0 与 §1.2 再动手**：§1.2 是今天现场实测出的结论，**推翻**了此前"改一处默认值就能改官方那次跑分"的说法（本库 `决赛高分抓手-默认值杠杆-20260922.md` 原 §0、`D:\wsl\tmp\gpu_verify\GPU实测-交接与决策.md` 原 §12 的表述均以此为准）。不读会做出反作用的事。
>
> 配套：[[GPU实测-交接与决策]]（工具、失败分支）、[[决赛高分抓手-默认值杠杆-20260922]]（杠杆表，§0/§5 已更正）、[[session-handoff-3d-2026-09-21]] 第二十~二十二节。

## 0. 三件事与判定线（北京时间）

| # | 事情 | 前置 | 判定线 |
|---|---|---|---|
| **T1** | 租 4090 跑 GPU 取证（路线 A：锁版本环境 + 真断网 `unshare -n` + 官方入口，40 题共享 raw） | 用户租机 + 给 SSH | **9/23 02:00** 前拿到 `gv_small.tgz`（含 `对拍摘要.txt` + `gates.tsv`）→ 过线则执行 T3；否则保持冻结、只交现有证据 |
| **T2** | 同一次租机**顺带**跑加固臂（纯 CPU，零额外 GPU 时间）：**只测不改** | 无（T1 同机） | 同 T1；拿到 §3.3 三个数即可 |
| **T3** | 若 GPU 证据/加固段要进包 → **第八次重打 + 门禁 + 重派发** | T1/T2 结果 + 时间余量 | **9/23 02:00** 前全绿；否则不动包 |

**当前交付状态（别再重做）**：
- 源码包 = **第七次重打·终版** `复现提交包/复现推理源码包_v5_20260921.zip`，**8,959,510 B** / SHA256 `58e1d2d117bf8f488a50d41a3a8cfdbda22aba0d39868eecd7ed50823b39ae84` / **86 条目**
- 镜像包 = `复现提交包/hy3d-repro_20260921.tar.gz`，23,867,134,532 B / `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914`（**未变动**，本次任何操作都不许改它）
- 上传夹 `复现提交包/上传百度云盘/` **12 项齐**；清单两份：`复现提交包/交付清单-SHA256.txt`、`上传百度云盘/交付清单-SHA256.txt`（内容一致）
- 材料死线 **9/23 24:00**；上传渠道 = 百度云盘；**实际上传 + 回填问卷仍是未闭合项**

---

## 1. 两个已核实前提（别重新论证，也别凭直觉推翻）

### 1.1 平台前提
- 极智算便宜档 4090（¥1.57/h）是**容器实例**，实例内**跑不了 docker**（嵌套容器）；能装 Docker 的只有裸金属整机（8×4090，¥264/天起）。依据：平台产品线页 + 包内 `cloud/租机执行清单.md:175`（我们自己早记过"实例上做不到容器级断网"）。
- 交付 tar **22.2 GiB**，本机上行实测 **0.22 MB/s ⇒ ≈29 小时** → 窗口内**不可能**把镜像搬到任何远端。百度云盘 SVIP 只加速百度侧，改变不了"本机 → 云实例"这一跳。
- ⇒ 唯一可行：**路线 A** —— 只传 9.6 MB 代码，19 GB 权重由云上自下；装 `requirements-lock.txt`（130 精确 pin）+ `reproduction/vendor/` 两个 wheel（**与交付镜像同版本、同文件**），并断言 `hy3dgen` 解析到 site-packages 而非仓库源码。**它不是"走上游 git 源码"**（那正是第二十节否掉的路径；源码对照是可选步骤 `[5] --with-repo`，本次**不开**）。
- ↕️ **一处已知口径冲突（不影响本作业单）**：用户 09-22 中午亲口说"初赛那台机器能装 Docker"，与本条前提复核（便宜档容器实例装不了）**冲突**（`session-handoff-3d-2026-09-22` 第二节有冲突表）。**冲突表怎么填都不改结论**：即便租到能装 Docker 的机器，**把 22.2 GiB 镜像搬上去这一步（≈29 h）依然是死结**，所以仍按路线 A 跑；唯一区别是那时可用容器级 `--network none`，而路线 A 用的是**更硬**的 `unshare -n`（命名空间内没有网络设备）。**不要为了"验证能不能装 Docker"在实例上多花一小时。**

### 1.2 ❗证伪：改包内默认值 ≠ 改官方那次跑分（2026-09-22 本机实测，硬证据）
- 官方 §3.5 运行形态 = **镜像加载 → 权重挂载 → 运行**（`官方要求核对与缺口清单-20260921.md:65`）；我方调用示例（`提交说明.md:75-80`、`reproduction/复现说明文档.md:96-100`）：

  ```bash
  docker run --rm --network none --gpus all \
    -v /abs/path/prompts.jsonl:/input/prompts.jsonl:ro -v /abs/path/out:/output \
    hy3d-repro bash run_infer.sh /input/prompts.jsonl /output
  ```
  —— **只挂 prompts 与输出目录，不挂源码包**；`bash run_infer.sh` 由镜像内 `/app/run_infer.sh` 解析（`reproduction/README-复现说明.md:144` 固定布局表）。
- 本机实测哈希（`docker run --rm hy3d-repro sha256sum …`）：
  - 镜像 `/app/run_infer.sh` = `2ed7b52acd8c07a0b9ddae7ece023816d50ee3fdc9f23444a135f34b2f1d05c9`，**与包内 `reproduction/run_infer.sh` 逐字节相同**
  - 镜像 `/app/build_submission.py` = `e1b66c38b145e5d36bb64c83a1310c6bea13efba177e859365e974362d6033d9`，**与包内 `pipeline/build_submission.py` 逐字节相同**
  - 镜像 `/app` 为平铺布局：`build_submission.py fetch_weights.sh generate_hy3d.py postprocess.py render_views.py run_infer.sh verify_weights.py`
- ⇒ **改包内 `run_infer.sh` 的默认值（`MAX_FACES`/`RENDER_SIZE`/`FDM_*`），对评委那次跑分零影响。** 要改评委跑分，只能改**镜像** → 重新 `docker commit`/重建 → 重新 `docker save | pigz` 22.2 GiB → 重传 + 重跑全部门禁。见 §3.1 的五条反对理由：**本窗口不做**。
- ⚠️ **危险点（本窗口最该避免的事故）**：`D:\wsl\tmp\dispatch6.py` 的一致性白名单只核对 5 个 `.py`（postprocess / render_views / build_submission / generate_hy3d / verify_weights），**不含 `run_infer.sh`**。只改包内 `run_infer.sh` 不会触发任何门禁，却会静默造成"包 ≠ 镜像"，两个复现路径产出不同产物。

### 1.3 加固参数本身有效 —— 正确用法是"评委可选覆盖"，不是改默认值
- 09-21 实测：`FDM_SETTLE_LAST=1` → `z_min` 归 0；`FDM_REQUIRE_SINGLE=1` → `dec_005` 修成单体、`con_010` 丢 4 件后仍 2 体并标 `single_component_failed`；`MAX_FACES=200000` 单题 → 177,372 面 / z_min 0 / PASS。
- 官方入口支持 `-e`（我们自己的断网实测就用 `-e INFER_PROC_ONLY=1`）⇒ 加固是**评委可选择施加**的可选项。
- 官方 §4 八条自查**不限制面数上限、不规定渲染分辨率** ⇒ 加固/提高上限的产物不违规。
- ⇒ 正确用法：**文档里的"可选覆盖"段 + 答辩素材**；默认值一个字节不改（§3.5）。

---

## 2. T1：租机取证（工具早已就绪，照着敲）

工具目录 `D:\wsl\tmp\gpu_verify\`（CLI 已逐一核准）：

| 文件 | 作用 |
|---|---|
| `gpu_verify.sh`（18.7 KB / sha256 前 16 `98e0fc1a9a7f4b51`） | 一键：`[0]`探针 `[1]`权重+校验门禁 `[2]`锁版本环境 `[3]`**两题冒烟（人眼门禁）** `[4]`全量 40 题阶段 1 `[5]`仓库对照(本次不开) `[6]`收集 |
| `gv_stats.py`（16.4 KB / `58f892498c1aebb9`） | 几何统计与对拍（glTF accessor 快路径，零内存，~0.5 s/文件） |
| `prompts40.jsonl`（21.4 KB / `b51bc27c97758eb4`） | 官方 7 键输入，顺序 = 初赛 40 题目录序 ⇒ 种子 42..81，可直接对拍 |
| `baseline_chusai_stats.json`（26 KB / `fe279f52376a73a0`） | 初赛 40 题 **raw 级**基线 |
| `baseline_chusai_model_stats.json`（16 KB / `f205b3a0dbd2d997`） | 初赛 40 题 **最终产物级**基线（已验证与《初赛40题产物体检报告》逐条吻合） |
| `pkg/`（9.6 MB） | v5 冻结包解压的 ASCII 顶层目录版（**内容零改动**） |

### 2.1 上传（本机执行）
```bash
scp -P <端口> gpu_verify.sh gv_stats.py prompts40.jsonl \
    baseline_chusai_stats.json baseline_chusai_model_stats.json root@<IP>:/root/gpu_verify/
scp -P <端口> -r pkg root@<IP>:/root/gpu_verify/
```

### 2.2 一键跑（全自动，含人眼门禁）
```bash
bash /root/gpu_verify/gpu_verify.sh --pkg /root/gpu_verify/pkg \
     --in /root/gpu_verify/prompts40.jsonl --work /root/gpu_verify --jobs 8
```
- **不要加 `--with-repo`**（需联网拉 f8db630 仓库；"轮子 2.0.2 vs 仓库 f8db630 的差异不在我们推理路径上"已于 09-22 逐处比对完毕）。
- 分步跑更稳：`--steps 0` → `--steps 1` → `--steps 2` → `--steps 3` → `--steps 4` → `--steps 6`。

### 2.3 人眼门禁（`[3]` 之后必须停下来看一眼）
`/root/gpu_verify/collect/smoke/<prompt_id>/` 里看 `t2i.png` 是不是干净概念图、`t2i_rembg.png` 是否去背、raw 非空、4 视图齐全。**不干净就停**（这说明等价环境有问题，别把 40 题硬跑完）。

### 2.4 回传
```bash
scp -P <端口> root@<IP>:/root/gpu_verify/gv_small.tgz .        # 几十 MB，含对拍摘要与日志
# 若磁盘与时间富余，再加 --pull-raw 出的 gv_raw.tgz（2 题 raw.glb，用于我方复核读数）
```

### 2.5 成功判据（4 条，都在 `collect/对拍摘要.txt` 与 `gates.tsv` 里）
1. 两题冒烟：图干净（人眼）+ 完成率 1.0 + 4 视图齐全
2. 40 题：完成率 ≥ 0.9、单题阶段 1 中位耗时 ≤ 1.5 分钟、尺寸全在 [2,300] mm
3. 对拍：面数一致、尺寸差 ≤ 3 mm、种子一致；**raw md5 全同 ⇒ 逐字节复现；md5 不同但几何一致 ⇒ 功能等价复现**（官方不要求逐字节一致，口径照实写）
4. 门禁无 FAIL（有 FAIL 先看详情再决定是否作废本次会话）

### 2.6 三条硬红线（其余失败分支见 [[GPU实测-交接与决策]] §6）
| 现象 | 动作 |
|---|---|
| 无 `nvidia-smi` / 无 GPU 直通 / 磁盘 < 60 G | **立刻关机重租**，不修 |
| `torch.cuda.is_available()==False` | **立刻关机重租**（环境问题修不出来） |
| 阶段 1 OOM（4090 24 G） | 记录 peak 显存 → 这是**评委也会撞的同一问题**，如实披露并给降配参数（steps/octree），不许隐瞒 |

---

## 3. T2：加固臂 —— 只测不改（同一次租机的 CPU 段，零额外 GPU 时间）

### 3.1 为什么不改默认值、不重建镜像（五条）
1. **无效**：评委跑的是镜像内 `/app/run_infer.sh`（§1.2 实测），改包内默认值对跑分零影响。
2. **要生效就得动镜像**：改镜像 = 重新导出 **22.2 GiB** + 重传（本机上行 0.22 MB/s）+ 重跑全部证据门禁（三题断网实测 + 40 题离线对拍）。
3. **会作废最强证据**：现有"40 题 × 4 视图 = 160/160 与初赛提交包**逐字节一致**"（`实测记录/14`）是在**当前默认值**（`RENDER_SIZE=1024`）下测得的。改默认值 → 这条证据的成立条件变了，等于拿"可复现性"这张王牌去换一点点画质。
4. **收益不确定**：面数/分辨率对评分的影响**没有实测数字**（§3.3 就是去把它测出来）。
5. **时间与风险不划算**：镜像两段式组装有已知卡死史（`docker commit` 的 PATH 拼接 bug），在死线前夜重建，正是"走弯路"。

### 3.2 两臂都在 CPU 上跑（A 臂 = 冻结默认 = 官方那一次）
```bash
cd /root/gpu_verify
G=/root/gpu_verify/gv_stats.py
PY=/root/lockenv/bin/python

# A 臂：冻结默认（= 官方入口跑的东西），40 题只走阶段 2，复用 [4] 产出的同一批 raw
INFER_PROC_ONLY=1 INFER_PYTHON=$PY INFER_RAW_DIR=/root/gpu_verify/raw \
INFER_WORK_DIR=/root/gpu_verify/work_A \
  bash /root/gpu_verify/pkg/reproduction/run_infer.sh \
       /root/gpu_verify/prompts40.jsonl /root/gpu_verify/out_A

# B 臂：加固 + 提高上限/分辨率（同 raw、同机、纯 CPU）
INFER_PROC_ONLY=1 INFER_PYTHON=$PY INFER_RAW_DIR=/root/gpu_verify/raw \
INFER_WORK_DIR=/root/gpu_verify/work_B \
MAX_FACES=200000 RENDER_SIZE=1536 FDM_SETTLE_LAST=1 FDM_REQUIRE_SINGLE=0 \
  bash /root/gpu_verify/pkg/reproduction/run_infer.sh \
       /root/gpu_verify/prompts40.jsonl /root/gpu_verify/out_B

# 统计（model → <work>/model_stats.json；compare → <work>/<label>.json|.txt）
$PY $G model   /root/gpu_verify/out_A /root/gpu_verify/prompts40.jsonl /root/gpu_verify/stA
$PY $G model   /root/gpu_verify/out_B /root/gpu_verify/prompts40.jsonl /root/gpu_verify/stB
$PY $G compare /root/gpu_verify/stA/model_stats.json /root/gpu_verify/stB/model_stats.json \
               /root/gpu_verify abA_vs_abB
$PY $G compare /root/gpu_verify/baseline_chusai_model_stats.json \
               /root/gpu_verify/stA/model_stats.json /root/gpu_verify chusai_vs_A
```
- 阶段开关是**环境变量** `INFER_PROC_ONLY=1`（`run_infer.sh:85`），不是 `--proc-only` 这种 flag。
- `INFER_PYTHON` 必须指向锁环境 python，否则会用系统 python。
- `run_infer.sh` 自身不 `export` `FDM_*`，但 `VAR=x cmd` 前缀赋值会进入子进程，`build_submission.py` 能读到 ✓。
- 每臂都记 `time` 总墙钟；逐题耗时优先取 `out_X/_logs/build_report.json`（字段不全就用总墙钟 ÷ 40）。
- **时间不够时的降级**：`head -n 12 prompts40.jsonl > prompts12.jsonl` 先跑前 12 题（前 12 题种子不变），只求相对倍数。
- ⚠️ 这两条 B 臂命令**只是临时覆盖**，不写回任何文件；这正是"只测不改"。

### 3.3 要拿的三个数 + 判据
| # | 数 | 采集点 | 判据 |
|---|---|---|---|
| 1 | 面数分布（是否真用满 20 万 / 被截断） | `stB/model_stats.json` | 若中位数仍远低于 200k ⇒ 说明上限不是瓶颈，杠杆②收益小 |
| 2 | `z_min` 是否 40/40 = 0 | `stB/model_stats.json` | 40/40 归零 ⇒ 加固①有效；否则查是哪几题 |
| 3 | 单题阶段 2 耗时倍数 = B ÷ A（**同机自我对照**，这是唯一可信的比法） | `time` 总墙钟 / `build_report.json` | ≤ 2× ⇒ 可写入文档；> 2× ⇒ 只保留 `FDM_SETTLE_LAST=1` 这一条 |
（现基线参照：本机纯 CPU 交付镜像内 40 题离线对拍，单题阶段 2 **中位 28.5 s / 最大 43.3 s**。**不要把租机的绝对秒数替换包内文档的本机数字**——口径不同，只引用"倍数"。）

### 3.4 附：`FDM_REQUIRE_SINGLE=1` 单独看
B 臂里它是 0（避免混入"丢件"变量）。若要评估它，另跑一小段：`head -n 12` 的 12 题 + `FDM_REQUIRE_SINGLE=1`，看 `body_count` 与是否出现 `single_component_failed`。**注意 `con_010` 在初赛会丢 4 件**——若题面明确要求"折线肋连接"之类结构，丢件会伤语义，**别盲目开**。

### 3.5 拿到数之后的三种处置（按结果选，只选一种）
| 情形 | 动作 | 代价 |
|---|---|---|
| A/B 全达标（判据 1~3 都过） | ① 在 `reproduction/复现说明文档.md` 与 `reproduction/README-复现说明.md` 增一节**「可选加固参数（评委可自行施加）」**：命令 + 实测数字 + 耗时代价 + "默认值与镜像内一致、不改"的声明；② 把 GPU 证据与加固数字写进 `方案文档.md` §七证据索引 + `实测记录/16` | 触发 §4 **第八次重打**（约 1~2 h）+ 重传 zip（8.9 MB，秒级） |
| 只有①②达标、耗时爆掉 | 同上，但可选覆盖**只写 `FDM_SETTLE_LAST=1`**（零语义风险那条） | 同左 |
| 不达标 / 没拿到数 | **不进包**：加固数字只进包外的 `D:\文本生成3D方案赛\决赛答辩准备\答辩讲者手册.md`（零重打），作为答辩"工程严谨性"素材 | 零 |

---

## 4. T3：第八次重打 runbook（**只在决定改包内文件时**执行）

### 4.1 触发条件
T1 证据要进包、或 §3.5 决定写入"可选加固"段 → 必须重打；**镜像 tar 与上传夹其他件零改动**。

### 4.2 打包
- staging 目录：`D:\wsl\work\pkg5\复现推理源码包`（zip6.py 的输入；**先确认它就是 7 次重打的来源**）
- 打包脚本：`D:\wsl\tmp\zip6.py`（用 Windows `py` 跑）。**⚠️ 它已落后两版**：现在 needle 里是第 4/5 次的值（`d746631c…` / `7,960,946` 与 `e0db7d9d…` / `8,768,569`），而**第七次重打是并行 session 用别的方式打的**。动手前先 `grep -rln "8,959,510\|58e1d2d1" /d/wsl/tmp/*.py` 找出实际用的那份；若仍用 `zip6.py`，必须先把 needle 更新为**第 6/7 次的值**：
  - sha：`102906910e20cd8b86b0fe5dd8bb8eda4ab9756641a5ab4abff589bfcdd5465d`（第 6 次）与 `58e1d2d117bf8f488a50d41a3a8cfdbda22aba0d39868eecd7ed50823b39ae84`（第 7 次，自身）
  - 体积：`8,768,573` / `8768573` 与 `8,959,510` / `8959510`
  - 并把新增证据追加进 `must` 列表（现含 7 条：方案文档、提交说明、PPT 三件、复现说明文档、`实测记录/14_初赛提交版几何离线对拍.txt`）
- 打包输出：`D:\文本生成3D方案赛\复现提交包\复现推理源码包_v5_20260921.zip`（**同名覆盖**）
- 打包后必须核：条目数（86 → 新值）、`testzip` OK、disk↔zip 逐文件 md5 一致、无权重二进制（`.safetensors/.onnx/.pth/.bin/.glb`）/无 `__pycache__`/无零字节、文本条目 utf-8 可解码、**自指扫描 0 命中**（包内任何文件不得记录包自身哈希与体积）。

### 4.3 一致性核对（`D:\wsl\tmp\dispatch6.py`）
1. 它的第 1 段：包内 5 个源文件 md5 **必须与镜像 `/app` 相同**——`postprocess.py e067e6f8…`、`render_views.py 4881bb9e…`、`build_submission.py 2058b50e…`、`generate_hy3d.py a0b6ce19…`、`verify_weights.py 989a093c…`。**任一项 DIFF = 你动了不该动的文件 / 镜像里是旧版 → 停下报告，不要改门禁的期望值。**
2. 它的第 2 段：派发 `01_`（zip）+ `06_`（PPT 三件）到上传夹并核对逐字节相同。
3. **它不覆盖 `04_`/`05_`**：若改了 `reproduction/复现说明文档.md` 或 `方案文档.md`，必须手动重拷到
   `上传百度云盘/369583+default13319669_04_复现说明文档.md`、`..._05_方案文档.md` 并核对逐字节相同（清单里已声明"逐字节相同"）。

### 4.4 清单与终局门禁
- 两份 `交付清单-SHA256.txt`（`复现提交包/` 与 `上传百度云盘/`）同步为**第八次重打**的字节数/SHA256/条目数/说明段。
- `D:\wsl\tmp\final_audit.py:11` 附近的期望值是**人工抄录自清单正文**的 → 必须同步，否则它会按旧值判 FAIL。
- 其余门禁照跑：`mkupload.py`（生成 `03_` 权重地址清单 + 校验 `01_` 的 sha 等于清单第 2 行）、`verify_upload.py`（上传夹清单）、`gate_zip_vs_upload.py`、`gate_cross_final.py`、`check_final_state.py`。
- 更新 `上传百度云盘/上传说明-百度云盘.md` §五（终值表）。

### 4.5 新增证据的编号
`实测记录/` 现有 **00–15**（15 = `15_初赛40题产物体检报告_20260921.md`）⇒ 新的 GPU 实测编号为 **`实测记录/16_GPU端到端断网实测.md`**（内容是 `gv_small.tgz` 里的 `collect/对拍摘要.txt` + 关键门禁 + 人眼门禁结论；**不要在包内记录包自身哈希**）。

### 4.6 改完必须重传
上传渠道 = 百度云盘；改包后**旧的网盘文件与问卷答案都作废**：重新上传 → 回填问卷。**这是本窗口最后一个未闭合项**（另有"百度网盘单文件上限未证实"，tar 走 `02_…生成分片.bat` + `合并分片.bat` 分片路径）。

---

## 5. 口径同步面（改包时按此 grep，别漏）

### 5.1 关于 160/160 的正确口径
现句子（"40 题 × 4 视图 = 160/160 张 PNG 与初赛提交包 `renders` 逐字节一致"）所在：
- `实测记录/14_初赛提交版几何离线对拍.txt:183,247,282`
- `reproduction/复现说明文档.md:143,152,178,183`
- `方案文档.md`（§七证据索引）、`答辩PPT/说明.md`
- 上传夹副本：`04_复现说明文档.md`、`05_方案文档.md`、`06_答辩PPT_说明.md`、`上传说明-百度云盘.md`

**正确表述（若 §3.5 写入"可选加固"段，必须同时加这句限定）**：
> 上述 160/160 逐字节一致是在**交付默认值**（`MAX_FACES=120000` / `RENDER_SIZE=1024` / FDM 加固关闭）下测得；若施加"可选加固参数"，渲染分辨率与几何会随之变化，该条不再逐字节成立——**这是评委可自行选择的可选覆盖，不是默认行为**。

### 5.2 grep 命令（在 staging 目录 `D:\wsl\work\pkg5\复现推理源码包` 下跑）
```bash
grep -rn "160/160" .
grep -rn "逐字节一致" .
grep -rn "120000\|12 万\|200000\|1024\|1536" . | grep -v "verify_weights\|FREE_K\|__pycache__"
```
（最后一条会命中一批**无关上下文**：`verify_weights.py` 的 `300*1024*1024`、`run_generation.sh` 的 `1024/1024` 等，只改"面数上限 / 渲染分辨率 / 默认值"语义的句子。）

### 5.3 **不要碰**的字样
`交付清单-SHA256.txt` 与 `上传工具-自测日志.txt` 里的"逐字节一致"是**分片/合并自测**的措辞（与复现无关）。别把它们改掉。

---

## 6. 禁做清单（No-Go）
1. **不改任何默认值**（`run_infer.sh` / `build_submission.py` 的 `MAX_FACES`/`RENDER_SIZE`/`FDM_*`），**不重建、不重新提交镜像**。
2. 不在实例上装 Docker、不试图 `docker load` 交付 tar（22.2 GiB / 0.22 MB/s ≈ 29 h，做不到）。
3. 不把 `hy3d-repro_20260921.tar.gz` 往任何远端传（它的哈希必须保持 `8c2668ac…`）。
4. 本次**不开** `--with-repo`（f8db630 仓库对照），除非时间明显富余且明确要这个对照。
5. 发现门禁 DIFF 时**先停下报告**，不许改门禁脚本的期望值去"通过"。
6. 不在租机上做任何"顺带改进"：不换模型、不调 `steps`/`octree`/`guidance`、不改 prompts、不试别的仓库版本。
7. 不动 `复现提交包/` 里除"两份清单 + 上传夹规定件"以外的东西；删除/覆盖前先只读确认范围、精确具名，**禁止宽泛通配**。
8. 密码/密钥只在对话里，**不许写进任何文件**；实例用完按平台流程关机退租（不跑任务时不要挂着计费）。

---

## 7. 诚实边界（必须保留的措辞，不许拔高）
- 阶段 1 的**真 GPU 全链路在本窗口仍未实测**。若 T1 跑通，措辞升级为：
  > 在**锁定依赖的等价环境**（`requirements-lock.txt` 130 pin + `reproduction/vendor/` 两个同版本 wheel）**+ 真断网 `unshare -n`** 下实测通过；与交付镜像的软件一致性由 `/app` 5 个源文件 md5 与 `run_infer.sh` sha256 **逐字节核对**支撑。
  **不要写成"官方镜像已全链路实测"**（除非真的在镜像内跑了 GPU，那需要能跑 Docker 的 GPU 主机）。
- 镜像**自足性**已实测（删除本机镜像后由 tar 单独 `docker load` 还原同 ID/同层数并跑通单题）——这条可以讲。
- 百度网盘**单文件上限未证实**：如实写"镜像包以分片提供（`02_…生成分片.bat` / `合并分片.bat`）"。
- 初赛 3.15 分 / 第 9 名是**压线晋级**，语义是明确弱项 —— 封面别把 3.15 当门面数字（沿用第二十一节结论）。