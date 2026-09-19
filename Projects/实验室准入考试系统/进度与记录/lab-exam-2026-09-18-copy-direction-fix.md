---
title: 2026-09-18 页面提示文案方向写反（上方→下方）修复
date: 2026-09-18
project: 实验室准入考试系统
tags:
  - lab-exam
  - 文案
  - 修复记录
---

# 2026-09-18 页面提示文案方向写反（「上方」→「下方」）修复

> commit **`2834ac8`**（父 `c8e911e`）已推 main（`c8e911e..2834ac8`，远端核对 `2834ac8b39542c47d231663de9520b9d543fbec7`）；**测试环境已手动 build 并复验全过（2026-09-18，入口 `index-D1EUAOW4.js` → `index-2si0ntx2.js`）；正式环境已随 09-18 发版上线（「下方」文案生效、旧「上方」0 处）**——push 不触发 Jenkins，两地都需手动 build。
> 4 文件 / 7 行增 7 行删，**纯文案改动、零逻辑改动**。对应避坑指南 #29、验收清单 2026-09-18 批次。

---

## 一、触发

业务侧在**学院统计页**（学院管理员账号）看到页头右上角小字：

> 导出内容与**上方**「考生类型」一致

而「考生类型」筛选卡**实际在页头下方**（页面顺序：页头 → 筛选卡（含考生类型）→ KPI 卡片区 → 考生明细表）。用户指出应改为「与**下方**「考生类型」一致」，并要求顺手清掉其它页面的同款方向错误。

## 二、修复清单（3 处 + 1 处 PRD 同步）

| 位置 | 原文案 | 改为 | 说明 |
| --- | --- | --- | --- |
| `web/src/views/college-admin/statistics.vue:6` | 导出内容与**上方**「考生类型」一致 | 与**下方**「考生类型」一致 | 页面上**可见**的提示小字（本次主线） |
| `web/src/views/college-admin/statistics.vue:50`（考生类型下拉 `title`） | 筛选下方考生明细与导出内容，不改变**上方**学生/教师 KPI 口径 | 去掉「上方」 | KPI 卡在筛选卡**下方**；hover 提示 |
| `web/src/views/college-admin/statistics.vue:271`（注释） | 不改**上方**学生/教师 KPI 口径 | 去掉「上方」 | 随上一条同步 |
| `web/src/components/CertificateExportPanel.vue:63`（导出内容下拉 `title`） | 不改变**上方**列表 | 不改变**下方**列表 | 学院/全校两个证书导出页**共用**该组件；列表卡片在导出选择器**下方** |
| `web/src/views/school-admin/statistics.vue:7`（导出范围下拉 `title`） | 不改变**上方**统计口径 | 不改变**下方**统计口径 | KPI 卡在页头**下方**；同文件 172 行注释同步去「上方」 |
| `需求确认文档-迭代版.md` §7.7.2 第 5 条 | 表头提示「导出内容与**上方**…」 | 「与**下方**…」 | PRD 与实现同步 |

**刻意不改**：`web/src/views/teacher/exam-detail.vue:632`「自动复制失败，请手动选择**上方**文本复制」——经核对**是对的**（提醒卡片正文确实在「一键复制」按钮上方）。全前端 `grep 上方` 后这是唯一残留。

## 三、验证方式与结果

- `vue-tsc -b` + `vite build` 全绿；构建产物 grep：新文案命中、旧文案 **0** 处。
- 浏览器实测（本机预览 + 学院管理员 `BN100003243`）：页面 locator 计数「新文案 1 / 旧文案 0 / 新 tooltip 1」，KPI（1496）正常加载；证书导出页、全校统计页同样实测通过（全校统计页用 `SCHOOL_ADMIN` 账号 `沈春洋`）。
- **截图证据**：`gui-test-screenshots/2026-09-18-copy-direction-fix/`
  - `01-学院统计页.png` — 页头右上角可见新文案「导出内容与**下方**「考生类型」一致」，KPI 1496 学生 / 36 本院教师正常
  - `02-全校统计页.png` — 全校统计页正常渲染（学生 8473 / 教师 282），DOM 里导出下拉 `title` 已为新文案
  - `03-证书导出页.png` — 证书导出页正常渲染，DOM 里「导出内容」下拉 `title` 已为新文案
  - DOM 复核一次抓三个布尔：`新文案 true / 旧文案 false / 新 tooltip true`
- ⚠️ **原生 `title` hover 提示不会出现在页面截图里**（浏览器原生 tooltip 不参与页面渲染）——三处里只有学院统计页页头那处是可见文案（可截图），另两处只能读 DOM 的 `title` 属性核对，不能拿"截图里没看见"当验证结论。

## 四、提交隔离（多会话共用工作区）

`web/src/views/college-admin/statistics.vue` 里同时存在**另一个会话未提交**的改动（考生明细标题随「考生类型」联动，新增 `audienceHint` computed，8 行增 / 1 行删），至今仍留在工作区。本次只提交自己的改动，流程：

1. 备份当前文件 → `git checkout HEAD -- <该文件>`（回到未改状态）
2. 只重新施加本次 3 行文案改动 → 单文件 `git add` → commit
3. 把备份还原回工作区（保留另一会话的未提交改动）
4. 复核：提交版本里 `audienceHint` 命中 **0**、`上方` 命中 **0**

> 教训：共用工作区提交前必须先 `git diff` 分清哪些 hunk 是自己的；"只 add 自己的文件"不够，**同一文件也可能混着两个人的改动**。

## 五、附带摸清的环境事实（本机渲染验证）

- 本机 3000 端口开发后端来自 `server/.env` 的 `AUTH_MODE="bearer"`，而 `web/.env.production` + `.env.production.local` 都是 `cookie` → 直接拿默认（正式）构建在本机预览会**卡在登录页**。
- 要在本机看页面：另出一份 bearer 副本到**仓库外**（不污染 `dist/`）：
  `VITE_AUTH_MODE=bearer npx vite build --outDir "$TEMP/labexam-preview-bearer" --emptyOutDir`，再 `npx vite preview --outDir "$TEMP/labexam-preview-bearer" --port 4173`（`/api` 由 vite 配置代理到 3000）。
- **构建模式指纹**：cookie 构建产物里含 `X-CSRF-Token`（1 次），bearer 构建 0 次；模式字面量会被构建器常量折叠，搜 `"cookie"`/`"bearer"` 查不出来。
- `VITE_AUTH_MODE=bearer npm run build` 只在单条命令里覆盖，**不写任何 env 文件**（仓库配置零改动）。
- 本机学院管理员账号 `BN100003243 / 123456`（localhost 库，`need_change_password=0`）可登录。

## 六、待办

- [x] 测试环境**手动 build main** 后，按 [[避坑指南-验收清单]] 2026-09-18 批次复验：**#29** 三处文案（其中两处为 hover 提示，需读 DOM `title`）+ **#30** 明细口径三态 —— **2026-09-18 已复验全过**，见 §八
- [x] ~~正式环境随 v0.3 系列发版一并上线~~ —— **实际分两次**：`2834ac8`（三处「上方→下方」文案，4 文件 7 行）**已于 2026-09-18 随 v0.2~v0.3.5 发版上线并在正式环境复核生效**；`00129a0`（明细口径提示跟随「考生类型」）**未上正式**（正式学院统计页当前仍显示旧提示），待下一次迭代一起 build（发版闸门见仓库 `deploy/RELEASE_CHECKLIST.md`）

## 七、同批遗留已补提交：明细口径提示跟随「考生类型」（`00129a0`，2026-09-18）

**是什么**：`college-admin/statistics.vue` 标题那句写死的「共 N 条（**含学生与教师**，与导出口径一致）」改为按当前「考生类型」输出「仅学生 / 仅教师 / 含学生与教师」。

**为什么不是可有可无**：明细表与 Excel 导出**共用** `statistics.service.ts:buildCandidatePaperWhere`（把 `audience` 翻成 `userType` 过滤，见 §1395）。把「考生类型」选成"仅教师"时，列表与导出真的只剩教师，可这句提示仍写"含学生与教师"——**与实际口径自相矛盾**，且正式环境（跑 `2834ac8`）正在显示这句错文案。

**来历**：它是 `2834ac8` 的同批内容，当时为保持"上方/下方"提交范围干净而**按文件级剥离**（§四 的教训在此兑现）；2026-09-18 经用户确认"提交、不删"后单独成一条提交。

**提交与验证**：`00129a0`（父 `6d90623`）已推 main，1 文件 / 8 增 1 删，`npx vue-tsc -b` 通过；**测试环境已于 2026-09-18 与 `2834ac8` 同一次 build（`index-2si0ntx2.js`）一起验过、全过（见 §八）；正式环境尚未上** —— 正式学院统计页当前仍显示旧提示「共 N 条（含学生与教师…）」，随下次迭代一起 build。

**测试环境准备（2026-09-18 实测记录）**：

- build 前基线产物指纹：`assets/index-D1EUAOW4.js`（+ `index-BPLXbD6i.css`、`rolldown-runtime-Dd_uD5pT.js`）——build 后应变化，用它判断新代码是否真的上线
- **账号修复**：学院管理员 `陈卓 IME000179 / Test@2026v2` 的 `COLLEGE_ADMIN` 角色在测试环境**被别的会话摘掉了**（只剩 TEACHER），无法进学院统计页；已按产品流程恢复为**电气电子智能工程学院（DQ）**管理员（`college_admins.id=751fa716-04fa-4c82-bf32-cfee18b71ad8`，`userId=7696616f-7a92-42c5-9a13-d686067454e7`），`needChangePassword=false` 可直接登录。`collegeId` 是他本人所属（教育学院），与"管哪个学院"无关，别混
- **三态预期条数**（陈卓＝电气口径，`GET /api/statistics/candidates` 实测）：全部 **73** / 仅学生 **50** / 仅教师 **23**——与 2026-09-17 v0.3.5 记录的 73/23/50 一致；若 build 前后有人动了测试数据，以实测为准

**How to verify**：见 [[避坑指南-验收清单]] #30（六条：三态文案 + 导出同口径 + KPI 不受影响 + 教师口径冲突提示回归）。

相关：[[lab-exam-2026-09-17-college-stats-candidate-detail-and-concurrency]]（该页 v0.3.5 明细与并发加固）、[[避坑指南]] #29、[[避坑指南-验收清单]]

## 八、测试环境复验结果（2026-09-18 ✅ 全过）

**部署确认**：Jenkins 手动 build 后入口指纹 `assets/index-D1EUAOW4.js` → **`assets/index-2si0ntx2.js`**，新文案落在三个懒加载 chunk 里。

| 验收点 | 结果 | 证据 |
| --- | --- | --- |
| 学院统计页页头小字 | 「导出内容与**下方**「考生类型」一致」 | 截图 `01-默认全部考生.png` |
| 学院页「考生类型」`title` | 「筛选下方考生明细与导出内容，不改变学生/教师 KPI 口径」 | 读 DOM `title` |
| 证书导出页「导出内容」`title`（学院入口 + 全校入口，共用组件） | 「只决定导出范围，不改变**下方**列表；…」 | 截图 `05`（`/college-admin/certificates-export`）+ `07`（`/school-admin/certificates-export`） |
| 全校统计页「导出内容」`title`（`admin`/`SCHOOL_ADMIN`） | 「只影响导出内容，不改变**下方**统计口径」 | 截图 `06` |
| #30 三态文案 + 条数 | 73 → 50 → 23，提示分别为「含学生与教师 / 仅学生 / 仅教师」 | 截图 `01/02/03` |
| 列表构成 | 「仅教师」态明细表整表 20 行（首页）`考生类型`列**全为「教师」** | 表头定位列索引统计 |
| 与导出同口径（行口径） | 导出 xlsx 数据行 **73 / 50 / 23**，与标题逐数相等（`scope=college`） | `GET /api/statistics/export` |
| KPI 反向验证 | 三态下 KPI 逐格相同（学生 1132 / 0.1% / 0.0% / 6；教师 60 / 3.3% / 50.0% / 3） | 三张截图对比 |
| 全校口径反向验证 | 导出 206 / 180 / 26，与 v0.3.5 基线（206=180+26）逐数吻合 | `GET /api/statistics/export?scope=school` |
| `teacherScopeConflict` 回归 | 仅教师 + 班级`2023 23电子一班` → 黄条「教师考生不属于任何专业/班级…」+ 明细 0 条；清除班级后回 23 条 | 截图 `04` |
| 残留扫描 | **全量 63 个产物 js**：命中「上方」**仅 1 处**（`exam-detail-DNnk-AI8.js`，即应保留的教师考试详情）；「下方」5 处（`statistics-CBxeOncB.js`×2、`CertificateExportPanel-Doi-flh6.js`×2、`statistics-BKBzg5QS.js`×1） | 页面内 `fetch` 逐文件正则统计 |

截图目录：`gui-test-screenshots/2026-09-18-testenv-hint-audience/01~06`（本地留存，不入库）。

> 方法记录：产物文案残留扫描不要用 `curl` 抓 `/assets/*.js`——本机 Git Bash 下 `grep -o` 出来的路径会丢前两字符导致 404；改成**页面内 `fetch` 同源抓取**（入口 html → 入口 js 里的 chunk 映射，63 个文件分批 `Promise.all`）最稳。