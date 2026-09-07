---
title: 09-07 交接 — 首提渲染审查发现系统性生成失败（噪声团），待重开云端修复
---

# 2026-09-07 会话交接（第 3 天：渲染审查 → 发现重大问题 → 修复计划）

> 前置阅读：[[文本生成3D方案赛-主索引]]、[[session-handoff-3d-2026-09-06]]

## 一、重大发现：已提交的 40 题几何全部是"噪声团"（语义≈0 分）

09-07 用户要求"40 题渲染图全部过一遍"，审查结论：

1. **视觉审查**：已看 18/40（con 全组 8 + dec 全组 10），全部为无意义锯齿噪声碎块，无一题能对应 prompt 语义（雨棚/笔筒/凉亭/相框/拱桥…均不存在）。因特征高度一致，判定其余 22 题同病（见下）
2. **几何签名一致**（抽查 con_001/dec_001/fun_005/sma_010 的 raw.glb）：700~910 万面、32³体素占用 74~79%、包围盒各向同性 1:1:1 —— 各向同性"菜花状"噪声团，扩散采样输出废损的典型特征
3. **几何体检本身是干净的**：40/40 水密、40/40 单体、0 尺寸超限 —— 所以 09-06 的 validate 全绿是"几何合法但语义为零"，validate 不查语义，这是流程漏洞

**结论**：09-06 10:23 提交的版本，FDM 物理合规分可能正常，**多视图语义分预计≈0**。9/7、9/8 两次提交是真正的有效机会，必须修复生成端。

## 二、根因分析（按证据强度排序）

- `gen_meta.json`：base_model = `/root/models/t2i + /root/models/shape` —— **用的是云端本地权重目录，非 HuggingFace 官方仓库名**（09-06 会话为省下载时间上传/缓存的权重）
- 单题仅 31 秒、无任何失败日志、40 题输出特征完全一致 → **系统性初始化/权重问题**，最可能：
  1. `/root/models/shape` 权重文件不完整或与配置不匹配（部分 shard 缺失 → 随机初始化 DiT → 噪声 latent → 菜花 SDF）⭐ 首要嫌疑
  2. t2i 权重同样问题 → 噪声概念图喂给 shape（镜像名 hy3d-t2i-fixed 暗示 t2i 曾出问题并"修过"，可能修 t2i 时 shape 权重未核验）
  3. scheduler/参数被改坏（可能性低，gen_params 显示 steps=30/guidance=5.5 正常）
- 后处理无罪：raw.glb 本身就是噪声（已在本地复渲染确认），后处理只是把它修"水密"

## 三、修复计划（等用户重开云实例后执行）

1. 用户：极智算控制台 → 从镜像 `hy3d-t2i-fixed` 创建/开机 → 粘贴公钥 `~/.ssh/autodl_hy3d.pub` → 把新 SSH 命令+密码发 ZCode
2. ZCode 接管后：
   - **不信任 /root/models 旧权重**：删除或绕开，改从 HF 镜像直拉 `tencent/Hunyuan3D-2mini`（shape）+ t2i 权重，核对文件清单/大小与官方一致
   - 单题端到端试验：生成 t2i 图 → **先看图**（概念图是否正常）→ shape → 渲染 → **人眼确认形状语义** 后才继续
   - 若 mini 仍噪声 → 换完整版 `tencent/Hunyuan3D-2` 或排查 scheduler
   - 通过后全量 40 题（nohup + 轮询）→ 拉回 → 本地重建提交包
3. 本地顺带修正：`--max-mm` 默认 150 曾把 dec 组"建议约180毫米"钳到 150 → 重建时改 `--max-mm 200`（prompt 硬上限仍优先）
4. validate 全绿 + **渲染图人工抽查（新增流程门槛，≥8 题抽样）** 后再让用户提交

## 四、时间预算

- 用户开机 + 发 SSH：~10 分钟；权重重拉 ~20-40 分钟（hf-mirror）；单题验证 ~10 分钟；全量 ~1.5-2.5h；拉回+重建 ~1h
- **今天 9/7 提交仍现实可行**；最迟 9/8（最后一天，不能再失手：必须渲染抽查通过才交）

## 五、流程教训（已固化）

- validate 全绿 ≠ 可提交：提交前必须人工/抽样目检渲染图（几何合法的噪声团骗过了 09-06 的检查）
- 权重来源必须核验（官方仓库名直拉 > 本地上传目录）；每次换权重来源都要单题语义验证
- gen_meta 记录"无失败"不代表成功——生成类任务必须看产物本身

## 六、（09-07 复盘）重开实例前的深度复盘 —— 用户要求"这次必须是有效结果"

### 6.1 根因链已完整闭环（两个确凿错误叠加）

1. **权重来源污染**：09-06 脚本注释自证用了 **ModelScope 拆包版权重**（`/root/models/*`，DiT ckpt 内 VAE 段为零占位，当时打过 `--vae-subfolder` 补丁），非官方 HF 布局，未做任何核验
2. **缺背景去除**：官方 minimal_demo 在喂 shape 前必须 `convert("RGBA") + BackgroundRemover()`；09-06 版把带背景的 HunyuanDiT 输出图直接喂入 → 图像条件被整张矩形图污染。官方 demo 已拉取核对（hy3d_readme.md / minimal_demo.py @jsdelivr 镜像）
3. 次要确认：t2i 权重不在 tencent/Hunyuan3D-2 仓库内（62GB 仓库无 t2i 目录），官方配套是独立仓库 `Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled`（diffusers 布局）——自制 /root/models/t2i 目录布局很可能不符
4. 权重文件清单已核（HF API via hf-mirror）：Hunyuan3D-2mini 全 22 文件、DiT/VAE 各变体 fp16 ckpt+safetensors；from_pretrained(model_path, subfolder=...) 是严格加载

### 6.2 开发集 40 题通读结论（测试集策略依据）

- 题目全部是"产品级规格"：卡扣铰链、0.2mm 榫槽间隙、3/4/5/6/8/10mm 分级孔、汉字浮雕「慢慢来」——**微细功能特征是 text-to-3D 模型做不到的，所有队伍同样做不到**；得分主战场 = 整体形态语义 + FDM 合规 + 干净度
- 原始 spec 句不是合格的文生图 prompt（"不得使用支撑"等制造约束对图像无意义且引入干扰）→ 已实现 `clean_t2i_prompt()`：剔除约束子句、保留视觉子句、追加"单一物体/纯白背景/产品概念图"风格后缀（离线单测通过）
- dev 集含多件套(两件收纳盒/四块拼图)——后处理的浮渣阈值(体积<1%主体)不会误杀大组件，安全

### 6.3 generate_hy3d.py 已重写为 v3（五道防垃圾门禁，离线单测通过）

权重仅认官方 HF 仓库（--vae-subfolder 默认空、官方单文件版无需覆盖；拆包版需显式传）→ t2i prompt 清洗 → **每题 t2i.png/t2i_rembg.png 落盘** → RGBA+rembg 官方预处理 → shape 后自动噪声检测（noise_suspect：体素占用>65% 且三轴比>0.8 判可疑；实测干净球体 7%、噪声团 74-79%，区分度极大；已验 40 题坏模型 100% 命中）→ SUSPECT 不计入合格数
另有：兼容 hy3dgen 2.x 的 HunyuanDiTPipeline 直构；纹理默认尝试、失败降级几何
本地管线：build_submission --max-mm 默认 150→200（不再钳制"建议约180毫米"题）

### 6.4 上机执行序（重开实例后，每道门禁不过不进下一步）

**时间预算（SSH 到手后起算，几何优先策略）**：
| 阶段 | 内容 | 耗时 | 门禁 |
| --- | --- | --- | --- |
| P0 | 用户开机+发SSH | ~10min（用户） | - |
| P1 | 环境核验：连机验GPU→隔离旧权重→上传v3脚本+题目→官方权重直拉(mini+DiT+paint) | 30~50min | 权重文件清单与HF API一致 |
| P2 | 冒烟1题(dev_001)：生成→拉回概念图+raw.glb→本地渲染目检 | 10~15min | t2i图人眼过+noise_suspect PASS，不过则排查(+30~60min) |
| P3 | dev集40题彩排（无纹理，~1-1.5min/题） | 40~70min（挂机） | 抽8题渲染目检全过 |
| P4 | test集40题全量（无纹理） | 60~90min（挂机） | 40题noise_suspect全PASS |
| P5 | **后处理+渲染+打包改在云端跑**（用户要求本机零负载；云上 pip 装 pymeshfix/fast-simplification 即可，matplotlib Agg 出图）→ 只拉回 submission.zip(~95MB)+40题渲染图(~50MB)+build_report.json | 25~40min | validate全绿 |
| P6 | 40题渲染图全部目检→用户PC提交→关机 | 40min | 用户确认 |

合计约 3.5~5.5 小时；向用户汇报点=P2后/P3后/P6前。**纹理增强为可选第二批**（texgen编译+40题重跑约+2.5~3.5h、+5~8元），用于 9/8 提交提质，若今天时间不够则放弃。费用合计约 10~15 元。

1. 冒烟 3 题（覆盖三类：dev_con_003 / dev_sma_002 / dev_dec_008）：
   `python generate_hy3d.py --prompts prompts/dev --out models_raw_dev --ids dev_con_003 dev_sma_002 dev_dec_008 --no-texture`
   - 人眼查每题 t2i.png（像不像该物体？纯背景？）→ t2i_rembg.png（是否抠干净）→ raw.glb 拉回本地渲染 + noise_suspect PASS
   - 类别覆盖理由：不同类别(功能件/小物/装饰)对生成难度的响应可能不同，3 题比 1 题多花约 5 分钟，降低"单题侥幸通过"风险
2. 冒烟通过 → dev 集全量 40 题 → 抽 8 题渲染目检
3. dev 验收通过 → test 集全量 → 拉回 → 40 题 noise_suspect 全 PASS 复核 → 本地后处理打包
4. 40 题渲染图**全部**过目（用户已明确要求）→ validate 全绿 → 提交（9/7 或最迟 9/8）
5. 失败预案：mini 仍噪声 → 换 `tencent/Hunyuan3D-2`（subfolder hunyuan3d-dit-v2-0）→ 再不行换 t2i 种子/步数排查；权重拉不动 → hf-mirror 环境变量确认

### 6.5 对用户承诺的边界（诚实原则）

- 可承诺：产物是真实的 3D 形状（每题经三道自动检测+人工目检）、提交包 100% 合规、FDM 合规最大化
- 不可承诺：**"一定前几名"无法保证**——语义分取决于所有参赛队的相对水平，微细特征(卡扣/孔位)所有 text-to-3D 方案都做不准；能做的是把开源管线调到当前时间预算内的最优（完整版 2 模型/纹理/octree 380 是已知的提质杠杆，视时间启用）

### 6.6 （09-07 深夜）重开实例前的前置工作执行记录 —— 全部客观验证

**A. 官方源码参数级核对**（jsdelivr 镜像拉取 main 分支源码逐行比对）：
- `Hunyuan3DDiTFlowMatchingPipeline.__call__(image, num_inference_steps, octree_resolution, guidance_scale, ...)` 返回 `List[List[trimesh.Trimesh]]` —— v3 脚本调用逐参数匹配 ✓
- `from_pretrained(model_path, device, dtype=fp16, use_safetensors=True, variant='fp16', subfolder)` ✓
- `HunyuanDiTPipeline.__call__(prompt, seed=0)`（text2image.py 81 行全文核对）✓
- 官方 minimal_demo 全文已存 $TEMP（rembg 流程模板）

**B. 权重加载路径的代码级发现（新增铁律）**：
- `smart_load_model`（shapegen/utils.py）**优先读本地缓存 `$HY3DGEN_MODELS`(默认 `~/.cache/hy3dgen`)**，命中即静默加载、不联网 → **P1 必须先 `rm -rf ~/.cache/hy3dgen` 并检查该环境变量**，否则官方仓库名也会加载到 09-06 的残留权重
- 未命中时 `snapshot_download(repo_id, allow_patterns=[subfolder/*])` 只拉指定子目录，尊重 HF_ENDPOINT ✓
- `rembg`/`onnxruntime` 在官方 requirements.txt 中 → 09-06 镜像里应已装好，BackgroundRemover 可直接用
- 已落物：`cloud/cloud_prep.sh`（P1 一键脚本：验GPU→清缓存→设镜像→装 pymeshfix/fast-simplification/matplotlib→预拉官方权重→布局检查→输出 P2 冒烟命令）

**C. 已提交包(09-06)按官方要求逐条审计**（固化工具 `pipeline/audit_official.py`，退出码可作门禁）：
- 40 题目录结构/metadata 8 字段/unit=mm/process.md 10 字段/renders 四图 —— 全部合规
- **发现 1 处缺陷：manifest.json 缺 `created_at`**（09-06 会话手改 manifest 改队名时丢失）
- **新增铁律：manifest.json 只能由 build_submission.py 的 --team-id/--team-name 参数生成，严禁手改**；每次构建后必须跑 `audit_official.py` 通过才可上传

**D. 客观未知项（无法本地验证，禁止假装知道；待群问/平台确认/提交后观察）**：
1. 多次提交按最高分还是最新分计分 —— FAQ 未写
2. manifest 的 team_id/team_name 是否需与平台"我的队伍"一致 —— 官方示例是占位符(team_001)，无明文要求
3. 官方"基础格式检查"具体包含哪些检查 —— 仅公开"可通过主办方基础格式检查"
4. 决赛"单题推理时间不得超过规定上限"的具体数字 —— 未公布
5. 纹理权重(hunyuan3d-paint-v2-0)在镜像里是否完整 —— 上机首跑纹理时验证

## 七、（09-07 上午）实例恢复实况与决策

- 用户从镜像 hy3d-t2i-fixed 重建实例：四川二区 node-n0068，4090（1.58 元/时，10:35 创建），**拉取镜像超 1.5 小时未完成**，SSH 不可用，带宽原因未知（平台未公开，不猜测）
- **决策（~11:40）：放弃等待，转方案 C** —— 该实例「更多操作→关机」→「更换/保存镜像→更换镜像」为官方 `PyTorch 2.3.0 + CUDA 12.4.1 + py3.10`（小镜像分钟级）→ 开机后从零装环境：cloud_prep.sh（清缓存 → pip 后处理依赖 → 官方权重直拉约 10GB：Hunyuan3D-2mini@dit-mini + HunyuanDiT-Distilled；纹理权重 hunyuan3d-paint 暂不拉，几何保底优先）
- 镜像仓库中的 hy3d-t2i-fixed **保留不删**（env 部分或有参考价值；其中的 ModelScope 拆包权重已判死刑，绝不复用）
- 若更换镜像界面流程与描述不符，用户截图反馈再定
