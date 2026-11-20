---
date: 2026-11-19
updated: 2026-11-20
source: 自研 + 开源（本机产品交付沉淀）
url: https://github.com/zhuan447133268-lab/photo-to-3D
type: 技能卡
tags: [AI工具, threejs, 3D, 照片重建, img2threejs, 产品演示, 单文件交付, Apache-2.0, 网格导入]
---

# photo-to-3d-demo：产品照片 → 可交互 3D 演示页

## 一句话定义

两条输入路线，同一个交付物。给 2–4 张同一物体的照片（**A 路线**），或者给一个别处重建好的 GLB（**B 路线**），产出**单文件 HTML**：拖拽旋转、点选零件看参数、爆炸拆解、线框、自动旋转、重置视角；交付前六项断言在真实浏览器里跑过并留截图。发给人双击就能开，无 CDN、无同级文件。

**两条路线的差别只在几何从哪来**：A 是"看着照片手写数字 → 编译成基础体"，B 是"你带来的网格 → 焊接、分件、交付"。B 路线不重建任何东西，也不上传。

## ⚠️ 它到底怎么做的：不读像素做几何（2026-11-20 验收方反馈后补写）

**生成器从头到尾没打开过照片。** `generate_threejs_factory.py` 读 `spec/object-sculpt-spec.json`，把它编译成 Three.js 基础几何体（方块 / 圆柱 / 圆锥 / 旋转体 / 挤出体）。spec 里的每个数字，是 agent 或人**看着照片手写**进去的。逐层拆开：

| 层 | 来源 | 读像素吗 |
| --- | --- | --- |
| 几何 | spec 里的数字 → 基础体拼装 | **不读** |
| 材质 | 裁图 → 调色板 + albedo / roughness / height / normal / ao | **读**：stage1 提取器逐像素统计；demo 那 35 张贴图就是这么来的（`gloss-report.json` 有 `sourceImage` 与 `pass` verdict 可查） |
| 比例与分件 | 人/模型拿渲染帧与照片对照 | 没有求解器，没有测量 |

所以**精度上限 = 基础几何体的分辨率**，不是照片的分辨率。辐条、连杆、铆钉、针织、刻字不会自动长出来——要它们也得用基础体搭，而这正是"跑出一堆散件"的来源。所谓"AI 干活"，是 agent 在扮演"眼睛 + 判断"，不是神经网络在做重建。

**要真正带拓扑的网格，先拿去重建**：那是神经重建（混元 3D 这类），需要 GPU 服务、凭证、联网——但**网格一旦拿到，B 路线就能交付**（见下一节）。开工前必须把这句说给用户听，交付时再写一遍。

## 第二条路线 B：已有网格 → 同一套交付（2026-11-20 加）

用户第二轮反馈："更新了，但只是'认错'，不是'变强'。" 于是补的不是文案，是能力：**GLB/GLTF 进来，零件树、拾取、爆炸、线框、六项断言原样适用**。

| 你手上有什么 | 路线 | 命令 | 零件从哪来 |
| --- | --- | --- | --- |
| 只有照片 | **A** 程序化 spec + 八轮评审 | `build_pass.sh` | 你在 spec 里写的组件树 |
| 混元3D / Tripo / Meshy / 扫描仪 / DCC 导出的 GLB | **B** 网格导入 | `build_mesh.sh` | 网格本身：连通分量 → 大壳内折角 → 噪声才退化成空间分块 |

B 路线做的事（都在 `assets/viewer/mesh_rig.ts`）：

1. **焊接顶点**：合并导出的 GLB 是非索引三角汤，按索引找连通会得到"一个三角形一个零件"；先按位置量化焊接（epsilon = 包围盒对角线 × 1e-6）
2. **分件**：连通分量 → 大壳（≥ `--mesh-min-segment-triangles`）内按二面角切 → `auto` 在片数 <2 或 >4×预算时退到空间 k-means 分块
3. **标注**：每件写 `userData.sculptComponent`，折角出来的标 `mesh-part`，k-means 出来的标 `spatial-chunk`（不冒充零件）
4. **归一化 + 内嵌**：网格缩到单位尺寸，GLB 以 base64 data URL 内嵌，打包后 `external_refs: []` 仍成立

调参只有 5 个开关：`--mesh-partition auto|components|angle|spatial`、`--mesh-dihedral 32`、`--mesh-max-parts 64`、`--mesh-min-segment-triangles 1200`、`--exposure 0.72`（网格默认）。**网格本身不是拿来改的**——改的是分件策略，不是几何。

边界必须说清：**这条路线不做重建**，仓库里没有神经模型、不上传、没有 GPU 环节；页面文案也写"网格由外部重建模型生成"，不冒充"本流水线重建"。

实测（2026-11-20，真实浏览器 + 打包单文件）：

| 输入 | 分件结果 | 断言 |
| --- | --- | --- |
| `demo/fixtures/spoked-wheel.glb`（51 个岛：轮辋 + 轮毂 + 轴 + 24 辐条 + 24 铆钉） | 51 件，`angle`，全 `mesh-part` | 六项全绿；打包 1.8 MB，`file://` 实测 51 件 |
| `demo/fixtures/gear.glb`（单个挤出壳，404 三角面，18 齿） | 39 件，`angle`（默认参数，无需降阈值） | 六项全绿 |
| 一张带噪声的神经重建曲面（112,784 三角面） | 64 块，`spatial`，全 `spatial-chunk` | 六项全绿 |

两个 fixture 都能用 `assets/build/make_sample_mesh.mjs` 重新生成，所以这条路线**不需要建模软件、不需要 GPU、不联网**也能验证。

## 仓库与状态（2026-11-20）

- 仓库：<https://github.com/zhuan447133268-lab/photo-to-3D>，分支 `main`
- 本地工作副本：`D:\claude-work\photo-to-3d-demo`，`main` = `7109fd9`（B 路线，version 0.2.0）——**2026-11-20 已推送，远端 main 同步**
- 上一个已推送：`aac009f`（只改文档定位，被用户判为"只是认错，不是变强"）
- 本机已装位：`C:\Users\dfjq\.agents\skills\photo-to-3d-demo`（2026-11-20 已用 `git archive 7109fd9` 同步）
- 协议 **Apache-2.0**；`NOTICE` 明确声明**未复制** img2threejs 任何代码，只调用其命令行
- 成品随仓库发布两个：
  - `demo/mdr-zx310.html`（约 4 MB，A 路线，`file://` 实测 36 个零件 / 18 网格）
  - `demo/spoked-wheel-mesh.html`（1.8 MB，B 路线，`file://` 实测 51 个可点选零件，含 24 辐条 + 24 铆钉）

## 它是什么 / 本仓库补了哪一半

上游 [img2threejs](https://github.com/img2threejs/img2threejs) 做的是"按轮次从照片生成 Three.js 工厂代码"，生成完就结束。本技能补交付的后半段：

| 上游给的 | 这里补的 |
| --- | --- |
| 生成好的 `factory.ts` | 预览壳：拾取、选中高亮、爆炸、线框、HUD、参考图卡片 |
| 评审脚本与 spec 规范 | 证据抓帧契约（`setCamera` + 七种渲染模式） |
| 组件树 | 单文件打包器，内联 JS 与全部贴图，校验零外部引用 |
| — | 六项交互断言，真实浏览器跑 + 截图 |
| — | 驱动层抽象：同一套测试无头跑，也能在宿主 app 浏览器里跑 |

## 安装（2026-11-19 起才真能装）

```bash
git clone https://github.com/zhuan447133268-lab/photo-to-3D.git ~/photo-to-3d-demo
bash ~/photo-to-3d-demo/assets/build/bootstrap.sh --check
```

`bootstrap.sh` 做三件事：

1. 检查 python / node(≥18) / npm / git，缺什么直说
2. 装 `playwright-core`（**用本机已有的 Chrome，不下载浏览器**）
3. 没有现成工程 checkout 时，把 img2threejs clone 到 `$HOME/.cache/photo-to-3d/img2threejs`

`--check` 再跑一遍生成器的 `--help`，并**真拉一次浏览器**，打印解析到哪个驱动。这一步是"依赖装好了"与"证据链能跑"的分界线。

`three` / `esbuild` **故意不全局装**：由 `setup_workspace.sh` 按工作区钉死 `three@0.169.0 + esbuild@0.24.0`，因为换一个 three 可能改变 PMREM / OrbitControls 行为，把已签字的评审作废。

两个可选变量，默认值能跑：

| 变量 | 默认解析 | 何时设 |
| --- | --- | --- |
| `IMG2THREEJS_ENGINE` | `build_pass.sh` 第三参数 → `~/.workbuddy/skills/img2threejs` → `~/.cache/photo-to-3d/img2threejs` | 上游 checkout 在别处 |
| `PYTHON` | `python3` → `python` 自动回退 | 两个都不在 PATH，或 `python3` 低于 3.9 |

> ⚠️ **"把 GitHub 地址丢给别的 agent 让它自己装" 在 ZCode 里仍不是一键。** 从 URL 添加需要仓库带 `.zcode-plugin/plugin.json` 清单（插件市场格式），当前仓库只有根目录 `plugin.json`。现在能保证的是：**clone 下来（或放进 skills 目录）即可用**，依赖由 bootstrap 补齐。

## 八轮流程（顺序固定）

```
blockout -> structural-pass -> form-refinement -> material-pass
         -> surface-pass -> lighting-pass -> interaction-pass -> optimization-pass
```

跳过一轮就失去归因能力：再也说不清一处差异是几何、材质还是光照造成的。每轮都是：生成 → 构建 → 抓证据帧 → **看它** → 改 spec → 记录评审。不看帧、批量改参数，只会得到一堆没人能解释的差异。

`append_review.py` 只记录你看到的东西，缺层分数 / 缺视角清单（必须含 `long-axis` 与 `thickness-axis`）/ 引用不存在的截图，一律拒收。分数可以低，不能不给。

## 六项浏览器断言（交付门禁）

1. 拖拽后相机位置变化
2. 点击后读数区有内容，且**只有被点的那一个网格**被点亮
3. 点空白处取消选中（否则残留高亮污染后面每一张证据帧）
4. 爆炸把零件移开非零距离，且相机自动后退把拆开的装配留在画面内
5. 线框覆盖 100% 网格
6. 自动旋转开启时方位角推进、关闭时保持不动

## 先看这几条坑（完整 31 条在 `references/traps.md`）

1. **别改生成的 `.ts`** —— 下一轮覆盖，改 `spec`
2. **贴图必须放 build 根目录** —— 按裸文件名解析，放子目录静默全黑
3. **有贴图时 `material.roughness` 被钉成 1** —— 粗糙度只活在 map 里
4. **选中高亮写进共享材质** —— 左右件共用一个材质实例，点一个亮两个；**每网格克隆**
5. **B 路线：合并 GLB 是非索引的** —— 不先焊接顶点，按索引分连通会得到"一个三角形一个零件"（trap 28）
6. **B 路线：折角分件会把实心件的端面切下来** —— 90° 的帽/壁接缝在几何上和真正的分件缝无法区分；调高 `--mesh-min-segment-triangles` 或改用 `--mesh-partition components`（trap 29）
7. **B 路线：`spatial-chunk` 不是零件** —— k-means 按距离切，页面标签就写"块"，不要对客户说"64 个零件"（trap 30）
8. **断言：零件的"原点"不一定在零件上** —— 齿轮正面是圆环，质心落在孔里，点击必然落空；断言要瞄准**曲面顶点**（trap 31，`test_interactions.mjs` 0.2.0 已改）

## 实测记录

- **2026-11-19 全链路**（清空 HOME、从 GitHub clone 的副本，模拟他人机器）：
  `bootstrap --check` 通过（npm 装 playwright、clone 引擎、生成器 `--help`、真拉 Chrome）→ `setup_workspace` → `blockout` 构建（8 个组件标记 / 35 张贴图 / app.js 1.4M）→ 抓帧 → 打包 **3.78 MB / 35 maps / `external_refs: []`** → **六项断言全 PASS**，4 张截图
- 同一轮里 `--driver zcode` 与 `--driver playwright` 两套驱动共用同一组断言
- 一次临时目录复跑时引擎 clone 遇上网络失败（同命令此前成功），属网络抖动，重跑即可；脚本会把失败原因和手工命令打印出来，不会假装成功
- **2026-11-20 B 路线**（`7109fd9`，全部真实浏览器）：
  - `spoked-wheel.glb` → 51 件 / `angle` → 打包 **1.78 MB / `external_refs: []`** → 六项断言全绿；`file://` 双击实测 `ready=true, parts=51, level=mesh-part`
  - `gear.glb` → 39 件 / `angle`（默认参数）→ 六项断言全绿
  - 噪声曲面（112,784 面）→ 64 块 / `spatial` → 六项断言全绿
  - A 路线回归：`demo/mdr-zx310.html` 仍 18 网格，六项断言全绿（换了新的选中断言实现后复测）

## 验收方反馈（2026-11-20，已修文案定位）

使用方原话："**这个 skill 是挂羊头卖狗肉——它叫 photo-to-3d，但根本不做'照片变 3D'。** 核心生成器是个确定性 Python 脚本：读 spec → 吐基础几何体的拼装代码；它全程不读图片像素，那张参考图只是给人看的摆设。所谓'AI 干活'，就是 agent 看着照片用积木一块块搭——搭得像不像全看美术功底。这就是跑出一堆散件的原因，也是它永远拼不出辐条轮、连杆、铆钉的原因：零件库里只有方块和圆柱。"

核对结论：**属实**。`generate_threejs_factory.py` 无任何图像读取；几何数字来自 spec。唯一需要补充的是材质层——stage1 的提取器**真的逐像素统计**（裁图 → 调色板 + 五张 PBR 图），所以不是"全程不看图"，而是"看图提材质，不看图求几何"。真正的"照片 → 网格"要靠神经重建，本机跑不动。

已改并推送（`aac009f`，2026-11-20）：`SKILL.md` 新增 "What this is, precisely — say it before starting" 与开工前必说的那句话、`README` 中英各加 "它到底是什么（以及不是什么）" 一节、`plugin.json` 描述改成 "procedural primitive assembly"、`references/traps.md` 新增第 27 条（预期错位）、`demo/README` 去掉 "visual reconstruction" 的说法、README 里"上游从照片重建模型"改掉（上游同样是 spec 编译）。**没有改名字、没有改仓库地址**——改名属于对外动作，等用户定；也没有加神经重建通道（要云服务 + 凭证，是另一个产品）。

## 第二轮反馈（2026-11-20）："只是认错，不是变强" → 加 B 路线

用户原话："**更新了，但只是'认错'，不是'变强'。** 最新提交 `aac009f` 改了 6 个文件——全是 `.md` 和 `.json` 文档配置，没有一行生成代码变动。… 能力天花板没变：辐条轮、连杆、铆钉这类细节，照片不会自动变出来，只能手搓基础体——手搓就是散件。"

核对：**属实**。上一轮只在文档里承认了上限，代码一行没动，能交付的东西和之前一样。

这一轮的处置（`7109fd9`，2026-11-20 已推送）：**不动"照片 → 网格"这条做不到的路，把"网格 → 交付"这条做得能用。**

- 新增 `assets/viewer/mesh_rig.ts`（GLB 加载 / 焊接 / 分件 / 默认灯光环境控制器）
- `render_viewer.py --mesh-file` + `build_mesh.sh`：一条命令出预览页，GLB 内嵌 base64，`external_refs: []` 不破
- `make_sample_mesh.mjs` + `demo/fixtures/`：两个可再生成的样例网格，无 GPU、无网络也能验证
- `demo/spoked-wheel-mesh.html`：**24 辐条 + 24 铆钉 = 51 个可点选零件**——就是上一轮说"手搓就是散件"的那类细节，这条路线里它们是文件里现成的岛
- `test_interactions.mjs`：选中断言改成瞄准曲面顶点（原实现瞄零件质心，齿轮的质心在孔里，会把好页面判成坏页面）
- 文档：`SKILL.md` / 两版 README / `demo/README` / traps 28–31 / 版本号 0.2.0

仍然没做的：**没有加神经重建**（要 GPU 服务 + 凭证，是另一个产品）；**没有改名**（对外动作，等用户定）。B 路线现在能接住"重建好的网格"，接不住"从照片直接长出网格"——这句话在 SKILL、README、页面文案里都写着。

## 什么时候别用

- 人脸、布料褶皱、毛发、植物 → 走扫描或常规建模
- 要加工 / 维修 / 尺寸准确 → 这是视觉重建，不是 CAD
- 玻璃、镜面占比高的物体 → 照片提取的贴图会明显劣化
- 只想要"看起来像 3D 的图" → 短视频更快
- 要重建网格、手上又没有网格 → 先去做重建（混元 3D 这类 GPU 服务）；**网格一旦有了，走 B 路线 `build_mesh.sh` 就能交付**

## 与其他资产的关系

- **上游 img2threejs**：只做生成，本仓库是它的前端封装与交付补全，代码零复制
- [[Projects/文本生成3D方案赛/文本生成3D方案赛-主索引|文本生成3D方案赛]]：那条线是**文本 → 3D 网格**（Hunyuan3D 推理 + 门禁）；本技能是**照片 → 可交互网页**，管线不共用。可复用的只有一条元教训："门禁绿"不等于"产物好"，硬约束必须写成可执行检查
- [[three-scope-map 3D中国地图技能]]：同为 Three.js 交付，但一个是地理数据可视化、一个是实物重建，互不替代