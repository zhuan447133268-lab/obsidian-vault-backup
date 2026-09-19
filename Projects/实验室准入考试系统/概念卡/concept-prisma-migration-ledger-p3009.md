# 概念卡：Prisma 迁移账本与 P3009

> 一句话：`prisma migrate deploy` 是**记账式**的——`_prisma_migrations` 表里没有的迁移它才执行；表结构已经在、账本没记，下次 deploy 就会重放撞 `Duplicate column` → 迁移标 failed → **P3009** 拒绝执行此后所有迁移。

## 机制

- 每个迁移执行成功 → `_prisma_migrations` 写一行（`migration_name` + `finished_at`）
- deploy 时逐条比对：账本里没有的才跑
- 某条迁移执行失败 → 标 failed → 之后所有 deploy 直接报 P3009（防半个库的状态被继续往上叠）

## 典型事故链（实验室准入考试 2026-09-18 实例）

1. 手工 ALTER 加了列（或库本来就是 db push / SQL 导入铺的底）→ 功能正常
2. 但 `_prisma_migrations` 没记（甚至**整张表为空**）→ 无人察觉
3. 下次发版跑 `migrate deploy` → 从第 1 条迁移开始重放 → `表已存在`/`Duplicate column`
4. P3009 卡死 → 新功能需要的字段补不上 → 上线即 500

## 处置

| 场景 | 命令 |
|---|---|
| 手工执行过某条迁移的 SQL，补登记 | `npx prisma migrate resolve --applied <迁移名>`（只写登记，不动表） |
| 迁移执行失败想重跑 | `npx prisma migrate resolve --rolled-back <迁移名>` 后重新 deploy |
| 整库铺底非 migrate 建的 | 对**全部**历史迁移逐条 resolve --applied（实验室项目 2026-09-18 对正式库补了 8 条） |

## 判读与自检

- 查证一句 SQL：`SELECT migration_name, finished_at FROM _prisma_migrations ORDER BY started_at;`
- resolve 补录的时间戳=执行时刻（全同一时间簇），migrate 正常跑的时间戳=各迁移原始执行时间——**可用时间戳区分"补录"与"真跑"**，也可用来判断是否误连了别的库
- 补录行 `applied_steps_count = 0` 属正常，只看有没有这一行
- 发版前置检查：`_prisma_migrations` 计数应等于 `prisma/migrations/` 目录数

## 红线

- resolve --applied 前**确认目标库**（`SELECT DATABASE();`）——连错库会把登记写到错误的库上
- 只为让 deploy 通过而**真跑**历史迁移 SQL = 撞"表已存在"，绝不这么做
- 手工交付 SQL 不得硬编码 `USE 库名;`（用 `DATABASE()` 校验当前库）

出处：[[lab-exam-2026-09-18-prod-500-audience-migration-missing]] §八 §九
