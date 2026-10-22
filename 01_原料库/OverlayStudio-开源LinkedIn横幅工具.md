# Overlay Studio（开源 LinkedIn 横幅生成器）

> 收藏日期：2026-10-21 ｜ 状态：小红书封面改造版已交付，服务器运行中，待用户试用反馈

## 基本信息

- **仓库**：[Pepps233/OverlayStudio](https://github.com/Pepps233/OverlayStudio)
- **定位**：开源 LinkedIn 横幅（banner）在线制作工具，拖拽式画布编辑器
- **技术栈**：Next.js 16 + React 19 + TypeScript，可选 Supabase 统计，MIT 协议
- **体量**：⭐ 8，2026-01 创建，2026-04 后未更新，有[在线 Demo](https://pepps233.github.io/OverlayStudio/)
- **亮点功能**：AI 图像融合（两张图无缝 blending，"给猫戴帽子"）

## 与我背景的匹配评估（2026-10-21）

- ❌ **直接帮助小**：唯一场景是 LinkedIn 封面，我的主阵地是公众号+小红书（[[工作台/选题库]]），库里无 LinkedIn 运营
- ✅ **转化点 1**：AI 图像融合可拆出来做培训课 demo / 小红书选题
- ✅ **转化点 2**：代码量小、技术新、MIT 随便改，适合当"AI Coding 改前端"的练手靶子
- 结论：收藏即可，不必深用

## 改造记录（小红书封面版）

- **改造日期**：2026-10-21
- **工作区**：`D:\claude-work\OverlayStudio-xhs`
- **运行副本**：`D:\小红书封面助手`（含 node_modules，桌面有快捷方式）
- **⚠️ 部署坑**：桌面（C:\Users\dfjq\Desktop）是 junction 指向 D:\Users\dfjq\Desktop，Turbopack dev 在 junction 路径下路径拼接错乱报 500，项目实体必须放真实路径，桌面只能放快捷方式
- **改动清单**：
  1. 画布 1584×396 → 900×1200（小红书 3:4）
  2. 删除 LinkedIn Profile 模拟预览块（`PreviewPanel.tsx` 重写）
  3. 删除首页营销区（HeroSection / Showcase）
  4. 界面文案中文化：标题/页头/素材分类（背景/贴纸/装饰）/预览标签
  5. 素材缩略图比例：背景改 3:4，贴纸/装饰改方形
  6. 导出文件名 `linkedin-banner` → `xhs-cover`

## 使用记录

- 2026-10-21 晚：交付后服务器被系统内存压力自动杀掉一次（Claude Code 后台保护机制），用户反馈 localhost:3000 打不开，已重启恢复
- **启动方式**：双击 `D:\小红书封面助手\启动.bat`（黑色窗口要一直开着）；桌面有快捷方式
- 试用反馈：待用户使用后回填

## 可继续做的方向

- 预置素材换成小红书风格（目前还是城市风景+猫狗帽子）
- 接入即梦生图当背景来源
- 加文字图层（目前只能贴图，不能加标题文字——这是它最大的短板）
- 沉淀为"AI 改造开源项目"培训课素材
