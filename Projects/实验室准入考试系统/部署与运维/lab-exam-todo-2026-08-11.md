---
date: '2026-08-11'
tags:
  - lab-exam
  - todo
  - 数据同步
  - 权限
  - 表单bug
status: pending
type: todo
---

## 更新记录

### 2026-08-11 前端表单 bug 修复已 push
- 提交 commit：`8ce5132` + `764f408`
- 推送分支：`main → origin/main`
- 包含改动：
  - `fix(users)`: 新增师生弹框角色切换时清空学院，避免班级列表加载错乱
  - `fix(users)`: 角色切换时清空全部表单字段（姓名/工号/学号/学院/班级），避免信息残留
- 自测：本地前端 dev + 测试库后端，admin 登录实测双向切换均正常，未误写库

### 2026-08-11 初始密码统一 123456 已 push
- 提交 commit：`853d11f`
- 推送分支：`main → origin/main`
- 包含改动：`fix(users)`: 新增与重置密码统一初始密码123456，避免随机密码难以传达
- 自测：真实接口调用验证，见「第 3.5 节」

---

## 一、金智库 → lab_exam 数据同步（待业务方确认阻塞项）

> 详见 [[lab-exam-todo-2026-08-10]] 第「2026-08-11 金智库→lab_exam 数据同步决策」段

- **已确认**：只同步哈尔滨剑桥学院(010201)在读学生；学号直接匹配；电气电子智能工程学院(DQ)已存在。
- **⚠️ 待确认**：金智库「智能与电气电子工程学院」(01020126, 约2723在读生) 归属。
  - 用户判定：**暂时不导入**，待找业务方确认映射到 DQ 还是 ZN，或新建学院。
  - **确认前不要导入该学院学生，同步脚本暂未编写。**

---

## 二、权限与数据匹配机制（实测结论）

### 1. 学院管理员数据范围
- 来源：`college_admins` 绑定表（不是 users.collegeId 人事归属字段）
- 绑定哪个学院 → 看哪个学院的数据（首页统计/本院教师/班级/分配班级）
- 已修复 `login` 接口返回 dataScope，前端登录后刷新，学院管理员首页统计和分配班级正常。

### 2. 「新增教师/管理员能否匹配到对应数据」实测结论
- **能**。权限范围来自绑定表：
  - 学院管理员 → `college_admins` 绑定（决定看哪个学院）
  - 教师 → `teacher_classes` 绑定（决定看哪些班级）
- **新增教师没填专业，分配班级时仍能选该学院班级** —— 分配班级时学院管理员看到的是自己管辖学院的所有班级（来自 college_admins 权限），与教师填没填专业无关。

### 3. 真实业务规则（用户确认）
- **每个学院的管理员，分配自己学院的教师去监考自己学院的班级。**
- 不会出现「人事归属学院 ≠ 管辖学院」的跨学院场景（之前的 100029018 案例是误操作，非系统问题）。

---

## 三、新增师生弹框表单残留 bug（已修复）

### 现象
- 在「新增师生」弹框，教师页填姓名/工号/学院 → 切换到学生页，姓名/学院被保留；若学院残留但班级列表被清空，则点班级下拉显示 no data。
- 反向（学生→教师）同理。

### 根因
- 角色切换时 `onRoleChange` 只清了 classId 和 classes，**没清 collegeId** → 学院残留但 classes 已空 → `onCollegeChange` 不触发 → 班级不加载。

### 修复（commit `764f408`）
```js
const onRoleChange = () => {
  form.name = ''
  form.staffNo = ''
  form.studentNo = ''
  form.collegeId = ''
  form.classId = ''
  classes.value = []
}
```
- 语义：切换角色 = 清空表单重新填。

### 自测结果（真实浏览器操作）
- 教师→学生：姓名/学号/学院/班级全部清空 ✅
- 学生→教师：姓名/工号/学院全部清空 ✅
- 未误写库 ✅

---

## 三-五、初始密码统一 123456（已修复，commit `853d11f`）

### 现象（用户反馈）
- 新增教师后弹窗出现一串随机密码（如 `Ab3kXm7Pq2`），但弹窗底部本写着"初始密码为 123456"，且随机密码管理员记不住、难以传达给老师，不合理。

### 根因
- commit `d0205c9`（security 审查）把初始密码从固定 `123456` 改成随机 `generateRandomPassword()` + `needChangePassword:true`，但忽略了管理员无法记住/传达随机密码的体验问题。属回归。

### 修复
- `users.service.ts` 两处随机密码改回固定 `123456`（保留 `needChangePassword:true` 首次登录强制改密，安全性不降）：
  - `createUser`（约436行）：`generateRandomPassword()` → `'123456'`
  - `resetPassword`（约1093行）：`generateRandomPassword()` → `'123456'`

### 自测结果（真实接口调用，本地库）
- 创建教师接口返回 `initialPassword = '123456'` ✅
- 重置密码接口返回 `password = '123456'` ✅
- 测试数据已清理，未污染本地库 ✅

### 附带
- 本地库 admin（系统管理员）登录密码 = `123456`（本地库与测试库 admin 密码不同，测试库是 `bBpeIAj92Oz6`）。

---

## 四、账号与凭据

- 测试环境：`https://lab-exam-test.oceghome.com`
  - admin 账号：`admin` / 密码：`bBpeIAj92Oz6`
  - 学院管理员：`100029018`（薛晓转，教育学院），密码 `oceg2026`
- 本地库（localhost:3306/lab_exam）：root 密码 `20210406`
- ⚠️ 注意：`lab-exam-claude-code` 会话中曾把 admin 明文密码记在 Obsidian（[[实验室准入考试管理员账号]]），安全风险，留意。

---

## 五、环境操作备注（教训）

- **server/.env 不要随意改**（不被 git 跟踪，改错难恢复）。本次自测曾误改本地库连接串，导致认证失败，已恢复。
- 自测纯前端交互 bug **用本地库即可，无需连测试库**。

---

## 六、前端设计规范落地（Claude Code 实施）

### 6.1 评审结论
- 引用面盘点：AppSearchForm 9 处、AppTable 14 处、AppFormDialog 5 处。
- 规范 2a（操作列 fixed=right）：低风险，可做。
- 规范 1（弹窗宽度自动决策）：`users.vue` 改 860px 必须同步改双列布局，其余 4 个弹窗改 400px。
- 规范 3（前端规范文档）：零代码风险。
- 规范 2b（分页收口到 AppTable）：高风险，本期不做，上线稳定后评估。
- 发现真 bug：`school-admin/college-admins.vue` 后端已分页但前端漏渲染 `el-pagination`，只能看第一页。

### 6.2 已 push 的改动

提交记录：

```
995c807 docs: 新增前端设计规范文档
43a4d02 feat(ui): 规范2a+1落地 — AppTable操作列fixed=right + AppFormDialog宽度自动决策
```

具体改动：
- **规范 2a**：8 处操作列加 `fixed="right"`。
  - `teacher/index.vue`、`teacher/exam-detail.vue`（papers + absentees）、`college-admin/teachers.vue`、`school-admin/classes.vue`、`school-admin/college-admins.vue`、`school-admin/majors.vue`、`school-admin/school-admins.vue`、`school-admin/users.vue`
- **规范 1**：`AppFormDialog.vue` 新增 `fieldCount` prop，按字段数自动选 400px/860px；5 个引用页传入 `field-count`；`users.vue` 弹窗改为双列布局。
- **规范 3**：新增 `web/docs/frontend-style-guide.md`。

### 6.3 Hermes 修复项状态

- `college-admins.vue` 补分页：commit `9ed6568`，已 push，需验证翻页。
- `teachers.vue` 错误提示：commit `cd4813a` 把 catch 改为空 catch（展示后端具体原因），后被 commit `7bfee5f` **revert** 回 `ElMessage.error('分配失败')`。
  - **用户已确认**：这个 revert 是用户让 Hermes 做的，`teachers.vue` 维持原样，不展示后端具体原因。

### 6.4 验证清单

#### 操作列 fixed=right
- [ ] `teacher/index.vue`：操作列固定
- [ ] `teacher/exam-detail.vue`（papers/absentees）：操作列固定
- [ ] `college-admin/teachers.vue`：操作列固定
- [ ] `school-admin/classes.vue`：操作列固定
- [ ] `school-admin/college-admins.vue`：操作列固定
- [ ] `school-admin/majors.vue`：操作列固定
- [ ] `school-admin/school-admins.vue`：操作列固定
- [ ] `school-admin/users.vue`：操作列固定

#### 弹窗宽度
- [ ] `teacher/index.vue`：创建考试弹窗 400px
- [ ] `college-admin/teachers.vue`：分配班级弹窗 400px
- [ ] `school-admin/college-admins.vue`：新增学院管理员弹窗 400px
- [ ] `school-admin/school-admins.vue`：新增学校管理员弹窗 400px
- [ ] `school-admin/users.vue`：新增师生弹窗 860px，双列布局，角色切换正常

#### Hermes 修复项
- [ ] `school-admin/college-admins.vue`：分页可翻页

### 6.5 新增 Obsidian 笔记
- [[索引]]
- [[2026-08-11 前端设计规范落地]]

---

## 关联会话
[[session-handoff-lab-exam-import-layout-test-2026-08-11]]