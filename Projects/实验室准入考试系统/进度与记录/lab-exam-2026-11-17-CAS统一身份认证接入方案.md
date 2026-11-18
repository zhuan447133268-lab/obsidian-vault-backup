# CAS 统一身份认证接入方案（2026-11-17）

> 来源：已读完两个参考仓库 —— ① `https://git.oceghome.com/aiproject/ai-coding`（main `金智统一身份认证skill` + `pcz` `cas-auth` 全套 references 与 `go-scaffold/10-login-integrations.md`）；② `https://git.oceghome.com/aiproject/student`（实习管理系统，**本校已在生产跑的 CAS+钉钉 实现**，main/`test` 双分支已读，CAS 相关提交史已逐条看过）。并对照本仓库 `D:\01-项目\2026准入题库-main`（main = `b234d9c`）真实代码逐处定位。
> 目的：解决「学生总忘密码、要老师重置」——把密码保管责任交回学校统一身份认证。
> **v2（2026-11-17 晚）**：读 `student` 项目后重写。多处设计被实证推翻（`<cas:user>` 不是学号、`service` 不能带 query、必须带 `appId/appSecret`），最终方案以 `student` 为骨架 + 本仓库的安全交接方式。

---

## 一、结论先行

1. **`student` 项目的做法更适合我们，直接拿它当蓝本**。它是本校生产系统，踩过的坑都有日期和提交号，比通用模板值钱。三处关键实证：
   - `<cas:user>` 返回的是 **14 位集成账号，不是学号**（`cas_service.go:129-148`），必须用 CAS 属性里的学号/工号回退匹配 —— 我上一版方案「uid 就是学号/工号」的假设**是错的**；
   - `service` 带 query 会被 CAS 判「应用未注册」（`auth_handler.go:123-125`，**2026-10-15 实测**）——所以 ai-coding 参考实现里 `buildServiceUrl` 拼 `?redirect_uri=` 的写法**在本校会直接失败**，回跳路径必须走 cookie；
   - 验票请求要带 **`appId` + `appSecret`**（`cas_service.go:24-35`、`config.example.yaml`），金智新版 Minos 注册的应用要校验，不带会被拒。
2. **能接，而且零迁移**：`users` 表从第一版迁移起就有 `cas_user_id` / `dingtalk_user_id` 两个唯一列（`schema.prisma:76-77`、`migrations/20260708014852_init/migration.sql:45-46,60-61`），全代码零引用。只需发版前 `SHOW COLUMNS` 复核正式库有这两列。
3. **接完之后的体验**：学生从钉钉工作台点链接 → 302 到学校 CAS → 浏览器里已有统一认证会话时**零输入直接进考试**（gateway 静默探测），没有会话输一次学号+统一密码。忘记密码走学校自助找回，**老师再也不需要重置密码**。
4. **必须保留账号密码登录做兜底**。`student` 敢在 2026-10-30 把学生密码入口整个下线（`e19db1f`），前提是它有 **CAS + 钉钉免登两条零输入通道**；我们本期只有 CAS 一条，authserver 一挂就全校考不了试，所以**本期保留密码兜底**，等钉钉免登也上了再谈下线。
5. **代价**：多一个外部依赖和一次 302（首屏多 1–2 秒）；学生端登录质量从此取决于 authserver 可用性。

---

## 二、两个参考仓库的硬事实（照抄，别自己猜）

### 2.1 金智 CAS 基础设施

| 项 | 值 |
|---|---|
| CAS 服务前缀 | `https://authserver.hcc.edu.cn/authserver` |
| 登录页 | `https://authserver.hcc.edu.cn/authserver/login` |
| 验票地址 | `https://authserver.hcc.edu.cn/authserver/serviceValidate` |
| 验票 query | `?service={service_url}&ticket={ticket}`（`student` 额外带 `appId`+`appSecret`） |
| 应用登记 | 金智 Minos 管理控制台，前端有 bug，当前需**找大峥哥**人工加；登记时要提供系统 URL |

**必须遵守的细则**

1. 验票路径是 `/serviceValidate`，**不是** `/cas/serviceValidate`（写错 404）。
2. `service` 必须与 CAS 侧登记**逐字符一致**；`student` 实测：**service 带 query 参数会被判「应用未注册」**，所以 service 只能是纯净的回调 URL，回跳目标另存 cookie。
3. ticket **一次性**：回调页刷新必然失败，要给「重新登录」而不是 500。
4. 验票 HTTP 必须设超时（`student` 用 10s），否则 authserver 卡住会拖住我们的请求。
5. `appId`/`appSecret`：金智新版要求，配在服务端 env，**不要出现在前端**。
6. 反代后 TLS 在 nginx 终结：推断对外地址时必须优先取 `X-Forwarded-Proto`，否则 service 会算成 `http://` 被 CAS 拒收（`auth_handler.go:229-238`）。

**两个参考仓库共有的架构原则**

> CAS 只负责证明「你是谁」（uid）；角色、学院、班级、考试资格一律查本系统自己的表。

参考项目曾用 CAS 属性猜校区，把校区标错，导致老用户必须清缓存重登。本项目**绝不按 CAS 属性写业务字段**，只有姓名可以用于「一致性校验」（见 6.4）。

---

## 三、`student` 项目到底怎么做的（逐条实证）

> 仓库路径：`server/internal/service/cas_service.go`、`server/internal/handler/auth_handler.go`、`server/cmd/server/main.go`、`pkg/config/config.go`、`config.example.yaml`、`frontend/src/utils/cas.ts`、`frontend/src/views/Login.vue`、`frontend/src-mobile/views/Login.vue`。main 与 `test` 分支的 `cas_service.go` 内容一致。

| # | 做法 | 证据 | 我们该不该抄 |
|---|---|---|---|
| 1 | `GET /cas/status` 返回 `{enabled, serverUrl}` | `auth_handler.go:106-112` | 抄 |
| 2 | `/cas/login?redirect_uri=&gateway=`：`redirect_uri` 存 cookie（600s，path 限定 `/api/v1/cas`），**不拼进 service**；`gateway` 原样透传给 CAS | `:115-138` | 抄（cookie 改 httpOnly） |
| 3 | `/cas/callback?ticket=`：ticket 为空**不报错**，直接回首页（gateway 空手回的场景） | `:145-151` | 抄 |
| 4 | 验票成功后按角色跳 `/admin/` 或 `/m/`，`token/userId/name/role/org` **拼在 URL query** | `:175-199` | **不抄**（见第四章） |
| 5 | 失败 302 回登录页并带 `?cas_error=` 文案；`redirect_uri` 只收站内相对路径（拒 `//`） | `:202-218` | 抄 |
| 6 | 路由别名 `/api/cas`、`/api/v1/auth/cas` 同时挂（防 Minos 登记 typo 改不动） | `main.go` | 抄 |
| 7 | 登录成功/失败都写操作日志，失败时附 **CAS 属性摘要**（业务属性优先、单值 50 字、整行 400 字上限） | `oplog_service.go:273-285`、`cas_service.go:84-117` | 抄（我们只打结构化日志，不建表） |
| 8 | `<cas:user>` 先按系统账号查；查不到再按属性 `学号/xh/工号/gh/学工号/班号/studentNo/employeeNumber…` 查，**且姓名必须与目标账号一致**，否则跳过 | `cas_service.go:124-149` | **必须抄** |
| 9 | **不自动建档**：花名册里的学生导入时已建号，CAS 查不到的号（14 位教育号/其他年级号）自动建档只会产生「未分班」垃圾档案（2026-10-29 学校要求） | `cas_service.go:119-123,150-152` | 抄（我们本就如此） |
| 10 | 登录后用 CAS 属性回填 `real_name` / `org_name`（仅当不同才写） | `cas_service.go:153-170` | 部分抄：只回填姓名，**不回填学院/班级**（那是我们业务数据，不能给 CAS 改） |
| 11 | 静默登录：隐藏 iframe 打开 `/cas/login?...&gateway=true`，`onload` 读同源 `?token=` 落地页；兜底 200ms 轮询 localStorage；**4000ms 超时** | `frontend/src/utils/cas.ts:55-113` | **必须抄**（判定方式改，见第七章） |
| 12 | `just_logout` 标记：本地退出后跳过静默探测，否则会被 CAS 会话**自动登回去**（点了退出等于没退） | `utils/cas.ts:8-18`、`Login.vue` | **必须抄** |
| 13 | 登录页把 `casEnabled` 缓存进 localStorage 先渲染按钮；`casStatus` 失败 1500ms 后重试一次 | `src-mobile/views/Login.vue:56-80` | **必须抄** |
| 14 | 钉钉 UA 分支走免登，**必须带 9s 超时**（`dd.ready` 异常时可能永不回调，页面卡住连 CAS 按钮都不出现） | `src-mobile/views/Login.vue:82-86` | 抄超时兜底（免登本期不做） |
| 15 | 2026-10-30 学校要求**下线学生学号密码登录**：理由「统一初始密码 123456 人人皆知，密码入口可冒用任意学生身份（登录即全部学生数据）」 | commit `e19db1f` | **本期不下线**，但这条直接指向我们的安全洞（见 8.3） |
| 16 | 无 CAS 单点退出（`/cas/logout`），只本地登出 + `just_logout` 标记 | `main.go` 无该路由 | 抄 |

**`student` 的每个坑都对应一次事故/一次学校要求**，所以它的形状不是「一个参考实现」，而是「本校 authserver 的实测手册」。

---

## 四、两个参考仓库的差异与取舍

| 议题 | `ai-coding`（模板） | `student`（本校生产） | 我们采用 |
|---|---|---|---|
| service 构造 | 拼 `?redirect_uri=` 进 service | service 纯净，redirect 走 cookie（2026-10-15 实测带 query 判未注册） | **student** |
| 验票参数 | `service`+`ticket` | 额外 `appId`+`appSecret` | **student** |
| uid 含义 | 假设是工号 | 14 位集成账号 + 属性回退 + 姓名校验 | **student** |
| 登录态交接 | token 拼 URL → 前端存 localStorage | 同（`?token=`） | **都不采用**：httpOnly cookie + 302 到 `/login?cas=1`，前端 `/auth/refresh` 换 CSRF |
| 静默登录 | 只提「必须留兜底表单」 | iframe+gateway 完整实现 + 超时 + just_logout | **student** |
| 自动建号 | 有 `cas_default_role` 自动建号选项 | 明确禁止 | **student**（我们业务上也不允许） |
| CSRF | 无（bearer） | 无（bearer+localStorage） | **保留我们的 CSRF**（cookie 模式必须有） |
| 验票限流 | 未提 | 未见 | **保留我们的**（按 CAS uid 10/5min） |

**一句话**：骨架抄 `student`，凭据交接抄我们自己。

理由：`student` 的 `?token=` 方案对我们不可接受 —— 我们的 token 是 httpOnly cookie + CSRF 双件套，URL 里出现任何凭据都会进浏览器历史、Referer、nginx access log；而他们的 bearer token 存 localStorage 本身就有 XSS 面。我们把 URL 交接换成「回调只种 cookie → 302 `/login?cas=1` → 前端 `/auth/refresh`」，安全上严格更优，且**不影响静默探测**（见 7.2）。

---

## 五、本项目现状（代码事实，接入点定位到行）

| 关注点 | 现状 | 位置 |
|---|---|---|
| 登录 | `POST /api/auth/login`，账号查 `studentNo`/`staffNo`，bcrypt 校验，`status=0` 拦 1005 | `server/src/modules/auth/auth.service.ts:39-124` |
| 会话签发 | `signAccessToken`（含 jti）+ `signRefreshToken`；cookie 模式回包带 `csrfToken` | 同上 `:79-123`、`:244-258` |
| Cookie 写入 | cookie 模式种 `access_token`/`refresh_token`（httpOnly + SameSite + Secure 由 env 控制） | `server/src/modules/auth/auth.controller.ts:42-50,117-135` |
| CSRF | 写操作由 `JwtAuthGuard` 校验 `X-CSRF-Token` = HMAC(jti) | `server/src/modules/auth/guards/jwt-auth.guard.ts:23,29-50` |
| 前端取 CSRF | cookie 模式登录回包存 sessionStorage；`/auth/refresh` 可换新 CSRF | `web/src/stores/auth.ts:112-131`、`web/src/api/request.ts:65-78,138-170` |
| 路由守卫 | 未登录 → `/login`；`needChangePassword` → 强制 `/change-password` | `web/src/router/index.ts:229-267`（改密 246-248） |
| 登录页 | 只有账号+密码表单；**onMounted 无条件 `clearToken()`** | `web/src/views/login/index.vue:12-39,57-59` |
| 用户表 | `name`（不是 realName）、`studentNo`、`staffNo`、`casUserId`、`dingtalkUserId`、`userType`(1教/2学)、`status` | `server/prisma/schema.prisma:74-107` |
| 配置 | 全走环境变量，无 `sys_config` 表；必填项由 `validateEnv()` 卡 | `server/src/config/index.ts`、`validate-config.ts:3-9` |
| 代理 | `app.set('trust proxy','loopback')`（够用，见 6.2） | `server/src/main.ts` |
| 限流 | `ThrottleGuard` 支持 `keyBy: user/account/ip`，按 ip 会退化成全站共享 | `server/src/common/guards/throttle.guard.ts:164-186` |
| 应急账号 | `admin`（`studentNo='admin'`）是唯一能重置学校管理员密码的账号 | `server/src/common/constants.ts` |
| HTTP 客户端 | 服务端**没有 axios**，Node 20 自带 `fetch` 够用 | `server/package.json` |

---

## 六、服务端设计

### 6.1 配置（只加 env，不加表）

```ini
CAS_ENABLED=false                                          # 默认关，发版零行为变化
CAS_SERVER_URL_PREFIX=https://authserver.hcc.edu.cn/authserver
CAS_LOGIN_PATH=/login
CAS_VALIDATE_PATH=/serviceValidate
CAS_SERVICE_URL=https://lab-exam.oceghome.com/api/auth/cas/callback   # 测试环境填 lab-exam-test...，硬配
CAS_APP_ID=                                                # 金智分配，空则不传
CAS_APP_SECRET=                                            # 金智分配，空则不传
CAS_ATTR_UID=userName                                      # 实测后定
CAS_ATTR_NAME=realName
CAS_ATTR_STUDENT_NO=学号                                    # 实测后定，逗号分隔多候选
CAS_ATTR_STAFF_NO=工号
```

- **不要**把 CAS 变量加进 `validate-config.ts` 的 `REQUIRED_ENVS` —— 否则所有存量部署（含 Jenkins 测试环境）会因缺变量启动失败。
- `CAS_SERVICE_URL` **硬配而不是按请求推断**：`student` 用 `schemeHost()` 推断是不得已（它要在多域名下跑），我们只有固定域名，硬配能彻底消除「service 差一个字符」这一整类故障。若留空则退回 `X-Forwarded-Proto` + Host 推断，并复用 `student` 的写法。

### 6.2 三个接口（挂在 `AuthController` 下，不加新模块）

| 路由 | 作用 | 要点 |
|---|---|---|
| `GET /api/auth/cas/status` | 前端判断是否显示「统一身份认证登录」 | 返回 `{ enabled }`；缓存进 localStorage 先渲染 |
| `GET /api/auth/cas/login?redirect=/student&gateway=true` | 302 到 CAS | `service` **固定**为 `CAS_SERVICE_URL`（纯净，无 query）；`redirect` 存 httpOnly cookie `cas_redirect`（600s、SameSite=Lax、path 限定 `/api/auth/cas`），只收站内相对路径 `^/(?!/)`；`gateway` 原样透传 |
| `GET /api/auth/cas/callback?ticket=ST-xxx` | 验票 → 建会话 → 302 回前端 | ticket 为空 → 302 回 `/login`（gateway 空手回，不报错）；验票带 `appId/appSecret`、10s `AbortSignal.timeout`；命中后种 cookie，302 到 `/login?cas=1` |

**同时挂路由别名**（照 `student`）：`/api/cas/*`、`/api/auth/*` 之外再加 `/api/v1/auth/cas/*` —— Minos 登记一旦路径写错，改登记要找金智人工处理，别名能自救。

**会话交接：不把 token 或 CSRF 放进 URL。** 回调只写 httpOnly cookie，然后 302 到 `/login?cas=1`；前端落地页调 `POST /api/auth/refresh` 拿新 `csrfToken`（cookie 模式 refresh 本来就返回它），再 `/auth/me`。
（bearer 模式仅供本地调试，可临时走 `?token=` 交接；生产 `AUTH_MODE=cookie`，不需要这条路径。）

### 6.3 会话签发复用（唯一需要重构的地方）

`auth.service.ts` 把 `login()` 里「密码校验之后」的 79–123 行抽成 `private buildSession(user)`，返回 `{ user: userInfo, accessToken, refreshToken, csrfToken, needChangePassword }`；
`login()` 与新增的 `loginWithCas(uid, attrs)` 共用它。

`loginWithCas` 的差异：

- `needChangePassword` 固定 `false`（CAS 用户没有本地初始密码，不该被拦到改密页）；
- 不碰 `passwordHash`。用户若同时有本地密码，本地登录仍按原逻辑强制改密。

`getMe` / `refresh` / `logout` **一行都不改**。

### 6.4 账号映射（唯一可能出事的地方，照抄 `student` 的两次查找 + 姓名校验）

```
1) 按 <cas:user> 查：OR [ casUserId = uid, studentNo = uid, staffNo = uid ]
2) 未命中 → 按属性里的学号/工号再查一次（候选键：学号,xh,工号,gh,学工号,班号,studentNo,staffNo,student_no,employeeNumber,jobNumber）
   命中后必须校验 姓名 相等（CAS 属性 realName/姓名/xm vs users.name），不等 → 跳过并记日志
3) 仍未命中 → 1604，文案带 CAS 账号原文
```

- 命中 `studentNo`/`staffNo` 且 `casUserId` 为空 → 回写 `casUserId = uid`。回写用条件更新 `WHERE id = ? AND cas_user_id IS NULL`；撞唯一索引（该 uid 已绑别人）→ **1604 + 日志**，绝不静默改绑。
- **姓名校验不能省**：双账号体系下（集成账号 vs 学号/工号）属性配错就会串号；`student` 的原话是「姓名对不上，不冒串号风险」。
- **`status = 0`** → 1005（前端已有全局「账号已被禁用」弹窗，无需新 UI）。
- **`admin` 不参与 CAS**：命中 `studentNo='admin'` 一律 1604。应急账号不能被外部认证接管。
- **不做自动开户**：本系统账号带学院/班级/角色，考试资格依赖班级名单（组卷按班取人），自动开户只会造出无班级的空账号。
- **不回填班级/学院**：`student` 用 CAS 属性回填 `org_name` 是因为它没有权威花名册；我们的学院/班级是导入时建好的业务数据，CAS 属性覆盖会破坏组卷取人。只允许「姓名不同则回填姓名」。

### 6.5 错误码（接在 15xx 段之后，避开已用的 1001–1510）

| 码 | 含义 | 用户侧表现 |
|---|---|---|
| 1601 | CAS 未启用 / 非 CAS 模式调用 | 按钮不显示，正常路径碰不到 |
| 1602 | 缺少或非法 ticket（含刷新回调页） | 登录页提示 +「重新登录」按钮 |
| 1603 | CAS 校验失败（XML 异常/authenticationFailure） | 同上，附 CAS 返回的原因 |
| 1604 | 认证通过但本系统无对应账号 / uid 绑定冲突 / 姓名不一致 | 提示联系学院管理员，显示 CAS 账号 |
| 1605 | CAS 服务不可达 / 超时 | 「统一身份认证暂不可用，请用账号密码登录」 |

### 6.6 限流（不做就是新的 #35）

- 回调**不能** `keyBy: 'ip'`：经 nginx 后全站共用 `127.0.0.1`（2026-11-10 事故，[[避坑指南]] #35）。
- ticket 一次性本身防重放；真正的风险是「同一 CAS 账号被反复建会话」→ 用 `RedisService` 做 `cas:login:{uid}` 计数，10 次 / 5 分钟，超限 1009。
- `/cas/login`、`/cas/callback` 本身是廉价 302，不额外限流。

### 6.7 可观测性（照 `student` 补，上一版漏了）

CAS 接进来之后，「昨天能登今天登不上」这类问题**只能靠登录日志查**。我们已有 NestJS Logger，不建表：

- 每次回调记一条：`uid`、命中方式（casUserId / studentNo / staffNo / attr:学号 / miss）、user.id、`status`、耗时、ticket 前 6 位；
- **失败时附 CAS 属性摘要**：业务属性排前（姓名/学号/工号/班号/学院），认证噪音（`authentication*`/`saml*`）后排，单值截 50 字、整行截 400 字 —— 这是定位「属性名跟预期不一样」的唯一手段；
- **ticket 不落全文**。

### 6.8 安全清单

- `redirect` 只收站内相对路径，拒 `//evil.com`、`https://...`（照 `student` `normalizeCasRedirect`）；
- `cas_redirect` cookie：**httpOnly**（`student` 这里是非 httpOnly，我们收紧）+ SameSite=Lax + 600s + Secure（生产）+ path `/api/auth/cas`；
- 验票 `AbortSignal.timeout(10_000)`，失败统一 1605/1603 并回登录页，**不抛 500**；
- XML 解析：长度上限 2MB + 正则取 `<cas:user>` / `<cas:attributes>` 子项（与两个参考实现一致）；不引 XML 库，避免 XXE；
- `appSecret` 只在服务端，日志脱敏。

---

## 七、前端设计

### 7.1 登录页（照 `student` 的渲染策略）

1. **双模式**：默认「统一身份认证登录」主按钮 + 下方「使用账号密码登录」切回现有表单（现有表单与 `loginAction` 一行不改）。
   ```ts
   window.location.href = `/api/auth/cas/login?redirect=${encodeURIComponent(route.query.redirect as string || authStore.homePath)}`
   ```
2. `casEnabled` 从 localStorage 先读，接口回来再校正；`/cas/status` 失败 1500ms 后重试一次 —— 钉钉 WebView 往返慢，按钮不能等接口才出现。
3. **落地页 `/login?cas=1`**：必须**跳过** `login/index.vue:57-59` 的 `clearToken()`，改为：
   `refreshAction()` → 成功则 `fetchMe()` → `router.replace(redirect || homePath)`；失败显示「统一身份认证已通过，但会话建立失败」+ 重新登录。
4. `?cas_error=` 时 toast 展示后清掉 query（ticket 复用/未知账号就靠这条说人话）。
5. **强制改密**：CAS 用户 `needChangePassword=false`，不触发 `router/index.ts:246-248`。

### 7.2 静默登录（`student` 最值钱的一招，必须抄）

```
if (刚退出过 just_logout) 跳过
else 隐藏 iframe → /api/auth/cas/login?redirect=...&gateway=true
     4000ms 超时
```

差异点：`student` 靠 iframe 落到同源 `?token=` 页读 token，我们**没有 token 进 URL**，所以判定改成：

- iframe 内落回同源 `/login?cas=1`（说明 CAS 有会话、cookie 已种）→ 主线程调 `POST /auth/refresh`，200 即静默登录成功；
- 落到 `/login`（gateway 空手回）或超时 → 维持未登录态，显示按钮。

同源 iframe 内的顶层导航写 cookie 是允许的（不是第三方 cookie 场景），这点在测试环境必须实测确认。

### 7.3 退出登录（`just_logout` 不能省）

- 本地 `/auth/logout` 清我们的 cookie；**不清 CAS 的 TGT**（清了会把学生从门户一起踢出去）；
- 登出成功后写 `just_logout`（sessionStorage），登录页读到就跳过静默探测 —— 否则下次打开页面又会被 CAS 会话**自动登回去**，用户会认为「退出登录是坏的」。

---

## 八、钉钉工作台这条链路

1. 学生实际路径：钉钉工作台 → 点链接 → 钉钉内置浏览器 → 我们 302 到 authserver → 登录 → 回跳。CAS 是**顶层导航**，`SameSite=Lax` 允许顶层 GET 带 cookie，不是第三方 cookie 场景。
2. **必须真机实测三点**：① iOS 内置浏览器是否保留我们域名的 `Secure`+`Lax` cookie；② Android 是否拦截跨域 302；③ authserver 登录页手机端自适应。
3. 钉钉内若失败，**一律回落账号密码表单**，文案说人话（「当前浏览器无法使用统一身份认证，请用账号密码登录」）。
4. 任何分支都要有超时（`student` 的钉钉免登踩过 `dd.ready` 永不回调 → 整页卡住，连 CAS 按钮都不出现；`withTimeout(..., 9000)`）。

### 8.3 关于「下线学生密码登录」（本期不做，但要写进路线）

`student` 在 2026-10-30 按学校要求把学生密码入口整个下线，理由（commit `e19db1f`）：

> 统一初始密码 123456 人人皆知，密码入口可冒用任意学生身份（登录即全部学生数据）。

**这条对我们是一个安全问题，不只是体验问题**：我们学生初始密码也是 123456、学号连号可猜，任何人可以登进别人的账号参加考试 —— 远程考试没有监考，登录凭据是唯一的身份锚点。因此：

- 本期（只有 CAS 一条通道）**不能下线密码入口**，否则 authserver 故障=全校停考；
- 路线图：CAS 稳定 1–2 个考试周期 + 钉钉免登上线后，把学生端默认入口收敛到 CAS/钉钉，密码入口降级为「仅在 CAS 故障公告期内开放」；
- 在此之前可做的低成本缓解：考试开始前批量把未改密学生的 `needChangePassword` 保持为 true（现在是首次登录强制改密，已有一半效果）。

---

## 九、上线台阶

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| P0（1 天） | 后端三接口 + 别名 + `buildSession` 重构 + 单测（mock XML：成功/失败/超时/未知 uid/姓名不一致/禁用/`admin`/ticket 复用） | `npm test` 全绿；`CAS_ENABLED=false` 时行为与现在完全一致 |
| P1（0.5 天） | 测试环境开 `CAS_ENABLED=true`，Minos 登记测试域名，**先抓一次真实 XML 确认 `<cas:user>` 与属性名** | 能打印出 uid + 学号/姓名属性；判定清是集成账号还是学号 |
| P2（0.5 天） | 首次写 `cas_user_id`、二次命中、属性回退命中、姓名不一致拒绝、未知 uid 1604 五条全过 | 测试库有记录且能清回 |
| P3（0.5 天） | 前端按钮 + 落地页 + 静默探测 + just_logout + 钉钉 Android/iOS 各 1 台真机 | 真机走完「工作台 → 考试列表」；退出后重开不被自动登回 |
| P4 | 正式登记生产 URL，先 1 个学院灰度（教师+学生各若干），观察 30 分钟 | 5xx=0、1604 名单可解释、1009=0；再全量 |

**回滚**：`CAS_ENABLED=false` + 重新构建（或回旧镜像）。无迁移、无数据变更，回滚零风险。

---

## 十、验收不变量（照复盘的闸门 2）

1. CAS 首次登录后 `SELECT cas_user_id FROM users WHERE id=?` 非空且等于 CAS uid；
2. 同一 uid 二次登录：users 行数不变、`cas_user_id` 不变、不产生第二条会话；
3. 未知 uid：users 计数不变、响应无 Set-Cookie、返回 1604 且文案含 uid；
4. **属性回退**：`<cas:user>` 为集成账号时，能按属性学号命中正确账号并回写 `cas_user_id`；
5. **姓名不一致**：CAS 属性的学号指向 A、姓名与 A 不同 → 1604，**不写** `cas_user_id`、**不建会话**；
6. 禁用账号（status=0）：1005，且**不写** `cas_user_id`；
7. `admin` 走 CAS：1604；
8. 回调后 `document.cookie` 读不到 `access_token`（httpOnly 生效），`/api/auth/me` 200；
9. 刷新回调页（ticket 复用）：1602，且**不产生第二个会话**；
10. `CAS_SERVER_URL_PREFIX` 改成错误地址：10s 内返回 1605，登录页不白屏；
11. **静默探测**：已有 CAS 会话时打开 `/login`，4s 内自动进入且地址栏无 token；
12. **just_logout**：点退出 → 重新打开系统 → 停在登录页，不被自动登回；
13. `CAS_ENABLED=false` 回归：账号密码登录、强制改密、401 刷新链路全部与改前一致；
14. 钉钉 iOS + Android 真机各 1 台完成一次页面加载。

---

## 十一、需要外部配合的四件事（落地前必须先拿到）

1. **Minos 控制台登记应用**：测试 `https://lab-exam-test.oceghome.com`、生产 `https://lab-exam.oceghome.com`，回调路径 `/api/auth/cas/callback`。控制台前端有 bug，需找金智运维（大峥哥）人工添加。登记时**确认是否要 appId/appSecret，以及 service 是否必须完全一致**。
2. **`appId` / `appSecret`**（若需要）：向金智要，配到服务端 env。
3. **测试账号**：学生 1 个 + 教师 1 个（确认教师返 BN 工号，能对上 `staff_no`）。
4. **一次真实 `serviceValidate` 的 XML**：确认 `<cas:user>` 到底是学号还是 14 位集成账号、属性名到底是 `userName`/`realName` 还是 `xh`/`姓名`。**属性名进配置，不硬编码**。

---

## 十二、和 2026-08-12「不接 CAS」结论的关系

[[2026-08-12 CAS统一身份认证评估结论]] 当时拍板「不接」，五条理由里最核心的是「低频一次性使用，忘密码已有管理员重置 123456 兜底」。**这个前提在 2026-11 被现实推翻**：

- 「管理员重置」在考试窗口期是老师被反复打断，不是零成本；复盘里它的成本已经不是个案（[[labexam-student-login-1001-after-forced-change]]）；
- 更关键的是**安全面**：123456 + 连号学号 = 可冒用任意学生身份参加考试，这是 08-12 评估时没纳入考量的维度，而 `student` 项目已经因此被学校要求下线密码入口；
- `student` 项目证明本校 authserver 的 CAS 通道在生产稳定跑着（2026-10 多次实测），「外部依赖不可用」的风险从"未知"变成"可评估+有兜底"。

因此本方案取代 08-12 结论；08-12 文档保留为决策史，不删。

---

## 十三、关联

- [[2026-08-12 CAS统一身份认证评估结论]]（被本方案取代，保留为决策史）
- [[lab-exam-2026-11-17-上线后问题复盘与质量改进]]（闸门 1.2 环境同构、闸门 2 不变量）
- [[避坑指南]] #35（按 IP 限流的全局共享事故）
- [[待发版清单]]（本次接入不得混进待发的 `b234d9c` 批次）

---

## 十四、实现与本地端到端验收（2026-11-17 已落地，分支 `feat/cas-auth`，未提交未推送）

用户拍板：CAS 是**独立功能迭代**，与待发的 `b234d9c` bug 批次互不影响，最后统一发版。

### 14.1 代码落点（`D:\01-项目\2026准入题库-main`，分支 `feat/cas-auth`）

| 文件 | 改动 |
| --- | --- |
| `server/src/config/index.ts` | `cas` 配置块（enabled / serverUrlPrefix / loginPath / validatePath / serviceUrl / appId / appSecret / uidKeys / nameKeys / studentNoKeys / staffNoKeys / timeout） |
| `server/src/modules/auth/cas.service.ts` | 新增：`buildLoginUrl`、`resolveServiceUrl`（配了 serviceUrl 优先，否则按 X-Forwarded-* + originalUrl 推）、`validateTicket`（带 appId/appSecret + 超时 + 2MB 上限）、`parseUser` / `parseFailure` / `parseAttributes` |
| `server/src/modules/auth/cas.controller.ts` | 新增三接口，路由别名 `auth/cas`、`cas`、`v1/auth/cas` |
| `server/src/modules/auth/auth.service.ts` | 抽 `buildSession`；新增 `loginWithCas`（绑定 → 账号直配 → 属性回退+姓名校验 → 1604，不自动建档） |
| `server/src/modules/auth/auth-cookies.ts` | 新增：cookie 模式下种/清会话 cookie（登录与 CAS 回调共用） |
| `server/src/modules/redis/redis.service.ts` | 补 PX 选项/计数能力（CAS 限流 `cas:login:${uid}` 用，按 uid 不按 IP） |
| `web/src/utils/cas.ts` | 新增：`markJustLogout` / `readJustLogout` / `clearJustLogout`、`normalizeRedirect`、`casLoginUrl`、`silentCasProbe`、`reportProbeResult` |
| `web/src/views/login/index.vue` | 双模式（CAS / 账号密码）+ 落地页 + iframe 防递归 + 静默探测 |
| `web/src/stores/auth.ts` | `logoutAction` 落 `just_logout`；`loginAction` 成功清除 |

### 14.2 验收结果（本地起假金智 CAS 全链路真跑）

假 CAS（127.0.0.1:4010）+ 后端 `dist/main.js`（cookie 模式，:3000）+ 生产构建 `vite preview`（:4173），真实浏览器操作，截图 14 张存 `gui-test-screenshots/2026-11-17-cas-auth-e2e/`（该目录 gitignore）：

| # | 场景 | 结果 |
| --- | --- | --- |
| 01 | 登录页出现「统一身份认证登录」入口 | ✅ |
| 02 | 点进学校 CAS 登录页 | ✅ |
| 03 | 回跳到 `/student` 首页 | ✅ |
| 04 | 个人中心身份 = 王卫 / 学号 1802210231（属性回退 `matchedBy=attr:studentNo`） | ✅ |
| 05/07 | 退出登录后停在登录页；刷新也**不**被 CAS 会话自动登回 | ✅ |
| 06 | 静默登录：有 CAS 会话时零输入自动进 `/student` | ✅ |
| 08 | 未知账号 → 1604，提示带认证账号 | ✅ |
| 09 | 姓名不一致 → 1604 拒绝（不写入绑定） | ✅ |
| 10 | `admin` 系统账号 → 1604「请使用账号密码登录」 | ✅ |
| 11 | 禁用账号 → 1005 | ✅ |
| 12 | 教师工号回退（芦思雨 / B100013865）并回写 `cas_user_id` | ✅ |
| 13 | `CAS_ENABLED=false`：缓存 `cas_enabled=1` 时登录页自我纠正回密码表单，无 iframe 探测 | ✅ |
| 14 | 关闭 CAS 后账号密码登录仍正常进 `/student`（回归） | ✅ |

单测：`auth.cas.spec.ts` + `cas.service.spec.ts` 27 条；后端全量 **218/218（15 套件）全绿**；`web` 构建通过（入口 `index-CmH5fE3d.js`）。

### 14.3 本轮真跑出来的两个真 bug（**不是环境问题，是会直接导致"静默登录永久失效"**）

1. **静默探测 URL 少一个 `?`**：`web/src/utils/cas.ts` 里 `\`${casLoginUrl()}&gateway=true\``，而 `casLoginUrl()` 无参数时**不含** `?`，实际请求成 `/api/auth/cas/login&gateway=true` —— 后端把整串当成登录路径，探测永不触发。现象是"按钮能登、静默登录永远不进"。修复=按需拼 `?`/`&`（`probeUrl.includes('?') ? '&' : '?'`）。
2. **探测 iframe 把整个系统也渲染了一遍**：iframe 落到 `/login?cas=1` 后 `enterAfterCas()` 会 `router.replace` 进 `/student`，等于在隐藏 iframe 里跑一整套 SPA。修复=`enterAfterCas(navigate)` 参数，iframe 内只换会话不导航（`enterAfterCas(!isInIframe)`）。

**只有真跑能抓到这两个**：静态构建、TS 类型、单测全过。

### 14.4 测试期踩到的坑（下次直接省半天）

- **`cas_user_id` 已绑定时会短路姓名校验**（设计如此：绑定即信任）。要验"姓名不一致被拒"，必须先把该账号 `cas_user_id` 置 NULL，否则会得到"通过"的假绿。
- **Git Bash 会改写 Unix 风格 env 值**：`CAS_VALIDATE_PATH=/serviceValidate` 传给 node 变成 `C:/Program Files/Git/serviceValidate`，验票 404。本地实测别用 env 传路径，让代码默认值生效（`.env` 文件里的值不受影响，生产部署无此问题）。
- **浏览器自动化 `locator.click()` 在本环境必超时**（元素可见可命中也不行）：跨域步骤用 `cua.click`，应用内按钮用 `evaluate(() => el.click())`。
- 截图偶发 `surface preparation timed out`：重试前先 `waitForLoadState`，且 **el-message toast 消失后无法补拍**，报错类截图必须当场拍。

### 14.5 仍待外部配合（对方不给，前端上线也进不去）

1. Minos 登记 `lab-exam` / `lab-exam-test`（回调 `/api/auth/cas/callback`）——用户负责找大峥哥。
2. `appId` / `appSecret`。
3. 学生 + 教师测试账号各一个。
4. **一次真实 `serviceValidate` 的 XML**：定 `<cas:user>` 到底是 14 位集成账号还是学号、属性名到底是 `userName`/`realName` 还是 `xh`/`姓名`。属性名全在配置里，拿到 XML 只改 env，不改代码。

### 14.6 状态

代码在 `feat/cas-auth` 分支工作区，**未 commit、未 push**（等用户指令）。`server/.env.example` 已加完整注释块，部署时照着填即可。