---
title: 2026-08-28 生产环境导入SQL重新生成+admin账号修复
tags:
  - lab-exam
  - deploy
  - database
  - session-handoff
type: project
date: '2026-08-28'
status: completed
---
# 2026-08-28 会话交接：生产环境导入 SQL 重新生成 + admin 账号修复

> 状态：✅ SQL 已重新生成，可交给运维执行
> 关联：[[生产环境数据库导入清单]]、[[lab-exam-deploy-checklist]]、[[2026-08-06 实验室准入考试系统部署状态-2026-08-06]]

---

## 一、背景

生产环境正式上线前，需要将测试环境验证过的基础数据（学院/专业/班级/教师/学生/学校管理员）和题库数据导入正式数据库。

原方案是直接运行 Python 脚本连库导入；本次改为**生成两个 SQL 文件**，由运维/DBA 在 MySQL 客户端执行，更安全、可审计、可回滚。

---

## 二、关键文件位置

| 文件 | 路径 | 说明 |
|---|---|---|
| 人员数据 SQL | `D:\claude-work\lab-exam\01_user_data.sql` | 17781 行，5.4M |
| 题库数据 SQL | `D:\claude-work\lab-exam\02_question_data.sql` | 2003 行，954K |
| SQL 生成脚本 | `D:\claude-work\lab-exam\generate_import_sql.py` | 不连库，仅生成 SQL |
| admin 密码文件 | `D:\claude-work\lab-exam\admin-password.txt` | 含 admin 明文密码与 bcrypt hash |
| 运维执行说明 | `D:\claude-work\lab-exam\ops-import-readme.md` | 给运维的步骤与验证 SQL |

---

## 三、本次修复内容

### 3.1 admin 账号缺失问题

**问题**：最初生成的 `01_user_data.sql` 只保留已有 admin（`DELETE FROM users WHERE student_no != "admin"`），如果生产库没有 admin，执行后系统管理员账号不存在。

**修复**：在 `generate_import_sql.py` 中增加 admin upsert，使用 `INSERT ... ON DUPLICATE KEY UPDATE`：

```python
lines.append('-- 创建/更新系统管理员 admin 账号')
admin_uid = str(uuid.uuid4())
lines.append(
    f"INSERT INTO users (id, name, student_no, user_type, status, password_hash, need_change_password, created_at, updated_at) "
    f"VALUES ('{admin_uid}', '系统管理员', 'admin', 1, 1, '{ADMIN_PASSWORD_HASH}', 1, '{now}', '{now}') "
    f"ON DUPLICATE KEY UPDATE password_hash = '{ADMIN_PASSWORD_HASH}', need_change_password = 1, updated_at = '{now}';"
)
admin_role_id = str(uuid.uuid4())
lines.append(
    f"INSERT INTO user_roles (id, user_id, role) "
    f"VALUES ('{admin_role_id}', (SELECT id FROM users WHERE student_no = 'admin'), 'SCHOOL_ADMIN') "
    f"ON DUPLICATE KEY UPDATE role = role;"
)
```

### 3.2 数据格式对齐测试环境

| 项目 | 最初 | 修复后 | 依据 |
|---|---|---|---|
| 选项格式 | `{"A":"内容"}` | `[{"key":"A","content":"内容"}]` | `question-import.service.ts` |
| 判断题答案 | `A` / `B` | `["TRUE"]` / `["FALSE"]` | 测试环境实际数据 |
| 通用安全题 college_id | 非存在的学院 ID | `NULL` | 后端服务逻辑 `GENERAL_SAFETY` 不关联学院 |

### 3.3 学校管理员恢复

沈春洋（BN100005453）、陈冰冰（IME000290）两位学校管理员仍在 `01_user_data.sql` 中恢复，使用与 admin 相同的 bcrypt hash。

---

## 四、验证结果

### 4.1 SQL 文件内容验证

- `01_user_data.sql`：17781 行
- `02_question_data.sql`：2003 行，2001 题
- admin upsert 位于 `01_user_data.sql` 第 16-18 行
- `SCHOOL_ADMIN` 出现 3 处：admin + 沈春洋 + 陈冰冰
- users INSERT：8753 条（8473 学生 + 278 教师 + 2 学校管理员；admin 为 upsert）

### 4.2 执行后预期数据量

- colleges：8 个
- majors：约 41 个
- classes：约 206 个
- teachers：278 人
- students：8473 人
- questions：2001 题
- 学校管理员：3 人（admin + 沈春洋 + 陈冰冰）

---

## 五、给运维的执行摘要

执行前必须：
1. 备份生产数据库
2. 确认已执行 `npx prisma migrate deploy`
3. 禁止执行 `npx prisma db seed`

执行：

```bash
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 01_user_data.sql
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 02_question_data.sql
```

执行后 admin 密码见 `admin-password.txt`。

---

## 六、待跟进事项

- [ ] 运维执行 SQL 后反馈执行结果
- [ ] 验证 admin、学校管理员、教师、学生登录
- [ ] 验证题库可见、组卷可用
- [ ] 恢复生产环境安全策略（限流、CORS、Cookie、admin 强密码）
- [ ] 配置数据库自动备份

---

**Why**：生产环境数据导入需要可审计、可回滚、格式与测试环境一致；admin 账号必须保证存在，否则系统无法初始化管理。

**How to apply**：新 session 启动时，先确认运维是否已执行 SQL；若未执行，直接发送两个 SQL 文件和 `admin-password.txt`。


---

## 2026-08-28 15:10 追加：运维导入报错修复

### 报错信息

施涛 8/28 14:56 反馈执行 `02_question_data.sql` 时报错：

```
[ERR] 3140 - Invalid JSON text: "Missing a comma or '}' after an object member." at position 136 in value for column 'questions.options'.
```

### 根因

`generate_import_sql.py` 中的 `escape_json` 只做了 `json.dumps()`，未考虑 MySQL 单引号字符串的转义规则。

当选项内容包含英文双引号 `"` 时：
1. `json.dumps()` 会转义为 `\"`
2. 生成的 SQL 形如 `'...\"...\"...'`
3. MySQL 解析单引号字符串时，默认会把 `\"` 还原为 `"`
4. 存入数据库的 JSON 中双引号失去转义，变成 `'..."..."...'`
5. MySQL 的 JSON 校验器解析时认为字符串提前结束，报 3140 错误

受影响行示例：
- 第 18 行：`在塑封袋上标明"小心玻璃"`
- 第 1840 行：`\"反正不用\"，继续堆放物品`

### 修复

修改 `generate_import_sql.py` 中的 `escape_json`：

```python
def escape_json(value: str) -> str:
    if value is None:
        return ''
    # json.dumps 会把内容中的双引号转义为 \"，但在 MySQL 单引号字符串中，
    # 反斜杠会被 MySQL 再次转义，导致 JSON 中的 \" 变成 "，破坏 JSON 结构。
    # 因此需要对生成的 JSON 字符串再做一次转义：\ -> \\，' -> ''
    s = json.dumps(value, ensure_ascii=False)
    s = s.replace('\\', '\\\\')
    s = s.replace("'", "''")
    return s
```

### 重新生成结果

- 生成时间：2026-08-28 15:06:48.400
- `01_user_data.sql`：17782 行
- `02_question_data.sql`：2003 行，2001 题
- 验证：所有 questions.options / questions.answer 字段经 MySQL 反斜杠还原后均可被 `json.loads()` 正确解析，无报错

### 给运维的重新执行说明

1. 重新下载最新版 `01_user_data.sql` 和 `02_question_data.sql`
2. 执行前仍须备份数据库
3. 按原命令重新导入：

```bash
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 01_user_data.sql
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 02_question_data.sql
```

### 待跟进

- [ ] 运维重新执行 SQL 后反馈结果
- [ ] 验证 admin / 学校管理员 / 教师 / 学生登录
- [ ] 验证题库可见、组卷可用
- [ ] 恢复生产环境安全策略（限流、CORS、Cookie、admin 强密码）
- [ ] 配置数据库自动备份


---

## 2026-08-28 15:25 追加：修复 1452 外键约束错误

### 报错信息

```
[ERR] 1452 - Cannot add or update a child row: a foreign key constraint fails (`lab_exam`.`questions`, CONSTRAINT `questions_college_id_fkey` FOREIGN KEY (`college_id`) REFERENCES `colleges` (`id`) ON DELETE SET NULL ON UPDATE CASCADE)
```

### 根因

`01_user_data.sql` 和 `02_question_data.sql` 中的 `college_id` 之前使用 `uuid.uuid4()` 随机生成，**每次重新生成都不一样**。如果运维只更新了 `02_question_data.sql` 而没有同步更新 `01_user_data.sql`，`questions.college_id` 就会引用不存在的 `colleges.id`，触发外键约束失败。

### 修复

修改 `generate_import_sql.py`：
1. 增加确定性 UUID 命名空间 `UUID_NAMESPACE`
2. 学院 `id` 改为基于学院名称生成：`uuid.uuid5(UUID_NAMESPACE, f'college:{name}')`

这样无论脚本何时运行，同一学院名称始终生成同一个 UUID，`01_user_data.sql` 和 `02_question_data.sql` 的 `college_id` 永远一致。

### 重新生成结果

- 生成时间：2026-08-28 15:20:22.xxx
- `01_user_data.sql`：17782 行
- `02_question_data.sql`：2003 行，2001 题
- 验证：
  - 所有 `questions.options` / `questions.answer` JSON 字段经 MySQL 还原后可解析，0 报错
  - 所有 `questions.college_id` 都能在 `colleges` 表中找到，0 缺失

### 给运维的最终执行说明

**必须两个文件一起重新导入**，否则仍会因旧 `01_user_data.sql` 中的随机 college_id 不匹配而报 1452：

```bash
# 1. 备份
mysqldump -u {用户名} -p{密码} -h {主机} {数据库名} > backup_20260828.sql

# 2. 重新导入（两个文件都要是最新版）
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 01_user_data.sql
mysql -u {用户名} -p{密码} -h {主机} -P {端口} {数据库名} < 02_question_data.sql
```

### 待跟进

- [ ] 运维两个文件一起重新导入后反馈结果
- [ ] 验证 admin / 学校管理员 / 教师 / 学生登录
- [ ] 验证题库可见、组卷可用
- [ ] 恢复生产环境安全策略（限流、CORS、Cookie、admin 强密码）
- [ ] 配置数据库自动备份


---

## 2026-08-28 15:35 追加：运维确认导入成功

运维反馈：将之前导入的 SQL 数据清空后，重新执行最新版 `01_user_data.sql` + `02_question_data.sql`，导入成功。

### 已确认完成项

- [x] 运维执行 SQL 后反馈结果

### 仍待跟进

- [ ] 验证 admin / 学校管理员 / 教师 / 学生登录
- [ ] 验证题库可见、组卷可用
- [ ] 恢复生产环境安全策略（限流、CORS、Cookie、admin 强密码）
- [ ] 配置数据库自动备份
