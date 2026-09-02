---
date: '2026-09-01'
description: 学生端「查看证书→返回跳错页」bug：根因 certificate-view.vue 写死 router.replace('/student/certificates')；修复 f4f50c4（history.state.back 优先回来源页，深链兜底证书列表）测试环境三链路回归全过；追加 tab 同步修复 443122d（onTabChange 写回 ?tab=，返回还原所在 tab）测试环境部署回归通过
name: lab-exam-2026-09-01-cert-back-nav-fix
tags:
  - lab-exam
  - student
  - router
  - certificate
  - fix
  - testenv-verified
type: project
---
# 2026-09-01 学生端「查看证书→返回跳错页」修复与 tab 还原追加

**时间**：2026-09-01（晚间）
**修复 commit**：`f4f50c4`（已推送）+ `443122d`（tab 同步追加，已推送）
**相关文件**：`web/src/views/student/certificate-view.vue`、`web/src/views/student/index.vue`

## 1. 问题现象（用户报告）

考试页面点「查看证书」→ 看完点左上角「返回」→ **直接跳到证书列表页**（/student/certificates），没有回到原本的考试页面。

## 2. 根因

`certificate-view.vue` 的 `onBack` 写死了 `router.replace('/student/certificates')`：
- 从**考试列表**（已考 tab，/student）进来 → 返回也应回 /student，但被 replace 到证书列表。
- 从**考试结果页**（/student/exams/:id/result）进来 → 返回也丢了来源页。
- 从**证书列表**进来 → 恰好等价（所以只在这条链路上表现正常，掩盖了 bug）。

## 3. 修复（f4f50c4，测试环境已 build）

```js
const onBack = () => {
  // 优先返回来源页（考试列表/考试结果/证书列表），仅深链直达时兜底去证书列表
  const from = window.history.state?.back as string | undefined
  if (from && from.startsWith('/student')) {
    router.back()
  } else {
    router.replace('/student/certificates')
  }
}
```

原理：vue-router `history.state.back` 记录上一路由；来源是站内 /student* 页面就 `router.back()` 回来源页，深链直达（如分享链接 / 收藏直达）无来源页时兜底证书列表。typecheck/前端 build 通过。

## 4. 测试环境回归（390×844 手机视口，张凯悦账号）

三条入口链路逐一实测，history.state 全程记录：

| 链路 | 操作路径 | 证书页 history.state.back | 返回后落点 URL | 结果 |
|---|---|---|---|---|
| 1 考试列表 | /student 已考tab「电子技术」→ 查看证书 → 返回 | `/student` | `/student`（考试列表） | ✅ 修复生效，不再跳证书列表 |
| 2 考试结果 | 结果页「电子技术」→ 查看证书 → 返回 | `/student/exams/2933…/result` | `/student/exams/2933…/result`（结果页） | ✅ 回到结果页 |
| 3 证书列表 | /student/certificates「运动控制系统」→ 查看证书 → 返回 | `/student/certificates` | `/student/certificates`（证书列表） | ✅ 不受回归影响 |

- 历史栈 position 完全对称（链路1: 15→16→15；链路2: 15→16→15；链路3: 16→17→16），三条链路返回均无多余历史残留。
- 深链兜底分支（`from` 非 /student 时去证书列表）为纯前端逻辑，深链场景（无 back 源）未实测但逻辑简单、不影响三条真实链路。

**已知附带现象**（已修，见 §6）：链路1 返回后落在 /student 但顶部 tab 重置为「待考」，因 tab 状态只存在组件内存、未同步 URL、返回触发组件重建。

截图：`gui-test-screenshots/2026-09-01-cert-back-regression/`（link1 / link2 / link3 返回后落点）。

## 6. 追加修复：返回后 tab 还原（commit 443122d，已推送）

- **现象**：链路1 返回 /student 后顶部 tab 落「待考」，用户原在「已考」tab（看证书）却看到空列表，体验断层。
- **根因**：`index.vue` 的 tab 状态（activeTab）初始化只读 `route.query.tab`、默认 PENDING（index.vue:115-116）；`onTabChange` 从不把当前 tab 写回 URL（原 169-172 只清列表+loadData）。→ 从已考 tab 进证书页时历史里来源 URL 为 `/student`（无 `?tab=`）→ `router.back()` 带回的也是无 tab 的 `/student` → StudentHome 重建后 activeTab 归零回 PENDING。对比：exam-result.vue 返回用 `replace('/student?tab=FINISHED')` 显式回填 tab，所以结果页链路正常。
- **修复**（单文件 2 行，index.vue onTabChange）：`router.replace({ query: { ...route.query, tab: activeTab.value } })`——tab 切换即同步 URL，replace 不新增历史记录；证书页 router.back() 时来源 URL 即含 `?tab=FINISHED`，返回重建组件后自动还原已考 tab，与 f4f50c4 天然配合。
- **验证**：vue-tsc + vite build 通过；**测试环境部署后回归通过（2026-09-01 Jenkins 部署）**——切已考 URL→`?tab=FINISHED`（position 17）、进证书 back=`/student?tab=FINISHED`（18）、返回落已考 tab 列表（17，`tab "已考" [selected]`）✅；「进行中」tab 同步 `?tab=IN_PROGRESS` ✅；直达 `?tab=FINISHED` 落已考 ✅。链路2/3 回归不破（结果页 18→19→18、证书列表 19→20→19）。截图 `gui-test-screenshots/2026-09-01-cert-back-regression/`（link1-tab-restore-after-deploy、link3-back-to-cert-list-after-deploy）。用户答复「修，禁止动别的代码」——本次仅此一处改动，其余代码零触碰。

## 5. 结论

三条真实链路回归全部通过，修复在测试环境验证闭环；**待用户确认是否同步 build 正式环境**。追加的 tab 还原修复 443122d 已推送、**测试环境部署后回归通过**（2026-09-01 Jenkins，bundle index-B6CubP6d）；正式部署可一次带上 f4f50c4 + 443122d 两个修复。

## 相关

- [[session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit]]（同日早些时候的另两项修复交接）
- [[lab-exam-2026-09-01-prod-build-regression]]
- 记忆：[[labexam-certificate-back-nav-fix]]