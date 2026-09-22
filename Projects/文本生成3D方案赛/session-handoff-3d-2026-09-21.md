---
title: 09-21 交接（平台镜像过期 → 本机重建路线，权重下载清单已就绪）
---

# 2026-09-21 会话交接

> 前置阅读：[[文本生成3D方案赛-主索引]]、[[session-handoff-3d-2026-09-20]]。本文件记录 09-21 的新事实与改定路线。

## 一、关键转折：平台镜像已失效

- 用户在极智算控制台确认：此前保存的实例镜像 **`hy3d-t2i-fixed` 已到期被平台清理**。
- 影响：09-20 交接「第九之三」的**路径 A（云 pull → save → 下载）彻底作废**，18G 权重与云端环境都取不回来了。
- 改定路线：**路径 B（本机重建）**——本机重新下载权重 → 本机 `docker build` → `docker save | gzip` → 交付离线镜像包；顺带在本机做 `--network none` 断网实测（官方评测环境同构）。
- 决策依据：权重全部是公开可再下载的，且本机 D 盘余 185G，时间窗口 09-21~09-24 足够（下载 ~2.5~3.5h + 构建/导出 ~1~2h）。

## 二、权重下载清单（已生成，用户手动下载中）

清单位置：**`D:\hy3d_weights\手动下载清单.md`**（+ `下载直链.txt` 给 IDM/迅雷/aria2 导入 + `一键下载.bat` 用 Windows 自带 curl 断点续传）

**共 23 个文件 / 18.92 GB**，全部来自 hf-mirror（2026-09-21 逐个实测 HTTP 200，Content-Length 与仓库索引逐字节一致）：

| 模块 | 来源仓库 | 文件数 | 体积 | 落位（本地）→ 镜像内 |
|---|---|---|---|---|
| 文生图 t2i | `Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled` | 18 | 14.49 GB | `download\t2i\` → `/root/models/t2i` |
| 形状 shape | `tencent/Hunyuan3D-2mini`（dit-v2-mini + vae-v2-mini） | 4 | 4.25 GB | `download\shape\` → `/root/models/shape` |
| 去背景 | `Gulraiz00/u2net`（u2net.onnx，md5 `60024c5c889badc19c04ad937298a77b`） | 1 | 0.18 GB | `download\u2net\` → `/root/.u2net/u2net.onnx` |

**不必下载（省约 20 GB）**：3B 形状 `hunyuan3d-dit-v2-0`（4.9G）与纹理链 `hunyuan3d-paint-v2-0 / delight`（约 15G）——复现镜像与 `run_infer.sh` 均不使用，初赛最终提交也未用纹理。（09-08 那份 30.4GB/53 文件的 manifest 是当时"全量备着"的清单，含这些用不上的部分。）

备用源：HuggingFace 官方（把域名换成 `huggingface.co`，路径一致）；ModelScope `AI-ModelScope/HunyuanDiT-v1.1-Diffusers-Distilled` 与 `AI-ModelScope/Hunyuan3D-2mini`（实测 200，但历史上有"零占位"事故，走这条会做零张量校验兜底）。

## 三、本机环境实测（09-21）

- 磁盘：D 盘余 **185G**（权重 18.9G + 镜像/中间产物约 40G，够），C 盘余 46G（**Docker 数据目录必须迁到 D 盘**）。
- **Docker：未安装**；WSL 平台存在（默认版本 2）但**未安装任何发行版**。
- ⚠️ **Docker Desktop 在本机装不了（09-21 实测硬结论）**：`D:\Docker\Docker Desktop Installer.exe`（4.76.0）退出码 1，其管理端日志 `C:\ProgramData\DockerDesktop\install-log-admin.txt` 明确写：
  > `Prerequisite failed: We've detected that you have an incompatible version of Windows.` / `Docker Desktop requires Windows 10 Pro/Enterprise/Home 22H2 (19045) or above.`
  本机为 **Windows 10 Enterprise LTSC 2021 = build 19044**，LTSC 通道**不会**升到 19045 → 换任何 Docker Desktop 版本前必须确认其最低系统要求，**正解是绕开 Desktop**：WSL2 发行版内装 docker engine（无 OS 版本门禁）。相关脚本 `D:\Docker\装WSL发行版.bat`、`D:\Docker\清理卡死WSL.bat`（`wsl --install` 实测卡死 7 分钟无产物，已弃用，改 rootfs 导入）。
- Python 3.14.3；`huggingface_hub` 1.25.1 已装（下载时仍应设 `HF_HUB_DISABLE_XET=1`）、`modelscope` 未装（本路线不需要，全走 hf-mirror）。
- 下载链路已实测可用：`curl.exe -L -C -` 直下 hf-mirror 成功（且 Windows 自带 curl 8.18，无需装任何工具）。

## 四、本机改动（09-21，Dockerfile 离线缺陷修复）

`reproduction/Dockerfile`：

1. **u2net 改为优先用构建上下文文件**：原先固定在构建期 `wget` 抓 hf-mirror → 真断网构建必失败；现改为先取 `reproduction/weights/u2net/u2net.onnx`（随上下文进镜像），缺失才联网抓，md5 校验保留（`60024c5c…`）。
2. **权重门禁重写**：原门禁「任一零张量即失败」会误杀合法的 `hunyuan3d-dit-v2-mini`（其内置 VAE 段已知为零占位，靠 `--vae-subfolder` 覆盖）→ 现改为 ① 7 个关键大文件按**精确字节数**核对（防截断/张冠李戴）；② 逐文件零张量分析：**整文件全零 = 占位权重 → 构建失败**；部分零段只告警（并打印明细）。

权重放置说明补齐：`reproduction/weights/{t2i,shape,u2net}/README-权重放置.txt`（含直链格式、字节数、镜像内目标路径、VAE 零占位说明）。

⚠️ **`复现提交包/复现推理源码包_v1_20260920.zip` 内的 Dockerfile 已过时** → 构建验证通过后必须重新打包源码包再提交。

## 五、下一步（按顺序）

1. 用户按清单下载 18.92 GB 到 `D:\hy3d_weights\download\`（下载中）
2. ZCode：逐文件核对字节数 → safetensors 零张量扫描 → u2net md5 → 落位 `reproduction/weights/`
3. **需用户动手（管理员）**：`wsl --install --no-distribution` → 装 Docker Desktop → 数据目录迁到 D 盘 → `docker --version` / `docker run --rm hello-world` 验证
4. ZCode：`docker build -f reproduction/Dockerfile -t hy3d-repro .` → 镜像内跑 `--network none` 断网 + 官方入口实测 → `docker save | gzip` 产出离线镜像包
5. ZCode：重打源码包（含新 Dockerfile）→ 更新 `提交说明.md` 实测记录（把 09-20 那批"未验证项"换成真结果）→ 09-24 前提交
6. 仍待问组委会（开放问题）：Docker 镜像**体积上限**与提交渠道（平台上传/网盘）、单题推理时限、答辩 PPT 与方案文档是否同窗口提交

## 六、风险

- 权重下载期断流（hf-mirror 每 7~9 分钟断流的历史规律）→ 断点续传可续，清单文件字节数逐条核对为准
- Docker Desktop 安装需管理员权限与可能的重启 → 建议与下载并行进行，不占用等待时间
- 本机无 GPU：镜像构建与 CPU 链路断网实测可做，**GPU 生成链路仍无法在本机断网实测**（若需真机验证只能再租实例，非必需——官方评测环境自会跑）
## 七、提分加固 L2 已实装并实测（09-21 上午，另一并行 session 追加）

> 背景：初赛 40 题产物逐题体检（详见 [[session-handoff-3d-2026-09-20]] 第十二节与 `output_test/初赛40题产物体检报告_20260921.md`）。

**实装（`pipeline/postprocess.py` + `pipeline/build_submission.py`，全部默认关闭 → 复现输出与初赛提交逐题一致）**
- `settle_last`（环境变量 `FDM_SETTLE_LAST=1`）：所有修复/减面结束后**再贴地一次**
- `require_single`（`FDM_REQUIRE_SINGLE=1`）：单体门禁——先焊接，再丢碎件，仍为多体则如实标记 `single_component_failed`（不静默交付）
- 面上限/渲染分辨率本就可用 `MAX_FACES` / `RENDER_SIZE` 环境变量调（无需改代码）
- `validate()` 新增 `quality_warnings`（多部件 xN / 悬空 z_min≠0），**不参与官方门槛判定**，只暴露问题

**关键证据：缺陷机制被逐阶段追踪抓到（真实 714 万面 raw）**
```
   settle_base   z_min -1.015 -> 0.000     ← 贴地
   decimate      z_min  0.000 -> 0.084     ← 减面又把底面抬起 88µm
   heavy_repair  z_min  0.084 -> 0.084
   交付(关闭加固) z_min = 0.084mm           ← 悬空
   交付(开启加固) z_min = 0.000mm           ← 终末贴地修好
```
→ 即 hid_sma_001 交付悬空 6.64mm 的同类机制（其链路在贴地后又被减面/重修复改变几何，幅度更大）。

**真实缺陷产物对照（关/开加固）**

| 题号 | 原缺陷 | 关闭加固 | 开启加固 |
| --- | --- | --- | --- |
| hid_sma_001 | 悬空 6.64mm | 1 体 / z_min 0.0 | 1 体 / z_min 0.0（不变） |
| hid_con_010 | 6 分离体（题面要求"通过肋连接"） | 6 体（原样） | 丢 4 件后仍 2 体 → **标记 failed=True**（不假装单体） |
| hid_dec_005 | 2 分离体（最大件 95.6%） | 2 体（原样） | **1 体**（丢 1 碎件）/ 水密 |
| hid_con_002 | 正常 | 1 体 | 1 体（不变） |

**默认关闭回归**：`hid_con_002`/`hid_con_010`/`hid_dec_006` 的件数（1/6/2）与面数（12 万）与原提交**逐题一致** → 复现包行为未被改动。

**官方入口端到端（`bash reproduction/run_infer.sh`，1 题，噪声 raw 714 万面，`MAX_FACES=200000 FDM_SETTLE_LAST=1 FDM_REQUIRE_SINGLE=1`）**
- 完成率 1.0 / 门槛 ≥0.9 → PASS（退出码 0）
- `final_faces` **177,372**（>12 万 → 上限提升确实生效）、`final_z_min_mm 0.0`、`final_parts 1`、水密 True
- `build_report.json` 新增字段齐全；`process.md` 写入"加固: 终末贴地；加固: 单体门禁"；单题耗时 304.5s（噪声 raw 比真实 raw 更重）

**待办**：`复现提交包/复现推理源码包_v1_20260920.zip` 内的 `pipeline/*.py` 副本已过时（与第四节 Dockerfile 同类问题）→ 重打包时一并更新。

## 八、租机时段预算 + 上机前准备（09-21 补，回答"3~4 小时够吗"）

**结论：3~4 小时不够；按 6 小时窗口租，实际约 4.5~5.5 h（N=4 候选）；按此前记录的 4090 档 1.6~2 元/h 约 10~13 元。提前做完提前关机，窗口留足不花钱，中途续租/重开才浪费（18.92 GB 要重下）。**

时间预算（全部有实测出处）：

| 阶段 | 耗时 |
|---|---|
| 开机 + SSH + 传代码 | 10~15 min |
| 装依赖（基础镜像须为 PyTorch 2.3.0 + CUDA 12.4.1 + py3.10） | 10~20 min（选错 +20 min） |
| 下权重 18.92 GB（4~6 连接脚本） | 15~45 min |
| 权重校验（18.9 GB 读盘 + 零张量） | 3~6 min |
| 冒烟 1 题 + 人眼 | 5~10 min（单题生成实测 **0.50 min** 中位，n=40） |
| 多候选生成 | N=2 → 40 min；N=4 → 80 min；N=6 → 120 min |
| 断网等价实测 | 10~20 min |
| 回传（胜出候选 raw 40×153 MB ≈ 6.2 GB + t2i_rembg.png） | 15~80 min |

**候选数推荐自适应两阶段（省 40% GPU 时间）**：第一阶段 N=2 全 40 题（40 min）→ 本机筛弱项 ~14 题 → 只给这些题补 3 个候选（21 min）= 约 61 min，等效"弱题 N=5、好题 N=2"。靠 `--ids` + 跳过已有候选实现；候选种子按题目在全量题表中的位置固定，跨次补候选不撞种子。

**选优放在哪一侧 + 回传策略（09-21 二次修正）**：硬门禁要靠几何，选优必须和候选数据同侧。默认走**实例上选优**——生成跑完（GPU 已空闲）后跑 `pipeline/select_candidates.py --jobs 8`，只回传胜出者的 `raw.glb`（40×153 MB ≈ 6.2 GB）＋13 个弱项题的其余候选 raw（约 +2 GB，留人工重选余地）＋全部小文件（`selection.json`/`candidates.json`/`gen_meta.json`/`t2i_rembg.png`）；另一条路（全部候选 raw 回传、本机选优）只在「后处理单候选 > 2 min」时用——**冒烟阶段先量一次单候选后处理耗时**再决定。语义分不在实例上算：CLIP 对细粒度没有分辨力（见第九节），粗筛本机用 `t2i_rembg.png` 即可。

**上机前已就绪的工件（09-21 新增/更新）**：

- `cloud/generate_hy3d.py`：多候选模式（`--candidates/--seed-stride`、`candidates.json` 从磁盘重建、`raw_stats` 面数/包围盒/z_min）+ **候选种子改用全量题表位置**（修掉了 `--ids`/`--limit` 补跑时种子漂移的隐患）
- `cloud/download_weights.sh`：实例侧下载（读 `weights_manifest.json`，4~6 连接、断点续传、体积核对、`--fallback-hf` 域后备）
- `cloud/verify_weights.py`：字节数 + git-sha1/sha256 + safetensors 零张量扫描 + u2net md5；支持 `--layout models`（实例）与 `flat`（本机下载目录），**已在本机下载目录实跑通过**（当时 20/23 完整、3 个在下载中，合计 12.34 GB）
- `cloud/weights_manifest.json`：23 文件 / 18.92 GB 的官方元数据（字节数 + 摘要）
- `cloud/租机执行清单.md`：逐条可复制的实例操作序列 + 关机前清单
- `pipeline/score_semantic.py` 加了 `--jobs`（渲染并行，本机标定从 ~60 min 压到 ~10 min）并修了 transformers 5.x 特征取用（投影特征在 `pooler_output`）

**断网实测的诚实边界**：GPU 时段只能证明"权重齐备 + 推理不依赖网络"（`HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE` + 无效代理/端点，或 `unshare -n` 若可用）；容器级 `--network none` 的证明只能靠本机离线 Docker 镜像（CPU 侧）。两份证据合起来才覆盖官方断网环境，任何一份都不能单独宣称"断网跑通"。

## 九、09-21 上午续（另一 session）：本机容器运行时改道 WSL + 下载/交付包收口

> 与第八节（租机计划）并行推进，互不冲突：第八节是"GPU 全链路怎么在实例上跑"，本节是"本机怎么把离线镜像做出来并证明断网可跑"。

### 9.1 Docker Desktop 判死，改走 WSL2 + docker engine（关键结论，别重试 Desktop）

- 安装器 `D:\Docker\Docker Desktop Installer.exe`（4.76.0）**退出码 1**；其管理端日志 `C:\ProgramData\DockerDesktop\install-log-admin.txt` 原文：
  `Prerequisite failed: We've detected that you have an incompatible version of Windows.` / `Docker Desktop requires Windows 10 Pro/Enterprise/Home 22H2 (19045) or above.`
  本机 = **Windows 10 Enterprise LTSC 2021 / build 19044**，LTSC 通道**不会**升到 19045 → **任何 Docker Desktop 版本都要先查它的最低系统要求**。
- **已跑通的替代路线**：
  1. `wsl --install -d Ubuntu` 实测**卡死 7 分钟零产物**（放弃）；
  2. 下载官方 rootfs 再导入（稳）：`https://cloud-images.ubuntu.com/wsl/jammy/current/ubuntu-jammy-wsl-amd64-ubuntu22.04lts.rootfs.tar.gz`（341,130,963 字节；md5 `b1774445c2d93216eb0f5193293f6a53` 与官方 MD5SUMS 一致）→ `wsl --import Ubuntu2204 D:\wsl\ubuntu <rootfs>`（**必须用 PowerShell 调，Git Bash 会 mangle 路径**）；vhdx 在 `D:\wsl\ubuntu\ext4.vhdx`，不占 C 盘。
  3. `apt-get install docker.io` → **Docker 29.1.3**；`/etc/wsl.conf` 写 `[boot] systemd=true` → `systemctl start docker` = active；overlayfs / cgroup v2 / 8 CPU / 9.7GB。
  4. `C:\Users\dfjq\.wslconfig` 改为 `memory=10GB / processors=8 / swap=8GB`（宿主 15.4GB / 12 逻辑核，默认只给 3~4GB，构建 19G 权重镜像不够）。
- **Docker Hub 直连不通**（`registry-1.docker.io` 超时）→ `/etc/docker/daemon.json` 配 `registry-mirrors`；实测 `/v2/` 可达：`docker.1panel.live`、`docker.m.daocloud.io`、`docker.1ms.run`、`docker.xuanyuan.me`、`hub.rat.dev`、`dockerproxy.net`（`nvcr.io` 亦可达）。`hello-world` 经镜像站**拉取+运行成功**。
- ⚠️ 当前唯一卡点：`nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04` 从 1panel 站拉到一半报 `httpReadSeeker: failed open: failed to discard to offset: unexpected EOF`（层已部分缓存，属断流可重试）→ 多站轮试脚本 `D:\wsl\get_base.sh`（1panel→daocloud→1ms→xuanyuan→rat.dev→dockerproxy→NGC 依次试，成功即 `docker tag` 回官方名，保证 Dockerfile 不用改）。
- **WSL 调用纪律（踩坑记录）**：脚本一律写文件放 `D:\wsl\`（WSL 内 `/mnt/d/wsl/`），用 `wsl -d Ubuntu2204 -u root -- bash /mnt/d/wsl/xxx.sh` 调用；**PowerShell 内联长命令必被引号解析搞坏**（本 session 试错 3 次，浪费约 10 分钟）。

### 9.2 权重下载与清单（本机）

- 进度：**21/23 已完成并核对字节数**，剩 `t2i/text_encoder_2/model-00001-of-00002`（4.99G）与 `t2i/transformer/diffusion_pytorch_model`（6.07G）。
- **看门狗** `D:\hy3d_weights\_staging\supervise.py`：只监控不自起（避免双写同一文件），curl 进程死掉或 **7 分钟字节数不增长**才 `-C -` 续传重启，并在 modelscope / hf-mirror 间轮换源；日志 `supervise_log.txt`。
- **`reproduction/weights_manifest.json` 已按权威字节数重建**：此前一版按"本机当前文件大小"生成，把在传文件的部分大小当成期望值（合计只算 6.13GiB、还谎报"0 个未完成"）→ 属错误产物已覆盖。现 23 条每条给「期望字节 + HF/hf-mirror + ModelScope 双直链」，`state/local_bytes` 显式标注"仅进度参考、不作校验依据"。
- `reproduction/verify_weights.py` 本机实跑：正确报出 2 个在传文件字节不符并 rc=1（错报 0 的版本已不存在）→ **门禁脚本本身可信**。

### 9.3 交付包收口

- **新包**：`复现提交包/复现推理源码包_v2_20260921.zip`（27 文件 / 63,299 字节）；**`v1_20260920.zip` 已删除**（内含旧 Dockerfile md5 `0c7a91e9…` ≠ 现行 `eb42db1b…`）。
- `提交说明.md` 已更新：§一 增补 `weights_manifest.json` / `verify_weights.py`；§二 体积改 14.49G/4.25G/0.18G + 新增「构建期权重硬门禁」；§四 形状来源改 `tencent/Hunyuan3D-2mini`（省约 17G 无用权重）；§五 目录树同步。
- 工作区洁净：`cloud/probe2~6.py`、`probe_shape.py` 移出工作区与交付包 → 归档 `D:\hy3d_weights\_staging\ws_archive\`。
- ⚠️ **v2 包可能仍落后于第八节的并行产出**（`cloud/download_weights.sh`、`cloud/verify_weights.py`、`cloud/weights_manifest.json`、`cloud/租机执行清单.md` 等是在我打包之后出现的）→ **最终提交前必须再同步一次并重打 v3**。

### 9.4 下一步（卡点排序）

1. 权重最后 2 个文件下完 → `verify_weights.py` 全绿 → 硬链接落位 `reproduction/weights/{t2i,shape,u2net}`（同盘硬链接，不额外占空间）
2. 基础镜像拿到（`get_base.sh`）→ `docker build -f reproduction/Dockerfile -t hy3d-repro .`（构建期门禁把关）
3. 镜像内 `--network none` 跑官方入口（`INFER_PROC_ONLY=1` + `D:\hy3d_offline_test\`）→ **必须保留日志/截图作为证据**
4. `docker save | gzip` 出离线镜像包 → 补 `提交说明.md` 实测记录 → 重打 v3 源码包
5. **GPU 全链路只能按第八节在 4090 实例上做**（本机无 NVIDIA GPU）

## 九·B、中文 CLIP 标定结果（另一 session 并行产出，与上一节编号并列，非同一件事）

数据：初赛 40 题**已交付产物**（`D:\文本生成3D方案赛\output_test\*` 的 model.glb 拷到临时目录），每题渲染 512px 透视图，用 `OFA-Sys/chinese-clip-vit-base-patch16`（本机离线权重，临时目录 `%TEMP%\cc_model`，753 MB）算题面↔渲染余弦。

**判别力测试（40 选 1 认出自己的题面）**：

| 指标 | 实测 | 随机基线 |
|---|---|---|
| top-1 | 7/40 = **18%** | 2.5% |
| top-5 | 25/40 = **62%**（清洗题面）／20/40 = 50%（原始题面） | 12.5% |
| 平均排名 | 8.3 / 40 | 20.5 |
| 自配 vs 错配相似度中位 | 0.4273 vs 0.3875 | — |
| 人工判定 8 个语义弱项平均排名 | **9.0** | 其余 32 题 8.1 |

**结论（重要，直接改变 L1 设计）**：CLIP 有真实全局信号，但**分不开我们自己产物之间的语义强弱**（弱项 9.0 vs 其余 8.1）。因此：

1. L1 候选选优的主判据 = **硬门禁（水密/贴地/尺寸/非噪声/单体）+ 人工抽检**，不是 CLIP；
2. CLIP 只保留：粗筛明显跑偏的候选、门禁打平时的并列裁决（代码与用法已写进 `pipeline/select_candidates.py` 与 `score_semantic.py` 的文档字符串，避免以后误用）；
3. 语义分真要提升 → 走 **L3 t2i 提示词工程 + 人工挑选**（这也是第二阶段补候选名单（13 题）的依据来源：硬门禁失败 5 题 + 人工目检语义弱 8 题，见 `cloud/租机执行清单.md` 第一节）；
4. 标定样本局限如实记录：n=40、人工标注是单人二值判断、只测了一个 CLIP 变体——所以只能说"这一个 CLIP 变体在细粒度上不可用"，不能说"所有语义打分器都没用"。

## 十、上机就绪状态（2026-09-21，等用户租机）

### 状态一句话（11:24 更正）

**用户尚未租机**（原记录"已开机一台空白 4090 实例"是我误记——09-21 11:24 用户明确说"我还没租服务器呢"）。历史端点全部失效，所以现在**卡在"用户去租一台 4090"这一步**；本机上机工件已全部备齐，租好并把 SSH 命令发来即可一键推进。

### 1. 连接阻塞（唯一待用户给的输入）

- 历史端点**全部失效**（已实测）：`183.222.230.10:40064` / `:40039` 连接超时；`222.211.217.183:40059` 拒绝连接（均为 09-06 / 09-07 旧实例）。
- 用户侧动作 = 工作区 `租极智算GPU-你只需做这3步.txt`（已按 09-21 结论更新：**数据盘 ≥80 GB 可用**、跑完**先关机、等数据全部回传再释放**）。
- 需要用户在对话里贴：**控制台那条 SSH 登录命令**（`ssh -p <端口> root@<IP>`），以及**是否已把本机公钥** `C:\Users\dfjq\.ssh\autodl_hy3d.pub` 粘进实例（未粘贴则密码也只在对话里给，绝不写入任何文件）。

### 2. 本机已就绪工件（实例是空机也能跑）

| 工件 | 作用 |
|---|---|
| `%TEMP%\hy3d_upload.tgz`（**66,557 B / 189 条目**，sha256[:16]=`6d6a2dbeaff3aa42`，11:55 最新重建，含新守卫与《上机避坑清单》） | 待上传包：`cloud/` + `pipeline/` + `prompts/`（81 题面），解包即用；已排除 `__pycache__` |
| `cloud/instance_setup.sh` | **空白机 7 步一键装机**：GPU/磁盘 → python+torch 版本核对 → HF 镜像环境（含 `HF_HUB_DISABLE_XET=1`）→ 15 秒测速 → clone Hunyuan3D-2 并 `git checkout f8db630` + 依赖 → 下权重 → `verify_weights.py` 硬门禁；`bash -n` 通过 |
| `cloud/run_generation.sh`（新增，11:17） | **付费时段一键跑完生成+选优**（阶段A 全量 2 候选 → 阶段B 13 题弱项各补 3 候选 → 硬门禁选优），幂等可续、先过权重门禁再烧 GPU；`--dry-run` 只打印命令（本机已验证） |
| `cloud/weak_ids.txt`（新增） | 弱项 13 题名单（硬门禁失败 5 + 人工目检语义弱 8），供阶段 B 使用 |
| `cloud/download_weights.sh` + `weights_manifest.json` | 可断点续传的 23 文件 / 18.92 GB 下载器（`--jobs` 多连接、`--fallback-hf` 换源） |
| `cloud/verify_weights.py` | 体积 + digest + safetensors 零张量扫描 + u2net md5（测试通过） |
| `cloud/租机执行清单.md` | 操作手册：第 0.5 步网络判据、时间预算表、13 题弱项补候选名单、关机清单、断网诚实边界；**第 3 节已改为"一键脚本"版命令** |

**阶段 A/B 的接口已用 stub 测试锁死（11:19 全绿）**：`%TEMP%\mc_test2.py`（stub 掉 GPU 管线）验证：阶段A 5 题×2 候选种子 `[42,1042,43,1043,…]`；阶段B `--ids 2 题 --candidates 5` 只跑 `cand_2..cand_4`（种子 2043/3043/4043/2045/3045/4045，与阶段A 不重复）、阶段A 产物 mtime 未被覆盖、`candidates.json` 仍含全部题（16 条）、重复执行不再生成任何候选。
⚠️ **踩坑记录（写进脚本注释了）**：阶段 B 不能用 `--candidates 1` 逐次补——那样产物会落到 `<out>/<pid>/raw.glb`，脱离 `cand_<k>/` 结构，下游 `select_candidates.py`（只认 `cand_*`）会漏掉这批候选；必须用 `--candidates 总数` 靠"已存在即跳过"来只补新候选。

### 3. 权重与网络结论（09-21 实测）

- **本机权重已下齐**：`verify_weights.py --skip-zero` 复验 **23/23 体积通过，18.92 GB**（权威副本 `D:\hy3d_weights\download\`）。→ 因此"本机下好再传上去"不再是必需路线，只在实例下载极慢时作为备选。
- **网络经济学**：本机上行实测约 **0.22 MB/s**（40 MB / 183 s）→ 18.92 GB 全量上传约 **24 小时**，不可行；实例自下估计 **15~60 min**。故默认路线 = **实例自下**。
- **1 分钟判据（上机第 0.5 步）**：`curl` hf-mirror 单文件 20 秒测速——实例下载 **≥5 MB/s → 实例自下**；**<1 MB/s 且本机上行实测 ≥5 MB/s → 改本机上传**。两边都慢时的兜底：关机保留数据盘（若平台支持），或实例上 build 镜像后回传 tar.gz。

### 4. 拿到 SSH 行后的动作顺序（不再需要额外决策）

1. 连通性 + `nvidia-smi` + `df -h`（要求 ≥60 GB 可用）；
2. 15 秒测速 → 定下载 / 上传路线；
3. `scp` 上传 tgz 并解包（67 KB，秒级）：`tar xzf hy3d_upload.tgz -C /root/hy3d`；
4. 空白机一键装机：`cd /root/hy3d && bash cloud/instance_setup.sh --weights-jobs 6`（内部已含"下权重与依赖并行 → 权重硬门禁 → 打印冒烟命令"）；
5. 冒烟 1 题（`--limit 1 --candidates 1 --no-texture --vae-subfolder hunyuan3d-vae-v2-mini`）+ **人眼看** `t2i.png` / `t2i_rembg.png`；
6. 断网等价实测（离线环境变量 + 日志无下载字样；`unshare -n` 可用则更硬）；
7. **一条命令跑完生成+选优（≈61 min）**：`nohup bash cloud/run_generation.sh --prompts prompts/test --out /root/session/raw --phase all --n-a 2 --n-b 3 --jobs 8 > /root/session.log 2>&1 &`——阶段A 40 题×2 候选（≈40 min）→ 阶段B 13 题弱项各补 3 候选（≈21 min）→ 硬门禁选优；中断后重跑同一命令即续做；
8. 回传胜出候选 `raw.glb` + 全部小文件（≈8 GB，视下行）；本机跑后处理 + 四视图渲染 + 打包；
9. 关机前按清单核对（权重权威副本在本机，**勿依赖平台镜像**——已过期一次）。

### 5. 本机侧并行进展（与第九节联动，11:13 更新）

- **权重已下齐**：`verify_weights.py --skip-zero` 复验 **23/23 体积通过、18.92 GB** → **第九节 9.4 第 1 步的卡点解除**，可做硬链接落位 `reproduction/weights/{t2i,shape,u2net}`。
- **Docker 路线已定，不是 Desktop（11:30 更新）**：第九节 9.1 已判死 Docker Desktop（本机 Win10 LTSC 19044 < 要求 19045）→ 改走 **WSL2（Ubuntu2204）+ docker.io 引擎**，已 active；**基础镜像 `nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04` 已通过 NGC 拉入（15 GB，tag 回官方名）**，原先的"层断流"卡点已解除；**`docker build -f reproduction/Dockerfile -t hy3d-repro .` 自 11:26:47 起在跑**（legacy builder 不支持 `--progress`；进程 `docker build` PID 628 存活，日志 `D:\wsl\build_log.txt`，预计 20~40 min）。**所以"实例上 build 镜像再回传"只是备选**，主线仍是本机 WSL 构建（这样 `--network none` 的离线证明才算数）。
- **多 session 协作约定（重要，防撞车）**：本工作区当前有 3 个 session 并行（①本 session＝GPU 上机准备与交付包；②"sess_55120b3c"＝Docker 镜像构建与离线实测；③"sess_71a196d8"＝权重下载与校验，已完成并追加第十一节）。分工：**下次重打源码包只做一次**——由 Docker session 在镜像构建 + `--network none` 实测 + `提交说明.md` 实测记录补完之后统一重打（v4），**本 session 不再单独重打**，避免出现两个互相矛盾的 zip；GPU 上机相关文件（`cloud/*`）由本 session 维护。
- **交付包已重打成 v3**：`复现提交包/复现推理源码包_v3_20260921.zip`（27 条目 / 67,741 字节），**v2 已删除**（v2 内含三处过期文件：`pipeline/score_semantic.py` 4264→6526、`pipeline/select_candidates.py` 12950→13795、`reproduction/Dockerfile` 5676→7215；均已同步为磁盘实测版）。v3 与磁盘 staging 逐条字节一致（已校验）。
- **包内范围决策（避免歧义）**：`复现推理源码包` 只放"评测方要跑的东西"（`reproduction/` + `pipeline/` + 生成端 `cloud/` 既有脚本）；**GPU 时段用的运维脚本不进包**——`cloud/download_weights.sh`、`cloud/verify_weights.py`、`cloud/weights_manifest.json`、`cloud/instance_setup.sh`、`cloud/租机执行清单.md` 留在工作区。包内 `reproduction/verify_weights.py`（构建期门禁，7 个关键文件 + safetensors 零张量扫描，被 Dockerfile 调用）与工作区 `cloud/verify_weights.py`（实例侧全 23 文件 + digest，支持 flat/models 布局）**是两份不同用途的校验器**，字节数均取自同一份 09-21 官方清单；改一处必须同步另一处。

### 6. 仍开放的两项

- **镜像构建进行中**：`docker build` 自 11:26:47 在跑 → 构建成功后镜像内 `--network none` 跑官方入口并留证（第九节 9.4 第 2~4 步）→ `docker save | gzip` → 补 `提交说明.md` 实测记录 → **由 Docker session 统一重打 v4 源码包**。
- **问组织方**（仍未答复）：镜像大小上限、单题推理时限、PPT/方案文档是否同一提交窗口。


## 十一、权重下载与校验「全部完成」（09-21 11:35，权重专项 session 追加）

一句话：**23 个文件 / 18.92 GB 全部下齐，对 HF 官方哈希逐字节校验通过（23/23），已落位 `reproduction/weights/`。**
第十节第 5 条的"体积通过（--skip-zero）"到此升级为**内容级通过**。

已完成（均有日志实证）：
1. **全量哈希校验 23/23**：9 个大文件走 sha256、14 个配置/分词器小文件走 git-blob-sha1，哈希逐仓取自 HF 元数据。
   ⚠ 记住这个坑：**LFS 文件的 sha256 在 `X-Linked-Etag` 响应头，不在 `ETag`**（`ETag` 对 LFS 是另一套值）。
2. **第二道独立门禁**：`reproduction/verify_weights.py --root <权重目录> --u2net <...>`
   → 7/7 关键文件字节数通过、u2net md5 `60024c5c…` 一致、7 个 safetensors **零占位扫描通过、0 处零段告警**；
   落位到 `reproduction/weights` 后再跑一遍，同样全通过。
3. **落位**：`reproduction/weights/{t2i,shape,u2net}` 共 23 个文件（17.62 GiB），**同盘硬链接**（零拷贝、零额外占用）。
   源件在 `D:\hy3d_weights\download\`，与落位处是同一份数据（互为硬链接）。
4. **双击路径实测**：`D:\hy3d_weights\一键下载.bat`（无参数）→ 打印 `校验结果：23/23 通过`、`exit code = 0`。

过程中修掉的真事故（别再踩）：
- **并发写把文件写坏**：一个旧的 ModelScope 下载进程仍在往 `transformer/diffusion_pytorch_model.safetensors` 追加写，
  与新下载器撞车 → 文件被写到 6,178,586,760 字节（目标 6,066,290,824）、哈希不符。
  根因：查"外部写入者"的 PowerShell 调用因 GBK/UTF-8 解码异常抛错，被当成"没有外部进程"继续写（**失败方向是危险的那一侧**）。
- 修法：编码异常不再抛出；**查不到状态一律按"可能有写入者"处理（fail-closed）**；写每个文件前再查一次、有人写就跳过；
  文件超过目标长度先截断再校验；哈希不符的文件自动删除重下。重下后 23/23 通过。
- **双源轮换提速**：清单里 5 个大文件补了 ModelScope 备用源（逐个实测 HTTP 206 支持断点续传），
  相邻分块轮流走两个源 → 聚合实测 **6.4 MB/s**（单源单流 0.6~0.7 MB/s）。换源不影响可信度：哈希仍以 HF 官方值为准。
- **bat 的编码坑**：`.bat` 里 `echo` 带英文双引号的中文行会让 cmd 解析错乱（报 `'' is not recognized`）。
  现在 bat 里只保留 ASCII 提示、中文全部交给 Python 打印；文件 CRLF、无 BOM，控制台默认代码页 936 下实测正常。

对后续步骤的硬提醒（集成注意）：
- **重新打源码包时必须排除 `reproduction/weights/`**：那里现在是 18.9 GB 实体文件（不再是空占位），打进 zip 会炸包。
  `.dockerignore` 已正确保留它（构建要用），但 zip 打包是另一套流程，别漏。
- **`docker build` 的上下文现在是 ~19 GB**（Dockerfile `COPY reproduction/weights/ /root/models/`，上下文 = 仓库根），
  WSL2 侧建议预留 ≥25 GB（上下文 + 镜像层）。构建期门禁会跑 `verify_weights.py`，按上面实测会直接通过。
- 权重权威副本现在有两份（硬链接）：`D:\hy3d_weights\download\` 与 `reproduction\weights\`；删任一边不影响另一边。
- 文件地图新增（均在 `D:\hy3d_weights\`）：`一键下载.bat`（双击=续传下载+全量校验）、`下载全部权重.py`（download/verify/place 三模式）、
  `官方清单-23文件.json`（唯一权威清单：字节数+哈希+5 条备用源）、`手动下载清单.md`、`下载与校验日志.txt`；
  09-08 那批旧清单（53 文件版）已收进 `历史存档-20260908的旧清单\`，不参与流程。

## 十二、上机避坑清单（09-21 11:50，等租机期间产出）—— 为"付费时段零无效动作"做的收口

用户要求：**开机前把之前踩过的坑、走过的弯路全部过一遍**。产物 = 工作区 `cloud/上机避坑清单.md`
（已按"付费时段阶段"排布：租机连接 → 装机权重 → 冒烟 → 批量生成 → 选优 → 回传打包 → 关机善后，
每行写清 坑 / 症状与最早告警 / 本次是否已自动挡住 / 命中代价，另附「已判死·禁止」与「本机侧别顺手处理」两张表）。

**1. 逐条核对"守卫是否真的存在"（不是纸面承诺，都在代码里复核过）**

| 守卫 | 文件 | 复核结果 |
|---|---|---|
| 权重门禁（缺失/体积/全局摘要/零张量占位） | `cloud/verify_weights.py` | `missing` 或 `fail` 均 `return 1`；`run_generation.sh` 用 `if ! ... ; then exit 1`（真退出，不是打印） |
| 毒缓存 `~/.cache/hy3dgen`、XET 断流、hy3dgen commit、无 GPU | `cloud/instance_setup.sh` | `rm -rf ~/.cache/hy3dgen`；`HF_HUB_DISABLE_XET=1` + `HF_ENDPOINT=hf-mirror` 且写入 `.bashrc`；固定 `f8db630`；第 1 步 `nvidia-smi` 硬退出 |
| 幂等续做 / 噪声团 / 种子稳定 / 清单重建 | `cloud/generate_hy3d.py` | "已存在，跳过"；`noise_suspect` 对空网格直接判 `suspect(empty)`；种子 = 全量题表位置 + `k*stride`；`candidates.json` 由磁盘 glob 重建 |
| 硬门禁选优与汇总 | `pipeline/select_candidates.py` | 门禁参数（facets/size/single/settle）与 `full_pass/degraded/no_candidate` 汇总均在 |
| 完成率 ≥90% | `reproduction/run_infer.sh` | 读 `validation.meets_90pct`，不达标即 FAIL |

**2. 复核中发现 3 处守卫缺口，已当场补上（并复验）**

- **VAE 空值告警**（`generate_hy3d.py`）：本地"多子目录"权重（`/root/models/shape` 下同时有 dit 与 vae）若不传
  `--vae-subfolder`，会静默吃 ckpt 内嵌 vae 段 —— 拆包版该段是零占位、网格全零，等到 `noise_suspect` 报错时 GPU 已白烧。
  现在加载管线时直接打 `[vae] [warn] ... 建议加 --vae-subfolder <名字>`。
- **磁盘双门禁**：`run_generation.sh` 新增第 0.5 步（默认阈值 70 G，`--min-free-gb 0` 跳过，不足即 `exit 3`）；
  `instance_setup.sh` 第 1 步阈值从"建议 ≥60G"改为 **≥80G 并 <70G 告警**（账：权重 19G + 候选 raw ≈120×150MB ≈18G + 选中集 ~10G）。
- **单候选耗时判据**：`run_generation.sh` 末尾自动算 `生成分钟 / raw.glb 数`，>1.5 min（本机基线 0.50 的 3 倍）即打
  `!! [告警]`——CPU 回退或显存降速会在这里当场暴露，不用等一小时才发现。
- 附带：新增 `--vae-sub` 覆盖参数；`--dry-run` 日志改落临时目录（本机预演不再满屏 `tee:` 报错）；删掉死代码 `py()`。

**3. 顺手改正一处会害人的文档错误**

`云环境恢复手册.md` 第五节第 3 条原写"t2i 调用会污染全局随机数 → 必须 t2i 之后重置 seed + shape 显式传 generator"。
按 `hy3dgen-2.0.2` wheel 源码核对：`text2image.py` 的 `__call__(prompt, seed)` **内部自己建
`torch.Generator().manual_seed(seed)` 并显式传给 pipe**，所以"污染"这一情形在现行实现下不成立，
现行脚本（t2i 之前设全局 seed）逐题可复现。文档已改成与新结论一致 —— **目的就是防止有人在付费时段"照着修"把生成行为改掉**。

**4. 不变量复核（都跑过）**

- `bash -n cloud/run_generation.sh` + `bash -n cloud/instance_setup.sh` 通过；`py_compile generate_hy3d.py` 通过。
- `--dry-run --phase all`：三条命令打印正确（阶段 A 全量 2 候选 → 阶段 B 13 题补 3 候选 `--candidates 5` → 硬门禁选优）；
  `--vae-sub my-vae-dir` 覆盖生效。
- **两阶段 stub 测试再次全绿**：阶段 A 种子 `[42,1042,…]`、阶段 B 种子 `[2043,3043,4043,2045,3045,4045]`、
  16 条清单含全量题、阶段 A 产物 mtime 未被改动、重复跑阶段 B 生成 0 个（幂等）。

**5. 上传包已重打（含新守卫与清单）**

`%TEMP%\hy3d_upload.tgz`：**66,557 B / 189 条目 / sha256[:16] `6d6a2dbeaff3aa42`**，
包内 `run_generation.sh`、`generate_hy3d.py`、`instance_setup.sh`、`weak_ids.txt` 与工作区**逐字节一致**，无 `__pycache__`。
（旧包 `49d64520323882e5` 已被覆盖；**这一版是含 runbook 新指引的最终包，实例上要用的就是它**。）

**6. 脚本管不了、只能人记的三条**

1. 冒烟后**人眼看** `t2i.png`/`t2i_rembg.png` 是否为干净单物体概念图（自动化只能给图，判不了语义）。
2. 选优输出末尾的 `full_pass / degraded / no_candidate` **必须人看**，`no_candidate > 0` 就回补候选，别直接进提交。
3. 结束**先"关机"**（保留数据盘），等本机确认拿到全部产物后再"释放/删除"——否则要重下 19 GB 权重。

**7. 待用户动作（卡点）**

租一台 4090（PyTorch 2.3.0 + CUDA 12.4.1 + py3.10，**数据盘 ≥80G 可用**）→ 把控制台 `ssh -p <端口> root@<IP>` 发我 →
按 `cloud/上机避坑清单.md` 的「0~25 分钟」顺序走，第 5 分钟先测速定"本机上传 or 实例自下"。

## 十三、本机离线镜像构建（09-21 12:00 前后，Docker 专项 session）

**目标**：交付官方契约要求的 Docker 镜像（断网可跑、权重内置），本机先构建 + 断网实测取证。

**1. 基础镜像：NGC 路线成功**
- `nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04` 已拿到：**ID `21196d81f56b`，DISK USAGE 15GB / CONTENT 5.44GB**，`nvcr.io/...` 与 `nvidia/cuda:...` 两个 tag 指向同一镜像。
- 镜像站路线（docker.1panel.live 等 6 家轮试）**全部失败**，固定报错 `httpReadSeeker: failed open: failed to discard to offset: unexpected EOF`；NGC 一轮成功。
- 两条路线共享同一批 blob（层 ID 相同，如 `2a5ee6fadd42`/`4d37a6bba88f`），所以中途停掉镜像站路线不损失已下载内容。
- **教训**：两条拉取路线并行会互相抢带宽（实测从 130MB/min 掉到 83MB/min），确认主路线后应立即停另一条。

**2. hy3dgen 的真实来源是 PyPI，不是 GitHub**
- `env_snapshot_20260907.txt` 第 69 行 `hy3dgen==2.0.2` 没有 `@ file://` 标记 → 当初是**从 PyPI 装的**，不是 `pip install -e .`。
- 已核实该 wheel 是真包：47 个文件、`hy3dgen/shapegen/pipelines.py` 内 `class Hunyuan3DDiTFlowMatchingPipeline`（第 675 行），shapegen 全纯 Python（不引用 custom_rasterizer/mcubes 等需编译模块）。
- 已 vendor 到构建上下文：`reproduction/vendor/hy3dgen-2.0.2-py3-none-any.whl`，**115,478 B，md5 `ae61f80c49650fcbd97fd759c3a5dcea`**。
- 意义：**构建期不再依赖 GitHub**（本机直连 github 实测 ~20KB/s、codeload 35s 只下 787KB，会拖死构建）。PyPI 版本还比 git 更贴近当初得分环境。

**3. 依赖锁版本：补上一个会改变数值的漏项**
- 上游 `requirements.txt`（f8db630）**全部是裸依赖名、零版本约束** → 直接装会拉"当天最新"的 torch/diffusers，与初赛得分环境不一致。
- 已按 env_snapshot 钉 30 个包（torch 2.3.1 / diffusers 0.31.0 / transformers 4.57.6 / numpy 2.2.6 …）。
- **新发现**：`hy3dgen/shapegen/models/autoencoders/surface_extractors.py` 里 `from skimage import measure` —— 这是**推理必经的 marching cubes 面提取**，版本会影响网格数值，而原钉版本清单里**没有 scikit-image**，必须补 `scikit-image==0.25.2`。

**4. 网络实测（决定构建方案的关键数据）**

| 目标 | 宿主机（WSL） | 容器内 |
|---|---|---|
| archive.ubuntu.com | 124 KB/s | — |
| mirrors.aliyun.com（apt） | ~300 KB/s（apt 索引实测） | **163 KB/s** |
| repo.huaweicloud.com（PyPI） | **6.5 MB/s** | 待测 |
| pypi.tuna（miniconda 198MB） | >1.5 MB/s | **546 KB/s**（6m03s） |
| mirrors.aliyun.com（PyPI） | 5.9 MB/s | 待测 |
| 官方 pypi.org / files.pythonhosted | 13 KB/s / 连通 | — |
| github / codeload | 20 KB/s | — |

**结论**：① 国际源（apt/pypi/github）必须绕开；② **容器网络只有宿主机的 1/3~1/9**，所以"联网下载"全部放宿主机做。

**5. 构建方案（已落到 Dockerfile）**
- apt → 阿里云；miniconda → 清华；conda python=3.10 → tuna `pkgs/main`（去掉 `-c conda-forge`，索引求解慢得多）；pip → 华为云 + 阿里云 extra-index。
- 针对容器网络慢：增加**可选**加速路径 —— 宿主机 `pip download` 预取全部轮子（约 3.9GB）→ `python3 -m http.server` 本地服务 → `docker build --build-arg PIP_FIND_LINKS=http://172.17.0.1:8765/ --build-arg PIP_NO_INDEX=1`，容器内不再联网。
  **默认路径仍是镜像源**（不传 build-arg 即可），保证第三方拿到 Dockerfile 能直接复现。
- 构建期硬门禁保留：权重逐文件字节数 + safetensors 零张量（整文件全零即构建失败）+ u2net md5；另加 `import hy3dgen.shapegen` 硬门禁（导入失败即构建失败，能一次验完 xatlas/trimesh/pymeshlab/skimage 整条依赖链）。

**6. 本机踩坑（都吃过一次，别再踩）**
- **中文路径不能走命令行传给 WSL**：`bash -c "..."` 里的中文路径会被 Git Bash 转码搞坏（`stat` 拿到空文件名）。→ 一律写进 `D:\wsl\*.sh` 再 `bash /mnt/d/wsl/x.sh`。
- **`pkill -f "docker build"` 会杀掉自己**（自身 cmdline 含该模式，退出码 15）。→ 用 `pkill -f "[d]ocker build"`。
- **WSL 的 `/tmp` 会被清掉**（约 1 分钟内，原因未追）。→ 暂存一律用 `D:\wsl\work\`。
- 本机 docker 是 **legacy builder**（无 buildx），**不支持 `--progress`**；Dockerfile 也据此写成 legacy 兼容（无 heredoc、无 `--mount`）。

**7. 下一步（本 session 正在做）**
`docker build` → `docker save | gzip` 出可交付镜像包 → `--network none` 断网实测（镜像内权重门禁 + `INFER_PROC_ONLY` 官方入口，留存日志）→ 重打源码包 **v4**（现有 `复现推理源码包_v3_20260921.zip` 是 11:13 的，缺 `reproduction/vendor/`、新 Dockerfile，以及并行 session 的 `cloud/download_weights.sh`、`cloud/租机执行清单.md` 等）→ 提交说明补实测记录。

## 十四、初赛 submit 规格核对 + 依赖闭包实测（09-21 12:2x，格式核对 session `sess_b548929b`）

**1. 官方 submission.zip 规格 vs 我方产物 —— 逐条命中**

用户提供了赛题页的提交示例原文（manifest.json / metadata.json / process.md 字段表）。拿它核对 `output_test/submission0907.zip`（初赛实际提交的那版，manifest 内署名 `CCF_BDCI_2026`/`T3D-Team`）：

- 结构：`manifest.json` 在 **zip 根**、40 个 `prompt_id` 目录（测试集 `hid_*` 全 40 题）、每题 `model.glb` + `metadata.json` + `process.md` + `renders/{front,side,top,perspective}.png`，**包内无多余条目**。
- 字段：manifest 5 键（`team_id`/`team_name`/`round`/`created_at`/`tasks[{prompt_id,path,primary_model}]`）、metadata 8 键（`prompt_id`/`primary_model`/`unit`/`base_model`/`seed`/`generation_time_minutes`/`postprocess`/`commercial_api_used`）、process.md 的 10 个标签（题目编号/使用模型/主要改进/生成参数/随机种子/生成耗时/后处理流程/失败样例与修正/是否使用商业API/数据来源说明）——**与官方示例完全一致**。
- 推论（未写进官方文档，待验）：复现阶段官方在断网环境跑 `run_infer.sh`，其 `/output` 应被同一套读法解析 → 必须保持同结构；我们额外写的 `logs/` 对应官方"推理失败需输出日志"，是要求不是违规。

**2. 格式核对暴露的 4 个交付质量缺口（均不影响评测，v4 一并修）**

| # | 位置 | 现状 | 影响 |
|---|---|---|---|
| a | `pipeline/build_submission.py:281-282` | `--team-id/--team-name` 默认值仍是官方示例 `team_001`/`example_team` | 官方入口经 `run_infer.sh:73-74`（`369583`/`default13319669`）覆盖 → **评测无影响**；但裸跑 `build_submission.py`（本机重打包、复现重跑）会写出示例署名 |
| b | 同文件 `:151-153` | `seed`/`generation_time_minutes` 取自 `gen_meta.json`，缺失退 `0` | 09-07 包里这两项就是 `0`/`0.0`（那批 raw 无 `gen_meta.json`）。生成链路会写真值；**若复现实测走 `INFER_PROC_ONLY` 复用旧 raw 则仍为 0** → 交付前确认 raw 目录带 `gen_meta.json` |
| c | 同文件 `:321` | `round` 硬编码 `"preliminary"` | 复现阶段名义不符；建议加环境变量开关 |
| d | `复现提交包/复现推理源码包_v3_20260921.zip` | 包内 `reproduction/Dockerfile` 是 11:13 旧版（**115 行**，无国内镜像 ARG、无 `PIP_FIND_LINKS`/`PIP_NO_INDEX`、无 u2net 上下文内置），**磁盘版 169 行**；md5 包内 `090161046335` vs 磁盘 `feb58b6c6746` | **v4 必须带磁盘版**，否则第三方照包构建会走国际源、u2net 可能联网 |

- 已确认**没问题**的：包内 `pipeline/build_submission.py`（md5 `192119050c1f`）与 `reproduction/run_infer.sh`（`c006c8d3f2cb`）与磁盘**逐字节一致**；包 27 条目、中文顶层目录 `复现推理源码包` 的 **UTF-8 标志位已置**（Linux 解压不乱码）。

**3. 依赖闭包实测（回答"wheelhouse 值不值"）**

- `D:\wsl\work\report.json`（12:17:49 产出）= **123 个包 / 3.31 GB**（逐包 HEAD 实测 content-length：121/123 取到；gradio、rich 未取到）。Top：torch 743MiB、nvidia_cudnn 698MiB、cublas 392MiB、cusparse 187MiB、nccl 168MiB、triton 160MiB。
- **PyPI 带进来的 CUDA 轮子约 1.9 GB 属冗余候选**（基础镜像已是 `nvidia/cuda:12.1.1-cudnn8-devel`）→ 需要减重时这是第一杠杆。
- 时间账：宿主机 6.5MB/s ≈ 8~10 min；容器内（实测 1/3~1/9）≈ 25~75 min。→ wheelhouse 省的只是"半小时到一小时"，代价是新增一条同样会断流的链路（12:06 那次 779MB torch 轮子被杀，它并不免疫）。**结论：可留，但降级为后台可选，不当关键路径。**

**4. 一处更正：11:26 那次 `docker build` 不是网络崩**

`build_log.txt` 末行 `exit=143` = SIGTERM，且 `D:\wsl\stop_build.sh` 时间戳 **11:33** → 是**主动停掉**的；日志里 `Can't add file ... read/write on closed pipe` 是被中断的表象。**"不绕 wheelhouse 就跑不通"从未被验证过**，别当既成结论引用。

**5. 本节的待办（按优先级）**

1. **问组委会**（第十节 6 的开放项，仍未问）：① 复现镜像体积上限与提交渠道（平台直传/网盘/镜像仓库）；② 单题推理时限；③ PPT 与方案文档是否同渠道同截止。**~~估账~~ 实测（09-21 21:05 已推翻估算，见第十五节第 8 条）**：镜像 CONTENT SIZE 23.9 GB，`docker save | pigz` 产物 **22.2 GiB（几乎压不动）**；本机上行 0.22 MB/s → 平台直传 **≈29 h，物理不可行**。
2. **v4 打包**按第 2 节 a~d 四行修正（重打包由 Docker session 统一做，本节仅登记，不另行重打）。
3. wheelhouse 按第 3 节降级；若要减重，优先砍 PyPI 的 CUDA 轮子。

## 十五、镜像已产出 + 三处缺陷修复 + 断网实测取证收口（09-21 19:00~20:1x，Docker/交付专项 session `sess_55120b3c`）

**一句话状态**：**交付镜像 `hy3d-repro` 已构建完成并验证到交付口径** —— 本机从零组装（阶段 A 容器装依赖 + `docker commit`；阶段 B 用**交付 Dockerfile 尾段原文** `docker build`），四次提交收敛到最终 ID，**镜像内 `--network none` 断网三题全流程 rc=0 / 完成率 1.0**，证据 `实测记录/00`~`13` 全部落盘；源码包 v5 与 `docker save` 镜像包在收尾中。**第十四节第 2 节的 4 个 v4 缺口已全部关闭**（见下第 5 条）。

**1. 交付镜像链（四次提交，前三次是修缺陷，第四次是交付质量修订）**

| 提交 | ID | 内容 | 为什么 |
|---|---|---|---|
| 阶段B（参照） | `1be9614c01b2` | 交付 Dockerfile 尾段 `docker build` 产物 | 作为"第三方照 Dockerfile 构建"的**逐字段比对基准** |
| 首次 | `ba59590d3f76` | 补装 `fast-simplification` | **弃用**：修复容器未加 `--entrypoint ""`，`docker commit` 把 bash entrypoint 一起继承 → 按官方调用形态报 rc=126 |
| 二次 | `2c0d481a4db1` | 同上，正确写回 ENTRYPOINT/CMD/WORKDIR | 减面缺陷修复 |
| 三次 | `e98522e9e498` | 加 `enforce_caps()` 减面后尺寸兜底 | 50.1 mm 越上限缺陷 |
| **四次（交付）** | **`56b164216646`** | `build_submission.py` 默认署名改为本队 + `round` 加环境变量 | 关闭 v4 缺口 a/c |

- 每次提交后都做**四字段逐字段比对**（`Config.Entrypoint` / `Cmd` / `WorkingDir` / `Env`）与参照镜像 `1be9614c01b2` **全部一致**，并跑"不带 `--entrypoint` 覆盖"的官方调用形态冒烟。
- 镜像内关键文件 md5 与工作区源码**逐字节一致**（`run_infer.sh 9f394ddc…` / `postprocess.py e067e6f8…` / `build_submission.py 2058b50e…`）。

**2. 三处缺陷（都带实证，别只看结论）**

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 单题耗时 >13 min、交付 `model.glb` 113 MB（正常 ~2 MB） | 镜像**漏装 `fast-simplification`**（初赛 `env_snapshot` 第 49 行有，本镜像锁文件/清单漏记）→ `decimate()` 静默 `return m` → 残留 714 万面 → matplotlib 逐面投影 0.1 ms/面 | 补装 + 二次提交；Dockerfile 加 pin + **减面功能自检**（缺失即构建失败）；锁 123→130；代码改**显式 stderr 告警** + `stats.over_face_cap` |
| 2 | 题面「50 毫米以内」但交付包围盒 **50.1 mm** | 减面（二次误差边折叠）**会移动顶点**，把已归一化的 50.0 顶到 50.1 | `postprocess.py` 加 `enforce_caps()`：改形全部结束后按各轴上限**只缩不放**兜底复核；三次提交 |
| 3 | 镜像内依赖闭包与锁不一致（127 vs 130） | matplotlib 家族 6 条被 Dockerfile 装上但**没写进锁文件/轮子清单** | 锁与 `wheels_manifest.json` 均补至 **130**（含 sha256），轮子仓库同步到 130 个文件；一致性校验 PASS |
| 4 | 源码默认署名是官方示例值、`round` 硬编码 | v4 缺口 a/c | 四次提交（见上表）；镜像内 `validate` 对断网三题产物**真跑通过**（`completion_ratio=1.0`） |

- **依赖闭包双 PASS**（`实测记录/10`）：镜像内 187 条已装包 vs 锁 130 条 → **130/130 版本完全一致**（多出 57 条经逐条核对为 conda/pip 工具链）；`--network none` + `--no-index` 下 **130/130 可解析**。**踩坑**：离线解析必须加 `--ignore-installed`，否则 pip 会把已满足的包（如 `packaging`）从 `Would install` 排除，误报 129 条"找不到"。

**3. 断网实测（交付口径证据，`实测记录/00`~`13`）**

- 三题一次容器跑完：**rc=0，`completion_ratio=1.0  meets_90pct=true`**，逐题 `OK`，`problems=[]`、`quality_warnings=[]`。
- 单题耗时（本机纯 CPU / AMD R5 4600U，最终镜像 `56b164216646` 实测）：**194.5 / 242.0 / 222.4 秒（合计 658.9 s）**；交付 `model.glb` 2.01 / 2.00 / 1.98 MB（md5 `8e9d0e13…` / `269a1520…` / `13bf793a…`），面数 112,784 / 111,750 / 110,610，3/3 水密单体，`over_face_cap=false`。
- 第 3 题（题面「50 毫米以内」）`post_decimate_rescale=0.99899`、最终包围盒 **50.0×50.0×50.0 mm** —— 缺陷 2 的修复在此显式生效。
- 产物结构与官方 §2.3 一致：`manifest.json`（键名 `tasks`）+ `<pid>/{model.glb,metadata.json,process.md,renders/{front,side,top,perspective}.png}` + `_logs/`；署名 `369583` / `default13319669`。
- **易踩的坑（已记进证据文件勘误）**：① 官方 manifest 的列表键名是 **`tasks`**（不是 `models`/`items`）；② `docker exec` 不带 `-i` 时 stdin 不生效 → heredoc 脚本**静默不执行**；③ 镜像内 `docker run` 不带 `--entrypoint ""` 时 NVIDIA 横幅会混进 stdout（曾把 md5 输出污染成孤立单词）。三处都已在 `13` 里逐条标注并用干净重跑覆盖。

**4. 证据文件一览（`D:\文本生成3D方案赛\实测记录\`，全部随源码包 v5 交付）**

`00` 缺陷实证（py-spy 采样/113MB 网格/快照对照）· `01` 断网实测全日志 · `02` 镜像内 `_logs/run_infer.log` 原件 · `03` 逐题 `build_report.json` · `04` 产物 manifest · `05` 权重门禁 · `06` 基础环境预演 · `07` 镜像内 187 条已装包 · `08` 镜像组装日志（+附录一/附录二）· `09` 交付镜像清单 · `10` 依赖闭包双 PASS · `11` 交付 Dockerfile 校验 · `12` 镜像导出实测 · `13` 提交/勘误/补录全记录 · `样例渲染图/<pid>/*.png`（12 张）

**5. 第十四节登记的 4 个 v4 缺口 —— 全部关闭**

| # | 缺口 | 现状 |
|---|---|---|
| a | `build_submission.py` 默认署名是官方示例值 | ✅ 已改为 `369583`/`default13319669`（env `TEAM_ID`/`TEAM_NAME` 可覆盖），四次提交入镜像 |
| b | `seed`/`generation_time_minutes` 缺 `gen_meta.json` 时退 0 | ✅ **实测已证伪风险**：本机断网实测的 raw 目录**自带 `gen_meta.json`**，产物 `metadata.json` 写的是真值 `seed=42`、`generation_time_minutes=0.52` |
| c | `round` 硬编码 `preliminary` | ✅ 改为 `SUBMISSION_ROUND` 环境变量（默认仍是 `preliminary`，与官方示例同值） |
| d | v3 包内 Dockerfile 落后磁盘（115 vs 169 行） | ✅ **v5 重打源码包时按当前磁盘版打包**（并新增 `reproduction/vendor/fast_simplification-*.whl`、`实测记录/样例渲染图/`） |

**6. 仍未闭合的两项（非本 session 能做）**

1. **镜像提交渠道/体积上限**：镜像包**已产出**——`复现提交包/hy3d-repro_20260921.tar.gz`，**23,867,134,532 字节（22.2 GiB）**，**SHA256 `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914`**；`docker save | pigz -6` rc=0、耗时 1357 s，看门狗未触发（结束余量 D: 24 GB），tar 结构 / 19 层体积 / `index.json`（manifest 摘要 `sha256:56b1642166463312…` = 交付镜像 ID）三项校验通过（证据 `12`）。**注意实测值推翻了此前的估算**：压缩后是 **22.2 GiB，不是预估的 12~18 GB**（权重为稠密浮点，gzip 基本压不动）。**本机上行 0.22 MB/s → 平台直传物理不可行**（22.2 GiB ≈ 29 h），仍需问组委会（网盘/分卷/镜像仓库）。
2. ~~方案文档（与答辩 PPT 一致）~~：**已补齐** `方案文档.md`（工作区根目录，已入源码包 v5）：赛题理解 → 总体方案 → 四个关键设计决策 → 实测数据 → 工程化与可复现性（含三个真问题的修复表）→ 局限与如实声明 → 证据索引 → 后续计划。答辩 PPT 本身仍未产出，文档首段已注明"与 PPT 同口径、PPT 定稿后同步"。

**7. 下一步（接手即做）**

1. ✅ 镜像包导出 + sha256 + tar 结构（证据 `12`）已记录；源码包 v5 已重打（含 `方案文档.md`、两个 vendor 轮子、`实测记录/` 全量含样例渲染图）。
2. ✅ `实测记录/07`/`09` 已按最终镜像 `56b164216646` 重取；文档数字全部对齐实测值（194.5 / 242.0 / 222.4 秒）。
3. 回问组委会两问（第 6 节 1：体积上限与提交渠道；单题时限）后决定是否分卷上传。
4. 答辩 PPT（口径对齐 `方案文档.md`，12~15 页）与 FDM 实物打印验证。

**8. 镜像包实测口径备忘（本轮两个"估错"的教训）**

- **`docker images` 的 60.5 GB 是 DISK USAGE（含共享基础层重复计），`CONTENT SIZE` 才是 `docker save` 的落盘量 = 23.9 GB**；压缩后 22.2 GiB，几乎等于未压缩——**不要再按"权重能压一半"估算交付体积**。
- 抓这两列要用机器可读口径：`docker image inspect -f '{{.Size}}'`（CONTENT SIZE）+ `docker history --format '{{.Size}}'`（逐层），不要用 `docker images` 的人类可读输出。

**9. 交付目录最终状态（`D:\文本生成3D方案赛\复现提交包\`，2026-09-21 21:30 冻结）**

| 文件 | 字节 | SHA256 |
| --- | --- | --- |
| `hy3d-repro_20260921.tar.gz` | 23,867,134,532 | `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` |
| `复现推理源码包_v5_20260921.zip` | 4,818,477 | `b9ce606f0aafafaa881e4d41f007267148cc60f8acd5d908faa3b769c1f62797`（终版：含镜像包恢复实测证据；此前两次重打分别是 `4057ebb7…` / `1c2866ce…`，均已被本次覆盖） |
| `交付清单-SHA256.txt` | 2,894 | （清单自身不含校验值，已写入两份包的字节数/哈希 + 加载与断网运行命令） |

- 源码包 v5 内容：**70 项**，含 `方案文档.md`、`reproduction/复现说明文档.md`、两个 vendor 轮子、`实测记录/00~13` + `样例渲染图/`（12 张 PNG）；**权重二进制 0 条**；70 个条目全部非 ASCII 名、UTF-8 正常；`testzip` OK。
- **三向一致性（新做的门禁）**：源码包 ↔ 工作区磁盘 ↔ **交付镜像内 `/app`** 逐文件 md5 一致 5/5（`run_infer.sh` `9f394ddc…` / `verify_weights.py` `989a093c…` / `postprocess.py` `e067e6f8…` / `build_submission.py` `2058b50e…` / `render_views.py` `4881bb9e…`），证据 `13` 末节 → **不存在"包内代码 ≠ 镜像内代码"的错配**（这正是上一轮 v3 包踩过的坑）。
- 归档独立复核：`pigz -t` 全量解码 rc=0（491 s，无 CRC 报错）→ 22.2 GiB 镜像包未截断。
- **交付包自足性实测（本轮最强的一条门禁）**：先 `docker rmi` 把本机镜像**连同全部中间提交层删干净**（日志 12 行 `Deleted: sha256:…`），再 `gunzip -c <交付 tar> | docker load`（rc=0，784 s）→ 恢复出的镜像 **ID / CONTENT SIZE / 层数与原镜像逐字段一致**；随即在恢复出的镜像内 `--network none` 跑单题阶段 2：官方入口 **rc=0**、`completion_ratio=1.0`、`problems=[]`，产物 `model.glb` md5 `8e9d0e133c89c9638f1d3aee74046903` **与三题实测同题产物逐字节相同** → **交付的 tar 是真能 load 回来并跑出同样结果的自足归档**（证据 `12` 末节）。
- 超期的 `复现推理源码包_v3_20260921.zip` 已移出交付目录（保留在 `D:\wsl\work\superseded\`），避免误交旧包；`复现提交包/复现推理源码包/` 空暂存目录已清空（仅剩一个被导出进程句柄占用的空壳，无内容）。

---

## 十六、视觉门禁：交付镜像在**初赛提交版 40 题真实几何**上的离线对拍 + 交付包重打（09-21 22:1x ~ 23:35，同一交付专项 session 续）

### 16.1 为什么做这一轮（补的正是此前最大的证据缺口）

官方复现评测的隐含要求是**"复现跑出来的产物 = 初赛提交的产物"**。此前本机唯一能做的断网实测（证据 `01~05`）用的是 **2026-09-05 调试期噪声 raw**（VAE 零占位缺陷期），只能证明"链路通、结构对、门槛过"，**证明不了"复现=提交"**——初赛提交版的原始网格只存在于已释放的云实例上，本机没有。

本轮换了个更强、且可证明的做法：**把初赛提交包 `output_test/submission0907.zip` 内 40 题的成品几何 `model.glb` 原封不动当作阶段 2 的输入**，在交付镜像内 `--network none` 重跑"后处理 → 四视图渲染 → 打包"，再与提交包逐项对拍。即：**给定同一几何，验证 CPU 侧全链产物与初赛提交同源等价**。

### 16.2 实测结果（初赛测试集**全量 40 题**）

| 项 | 结果 |
| --- | --- |
| 输入 | 40/40 题的 `model.glb`（逐字节未改；`prompts.jsonl`/`gen_meta.json` 依提交包 metadata + 题面重建，文件内自带 `_note` 声明） |
| 渲染单步隔离复现 | 40 题 rc=0，**160/160 张 PNG 与提交包 renders 逐字节一致（40/40 题 × 4 视图）**，用时 1471 s |
| 官方入口阶段 2 全链 | rc=0，完成率 1.0 / 门槛 PASS，用时 1458 s；`metadata.json` **逐字段一致** |
| 几何物理量 | 面数 / 顶点数 / 单体数 / 水密性 **40/40 题全同**（双方全 watertight、bodies=1） |
| 包围盒 | **39/40 ≤0.01 mm**（中位 **0.0006 mm** = 0.6 μm；5 题逐分量完全相同）；唯一离群 = `hid_sma_001` 26.69 mm |
| 底面贴地 | 复现后 **40/40 题 zmin=0.0000 mm**（提交版有 16 题为 −0.0002~−0.0031 mm 负残留、`hid_dec_007` +0.0131 mm 微悬空 → 均被复现链归零） |
| 阶段 2 渲染同时逐字节一致 | 3/40 题（`hid_con_001` / `hid_fun_006` / `hid_sma_010`） |
| GLB 整体逐字节一致 | 0/40，但**差异已逐字段定位**：glTF JSON 头 mesh 的 `extras` 键不同（提交 `{"processed":true}` vs 复现多出 `units/from_gltf_primitive/name/node`），accessors（含 min/max）/buffers/bufferViews/scene 全同；上述 3 题的 **BIN 几何块逐字节相同** |

### 16.3 唯一离群题 `hid_sma_001`：如实披露 + 三条旁证归因

- 提交版：外廓 **43.3×35.9×43.2 mm**、底面 **zmin=+6.6371 mm（整体悬空 6.64 mm）**；题面要求「整体外廓不超过 70 毫米」。
- 复现版：外廓 **70.0×58.0×69.8 mm**、zmin **0.0000 mm**（按题面归一 + 贴地）。
- **归因（指向提交版自身缺陷，不是复现链缺陷）**：① 初赛构建报告 `build_report.json` 该题 `final_longest_mm=70.0`（目标）vs 实际 `43.3`，且 `heavy_repair=true` → v2 的"归一 + 贴地"发生在 pymeshfix 重建**之前**，被重建工序改动（其余 39 题目标/实际差 <0.05 mm，仅此题 26.7 mm）；② `output_test/初赛40题产物体检报告_20260921.md` 第 2 行早已登记该缺陷并给出修复方向"**先去碎块/减面，后贴地**"；③ 交付镜像正是按修正后顺序实现的（40/40 题 zmin 全为 0）。
- 结论：26.69 mm = **提交版缺陷被修正的量**，方向正向，已在源码包文档中显式披露，不掩盖。

### 16.4 样例渲染图目录重组（口径问题彻底解决）

`实测记录/样例渲染图/`（23 个条目）现在是**三批来源不同**、口径写死在 `来源说明.md` 里：

- `来源说明.md`：三批图的来源/证明力/生成方式/复核命令（**新增，评委先看这份**）
- `初赛提交版几何/`（9 张）：`00_8题对拍总览_透视对照.png`（左=提交版、右=复现）+ 8 题 `<pid>_提交版vs复现_四视图.png`（上=提交版、下=复现，页脚标注该题对拍数字）
- `00_40题总览_perspective.png`：**初赛提交包自带的** 40 题透视渲染拼版（明确标注"不是交付镜像产物"）
- `调试期raw_仅链路连通性/`（12 张）：09-05 调试期噪声 raw 的链路证据（明确标注"不代表语义质量"）

**人工目检结论**：8 题对照图上、下两排肉眼无可见差异；唯一有实质差异的是 `hid_sma_001`（页脚数字给出 43.3→70.0 mm、悬空 6.64→0.00 mm）。

### 16.5 交付包重打与冻结值更新（**历史快照 —— 已被第十七节 09-22 第四次重打取代**）

> ⚠️ 本小节是 09-21 23:43 的冻结值；**终版值见文件末第十八节**（zip 改为 **8,768,573 / `10290691…`，85 项**，冻结时间 2026-09-22，镜像包未变）。下表保留作历史对照。

| 交付物 | 文件 | 字节 | SHA256 |
| --- | --- | --- | --- |
| Docker 镜像（**未变**） | `hy3d-repro_20260921.tar.gz` | 23,867,134,532 | `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` |
| 算法源码 + 文档 + 证据（23:43 第三次重打；**已被 §17、§18 取代**） | `复现推理源码包_v5_20260921.zip` | 7,958,870 | `190410d7b4619213688649a83f678d1531c399bdfa57a9f1233620b34ac31bd2` |
| 校验清单（清单自身不含校验值） | `交付清单-SHA256.txt` | — | 冻结时间已更新为 **2026-09-21 23:43** |

- **三次重打的净变化**：① 23:35 首次（纳入证据 14 + 三批样例图口径，82 项）；② 23:40 只改 `提交说明.md`（§五「目录结构」非全量说明 + §六「交付方式与上传清单」：两份问卷链接、截止 2026-09-23 24:00、材料按 `369583+default13319669` 命名、镜像上传渠道仍待问组委会）；③ 23:43 再加证据 14 的收口节 §4（记录前两次重打）。条目数始终 **82**，镜像包与其余文件未变动。
- **收口原则（避免自指死循环）**：终版字节数/SHA256 **只**写 `交付清单-SHA256.txt`（在包外）；包内任何文件都不记录包自身哈希——否则每次改包都要再改包内哈希、再打包，永无终点。

- 源码包重打后 **82 项**（原 70；新增 `来源说明.md` + `初赛提交版几何/` 9 张对照图）；`testzip` OK；**权重二进制 0 条**；条目名 UTF-8 正常。
- **三向一致性复核（重打后再做一次）**：包内 `pipeline/{postprocess,render_views,build_submission}.py`、`cloud/generate_hy3d.py`、`reproduction/verify_weights.py` ↔ 镜像内 `/app/*.py` md5 **5/5 一致**（新增 `generate_hy3d.py` 也纳入比对）。
- 磁盘 ↔ zip 逐文件 md5 一致 0 处不一致（含 `提交说明.md`/`方案文档.md`/两份复现说明/证据 14/来源说明）。
- **包内不记录自身哈希**（自指）——哈希只写 `交付清单-SHA256.txt`（清单在包外）；证据 14 亦只记录条目数与校验结论、指向清单取哈希。

### 16.6 同步过的文档（口径一次性拉齐）

`提交说明.md`（§1 证据行、§3.1 对拍块、§3.2 证据清单、§5 目录树）、`方案文档.md`（§四 实测数据行、§七 证据索引）、`reproduction/复现说明文档.md`（附 B 清单、说明 1、3.5 表行）、`reproduction/README-复现说明.md`（§七 两条 bullet）、`复现提交包/交付清单-SHA256.txt`（第 2 行 + §三 证据清单 + 冻结时间）——**五处全部改为 40 题口径**，并把 `hid_sma_001` 的披露与"GLB 差异只来自 extras 键"写进正文，避免评委先发现、我们后解释。

### 16.7 仍未闭合（不随本轮变化）

1. **镜像提交渠道 / 体积上限**：仍未问组委会（本机上行 0.22 MB/s，22.2 GiB 直传 ≈29 h 不可行）。
2. **答辩 PPT**：仍未产出（`方案文档.md` 首段已注明"与 PPT 同口径、PPT 定稿后同步"）。
3. 阶段 1（文生图 + 形状生成）本机无 GPU，**不可重跑**——语义质量的复现证据是初赛提交本身（40 题 / 3.15 分 / 第 9 名），本轮实验只证明 **CPU 侧全链同源等价**，两者合起来才是完整证据链（此边界已写进全部文档）。

## 十七、09-22 上午：官方 v1.0 逐条复核 → 第四次重打（终版）+ 上传材料备齐（百度云盘）

触发：用户要求「再梳理一遍组委会发的决赛复现提交要求，看除填两份问卷外还要做什么，材料是否按官方要求备好」，并明确**上传渠道 = 百度云盘**。

### 17.1 核对结论（官方 v1.0 全文见 `D:\wsl\复现提交要求_文本.txt`，5,916 B / 3 页）

逐条对完 **§1 五项提交物 / §2.1~2.4 运行与产物规格 / §3.1~3.5 文档模板 / §4 自查清单 8 项**，**唯一被判定"文档没写透"的是 §2.2 输入兼容性**（"其余字段原样透传"这条只在代码里成立、文档里没实证），其余各项此前已闭合。因此本轮**只改文档、不改代码**——改代码会让已冻结的镜像包失效（镜像 tar 不动）。

**§2.2 补的实证（写进 `reproduction/复现说明文档.md` §3.5 新增「输入兼容性」小节 + `实测记录/14`）**：
- 40 题全量对拍所用 `prompts.jsonl` 的键集合与**官方题面 `prompt.json` 完全一致**（`prompt_id/lang/category/prompt/prompt_en/prompt_intent/constraints` 7 键）→ **40/40 rc=0、完成率 1.0**；
- 该文件 40 行里存在 **2 种字段顺序**（部分行 `prompt_id` 排在行尾），入口全部通过 → 字段顺序无关；
- 产物侧不回写输入字段：`manifest.json` 的 `tasks` 只有 `prompt_id/path/primary_model`，每题 `metadata.json` 只有官方 8 个必填键。

### 17.2 证据 14 的一处事实更正（诚实性）

此前证据 14 写「`_note` 字段随 `prompts.jsonl` 传入」——**实测 `grep -c _note` = 0，键集合 = 7**，`_note` 只存在于 `raw/<pid>/gen_meta.json`。已按实际文件更正原文并注明"本行此前表述不准确，2026-09-22 按实际文件更正"。

### 17.3 第四次重打（**已被 §18.3 的第五次、第六次重打取代**：条目数 82 → 85、zip 终值 8,768,573 / `10290691…`；下表为当时快照）

| 交付物 | 文件 | 字节 | SHA256 |
| --- | --- | --- | --- |
| Docker 镜像（**未变**） | `hy3d-repro_20260921.tar.gz` | 23,867,134,532 | `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` |
| 算法源码 + 文档 + 证据（09-22 第四次重打，**当时快照；终版见 §18.3**） | `复现推理源码包_v5_20260921.zip` | ~~7,960,946~~ → ~~8,768,569~~ → **8,768,573** | ~~`d746631c…`~~ → ~~`e0db7d9d…`~~ → **`10290691…`** |
| 校验清单（清单自身不含校验值） | `交付清单-SHA256.txt` | ~~6,954~~ → ~~8,107~~ → **8,417** | 冻结时间 **2026-09-22**（md5 ~~`e16c06e1…`~~ → ~~`ae32949c63eabbc692fa093c26a8cd51`~~ → **`db7f7b5a184ead3be85e9f46c468b818`**） |

- 三处净变化：① `实测记录/14` 的 `_note` 出处更正 + 新增【输入字段形态】块；② `reproduction/复现说明文档.md` 新增 §3.5「输入兼容性（官方 2.2 节）」；③ `提交说明.md` §六 上传渠道定为**百度云盘**（并写明分片脚本与 Dockerfile 备选路线）。
- 重打后门禁（全部独立执行）：**磁盘 ↔ zip 全量 82 项 md5 对拍 0 不一致 / 0 缺失**、`testzip` OK、**权重二进制 0 条**、`__pycache__` 0 条、**包内自指哈希扫描 0 命中（58 个文本条目经 UTF-8 解码）**、包内 5 个推理源码 ↔ **镜像内 `/app` md5 仍 5/5 一致**（`docker run --rm --network none --entrypoint "" hy3d-repro bash -lc 'md5sum /app/*.py'`）。

### 17.4 上传材料备齐（`D:\文本生成3D方案赛\复现提交包\上传百度云盘\`，09-22 新建）

> ⚠️ **下表是第四次重打时的快照；终版见 §18.4**（zip 8,768,573 / `4409060d…`、加 `06_答辩PPT` 三项、清单 8,417 / `db7f7b5a…`、`上传说明-百度云盘.md` 8,777 / `a1479873…`）。

官方 §1 五项**具名成文件**（命名 = `369583+default13319669_序号_名称`）：

| 官方 §1 | 文件 | 大小 | md5 |
| --- | --- | --- | --- |
| ① 算法源代码 | `…_01_算法源代码_复现推理源码包_v5_20260921.zip` | 7,960,946 | `1c50d62aa093e8b15a201da4a6071cfe` |
| ② 运行环境 | `…_02_运行环境_镜像包_生成分片.bat`（非镜像本体，见下） | 4,230 | `2aaa1e992d2f8a7b141807eb1ad3e29e` |
| ③ 模型权重 | `…_03_模型权重_下载地址与SHA256.md`（23 文件公开源直链 + 逐文件 SHA256） | 12,348 | — |
| ④ 复现说明文档 | `…_04_复现说明文档.md`（官方 §3 模板单文件） | 29,779 | `243f5507d9669681799b77247f98cfb9` |
| ⑤ 方案文档 | `…_05_方案文档.md`（与答辩 PPT 同口径） | 13,379 | `7c46687f4bb4b351de859b0fe1d3a862` |
| — 校验清单 / 说明 / 工具 | `交付清单-SHA256.txt`（6,954 / `e16c06e1…`，与工作区同名文件逐字节相同）、`上传说明-百度云盘.md`（7,578 / `0dd60aae…`）、`合并分片.bat`（1,301 / `92d73e9c5838c6ba72c8810435234576`）、`上传工具-自测日志.txt`（6,140 / `290329e11a04bcedf4b6d9f66c45bef8`） | — | — |

- **镜像包（22.2 GiB）走分片**：`…_02_…生成分片.bat` = `SPLIT` 工具脚本（`SRC=D:\文本生成3D方案赛\复现提交包\hy3d-repro_20260921.tar.gz`、`OUTDIR=C:\百度网盘上传\镜像分片`、`PARTSIZE=3700000000`、先校 SHA256 = `8c2668ac…` 再切、产出 ≤3.7 GB × 7 片 + `分片清单-SHA256.txt` + 自动把 `合并分片.bat` 复制到分片目录）；`合并分片.bat` = 逐片 `copy /b "a"+"b"` 还原 + certutil 校验 + `gunzip -c … | docker load` 提示。
- **分片/合并工具已真跑验证**：用 3,500,007 B 样本在中文路径下 cmd 端到端执行「切分 → 合并 → md5」，结果 **PASS · 逐字节一致**；原始输出留存 `上传工具-自测日志.txt`（6,140 B）。
- **官方 §1 第 2 项允许二选一**（"镜像 tar **或** Dockerfile + 构建说明"），故分片**不是必选项**：若百度网盘单文件上限吃不下 22.2 GiB，可直接改交 `reproduction/Dockerfile` + 构建说明（DB 内已有 `Dockerfile` 校验记录）。
- 上传注意：文件夹命名 `369583+default13319669`；**分享有效期务必选「永久」**（会填进问卷②）；上传完把链接回填问卷②。

### 17.5 仍未闭合（09-22）

1. **百度网盘单文件上传上限**：本 session 无 WebSearch，WebFetch（`help.baidu.com`、`pan.baidu.com/buy/center`）均未取到数字 → **不臆断**，按 ≤3.7 GB × 7 分片 + Dockerfile 双路线准备，实际以客户端提示为准。
2. ~~**答辩 PPT**：仍未产出。~~ **已于 09-22 上午产出并闭合**（`答辩PPT/` 三件套，13 页；见 §18.1）；官方 §1 第 5 项「方案文档与答辩 PPT 一致」现有 PPT 实物双向可达。
3. 阶段 1 无本机 GPU、不可重跑（同 §16.7 第 3 条，边界已写入全部文档）。

## 十八、09-22 上午（续）：答辩 PPT 产出 + 第五次重打 + 第六次重打（终版）+ 上传夹 06 项

触发：官方 §1 第 5 项「方案文档**与答辩 PPT 一致**」此前只有文档、没有 PPT 实物 → 本轮用 **bento-deck** 技能产出 13 页单文件 HTML deck；因为「方案文档.md」「提交说明.md」都在源码包内，改完两份文档后**源码包必须第五次重打**（镜像包不动）。第五次重打后逐页目检 13 页全渲染截图，又抓出 PPT 上一处数字滞后 → **第六次重打**收口（见 §18.6）。

### 18.1 答辩 PPT（本次新建 `D:\文本生成3D方案赛\答辩PPT\`）

> ⚠️ 下表为第五次重打口径；**第六次重打后的终值见 §18.6**（可编辑版 `3ed71a46…` / md5 `5fe04ce0…`、放映版 `4fd67638…` / md5 `dde564d3…`；`说明.md` 未变）。字节数三行均未变。

| 文件 | 字节 | SHA256 | md5 |
| --- | --- | --- | --- |
| `369583+default13319669_答辩PPT.bento.html`（**可编辑版**） | 652,855 | ~~`62ce1e9041103f0cfecd2f02fea99b2dabb7f3f2a21f64a14bff4aa8fd8882e5`~~ → `3ed71a4630d8bf37a03d5fea5f3644f55e32d62cd2080ca882ccf87bce8c5b0d` | ~~`22337dc3ca043e41339f6e19ab54e414`~~ → `5fe04ce050888637fca64a78a40d14ee` |
| `369583+default13319669_答辩PPT.play.bento.html`（**放映版**） | 652,871 | ~~`9f70b2ffff4908098ea1743d7b4133b0d43ebbb5a69ff12444ce891b262f79c2`~~ → `4fd67638888f83d912933c54c07885e16ddcfd2e98b1affa428917e7941d3b25` | ~~`a9aa0712e13d3eb9f70a11f3014c6e57`~~ → `dde564d39f212f5a27fd8ab5e2825765` |
| `说明.md`（打开方式/翻页键/两个版本区别） | 1,777 | `cfddbba693a7bcb2bc3360d9a0478c30ab0ee59f9b87061ff04a741463f94368` | `0c97fa70bcd056427013218bc1895871` |

- **工具选择**：本机有 `bento-deck`（`C:\Users\dfjq\.agents\skills\bento-deck\`，IKB 克莱因蓝、单文件 HTML、内置中文编辑器 + morph + 演讲者备注），**`PPT-master` 本机不存在**（已核）。deck 源 = `decks/bdci_text2_3d.py`（放在 skill 目录内，不落工作区）。
- **13 页顺序**：问题理解 → 总体方案 → 四个关键设计决策 → 实测数据 → 「复现 = 初赛提交」对拍（最强门禁）→ 官方要求逐条达成 → 工程化交付 → 三个真问题 → 局限与如实声明 → 提交材料与上传 → 一键复现；**页面上每个数字都取自 `方案文档.md`**（同口径、同数字来源），故官方第 5 项"一致"是**构造上成立**，不是事后比对。
- 两个版本内容一致：放映版只读（双击即全屏放映、`←`/`→` 翻页、`S` 看备注）；可编辑版带内置编辑器，评委/队友可改。
- 交付**双份**：上传夹 `06_` 三项 + 源码包内 `答辩PPT/` 三项（同一份，已 md5 逐份复核）。

### 18.2 截图抽验（两轮）发现并修掉的三处缺陷

1. **P4 左右栏错位**：右栏标题与左栏不在同一 y、单位说明悬空成"cm。"→ 重构为两栏同 y=190/230 + 整幅「尺寸语义 → 轴映射 → 词表」表；
2. **P12 表格第 5 行被裁**：① 校验格写成三行撑破固定表高 → 压回两行（"85 个条目 /（哈希见随附清单）"）；
3. **自指缺陷（由门禁抓到，重要）**：deck 里写了**旧 zip 的字节数 7,960,946 与旧哈希** —— 既属"包内记录自身哈希"的自指，又会随着每次重打过期 → 删掉字节数与旧哈希，只留"85 个条目（哈希见随附清单）"。**修完重打后自指扫描 0 命中**。

### 18.3 第五次重打（82 → 85 项；镜像包未变）

| 交付物 | 文件 | 字节 | SHA256 |
| --- | --- | --- | --- |
| Docker 镜像（**未变**） | `hy3d-repro_20260921.tar.gz` | 23,867,134,532 | `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` |
| 算法源码 + 文档 + 证据 + **答辩 PPT**（~~第五次重打~~ → **第六次重打 = 终版见 §18.6，85 项**） | `复现推理源码包_v5_20260921.zip` | ~~8,768,569~~ → **8,768,573** | ~~`e0db7d9dea74782c24bee78d9603fd6be43c60978867fd05d7a9ff47ddcad48a`~~ → **`102906910e20cd8b86b0fe5dd8bb8eda4ab9756641a5ab4abff589bfcdd5465d`** |
| 校验清单（清单自身不含校验值） | `交付清单-SHA256.txt` | ~~8,107~~ → **8,417** | 冻结时间 **2026-09-22**，md5 ~~`ae32949c63eabbc692fa093c26a8cd51`~~ → **`db7f7b5a184ead3be85e9f46c468b818`**（上传夹内副本逐字节相同） |

- 净变化：① 新增 `答辩PPT/` 三件套；② `方案文档.md` 口径说明改写 + §八 第 1 项改为「答辩 PPT（已完成，2026-09-22）」并列出 13 页顺序；③ `提交说明.md` §一/§五/§六 同步收录 PPT（§五 明确"完整 85 个条目"）；④ `实测记录/14` 更正一处条目名编码表述 + 新增 §6 第五次重打记录。
- 重打门禁（全部独立执行）：**磁盘 ↔ zip 全量 85 项 md5 对拍 0 不一致 / 0 缺失**、`testzip` OK、权重二进制 0 条、`__pycache__` 0 条、**包内自指哈希扫描 0 命中**、包内 5 个推理源码 ↔ **镜像内 `/app` md5 仍 5/5 一致**。
- **重打后二次核验（本 session 收尾时又跑了一遍；下面这段是第五次重打口径，第六次见 §18.6）**：两份 zip 副本 md5 均 = `f00b5c281ab7290d8568898fba772f2c`（8,768,569 B，逐字节同一份）；**上传夹 7/7 副本与其工作区原件逐字节一致**（01↔源码包、04↔复现说明文档、05↔方案文档、06×3↔答辩PPT/、交付清单）；**包内 `方案文档.md` md5 `bc22d131…` = 磁盘版 md5**（证明文档改写确实进了包）；工作区全树无 `_v3_`/`_v4_` 旧包残留。
- 收尾又修一处错别字：`交付清单-SHA256.txt` 第 43 行「离构建支持」→「**离线构建支持**」（该文件在两份交付包**之外**，故无需再次重打；修完两份副本仍逐字节相同，字节数 8,104 → 8,107）。

### 18.4 上传夹现状（`复现提交包/上传百度云盘/`，12 项；**第六次重打后的终值**）

`01_算法源代码_…zip`（8,768,573 / `4409060d…`）· `02_运行环境_镜像包_生成分片.bat`（4,230）· `03_模型权重_下载地址与SHA256.md`（12,348）· `04_复现说明文档.md`（29,779）· `05_方案文档.md`（14,057 / `bc22d131…`）· `06_答辩PPT_可编辑版/放映版/说明.md`（652,855 / 652,871 / 1,777）· `上传工具-自测日志.txt`（6,140）· `上传说明-百度云盘.md`（9,338 / md5 `c9bc0f3587a51395493d2405847a37c4`）· `交付清单-SHA256.txt`（8,417 / `db7f7b5a…`）· `合并分片.bat`（1,301）

（第五次重打口径的旧值：zip 8,768,569 / `f00b5c28…`、清单 8,107 / `ae32949c…`、上传说明 8,777 / `a1479873…`。）

### 18.5 仍未闭合（09-22 收尾）

1. **上传动作本身**：`上传百度云盘/` 整个文件夹 + （若走分片）`镜像分片` 文件夹传到网盘 → 分享有效期选「永久」→ 链接回填问卷②；队长填问卷①。
2. **镜像包走哪条路**（分片 vs Dockerfile + 构建说明，官方 §1 第 2 项并列可选）：百度网盘**单文件上限仍未核实**（不臆断）→ 两条路都已备好，建议群里问一句再决定；本机上行 0.22 MB/s，直传单文件 22.2 GiB ≈29 h 不可行。
3. 阶段 1 无本机 GPU、不可重跑（同 §16.7 第 3 条，边界已写入全部文档）。

### 18.6 第六次重打 = 终版（09-22 上午，PPT 数字滞后触发；条目数仍 85）

- **触发**：第五次重打后把 13 页**全页渲染截图逐张目检**（不是抽样），发现第 12 页「⑤ 方案文档」校验列仍写 `方案文档.md` 重写**之前**的体积 **13,379 B**（重写后真实值 **14,057 B**）。→ 改 deck 源文件该单元格 → `build.py` 重建两版 → 重截 P12 目检确认。
- **为何必须重打 zip**：`答辩PPT/` 三件套**在源码包内**，PPT 改了包就变了 —— 这是 §18.2 第 3 条「自指缺陷」的同一逻辑延伸：**PPT 里不能出现任何会随重打过期、或记录包自身哈希的信息**；但**可以且应当**出现方案文档的真实体积（那是文档属性，不是包的属性），故此处是"改对值"而非"删掉值"。
- **终值（口径唯一，全文以此为准）**：

| 交付物 | 文件 | 字节 | SHA256 | md5 |
| --- | --- | --- | --- | --- |
| Docker 镜像（**未变**） | `hy3d-repro_20260921.tar.gz` | 23,867,134,532 | `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` | — |
| 算法源码 + 文档 + 证据 + 答辩 PPT（**第六次重打 = 终版，85 项**） | `复现推理源码包_v5_20260921.zip` | **8,768,573** | **`102906910e20cd8b86b0fe5dd8bb8eda4ab9756641a5ab4abff589bfcdd5465d`** | `4409060d9b8d0ebdfbf4b727b1cfb72c` |
| 答辩 PPT 可编辑版 | `…_06_答辩PPT_可编辑版.bento.html` | 652,855 | `3ed71a4630d8bf37a03d5fea5f3644f55e32d62cd2080ca882ccf87bce8c5b0d` | `5fe04ce050888637fca64a78a40d14ee` |
| 答辩 PPT 放映版 | `…_06_答辩PPT_放映版.bento.html` | 652,871 | `4fd67638888f83d912933c54c07885e16ddcfd2e98b1affa428917e7941d3b25` | `dde564d39f212f5a27fd8ab5e2825765` |
| 答辩 PPT 说明（**未变**） | `…_06_答辩PPT_说明.md` | 1,777 | `cfddbba693a7bcb2bc3360d9a0478c30ab0ee59f9b87061ff04a741463f94368` | `0c97fa70bcd056427013218bc1895871` |
| 校验清单 | `交付清单-SHA256.txt`（两份副本） | 8,417 | — | `db7f7b5a184ead3be85e9f46c468b818` |
| 上传说明 | `上传说明-百度云盘.md` | 9,338 | — | `c9bc0f3587a51395493d2405847a37c4` |

- **重打门禁（全部独立执行，无一项沿用旧结论）**：`entries: 85`；`testzip` OK；**磁盘 ↔ zip 全量 85 项 md5 对拍 mismatch=0 / missing=0**；权重二进制泄漏 0；`__pycache__`/`.pyc` 0；零字节条目 0；58 个文本条目 UTF-8 全部可解码；**包内自指扫描（本轮把扫描词表扩到 zip 自身新旧 sha/字节数 + PPT 两版新旧 sha256，覆盖 61 个文本条目）hits=0**；7 个关键入口文件齐备；`样例渲染图/` 23 条、`答辩PPT/` 3 条。
- **包内推理源码 ↔ 镜像内 `/app` md5 仍 5/5 一致**（`docker run --rm --network none --entrypoint "" hy3d-repro bash -lc 'md5sum /app/*.py'` 重跑复核：`build_submission.py` `2058b50e69226b271073b25859c99521`、`generate_hy3d.py` `a0b6ce19fea526bfd598e72ea1101d78`、`postprocess.py` `e067e6f8058d021f158f10ffabed8c90`、`render_views.py` `4881bb9e8186843b1a652be7b0560bfa`、`verify_weights.py` `989a093c616f4d0c45d6388922b61187`）。
  **09-22 收尾再独立复核一遍（全值）**：镜像内 `md5sum /app/*.py` 五值 = 磁盘 `pipeline/build_submission.py`・`cloud/generate_hy3d.py`・`pipeline/postprocess.py`・`pipeline/render_views.py`・`reproduction/verify_weights.py` 逐一相同（工作区另有同名历史副本 `带到4090电脑/generate_hy3d.py`、`cloud/verify_weights.py`，**不参与此断言**，勿混用）。
- **传播已核**：`复现提交包/` 与 `上传百度云盘/01_` 两份 zip **逐字节相同**（8,768,573 / `4409060d…` / `10290691…`）；PPT 两版与 `说明.md` 已按新哈希派发进上传夹 `06_` 三项；`交付清单-SHA256.txt` 两份副本改写后仍**逐字节相同**；上传夹现状见 §18.4（12 项，全部为终值）。

## 十九、09-22 收口总览 —— **新 session 从这里接**（材料已备齐并逐项验真；只剩上传与决策）

> 本节是**自足的一节**：只读这一节 + [[文本生成3D方案赛-主索引]]，就能接手。
> 上一节（§18）记录生产过程的细节；本节只讲**现在是什么状态、还差什么、怎么验**。

### 19.1 一句话状态

**官方 v1.0《决赛复现提交要求》五项提交物全部备齐、全部验真，上传夹 12 项可直接拖进百度云盘。** 除队长/用户填两份问卷外，只剩三件事：**实际上传**、**定镜像包走哪条路**、**把 5 个问题问清组委会**。死线 **2026-09-23 24:00**（本节写于 09-22，仅剩一天）。

### 19.2 官方 §1 五项提交物：实体文件 + 终值哈希（口径唯一）

| 官方项 | 我方实体文件 | 字节 / SHA256 | 验真方式 |
| --- | --- | --- | --- |
| ① 算法源代码 | `369583+default13319669_01_算法源代码_复现推理源码包_v5_20260921.zip` | **8,768,573** / `102906910e20cd8b86b0fe5dd8bb8eda4ab9756641a5ab4abff589bfcdd5465d`（md5 `4409060d9b8d0ebdfbf4b727b1cfb72c`）/**85 条目** | `testzip` OK；磁盘 ↔ 包内 85 项 md5 **零差异零缺失**；权重二进制 0 条；`__pycache__` 0 条；零字节 0 条；58 个文本条目 UTF-8 全可解码；**包内自指/陈旧哈希扫描（覆盖 61 个文本条目、含 zip 与 PPT 的新旧值）0 命中**；两份副本**逐字节相同** |
| ② 运行环境 | `hy3d-repro_20260921.tar.gz` + `…_02_运行环境_镜像包_生成分片.bat`（4,230）+ `合并分片.bat`（1,301）<br>**并列备份路线**：包内 `reproduction/Dockerfile` + 构建说明 | tar **23,867,134,532** / `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` | 本次用 `certutil -hashfile` **在磁盘上直算复核 = 清单一致**；`pigz -t` 全量解码 rc=0（无截断）；**删净本机镜像后由该 tar 单独 `docker load` 还原出同 ID `56b164216646`/同 CONTENT SIZE 23,889,774,410 B/同 19 层，并断网跑通单题且产物与三题实测逐字节相同**；分片工具已用 3,500,007 B 样本真跑「切→合并→md5 逐字节一致」 |
| ③ 模型权重 | `…_03_模型权重_下载地址与SHA256.md`（12,348） | — | 23 文件国内双源（ModelScope + hf-mirror）+ 逐文件 SHA256 + 许可证 + 镜像内路径；本地 sha256 与官方摘要**零不符**；由 `weights_manifest.json` 自动生成、无手工转写 |
| ④ 复现说明文档 | `…_04_复现说明文档.md`（29,779） | — | 官方 §3 模板**单文件**，3.1~3.5 五节齐备；附 A 官方自查 8 条逐项对照、附 B 证据索引、附 C 修复记录 |
| ⑤ 方案文档 | `…_05_方案文档.md`（14,057 / md5 `bc22d131091ae3b65a14ba25b1cdef21`） | — | 官方唯一硬约束「**与答辩 PPT 一致**」：PPT 页内每个数字逐项取自该文档（构造上一致），且 13 页全渲染图**逐页目检核对过** |
| ⑥ 答辩 PPT（附加） | `…_06_答辩PPT_放映版.bento.html`（652,871 / SHA256 `4fd67638888f83d912933c54c07885e16ddcfd2e98b1affa428917e7941d3b25`）<br>`…_06_答辩PPT_可编辑版.bento.html`（652,855 / SHA256 `3ed71a4630d8bf37a03d5fea5f3644f55e32d62cd2080ca882ccf87bce8c5b0d`）<br>`…_06_答辩PPT_说明.md`（1,777 / SHA256 `cfddbba693a7bcb2bc3360d9a0478c30ab0ee59f9b87061ff04a741463f94368`） | 见左 | 13 页单文件 HTML（`←`/`→` 翻页、`S` 看备注、可编辑版内置中文编辑器）；随源码包 `答辩PPT/` 另有一份，**包内外逐字节相同** |
| 校验/说明 | `交付清单-SHA256.txt`（**8,417** / md5 `db7f7b5a184ead3be85e9f46c468b818`，两份副本逐字节相同）、`上传说明-百度云盘.md`（9,338 / md5 `c9bc0f3587a51395493d2405847a37c4`）、`上传工具-自测日志.txt`（6,140） | — | 清单在两份交付包**之外**，故自身不含自身哈希（避免自指死循环） |

**运行与接口（§2.1~2.4）**：入口 `bash run_infer.sh /input/prompts.jsonl /output` 已按契约实现、断网 `--network none` 实测 rc=0；输出结构 `manifest.json` + `_logs/` + 每题 `{model.glb, metadata.json, process.md, renders/四视图}` 逐条命中；`metadata.json` 8 键齐全；单位 mm、Z-up 底面朝下、真实量级、**未归一化**均满足。**官方 §4 八条自查清单**在 `04_复现说明文档.md` 附 A 中逐条对应到证据文件。

### 19.3 除了两份问卷，还剩什么（可照做）

1. **实际上传**（需用户百度网盘账号，我无法代做）：网盘新建文件夹 `369583+default13319669` → 拖入 `D:\文本生成3D方案赛\复现提交包\上传百度云盘\` **全部 12 项** +（若走分片）`镜像分片` 文件夹 → **分享有效期必须选「永久」**（默认 7 天，评委到期打不开）→ 链接回填问卷② `docs.qq.com/form/page/DYmFWa1Vyd0dLa21n`。传完用**未登录浏览器**自开一次验证。问卷① `docs.qq.com/form/page/DYnVkVFpUZHpSS2dU` 由**队长**填。
2. **定镜像包路线**（官方 §1 第 2 项是**并列**写法，二选一）：
   - **分片上传**：双击 `…_02_运行环境_镜像包_生成分片.bat` → 切 ≤3.7 GB × 7 片 + 分片清单 + 自动放入 `合并分片.bat`；输出默认 `C:\百度网盘上传\镜像分片\`，需约 22.4 GB 空闲。
   - **只交 Dockerfile + 构建说明**：包内已备 `Dockerfile` / `requirements-lock.txt`（130 包）/ `wheels_manifest.json` / `vendor/` 两个自备轮子 / 两条零联网构建通道 → **完全免去 22.2 GiB 传输**（回填问卷备注里写明"按官方 §1 第 2 项并列可选，采用 Dockerfile + 构建说明"）。
   - 事实依据：本机上行实测 **0.22 MB/s** → 直传单文件 22.2 GiB ≈ **29 小时**，不可行；**百度网盘单文件上限未获确认**（本 session 无 WebSearch，未取到数字，**不臆断**）。
3. **一次问清组委会 5 件事**（09-20 起挂着，**至今未问**）：① 镜像体积上限与提交渠道；② 单题推理时限；③ 答辩 PPT 与方案文档是否同窗口（09-21~24）同渠道提交；④ 有无 PPT 模板与命名规范；⑤ 大群通知的《复现材料准备说明》与 v1.0 PDF 冲突时以哪份为准。**渠道提示**：本机钉钉 14 个群**没有本赛事群**（09-22 实测），跨会话搜索也无命中 → 官方口径渠道是**平台站内信 / 邮箱 / 赛题页**，别指望从钉钉补口径。

### 19.4 如实声明的边界（不要在新 session 里被"看起来全绿"骗过去）

- **阶段 1（GPU 文生图 / 形状生成）本机无法重跑**——本机无 NVIDIA GPU。包内 `实测记录/01~05` 的断网实测走的是**阶段 2**（`INFER_PROC_ONLY=1`）；本机唯一一套 40 题原始网格是 09-05 调试期噪声批次（VAE 缺陷期，语义不正确）。此边界写在包内 `样例渲染图/来源说明.md` 与 `04_复现说明文档.md`，**没有藏**。
- 最强的一条证据是**交付镜像内断网、以初赛提交包 40 题真实成品几何为阶段 2 输入重跑**：渲染图 **160/160 张逐字节一致**（40/40 题 × 4 视图）、metadata 逐字段一致、面/顶点/单体/水密 40/40 相同、包围盒 39/40 ≤0.01 mm（中位 0.0006 mm）；唯一离群 `hid_sma_001`（26.69 mm）已用三条旁证归因为**提交版自身缺陷被复现修正**（提交版 43.3 mm 且整体悬空 6.64 mm → 复现 70.0 mm 贴地）。
- 百度网盘单文件上限**未获确认**，两条路线都已备好，没有拿猜测当结论。

### 19.5 若新 session 要动手改任何东西，先读这三条纪律（附：复核工具与收尾门禁结果）

1. **包 = 已测代码**：`答辩PPT/`、`方案文档.md`、`提交说明.md` 等**都在源码包内**，改任何一件 → **必须重打 zip → 重跑全部门禁 → 更新包外的 `交付清单-SHA256.txt`（两份副本）与 `上传说明-百度云盘.md` §五 → 重新派发到上传夹 `01_` 与 `06_`**。重打工具保留在 `D:/wsl/tmp/zip6.py`（另 `dispatch6.py` 派发 + `final_audit.py` 终检），**必须用 Windows `py` 跑**（脚本内是 Windows 路径，用 WSL python 跑会产出垃圾空包）。
2. **自指禁令**：包内任何文件**不得记录包自身哈希，也不得记录会随重打而过期的哈希**；哈希只写在包外的清单里。现有扫描词表已覆盖 zip 自身新旧 sha/字节数 + PPT 两版新旧 sha256，**重打后必须跑出 hits=0**。
3. **危险操作纪律**：任何删除/覆盖前先只读确认范围、精确具名、禁止宽泛通配、独立成步、事后复核。历史上一次在 WSL python 下误跑 `zip6.py` 曾在工作区根目录生成一个 22 字节怪名文件，已按名精确删除并复核。
4. **复核工具清单**（全在 `D:/wsl/tmp/`，除注明外都用 Windows `py` 跑，**均为只读**）：`final_audit.py`（清单声明值 vs 真实文件 + zip 内条目对拍）、`gate_zip_vs_upload.py`（包内 ↔ 上传夹 ↔ 磁盘逐字节 + **全 85 条自指扫描**）、`gate_cross_final.py`（上传夹 ↔ 工作区逐字节）、`check_final_state.py`（陈旧值 / 制表符扫描）、`check_links19.py`（wiki 链接可达 + 本节关键值门禁）、`verify_upload.py`・`mkupload.py`（上传夹生成与复核）、`gen_split_bat2.py`（重生成分片 bat）、`zip6.py`・`dispatch6.py`（重打与派发，**改动型**，勿轻易跑）。
5. **09-22 收尾这一轮的门禁结果（全绿，可引用）**：上传夹 **12 项**声明值全 OK（zip `8,768,573` / md5 `4409060d9b8d0ebdfbf4b727b1cfb72c` / sha256 `102906910e20cd8b86b0fe5dd8bb8eda4ab9756641a5ab4abff589bfcdd5465d`；PPT 两版 sha256；`05_方案文档.md` md5 `bc22d131091ae3b65a14ba25b1cdef21`；清单 md5 `db7f7b5a184ead3be85e9f46c468b818`；上传说明 md5 `c9bc0f3587a51395493d2405847a37c4`；无未申报文件）；zip 两份副本 / `05`·`04` / PPT 三件 / 交付清单 与工作区**逐字节 IDENTICAL**；**包内 5 件**（`答辩PPT/`×3 + `方案文档.md` + `提交说明.md`）与磁盘**逐字节 IDENTICAL**、**全 85 条自指扫描 hits=0**；§19 关键值 **14/14** 齐备、**无制表符**、**18 条 wiki 链接 0 缺失**；镜像内 `md5sum /app/*.py` 与磁盘 5 文件（`pipeline/build_submission.py`・`cloud/generate_hy3d.py`・`pipeline/postprocess.py`・`pipeline/render_views.py`・`reproduction/verify_weights.py`）逐一相同；**本机 `hy3d-repro`（`56b164216646`）仍在**，可直接复跑复核。

## 二十、09-22：阶段 1 未重跑 —— 能否提交与风险评估（结论级，新 session 可直接引用）

> 触发：用户提问"阶段 1（GPU 文生图/形状生成）本机无法重跑，不跑阶段 1 是否可以提交复现材料，风险是什么？要求以客观事实为准、与官方口径一致"。
> 核对方式：官方 v1.0 逐字（桌面 `.docx` 解包取全文，与 `.pdf` 同版）+ 包内四处声明 + 入口/脚本静态核对。**本次未改动任何交付物**。

### 20.1 结论三条

1. **可以提交，不因"没跑阶段 1"构成材料缺失。** 官方 v1.0 全文没有一条要求"参赛队自行跑通全流程"或"提交实测证据/日志"；首页原文"**主办方将在断网隔离环境下按第 2 节接口运行你们的代码**"——复现的**执行主体是主办方**。§1 五项提交物与 §4 八条自查清单中均无"实测报告"一件；我方 `实测记录/` 属自愿附加的加分项，不是门槛。
2. **"未跑阶段 1"已在包内主动披露四处，不属于隐瞒或夸大**：`04_复现说明文档.md` §3.1「无 GPU 也能跑」（明写走 `INFER_PROC_ONLY=1` 只跑阶段 2）、§3.5 限制 6（明写本机无 NVIDIA GPU、初赛 raw 已随云实例释放）、附 B 说明 1（明写 01~05 只证入口契约/后处理连通性/产物结构，**不代表生成语义质量**）、`实测记录/样例渲染图/来源说明.md`（三批图逐批标口径）。
3. **真正的风险不在"能不能交"，而在"主办方跑的时候阶段 1 是否一次通过"** —— 属"低概率、高后果"残差风险，范围见 20.2。

### 20.2 残差风险已收窄到单一环节

已实测/已核对、可覆盖的部分：

- **代码同一份**：镜像内 `/app` 5 个推理源码 ↔ 源码包 ↔ 磁盘 md5 一致 5/5（含 `generate_hy3d.py`）。
- **入口与脚本参数对齐**（09-22 本次静态核对，新增证据）：`run_infer.sh` 阶段 1 传入的 `--prompts / --out / --t2i-model / --shape-model / --shape-subfolder / --vae-subfolder` 与 `--tex-model / --no-texture`，在 `cloud/generate_hy3d.py` 的 argparse 中**全部存在且语义相符**（默认 `TEX_MODEL` 为空 → 走 `--no-texture`）；默认超参 `steps=30 / octree=320 / guidance=5.5 / seed_base=42` 与初赛实测口径（`方案文档.md` 第 73 行）**逐项一致**；阶段 1 前置自检（t2i/shape 权重目录非空、u2net 就位）已在镜像内实跑通过（`实测记录/01`：14G/4.0G/168M）。
- **软件栈同源**：初赛跑通时的环境快照 `reproduction/env_snapshot_20260907.txt` 与镜像内关键包**版本号一致**（torch 2.3.1 / diffusers 0.31.0 / transformers 4.57.6 / hy3dgen 2.0.2 / rembg 2.0.69 / numpy 2.2.6 / trimesh 5.1.0 / accelerate 1.14.0）。**未核对项（如实记）**：快照不含 torch wheel 的 CUDA flavor（cu121 vs cu124），镜像内为 `+cu121`。
- **权重**：镜像内 24 文件门禁通过（`实测记录/05`）；这批权重 + 代码曾在云 4090 上产出初赛提交版产物。

仍未实测（= 残差风险的全部内容）：**镜像内 CUDA 12.1 运行时 + 宿主驱动 ≥530 条件下，`diffusers`/`hy3dgen` 真正把 HunyuanDiT(1.52B) + 形状 DiT(1.91B) 加载进 24 G 显存并出图**。另：显存下限未做边界测试（已在限制 1 如实声明）。

### 20.3 补跑阶段 1 的边际收益与反作用风险（如实权衡）

- **路径 A（租 4090 走源码方式）**：`云环境恢复手册.md` 的平台自定义镜像 `hy3d-t2i-fixed` 可 5 分钟恢复环境，或按 `cloud/` 脚本重装；成本约 1~2 h + 十几元。**只能证明"源码 + 权重在本轮修复版代码下仍能在 GPU 上出有效几何"，不能证明"交付镜像内阶段 1 可跑"**（容器 CUDA 运行时那一层仍未触及）。**反作用风险**：换硬件后扩散采样结果大概率不与初赛提交版逐字节一致，若补跑反而要在文档里新增一段"与初赛不完全一致"的说明——而官方并未要求逐字节复现（该命题只在阶段 2 侧被我方以 160/160 对拍自证）。
- **路径 B（把交付镜像 load 到 GPU 机器上跑阶段 1）**：唯一能真正闭合残差风险的路径，**卡在传输**——镜像包 22.2 GiB、本机上行实测 0.22 MB/s ≈ 29 h，9/23 24:00 前**物理不可行**；且租用实例多为容器环境，不能再跑 Docker。
- 结论：窗口内路径 B 不可行、路径 A 收益有限且有反作用风险 → **"不跑阶段 1"是当前条件下的合理选择，不是懒**。

### 20.4 优先级更高的一件（别被阶段 1 分散注意力）

真正卡住"能不能交"的是**镜像包传输与渠道**（见 `19.3` 第 2、3 条）：22.2 GiB 单文件 / 上行 0.22 MB/s / 网盘单文件上限未获官方确认 / 组委会 5 问至今未问。官方 §1 第 2 项是**并列可选**（Dockerfile + 构建说明），是时间窗内的降风险选项。

### 20.5 建议动作（按优先级）

1. **不因阶段 1 推迟提交**：材料齐、口径实（四处主动披露），按现方案上传 + 回填问卷。
2. 问组委会时把"镜像包形态/单文件上限"与"能否按 §1 第 2 项走 Dockerfile 路线"合并成一问 → 一次同时解决渠道与残差风险的一半。
3. 若手上/能借到 4090 机器（`带到4090电脑/` 即为此准备）且确要补证据：**必须用 `cloud/generate_hy3d.py`（09-21 版，15,904 B）**；`带到4090电脑/generate_hy3d.py`（09-04 版，5,511 B）是 VAE 零占位缺陷期版本，**用了会产出噪声几何**（第十五节已登记"不参与断言、勿混用"）。
4. **不建议**为此改附 A 第 1 行措辞而重打交付包：代价是全部门禁 + 重派 + 重出两份清单；收益仅是降低"快速浏览者误读"的可能（三处正文已写明阶段划分）。

---

## 二十一、09-22：答辩 PPT 体裁复核 —— **它是合格的「提交版」，不是合格的「答辩稿」**（用户提问「这份 PPT 支撑不了线上答辩，像项目梳理而非答辩思路」触发）

**用户判断成立。** 更准确的定性不是"内容不好"，而是**交付对象错配**：现在这 13 页是为官方 §1 第 5 项「方案文档与答辩 PPT 一致」优化的——它的使命是**与 `方案文档.md` 同口径、可逐项核查**，本质是"方案文档的可视化 + 验收证据墙"。这个使命它完成得很好。但**决赛当天线上答辩要说服的是评审的三条考察重点**（算法创新与管线设计 / 工程落地与系统效率 / Demo 演示），而这份 deck 的叙事顺序、信息密度、证据取舍都是按"文档阅读"设计的，不是按"8~10 分钟口头说服 + 共享屏幕"设计的。

### 21.1 量化证据（本 session 逐页解析 `答辩PPT/*.bento.html` 内 bento JSON 得出，非印象判断）

| 指标 | 实测值 | 答辩稿的合理量 | 判定 |
|---|---|---|---|
| 全 deck 纯文字量 | **6,030 字**（页均 **463 字**） | 页均 80~120 字 | ❌ 超 4~5 倍；按 240 字/分钟"读稿"需 25 分钟 |
| 正文字号 | **众数 14 px / 最小 12 px**（≥30 px 的只有 19 处 / 共 165 处元素） | 演示正文 ≥24 px | ❌ 线上共享屏幕后评委小窗口不可读 |
| 表格为主体的页 | **4 / 13 页**（第 4、8、10、12 页；表格单元格合计 1,599 字） | ≤1 页 | ❌ 表格是文档体裁，不是演示体裁 |
| 页标题句式 | 多为**验收结论/自查结论**（"交付不是「结构看着对」…""我们不宣称没有验证过的东西""五项提交物已按…命名就绪""官方入口一次跑完，门槛与物理合规全部达标"） | 主张句/问题句 | ❌ 主语是"我们交付了什么"，不是"我们发现了什么、怎么想" |
| 官方三条考察重点覆盖 | 算法创新与管线设计 ✅（②③④⑤）／工程落地与系统效率 ✅（⑥⑧⑨⑩）／**Demo 演示 ❌ 无专门页** | 三条都要 | ❌ 缺 1/3 |
| 官方「FDM 实物打印验证」 | **0 页**（deck 内 `FDM`/`打印` 20+5 处命中，全部在讲"可打印性/后处理"，`实物`/`视频` 命中 0） | 应有实物或切片实证页 | ❌ 缺 |
| Q&A 预埋页 | **0 页**（最强证据 ⑦ 对拍、⑨ 镜像自足性、⑧ 官方自查表都摆在主讲线上） | 高价值证据应沉到 Q&A 库 | ❌ 主讲线被证据挤占 |
| Demo 形式 | 第 13 页是**三行命令的文字说明**，不是演示 | 现场跑或录屏 | ❌ "说明"≠"演示" |

**结构性问题一句话**：现在的主讲线是「赛题理解 → 方案 → 决策 → 数据 → 对拍 → 官方逐条 → 交付 → 问题 → 局限 → 材料 → 一键复现」——这是一条**交付清单线**。答辩线应该是「矛盾是什么 → 我们的选择 → 它真的成（现场证明）→ 它哪里还不成 + 怎么补」。

另一处**定位风险（值得单独记住）**：初赛 **3.15 / 第 9 名**是压线晋级、**语义是明确弱项**（`文案-解题思路与作品亮点.md` 已自认），而现 deck 把 3.15 摆在封面当门面、把最强证据给了"复现=提交"——等于答了一场"我们合规"的辩，而不是"我们方案好"的辩。语义与多视图视觉恰恰是评分里权重最大的那一块。

### 21.2 为什么不建议现在动手重做（三条硬理由，不是拖延）

1. **时序**：决赛在 **10-08~31**，晚于本窗口（09-23 24:00 交复现材料）。这个窗口要交的是"与方案文档一致"的那一份，**现 deck 正好满足**。
2. **素材**：答辩版的价值全在三样**尚无**的东西上——① FDM 实物（`找打印机` 仍是待办，实物未打印）② Demo 录屏（未录）③ 若做 L1/L3 语义提分（`主索引 §7 第 6 条`）后的**新数字**。现在做，内容一个月后大概率要推翻重做。
3. **代价**：动 deck 会牵动源码包 v5（**终版**）与上传夹 `06_` → 按 `§19.5 纪律`必须**第七次重打 + 重出两份 SHA256**。为一个要推翻的版本付这个代价不值。

→ **处置：提交版零改动保留；另起一个「决赛答辩版」，本窗口只定结构、采素材留到公布入围（09-30）之后。**

### 21.3 决赛答辩版结构方案（12 页，目标 8~10 分钟主讲 + Q&A；**待用户确认后再动手**）

核心叙事线：**矛盾 → 选择 → 现场证明 → 边界与下一步**。原则上**证据一条不丢**：主讲线只留最有说服力的，其余全部沉到 Q&A 预埋页。

| 页 | 任务 | 时长 | 素材要求 | 相对现 deck 的变化 |
|---|---|---|---|---|
| 1 | 封面：一句主张 + 一个数字 | 10 s | 主张改为"把 3D 生成做成能交给别人跑起来的生产线" | **撤掉封面上的 3.15/第 9 名**（挪到第 10 页诚实定位） |
| 2 | 矛盾：语义 vs 可打印的互相拉扯 | 45 s | 压到 3 行 | 现第 2 页，砍 2/3 |
| 3 | 一屏看懂的管线 + 每步耗时占比 | 60 s | 现状图加耗时标注 | 现第 3 页，加"效率"维度 |
| 4 | **创新点 1：尺寸语义解析器**（真实 prompt → 解析结果 → 交付尺寸三行对照） | 60 s | 需挑 2~3 条真实题面做实例 | 现第 4 页去掉词表表格，换成**实例** |
| 5 | 创新点 2：CPU 全软件渲染的取舍（配 4 视图实图） | 45 s | 已有（`样例渲染图/`） | 现第 5 页拆出 |
| 6 | 工程落地：三处静默降级，主讲只讲 `fast-simplification` 一例（另两例一句话带过） | 60 s | 已有（`实测记录/00`） | 现第 10 页，收窄到 1 例 |
| 7 | **Demo 演示位（全场最重要）** | 90~120 s | **待采：OBS 录屏 + 现场跑兜底两手准备** | **全新**（现 deck 缺） |
| 8 | 效果证据：40 题四视图拼版满屏 + 一句话给"160/160 逐字节一致" | 60 s | 已有（`样例渲染图/00_40题总览_perspective.png`） | 现第 7 页**只留结论**，对拍方法沉到 Q&A |
| 9 | **FDM 实物：切片预览 → 打印件 → 卡尺量关键尺寸** | 60 s | **待采：打印机 + 多角度视频/特写**；拿不到则退化为"切片软件打开交付 glb"的截图 + 壁厚/支撑数据，并注明"实物打印进行中" | **全新**（现 deck 缺） |
| 10 | 如实边界 + 诚实定位（3 条，语义弱项单列）+ 下一步三条路径 | 45 s | 已有素材 | 现第 11 页 5 条压 3 条，**3.15 与本轮改进方向放这里** |
| 11 | 为什么是我们 + 一句话收尾 | 20 s | 已有 | 现第 13 页精简 |
| 12+ | **Q&A 预埋页（不占主讲时间）** | — | 现 deck 第 8 页（官方逐条达成）、第 9 页（镜像自足性实测）、第 12 页（提交材料与 SHA256）、`hid_sma_001` 离群题归因、依赖闭包双 PASS | **现 deck 的"证据页"整体下移到这里**——不浪费，不占时 |

### 21.4 线上答辩的四个实操坑（现 deck 的"放映版"直接拿去共享屏幕会踩）

1. **演讲者备注会露出去**：放映版按 `S` 打开的备注浮层是页面内元素，**屏幕共享时评委也看得见**。→ 应把备注单独导出成一份讲稿，或第二屏/手机上看，**不要在主共享窗口里按 S**。
2. **字号**：现 deck 正文 14 px，线上共享后基本读不清；答辩版正文一律 ≥24 px，数字页 ≥48 px。
3. **Demo 必须有录屏兜底**：现场跑存在显存/时间/共享软件切换三重失败风险（且阶段 1 真 GPU 出图在本机从未实测过，见第二十节）→ 答辩版第 7 页**必须**预先录好一段，现场失败直接切录制。
4. **计时**：官方无时长规定 → 申请时必问；同时备 **5 分钟压缩版**（只讲 1、2、7、8、9、11 六页）。

### 21.5 并入组委会问题清单（原 5 问 → **7 问**，第 6、7 问为本次新增）

1. 镜像体积上限与提交渠道
2. 单题推理时限
3. 答辩 PPT 与方案文档是否同窗口（09-21~24）同渠道提交
4. 有无 PPT 模板与命名规范
5. 能否按 §1 第 2 项走 Dockerfile 路线（替代 22.2 GiB 镜像包）
6. **🆕 决赛线上答辩的时长限制与发言规则**（是否限时、是否允许放录屏）
7. **🆕 决赛「Demo 演示」的具体形式**（现场实时跑 / 允许提前录屏 / 需不需要留演示用输入样例）

### 21.6 决策状态

| 项 | 状态 |
|---|---|
| 提交版 deck（13 页，已冻结在源码包 v5 + 上传夹 06） | ✅ **零改动保留**（不作为答辩主稿） |
| 决赛答辩版（12 页结构如上） | ⏸ **待用户确认后动手**；素材采集排在 09-30 公布入围之后 |
| 是否现在重打源码包 | ❌ **不需要**（提交版不动 → 无自指牵连） |

## 二十二、09-22：答辩 PPT 提交时机定论 + 讲者手册产出（用户提问「本次交还是决赛交」+ 新约束「必须是我能讲出来并理解的」）

### 22.1 提交时机（**结论级，可直接执行**）

> ⚠️ **本节已被第二十三节推翻（2026-09-22 用户明确指示）** —— 用户原话：「**9 月 23 交付的文件包要与答辩 PPT 一致，所以这次就是要出答辩 PPT**」。含义：官方 §1 第 5 项把「方案文档」与「答辩 PPT」绑成一致性约束，**如果本窗口交的是一份"项目梳理式"的 deck，那方案文档也就被钉死在那套口径上**；用户要的是一份**真正的答辩稿**，因此**本窗口交的必须是答辩版**。→ 下表「交现有提交版 / 决赛版不交」两行**作废**，实际执行见 §23；本节的量化差距分析与讲者手册结论仍然有效并被 §23 沿用。

| 项 | 结论 | 依据 |
|---|---|---|
| **本窗口（09-23 24:00 前）交哪一份** | ✅ **交现有 13 页「提交版」**（已冻结在上传夹 `06_` 与源码包 v5，**零改动**） | ① **赛题页**原文把「答辩PPT」列入复现阶段提交内容（"答辩PPT、完整的算法源代码、运行环境配置（Docker 镜像）、复现说明文档、最终版方案文档"）→ 不交要额外解释，反而生变；② 官方 v1.0 §1 第 5 项唯一硬约束是「方案文档与答辩 PPT 一致」，按此口径 PPT 是方案文档的**一致性锚点**，抽掉则约束悬空；③ 已在冻结包内，**零成本** |
| **「决赛答辩版」本次交吗** | ❌ **不交，留决赛当天用** | ① 官方 v1.0 全文**无一条**要求决赛 PPT 在本窗口定稿（具名 5 项不含 PPT、§4 自查清单 8 条无 PPT 条目）；② 决赛版的两张核心页（Demo 录屏、FDM 实物）**素材尚不存在**（用户 09-22 明确：无录屏、无实物）；③ 若做 L1/L3 语义提分，数字还会更新 |
| **两份会不会破坏「一致」** | ❌ **不会** | 决赛版 = 提交版的**重排 + 精简 + 白话化**，数字与口径**零新增、零改动**（不引入任何未验证宣称）。先例已在：现在同包的「放映版 / 可编辑版」本就是"同一内容、多种呈现" |

**两处官方口径本就冲突（如实记住，别当成我方能决定的）**：v1.0 具名 5 项**不含** PPT；赛题页把「答辩PPT」**列入**复现提交内容。我方选择按**并集**处理（既放进提交物，又保持与方案文档一致），这是最保守的选择。→ 仍是待问组委会的第 ③ 问（是否同窗口同渠道）+ ④（模板/命名）。

### 22.2 新增硬约束：**PPT 必须是用户本人能讲出来、能理解的**

**用户 09-22 原话**：「决赛答辩的PPT，必须符合我能讲出来并且能理解的内容，既有深度也有理解性」。这是设计约束，不是偏好——**用户 0 基础，讲不出来 = 被追问一句就崩**。

**量化现存差距（本 session 逐页统计）**：现 13 页共出现 **38 种专业术语、61 处命中、页均 4.7 种**；最密的是**第 3 页（15 种）**，其次第 7 页（8 种）、第 2 页（6 种）。→ **现 deck 不满足这条约束**。

**已定设计原则（决赛版与讲稿都照此做）**：
1. **深度分层**——**主讲层**（10 页）用户必须能自己讲；**备用层**（官方逐条达成、SHA256 清单、离群题归因）用户只需能"**指路**"到证据文件，不需要深讲。评委问深了翻到备用页，不靠即兴解释。
2. **术语白话优先**——页面写名词、**口播一律白话**；每个技术点都要能回答"**为什么这么做**"（这是用户真正理解的部分），"怎么做"可以答"细节在随包源码里，我讲思路"。
3. **兜底话术**（背下来）："这一项我没有实测到那一步，我不在这里给结论；随包 `实测记录/` 里是当时的原始输出，会后我可以把文件发您。" —— **与材料立身之本（不宣称没验证过的）一致，当场认边界反而加分**。

### 22.3 讲者手册已产出（**本次新增，不在冻结包内**）

`D:\文本生成3D方案赛\决赛答辩准备\答辩讲者手册.md` —— 现有 13 页的**逐页讲法**：每页给【一句话，能直接用嘴说】+【讲法，术语翻成常识】+【可能被追问 2~3 条及白话答法】+【证据指路】；另含**开场三句**（含"主动认语义弱项"的策略说明）、**通用兜底话术 + 三句禁忌**、**22 条术语白话对照表**。

- ⚠️ **位置刻意放在 `决赛答辩准备/`，不放进 `答辩PPT/`**：后者在源码包 v5（终版）内，往里面加文件会造成**磁盘与冻结包漂移**，撞 `§19.5 纪律①`（包=已测代码，改任何一件必须重打重发）。**本手册不进包、不改包，故无需第七次重打**。
- 决赛版 PPT 的讲稿直接以本手册为底稿（数字与口径不会因重排而变化），**现在写不算白干**。

### 22.4 没有 Demo 录屏、没有实物 —— 现在就能做的三个替代（**不必等 GPU、不必等打印机**）

| 决赛版需要 | 现状 | **现在可做的替代** | 成本 |
|---|---|---|---|
| Demo（第 7 页，官方考察重点） | 无录屏 | **A. 流程演示（今天可做）**：本机在交付镜像内跑官方三行命令的**屏幕录制**——本机有 WSL2+docker，**后半段纯 CPU 可跑**，且这是断网环境、评委也能复现 → 说服力反而强。**B. 结果演示（今天可做）**：把已有 40 题四视图/`样例渲染图/00_40题总览_perspective.png` 做成翻页或旋转动画。**C. 完整"中文→3D"演示**：需再租一次 4090（约十几元/数小时），且**顺带能拿到 L1 候选选优后的新数字**——一个动作解决两件事 | A/B 零成本；C 约 10~13 元 |
| FDM 实物（第 9 页） | 无打印机 | **切片验证（今天可做，且是 FDM 可打印性的直接证据）**：用切片软件（Cura / PrusaSlicer）打开交付的 `model.glb`，截图证明它被正常接受（水密/单体/贴地 → 免支撑或少支撑）+ 壁厚 + 预计打印时长。**"能被切片软件吃下去"正是 FDM 合规的语言**，比任何术语都好懂 | 零成本（软件免费） |

→ **结论：决赛版可以现在就动手做 10/12 页；只有第 7 页（Demo）与第 9 页（实物）等素材。** 原判断"素材采集排在 09-30 之后"**部分修正**：A/B 两条替代路径今天即可采，建议趁复现材料提交后、公布入围前（09-23~09-29）把这两样做掉。

### 22.5 组委会问题清单（维持 7 问，第 ③④ 问与本次决策直接相关）

原 5 问 + 新增第 6 问（决赛答辩时长与发言规则、是否允许放录屏）+ 第 7 问（决赛「Demo 演示」的具体形式：现场实时跑 / 允许提前录屏 / 是否需留演示输入样例）。

---

## 二十三、09-22：**答辩 PPT 重做为真正的答辩版** —— 第七次重打 = 终版（用户指令「9月23交付的文件包要与答辩PPT一致，所以这次就是要出答辩PPT」触发）

> 这一节是 **§21（体裁复核）+ §22（时机与讲者手册）的收口**：结论从"另起决赛版、本窗口交提交版"改为**"本窗口就交答辩版"**，且**已经做完、已经重打、已刷新上传夹**。新 session 只需读本节 + §19.3 即可接手上传。

### 23.1 一句话状态

**答辩 PPT 已从「交付清单式梳理」重做成「真答辩稿」并冻结进交付物**：13 页（**11 页主讲 + 2 页提问备用附录**）、每页备注首行是一句可照读的话、内嵌 3 张真实产物配图、单文件无外部依赖。因 PPT 随源码包交付 → **第七次重打**源码包 → 条目 85 → **86**、zip **8,768,573 / `10290691…`** → **8,959,510 / `58e1d2d117bf8f488a50d41a3a8cfdbda22aba0d39868eecd7ed50823b39ae84`**。上传夹 6 个过期文件已刷新、`交付清单-SHA256.txt` 与 `上传说明-百度云盘.md` 已改写。**镜像包哈希 `8c2668ac…` 未变动。**

### 23.2 为什么要重做（§21 的量化结论 → 决策）

§21 已量化证明旧 deck「合格提交版、不合格答辩稿」：页均 463 字（合理 80~120）、正文众数 **14 px**（合理 ≥24）、**4/13 页主体是表格**、官方三条考察重点缺 Demo 演示、FDM 实物 **0 页**、Q&A 预埋 **0 页**、**38 种术语 / 61 处命中 / 页均 4.7 种**。§22 给"另起决赛版"的方案，但用户 09-22 拍板：**本窗口就要出答辩版**（理由见 §22.1 顶部横幅）。

→ 于是**同一份文件、同一个命名**就地重做：`答辩PPT/369583+default13319669_答辩PPT*.bento.html` 文件名不变（官方命名约定、分片脚本与上传夹引用都不动），内容整体替换。旧版已归档到**非包目录** `D:\文本生成3D方案赛\决赛答辩准备\历史版本_交付清单式13页\`（含旧两版 + 旧说明 + 旧 deck 源），**留史不丢**。

### 23.3 新版 13 页结构（**11 主讲 + 2 附录**，页码即翻页顺序）

| 页 | 标题 | 这一页的作用 |
|---|---|---|
| 1 | 封面「**既要像，又要能打出来**」 | 钩子；副标题 = 本轮最硬成果；3.15 / 第 9 名**明写在封面上**（不遮掩，评委手上有） |
| 2 | 一对互相拉扯的要求 | 官方三类要求 + **三条反作弊红线主动念出来**；结尾埋伏笔「像不像没做够」 |
| 3 | 一条链，两段算力：能自己控的，绝不交给运气 | 五步大链条动效 + **为什么前半段必须有显卡、后半段坚持不要显卡**（唯一一处大 step_chain） |
| 4 | 尺寸不是统一缩放，而是逐题读懂 | **三句真实题面**（`hid_con_002` 外径≤85 / `hid_dec_001` 建议约 120 / `hid_con_007` 总厚度≤20）+ 硬上限 vs 建议值 |
| 5 | 出图这一步，宁可慢，也要一定出得来 | OpenGL vs 纯软件渲染 + **内嵌四视图配图**（`hid_con_002` 真实提交产物） |
| 6 | 一个看不见的 0.1 毫米 | 最有故事的一页：减面挪顶点 → 50.0→50.1 越题面上限 → 「只缩不放」兜底；金句「**静默降级比直接报错危险得多**」 |
| 7 | 评委拿到之后，就是这三行（**Demo 页**） | 官方 §3.5 三行命令 + **40 题接触表配图** + 三个结果数字 + 必须自己说的诚实句（本机无显卡，演示的是后半段） |
| 8 | **160 / 160 —— 渲染图一张不差**（王牌） | 三步讲方法 + 三个数字 + **上下对照配图** + 主动讲唯一离群题 `hid_sma_001`（是复现把它修好了） |
| 9 | 我们用切片算过：基本不需要支撑（**FDM 页**） | 悬空面积 **0.22% / 0.39% / 0.68%** + 表面闭合 **40/40**、贴地 **39/40** + 诚实句（实物与 PrusaSlicer 体检安排在决赛前） |
| 10 | 我们不宣称没有验证过的东西 | ✓做到 3 条 / —没做到 3 条 / 下一步 3 条（多候选选优是唯一能系统性提语义分的办法） |
| 11 | 结语 | 金句收尾：「一致的产物、可查的证据，和敢说出口的边界」 |
| A1（12） | 工程落地：三个真缺陷 + 包能不能自己站起来 | **提问备用**：静默降级 / 减面越限 / 依赖闭包 127vs130 + 删净镜像再单独还原的自足性实测 |
| A2（13） | 官方 v1.0 每一条落在哪里 | **提问备用**：§1~§4 逐条落点表（7 行），问哪条念哪行 |

- **体裁上是真答辩稿**：主讲页全部换成"白话标题 + 少字 + 大字号"，页面只留数字与结论，术语留在备注口播层；**Demo 位（第 7 页）与 FDM 位（第 9 页）都已补齐**（用的是"现在就能采"的替代证据，见 §22.4 的 A/B 路径与切片口径）；**Q&A 预埋页 2 页**。
- **验收口径（§22.2 硬约束）**：每页备注第一行是「**【一句话】**」，用户可照着念；第 6/7/8/9/10 页的备注里带 **【诚实部分】**，明确"主动说，别等评委问"。

### 23.4 新增证据：`实测记录/15_初赛40题产物体检报告_20260921.md`（**这就是 85→86 那一件**）

第 9 页的三个切片数字（0.22% / 0.39% / 0.68%）与两组硬指标（表面闭合 40/40、贴地 39/40）必须有随包出处 → 把 09-21 的体检报告按证据 14 的体例**收编为证据 15** 放进包，并在 `方案文档.md` §七证据索引、`答辩PPT/说明.md` 口径节里指向它。同时**如实保留了初赛产物的三类已知不足**（33/40 被 12 万面截断丢约 77% 细节、4 题多部件分离实体、语义是主要失分面）——与证据 14 的分工写进了文件头：**14 证"可复现"，15 证"初赛提交本身有哪些不足"**。

### 23.5 一致性连锁（改了 PPT 就必须同步的四处，全部已完成）

| 文件 | 改动 |
|---|---|
| `方案文档.md`（14,057 → **16,236** B / `1fb40db4…`） | ① 口径说明「13 页 = 11 主讲 + 2 附录」② §四表新增两行：**FDM 可打印性**（切片三数字 + 40/40 + 39/40 + 「实物打印与 PrusaSlicer 真实切片体检安排在决赛前，本档不宣称已有实物」）、**初赛产物的已知不足** ③ §七证据索引补 15 ④ §八第 1 项换成新 ①~⑪ 页序 + 附录 A/B + 一致性自检说明 |
| `提交说明.md`（→ **25,342** B） | §一 表格断网证据与 PPT 行改口径、§五 目录树注释（`14` 行补 `15_…`）与「完整 85 → **86** 个条目」、时间线行改「13 页 = 11 主讲 + 2 附录」 |
| `答辩PPT/说明.md`（1,777 → **3,596** B / `1847b8f0…`） | 重写：新页序表 13 行、【一句话】/【讲法】备注约定、⚠️ **按 `S` 会把备注显示在共享屏幕上**、口径与一致性节逐数字列出处（含 `实测记录/15`）、旧版归档位置指路 |
| `交付清单-SHA256.txt`（8,417 → **9,553 → 9,951** B） | 冻结时间改「**第七次重打 = 终版**」，逐项记录起因/连锁/新值，并显式作废旧值；§三 追加一条「**重打台账在哪**」——说明包内 `实测记录/14` 的「重打记录」节**截至第五次重打**，第五次之后（含第七次）都记在本清单**头部**，属**刻意分工**：本清单在包**外**，更新它不动包内任何字节、不触发重打，也避开"包内记录包自身哈希"的自指。上传夹内同名副本已 `cp -f` 同步并 md5 复核一致 |

### 23.6 第七次重打的关键数字（**新 session 只要这一张表**）

| 交付物 | 新值 | 旧值（**已作废**） |
|---|---|---|
| 源码包 `复现推理源码包_v5_20260921.zip` | **8,959,510 B** / `58e1d2d117bf8f488a50d41a3a8cfdbda22aba0d39868eecd7ed50823b39ae84` / **86 条目** | 8,768,573 / `102906910e20…` / 85 |
| 放映版 `…_答辩PPT.play.bento.html` | **784,451 B** / `56d35faecf8822dcf8b7dfd59da89a1705b84bd952af2e47384e04f245237186` | 652,871 / `4fd67638…` |
| 可编辑版 `…_答辩PPT.bento.html` | **784,435 B** / `ca2f37e22edaee00afda42da5e51a2efd9cb2697503e427bc4ebd7296e70637c` | 652,855 / `3ed71a46…` |
| `…_答辩PPT_说明.md` | **3,596 B** / `1847b8f05e8319c684462d4b06ec167cf2947405310c32dea8ac95486f76ff52` | 1,777 / `cfddbba6…` |
| `…_05_方案文档.md` | **16,236 B** / `1fb40db4827dc64b870f6f54b95df771214e81f5722dce989c57d67b0585d3e3` | 14,057 / `d7075c11…` |
| 镜像包 `hy3d-repro_20260921.tar.gz` | 23,867,134,532 B / `8c2668ac1ee4312bbd70aa918d15c170de086056e5bbffe913bc081988cf3914` | **未变动** |

**重打后已复核**：① 86 条目、无 `__pycache__`/`.pyc`；② 包内六个关键文件与磁盘工作区 **md5 逐字节一致**；③ 包内 `.md`/`.txt` **无自指哈希**（含本次新值本身）；④ 包结构与前一版一致（**顶层是 `复现推理源码包/` 单层前缀**——第一次重打曾误打成扁平结构，已修正，这类结构回归务必再查）；⑤ 全库 md/txt/json 扫描**无残留旧哈希**。
⚠️ **踩过一次的坑（写给下一次）**：`shutil.move` 跨盘在 Windows 上会先 `copy2` 再 `unlink`，`unlink` 失败时**文件已经写进去了**——若脚本报错就当"没改"继续重跑，会把前缀叠加成双层。**重打脚本必须建包在目标同盘（`tempfile.mkdtemp(dir=...)`）+ 用 `os.replace`，并在写完后再验一次条目结构。**

### 23.7 讲者手册已同步到新页序（**不在包内**）

`D:\文本生成3D方案赛\决赛答辩准备\答辩讲者手册.md` 重写：新 13 页**逐页**给【一句话 / 讲法 / 可能被问 / 证据指路】，附录 A/B 单独成节并标注"主讲时不要翻到"；保留开场三句、通用兜底话术 + 三句禁忌、术语白话对照表（新增"切片/支撑""首题候选"两条）。位置仍在 `决赛答辩准备/`，**刻意不进包**（进包就要再重打一次）。

### 23.8 仍未闭合（本窗口剩余动作，与 §19.3 同）

① **实际上传百度云盘**（上传夹已刷为最新 12 项）→ 分享有效期选「**永久**」→ 回填问卷②；② **定镜像包走哪条路**（分片 ≤3.7 GB×7 / 官方并列允许的 Dockerfile + 构建说明），**百度网盘单文件上限仍未获官方确认**；③ **一次问清组委会 7 问**（第 ③④ 与 PPT 是否同窗口同渠道有关）；④ 队长填问卷①。**死线 2026-09-23 24:00。**

### 23.9 新版 deck 的源文件已归档（**可重建**）

- 源（bento 数据源，纯 Python）：`C:\Users\dfjq\.agents\skills\bento-deck\decks\bdci_text2_3d_answer.py`（31,843 B / md5 `53bc7710a684d4ad8a4e39a9b3031766`）
- **副本已归入工作区**：`D:\文本生成3D方案赛\决赛答辩准备\deck源_bdci_text2_3d_answer.py`（同一字节）；旧 deck 的源在 `决赛答辩准备\历史版本_交付清单式13页\deck源_bdci_text2_3d.py`
- 重建方式：在 `bento-deck` 技能目录下跑该技能的 `build.py` → 产出 `<OUT_STEM>.bento.html`（可编辑）与 `<OUT_STEM>.play.bento.html`（放映）。`OUT_STEM` 已指向 `D:\文本生成3D方案赛\答辩PPT\369583+default13319669_答辩PPT`，即**重建会直接覆盖交付文件** —— 重建前先确认是否要重打源码包（§19.5 纪律①）。
- ⚠️ **bento 文本 html 白名单只有 `<b> <i> <br>`**：`<code>`/`<span>` 会被拒（技能自带说明里的白名单是错的）。命令块用「元素字段 `fontFamily` 设成等宽栈」实现，行内改字号要拆成两个 `T()` 元素 —— 这一条是新 deck 第一版返工的原因，**下次别再撞**。
- ✅ **bento 支持图片元素**（`{"type":"image", …, "src":"data:image/jpeg;base64,…"}`）：新 deck 的 3 张配图就是这么内嵌的，单文件仍自足、体积从 652 KB 涨到 784 KB。

### 23.10 交付版 PPT 的放映行为已确认（2026-09-22；**用户决定不留截图证据、自行眼检**）

> **本节的定位（重要，别再自己加戏）**：用户 2026-09-22 明确指示——**"不用对交付版 PPT 做浏览器实测并留截图证据，没必要，我回自己眼检"**。因此**截图证据一律不留**（生成过的已按「工作区洁净」删除），**后续 session 也不要再为"留 PPT 测试截图"重复这一步**。本节保留的只是**一次性的运行结论 + `S` 键的真实行为**，供写讲稿/答疑时引用；**交付版的最终视觉验收以用户本人眼检为准**，不以本节为准。

**实测环境**：本机真实 Chrome（Playwright 驱动，headless，1920×1080；幻灯片设计画布 1280×720，1.5× 缩放正好铺满）。**打开方式是 `file://`——即评委双击的真实场景**，不是 http 起服务。会话内置浏览器工具**在子代理中不可用**（`Browser is not available in subagent`）且不支持 `file:` 协议，故改走本机 Chrome；**为不留缺口，先 http 跑一遍完整 13 页，再用 `file://` 原样重跑一遍全部 13 页 + 备注 + 可编辑版，两次结论一致**。

| 检查项 | 实测结果 |
|---|---|
| 页数 / 翻页 | **13 页**，`→` 从 idx 0 走到 12，无跳页卡页；13 个 `section` + 13 个 `aside.notes` 一页一备注；页脚 `02/13 … 13/13` 对得上 |
| **3 张内嵌图是否真渲染** | **✅ 全部真实渲染**（判据不是"没有破图图标"，而是每张 `img.complete=true` + `naturalWidth/Height` 为真实像素 + `getBoundingClientRect()` 有真实作画尺寸）：p05 1740×354→1632×348（四视图：正视/侧视/俯视/透视，燕尾榫笔筒，侧向凸柱可见）、p07 1040×426→780×348（**10×4 = 40 格接触表**，格上方有题号）、p08 1040×499→780×393（**上下两组四视图对照**，上排每格下绿字「阶段2 逐字节一致」） |
| 变形 | **无**。容器比例与原生比例不等，但 `object-fit: contain` 等比缩放居中留边——p05 的正视图是正圆、p07 的格子是方的 |
| 文字溢出 / 跑版 | **13 页全 overflow = 0**（逐页扫每个可见元素包围盒是否越出画布四边）；p12/p13 表格边框完整、文字全在格内、底部提示框与页脚都在画布内 |
| JS 报错 | `file://` 下**零报错**（两个版本皆然） |
| 可编辑版 | `file://` 打开正常，零报错，工具栏渲染出 `bento/slides v1.2.3 文本 形状 图片 媒体 表格 图表 评论 共享 保存`，**3 张内嵌图 0 张破图** |
| 被改动的交付文件 | **零**。两版字节数与时间戳维持原样（784,451 / 784,435，均 11:23）→ **GATE-1 哈希对账仍然成立** |

**截图证据：按用户指示已删除**（曾生成 15 张：`p01_封面.png` … `p13_附录B.png` + `p01_备注实测.png` + `editable_check.png`，目录 `决赛答辩准备\PPT实测截图_20260922\`，连同更早的 `_shots/`、`_shots2/`、`_shots3/`、`_tmp_view_*.png` 一并清掉）。**不要再为留 PPT 测试截图而重复这一步**。

**一处实测行为与交付文档的措辞差异 —— 已判定为"不够精确，但不是错误"，故不动冻结包**：按 `S` **不是**在当前页盖浮层，而是**新开一个「演讲者视图」独立窗口**（当前页大预览 + 下一页 + 计时器 `00:03`/剩余 `11:56` + **完整备注正文**：DOM `.sv-notes`，`display` 非 none 且有真实高度 + 底部 13 页胶片条）；**再按 `S` 关不掉它**（连按只重复聚焦），须**手动关窗**。

- 交付文档 `答辩PPT/说明.md` 第 32 行的原话是"按 `S` 后备注会显示在共享画面上，别在投屏状态翻备注页"。在**共享整个屏幕**（线上答辩最常见）下这句话**成立且保守安全**——新开的窗口就在共享范围内，评委会看到。它**没有**声称"按 S 能开关"，所以**不构成事实错误**，只是没写"是独立窗口 + 关法是手动关窗"。
- **决策：不改 `说明.md`**。它在**源码包内**，改一个字节就要触发**第八次重打** + 全套哈希连锁（§19.5 纪律①），而收益只是把一句"保守够用"的话说得更细；**离 09-23 24:00 只剩一天，冻结包不动**。
- **精确行为已写进 `决赛答辩准备/答辩讲者手册.md` 的「放映技巧」块**（手册在**包外**，可自由更新、不触发重打）——加了四条：① 别按 `S` 的真实原因（独立窗口会进"整个屏幕"共享）② 再按 `S` 关不掉、要手动关 ③ 只共享"浏览器标签页"时其实安全，但**按最保守的来** ④ 想用演讲者视图就**在开始共享前**按 `S` 摆好窗口，没有副屏就别用。
