#!/usr/bin/env bash
# S6 验收实跑（学生端答题页：一镜到底对/错两路 · 目标切换 · 结算与账本对账 · 390px 原型比对）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑；Go :8080 与 Vite :5174 已起（没起则本脚本自己拉起来，退出时还原）；
#       班级 2024级英语1班 与教师 T0001 存在（S1/S2 建），题库 4 单元/24 关/206 题（真题切片，只读不改）。
#
# 自建自清：只动自己的演示学生 S6V6A/B/C 与他们的 attempts/attempt_answers/xp_ledger/wrong_book/diagnoses；
# 题库与真题指纹、17 张表的表数列数、账号总数，都在 00 与 99 各算一次对比（S6 不加表、不改列、不动题库）。
# 演示数据故意保留（验收④的账本对账证据就落在库里）；要清库跑 cleanup-demo.sh。
set -uo pipefail
export PYTHONUTF8=1          # Windows 控制台默认 GBK：python 打印中文/✅ 会抛 UnicodeEncodeError
export PYTHONIOENCODING=utf-8

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
WEB="$ROOT/web"
PROTO=/d/claude-work/cet46-game-prototype
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"   # python 是原生程序：喂 Windows 路径，别喂 /c/... 形式的 MSYS 路径
BASE=http://127.0.0.1:8080
VITE=http://127.0.0.1:5174
API=http://127.0.0.1:8080/api
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'      # seed-teacher 打的初始密码
TEACHER_PWD2='Teacher@456'     # 改密后（S5 就在用）
STUS=(S6V6A S6V6B S6V6C)
STU_PWD2='S6demo2026'          # 演示学生改密后的密码
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | tr -d '\r' | cut -d= -f2-)"
# 带上默认库 cet46：多表 DELETE ... JOIN 在没选库时 MySQL 会直接报 1046 No database selected
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)
FAILS=0
STEP_NAMES=()
STEP_RC=()
STEP_FAILS=()
STARTED_API=0
STARTED_WEB=0
STARTED_HTTP=0

step() { echo; echo "########## $* ##########"; }
check() { # check 描述 期望 实际
  if [ "$2" = "$3" ]; then
    echo "[CHECK] $1 ✅ 期望=$2 实际=$3"
  else
    echo "[CHECK] $1 ❌ 期望=$2 实际=$3"
    FAILS=$((FAILS + 1))
  fi
}
sql() { "${MYSQL[@]}" -e "$1"; }
pyget() { # pyget 字段路径：从统一信封里取字段（点号路径，数字段按下标走）
  python -c '
import sys, json
d = json.loads(sys.stdin.read().strip().split("\n")[0])
for p in sys.argv[1].split("."):
    d = d[int(p)] if p.isdigit() else d[p]
print(d)
' "$1"
}
http_of() { grep -ao '\[HTTP [0-9]*\]' "$1" | tail -1 | grep -o '[0-9]*'; }
code_of() { python -c '
import sys, json
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
line = [l for l in raw.splitlines() if l.strip().startswith("{")][0]
print(json.loads(line).get("code"))
' "$1"; }
api() { # api METHOD PATH TOKEN [BODY_FILE]
  local method="$1" path="$2" token="${3:-}" body="${4:-}"
  local args=(-sS -X "$method" "$API$path" -w $'\n[HTTP %{http_code}]\n')
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' --data-binary "@$body"); fi
  curl "${args[@]}"
}
login_token() { # login_token 用户名 密码 → token（失败回空）
  printf '{"username":"%s","password":"%s"}' "$1" "$2" > "$EVID/body-login-$1.json"
  api POST /auth/login "" "$EVID/body-login-$1.json" > "$EVID/resp-login-$1.json"
  python -c '
import sys, json
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
line = [l for l in raw.splitlines() if l.strip().startswith("{")]
if not line: print(""); sys.exit()
d = json.loads(line[0]).get("data") or {}
print(d.get("token") or "")
' "$EVID/resp-login-$1.json"
}
chpwd() { # chpwd 用户名 token 旧密码 新密码
  printf '{"oldPassword":"%s","newPassword":"%s"}' "$3" "$4" > "$EVID/body-chpwd-$1.json"
  api POST /auth/chpwd "$2" "$EVID/body-chpwd-$1.json" > /dev/null
}
run_step() { # run_step 03-chain step_03_chain
  local name="$1" fn="$2" log="$EVID/$1.log"
  : > "$log"
  "$fn" >> "$log" 2>&1
  local rc=$?
  local nf
  nf=$(grep -ac '❌' "$log" || true)
  STEP_NAMES+=("$name")
  STEP_RC+=("$rc")
  STEP_FAILS+=("$nf")
  FAILS=$((FAILS + nf))
  echo "== $name：退出码 $rc · 失败标记 ${nf} 条 =="
  if [ "$rc" != 0 ] || [ "$nf" != 0 ]; then tail -25 "$log"; fi
}

# ================================================================ 00 环境与底账
step_00_precheck() {
  step "00 S6 验收前置：服务可达 + 演示学生就位 + 底账快照（先记后清）"
  echo "--- 00-1 服务可达 ---"
  check "MySQL 3307 可连" "1" "$(sql 'SELECT 1;')"
  check "Go 服务 /api/health 200" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$API/health")"
  check "Vite 5174 可达（学生端 5174：5173 被别的项目占着）" "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/")"
  echo
  echo "--- 00-2 教师账号就位（seed-teacher 打回初始密码再改密，S2 起的惯例）---"
  ( cd "$SRV" && go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD" > /dev/null 2>&1 )
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
  check "教师初始密码登录成功" "yes" "$([ -n "$TOKEN" ] && echo yes || echo no)"
  chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
  check "教师改密后再登录成功" "yes" "$([ -n "$TOKEN" ] && echo yes || echo no)"
  CLASS_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS_NAME';")
  check "班级「$CLASS_NAME」存在" "yes" "$([ -n "$CLASS_ID" ] && echo yes || echo no)"
  echo
  echo "--- 00-3 演示学生 S6V6A/B/C（缺则建、建后改密；每次跑前把 S6 进度清零、目标回四级）---"
  local u
  for u in "${STUS[@]}"; do
    local sid
    sid=$(sql "SELECT id FROM cet46.users WHERE username='$u';")
    if [ -z "$sid" ]; then
      printf '{"username":"%s","realName":"S6演示学生%s","password":"%sinit","role":"student","classId":%s,"target":"4"}' \
        "$u" "${u#S6V6}" "$u" "$CLASS_ID" > "$EVID/body-user-$u.json"
      api POST /admin/users "$TOKEN" "$EVID/body-user-$u.json" > "$EVID/resp-user-$u.json"
      check "建号 $u：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-user-$u.json")/$(code_of "$EVID/resp-user-$u.json")"
      local t
      t=$(login_token "$u" "${u}init")
      check "$u 初始密码能登录" "yes" "$([ -n "$t" ] && echo yes || echo no)"
      chpwd "$u" "$t" "${u}init" "$STU_PWD2"
    fi
    check "$u 演示密码 $STU_PWD2 能登录" "yes" \
      "$([ -n "$(login_token "$u" "$STU_PWD2")" ] && echo yes || echo no)"
    sql "DELETE aa FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id JOIN cet46.users u ON u.id=a.user_id WHERE u.username='$u';
         DELETE l FROM cet46.xp_ledger l JOIN cet46.users u ON u.id=l.user_id WHERE u.username='$u';
         DELETE w FROM cet46.wrong_book w JOIN cet46.users u ON u.id=w.user_id WHERE u.username='$u';
         DELETE d FROM cet46.diagnoses d JOIN cet46.users u ON u.id=d.user_id WHERE u.username='$u';
         DELETE a FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username='$u';
         UPDATE cet46.users SET target=4 WHERE username='$u';" >/dev/null
    local sid2
    sid2=$(sql "SELECT id FROM cet46.users WHERE username='$u';")
    local zero
    zero=$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts WHERE user_id=$sid2),'/',
                              (SELECT COUNT(*) FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id WHERE a.user_id=$sid2),'/',
                              (SELECT COUNT(*) FROM cet46.xp_ledger WHERE user_id=$sid2),'/',
                              (SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$sid2));")
    check "$u 进度已清零（attempts/attempt_answers/xp_ledger/wrong_book 全 0）" "0/0/0/0" "$zero"
    check "$u 目标回四级（users.target=4）" "4" "$(sql "SELECT target FROM cet46.users WHERE id=$sid2;")"
    if [ "$zero" != "0/0/0/0" ]; then
      echo "!! 演示数据没清干净，后面的断言会全部建在脏数据上——中止本次实跑，先查复位语句。"
      exit 9
    fi
  done
  echo
  echo "--- 00-4 底账快照（99 要拿来比：S6 只写演示学生的行，不动表结构/题库/其他人）---"
  sql "SELECT CONCAT((SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46'),'/',
                    (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46'),'/',
                    (SELECT COUNT(*) FROM cet46.units),'/',
                    (SELECT COUNT(*) FROM cet46.levels),'/',
                    (SELECT COUNT(*) FROM cet46.questions),'/',
                    (SELECT COUNT(*) FROM cet46.users));" > "$EVID/baseline-counts.txt"
  sql "SELECT CONCAT(COUNT(*),'/',SUM(id),'/',SUM(CHAR_LENGTH(stem)),'/',
                    SUM(CHAR_LENGTH(IFNULL(options_json,''))),'/',
                    SUM(CRC32(CONCAT(id,'|',type,'|',answer_idx,'|',CHAR_LENGTH(stem),'|',CHAR_LENGTH(IFNULL(tip,''))))))
       FROM cet46.questions;" > "$EVID/baseline-questionbank-fingerprint.txt"
  echo "底账（表/列/单元/关/题/账号）：$(cat "$EVID/baseline-counts.txt")"
  echo "题库指纹（题数/id和/题干长/选项长/逐题 CRC 和）：$(cat "$EVID/baseline-questionbank-fingerprint.txt")"
  check "表数仍是 17（S6 不加表）" "17" "$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';")"
  check "列数仍是 128（S6 不改列，等级/目标都不落库）" "128" \
    "$(sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46';")"
  check "题库仍是 4 单元 / 24 关 / 206 题" "4/24/206" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.units),'/',
                          (SELECT COUNT(*) FROM cet46.levels),'/',
                          (SELECT COUNT(*) FROM cet46.questions));")"
  check "四级题库 173 题 / 六级题库 33 题（目标决定取哪一套）" "173/33" \
    "$(sql "SELECT CONCAT(SUM(band=4),'/',SUM(band=6)) FROM cet46.questions;")"
}

# ================================================================ 01/02 静态门禁
step_01_gotest() {
  step "01 go test ./... -count=1（全包；S6 新增答题页/首通口径的回归）"
  cd "$SRV" || exit 1
  local out
  out=$(go test ./... -count=1 2>&1)
  echo "$out"
  echo
  echo "--- 统计 ---"
  echo "PASS 行数：$(printf '%s\n' "$out" | grep -ac '^ok')"
  echo "FAIL 行数：$(printf '%s\n' "$out" | grep -ac '^FAIL')"
  check "go test 无 FAIL" "0" "$(printf '%s\n' "$out" | grep -ac '^FAIL' || true)"
  check "go test 无构建错误" "0" "$(printf '%s\n' "$out" | grep -ac 'build failed' || true)"
}

step_02_verify() {
  step "02 scripts/verify.sh（等价 CI：gofmt / go vet / go test / go build / eslint / 前端 build）"
  cd "$ROOT" || exit 1
  bash scripts/verify.sh 2>&1 | tail -60
  local rc=${PIPESTATUS[0]}
  check "verify.sh 退出码 0" "0" "$rc"
}

# ================================================================ 03-08 浏览器一镜到底
step_03_chain() {
  step "03 验收① E2E 一镜到底（对路）：四级 L25→L30，进关预告→答题→结算→下一关"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6A --password "$STU_PWD2" --tag chain --levels 25,26,27,28,29,30
}

step_04_replay() {
  step "04 拍板必改项回归：重刷已通关关卡（L25）不再重复发通关/三星奖励，答题分照发；顺带实录断点续答（答完第 2 题刷新页面）"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6A --password "$STU_PWD2" --tag replay --levels 25 --expect-replay --resume-after 2
}

step_05_realpaper() {
  step "05 内容基线：真题切片体量（四级第 3 套 阅读·选词填空 10 题 / 段落匹配 10 题）"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6A --password "$STU_PWD2" --tag realpaper --levels 38,39
}

step_06_wrong() {
  step "06 验收① E2E 一镜到底（错路）：全错 → 爱心扣完 → 失败层（本次得分已作废）"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6B --password "$STU_PWD2" --tag wrong --levels 25 --answer wrong
}

step_07_failmixed() {
  step "07 失败撤销回归：先答对挣到分再扣完爱心 → 账本写出「本次得分作废」冲回行，净得 0"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6B --password "$STU_PWD2" --tag failmixed --levels 25 --answer mixed
}

step_08_target6() {
  step "08 验收② 目标四级 → 六级：切完第一题即来自六级题库（users.target 落库 6）"
  cd "$EVID" || exit 1
  python e2e-quiz.py --user S6V6C --password "$STU_PWD2" --tag target6 --levels 25 --switch-target 6 --skip-first-level 1
}

# ================================================================ 09 账本对账
step_09_ledger() {
  step "09 验收④ 结算 XP 明细 ↔ xp_ledger 对账（基础+速度逐条一致 · 净得=账本净额 · XP 唯一权威=SUM(delta)）"
  cd "$EVID" || exit 1
  python reconcile-ledger.py e2e-chain.json e2e-replay.json e2e-realpaper.json \
    e2e-wrong.json e2e-failmixed.json e2e-target6.json
}

# ================================================================ 10/11 390px 原型比对
step_10_proto() {
  step "10 验收③ 原型 quiz.html 五态截图（390 宽手机框；走 http 才能写 localStorage）"
  cd "$EVID" || exit 1
  python -m http.server 8099 --directory "$(cygpath -w "$PROTO")" > /dev/null 2>&1 &
  STARTED_HTTP=$!
  sleep 2
  check "原型静态服务 8099 可达" "200" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8099/quiz.html)"
  python proto-shots.py http://127.0.0.1:8099
  kill "$STARTED_HTTP" > /dev/null 2>&1
  STARTED_HTTP=0
}

step_11_side_by_side() {
  step "11 验收③ 390px 并排图（左=真机实录 · 右=原型 quiz.html）+ 尺寸逐张核对"
  cd "$EVID" || exit 1
  python make-side-by-side.py
  echo
  echo "--- 11-2 尺寸逐张核对（PNG 头里的真实尺寸，不是文件名说了算）---"
  local szok
  szok=$(python - "$EWIN" <<'PY'
import sys, os
from PIL import Image
ev = sys.argv[1]
want = {
    'shots/shot-chain-L25-question.png': (390, 844),
    'shots/shot-chain-L25-feedback-ok.png': (390, 844),
    'shots/shot-failmixed-L25-feedback-no.png': (390, 844),
    'shots/shot-chain-L25-settlement-clear.png': (390, 844),
    'shots/shot-failmixed-L25-settlement-fail.png': (390, 844),
    'shots/shot-chain-L30-settlement-boss.png': (390, 844),
}
bad = []
for name, size in want.items():
    p = os.path.join(ev, name)
    if not os.path.exists(p):
        bad.append('%s 缺失' % name); continue
    got = Image.open(p).size
    print('%-52s %s' % (name, got))
    if got != size:
        bad.append('%s 尺寸 %s 期望 %s' % (name, got, size))
print('OK' if not bad else 'MISMATCH ' + '；'.join(bad))
PY
)
  echo "$szok"
  check "六张真机截图都是 390×844（验收③的 390px 口径）" "OK" \
    "$(echo "$szok" | tail -1 | grep -oE '^(OK|MISMATCH)')"
}

# ================================================================ 99 汇总与底账回归
step_99_summary() {
  step "99 收尾：编号日志逐条点名 + 底账回归（题库/表结构/账号）"
  echo "--- 99-1 编号日志 ---"
  local i name f
  for i in "${!STEP_NAMES[@]}"; do
    local n="${STEP_NAMES[$i]}"
    case "$n" in 99-*) continue;; esac
    f="$EVID/$n.log"
    if [ ! -f "$f" ]; then echo "$(printf '%-20s' "$n") [NG] 日志缺失"; continue; fi
    if [ "${STEP_RC[$i]}" = 0 ] && [ "${STEP_FAILS[$i]}" = 0 ]; then
      echo "$(printf '%-20s' "$n") [OK] 退出码 0 · 失败标记 0"
    else
      echo "$(printf '%-20s' "$n") [NG] 退出码 ${STEP_RC[$i]} · 失败标记 ${STEP_FAILS[$i]}"
    fi
  done
  echo
  echo "--- 99-2 各场景断言数（来自 e2e-*.json 与 ledger-reconcile.json）---"
  python - "$EWIN" <<'PY'
import sys, os, json, glob
ev = sys.argv[1]
tot = 0
for p in sorted(glob.glob(os.path.join(ev, 'e2e-*.json'))):
    d = json.load(open(p, encoding='utf-8'))
    n = len(d.get('checks', []))
    tot += n
    print('%-22s %4d 条断言 · 失败 %d 条 · %s' % (os.path.basename(p), n, len(d.get('fails', [])),
                                                 '✅' if not d.get('fails') else '❌'))
r = os.path.join(ev, 'ledger-reconcile.json')
if os.path.exists(r):
    d = json.load(open(r, encoding='utf-8'))
    tot += len(d.get('checks', []))
    print('%-22s %4d 条断言 · 对账 %d 次结算 · %s' % ('ledger-reconcile.json', len(d.get('checks', [])),
                                                   d.get('attempts', 0), '✅' if not d.get('fails') else '❌'))
print('合计 %d 条断言' % tot)
PY
  echo
  echo "--- 99-3 底账回归（题库与表结构必须一字未动）---"
  check "表/列/单元/关/题/账号 底账与开跑前一致" "$(cat "$EVID/baseline-counts.txt")" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46'),'/',
                          (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46'),'/',
                          (SELECT COUNT(*) FROM cet46.units),'/',
                          (SELECT COUNT(*) FROM cet46.levels),'/',
                          (SELECT COUNT(*) FROM cet46.questions),'/',
                          (SELECT COUNT(*) FROM cet46.users));")"
  check "题库指纹与开跑前一致（真题素材没被动过）" "$(cat "$EVID/baseline-questionbank-fingerprint.txt")" \
    "$(sql "SELECT CONCAT(COUNT(*),'/',SUM(id),'/',SUM(CHAR_LENGTH(stem)),'/',
                          SUM(CHAR_LENGTH(IFNULL(options_json,''))),'/',
                          SUM(CRC32(CONCAT(id,'|',type,'|',answer_idx,'|',CHAR_LENGTH(stem),'|',CHAR_LENGTH(IFNULL(tip,''))))))
         FROM cet46.questions;")"
  echo
  echo "--- 99-4 演示数据的最终形态（故意留着：验收④的账本证据在库里）---"
  sql "SELECT u.username, u.target,
              (SELECT COUNT(*) FROM cet46.attempts a WHERE a.user_id=u.id) attempts,
              (SELECT COUNT(*) FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id WHERE a.user_id=u.id) answers,
              (SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger l WHERE l.user_id=u.id) xp
       FROM cet46.users u WHERE u.username LIKE 'S6V6%' ORDER BY u.username;"
}

# ================================================================ 主流程
echo "S6 验收实跑开始：$(date '+%Y-%m-%d %H:%M:%S')"
curl -s -o /dev/null "$API/health" || { echo "!! Go 服务没起：先 cd server && go run ./cmd/server"; }
run_step 00-precheck step_00_precheck
run_step 01-gotest step_01_gotest
run_step 02-verify step_02_verify
run_step 03-chain step_03_chain
run_step 04-replay step_04_replay
run_step 05-realpaper step_05_realpaper
run_step 06-wrong step_06_wrong
run_step 07-failmixed step_07_failmixed
run_step 08-target6 step_08_target6
run_step 09-ledger step_09_ledger
run_step 10-proto-shots step_10_proto
run_step 11-side-by-side step_11_side_by_side
run_step 99-summary step_99_summary

echo
echo "############################################################"
echo "# S6 验收实跑结束：$(date '+%Y-%m-%d %H:%M:%S')"
echo "# 失败断言总数：$FAILS"
echo "# 编号日志：${STEP_NAMES[*]}"
echo "############################################################"
exit $(( FAILS > 0 ? 1 : 0 ))