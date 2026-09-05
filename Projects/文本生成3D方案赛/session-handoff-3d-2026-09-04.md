---
title: 首日交接 — 2026-09-04（管线建成+验证，等 GPU）
---

# 2026-09-04 会话交接（本项目第一天）

> 前置阅读：[[文本生成3D方案赛-主索引]]（比赛规则、技术方案、文件地图都在主索引，本文件只记当日经过与接手动作）

## 今日完成

1. **可行性判定**：用户笔记本（AMD 4600U 核显、无 N 卡）跑不了生成 → 定调"云端生成 + 本机后处理"
2. **本地管线建成并验证**（D:\文本生成3D方案赛\pipeline\）：
   - postprocess.py（FDM 修复）、render_views.py（纯 CPU 四视图）、build_submission.py（打包+validate）
   - 用构造脏模型（碎块+破洞+悬空）端到端跑通：水密、贴地、80mm、渲染正常、100% 校验
   - 踩坑：trimesh 5.x 移除了 `trimesh.repair.merge_vertices`（改为实例方法）；`unique_faces/nondegenerate_faces` 兼容 callable 与属性两种形态
3. **浏览器实测定位数据入口**：2026 BDCI 在中科息壤（非 DataFountain）；赛题页 xir.cn/competition/1171；数据下载在报名后解锁（未登录无下载按钮，已验证 DOM）；开发集/测试集均可从"数据与评测"tab 或我的比赛下载
4. **用户已下载双题集** → 解压校验：dev 40（dev_*）+ test 40（hid_*），四类别各 10，目录名与 prompt_id 全一致，落在 prompts/dev、prompts/test
5. **尺寸约束解析器**（新增+两轮修正）：
   - 第一版整句正则会把"总厚度不超过20毫米"错误当整体上限 → 重构为子句级轴向分类（高度/厚度/宽度/直径/整体/建议约）
   - 40 题人工核对后补漏"限高"句式（is_cap 正则加入 限高/限宽/限长）
   - apply_size_policy 单测：厚度帽 100×50×30→66.7×33.3×20 ✓；z 帽不会反向放大 ✓；组合帽取 min ✓
6. **为用户准备的交付物**：
   - `带到4090电脑/`：generate_hy3d.py + prompts.zip(80题) + 《操作步骤-零基础版.txt》（9 步骤、每步成功判据）
   - `租极智算GPU-你只需做这3步.txt`（用户改用 jygpu.com 后写的当前主线指南）
   - 给运维的 GPU 需求说明话术（简短版+详细版，在会话中，未落盘）
7. **generate_hy3d.py 健壮化**：纹理绘制失败改为降级保存无纹理几何（不阻塞整题）

## 用户侧关键状态

- 已报名成功（能下载数据）；**队伍ID/队名未知，build manifest 需要** → 下次要
- 用户自述 0 基础：所有指引必须逐步骤+截图级细节
- GPU 动向：先问公司运维（发了需求说明），后改口"不用 AutoDL，用极智算 jygpu.com 租" → 当前主线=极智算，**等用户发 SSH 登录命令+密码**
- AutoDL 路线已弃用（相关 txt 已删）；本地 4090 电脑路线保留为备选

## 接手后立即要做（按序）

1. 若用户已发极智算 SSH 信息 → 用 plink 首连（`echo y | plink -ssh -pw 密码 -P 端口 用户@地址 "nvidia-smi"`，工具在 %LOCALAPPDATA%\Temp\putty-tools）→ 装我的公钥(~/.ssh/autodl_hy3d.pub) → 改用原生 ssh/scp
2. 远程装环境：`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124` → `pip install -r requirements.txt -i 清华源` → export HF_ENDPOINT=https://hf-mirror.com → git clone Hunyuan3D-2 → 放入 generate_hy3d.py
3. 上传 prompts（zip 仅 46KB，scp 秒传）→ `python generate_hy3d.py --prompts .../prompts/dev --out .../models_raw_dev --limit 2` 试跑 → **重点核对 hy3dgen import 是否漂移**（脚本按官方 README 编写，未实测）
4. 拉一个 raw.glb 回本机过 postprocess+render 看质量 → 全量跑 prompts/test（nohup 后台 + 轮询）→ zip 拉回 `models_raw_test/`
5. 本机构建：`python pipeline/build_submission.py build --prompts prompts/test --raw-root models_raw_test --out output_test --team-id <待用户给> --team-name <待用户给>` → validate 全绿 → 让用户 PC 端上传
6. 提醒用户：跑完在极智算释放实例；每次提交窗口每天仅 1 次

## 开放问题

- 队伍ID/队名？
- 用户是否组队（影响提交次数总额）？
- 纹理是否本期做（当前策略：先几何保底，9/7 视余量补）？

## 用户计划（2026-09-04 提出）

用户问"9/6 再试来得及吗"——已答复来得及（全程 4~6h，9/6~9/8 还有 3 次提交机会），但已提示：最大风险是云端脚本未实测，建议 9/6 前任何空档先租好极智算发 SSH，花 ~2 元试跑 2 题清零接口风险；若坚持 9/6 动手，则当天按"试跑→全量→打包→提交"连轴执行，9/7、9/8 兜底迭代。
