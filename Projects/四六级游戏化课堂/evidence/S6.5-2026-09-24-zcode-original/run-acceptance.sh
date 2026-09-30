#!/usr/bin/env bash
# S6.5 验收实跑（个人学习档案页：错题本 · 六边形能力画像 · 成长曲线 · 复盘提醒）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑；Go :8080（含 S6.5 新代码）与 Vite :5174 已起；
#       班级 2024级英语1班 与教师 T0001 存在（S1/S2 建），题库 4 单元/24 关/206 题（只读不改）。
#
# 自建自清：只动演示学生 S65A/S65B/S65C 与他们的 attempts/attempt_answers/xp_ledger/wrong_book/diagnoses；
# 题库指纹、17 张表的表数列数、账号总数在 00 与 99 各算一次对比（S6.5 不加表、不改列、不动题库）。
# 演示数据故意保留（验收①②③的证据落在库里）；要清库跑 cleanup-demo.sh。
#
# 三个数据面的对拍口径（这是本阶段验收的核心）：
#   手算（plan-seed.json：脚本按计划答了什么）× SQL 聚合（独立重写的映射/分桶）× 接口回执，
#   三方必须一致；真浏览器再把页面 DOM 与接口回执逐项对齐（页面上必须真的画出那些数）。
set -uo pipefail
export PYTHONUTF8=1          # Windows 控制台默认 GBK：python 打印中文/✅ 会抛 UnicodeEncodeError
export PYTHONIOENCODING=utf-8

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"   # python 是原生程序：喂 Windows 路径，别喂 /c/... 形式的 MSYS 路径
API=http://127.0.0.1:8080/api
VITE=http://127.0.0.1:5174
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'      # seed-teacher 打的初始密码
TEACHER_PWD2='Teacher@456'     # 改密后（S5/S6 都在用）
STU_A=S65A
STU_B=S65B
STU_C=S65C
STU_PWD2='S65demo2026'         # 演示学生改密后的密码
STU_C_INIT='S65Cinit'          # S65C 故意不改密：验证 40302 门禁
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | tr -d '\r' | cut -d= -f2-)"
# 带上默认库 cet46：多表 DELETE ... JOIN 在没选库时 MySQL 会直接报 1046 No database selected
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)
FAILS=0
STEP_NAMES=()
STEP_RC=()
STEP_FAILS=()

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
run_step() { # run_step 03-seed step_03_seed
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
  if [ "$rc" != 0 ] || [ "$nf" != 0 ]; then tail -30 "$log"; fi
}

# ================================================================ 00 环境与底账
step_00_precheck() {
  step "00 S6.5 验收前置：服务可达 + 演示学生就位 + 底账快照"
  # 截图与断言 JSON 每跑一次全部重生成：混着上一跑的旧文件（旧命名、旧帧、被覆盖过的 JSON）
  # 当证据是自欺——上一跑就出现过 4 张截图字节完全一样、auth 模式把 full 模式的 JSON 覆盖掉。
  rm -rf "$EVID/shots"; mkdir -p "$EVID/shots"
  rm -f "$EVID"/e2e-*.json "$EVID"/profile-*.json
  echo "--- 00-1 服务可达 ---"
  check "MySQL 3307 可连" "1" "$(sql 'SELECT 1;')"
  check "Go 服务 /api/health 200" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$API/health")"
  check "Vite 5174 可达（学生端 5174：5173 被别的项目占着）" "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/")"
  check "档案页路由 /s/me 可达" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/s/me")"
  check "S6.5 新接口已挂上（未带 token → 401，不是 404）" "401" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$API/profile/overview")"
  # 开发服务器吐旧缓存，会把「代码已改」测成「页面没变」（S6.5 首跑就栽在这：红点代码没进浏览器）。
  # 直接问 Vite 要 S6.5 改过的两个文件，拿不到新标记就说明是旧模块 → 重启 Vite 再跑。
  check "Vite 吐的是 S6.5 之后的 BottomNav（含复盘红点）" "yes" \
    "$(curl -s "$VITE/src/student/components/BottomNav.vue" | grep -q 'hasPending' && echo yes || echo no)"
  check "Vite 吐的是 S6.5 之后的 ProfileView（含档案页接口）" "yes" \
    "$(curl -s "$VITE/src/student/views/ProfileView.vue" | grep -q 'setProfileBadge' && echo yes || echo no)"
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
  echo "--- 00-3 演示学生（缺则建、建后改密；每次跑前把 S6.5 的数据清零）---"
  local u
  for u in "$STU_A" "$STU_B" "$STU_C"; do
    local sid
    sid=$(sql "SELECT id FROM cet46.users WHERE username='$u';")
    if [ -z "$sid" ]; then
      printf '{"username":"%s","realName":"S6.5演示学生%s","password":"%sinit","role":"student","classId":%s,"target":"4"}' \
        "$u" "${u#S65}" "$u" "$CLASS_ID" > "$EVID/body-user-$u.json"
      api POST /admin/users "$TOKEN" "$EVID/body-user-$u.json" > "$EVID/resp-user-$u.json"
      check "建号 $u：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-user-$u.json")/$(code_of "$EVID/resp-user-$u.json")"
      local t
      t=$(login_token "$u" "${u}init")
      check "$u 初始密码能登录" "yes" "$([ -n "$t" ] && echo yes || echo no)"
      if [ "$u" != "$STU_C" ]; then chpwd "$u" "$t" "${u}init" "$STU_PWD2"; fi
    fi
    if [ "$u" = "$STU_C" ]; then
      # S65C 故意留在「首登未改密」状态：用来验 40302 门禁。
      # 建号时写的初始密码就是 $STU_C_INIT，之后从不改密，所以重跑也还能用它登录。
      check "$u 处于首登未改密状态（$STU_C_INIT 能登录）" "yes" \
        "$([ -n "$(login_token "$u" "$STU_C_INIT")" ] && echo yes || echo no)"
      # 「未改密」不落库成布尔列，而是 pwd_hash 的前缀 init$（见 auth.IsInitialPassword）
      check "$u pwd_hash 带 init\$ 前缀（首登未改密标记）" "init\$" \
        "$(sql "SELECT LEFT(pwd_hash,5) FROM cet46.users WHERE username='$STU_C';")"
      continue
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
                              (SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$sid2),'/',
                              (SELECT COUNT(*) FROM cet46.diagnoses WHERE user_id=$sid2));")
    check "$u 进度已清零（attempts/answers/xp/wrong/diagnoses 全 0）" "0/0/0/0/0" "$zero"
    check "$u 目标回四级（users.target=4）" "4" "$(sql "SELECT target FROM cet46.users WHERE id=$sid2;")"
    if [ "$zero" != "0/0/0/0/0" ]; then
      echo "!! 演示数据没清干净，后面的断言会全部建在脏数据上——中止本次实跑，先查复位语句。"
      exit 9
    fi
  done
  echo
  echo "--- 00-4 底账快照（99 要拿来比：S6.5 只写演示学生的行，不动表结构/题库/其他人）---"
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
  check "表数仍是 17（S6.5 不加表：档案页只读现成的五张表）" "17" \
    "$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';")"
  check "列数仍是 128（S6.5 不改列：等级/画像都不落库）" "128" \
    "$(sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46';")"
  check "题库仍是 4 单元 / 24 关 / 206 题" "4/24/206" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.units),'/',
                          (SELECT COUNT(*) FROM cet46.levels),'/',
                          (SELECT COUNT(*) FROM cet46.questions));")"
  check "四级题库 173 题 / 六级题库 33 题（画像取哪一套由目标决定）" "173/33" \
    "$(sql "SELECT CONCAT(SUM(band=4),'/',SUM(band=6)) FROM cet46.questions;")"
}

# ================================================================ 01/02 静态门禁
step_01_gotest() {
  step "01 go test ./... -count=1（全包；S6.5 新增画像/错题本/曲线的回归）"
  cd "$SRV" || exit 1
  local out
  out=$(go test ./... -count=1 2>&1)
  echo "$out"
  echo
  echo "--- 统计 ---"
  echo "PASS 行数：$(printf '%s\n' "$out" | grep -ac '^ok')"
  check "go test 无 FAIL" "0" "$(printf '%s\n' "$out" | grep -ac '^FAIL' || true)"
  check "go test 无构建错误" "0" "$(printf '%s\n' "$out" | grep -ac 'build failed' || true)"
  check "profile 相关包都在通过列表里" "2" \
    "$(printf '%s\n' "$out" | grep -aE 'internal/(quiz|router)' | grep -ac '^ok' || true)"
}

step_02_verify() {
  step "02 scripts/verify.sh（等价 CI：gofmt / go vet / go test / go build / eslint / 前端 build）"
  cd "$ROOT" || exit 1
  bash scripts/verify.sh 2>&1 | tail -60
  local rc=${PIPESTATUS[0]}
  check "verify.sh 退出码 0" "0" "$rc"
}

# ================================================================ 03 数据准备（计划内作答）
step_03_seed() {
  step "03 数据准备：把 $STU_A 的 24 关按计划打完（含 2 道故意错题）+ 2 次诊断 + 5 关流水回拨到过去几周"
  cd "$EVID" || exit 1
  python profile-seed.py --user "$STU_A" --password "$STU_PWD2" --tag seed
}

# ================================================================ 04 三方对拍（补题前）
step_04_reconcile_pre() {
  step "04 验收①②③（补题前）：手算 × SQL × 接口三方对拍（六维 / 错题本 / 曲线 / 概览）"
  cd "$EVID" || exit 1
  python profile-reconcile.py --user "$STU_A" --password "$STU_PWD2" --tag seed --phase pre
}

# ================================================================ 05 真浏览器（有提醒条 + 红点）
step_05_browser_full() {
  step "05 验收①②③（页面侧）：真浏览器 390×844 打开档案页，页面画出来的数逐项对齐接口回执 + 截图"
  cd "$EVID" || exit 1
  python profile-e2e.py --mode full --user "$STU_A" --password "$STU_PWD2" --tag s65
}

# ================================================================ 06 补回错题（掌握标记 + 提醒熄灭）
step_06_mastery() {
  step "06 推送形态回归：重刷那两关答对 → wrong_book 标 mastered（不改 last_at）→ 提醒条与红点熄灭"
  cd "$EVID" || exit 1
  python profile-e2e.py --mode mastery --user "$STU_A" --password "$STU_PWD2" --tag seed
}

# ================================================================ 07 补题后再对拍一次
step_07_reconcile_post() {
  step "07 验收①②③（补题后）：同一套对拍再跑一遍（数据变了，口径不能变）"
  cd "$EVID" || exit 1
  python profile-reconcile.py --user "$STU_A" --password "$STU_PWD2" --tag seed --phase post
}

# ================================================================ 08 空态与门禁
step_08_empty_auth() {
  step "08 空态与门禁：新学生 S65B 的档案页空态（390×844）+ 401/40302/同学隔离"
  cd "$EVID" || exit 1
  python profile-e2e.py --mode empty --user "$STU_B" --password "$STU_PWD2" --tag empty
  echo
  python profile-e2e.py --mode auth --user "$STU_A" --password "$STU_PWD2" --peer "$STU_B" \
    --peer-password "$STU_PWD2" --init-user "$STU_C" --init-password "$STU_C_INIT" --tag auth
}

# ================================================================ 09 截图与断言汇总
step_09_shots() {
  step "09 证据清点：截图逐张校验（真实尺寸 + 同场景内两两不同）+ 各场景断言数汇总"
  cd "$EVID" || exit 1
  python - "$EWIN" <<'PY'
import glob
import hashlib
import json
import os
import struct
import sys

ev = sys.argv[1]


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24])


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


bad = []
# 每个场景要有的证据，逐条点名（缺一张就是缺证据，不能靠"文件数>0"糊过去）
WANT = {
    's65': ['top', 'ability', 'trend', 'wrongbook', 'wrongbook-expanded', 'navbar', 'map', 'page'],
    'empty': ['top', 'ability', 'trend', 'wrongbook', 'navbar', 'page'],
}
for tag, names in sorted(WANT.items()):
    print('--- 场景 {} 截图 ---'.format(tag))
    seen = {}
    for n in names:
        p = os.path.join(ev, 'shots', 'shot-{}-{}.png'.format(tag, n))
        if not os.path.exists(p):
            bad.append('缺 screenshot：shot-{}-{}.png'.format(tag, n))
            print('%-34s 缺失' % os.path.basename(p))
            continue
        w, h = png_size(p)
        hh = md5(p)
        seen.setdefault(hh, []).append(n)
        kind = '整页' if n == 'page' else '元素/视口'
        print('%-34s %-8s %sx%s  md5 %s' % (os.path.basename(p), kind, w, h, hh[:8]))
        if w > 390:
            bad.append('%s-%s 宽 %s > 390' % (tag, n, w))
        if n == 'page':
            if w != 390:
                bad.append('shot-%s-page 整页截图应 390 宽，实际 %s' % (tag, w))
            if h <= 844:
                bad.append('shot-%s-page 整页截图只有 %s 高（≤ 一屏 844）：说明拍到的还是一屏，'
                           '内层滚动容器没被拍全' % (tag, h))
        elif h < 40:
            bad.append('shot-%s-%s 高度 %s 太小，不像一块内容' % (tag, n, h))
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    if dup:
        for hh, names_dup in dup.items():
            bad.append('场景 %s 有 %d 张截图字节完全相同（%s）：等于只有一张证据'
                       % (tag, len(names_dup), '、'.join(names_dup)))
    print('本场景 {} 张截图 · 去重后 {} 张'.format(len(names), len(seen)))
print('SHOTS_OK' if not bad else 'SHOTS_MISMATCH ' + '；'.join(bad))
PY
  echo
  echo "--- 09-2 各场景断言数（来自 e2e/profile-*.json）---"
  python - "$EWIN" <<'PY'
import glob
import json
import os
import sys

ev = sys.argv[1]
tot, bad = 0, []
for p in sorted(glob.glob(os.path.join(ev, '*.json'))):
    name = os.path.basename(p)
    if not (name.startswith('e2e-') or name.startswith('profile-')):
        continue
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001
        print('%-34s 读不动：%s' % (name, exc))
        continue
    if 'checks' not in d:
        continue
    n, f = len(d['checks']), len(d.get('fails') or [])
    tot += n
    if f:
        bad.append(name)
    print('%-34s %4d 条断言 · 失败 %d 条 · %s' % (name, n, f, '✅' if not f else '❌'))
print('合计 %d 条断言' % tot)
print('ALL_JSON_OK' if not bad else 'JSON_FAILS ' + '；'.join(bad))
PY
}

# ================================================================ 99 汇总与底账回归
step_99_summary() {
  step "99 收尾：编号日志逐条点名 + 底账回归（题库/表结构/账号）"
  echo "--- 99-1 编号日志 ---"
  local i
  for i in "${!STEP_NAMES[@]}"; do
    local n="${STEP_NAMES[$i]}"
    case "$n" in 99-*) continue;; esac
    if [ ! -f "$EVID/$n.log" ]; then echo "$(printf '%-20s' "$n") [NG] 日志缺失"; continue; fi
    if [ "${STEP_RC[$i]}" = 0 ] && [ "${STEP_FAILS[$i]}" = 0 ]; then
      echo "$(printf '%-20s' "$n") [OK] 退出码 0 · 失败标记 0"
    else
      echo "$(printf '%-20s' "$n") [NG] 退出码 ${STEP_RC[$i]} · 失败标记 ${STEP_FAILS[$i]}"
    fi
  done
  echo
  echo "--- 99-2 底账回归（题库与表结构必须一字未动）---"
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
  echo "--- 99-3 演示数据的最终形态（故意留着：三个数据面的证据在库里）---"
  sql "SELECT u.username,
              (SELECT COUNT(*) FROM cet46.attempts a WHERE a.user_id=u.id) attempts,
              (SELECT COUNT(*) FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id WHERE a.user_id=u.id) answers,
              (SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger l WHERE l.user_id=u.id) xp,
              (SELECT COUNT(*) FROM cet46.wrong_book w WHERE w.user_id=u.id) wrong,
              (SELECT SUM(mastered) FROM cet46.wrong_book w WHERE w.user_id=u.id) mastered,
              (SELECT COUNT(*) FROM cet46.diagnoses d WHERE d.user_id=u.id) diags
       FROM cet46.users u WHERE u.username LIKE 'S65%' ORDER BY u.username;"
}

# ================================================================ 主流程
echo "S6.5 验收实跑开始：$(date '+%Y-%m-%d %H:%M:%S')"
curl -s -o /dev/null "$API/health" || { echo "!! Go 服务没起：先 cd server && go run ./cmd/server"; }
run_step 00-precheck step_00_precheck
run_step 01-gotest step_01_gotest
run_step 02-verify step_02_verify
run_step 03-seed step_03_seed
run_step 04-reconcile-pre step_04_reconcile_pre
run_step 05-browser-full step_05_browser_full
run_step 06-mastery step_06_mastery
run_step 07-reconcile-post step_07_reconcile_post
run_step 08-empty-auth step_08_empty_auth
run_step 09-shots step_09_shots
run_step 99-summary step_99_summary

echo
echo "############################################################"
echo "# S6.5 验收实跑结束：$(date '+%Y-%m-%d %H:%M:%S')"
echo "# 失败断言总数：$FAILS"
echo "# 编号日志：${STEP_NAMES[*]}"
echo "############################################################"
exit $(( FAILS > 0 ? 1 : 0 ))