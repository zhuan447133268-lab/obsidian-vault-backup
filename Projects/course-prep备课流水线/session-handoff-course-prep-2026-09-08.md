---
date: '2026-09-08'
project: linmumu-course-prep
status: handoff
tags:
  - course-prep
  - session-handoff
---
# course-prep 会话交接 2026-09-08（v1.2 后 SVG 取景加固已推）

## 项目一句话

`linmumu-course-prep`（大学老师备课流水线 skill）已发布 https://github.com/zhuan447133268-lab/linmumu-course-prep ，对外分享用。本地仓库 `D:\claude-work\linmumu-course-prep`，授权 CC BY-NC 4.0。

## 当前状态（截至 2026-09-08）

| 版本 | 提交 | 内容 |
|---|---|---|
| v1.1 | 84d76bb | LICENSE、联系方式、README 依赖说明 |
| v1.2 | 94a209b | 03 讲稿/04 测验 docx 直出（docx_lib.py + 答案区分页，学生版/教师版一份两用），三查脚本直接读 docx |
| v1.2+ | **50792ba（最新 main）** | 05 交互演示 SVG 取景加固 + 查3 小数误报修复 |

## 本次会话做的事（全部已推 main）

1. **查2 新增 `check_svg_frame` 机器检查**（scripts/check_deliverables.py）：05 的 SVG 内容包围盒在 viewBox 横/纵两个方向覆盖率均须 ≥50%，否则 FAIL。
   - 回归验证：坏 viewBox `-60 -220 220 440`（61%/46%）→ FAIL；修好版（100%/100%）与仓库骨架 demo_template.html（90%/56%）→ PASS。
2. **demo_template.html 加「SVG 取景铁律」注释块**：viewBox 必须手工紧凑取景，绝不允许沿用公式坐标系；svg 已带 max-width:430px + 居中。
3. **SKILL.md 铁律9/纪律3、README 三查清单**同步纳入取景项。
4. **查3 页数声明正则补小数尾巴守卫**：`7.08 页脚线` 这类不再误报成「8 页」（自测课 00 附注曾因此误 FAIL）。
5. 自测课三查恢复 **0 FAIL / 0 WARN**。

## 踩坑根因（为什么第一版没事）

第一版模板是**先定画框再摆图形**（画框服务人眼）；我出的 bug 是**画框跟随公式坐标系**（x=20·Re(s) → 画框 1:2 竖长、内容只占横向 39%，整页放大、大片空白）。修法：viewBox 手工紧贴内容 + `max-width` 限宽居中。

## 关键路径

- 仓库：`D:\claude-work\linmumu-course-prep`（git main 已推 50792ba）
- 标准自测课：`D:\claude-work\selftest\备课产出\自动控制原理\第6节-根轨迹\`（六件齐 + _recalc.py）
- 自测约定：**改 skill 任何部分，必须跑《自动控制原理·根轨迹》标准自测课，三查 0 FAIL/0 WARN 才能推**

## 待办（新 session 接手）

1. ⏳ 用户关掉 WPS 后，补跑 `export_shots.py` 逐页截图终验（本机 WPS 占 COM → RPC_E_CALL_REJECTED，目前降级为坐标核对，自测课 00 附注已标）。
2. （可选）把 v1.2+ 的取景检查变化补进 references/exemplar.md 的 05 金样对照（本次没动 exemplar，只改了注释+机器卡线）。
3. （观察项）SKILL.md 自测约定里的挑刺交叉验证：重要课程建议换新会话重跑 06。

## 可沉淀 Skill/概念卡

- **SVG 取景铁律**：画框是给人眼服务的，坐标单位是画布单位不是物理单位。viewBox 永远手工紧凑取景（内容横/纵 ≥50%），公式坐标系只用来算点、不用来定框。机器可卡线：包围盒覆盖率检查。本项目已固化在 check_deliverables.py `check_svg_frame`。
- **交付类项目双保险模式**：用户踩坑类教训 = 注释（提醒写代码的人）+ 机器检查（卡住不提醒也能跑的人），只加注释等于没加。
