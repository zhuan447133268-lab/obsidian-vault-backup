#!/usr/bin/env bash
# S5 验收实跑（学生端·闯关地图：登录态与路由守卫、解锁链/星标/首刷口径、真实 XP 与等级折算、目标切换、考试倒计时）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑，8080 端口空闲，班级 2024级英语1班 存在（S1 建）。
# 自建自清：只建自己的演示学生（S5V5）与它自己的 attempts / xp_ledger 演示进度；
# 题库（4 单元/24 关/206 题）、第 10 周真题、真实账号只读不改——
# 第 10 周真题指纹、17 张表的表数与列数，都在 00 与 99 各算一次对比。
#（T0001 会被 seed-teacher 打回初始密码再改密，这是 S2 就在用的惯例，复跑前重跑一次即可）。
set -uo pipefail
# 固定 Python 的 UTF-8 输出：Windows 控制台默认 GBK 时，print 中文/✅ 会抛 UnicodeEncodeError。
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
WEB="$ROOT/web"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"   # Python 是原生程序：给它 Windows 路径，别喂 /c/... 形式的 MSYS 路径
BASE=http://127.0.0.1:8080
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'
TEACHER_PWD2='Teacher@456'
STU=S5V5
STU_PWD='S5V5init'      # 初始密码（老师发的），≥6 位；登录后必须改密
STU_PWD2='S5demo2026'   # 改密后的密码
# 演示进度的账本总额（S5 只验证「展示口径」，不验证 XP 怎么赚的——那是 S3 的验收内容）
DEMO_XP=740
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | cut -d= -f2-)"
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4)
FAILS=0

step() { echo; echo "########## $* ##########"; }
check() { # check 描述 期望 实际
  if [ "$2" = "$3" ]; then
    echo "[CHECK] $1 ✅ 期望=$2 实际=$3"
  else
    echo "[CHECK] $1 ❌ 期望=$2 实际=$3"
    FAILS=$((FAILS + 1))
  fi
}
# pyget 字段路径：从统一信封里取字段（点号路径，数字段按下标走）；用法：pyget data.token < resp.json
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
login_token() { # login_token 用户名 密码
  printf '{"username":"%s","password":"%s"}' "$1" "$2" > "$EVID/body-login-$1.json"
  api POST /api/auth/login "" "$EVID/body-login-$1.json" > "$EVID/resp-login-$1.json"
  pyget data.token < "$EVID/resp-login-$1.json"
}
chpwd() { # chpwd 用户名 token 旧密码 新密码
  printf '{"oldPassword":"%s","newPassword":"%s"}' "$3" "$4" > "$EVID/body-chpwd-$1.json"
  api POST /api/auth/chpwd "$2" "$EVID/body-chpwd-$1.json" > /dev/null
}
sql() { "${MYSQL[@]}" -e "$1" | tr -d '\r'; }        # mysql 逐行 CRLF：取值前先去掉 \r
http_of() { grep -ao '\[HTTP [0-9]*\]' "$1" | tail -1 | tr -dc '0-9'; }
code_of() { pyget code < "$1"; }
# 独立口径的倒计时对拍：不 import 服务端任何东西，用 Python 自己算 12 月第二个周六
countdown_check() { # countdown_check today examDate daysLeft
  python - "$1" "$2" "$3" <<'PY'
import sys, datetime
today = datetime.date.fromisoformat(sys.argv[1])
exam  = datetime.date.fromisoformat(sys.argv[2])
days  = int(sys.argv[3])
def second_saturday(y):            # 12/1 起找第一个周六，再 +7 天
    d = datetime.date(y, 12, 1)
    return d + datetime.timedelta(days=(5 - d.weekday()) % 7 + 7)
want = second_saturday(today.year)
if want < today:                   # 考试日已过（考试当天仍算当天，倒计时 0）→ 滚动到下一年
    want = second_saturday(today.year + 1)
errs = []
if want.isoformat() != exam.isoformat():
    errs.append('下次考试日 api=%s 独立算=%s' % (exam, want))
if (exam - today).days != days:
    errs.append('倒计天数 api=%d 独立算=%d' % (days, (exam - today).days))
if exam.month != 12 or exam.weekday() != 5 or not (8 <= exam.day <= 14):
    errs.append('考试日不是 12 月的第二个周六：%s' % exam)
print('OK' if not errs else 'MISMATCH ' + '；'.join(errs))
PY
}
# 解锁链复核：重复实现「单元内第一个有题的关永远开放，其后每关要前一关通关，空关永不解锁」，
# 同时逐关对账 questionCount 与库里的真值。
chain_check() { # chain_check resp.json db-counts.tsv band
  python - "$1" "$2" "$3" <<'PY'
import sys, io, json
resp, tsv, band = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.loads(io.open(resp, encoding='utf-8').readline())['data']
items = d['items']
db = {}
for line in io.open(tsv, encoding='utf-8'):
    line = line.rstrip('\r\n')
    if not line:
        continue
    lid, cnt = line.split('\t')
    db[int(lid)] = int(cnt)
errs = []
for it in items:
    if db.get(it['id']) != it['questionCount']:
        errs.append('题量对不上(id=%s) api=%s 库=%s' % (it['id'], it['questionCount'], db.get(it['id'])))
seen, prev = set(), {}
for it in items:
    if it['questionCount'] == 0:
        want = False                       # 空关：既不开放也不占链条
    else:
        want = True
        if it['unitId'] in seen:
            want = prev.get(it['unitId'], False)
        seen.add(it['unitId'])
        prev[it['unitId']] = it['cleared']
    if it['unlocked'] != want:
        errs.append('解锁对不上(id=%s 第%s关) api=%s 独立算=%s' % (it['id'], it['seq'], it['unlocked'], want))
print('OK' if not errs else 'MISMATCH ' + '；'.join(errs[:6]))
PY
}
# 从 levels 响应里按固定口径取值。key 是内置的具名查询——不把 Python 代码交给 shell 解析
#（踩过一次：`"sum(...)"` 里的 `(` 会被 bash 当成子 shell，整个脚本语法错，见 2026-09-24 记录）。
levels_agg() { # levels_agg resp.json <key>
  python - "$1" "$2" <<'PY'
import sys, io, json
d = json.loads(io.open(sys.argv[1], encoding='utf-8').readline())['data']
items, units = d['items'], d['units']
key = sys.argv[2]
first_seq = lambda s: [i for i in items if i['seq'] == s][0]   # items 已按 周/关 升序，取第一条=第一个单元的那一关
val       = lambda xs: '/'.join(str(x) for x in xs)
q = {
    'sum_q':              lambda: sum(i['questionCount'] for i in items),
    'items_n':            lambda: len(items),
    'unit_sum_q':         lambda: sum(u['questionCount'] for u in units),
    'unit_sum_levels':    lambda: sum(u['levelCount'] for u in units),
    'units_n':            lambda: len(units),
    'unit0_cleared':      lambda: units[0]['clearedCount'],
    'unit0_levels':       lambda: units[0]['levelCount'],
    'first3_cleared':     lambda: val(i['cleared'] for i in items[:3]),
    'first3_stars':       lambda: val(i['stars'] for i in items[:3]),
    'first3_attempts':    lambda: val(i['attempts'] for i in items[:3]),
    'open_first_n':       lambda: sum(1 for i in items if i['unlocked'] and i['seq'] == min([j['seq'] for j in items
                             if j['unitId'] == i['unitId'] and j['questionCount'] > 0] or [0])),
    'seq1_unlocked':      lambda: first_seq(1)['unlocked'],
    'seq4_unlocked':      lambda: first_seq(4)['unlocked'],
    'seq5_unlocked':      lambda: first_seq(5)['unlocked'],
    'seq4_first_none':    lambda: first_seq(4)['firstResult'] is None,
    'seq2_first_attempt': lambda: first_seq(2)['firstResult']['attemptId'],
    'seq2_first_row':     lambda: '%s/%s/%s' % (first_seq(2)['firstResult']['correct'],
                                                first_seq(2)['firstResult']['total'],
                                                first_seq(2)['firstResult']['stars']),
    'boss_unlocked':      lambda: [i['unlocked'] for i in items if i['isBoss']][0],
    'b6_zhenti_q':        lambda: sum(i['questionCount'] for i in items if i['weekNo'] in (9, 10, 11)),
    'b6_zhenti_open':     lambda: sum(1 for i in items if i['weekNo'] in (9, 10, 11) and i['unlocked']),
    'b6_unit_shape':      lambda: val(0 if u['questionCount'] == 0 else u['levelCount'] for u in units),
}
# 必须惰性求值：写成字典字面量直接算值，取 sum_q 也会被无关的 seq2_first_attempt 拖崩——
# 新学生根本没打过第 2 关，firstResult=None，[ ]['attemptId'] 抛 TypeError，
# 于是 06 号（无进度基线）5 条断言拿到空值假失败。2026-09-24 实跑踩过一次。
print(q[key]())
PY
}

cd "$SRV" || exit 1
if curl -sS -o /dev/null "$BASE/api/health" 2>/dev/null; then
  echo "!! $BASE 已被占用（可能上一轮的服务还在跑），先停掉再复跑" >&2
  exit 1
fi

# ================================================================ 00 动库前现状
{
  step "00 前置：MySQL 3307 现状 + 17 张表红线 + 第 10 周真题指纹 + 幂等清理"
  sql "SELECT VERSION() AS mysql_version;"
  echo "--- 幂等清理：先删上一轮可能残留的演示学生及其进度，再算底账 ---"
  echo "（顺序要紧：底账必须「先清后算」。否则复跑时底账里还含上一轮的演示学生，"
  echo "  99 号回归会拿「含残留的基线」去比「清干净后的现状」，比出一堆假差值。）"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU'));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.wrong_book  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.diagnoses   WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.users       WHERE username='$STU';"
  check "清理后无残留演示学生" "0" "$(sql "SELECT COUNT(*) FROM cet46.users WHERE username='$STU';")"
  check "清理后演示账号不占 attempts" "0" \
    "$(sql "SELECT COUNT(*) FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username='$STU';")"
  echo
  echo "--- 动库前的底账（已清掉演示学生，复跑可复现）---"
  sql "SELECT
        (SELECT COUNT(*) FROM cet46.users)           AS users,
        (SELECT COUNT(*) FROM cet46.classes)         AS classes,
        (SELECT COUNT(*) FROM cet46.units)           AS units,
        (SELECT COUNT(*) FROM cet46.levels)          AS levels,
        (SELECT COUNT(*) FROM cet46.questions)       AS questions,
        (SELECT COUNT(*) FROM cet46.attempts)        AS attempts,
        (SELECT COUNT(*) FROM cet46.attempt_answers) AS attempt_answers,
        (SELECT COUNT(*) FROM cet46.xp_ledger)       AS xp_ledger,
        (SELECT COUNT(*) FROM cet46.wrong_book)      AS wrong_book,
        (SELECT COUNT(*) FROM cet46.diagnoses)       AS diagnoses;"
  sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.users),'/',
                     (SELECT COUNT(*) FROM cet46.units),'/',
                     (SELECT COUNT(*) FROM cet46.levels),'/',
                     (SELECT COUNT(*) FROM cet46.questions),'/',
                     (SELECT COUNT(*) FROM cet46.attempts),'/',
                     (SELECT COUNT(*) FROM cet46.attempt_answers),'/',
                     (SELECT COUNT(*) FROM cet46.xp_ledger));" > "$EVID/baseline-counts.txt"
  echo "底账（users/units/levels/questions/attempts/attempt_answers/xp_ledger）= $(cat "$EVID/baseline-counts.txt")"
  echo
  echo "--- 表清单与列数（§7 红线：17 张表；S5 是只读加接口，不加表不改列）---"
  TABLES_NOW=$(sql "SELECT GROUP_CONCAT(table_name ORDER BY table_name) FROM information_schema.tables WHERE table_schema='cet46';")
  echo "$TABLES_NOW"
  check "表名清单与 17 张红线一致（S5 未加表）" \
    "attempt_answers,attempts,audit_log,classes,coupon_redeems,coupons,diagnoses,levels,questions,reminders,seasons,team_members,teams,units,users,wrong_book,xp_ledger" \
    "$TABLES_NOW"
  check "表数 17" "17" "$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';")"
  COLUMNS_NOW=$(sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46';")
  printf '%s\n' "$COLUMNS_NOW" > "$EVID/baseline-columns.txt"
  check "列数基线 128（S5 未改列；99 号再算一次比对）" "128" "$COLUMNS_NOW"
  echo
  echo "--- 题库与分套底账（S5 的地图题量必须与这里逐关对账）---"
  sql "SELECT band, COUNT(*) AS 题数 FROM cet46.questions WHERE enabled=1 GROUP BY band;"
  sql "SELECT u.week_no AS 周, COUNT(DISTINCT l.id) AS 关数,
              SUM(CASE WHEN q.band='4' THEN 1 ELSE 0 END) AS 四级题,
              SUM(CASE WHEN q.band='6' THEN 1 ELSE 0 END) AS 六级题
       FROM cet46.units u JOIN cet46.levels l ON l.unit_id=u.id
       LEFT JOIN cet46.questions q ON q.level_id=l.id AND q.enabled=1
       GROUP BY u.week_no ORDER BY u.week_no;"
  echo
  echo "--- 第 10 周真题指纹（只读；99 号再算一次比对，证明 S5 没碰题库）---"
  BASELINE_W10=$(sql "SELECT MD5(GROUP_CONCAT(CONCAT_WS('|', q.id, q.type, CHAR_LENGTH(q.stem), MD5(q.stem), q.answer_idx, MD5(q.options_json)) ORDER BY q.id SEPARATOR ';'))
    FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
    WHERE u.week_no=10 AND q.type IN ('cloze','match');")
  printf '%s\n' "$BASELINE_W10" > "$EVID/baseline-week10-md5.txt"
  echo "第 10 周 20 道阅读真题指纹 = $BASELINE_W10"
} > "$EVID/00-precheck.log" 2>&1

# ================================================================ 01 全仓单测
{
  step "01 全仓单测（go test ./... -count=1 -v）：S5 改动不许碰坏 S0~S4"
  go build ./... && echo "[build] go build ./... 退出码 0"
  echo
  echo "--- go test ./... -v -count=1 （-v 是为了数用例条数；包级结果在最后）---"
  go test ./... -v -count=1 2>&1 | tr -d '\000' > "$EVID/gotest-all-v.txt"
  grep -E '^(ok|FAIL|\?)' "$EVID/gotest-all-v.txt"
  echo
  echo "--- 断言 ---"
  check "用例通过条数（S4 是 160，S5 新增 9 条：exam 4 + quiz level 2 + 路由 3）" "169" \
    "$(grep -c '^--- PASS' "$EVID/gotest-all-v.txt")"
  check "用例失败条数 0" "0" "$(grep -c '^--- FAIL' "$EVID/gotest-all-v.txt")"
  check "ok 包数 10" "10" "$(grep -c '^ok' "$EVID/gotest-all-v.txt")"
  check "失败包 0" "0" "$(grep -c '^FAIL' "$EVID/gotest-all-v.txt")"
} > "$EVID/01-gotest-all.log" 2>&1
rm -f "$EVID/gotest-all-v.txt"

# ================================================================ 02 倒计时单测明细（验收④）
{
  step "02 验收④ 考试倒计时的程序计算与单测（internal/exam）"
  echo "--- 用例表：先用 grep 把「给定今天 → 下次考试日」的断言表原样贴出来 ---"
  echo '（表来自 server/internal/exam/exam_test.go，行号为该文件行号）'
  grep -n 'want time.Time$\|today time.Time$\|day(20[0-9][0-9], time\.' "$SRV/internal/exam/exam_test.go"
  echo
  echo "--- go test ./internal/exam/ -v ---"
  go test ./internal/exam/ -v -count=1 2>&1 | tr -d '\000'
  go test ./internal/exam/ -v -count=1 2>&1 | tr -d '\000' > "$EVID/exam-verbose.txt"
  echo
  echo "--- 断言 ---"
  check "exam 包顶层用例 4 条全绿（规则/下次考试日/倒计时/目标校验）" "4" \
    "$(grep -c '^--- PASS: Test' "$EVID/exam-verbose.txt")"
  check "exam 包零失败" "0" "$(grep -c '^--- FAIL' "$EVID/exam-verbose.txt")"
  check "TestNext 子用例 8 条全绿（含考试次日→跨年滚动）" "8" \
    "$(grep -c '^    --- PASS: TestNext/' "$EVID/exam-verbose.txt")"
  check "TestDaysLeft 子用例 5 条全绿（含 9/24→12/12 共 79 天）" "5" \
    "$(grep -c '^    --- PASS: TestDaysLeft/' "$EVID/exam-verbose.txt")"
  echo
  echo "验收④点名的那条：给定今天=2026-09-24，断言下次考试日=2026-12-12 —— 用例表里在："
  check "用例表含「2026-09-24 → 2026-12-12」（S5 交卷日；TestNext 与 TestDaysLeft 各一条）" "2" \
    "$(grep -c 'day(2026, time.September, 24), day(2026, time.December, 12)' "$SRV/internal/exam/exam_test.go")"
  check "用例表含「考试次日 2026-12-13 → 2027-12-11」（跨年滚动）" "1" \
    "$(grep -c 'day(2026, time.December, 13), day(2027, time.December, 11)' "$SRV/internal/exam/exam_test.go")"
  check "用例表含 12/1 即周六的年份 2029-12-08（规则表与滚动表各一条）" "2" \
    "$(grep -c 'day(2029, time.December, 8)' "$SRV/internal/exam/exam_test.go")"
  check "用例表含区间上界 2030-12-14" "1" \
    "$(grep -c 'day(2030, time.December, 14)' "$SRV/internal/exam/exam_test.go")"
  check "倒计时 79 天的用例在表里" "1" \
    "$(grep -c 'time.December, 12), 79,' "$SRV/internal/exam/exam_test.go")"
} > "$EVID/02-gotest-exam.log" 2>&1
rm -f "$EVID/exam-verbose.txt"

# ================================================================ 03 起真服务
{
  step "03 启动 Go 服务（真 MySQL 3307），供接口实录"
} > "$EVID/03-server-start.log" 2>&1
go run ./cmd/server >> "$EVID/03-server-start.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
  sleep 1
  curl -sS "$BASE/api/health" > /dev/null 2>&1 && break
done
{
  echo "--- GET /api/health ---"
  curl -sS -w $'\n[HTTP %{http_code}]\n' "$BASE/api/health"
  echo
  echo "--- S5 相关路由（登录态/学生端/考试倒计时）---"
  grep -E 'auth|quiz|exam' "$EVID/03-server-start.log" | grep -E 'GET|POST|PATCH' | head -30 || true
} >> "$EVID/03-server-start.log" 2>&1

# ================================================================ 04 登录态与三道门（验收③的服务端一半）
{
  step "04 登录态：教师建号 → 学生首登必须改密（40302）→ 改密后进门"
  go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD" > /dev/null 2>&1

  echo "--- 04-1 教师：初始密码能登录，但业务接口被 40302 拦（首登未改密）---"
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
  check "教师用初始密码登录成功（拿到 token）" "yes" "$([ -n "$TOKEN" ] && echo yes || echo no)"
  check "教师登录态下 mustChangePwd=true（前端据此跳改密页）" "True" "$(pyget data.mustChangePwd < "$EVID/resp-login-$TEACHER.json")"
  api GET /api/admin/users "$TOKEN" > "$EVID/resp-teacher-gated.json"
  check "未改密教师访问 /api/admin/users：HTTP 403" "403" "$(http_of "$EVID/resp-teacher-gated.json")"
  check "未改密教师访问 /api/admin/users：业务码 40302" "40302" "$(code_of "$EVID/resp-teacher-gated.json")"
  chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
  check "改密后再登录：mustChangePwd=false" "False" "$(pyget data.mustChangePwd < "$EVID/resp-login-$TEACHER.json")"
  api GET /api/admin/users "$TOKEN" > "$EVID/resp-teacher-users.json"
  check "改密后教师能进后台：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-teacher-users.json")/$(code_of "$EVID/resp-teacher-users.json")"

  echo
  echo "--- 04-2 学生：新建 → 初始密码登录成功但地图接口被 40302 拦 → 改密后放行 ---"
  CLASS_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS_NAME';")
  printf '{"username":"%s","realName":"S5演示学生","password":"%s","role":"student","classId":%s,"target":"4"}' \
    "$STU" "$STU_PWD" "$CLASS_ID" > "$EVID/body-user-$STU.json"
  api POST /api/admin/users "$TOKEN" "$EVID/body-user-$STU.json" > "$EVID/resp-user-$STU.json"
  check "教师建演示学生：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-user-$STU.json")/$(code_of "$EVID/resp-user-$STU.json")"
  SID=$(sql "SELECT id FROM cet46.users WHERE username='$STU';")
  check "演示学生落在 2024级英语1班" "$CLASS_ID" "$(sql "SELECT class_id FROM cet46.users WHERE id=$SID;")"

  T=$(login_token "$STU" "$STU_PWD")
  check "学生用初始密码登录成功" "yes" "$([ -n "$T" ] && echo yes || echo no)"
  check "学生登录态下 mustChangePwd=true" "True" "$(pyget data.mustChangePwd < "$EVID/resp-login-$STU.json")"
  api GET /api/quiz/levels "$T" > "$EVID/resp-levels-gated.json"
  check "未改密学生取地图：HTTP 403" "403" "$(http_of "$EVID/resp-levels-gated.json")"
  check "未改密学生取地图：业务码 40302" "40302" "$(code_of "$EVID/resp-levels-gated.json")"
  api GET /api/exam/next "$T" > "$EVID/resp-exam-gated.json"
  check "未改密学生取倒计时：业务码 40302" "40302" "$(code_of "$EVID/resp-exam-gated.json")"
  chpwd "$STU" "$T" "$STU_PWD" "$STU_PWD2"
  TOKEN5=$(login_token "$STU" "$STU_PWD2")
  check "改密后再登录：mustChangePwd=false" "False" "$(pyget data.mustChangePwd < "$EVID/resp-login-$STU.json")"
  api GET /api/quiz/levels "$TOKEN5" > "$EVID/resp-levels-new.json"
  check "改密后取地图：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-levels-new.json")/$(code_of "$EVID/resp-levels-new.json")"
  api GET /api/exam/next "$TOKEN5" > "$EVID/resp-exam-b4.json"
  check "改密后取倒计时：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-exam-b4.json")/$(code_of "$EVID/resp-exam-b4.json")"
} > "$EVID/04-auth-gates.log" 2>&1

# ================================================================ 05 倒计时接口（验收④）
{
  step "05 验收④ 倒计时接口：考试日、倒计天数、场次、目标分数（含独立口径对拍）"
  TODAY=$(pyget data.today < "$EVID/resp-exam-b4.json")
  EXAM4=$(pyget data.examDate < "$EVID/resp-exam-b4.json")
  DAYS4=$(pyget data.daysLeft < "$EVID/resp-exam-b4.json")
  echo "--- 05-1 四级：GET /api/exam/next 原样 ---"
  head -1 "$EVID/resp-exam-b4.json"
  echo "接口给的 today=$TODAY  examDate=$EXAM4  daysLeft=$DAYS4"
  echo
  echo "--- 05-2 独立口径对拍（Python 自己算 12 月第二个周六与天数差，不 import 服务端任何东西）---"
  check "四级倒计时与独立口径一致（考试日=12月第二个周六、天数=日期差）" "OK" \
    "$(countdown_check "$TODAY" "$EXAM4" "$DAYS4")"
  check "target=4" "4" "$(pyget data.target < "$EVID/resp-exam-b4.json")"
  check "targetLabel=英语四级" "英语四级" "$(pyget data.targetLabel < "$EVID/resp-exam-b4.json")"
  check "四级是上午考" "上午" "$(pyget data.session < "$EVID/resp-exam-b4.json")"
  check "目标分数=过级线 425" "425" "$(pyget data.goalScore < "$EVID/resp-exam-b4.json")"
  check "满分 710" "710" "$(pyget data.scoreFull < "$EVID/resp-exam-b4.json")"
  echo
  echo "--- 05-3 切到六级：同一场考试（考试日不变）、下午考 ---"
  printf '{"target":"6"}' > "$EVID/body-target-6.json"
  api PATCH /api/auth/target "$TOKEN5" "$EVID/body-target-6.json" > "$EVID/resp-target-6.json"
  check "切六级：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-target-6.json")/$(code_of "$EVID/resp-target-6.json")"
  check "回执里的 target=6" "6" "$(pyget data.target < "$EVID/resp-target-6.json")"
  api GET /api/exam/next "$TOKEN5" > "$EVID/resp-exam-b6.json"
  check "六级考试日与四级相同（同一天两场）" "$EXAM4" "$(pyget data.examDate < "$EVID/resp-exam-b6.json")"
  check "六级是下午考" "下午" "$(pyget data.session < "$EVID/resp-exam-b6.json")"
  check "targetLabel=英语六级" "英语六级" "$(pyget data.targetLabel < "$EVID/resp-exam-b6.json")"
  check "六级倒计时与独立口径一致" "OK" \
    "$(countdown_check "$(pyget data.today < "$EVID/resp-exam-b6.json")" "$(pyget data.examDate < "$EVID/resp-exam-b6.json")" "$(pyget data.daysLeft < "$EVID/resp-exam-b6.json")")"
  echo
  echo "--- 05-4 非法目标值被拒（400 + 40001）---"
  for bad in 5 '' abc 44; do
    printf '{"target":"%s"}' "$bad" > "$EVID/body-target-bad.json"
    api PATCH /api/auth/target "$TOKEN5" "$EVID/body-target-bad.json" > "$EVID/resp-target-bad.json"
    check "target='$bad' 被拒：HTTP 400 + 40001" "400/40001" "$(http_of "$EVID/resp-target-bad.json")/$(code_of "$EVID/resp-target-bad.json")"
  done
  check "被拒后库里 target 没被改坏" "6" "$(sql "SELECT target FROM cet46.users WHERE id=$SID;")"
  echo
  echo "--- 05-5 幂等：同一个目标重复提交不报错、不改坏 ---"
  printf '{"target":"6"}' > "$EVID/body-target-6b.json"
  api PATCH /api/auth/target "$TOKEN5" "$EVID/body-target-6b.json" > "$EVID/resp-target-6b.json"
  check "重复提交 target=6：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-target-6b.json")/$(code_of "$EVID/resp-target-6b.json")"
  check "库里仍是 6" "6" "$(sql "SELECT target FROM cet46.users WHERE id=$SID;")"
  check "接口回执的 user.id 是本人" "$SID" "$(pyget data.id < "$EVID/resp-target-6b.json")"
} > "$EVID/05-countdown.log" 2>&1

# ================================================================ 06 解锁链（验收②，无进度基线）
{
  step "06 验收② 解锁状态与后端一致（新学生无进度基线）"
  echo "--- 06-1 库里逐关题量（band=4, enabled=1）---"
  sql "SELECT l.id, (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id=l.id AND q.band='4' AND q.enabled=1)
       FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.class_id=$CLASS_ID
       ORDER BY u.week_no, l.seq, l.id;" > "$EVID/db-level-counts-b4.tsv"
  cat "$EVID/db-level-counts-b4.tsv"
  echo
  echo "--- 06-2 解锁链复核 + 题量逐关对账（独立实现一遍规则）---"
  check "解锁链/题量全部一致（新学生：每单元第一关开着，其余锁着）" "OK" \
    "$(chain_check "$EWIN/resp-levels-new.json" "$EWIN/db-level-counts-b4.tsv" 4)"
  check "关卡数 24" "24" "$(pyget data.total < "$EVID/resp-levels-new.json")"
  check "做题量合计=173（四级题库）" "173" "$(levels_agg "$EWIN/resp-levels-new.json" sum_q)"
  check "库里的四级可用题数也是 173" "173" "$(sql "SELECT COUNT(*) FROM cet46.questions WHERE band='4' AND enabled=1;")"
  check "新学生 XP=0（没进度就是 0，不是种子数据）" "0" "$(pyget data.xpTotal < "$EVID/resp-levels-new.json")"
  check "新学生等级=1" "1" "$(pyget data.lv < "$EVID/resp-levels-new.json")"
  check "一级 300 XP 的斜率由服务端下发" "300" "$(pyget data.xpPerLevel < "$EVID/resp-levels-new.json")"
  echo
  echo "--- 06-3 每单元第一个「有题」的关都开着（原型口径：单元=一套题，周与周之间不互相锁死）---"
  echo "四级的 4 个单元全部有题，所以 4 个单元的第一个可玩关应该都 unlocked=true："
  check "开着的第一关数 = 单元数 = 4" "4" \
    "$(levels_agg "$EWIN/resp-levels-new.json" open_first_n)"
  check "推荐起点=第一个可玩关（=unit3 第 1 关）" \
    "$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=3 AND u.class_id=$CLASS_ID AND l.seq=1;")" \
    "$(pyget data.recommendedLevelId < "$EVID/resp-levels-new.json")"
  echo
  echo "--- 06-4 单元合计与关卡合计对得上 ---"
  check "单元合计题数 = 关卡题数合计（4 个单元 = 173）" "173" \
    "$(levels_agg "$EWIN/resp-levels-new.json" unit_sum_q)"
  check "单元合计关数 = 关卡数（24）" "24" \
    "$(levels_agg "$EWIN/resp-levels-new.json" unit_sum_levels)"
  check "单元数 4" "4" "$(levels_agg "$EWIN/resp-levels-new.json" units_n)"
} > "$EVID/06-levels-unlock.log" 2>&1

# ================================================================ 07 造进度后的地图口径
{
  step "07 验收② 有进度时的通关/星标/首刷口径 + 验收③ 真实 XP 与等级"
  echo "--- 07-1 造演示进度：unit3 第 1/2/3 关通关（第 2 关先 2 星再 3 星，验证「星级取历史最好」）---"
  sql "SET @uid := (SELECT id FROM cet46.users WHERE username='$STU');
       SET @u3  := (SELECT id FROM cet46.units WHERE week_no=3 AND class_id=$CLASS_ID);
       SET @l1  := (SELECT id FROM cet46.levels WHERE unit_id=@u3 AND seq=1);
       SET @l2  := (SELECT id FROM cet46.levels WHERE unit_id=@u3 AND seq=2);
       SET @l3  := (SELECT id FROM cet46.levels WHERE unit_id=@u3 AND seq=3);
       INSERT INTO cet46.attempts (user_id, level_id, unit_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at, finished_at)
         VALUES (@uid, @l1, @u3, 5, 5, 3, 0, 999999, 111, 'finished', NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY);
       INSERT INTO cet46.attempts (user_id, level_id, unit_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at, finished_at)
         VALUES (@uid, @l2, @u3, 4, 5, 2, 0, 0, 222, 'finished', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY);
       INSERT INTO cet46.attempts (user_id, level_id, unit_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at, finished_at)
         VALUES (@uid, @l2, @u3, 5, 5, 3, 0, 0, 333, 'finished', NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY);
       INSERT INTO cet46.attempts (user_id, level_id, unit_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at, finished_at)
         VALUES (@uid, @l3, @u3, 5, 5, 3, 0, 0, 444, 'finished', NOW(), NOW());
       INSERT INTO cet46.attempts (user_id, level_id, unit_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at)
         VALUES (@uid, @l1, @u3, 1, 5, 0, 0, 0, 555, 'in_progress', NOW());
       INSERT INTO cet46.xp_ledger (user_id, delta, reason, ref_type, ref_id, created_at)
         VALUES (@uid, $DEMO_XP, 's5_demo_seed', 'attempt', (SELECT MIN(id) FROM cet46.attempts WHERE user_id=@uid), NOW());"
  echo "库里现在的 attempts / xp_ledger："
  sql "SELECT a.id, a.level_id, a.correct, a.total, a.stars, a.status, a.xp_earned
       FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username='$STU' ORDER BY a.id;"
  sql "SELECT id, delta, reason, ref_type, ref_id FROM cet46.xp_ledger WHERE user_id=$SID;"
  sql "SELECT id, level_id, correct, total, stars, score710, xp_earned, shuffle_seed, status, started_at, finished_at FROM cet46.attempts WHERE user_id=$SID ORDER BY id;" > "$EVID/db-attempts-seeded.tsv"
  echo
  echo "--- 07-2 重新取地图 ---"
  api GET /api/quiz/levels "$TOKEN5" > "$EVID/resp-levels-progress.json"
  check "取地图：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-levels-progress.json")/$(code_of "$EVID/resp-levels-progress.json")"
  echo
  echo "--- 07-3 通关与星标 ---"
  check "第 1/2/3 关 cleared=true" "True/True/True" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" first3_cleared)"
  check "星级取历史最好（第 2 关先 2 星后 3 星 → 展示 3 星）" "3/3/3" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" first3_stars)"
  check "第 4 关 unlocked=true（上一关通关后自动解锁）" "True" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" seq4_unlocked)"
  check "第 5 关仍锁着" "False" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" seq5_unlocked)"
  check "单元 Boss 仍锁着" "False" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" boss_unlocked)"
  check "推荐起点推进到第 4 关" "$(sql "SELECT id FROM cet46.levels WHERE unit_id=(SELECT id FROM cet46.units WHERE week_no=3 AND class_id=$CLASS_ID) AND seq=4;")" \
    "$(pyget data.recommendedLevelId < "$EVID/resp-levels-progress.json")"
  echo
  echo "--- 07-4 首刷口径：firstResult = 该关第一条 finished（不是最好成绩、也不是最后一次）---"
  FIRST_L2=$(sql "SELECT id FROM cet46.attempts WHERE user_id=$SID AND level_id=(SELECT id FROM cet46.levels WHERE unit_id=(SELECT id FROM cet46.units WHERE week_no=3 AND class_id=$CLASS_ID) AND seq=2) AND status='finished' ORDER BY id ASC LIMIT 1;")
  check "第 2 关 firstResult.attemptId = 首刷那条 attempt" "$FIRST_L2" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" seq2_first_attempt)"
  check "首刷成绩如实是 4/5、2 星（不是被 3 星覆盖后的样子）" "4/5/2" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" seq2_first_row)"
  check "没通关的关 firstResult 为空（第 4 关）" "True" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" seq4_first_none)"
  echo
  echo "--- 07-5 attempts 计数（含没打完的那条 in_progress）---"
  check "第 1/2/3 关 attempts=2/2/1（第 1 关多出来那条是 in_progress）" "2/2/1" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" first3_attempts)"
  echo
  echo "--- 07-6 验收③ 真实 XP：只认账本聚合，attempts.xp_earned 里塞的 999999 不许算数 ---"
  check "XP = SELECT SUM(delta) FROM xp_ledger = $DEMO_XP" "$DEMO_XP" \
    "$(pyget data.xpTotal < "$EVID/resp-levels-progress.json")"
  check "账本聚合也确实等于 $DEMO_XP" "$DEMO_XP" "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$SID;")"
  check "attempts.xp_earned 里那个 999999 被忽略（否则 XP 会变成 1000739）" "$DEMO_XP" \
    "$(pyget data.xpTotal < "$EVID/resp-levels-progress.json")"
  check "等级=Lv3（740 = 2×300 + 140）" "3" "$(pyget data.lv < "$EVID/resp-levels-progress.json")"
  check "本级进度=140" "140" "$(pyget data.xpInLevel < "$EVID/resp-levels-progress.json")"
  check "本级上限=300" "300" "$(pyget data.xpPerLevel < "$EVID/resp-levels-progress.json")"
  echo "（users.lv 列故意不动，等级一律由账本折算——地图上的 LV 徽标与进度条同源）"
  check "库里 users.lv 仍是 1（S5 不写这个列）" "1" "$(sql "SELECT lv FROM cet46.users WHERE id=$SID;")"
  echo
  echo "--- 07-7 单元合计也跟着动 ---"
  check "unit3 clearedCount=3" "3" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" unit0_cleared)"
  check "拟毕业标记：本单元 6 个可玩关里通了 3 个（前端由此判定是否显示毕业横幅）" "6" \
    "$(levels_agg "$EWIN/resp-levels-progress.json" unit0_levels)"
} > "$EVID/07-levels-progress.log" 2>&1

# ================================================================ 08 六级切套（空关置灰）
{
  step "08 验收② 切到六级：真题单元空关必须置灰且不占解锁链"
  echo "--- 08-1 六级视角的逐关题量（band=6）---"
  sql "SELECT l.id, (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id=l.id AND q.band='6' AND q.enabled=1)
       FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.class_id=$CLASS_ID
       ORDER BY u.week_no, l.seq, l.id;" > "$EVID/db-level-counts-b6.tsv"
  cat "$EVID/db-level-counts-b6.tsv"
  echo
  api GET /api/quiz/levels "$TOKEN5" > "$EVID/resp-levels-b6.json"
  check "取地图（六级）：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-levels-b6.json")/$(code_of "$EVID/resp-levels-b6.json")"
  check "解锁链/题量全部一致（含空关：questionCount=0 一律 unlocked=false）" "OK" \
    "$(chain_check "$EWIN/resp-levels-b6.json" "$EWIN/db-level-counts-b6.tsv" 6)"
  check "做题量合计=33（六级题库）" "33" "$(levels_agg "$EWIN/resp-levels-b6.json" sum_q)"
  check "库里的六级可用题数也是 33" "33" "$(sql "SELECT COUNT(*) FROM cet46.questions WHERE band='6' AND enabled=1;")"
  check "三个真题单元（第 9/10/11 周）题量全 0" "0" \
    "$(levels_agg "$EWIN/resp-levels-b6.json" b6_zhenti_q)"
  check "三个真题单元的关卡全部 unlocked=false（不给六级学生开门）" "0" \
    "$(levels_agg "$EWIN/resp-levels-b6.json" b6_zhenti_open)"
  check "空关不占链条：unit3 的第 1 关照样开着（第 9 周空关没把它锁死）" "True" \
    "$(levels_agg "$EWIN/resp-levels-b6.json" seq1_unlocked)"
  check "四个单元的有题关数：unit3 有题、9/10/11 空" "6/0/0/0" \
    "$(levels_agg "$EWIN/resp-levels-b6.json" b6_unit_shape)"
  echo
  echo "--- 08-2 已注册口径：attempts 没有 band 列，通关/星级在四六级之间共享（S5 登记项，等拍板）---"
  check "六级视角下 unit3 的第 1~3 关仍显示已通关（跨套共享，属已知登记项）" "True/True/True" \
    "$(levels_agg "$EWIN/resp-levels-b6.json" first3_cleared)"
  check "六级视角下 XP 仍是同一本账（740）" "$DEMO_XP" "$(pyget data.xpTotal < "$EVID/resp-levels-b6.json")"
  echo
  echo "--- 08-3 切回四级（收尾状态与 00 号一致：目标=4）---"
  printf '{"target":"4"}' > "$EVID/body-target-4.json"
  api PATCH /api/auth/target "$TOKEN5" "$EVID/body-target-4.json" > "$EVID/resp-target-4.json"
  check "切回四级：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-target-4.json")/$(code_of "$EVID/resp-target-4.json")"
  check "库里 target=4" "4" "$(sql "SELECT target FROM cet46.users WHERE id=$SID;")"
} > "$EVID/08-levels-band6.log" 2>&1

# ================================================================ 09 前端构建与守卫产物
{
  step "09 前端：typecheck + build（学生会看到的那份东西必须能构建出来）"
  cd "$WEB" || exit 1
  echo "--- npm run typecheck（vue-tsc --noEmit）---"
  npm run typecheck 2>&1 | tail -20
  TSC=${PIPESTATUS[0]}
  echo "[typecheck 退出码] $TSC"
  echo
  echo "--- npm run build（含 typecheck + vite build）---"
  npm run build 2>&1 | tail -30
  BLD=${PIPESTATUS[0]}
  echo "[build 退出码] $BLD"
  echo
  echo "--- 断言 ---"
  check "typecheck 退出码 0" "0" "$TSC"
  check "build 退出码 0（vite 真构建过，下面的 dist 断言不是在拿旧产物顶包）" "0" "$BLD"
  check "学生端入口产物 dist/s.html 存在" "yes" "$([ -f "$WEB/dist/s.html" ] && echo yes || echo no)"
  check "产物里带学生端主 chunk" "yes" \
    "$(ls "$WEB/dist/assets" 2>/dev/null | grep -c '^s-.*\.js$' | awk '{print ($1>0)?"yes":"no"}')"
  check "改密路由进了产物（打包 JS 里能搜到 chpwd）" "yes" \
    "$(grep -al 'chpwd' "$WEB/dist/assets"/*.js 2>/dev/null | wc -l | awk '{print ($1>0)?"yes":"no"}')"
  check "登录跳转带着 redirect 参数（源码守卫）" "1" \
    "$(grep -c 'query: { redirect: to.fullPath }' "$WEB/src/student/router.ts")"
  check "改密页是唯一「未改密也放行」的路由" "1" \
    "$(grep -c 'allowUnchangedPwd: true' "$WEB/src/student/router.ts")"
  check "未登录一律回登录页（源码守卫）" "1" \
    "$(grep -c 'if (!session.isLoggedIn)' "$WEB/src/student/router.ts")"
  cd "$SRV" || exit 1
} > "$EVID/09-frontend-build.log" 2>&1

# ================================================================ 10 未登录访问（验收③）
{
  step "10 验收③ 未登录访问：服务端一律 401/40101（前端跳转见 11 号截图）"
  for path in /api/quiz/levels /api/exam/next /api/auth/me; do
    api GET "$path" "" > "$EVID/resp-unauth.json"
    check "不带 token 访问 $path：HTTP 401" "401" "$(http_of "$EVID/resp-unauth.json")"
    check "不带 token 访问 $path：业务码 40101" "40101" "$(code_of "$EVID/resp-unauth.json")"
  done
  api GET /api/quiz/levels "not-a-jwt" > "$EVID/resp-badtoken.json"
  check "伪造 token 访问地图：HTTP 401 + 40101" "401/40101" "$(http_of "$EVID/resp-badtoken.json")/$(code_of "$EVID/resp-badtoken.json")"
  api PATCH /api/auth/target "" "$EVID/body-target-4.json" > "$EVID/resp-unauth-target.json"
  check "不带 token 切目标：HTTP 401 + 40101" "401/40101" "$(http_of "$EVID/resp-unauth-target.json")/$(code_of "$EVID/resp-unauth-target.json")"
  echo
  echo "--- 学生端路由守卫（源码三道路径，构建产物同源）---"
  grep -n 'public: true\|allowUnchangedPwd\|redirect: to.fullPath\|mustChangePwd' "$WEB/src/student/router.ts"
} > "$EVID/10-unauth.log" 2>&1

# ================================================================ 11 截图清单（验收①，尺寸必须是真的视口尺寸）
{
  step "11 验收① 视觉实录清单与尺寸校验（与原型并排的两张 + 流程截图）"
  echo "--- 11-1 浏览器实录产物 ---"
  ls -1 "$EVID"/*.png 2>/dev/null
  echo
  echo "--- 11-2 尺寸逐张核对（PNG 头里的真实尺寸，不是文件名说了算）---"
  python - "$EWIN" <<'PY'
import sys, os, io
from PIL import Image
ev = sys.argv[1]
want = {
    'shot-01-login-redirect-390x844.png': (390, 844),
    'shot-02-target-overlay-390x844.png': (390, 844),
    'shot-03-map-lv3-390x844.png': (390, 844),
    'shot-04-map-pc-1440x900.png': (1440, 900),
    'shot-05-unit-cleared-banner-390x844.png': (390, 844),
    'shot-06-unit6-switch-folded-390x844.png': (390, 844),
    'shot-07-empty-levels-grey-390x844.png': (390, 844),
    'shot-08-chpwd-first-login-390x844.png': (390, 844),
    'shot-09-map-mid-900x760.png': (900, 760),
    'proto-390x844.png': (390, 844),
    'proto-1440x900.png': (1440, 900),
    'cmp-390x844.png': (852, 888),
    'cmp-1440x900.png': (2952, 944),
}
bad = []
for name, size in want.items():
    p = os.path.join(ev, name)
    if not os.path.exists(p):
        bad.append('%s 缺失' % name)
        continue
    got = Image.open(p).size
    print('%-42s %s' % (name, got))
    if got != size:
        bad.append('%s 尺寸 %s 期望 %s' % (name, got, size))
print('OK' if not bad else 'MISMATCH ' + '；'.join(bad))
PY
  check "13 张实录图全部存在且尺寸是真实视口尺寸" "OK" \
    "$(python - "$EWIN" <<'PY'
import sys, os
from PIL import Image
ev = sys.argv[1]
want = {
    'shot-01-login-redirect-390x844.png': (390, 844),
    'shot-02-target-overlay-390x844.png': (390, 844),
    'shot-03-map-lv3-390x844.png': (390, 844),
    'shot-04-map-pc-1440x900.png': (1440, 900),
    'shot-05-unit-cleared-banner-390x844.png': (390, 844),
    'shot-06-unit6-switch-folded-390x844.png': (390, 844),
    'shot-07-empty-levels-grey-390x844.png': (390, 844),
    'shot-08-chpwd-first-login-390x844.png': (390, 844),
    'shot-09-map-mid-900x760.png': (900, 760),
    'proto-390x844.png': (390, 844),
    'proto-1440x900.png': (1440, 900),
    'cmp-390x844.png': (852, 888),
    'cmp-1440x900.png': (2952, 944),
}
bad = []
for name, size in want.items():
    p = os.path.join(ev, name)
    if not os.path.exists(p):
        bad.append('%s 缺失' % name); continue
    if Image.open(p).size != size:
        bad.append('%s 尺寸 %s 期望 %s' % (name, Image.open(p).size, size))
print('OK' if not bad else 'MISMATCH ' + '；'.join(bad))
PY
)"
  echo
  echo "--- 11-3 两张并排图的构成（左=真数据实录，右=原型 index.html）---"
  python - "$EWIN" <<'PY'
import sys, os, hashlib
ev = sys.argv[1]
for n in ['cmp-390x844.png', 'cmp-1440x900.png', 'shot-03-map-lv3-390x844.png', 'shot-04-map-pc-1440x900.png',
          'proto-390x844.png', 'proto-1440x900.png', 'shot-05-unit-cleared-banner-390x844.png',
          'shot-06-unit6-switch-folded-390x844.png', 'shot-07-empty-levels-grey-390x844.png']:
    p = os.path.join(ev, n)
    if os.path.exists(p):
        print('%-42s %8d bytes  md5=%s' % (n, os.path.getsize(p), hashlib.md5(open(p,'rb').read()).hexdigest()[:12]))
PY
} > "$EVID/11-evidence-shots.log" 2>&1

# ================================================================ 99 清理与回归
{
  step "99 清理演示数据 + 回归对账（做题库、真题、账号一律恢复原样）"
  echo "--- 99-1 删演示学生（连带 attempts/attempt_answers/xp_ledger）---"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU'));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.wrong_book  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.diagnoses   WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.users       WHERE username='$STU';"
  check "演示学生已删净" "0" "$(sql "SELECT COUNT(*) FROM cet46.users WHERE username='$STU';")"
  check "演示进度已删净（attempts/attempt_answers/xp_ledger 三张表按本学生清零）" "0/0/0" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts WHERE user_id=$SID),'/',
                          (SELECT COUNT(*) FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id WHERE a.user_id=$SID),'/',
                          (SELECT COUNT(*) FROM cet46.xp_ledger WHERE user_id=$SID));")"
  check "五张学生产表回到动库前（attempts/attempt_answers/xp_ledger/wrong_book/diagnoses）" "0/0/0/0/0" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts),'/',
                          (SELECT COUNT(*) FROM cet46.attempt_answers),'/',
                          (SELECT COUNT(*) FROM cet46.xp_ledger),'/',
                          (SELECT COUNT(*) FROM cet46.wrong_book),'/',
                          (SELECT COUNT(*) FROM cet46.diagnoses));")"
  echo
  echo "--- 99-2 题库与账号回归 ---"
  check "底账回到动库前（users/units/levels/questions/attempts/attempt_answers/xp_ledger）" \
    "$(cat "$EVID/baseline-counts.txt")" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.users),'/',
                          (SELECT COUNT(*) FROM cet46.units),'/',
                          (SELECT COUNT(*) FROM cet46.levels),'/',
                          (SELECT COUNT(*) FROM cet46.questions),'/',
                          (SELECT COUNT(*) FROM cet46.attempts),'/',
                          (SELECT COUNT(*) FROM cet46.attempt_answers),'/',
                          (SELECT COUNT(*) FROM cet46.xp_ledger));")"
  check "单元数 4" "4" "$(sql "SELECT COUNT(*) FROM cet46.units;")"
  check "关卡数 24" "24" "$(sql "SELECT COUNT(*) FROM cet46.levels;")"
  check "题目数 206" "206" "$(sql "SELECT COUNT(*) FROM cet46.questions;")"
  check "表数仍是 17（S5 没加表）" "17" "$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';")"
  check "列数仍是 128（S5 没改列）" "$(cat "$EVID/baseline-columns.txt")" \
    "$(sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46';")"
  echo
  echo "--- 99-3 真题指纹回归：第 10 周 20 道阅读真题与 00 号比对 ---"
  NOW_W10=$(sql "SELECT MD5(GROUP_CONCAT(CONCAT_WS('|', q.id, q.type, CHAR_LENGTH(q.stem), MD5(q.stem), q.answer_idx, MD5(q.options_json)) ORDER BY q.id SEPARATOR ';'))
    FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
    WHERE u.week_no=10 AND q.type IN ('cloze','match');")
  echo "00 号基线 = $(cat "$EVID/baseline-week10-md5.txt")"
  echo "99 号现况 = $NOW_W10"
  check "第 10 周真题未被 S5 验收改动（题量/题干/答案/选项指纹逐位一致）" \
    "$(cat "$EVID/baseline-week10-md5.txt")" "$NOW_W10"
} > "$EVID/99-cleanup.log" 2>&1

kill "$SERVER_PID" 2>/dev/null
printf '\n--- 服务已停（PID %s）---\n' "$SERVER_PID" >> "$EVID/03-server-start.log"
echo
# 只数脚本自己的编号日志（00~99）。用 "$EVID"/*.log 会把外部重定向进来的
# run-transcript.log（整场会话的原始输出，含本脚本打印的摘要行）一起数进去，
# 复跑时计数器就对不上了——2026-09-24 在 S4 验收上踩过一次，S5 起固定用编号日志。
CHECK_TOTAL=$(grep -ah '\[CHECK\]' "$EVID"/[0-9][0-9]-*.log | wc -l | tr -d ' ')
CHECK_FAIL=$(grep -ah '❌' "$EVID"/[0-9][0-9]-*.log | wc -l | tr -d ' ')
CHECK_OK=$(grep -ah '✅' "$EVID"/[0-9][0-9]-*.log | wc -l | tr -d ' ')
echo "==== S5 验收实跑结束：校验失败项 = $FAILS，断言 $CHECK_TOTAL 行（✅ $CHECK_OK / ❌ $CHECK_FAIL）===="
if [ "$FAILS" = "$CHECK_FAIL" ]; then
  echo "计数自检：计数器与日志行数一致 ✅"
else
  echo "计数自检：计数器=$FAILS 与日志 ❌ 行数=$CHECK_FAIL 不一致 ❌（有失败行没写进日志，需人工看）"
fi
echo "日志目录：$EVID"