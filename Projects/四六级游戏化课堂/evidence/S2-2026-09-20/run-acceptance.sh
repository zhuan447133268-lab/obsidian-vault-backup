#!/usr/bin/env bash
# S2 验收实跑（题库后端）。产出同目录下的编号日志，一键复现：
#   bash run-acceptance.sh
# 前置：MySQL 127.0.0.1:3307 在跑（数据目录 data/mysql-dev），8080 端口空闲，原型 quiz.html 在位。
# 原型默认在 D:/claude-work/cet46-game-prototype/quiz.html（仓库外），可用 PROTO=... 覆盖。
set -uo pipefail

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
PROTO="${PROTO:-D:/claude-work/cet46-game-prototype/quiz.html}"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE=http://127.0.0.1:8080
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'
TEACHER_PWD2='Teacher@456'
TEACHER2=T0002
TEACHER2_PWD='Teacher@123'
TEACHER2_PWD2='Teacher@456'
STU_PWD='Student@2024'
STU_PWD2='Student@2025'
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | cut -d= -f2-)"
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4)

step() { echo; echo "########## $* ##########"; }
# pyget data.token  → 从统一信封里取字段（点号路径，数字段按下标走）
pyget() {
  python -c '
import sys, json
d = json.loads(sys.stdin.read().strip().split("\n")[0])
for p in sys.argv[1].split("."):
    d = d[int(p)] if p.isdigit() else d[p]
print(d)
' "$1"
}
api() { # api METHOD PATH TOKEN [BODY_FILE]
  local method="$1" path="$2" token="${3:-}" body="${4:-}"
  local args=(-sS -X "$method" "$BASE$path" -w $'\n[HTTP %{http_code}]\n')
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' --data-binary "@$body"); fi
  curl "${args[@]}"
}
# login_token 用户名 密码  → 只回 token
login_token() {
  printf '{"username":"%s","password":"%s"}' "$1" "$2" > "$EVID/body-login-$1.json"
  api POST /api/auth/login "" "$EVID/body-login-$1.json" | pyget data.token
}
# chpwd 用户名 token 旧密码 新密码
chpwd() {
  printf '{"oldPassword":"%s","newPassword":"%s"}' "$3" "$4" > "$EVID/body-chpwd-$1.json"
  api POST /api/auth/chpwd "$2" "$EVID/body-chpwd-$1.json"
}
sql() { "${MYSQL[@]}" -e "$1"; }

cd "$SRV" || exit 1

# ---------------------------------------------------------------- 00 动库前先看清现状
{
  step "00 前置：MySQL 3307 现状（本阶段只加题库数据，不动 S1 的班级/学生）"
  sql "SELECT VERSION() AS mysql_version;"
  sql "SELECT
      (SELECT COUNT(*) FROM cet46.users)     AS users,
      (SELECT COUNT(*) FROM cet46.classes)   AS classes,
      (SELECT COUNT(*) FROM cet46.units)     AS units,
      (SELECT COUNT(*) FROM cet46.levels)    AS levels,
      (SELECT COUNT(*) FROM cet46.questions) AS questions;"
  sql "SELECT c.id, c.name, u.username AS teacher FROM cet46.classes c LEFT JOIN cet46.users u ON u.id = c.teacher_id;"
} > "$EVID/00-db-before.log" 2>&1

# ---------------------------------------------------------------- 01 交付物再生（模板 + 原型转 xlsx/csv）
{
  step "01 交付物：模板 + 原型题库转 xlsx/csv（验收①的前半段）"
  go run ./cmd/qbank -template testdata/qbank/question-bank-template.xlsx
  echo
  go run ./cmd/qbank -from-prototype "$PROTO" -class "$CLASS_NAME" -out testdata/qbank/prototype-66.xlsx
  echo
  go run ./cmd/qbank -to-csv testdata/qbank/prototype-66.xlsx -out testdata/qbank/prototype-66.csv
  echo
  echo "--- 产物 ---"
  ls -l testdata/qbank/
  echo
  echo "--- 成品按 分套/关卡/题型 汇总（对照原型 QBANK_4 / QBANK_6）---"
  python - <<'PY'
import csv, collections
rows = list(csv.DictReader(open("testdata/qbank/prototype-66.csv", encoding="utf-8-sig")))
agg = collections.defaultdict(collections.Counter)
for r in rows:
    agg[(r["备考目标"], r["关卡序号"])][r["题型"]] += 1
for key in sorted(agg, key=lambda k: (k[0], int(k[1]))):
    c = agg[key]
    print(f"band={key[0]} 关卡{key[1]}: 共{sum(c.values())}题  " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
per = collections.Counter(r["备考目标"] for r in rows)
print(f"合计：四级 {per['4']} 题，六级 {per['6']} 题，共 {len(rows)} 题")
PY
} > "$EVID/01-deliverables.log" 2>&1

# ---------------------------------------------------------------- 02 导入题库（CLI，验收①）
{
  step "02 验收①：原型题库（四级 33 + 六级 33）灌入零报错"
  echo "--- 02-0 先清空题库三张表（只删 S2 自己的题库数据，S1 的班级/学生原样保留），"
  echo "          这样「首次灌入」的证据每次都能复现（不会因为上一轮已导过而变成 skipped）---"
  sql "DELETE FROM cet46.questions; DELETE FROM cet46.levels; DELETE FROM cet46.units;"
  echo "清理后题目数：$(sql "SELECT COUNT(*) FROM cet46.questions;")"
  echo
  go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD"
  echo
  echo "--- 导入 $CLASS_NAME（教师 $TEACHER）---"
  go run ./cmd/qbank -file testdata/qbank/prototype-66.xlsx -teacher "$TEACHER"
  echo
  echo "--- 再导一次：应全部跳过（同关卡下 分套+题型+题干 相同的题不重复建）---"
  go run ./cmd/qbank -file testdata/qbank/prototype-66.xlsx -teacher "$TEACHER"
} > "$EVID/02-import-cli.log" 2>&1

# ---------------------------------------------------------------- 03 落库对账 + 表结构红线
{
  step "03 落库对账（真 MySQL）"
  sql "SELECT band AS 分套, COUNT(*) AS 题数 FROM cet46.questions GROUP BY band ORDER BY band;"
  sql "SELECT COUNT(*) AS 单元数 FROM cet46.units;"
  sql "SELECT seq AS 关卡序号, name AS 关卡名, type AS 类型, time_limit AS 限时秒, is_boss AS Boss,
        (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id = l.id AND q.band='4') AS 四级题数,
        (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id = l.id AND q.band='6') AS 六级题数
      FROM cet46.levels l ORDER BY seq;"
  sql "SELECT enabled AS 启用, COUNT(*) AS 题数 FROM cet46.questions GROUP BY enabled;"
  echo
  step "03b 表结构红线（任务书 §7）：questions 表结构须与开发方案 v1.0 §4 一致（含 enabled 默认值、answer_idx varchar）"
  "${MYSQL[@]}" -e "SHOW CREATE TABLE cet46.questions\G"
} > "$EVID/03-db-after.log" 2>&1

# ---------------------------------------------------------------- 04 坏行样例
{
  step "04 坏行清单：行号（表头算第 1 行）+ 定位 + 原因，且整份不落库"
  echo "--- 导入前题目数 ---"
  sql "SELECT COUNT(*) FROM cet46.questions;"
  echo "--- 导入 testdata/qbank/bad-rows-sample.csv（含 6 类坏行 + 1 行正常）---"
  go run ./cmd/qbank -file testdata/qbank/bad-rows-sample.csv -teacher "$TEACHER"
  echo "--- 导入后题目数（应不变）---"
  sql "SELECT COUNT(*) FROM cet46.questions;"
} > "$EVID/04-bad-rows.log" 2>&1

# ---------------------------------------------------------------- 05 起真服务
{
  step "05 启动 Go 服务（真 MySQL），供接口实录"
} > "$EVID/05-server-start.log" 2>&1
go run ./cmd/server >> "$EVID/05-server-start.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
  sleep 1
  curl -sS "$BASE/api/health" > /dev/null 2>&1 && break
done
{
  echo "--- GET /api/health ---"
  curl -sS -w $'\n[HTTP %{http_code}]\n' "$BASE/api/health"
} >> "$EVID/05-server-start.log" 2>&1

# ---------------------------------------------------------------- 06 登录 + 接口上传（验收①的接口面）
{
  step "06 验收①（接口面）：POST /api/admin/import-questions 上传 prototype-66.xlsx"
  echo "--- 06-1 教师登录（seed 后的初始密码 → 首登须改密）---"
  printf '{"username":"%s","password":"%s"}' "$TEACHER" "$TEACHER_PWD" > "$EVID/body-login-$TEACHER.json"
  api POST /api/auth/login "" "$EVID/body-login-$TEACHER.json"
  echo
} > "$EVID/06-curl-import-endpoint.log" 2>&1

TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
{
  echo "--- 06-2 首登未改密时，教师接口应 403/40302 ---"
  api GET /api/admin/units "$TOKEN"
  echo
  echo "--- 06-3 改密 $TEACHER_PWD → $TEACHER_PWD2 ---"
  chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
  echo
} >> "$EVID/06-curl-import-endpoint.log" 2>&1

TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
{
  echo "--- 06-4 重传同一份 xlsx（应 created=0 / skipped=66，幂等）---"
  curl -sS -X POST "$BASE/api/admin/import-questions" -H "Authorization: Bearer $TOKEN" \
    -F "file=@testdata/qbank/prototype-66.xlsx" -w $'\n[HTTP %{http_code}]\n'
  echo
  echo "--- 06-5 下载导入模板（教师侧交付物）---"
  curl -sS -D - -o "$EVID/downloaded-template.xlsx" -H "Authorization: Bearer $TOKEN" \
    "$BASE/api/admin/import-questions/template" | head -8
  echo "下载文件大小：$(stat -c%s "$EVID/downloaded-template.xlsx") 字节"
} >> "$EVID/06-curl-import-endpoint.log" 2>&1

# ---------------------------------------------------------------- 07 学生取题（验收②）
{
  step "07 验收②：按 band + level 取题过滤正确（接口实录）"

  echo "--- 07-0 演示账号 S4001/S6001/S9001 若已存在先清掉（本脚本自己建的演示账号，无关联流水）---"
  sql "DELETE FROM cet46.users WHERE username IN ('S4001','S6001','S9001');"
  echo "已清理（如本来不存在则影响 0 行）"
  echo
  echo "--- 07-1 建两个演示学生：S4001（备考四级）/ S6001（备考六级），同在 $CLASS_NAME ---"
  CLASS_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS_NAME';")
  echo "班级 $CLASS_NAME id=$CLASS_ID"
  for pair in S4001:4 S6001:6; do
    stu="${pair%%:*}"; tgt="${pair##*:}"
    printf '{"username":"%s","realName":"演示学生%s","password":"%s","role":"student","classId":%d,"target":"%s"}' \
      "$stu" "$stu" "$STU_PWD" "$CLASS_ID" "$tgt" > "$EVID/body-user-$stu.json"
    echo "POST /api/admin/users $stu target=$tgt"
    api POST /api/admin/users "$TOKEN" "$EVID/body-user-$stu.json"
    echo
    STU_TOKEN=$(login_token "$stu" "$STU_PWD")
    echo "首登（初始密码）→ 改密 → 重新登录"
    chpwd "$stu" "$STU_TOKEN" "$STU_PWD" "$STU_PWD2"
    echo
    STU_TOKEN=$(login_token "$stu" "$STU_PWD2")
    echo "学生 $stu 登录成功（已改密），token 长度 ${#STU_TOKEN}"
    eval "TOKEN_$stu=$STU_TOKEN"
    echo
  done

  echo "--- 07-2 四级学生 S4001 取关卡（GET /api/quiz/levels）---"
  api GET /api/quiz/levels "$TOKEN_S4001"
  echo
  echo "--- 07-3 六级学生 S6001 取关卡（同班同关卡，可见题数按各自分套）---"
  api GET /api/quiz/levels "$TOKEN_S6001"
  echo

  LEVEL1=$(sql "SELECT id FROM cet46.levels ORDER BY seq LIMIT 1;")
  LEVEL6=$(sql "SELECT id FROM cet46.levels ORDER BY seq DESC LIMIT 1;")
  echo "第 1 关 id=$LEVEL1，Boss 关 id=$LEVEL6"
  echo
  echo "--- 07-4 四级学生取第 1 关（应 5 题，全是四级词汇题，answerIdx/exp/tip 不在响应里）---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S4001"
  echo
  echo "--- 07-5 六级学生取同一关（应 5 题，题干与四级完全不同）---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S6001"
  echo
  echo "--- 07-6 四级学生取 Boss 关（应 8 题，含 1 道翻译题）---"
  api GET "/api/quiz/questions?level=$LEVEL6" "$TOKEN_S4001" | python -c '
import sys, json, collections
raw = sys.stdin.read().split("\n")[0]
d = json.loads(raw)["data"]
print("total =", d["total"])
print("题型分布：", dict(collections.Counter(q["type"] for q in d["items"])))
print("题号：", [q["id"] for q in d["items"]])
'
  echo
  echo "--- 07-7 交叉验证：同一关卡两套题库题干零重叠 ---"
  {
    api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S4001"
    api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S6001"
  } | python -c '
import sys, json
lines = [l for l in sys.stdin.read().splitlines() if l.startswith("{")]
a = json.loads(lines[0])["data"]["items"]
b = json.loads(lines[1])["data"]["items"]
sa, sb = {x["stem"] for x in a}, {x["stem"] for x in b}
print(f"四级 {len(a)} 题 / 六级 {len(b)} 题，题干交集 {len(sa & sb)} 条（必须为 0）")
print("四级首题：", min(sa)[:70])
print("六级首题：", min(sb)[:70])
'
} > "$EVID/07-curl-quiz-band-level.log" 2>&1

# ---------------------------------------------------------------- 08 停用不下发（验收③）
{
  step "08 验收③：enabled=false 的题不下发"
  LEVEL1=$(sql "SELECT id FROM cet46.levels ORDER BY seq LIMIT 1;")
  QID=$(sql "SELECT id FROM cet46.questions WHERE level_id=$LEVEL1 AND band='4' ORDER BY id LIMIT 1;")
  echo "第 1 关 id=$LEVEL1，停用题目 id=$QID（四级第 1 题）"
  echo
  echo "--- 08-1 停用前：教师视角读该题（enabled=true，含答案与解析）---"
  api GET "/api/admin/questions/$QID" "$TOKEN"
  echo
  echo "--- 08-2 停用前：四级学生取第 1 关的题数 / 关卡列表里的可见题数 ---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S4001" | head -1 | pyget data.total
  api GET /api/quiz/levels "$TOKEN_S4001" | head -1 | pyget data.items.0.questionCount
  echo
  echo "--- 08-3 PATCH /api/admin/questions/$QID {\"enabled\": false} ---"
  printf '{"enabled":false}' > "$EVID/body-disable.json"
  api PATCH "/api/admin/questions/$QID" "$TOKEN" "$EVID/body-disable.json"
  echo
  echo "--- 08-4 落库核对（enabled 列应为 0）---"
  sql "SELECT id, enabled FROM cet46.questions WHERE id=$QID;"
  echo
  echo "--- 08-5 教师视角读回（enabled 应为 false）---"
  api GET "/api/admin/questions/$QID" "$TOKEN" | head -1 | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("enabled =", d["enabled"], "| answerIdx =", d["answerIdx"], "| exp 非空 =", bool(d["exp"]))
'
  echo
  echo "--- 08-6 停用后：四级学生取题（题数 5→4，且不再含该 id）---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S4001" | python -c '
import sys, json
d = json.loads([l for l in sys.stdin.read().splitlines() if l.startswith("{")][0])["data"]
target = int(sys.argv[1])
print("total =", d["total"])
print("下发题目 id：", [x["id"] for x in d["items"]])
print(f"是否仍含被停用的 id={target}：", any(x["id"] == target for x in d["items"]))
' "$QID"
  echo "关卡列表里的可见题数（应为 4）："
  api GET /api/quiz/levels "$TOKEN_S4001" | head -1 | pyget data.items.0.questionCount
  echo
  echo "--- 08-7 六级学生不受影响（同一关卡，六级题数不变）---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S6001" | head -1 | pyget data.total
  echo
  echo "--- 08-8 恢复启用（还原现场，方便复验）---"
  printf '{"enabled":true}' > "$EVID/body-enable.json"
  api PATCH "/api/admin/questions/$QID" "$TOKEN" "$EVID/body-enable.json" > /dev/null
  sql "SELECT id, enabled FROM cet46.questions WHERE id=$QID;"
} > "$EVID/08-curl-enabled-off.log" 2>&1

# ---------------------------------------------------------------- 09 鉴权/越权/答案不泄露
{
  step "09 鉴权与隔离：未登录 401、学生调教师接口 403、跨教师 404、答案不泄露"
  echo "--- 09-1 未登录 GET /api/admin/questions ---"
  api GET /api/admin/questions ""
  echo
  echo "--- 09-2 未登录 GET /api/quiz/levels ---"
  api GET /api/quiz/levels ""
  echo
  echo "--- 09-3 学生 token 调教师接口（应 403/40301）---"
  api GET /api/admin/questions "$TOKEN_S4001"
  echo
  echo "--- 09-4 学生 token 调导入接口（应 403）---"
  curl -sS -X POST "$BASE/api/admin/import-questions" -H "Authorization: Bearer $TOKEN_S4001" \
    -F "file=@testdata/qbank/prototype-66.xlsx" -w $'\n[HTTP %{http_code}]\n'
  echo
  echo "--- 09-5 另一个教师 $TEACHER2 看 $TEACHER 的题库（应 200 + 空列表）---"
  go run ./cmd/seed-teacher -username "$TEACHER2" -name 李老师 -password "$TEACHER2_PWD" > /dev/null
  T2=$(login_token "$TEACHER2" "$TEACHER2_PWD")
  chpwd "$TEACHER2" "$T2" "$TEACHER2_PWD" "$TEACHER2_PWD2" > /dev/null
  T2=$(login_token "$TEACHER2" "$TEACHER2_PWD2")
  api GET /api/admin/questions "$T2"
  echo
  echo "--- 09-6 $TEACHER2 按 id 直取 $TEACHER 的题（应 404，不泄露存在性）---"
  QID=$(sql "SELECT id FROM cet46.questions ORDER BY id LIMIT 1;")
  api GET "/api/admin/questions/$QID" "$T2"
  echo
  echo "--- 09-7 $TEACHER2 往 $TEACHER 的关卡建题（应 404）---"
  LEVEL1=$(sql "SELECT id FROM cet46.levels ORDER BY seq LIMIT 1;")
  printf '{"levelId":%d,"band":"4","type":"vocab","stem":"越权试探","options":["a","b"],"answerIdx":"0","exp":"试探"}' "$LEVEL1" > "$EVID/body-crosslearn.json"
  api POST /api/admin/questions "$T2" "$EVID/body-crosslearn.json"
  echo
  echo "--- 09-8 答案不泄露：学生取题响应里不得出现 answerIdx/exp/tip/knowledgeTag ---"
  api GET "/api/quiz/questions?level=$LEVEL1" "$TOKEN_S4001" | python -c '
import sys, json
body = sys.stdin.read().strip().splitlines()[0]
d = json.loads(body)

def collect_keys(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            acc.add(k)
            collect_keys(v, acc)
    elif isinstance(o, list):
        for v in o:
            collect_keys(v, acc)
    return acc

seen = collect_keys(d["data"], set())
items = d["data"]["items"]
banned = ("answerIdx", "exp", "tip", "knowledgeTag", "optionsJson")
hit = sorted(k for k in banned if k in seen)
print("响应体（前 120 字符）：", body[:120])
print("data 下出现过的所有键：", sorted(seen))
print("单题字段：", sorted(items[0].keys()))
print("下发题数：", len(items))
print("禁字段命中（按 JSON 键判定，不看题干里的子串）：", hit if hit else "无 ✅")
'
  echo
  echo "--- 09-9 未分班学生取关卡/取题（应空列表 + 404）---"
  printf '{"username":"S9001","realName":"未分班学生","password":"%s","role":"student","target":"4"}' "$STU_PWD" > "$EVID/body-user-S9001.json"
  api POST /api/admin/users "$TOKEN" "$EVID/body-user-S9001.json" > /dev/null
  T9=$(login_token S9001 "$STU_PWD")
  chpwd S9001 "$T9" "$STU_PWD" "$STU_PWD2" > /dev/null
  T9=$(login_token S9001 "$STU_PWD2")
  echo "取关卡："
  api GET /api/quiz/levels "$T9" | head -1
  echo "取题："
  api GET "/api/quiz/questions?level=$LEVEL1" "$T9"
} > "$EVID/09-curl-authz.log" 2>&1

# ---------------------------------------------------------------- 10/11 测试与一键校验
{
  step "10 go test ./...（服务层 + router 层 HTTP 全链路）"
  go test ./... 2>&1 | tr -d '\000'
  echo
  step "10b 本阶段新增/相关的测试用例（逐个列出）"
  go test ./internal/qbank/ ./internal/service/ ./internal/router/ -v 2>&1 | tr -d '\000' | grep -E '^(--- PASS|--- FAIL)' | grep -v '/'
} > "$EVID/10-gotest.log" 2>&1

{
  step "11 scripts/verify.sh（gofmt + go vet + go test + go build + eslint + 前端构建）"
} > "$EVID/11-verify-sh.log" 2>&1
bash "$ROOT/scripts/verify.sh" >> "$EVID/11-verify-sh.log" 2>&1
echo "verify.sh 退出码: $?" >> "$EVID/11-verify-sh.log"

kill "$SERVER_PID" 2>/dev/null
printf '\n--- 服务已停（PID %s）---\n' "$SERVER_PID" >> "$EVID/05-server-start.log"
echo "验收实跑结束，日志在 $EVID"