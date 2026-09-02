---
name: lab-exam-2026-09-01-admin-password
description: admin 密码之谜收口——用户本人把正式环境 admin 密码从 Gb$d!a$X8&eTbij4 改成了 oceg2026；正式库仍是 8-28 旧版 SQL（学校管理员=admin 强密码，fix SQL 未执行）
type: project
date: 2026-09-01
---

# admin 密码之谜收口（2026-09-01）

## 结论

1. **admin 密码不再是 Gb$d!a$X8&eTbij4 不是异常**：用户本人已把正式环境 admin 密码改为 **oceg2026**（2026-09-01 用户亲自确认）。早前会话"admin/Gb$d!a$X8&eTbij4 可登录（code 0）→ 现在 1001"的时序矛盾由此完全解释——会话期间用户改了密码。
2. **正式库仍是 8-28 旧版 SQL**：实测 `BN100005453`（沈春洋）用 **admin 强密码 Gb$d!a$X8&eTbij4 登录成功（code 0）**，而 `hByUWawE5^6aaW`（fix SQL 方案 B 密码）与 `123456` 均 1001——证明 `fix-school-admin-password.sql`（生成 2026-09-01 11:38）**尚未在正式库执行**，学校管理员密码仍是旧版 SQL 写入的 admin 强密码。
3. `admin-password.txt` / `01_user_data.sql` 中的 bcrypt hash `$2a$10$Y/.vaqQvqQYQxs51R3mcDuXZaes/QwJoz39uS2PsfZVwEagG5wXoK` = `Gb$d!a$X8&eTbij4`（bcryptjs 实测 true）——这是**初始密码**，现在正式环境已失效属预期。

## 对用户的实际意义

- 正式环境 admin 密码 = **oceg2026**（用户改的，下次需要时直接用）。
- 学校管理员的 `fix-school-admin-password.sql` 还没执行；何时执行、用方案 A（123456）还是方案 B（各自强密码）等用户拍板后我再操作（需用户先给正式库执行权限/方式）。

## 相关链接

- [[session-handoff-lab-exam-prod-import-sql-regenerated-2026-08-28]]（8-28 旧版 SQL 背景）
- [[lab-exam-2026-09-01-teacher-mobile-adaptive]]（同日另一结论）
- 记忆：[[labexam-admin-password-user-changed]]