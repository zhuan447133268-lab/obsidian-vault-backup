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
