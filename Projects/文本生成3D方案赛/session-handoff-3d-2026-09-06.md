---
title: 09-06 交接（首次提交成功 + 复现包就绪 + 云端已关）
---

# 2026-09-06 会话交接（第 2 天：首提入库、复现包整理完）

> 前置阅读：[[文本生成3D方案赛-主索引]]。本文件记录 09-04 之后的新进展与当前状态。

## 一、当前状态速览（09-06 18:00 前核实）

| 项 | 状态 |
| --- | --- |
| 首版提交 | ✅ 2026-09-06 10:23:59 提交 submission.zip（94.4MB / 281 文件 / 40 题全量），状态「评测排队中」，榜单「初赛 - A榜」 |
| 今日提交额度 | 已用 1 次（每天限 1 次；提交窗口 09-02 ~ 09-08，**还剩 09-07、09-08 两天**） |
| 成绩 | 暂无（09-09 ~ 09-20 评测 + 专家评审） |
| 云端 GPU | 已关闭；**镜像 hy3d-t2i-fixed 已保存**（含 18G 权重 + 脚本 + prompts），重开 5~10 分钟恢复 |
| 复现包 | ✅ D:\文本生成3D方案赛\reproduction\（run_infer.sh + Dockerfile + fetch_weights.sh + README），CPU 链路冒烟通过 |
| 队伍信息 | manifest 署名 team_id=CCF_BDCI_2026 / team_name=T3D-Team；账号昵称「大北鼻 a2cb49ed04444」（提交记录用户列为手机号+异常前缀，疑似平台展示 bug，不影响） |

## 二、09-04 之后新增的关键事实

1. **云端生成全量完成**：极智算 4090（222.211.217.183 端口 40059，密钥 ~/.ssh/autodl_hy3d）跑完测试集 40 题 → 拉回 D:\文本生成3D方案赛\models_raw_test\（每题 raw.glb + gen_meta.json）
2. **本地后处理 + 打包全量通过**：output_test\submission\ 40 题 validate 全绿（100%、watertight、112k+ 面）；submission.zip 经 zip 字节级复检（CRC/结构/manifest/GLB 水密）
3. **pymeshfix 0.18.1 兼容修复**：`mf.v/mf.f` 已移除 → postprocess.py 改用 `mf.points/mf.faces`（条件分支兼容旧版）
4. **平台登录方式**：xir.cn 登录弹窗默认微信扫码，右上角 `.login-type` 图标可切「验证码登录」（手机号 + 短信验证码 + 协议勾选）。本次即用手机号验证码登录成功
5. **上传方式（关键经验）**：平台 IAB 浏览器不支持 `fileChooser.setFiles`（能力受限）→ 采用「本机起 CORS 临时 HTTP 服务 + 页面 fetch zip 字节 + DataTransfer 注入 el-upload」成功上传 94MB zip
6. **提交入口**：竞赛详情页「去提交」按钮 → /competition/1171/submit（el-upload + 描述 textarea + 提交按钮）→ 提交后记录在「我的比赛」(profile) 页表格 + 展开可见初赛-A榜/文件名/描述/评测日志
7. **复现包装订**：见 reproduction/README-复现说明.md；`bash run_infer.sh /input/prompts.jsonl /output`，阶段1 GPU 生成（Hunyuan3D-2）→ 阶段2 CPU 后处理+渲染+元数据；Dockerfile 权重固定布局 /root/models/{t2i,shape} + 构建时零张量校验
8. **FAQ 关键规则**：组队 1-5 人、组队提交总次数 ≤ 开赛天数×3；"多次提交取最优还是最新成绩"页面未写明（建议群内确认或 09-09 后观察）

## 三、待办 / 决策点（按优先级）

1. **09-07、09-08 是否补提**：官方评分 09-09 才开始；若想优化，翻 output_test\submission\<id>\renders\*.png 挑弱项 → 弱项=打印性差可本地调参重后处理（无需 GPU）；弱项=语义差需重开云端补跑 `generate_hy3d.py --ids <id>`（成本约 1~2 元）
2. **云实例重开方法**（若需补跑）：极智算控制台 → 镜像 hy3d-t2i-fixed → 粘贴公钥 ~/.ssh/autodl_hy3d.pub 内容 → 开机后发新 SSH 端口/IP 给 ZCode
3. **09-21 ~ 09-24**：若初审进 TOP10 → 交复现推理资料（用云端 18G 权重 docker build hy3d-repro 镜像）
4. **09-30**：关注入围决赛名单；决赛需 FDM 实物打印（提前录视频/摄像头特写）

## 四、风险与提醒

- 剩余提交额度仅 2 次：任何补提前必须先 local validate 全绿
- 每队每天 1 次提交（自然日刷新）
- 反作弊红线：渲染图必须来自提交 model.glb 真实渲染（本管线即如此）；禁止极简几何骗分
- 服务器已关、镜像在手：下次谁接管先读本文件 + 主索引，避免重复摸索登录/上传/复现等已知坑

## 五、开放问题

- 多次提交如何计分（最高分/最新分）？→ FAQ 群问或 09-09 后看记录页验证
- 队伍ID/队名是否要与平台「我的比赛-我的队伍」对齐（manifest 目前用 CCF_BDCI_2026/T3D-Team）？
- 初赛若表现一般，决赛可行性评估（换完整版 Hunyuan3D-2 / 调 octree / 上纹理）？