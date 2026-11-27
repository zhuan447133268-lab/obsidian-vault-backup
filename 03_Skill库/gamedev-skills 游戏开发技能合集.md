---
date: 2026-11-26
source: GitHub `gamedev-skills/awesome-gamedev-agent-skills` + 本机 `npx skills --list` 全量条目核实
url: https://github.com/gamedev-skills/awesome-gamedev-agent-skills
type: 技能卡
tags: [AI工具, 游戏开发, AgentSkills, 跨引擎, 路由, 通用功法, 已装4项, MIT]
---

# gamedev-skills：80 本游戏开发「小抄」，本机只装了 4 本

> 本机安装位置：`~/.agents/skills/`（源）→ `~/.workbuddy/skills/`（Junction）、`~/.zcode/skills/` + `~/.codebuddy/skills/`（symlink）
> 2026-11-26 全量 `--list` 核实：80 个条目，Node v22.22.2 满足 22.20+ 要求

## 一句话定义

不是一个工具，是 **80 份给 AI 看的 SKILL.md 说明书**。每份只讲一件具体的事——「存档怎么写才不坏」「血条怎么摆不跑偏」「打击感怎么做出来」。AI 遇到对应问题时翻到那本，才干得专业。不是软件，不用运行。

## 关键判断：整套 80 个不能全装，按你的项目倒推只留 4 个

第一轮判断曾误判为「对用户没用」，理由是工作区里的经营看板 / 教师培训 / 公众号跟游戏无关。看到 `D:/03-个人文档/学习空间` 下的实际项目后推翻：

| 项目 | 技术栈 |
|---|---|
| `snow-ryokan` | 单文件 HTML + Canvas 2D，102KB `index.html` 手写 `S` 状态机、`loop(ts)`、`drawSnow` 粒子、`renderBar/renderActions/renderLog` 三套 UI；AI 生成 PNG 素材（清单明确「蒸汽雪花由程序叠加，素材里不要带」） |
| `forest-treehouse` / `lampwake` / `ai-game-course` | 本地 `three.min.js` 老版本（非 r187、非 import maps） |
| `cozy-desk` / `tangli` | Electron 桌面宠物 |

**结论**：Godot / Unity / Unreal / Bevy / Roblox / Phaser / Ebitengine 等 44 本引擎说明书是废纸；`router` 会把需求路由到错的方向；`threejs-*` 三本锁 r187 + import maps，跟本地 `three.min.js` 对不上；`workflows` 里的 Steam / itch 上架用不上。**这个仓库里没有原生 Canvas 2D 技能**——你手搓的那套骨架它管不着。

## 已装的 4 个（按实际价值排序）

| 条目 | 分组 | 大白话作用 | 对应到你的哪里 |
|---|---|---|---|
| `create-game-assets` | Disciplines | AI 生成素材的质检手册：风格统一、透明背景不出白边、授权记录 | `snow-ryokan/素材生成清单.md` 那套流程，从凭手感变成有流程 |
| `game-ui-ux` | Disciplines | 界面怎么摆不出错：锚点容器、缩放、安全区、事件驱动而非轮询 HUD | 手写的 `renderBar/renderActions/renderLog`，窗口一变就可能乱 |
| `game-feel` | Disciplines | 让操作有手感：trauma 震屏、hit-stop、缓动、squash & stretch | 雪夜灯光呼吸、蒸汽、湖面倒影那些硬编码 `t` 参数的动画 |
| `prototype-fast` | Workflows | 一小时验证一个点子：一句话 brief → 灰盒 → debug HUD → 试玩 → keep/kill/retune | 跟「2 小时跟做课」一个节奏 |

可选未装：`save-systems`（存档/继续营业，想给旅馆加进度持久化再装）、`visual-novel`（分支剧情，tangli 叙事线要扩再装）。

## 80 条全量分组（`--list` 核实）

- **Disciplines 通用功法（15）**：`ai-behavior-trees-utility-ai` · `audio-design` · `camera-systems` · `create-game-assets`✅ · `dialogue-systems` · `game-ai` · `game-feel`✅ · `game-ui-ux`✅ · `input-systems` · `level-design` · `performance-optimization` · `physics-tuning` · `procedural-gen` · `save-systems` · `shader-programming`
- **Genres 玩法模板（9）**：`card-game` · `fps-shooter` · `platformer` · `puzzle` · `roguelike` · `rpg` · `survival-crafting` · `tower-defense` · `visual-novel`（**没有专门的经营模拟模板**）
- **Godot 4.7（16）**：2d-movement / 3d-essentials / animation / audio / csharp / export / gdscript / gdscript-headless-testing / multiplayer / nodes-scenes / physics / resources / shaders / signals-groups / tilemap / ui-control
- **Unity 6.3 LTS（9）**：animation / build-pipeline / build-size / csharp-scripting / input-system / navmesh / physics / scriptableobjects / tilemap-2d
- **Unreal 5.8（6）**：behavior-trees / blueprints / cpp-gameplay / enhanced-input / niagara / packaging
- **Web Engines（6）**：`phaser-arcade-physics` · `phaser-core` · `pixijs-rendering` · `threejs-gltf-loading` · `threejs-materials-lighting` · `threejs-scene-setup`
- **Other Engines（12）**：`bevy-ecs` · `defold-core` · `love2d-core` · `pygame-core` · `roblox-*`×8
- **Router（1）**：`router` — 自动识别引擎 + 任务再加载对口技能
- **Workflows（5）**：`game-docs` · `game-jam` · `itch-publish` · `prototype-fast`✅ · `steam-publish`
- **Ebitengine（1）**：`ebitengine-game`

## 安装记录与坑（2026-11-26）

```bash
npx -y skills add gamedev-skills/awesome-gamedev-agent-skills -g \
  -a codebuddy -a zcode \
  -s create-game-assets -s game-feel -s game-ui-ux -s prototype-fast -y
```

1. **`npx skills add` 装不进 `~/.workbuddy/skills/`**。CLI 的有效 agent 列表里没有 workbuddy，只有 `codebuddy`（落到 `~/.codebuddy/skills/`）和 `zcode`（落到 `~/.zcode/skills/`），二者都是 symlink 到 `~/.agents/skills/`。
2. **WorkBuddy 要手动补链**。Git Bash `ln -s` 在本机报 `Operation not permitted`；可行解 = PowerShell `New-Item -ItemType Junction -Path <workbuddy-skills>/<name> -Target <.agents/skills>/<name>`。已验证 Junction 可读到 SKILL.md。
3. 探测 agent 标识的快捷法：随便给个无效 `-a` 值，CLI 会报 `SKILLS_INVALID_AGENTS` 并列出全部合法 agent。
4. `--list` 会 clone 整个仓库再发现技能，输出含大量 spinner 噪声（35KB），用 `--json` 可拿干净输出。
5. 安装回执提示「Review skills before use; they run with full agent permissions」——技能是给 AI 的说明文档，但它可能带脚本（如 `create-game-assets/scripts/asset_report.py`），用前过一眼。

## 核验状态

- [x] 4 个条目在 `~/.agents/skills/` 源目录存在且 SKILL.md 完整
- [x] `~/.zcode/skills/` + `~/.codebuddy/skills/` 各有 4 条 symlink
- [x] `~/.workbuddy/skills/` 各有 4 条 Junction，SKILL.md 可读
- [ ] 尚未在实际游戏开发中调用，价值判断基于条目描述 + 项目代码倒推，需实跑后回填
