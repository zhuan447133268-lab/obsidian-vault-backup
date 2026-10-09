#!/usr/bin/env bash
# S7 验收实跑（小队：组队/单人队 · 成员互见成绩 · 互相提醒 · 小队宝箱）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑；Go :8080（**含 S7 代码**）与 Vite :5174 已起；
#       班级 2024级英语1班（id=1）与 2024级英语9班（id=2）存在（S1/S2 建）；
#       题库 4 单元/24 关/206 题（只读不改）。
#
# 自建自清：只动演示学生 S7A/S7B/S7C/S7D/S7E 与他们的小队/成员/提醒/attempts/answers/xp 行；
# 题库指纹、17 张表的表数列数、单元/关/题数在 00 与 99 各算一次对比（S7 不加表、不改列、不动题库）。
# 演示数据故意保留（验收①②③的证据落在库里）；要清库跑 cleanup-demo.sh。
#
# 三个数据面的对拍口径（本阶段验收的核心）：
#   手算（plan-*.json：脚本按计划答了什么）× SQL 聚合（独立重写的周分桶/聚合）× 接口回执，
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
CLASS1='2024级英语1班'
CLASS2='2024级英语9班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'      # seed-teacher 打的初始密码
TEACHER_PWD2='Teacher@456'     # 改密后（S5/S6/S6.5 都在用）
STU_PWD2='S7demo2026'          # 演示学生改密后的密码
STU_C_INIT='S65Cinit'          # S65C 故意不改密：验 40302 门禁
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
run_step() { # run_step 05-browser-full step_05_browser_full
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
  if [ "$rc" != 0 ] || [ "$nf" != 0 ]; then tail -40 "$log"; fi
}

# ================================================================ 00 环境与底账
step_00_precheck() {
  step "00 S7 验收前置：服务可达 + 演示学生就位 + 底账快照"
  # 截图与断言 JSON 每跑一次全部重生成：混着上一跑的旧文件（旧命名、旧帧、被覆盖过的 JSON）
  # 当证据是自欺——S6.5 就出现过 4 张截图字节完全一样、auth 模式把 full 模式的 JSON 覆盖掉。
  rm -rf "$EVID/shots"; mkdir -p "$EVID/shots"
  rm -f "$EVID"/e2e-*.json "$EVID"/team-*.json "$EVID"/plan-*.json
  echo "--- 00-1 服务可达 ---"
  check "MySQL 3307 可连" "1" "$(sql 'SELECT 1;')"
  check "Go 服务 /api/health 200" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$API/health")"
  check "Vite 5174 可达（学生端 5174：5173 被别的项目占着）" "200" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/")"
  check "小队页路由 /s/team 可达" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/s/team")"
  check "S7 新接口已挂上（未带 token → 401，不是 404）" "401" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$API/team/overview")"
  # 开发服务器吐旧缓存，会把「代码已改」测成「页面没变」。直接问 Vite 要 S7 改过的两个文件。
  check "Vite 吐的是 S7 之后的 TeamView（含小队接口调用）" "yes" \
    "$(curl -s "$VITE/src/student/views/TeamView.vue" | grep -q 'fetchTeamOverview' && echo yes || echo no)"
  check "Vite 吐的是 S7 之后的 BottomNav（含小队红点）" "yes" \
    "$(curl -s "$VITE/src/student/components/BottomNav.vue" | grep -q 'teamBadge' && echo yes || echo no)"
  echo
  echo "--- 00-2 教师账号就位（seed-teacher 打回初始密码再改密，S2 起的惯例）---"
  ( cd "$SRV" && go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD" > /dev/null 2>&1 )
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
  check "教师初始密码登录成功" "yes" "$([ -n "$TOKEN" ] && echo yes || echo no)"
  chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
  TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
  check "教师改密后再登录成功" "yes" "$([ -n "$TOKEN" ] && echo yes || echo no)"
  CLASS1_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS1';")
  CLASS2_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS2';")
  check "班级「$CLASS1」存在" "yes" "$([ -n "$CLASS1_ID" ] && echo yes || echo no)"
  check "班级「$CLASS2」存在（S7 跨班隔离用）" "yes" "$([ -n "$CLASS2_ID" ] && echo yes || echo no)"
  echo
  echo "--- 00-3 演示学生（缺则建、建后改密；每次跑前把 S7 的队/成员/提醒/成绩清零）---"
  # 先清 S7 数据（含队与提醒），再建号：清出来的是干净账
  sql "DELETE r FROM cet46.reminders r JOIN cet46.users u ON u.id=r.from_user WHERE u.username LIKE 'S7%';
       DELETE r FROM cet46.reminders r JOIN cet46.users u ON u.id=r.to_user WHERE u.username LIKE 'S7%';
       DELETE tm FROM cet46.team_members tm JOIN cet46.users u ON u.id=tm.user_id WHERE u.username LIKE 'S7%';
       DELETE t FROM cet46.teams t JOIN cet46.users u ON u.id=t.leader_id WHERE u.username LIKE 'S7%';
       DELETE aa FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S7%';
       DELETE l FROM cet46.xp_ledger l JOIN cet46.users u ON u.id=l.user_id WHERE u.username LIKE 'S7%';
       DELETE w FROM cet46.wrong_book w JOIN cet46.users u ON u.id=w.user_id WHERE u.username LIKE 'S7%';
       DELETE d FROM cet46.diagnoses d JOIN cet46.users u ON u.id=d.user_id WHERE u.username LIKE 'S7%';
       DELETE a FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S7%';
       UPDATE cet46.users SET target=4 WHERE username LIKE 'S7%';" >/dev/null
  local u cid
  for u in S7A S7B S7C S7D S7E; do
    case "$u" in
      S7D) cid="$CLASS2_ID";;
      *)   cid="$CLASS1_ID";;
    esac
    local sid
    sid=$(sql "SELECT id FROM cet46.users WHERE username='$u';")
    if [ -z "$sid" ]; then
      printf '{"username":"%s","realName":"S7演示学生%s","password":"%sinit","role":"student","classId":%s,"target":"4"}' \
        "$u" "${u#S7}" "$u" "$cid" > "$EVID/body-user-$u.json"
      api POST /admin/users "$TOKEN" "$EVID/body-user-$u.json" > "$EVID/resp-user-$u.json"
      check "建号 $u：HTTP 200 + code 0" "200/0" "$(http_of "$EVID/resp-user-$u.json")/$(code_of "$EVID/resp-user-$u.json")"
      local t
      t=$(login_token "$u" "${u}init")
      check "$u 初始密码能登录" "yes" "$([ -n "$t" ] && echo yes || echo no)"
      chpwd "$u" "$t" "${u}init" "$STU_PWD2"
    fi
    check "$u 演示密码 $STU_PWD2 能登录" "yes" \
      "$([ -n "$(login_token "$u" "$STU_PWD2")" ] && echo yes || echo no)"
    sid=$(sql "SELECT id FROM cet46.users WHERE username='$u';")
    local zero
    zero=$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts WHERE user_id=$sid),'/',
                              (SELECT COUNT(*) FROM cet46.team_members WHERE user_id=$sid),'/',
                              (SELECT COUNT(*) FROM cet46.reminders WHERE from_user=$sid),'/',
                              (SELECT COUNT(*) FROM cet46.xp_ledger WHERE user_id=$sid));")
    check "$u 进度与队伍已清零（attempts/team_members/reminders/xp 全 0）" "0/0/0/0" "$zero"
    if [ "$zero" != "0/0/0/0" ]; then
      echo "!! 演示数据没清干净，后面的断言会全部建在脏数据上——中止本次实跑，先查复位语句。"
      exit 9
    fi
  done
  echo
  echo "--- 00-4 底账快照（99 要拿来比：S7 只写演示学生的行，不动表结构/题库/其他人）---"
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
  check "表数仍是 17（S7 不加表：小队用现成的 teams/team_members/reminders）" "17" \
    "$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';")"
  check "列数仍是 128（S7 不改列）" "128" \
    "$(sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='cet46';")"
  check "题库仍是 4 单元 / 24 关 / 206 题" "4/24/206" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.units),'/',
                          (SELECT COUNT(*) FROM cet46.levels),'/',
                          (SELECT COUNT(*) FROM cet46.questions));")"
}

# ================================================================ 01/02 静态门禁
step_01_gotest() {
  step "01 go test ./... -count=1（全包；S7 新增小队口径/服务/路由的回归）"
  cd "$SRV" || exit 1
  local out
  out=$(go test ./... -count=1 2>&1)
  echo "$out"
  echo
  echo "--- 统计 ---"
  echo "PASS 行数：$(printf '%s\n' "$out" | grep -ac '^ok')"
  check "go test 无 FAIL" "0" "$(printf '%s\n' "$out" | grep -ac '^FAIL' || true)"
  check "go test 无构建错误" "0" "$(printf '%s\n' "$out" | grep -ac 'build failed' || true)"
  check "小队相关包（quiz/service/router）都在通过列表里" "3" \
    "$(printf '%s\n' "$out" | grep -aE 'internal/(quiz|service|router)' | grep -ac '^ok' || true)"
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
  step "03 数据准备：S7A 打 4/5+3/5（正好 70%）、S7B 打 3/5、S7C 一关不打；S7E 打 5/5（单人队 XP 照计的证据）；S7D 是 2 班学生、一关不打（跨班隔离用例）"
  cd "$EVID" || exit 1
  python team-seed.py --mode seed --tag seed
}

# ================================================================ 04 验收①②③ 接口侧主体
step_04_reconcile_pre() {
  step "04 验收①②③（接口侧）：建队/加入/单人队/宝箱条件/提醒落库/阈值边界 + 三方对拍"
  cd "$EVID" || exit 1
  python team-reconcile.py --phase pre
}

# ================================================================ 05 真浏览器：队长
step_05_browser_full() {
  step "05 验收①①（页面侧）：队长 S7A 真机 390×844 —— 页面画的数逐项对齐接口 + 真点提醒 + 截图"
  cd "$EVID" || exit 1
  python team-e2e.py --mode full --user S7A --password "$STU_PWD2" --tag full
}

# ================================================================ 06 真浏览器：队员
step_06_browser_member() {
  step "06 验收①（到达侧）：队员 S7B 收到队长提醒 → 页顶提醒条 + 底栏红点 → 点「知道了」熄灭"
  cd "$EVID" || exit 1
  python team-e2e.py --mode member --user S7B --password "$STU_PWD2" --tag member
}

# ================================================================ 07 真浏览器：未入队 → 单人队
step_07_browser_solo() {
  step "07 验收②（页面侧）：S7E 未入队态（含本班候选小队）→ 真填名字点建队 → 单人队（无加成/无宝箱/XP 照计）"
  cd "$EVID" || exit 1
  python team-e2e.py --mode solo --user S7E --password "$STU_PWD2" --tag solo
}

# ================================================================ 08 补打（把宝箱推过阈值）
step_08_topup() {
  step "08 补打：三人按解锁链继续打（每关全对），直到小队宝箱解锁为止（轮数不预写死）"
  cd "$EVID" || exit 1
  python team-seed.py --mode topup --tag topup
}

# ================================================================ 09 补打后再对拍
step_09_reconcile_post() {
  step "09 验收①③（补打后）：宝箱解锁 + 弱标记翻转 + 提醒不变式（数据变了，口径不能变）"
  cd "$EVID" || exit 1
  python team-reconcile.py --phase post
}

# ================================================================ 10 真浏览器：解锁态
step_10_browser_unlocked() {
  step "10 验收①（解锁态）：队长页宝箱「已解锁」+ 需要加油 0 人 + 已提醒态留存"
  cd "$EVID" || exit 1
  python team-e2e.py --mode unlocked --user S7A --password "$STU_PWD2" --tag unlocked
}

# ================================================================ 11 截图与断言汇总
step_11_shots() {
  step "11 证据清点：截图逐张校验（真实尺寸 + 同场景内两两不同 + 必备画面点名）+ 断言数汇总"
  cd "$EVID" || exit 1
  local rc1=0 rc2=0
  python - "$EWIN" <<'PY'
import hashlib
import json
import os
import struct
import sys
import traceback

ev = sys.argv[1]

# 每个场景必须有的画面（点名到张，缺一张就是缺证据，不能靠"文件数>0"糊过去）
MANDATORY = {
    'full': ['top', 'teamxp', 'weeksum', 'members', 'invite', 'navbar', 'page',
             'toast-invite', 'toast-remind', 'toast-nudgeall'],
    'member': ['top', 'pushbar-el', 'members', 'acked', 'navbar', 'page'],
    'solo': ['noteam-top', 'noteam-page', 'create', 'joincard', 'cands', 'solo-top', 'solo-teamxp',
             'solo-member', 'solo-page'],
    'unlocked': ['top', 'unlocked-xp', 'invite', 'weeksum', 'page'],
}


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24])


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


bad = []


def fail(msg):
    """每条缺陷都印成 [CHECK] … ❌：run_step 靠 ❌ 计数，只印自定义摘要等于没报错。"""
    bad.append(msg)
    print('[CHECK] {} ❌ 期望=合格 实际=不合格'.format(msg))


try:
    total = 0
    scenes = 0
    for tag in sorted(MANDATORY):
        # 截图清单以 e2e-team-<tag>.json 为准（脚本自己记的 shots），再点名必备画面：
        # 这样"新加了一张截图却忘了校验"和"脚本没拍到"都能被发现。
        meta = os.path.join(ev, 'e2e-team-{}.json'.format(tag))
        if not os.path.exists(meta):
            fail('缺场景断言 JSON e2e-team-{}.json（该场景没跑完＝没有页面证据）'.format(tag))
            continue
        scenes += 1
        listed = json.load(open(meta, encoding='utf-8')).get('extra', {}).get('shots') or []
        print('--- 场景 {}：JSON 记录 {} 张截图 ---'.format(tag, len(listed)))
        for name in sorted(set(listed)):
            if listed.count(name) > 1:
                fail('场景 {} 的清单里 {} 记了 {} 次（记账笔误：一张证据被记成多张）'
                     .format(tag, name, listed.count(name)))
        seen = {}
        for name in listed:
            p = os.path.join(ev, 'shots', name)
            if not os.path.exists(p):
                fail('JSON 里记了但磁盘上没有：{}'.format(name))
                continue
            w, h = png_size(p)
            hh = md5(p)
            seen.setdefault(hh, []).append(name)
            kind = '整页' if name.endswith('-page.png') else '元素/视口'
            print('%-40s %-8s %sx%-5s md5 %s' % (name, kind, w, h, hh[:8]))
            if w > 390:
                fail('{} 宽 {} > 390'.format(name, w))
            if name.endswith('-page.png'):
                if w != 390:
                    fail('{} 整页截图应 390 宽，实际 {}'.format(name, w))
                # 整页要有「一页纸」的体积；是否真覆盖了内层容器的全部内容，
                # 由 e2e 脚本按内容高度逐张断言（见 0x-browser-*.log 的「覆盖内层容器全部内容」）。
                if h < 500:
                    fail('{} 只有 {} 高，不像整页（内层滚动容器可能没被拍全）'.format(name, h))
            elif h < 40:
                fail('{} 高度 {} 太小，不像一块内容'.format(name, h))
        for name in MANDATORY[tag]:
            p = os.path.join(ev, 'shots', 'shot-{}-{}.png'.format(tag, name))
            if not os.path.exists(p):
                fail('缺必备画面：shot-{}-{}.png'.format(tag, name))
        dup = {k: sorted(set(v)) for k, v in seen.items() if len(set(v)) > 1}
        for hh, names in dup.items():
            fail('场景 {} 有 {} 张截图字节完全相同（{}）：等于只有一张证据'
                 .format(tag, len(names), '、'.join(names)))
        print('本场景 {} 张 · 去重后 {} 张'.format(len(listed), len(seen)))
        total += len(listed)
    if scenes != len(MANDATORY):
        fail('只清点到 {} 个场景，应为 {} 个'.format(scenes, len(MANDATORY)))
    print('截图合计 {} 张'.format(total))
    if bad:
        print('SHOTS_MISMATCH {} 条'.format(len(bad)))
    else:
        print('[CHECK] 截图逐张校验（{} 张 / {} 场景：真实尺寸 + 同场景两两不同 + 必备画面点名）'
              ' ✅ 期望=SHOTS_OK 实际=SHOTS_OK'.format(total, scenes))
        print('SHOTS_OK')
except Exception as exc:  # noqa: BLE001
    traceback.print_exc()
    fail('截点清点脚本自身异常（{}）：本次清点不可信'.format(exc))
    print('SHOTS_MISMATCH 内部异常')
    sys.exit(2)
sys.exit(1 if bad else 0)

PY
  rc1=$?
  echo
  echo "--- 11-2 各场景断言数（来自 e2e-team-*.json / team-*.json）---"
  python - "$EWIN" <<'PY'
import glob
import json
import os
import sys

ev = sys.argv[1]
tot, bad = 0, []
for p in sorted(glob.glob(os.path.join(ev, '*.json'))):
    name = os.path.basename(p)
    if not (name.startswith('e2e-') or name.startswith('team-')):
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
  rc2=$?
  return $(( rc1 || rc2 ))
}

# ================================================================ 99 汇总与底账回归
step_99_summary() {
  step "99 收尾：编号日志逐条点名 + 底账回归（题库/表结构/账号）"
  echo "--- 99-1 编号日志 ---"
  local i
  for i in "${!STEP_NAMES[@]}"; do
    local n="${STEP_NAMES[$i]}"
    case "$n" in 99-*) continue;; esac
    if [ ! -f "$EVID/$n.log" ]; then echo "$(printf '%-22s' "$n") [NG] 日志缺失"; continue; fi
    if [ "${STEP_RC[$i]}" = 0 ] && [ "${STEP_FAILS[$i]}" = 0 ]; then
      echo "$(printf '%-22s' "$n") [OK] 退出码 0 · 失败标记 0"
    else
      echo "$(printf '%-22s' "$n") [NG] 退出码 ${STEP_RC[$i]} · 失败标记 ${STEP_FAILS[$i]}"
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
  echo "--- 99-3 演示数据的最终形态（故意留着：验收①②③的证据在库里）---"
  sql "SELECT u.username, u.class_id,
              (SELECT COUNT(*) FROM cet46.attempts a WHERE a.user_id=u.id) attempts,
              (SELECT COALESCE(SUM(l.delta),0) FROM cet46.xp_ledger l WHERE l.user_id=u.id) xp,
              (SELECT COUNT(*) FROM cet46.team_members tm WHERE tm.user_id=u.id AND tm.left_at IS NULL) in_team,
              (SELECT COUNT(*) FROM cet46.reminders r WHERE r.from_user=u.id) sent,
              (SELECT COUNT(*) FROM cet46.reminders r WHERE r.to_user=u.id) got
       FROM cet46.users u WHERE u.username LIKE 'S7%' ORDER BY u.username;"
  echo
  echo "--- 99-4 小队最终形态 ---"
  sql "SELECT t.id, t.name, t.emoji, u.username leader,
              (SELECT COUNT(*) FROM cet46.team_members tm WHERE tm.team_id=t.id AND tm.left_at IS NULL) members,
              (SELECT COUNT(*) FROM cet46.reminders r WHERE r.team_id=t.id) reminders
       FROM cet46.teams t JOIN cet46.users u ON u.id=t.leader_id
       WHERE u.username LIKE 'S7%' ORDER BY t.id;"
}

# ================================================================ 主流程
echo "S7 验收实跑开始：$(date '+%Y-%m-%d %H:%M:%S')"
curl -s -o /dev/null "$API/health" || { echo "!! Go 服务没起：先 cd server && ./server-s7.exe（或 go run ./cmd/server）"; }
run_step 00-precheck step_00_precheck
run_step 01-gotest step_01_gotest
run_step 02-verify step_02_verify
run_step 03-seed step_03_seed
run_step 04-reconcile-pre step_04_reconcile_pre
run_step 05-browser-full step_05_browser_full
run_step 06-browser-member step_06_browser_member
run_step 07-browser-solo step_07_browser_solo
run_step 08-topup step_08_topup
run_step 09-reconcile-post step_09_reconcile_post
run_step 10-browser-unlocked step_10_browser_unlocked
run_step 11-shots step_11_shots
run_step 99-summary step_99_summary

echo
echo "############################################################"
echo "# S7 验收实跑结束：$(date '+%Y-%m-%d %H:%M:%S')"
echo "# 失败断言总数：$FAILS"
echo "# 编号日志：${STEP_NAMES[*]}"
echo "############################################################"
exit $(( FAILS > 0 ? 1 : 0 ))