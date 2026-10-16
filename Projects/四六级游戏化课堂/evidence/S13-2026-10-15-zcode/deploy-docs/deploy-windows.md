# 四六级游戏化课堂 — Windows 试点部署说明（S13）

面向运维/信息老师。**交付方式**：源码 + `deploy/` 目录（脚本会自动把编译产物落到 `D:\cet46-pilot`）。
试点机 = 长期开机、学生手机与教师电脑可通过局域网访问的那台 Windows 机器。

## 0. 一页速览

| 项 | 值 |
|---|---|
| 部署根目录 | `D:\cet46-pilot` |
| 访问入口 | 学生端 `http://<本机IP>/s`、教师端 `http://<本机IP>/t` |
| 后端 | `D:\cet46-pilot\server\cet46-server.exe`，端口 **8090**（开发验收环境用 8080，两套并存） |
| 前端 | `D:\cet46-pilot\web-dist`（Nginx 同源托管，`/api` 反代 8090） |
| 数据库 | 现成 MySQL 8 上的 `cet46_pilot` 库 + 专用账号 `cet46_pilot`（口令随机） |
| 备份 | 每日 03:00 mysqldump → `D:\cet46-pilot\backup`，保留 30 天 |

## 1. 交付物清单

```text
D:\cet46-pilot\
  server\cet46-server.exe        后端服务（启动时自动迁移建表）
  server\.env                    试点配置（随机口令/密钥，不进 git）
  bin\migrate.exe                建表（幂等）
  bin\seed-teacher.exe           建/重置教师与校级账号
  bin\import-users.exe           班级名单导入
  bin\qbank.exe                  题库导入（与 API 同 service）
  web-dist\                      前端产物（index.html / s.html / t.html / teacher-training.html）
  scripts\01..09*.ps1           初始化 / 构建 / 灌数据 / 备份 / 恢复演练 / 启停
  docs\nginx.windows.conf        Nginx 反代配置（并入 nginx.conf 的 http 段）
  docs\teacher-training.html     教师 30 分钟培训页（同一份也放进 web-dist，教室电脑直接开）
  docs\pilot-walkthrough.md      真机走查清单（验收③：iOS/Android 各走完一关，含防火墙前置条件）
  docs\deploy-windows.md         本文件
  data\真题题库-140题.csv        真实题库导入源
  data\班级学生导入模板.xlsx     名单模板（名单列：班级,学号,姓名,初始密码）
  backup\  logs\  sql\           备份、日志、建库脚本与秘密（均在部署根目录，不进 git）
```

源码仓库侧同名资产：`deploy/scripts/*.ps1`、`deploy/nginx.windows.conf.example`、`deploy/pilot.env.example`、`deploy/sql/000_mysql_init.sql`。

> `deploy/sql/000_mysql_init.sql`（公司现成 MySQL 的手工建库建号路径）里的口令是占位串 `__CT46_STRONG_PWD__`，**必须先换成随机强口令再执行**；照抄占位串或任何示例值上线等同默认口令，违反 §4.5 铁律。走 `01-init-db.ps1`（推荐路径）时口令由脚本随机生成，无须手工替换。

## 2. 前置条件

1. **MySQL 8**（现成实例即可，试点用 3306）：本机已装 MySQL 8.4（Windows 服务 `MySQL84`）。需要 root 口令做一次性建库建号。
2. **Nginx for Windows**（解压即用，不需要管理员）：
   - 下载 `https://nginx.org/download/nginx-<version>.zip`，解压到 `D:\cet46-pilot\nginx\`；
   - 把 `docs\nginx.windows.conf` 的内容并入 `D:\cet46-pilot\nginx\conf\nginx.conf` 的 `http { ... }` 段内；
   - 校验配置：`cd D:\cet46-pilot\nginx && nginx.exe -t`（应用配置用 `nginx.exe -s reload`）。
3. **权限**：
   - 编译、建库、起服务、注册备份任务：**普通权限即可**；
   - 放行防火墙（让学生手机能访问 80 端口）与「无人登录也运行」的计划任务：**需要管理员**，一次性。
4. **端口**：80（Nginx）、8090（试点后端）。开发验收环境用的是 8080/3307，两者不冲突。

## 3. 首次部署（五步）

在源码仓库 `D:\claude-work\cet46-game` 下执行（Git Bash 或 PowerShell 均可）：

```powershell
# ① 编译产物并落到部署根目录（Go 二进制 + 前端 build）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\02-build-and-stage.ps1

# ② 建试点库与专用账号（会提示输入 MySQL root 口令；生成随机口令与 SECRET_KEY）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\01-init-db.ps1

# ③ 建 17 张表 + 建账号（校级 admin / 任课教师，口令取 ② 生成的一次性值）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\03-migrate-and-seed.ps1

# ④ 灌真实班级名单与真题题库，并打印对拍
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\04-import-real-data.ps1 `
  -RosterPath D:\cet46-pilot\data\真实名单.csv

# ⑤ 起服务（后端 + Nginx）并健康检查
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\08-start-pilot.ps1
```

预期：② 输出 `pilot_db_init` 成功并生成 `D:\cet46-pilot\初始口令-移交后删除.txt`；③ 输出 `tables=17`；④ 输出 `questions_total 140`、`empty_stem 0`、`empty_answer 0`；⑤ 输出 `/api/health → {"code":0,...}` 与局域网访问地址。

**口令分发（铁律）**：初始口令是一次性随机值，只写在 `初始口令-移交后删除.txt` 里，交给任课教师后**立即删除该文件**；所有账号首次登录强制改密。生产环境禁止使用默认口令。细则见 §4.5。

### 3.1 整库复位（试运行前清洁 / 试跑搞脏后重来）

```powershell
# 交互确认（要输 yes）；脚本化执行加 -Force。不需要 root。
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\10-reset-pilot-data.ps1 -Force
```

动作串一遍首次部署：停服 → 重建空库 → 03 建表建账号 → 04 灌名单题库 → 起服 → 对账。
复位后的标准态：表 17 · 员工账号 2 · 学生 41 · 班级 1 · 题库 140 · 答题 0 · 流水 0 · 43 个账号全部「初始口令待改」。
实录：`logs\reset-<时间戳>.txt`。**历史数据全丢**，所以平时别拿它当清理学生练手数据的开关。

## 4. 上线后验证

1. `GET /api/health` 返回 `code=0`；
2. 手机/电脑打开 `http://<本机IP>/s` 出现学生端登录页；`/t` 出现教师端登录页；
3. 教师账号登录后强制改密，改密后进入看板；
4. 看板能看到真实班级（`2024级英语1班`）与人数；
5. 地图页能进第 9/10/11 周单元，五关链路可点开；
6. 进一关答题 → 结算，XP 入账（账本）；重打不重复发通关奖励；
7. 课中实时大屏 `/t/live` 在答题时数字会动（刷新间隔 = `LIVE_REFRESH_SECONDS`，缺省 10s）；
8. 学生端请求 `/api/admin/*` 返回 403（学生端零出口）。

## 4.5 生产初始口令与首次登录强改（S13 必闭环）

**为什么不设固定初始口令**：固定值（如 `admin123`）在校园网里等于没有口令——试点机开着 80 端口，
谁都能试出来。所以初始口令一律是**随机生成的一次性值**，用完即废。

| 对象 | 口令怎么来 | 发给谁 | 强制改密 |
|---|---|---|---|
| 校级 admin / 任课教师 | `01-init-db.ps1` 用 `RandomNumberGenerator` 生成 15 位（12 随机 + `9aZ` 保证含字母数字），落在 `sql\pilot_secrets.json` 与 `初始口令-移交后删除.txt` | 当面/电话告知本人 | 是：首次登录必须先改密 |
| 学生（41 人） | 建名单时每人一条互不相同的 10 位随机口令，落在 `data\学生初始口令-分发后删除.csv` | 打印/裁成纸条发本人，或当场发链接让学生自取 | 是：同上 |

**机制**：初始口令的哈希带 `init$` 前缀（复用 `pwd_hash`，零 schema 改动）。服务端据此判定
「这个账号还没改过密」：`POST /api/auth/login` 照常成功并回 `mustChangePwd:true`，
但**除改密接口外的一切业务接口一律 403 `40302 首次登录须先修改初始密码`**——
不改密就拿不到看板、地图、题库，所以「默认口令能长期用」这条路在服务端就没有出口。
改密用 `POST /api/auth/chpwd {oldPassword,newPassword}`，改完旧令牌立即作废（要重新登录）。

**分发后必做两件事**：
1. 删除 `初始口令-移交后删除.txt` 与 `data\学生初始口令-分发后删除.csv`（口令是本机唯一明文副本）；
2. 复核「重置为初始态」是否生效：登录任一员工账号应看到改密页，直连业务接口应得 40302。

**重置成初始态**：`03-migrate-and-seed.ps1` 可重跑，它会把 admin/教师口令重置回
`pilot_secrets.json` 里的一次性值（`seed-teacher` 幂等：已存在则重置密码并确保角色）；
整库复位（§3.1）也是同一效果。任课教师忘记自己改过的密码时，运维用这条路径帮他重置为一次性值再当面告知——
注意**不要**用它在生产里造一个长期口令。

**别做的两件事**：① 不要在 `.env`、文档、群公告里写任何口令；`sql\pilot_secrets.json` 留着是因为
运维还要靠它重置，但它等同于口令本，别外发。② 不要把 `server\.env` 与 `pilot_secrets.json` 提交进 git
（任务书 §3 铁律 6：凭证不进仓库）。

## 5. 每日备份与恢复演练

```powershell
# 注册「每日 03:00」计划任务（普通权限即可；登录状态下才会跑）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\06-register-backup-task.ps1

# 无人登录也要跑（SYSTEM 身份）——需要管理员 PowerShell 执行这一条
schtasks /Create /TN cet46-pilot-daily-backup-0300 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"D:\cet46-pilot\scripts\05-backup-db.ps1\"" /SC DAILY /ST 03:00 /RU SYSTEM /RL HIGHEST /F

# 手工试跑一次备份（验证脚本）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\05-backup-db.ps1

# 恢复演练（默认 InPlace：停服 → 干净库恢复 → 起服 → 计数比对 → 写实录）
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\07-restore-drill.ps1
# 只抽查不动在线库：加 -Mode Scratch
```

- 备份产物：`D:\cet46-pilot\backup\cet46_pilot-<时间戳>.sql`，自动删除 30 天前的旧备份；日志 `logs\backup.log`。
- 恢复演练实录：`logs\restore-drill-<时间戳>.txt`（含备份文件名与大小、恢复前后计数、健康检查结果）。
- 演练需要 MySQL root 口令（重建库用），交互输入、不落盘。

## 6. 部署级配置盘点（一个不能漏）

| 配置 | 落点 | 值 / 说明 |
|---|---|---|
| `HTTP_PORT` | `server\.env` | 8090（与开发 8080 分开） |
| DB DSN | `server\.env` | `cet46_pilot` @ 127.0.0.1:3306，专用账号 + 随机口令 |
| `SECRET_KEY` | `server\.env` | 64 位随机（缺了服务拒绝启动；改它 = 全部登录态失效） |
| `LIVE_REFRESH_SECONDS` | `server\.env` | 10（S11 D7 部署级拍板；非正值自动回落 10） |
| 联赛结算 cron | 服务内置 | 每周日 23:00（`robfig/cron`），无需外部配置 |
| 备份 cron | Windows 计划任务 | 每日 03:00，保留 30 天（无人登录跑需 SYSTEM 身份，见 §5） |
| 速度加成限幅 | 服务内置（无开关） | 客户端上报耗时不得小于服务端观测窗口（宽容 2 秒），差多少按条摊回来；S13 到期结论，见 §6.1 |
| 前端 API base | Nginx 同源 | `/api` 反代 8090；**不开 CORS**（前后端同源） |

### 6.1 速度加成信任客户端 elapsedMs 的到期结论（S13 必闭环）

**背景**：速度加成读客户端上报的 `elapsedMs`（`10 × (1 − 单题耗时/单题限时)`，夹到 0~10）。
客户端可以把它报成 0 → 每题白拿满 10 分。S3 曾拍板「保持原型语义，S13 部署前再评估是否限幅」。

**结论：限幅（`ClampElapsedMsBatch`）**。服务端没有单题秒表，上报值是唯一信息源，不能丢；
但服务端能自己量出一段时间窗——**同一 attempt 里，本批作答和上一次落库之间必然隔了这么久**。
于是：窗口减去 2 秒宽容（网络往返 + 渲染 + 秒表起止点差异）作为上报值总和的底，缺口按条摊回来。

- **为什么是「按批」而不是逐条**：真机一题一交（`QuizView` 每题一个请求），条数 = 1，
  规则退化成「把这条抬到窗口」；而一次整关提交的脚本一进来条数 = n，
  逐条抬会把「7 题各 8 秒」这种诚实上报也判成 0 分（单题窗口无从观测，只有总窗口可信）。
- **诚实上报一字不改**：实测窗口与上报的落差在百毫秒量级，2 秒宽容给足余量。
- **没上报（`elapsedMs` 缺省）与负数**：不抬也不摊派，仍按 0 速度分——那是「没数据」，
  不是「很快」，硬编一个数字等于替学生编造耗时。
- **留痕**：命中限幅写服务端日志 `[速度限幅] attempt#N 观测窗口 Xms，本批 K 条上报合计不足，共抬 Yms`
  （`logs\server.err.log`）。**不写 audit_log**：那是给学生和老师看的操作留痕表，秒答刷分属于个别现象，
  每条都记会把审计表读成噪声。
- **代价**：限幅只能拦「物理上不可能」的谎报——一关的窗口如果是 6 秒而单题限时 68 秒，
  报 0 依然拿得到速度分，因为那 6 秒是真的。它拦的是「磨了 55 秒却报 0」这类，够用。

## 7. 升级部署

```powershell
# 仓库拉到新版本后：
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\02-build-and-stage.ps1   # 重新编译
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\09-stop-pilot.ps1       # 停服
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\scripts\08-start-pilot.ps1       # 起服（自动迁移新表）
```
数据库结构变更由服务启动时的迁移负责（幂等可重跑）；升级前建议先手工跑一次备份。

**升级要留意的两类时间**（都是迁移在启动时干的活，服务要等它做完才开始监听）：

1. **建表/加列**：几毫秒级，无感。
2. **建索引**（如 S13 这次给 `xp_ledger` 补的三个索引）：要在启动时把整表扫一遍。
   试点库 5.8 万行约 0.3 秒/个；按学期末的流水量估（几十万行）也就是秒级，
   但**别在课堂进行中升级**——迁移期间服务没起来，学生端会取不到卷。
   判断依据看 `logs\server.log` 启动段里的 `CREATE INDEX ...` 行与 `SLOW SQL` 提示。

## 8. 常见问题

- **手机打不开页面**：① 手机与试点机是否同一局域网（同 WiFi）；② 防火墙是否放行 80 端口（管理员执行：`netsh advfirewall firewall add rule name="cet46-web" dir=in action=allow protocol=TCP localport=80`）；③ Nginx 是否在跑（`Get-Process nginx`）。
- **80 端口被占用**：`netstat -ano | findstr :80` 看占用进程；被 IIS/别的服务占用时，改 `nginx.windows.conf` 的 `listen` 端口并同步告知访问地址。
- **后端起不来**：看 `logs\server.err.log`。常见原因：`SECRET_KEY` 为空（服务拒绝启动）、库连接信息不对、8090 被占。
- **别把试点库当开发库**：开发验收环境是 3307 上的 `cet46` + 8080 上的服务；试点是 3306 上的 `cet46_pilot` + 8090。两者数据互不影响，历代验收夹具留在开发库作活证据。
- **名单导入有坏行**：整份不落库并给出行号清单（S1 口径：只导一半比失败更糟），修好文件重跑即可。

## 9. 日志与产物位置

| 内容 | 位置 |
|---|---|
| 后端 stdout / stderr | `logs\server.log` / `logs\server.err.log` |
| 备份日志 | `logs\backup.log` |
| 恢复演练实录 | `logs\restore-drill-*.txt` |
| Nginx 日志 | `nginx\logs\access.log` / `error.log` |
| 备份文件 | `backup\cet46_pilot-*.sql` |