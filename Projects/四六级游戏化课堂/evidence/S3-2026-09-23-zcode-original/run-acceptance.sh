#!/usr/bin/env bash
# S3 验收实跑（答题引擎后端：取卷 / 判分 / XP 账本 / 错题本 / 解锁链 / 诊断卷）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑（S0 建），8080 端口空闲，班级 2024级英语1班 里已有第 3/9/10/11 周的关卡。
# 自建自清：只创建自己的演示学生（S3V4/S3V6）、他们的流水，以及 08b 用来实测解锁链与 Boss 710 分制的
# 第 12 周演示单元（跑完连单元带关卡题目一起删）；不动题库原有 206 题、不动真实账号密码
#（T0001 会被 seed-teacher 打回初始密码再改密，这是 S2 就在用的惯例，复跑前重跑一次即可）。
set -uo pipefail

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE=http://127.0.0.1:8080
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'
TEACHER_PWD2='Teacher@456'
STU4=S3V4
STU6=S3V6
STU_PWD='Student@2024'
STU_PWD2='Student@2025'
# 演示层：第 9 周「阅读 · 段落匹配」= match 题型。S3 决策：段落编号带语义，match 不洗选项，
# 所以验收脚本能像前端一样预知正确选项的展示下标（见 03 号日志的「展示序=题库序」实测）。
LV_MATCH=37
LV_SHUFFLE=25   # 第 3 周「高频词」= vocab，选项会洗序（用来证明洗牌真的在生效）
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
sql() { "${MYSQL[@]}" -e "$1"; }

cd "$SRV" || exit 1
if curl -sS -o /dev/null "$BASE/api/health" 2>/dev/null; then
  echo "!! $BASE 已被占用（可能上一轮的服务还在跑），先停掉再复跑" >&2
  exit 1
fi

# ================================================================ 00 动库前现状
{
  step "00 前置：MySQL 3307 现状 + 本阶段要动的五张表起点（应为全 0）"
  sql "SELECT VERSION() AS mysql_version;"
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
  echo
  echo "--- 演示班级 $CLASS_NAME 的关卡底账（4 个单元：第 3/9/10/11 周；9/10/11 周只有四级题）---"
  sql "SELECT u.week_no AS 周, l.seq AS 序号, l.name AS 关卡, l.type AS 类型, l.time_limit AS 限时秒, l.is_boss AS Boss,
         (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id=l.id AND q.band='4') AS 四级题,
         (SELECT COUNT(*) FROM cet46.questions q WHERE q.level_id=l.id AND q.band='6') AS 六级题
       FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id
       WHERE u.class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME')
       ORDER BY u.week_no, l.seq;"
  echo
  echo "--- 演示关卡 $LV_MATCH：match 题型，答案下标可从题库读出（脚本据此扮演「知道答案的学生」）---"
  sql "SELECT id, answer_idx, JSON_LENGTH(options_json) AS 选项数 FROM cet46.questions WHERE level_id=$LV_MATCH ORDER BY id;"
  echo
  echo "--- 幂等清理：先删掉上一轮可能残留的演示学生及其流水、以及 08b 自建的演示单元 ---"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6')));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.wrong_book WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.diagnoses WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.users WHERE username IN ('$STU4','$STU6');"
  sql "DELETE FROM cet46.questions WHERE level_id IN (SELECT id FROM cet46.levels WHERE unit_id IN (SELECT id FROM cet46.units WHERE week_no=12 AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME')));
       DELETE FROM cet46.levels WHERE unit_id IN (SELECT id FROM cet46.units WHERE week_no=12 AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME'));
       DELETE FROM cet46.units WHERE week_no=12 AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME');"
  echo "清理后演示学生数（应为 0）：$(sql "SELECT COUNT(*) FROM cet46.users WHERE username IN ('$STU4','$STU6');")"
  echo "清理后单元/关卡/题目数（应为 4/24/206）：$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.units),'/',(SELECT COUNT(*) FROM cet46.levels),'/',(SELECT COUNT(*) FROM cet46.questions));")"
} > "$EVID/00-db-before.log" 2>&1

# ================================================================ 01 数值表单测（验收① 红线）
{
  step "01 验收①：§6 数值表逐条 Go 单测（含速度加成三组边界：秒答 / 压线 / 超时）"
  go test ./internal/quiz/ -v 2>&1 | tr -d '\000' | grep -E '^(=== RUN|--- PASS|--- FAIL|ok|FAIL)'
  echo
  echo "--- 速度加成三组边界（同一条用例里锁死：秒答 0ms→+10、压线 60000ms→0、超时 90000ms→0）---"
  go test ./internal/quiz/ -run 'TestSpeedBonus|TestScoreAnswer|TestSettle|TestSettleBoss' -v 2>&1 | tr -d '\000' | grep -E '^(--- PASS|--- FAIL|    engine_test)'
} > "$EVID/01-numeric-table.log" 2>&1

# ================================================================ 02 起真服务
{
  step "02 启动 Go 服务（真 MySQL 3307），供接口实录"
} > "$EVID/02-server-start.log" 2>&1
go run ./cmd/server >> "$EVID/02-server-start.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
  sleep 1
  curl -sS "$BASE/api/health" > /dev/null 2>&1 && break
done
{
  echo "--- GET /api/health ---"
  curl -sS -w $'\n[HTTP %{http_code}]\n' "$BASE/api/health"
  echo
  echo "--- S3 新增路由（启动日志里的路由表）---"
  grep -E 'quiz|diag' "$EVID/02-server-start.log" | grep -E 'GET|POST' || true
} >> "$EVID/02-server-start.log" 2>&1

# ---- 教师登录 + 自建演示学生（与 S2 同口径：seed-teacher 幂等重置密码 → 首登改密 → 再登录）
go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD" > /dev/null 2>&1
TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
CLASS_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS_NAME';")
for pair in "$STU4:4" "$STU6:6"; do
  stu="${pair%%:*}"; tgt="${pair##*:}"
  printf '{"username":"%s","realName":"S3演示学生%s","password":"%s","role":"student","classId":%s,"target":"%s"}' \
    "$stu" "$tgt" "$STU_PWD" "$CLASS_ID" "$tgt" > "$EVID/body-user-$stu.json"
  api POST /api/admin/users "$TOKEN" "$EVID/body-user-$stu.json" > "$EVID/resp-user-$stu.json"
  T=$(login_token "$stu" "$STU_PWD")
  chpwd "$stu" "$T" "$STU_PWD" "$STU_PWD2"
  T=$(login_token "$stu" "$STU_PWD2")
  eval "TOKEN_$stu=$T"
done
TOKEN4="$TOKEN_S3V4"
TOKEN6="$TOKEN_S3V6"

# ================================================================ 03 取卷（验收③）
{
  step "03 验收③：同一 attempt 反复取卷，seed 与题目顺序不变；选项洗牌真的在洗；答案零泄露"
  echo "--- 03-0 演示学生 $STU4（四级）第 1 次取第 3 周第 1 关（vocab 5 题，选项会洗序）---"
  api GET "/api/quiz/paper?level=$LV_SHUFFLE" "$TOKEN4" > "$EVID/resp-paper-25-1.json"
  head -1 "$EVID/resp-paper-25-1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("attemptId =", d["attemptId"], "| shuffleSeed =", d["shuffleSeed"], "| resumed =", d["resumed"], "| 爱心 =", d["lives"])
print("关内题目 id 顺序 =", [q["id"] for q in d["questions"]])
print("每题的选项展示顺序（前 3 个选项的前 24 字）：")
for q in d["questions"]:
    print("  题", q["id"], "(", q["type"], ")：", [o[:24] for o in q["options"]][:3], "…共", len(q["options"]), "项")
print("题干开头：", d["questions"][0]["stem"][:60])
'
  A1=$(pyget data.attemptId < "$EVID/resp-paper-25-1.json")
  S1=$(pyget data.shuffleSeed < "$EVID/resp-paper-25-1.json")
  echo
  echo "--- 03-1 第 2 次取同一关（应复用 attempt=$A1、seed=$S1、题序一致）---"
  api GET "/api/quiz/paper?level=$LV_SHUFFLE" "$TOKEN4" > "$EVID/resp-paper-25-2.json"
  head -1 "$EVID/resp-paper-25-2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("attemptId =", d["attemptId"], "| shuffleSeed =", d["shuffleSeed"], "| resumed =", d["resumed"])
print("关内题目 id 顺序 =", [q["id"] for q in d["questions"]])
'
  A2=$(pyget data.attemptId < "$EVID/resp-paper-25-2.json")
  S2=$(pyget data.shuffleSeed < "$EVID/resp-paper-25-2.json")
  check "两次取卷复用同一 attempt" "$A1" "$A2"
  check "两次取卷 seed 一致" "$S1" "$S2"
  check "两次取卷题目顺序一致（id 序列）" \
    "$(head -1 "$EVID/resp-paper-25-1.json" | python -c 'import sys,json; print(",".join(str(q["id"]) for q in json.loads(sys.stdin.read())["data"]["questions"]))')" \
    "$(head -1 "$EVID/resp-paper-25-2.json" | python -c 'import sys,json; print(",".join(str(q["id"]) for q in json.loads(sys.stdin.read())["data"]["questions"]))')"
  echo
  echo "--- 03-2 选项洗牌举证：把下发选项跟题库 options_json 逐题比序 ---"
  {
    echo "==PAPER=="; cat "$EVID/resp-paper-25-1.json"
    echo "==KEY2=="
    sql "SELECT id, type, options_json FROM cet46.questions WHERE level_id=$LV_SHUFFLE ORDER BY id;"
  } | python -c '
import sys, json
raw = sys.stdin.read().split("\n")
paper = None; rows = []
mode = None
for line in raw:
    if line == "==PAPER==": mode = "paper"; continue
    if line == "==KEY2==": mode = "key"; continue
    if mode == "paper" and line.startswith("{"): paper = json.loads(line)["data"]
    elif mode == "key" and "\t" in line:
        qid, typ, opts = line.split("\t", 2); rows.append((int(qid), typ, json.loads(opts)))
bank = {r[0]: r for r in rows}
same = diff = 0
for q in paper["questions"]:
    typ, bank_opts = bank[q["id"]][1], bank[q["id"]][2]
    ok = q["options"] == bank_opts
    same += ok; diff += (not ok)
    print("  题", q["id"], "类型=", typ, "展示序==题库序：", ok, "（", len(q["options"]), "项）")
print(f"结论：{same} 题同序 / {diff} 题被洗过（vocab 会洗、match 不洗）")
'
  echo
  echo "--- 03-3 断点续答：先交 1 题（只看现场是否保住；选项被洗过、正确项下标不可预知，"
  echo "        所以故意给单选题报 4 个下标——判分要求序列等长，这题必然判错、必然 0 XP，"
  echo "        后面的绝对分值（330 / 805）才不会被这次探针的随机对错污染）---"
  head -1 "$EVID/resp-paper-25-1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print(json.dumps({"attemptId": d["attemptId"],
                  "answers": [{"questionId": d["questions"][0]["id"], "pickedIdx": "0,1,2,3"}]}, ensure_ascii=False))
' > "$EVID/body-submit-probe.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-probe.json" > "$EVID/resp-submit-probe.json"
  head -1 "$EVID/resp-submit-probe.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
f = d["feedback"][0]
print("status =", d["status"], "| 进度 =", d["progress"], "| 本题对错 =", f["isCorrect"], "| 正确项展示下标 =", f["correctIdx"], "| 本题 XP =", f["xp"])
'
  check "探针这块答错 = 0 分（答错不倒扣）" "0" "$(head -1 "$EVID/resp-submit-probe.json" | pyget data.feedback.0.xp.base)"
  check "探针后账本仍为 0（答错不落任何流水）" "0" "$(sql "SELECT COALESCE(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');")"
  echo
  echo "--- 03-4 再取一次卷：应 resumed=true，seed 与题序仍不变，且带回答回执 ---"
  api GET "/api/quiz/paper?level=$LV_SHUFFLE" "$TOKEN4" > "$EVID/resp-paper-25-3.json"
  head -1 "$EVID/resp-paper-25-3.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("attemptId =", d["attemptId"], "| shuffleSeed =", d["shuffleSeed"], "| resumed =", d["resumed"])
print("已回答回执 =", d["answered"])
print("题目 id 顺序 =", [q["id"] for q in d["questions"]])
'
  check "断点续答 resumed=true" "True" "$(pyget data.resumed < "$EVID/resp-paper-25-3.json")"
  check "断点续答 seed 不变" "$S1" "$(pyget data.shuffleSeed < "$EVID/resp-paper-25-3.json")"
  echo
  echo "--- 03-5 答案零泄露：取卷响应里不得出现 answerIdx / exp / tip / knowledgeTag ---"
  python -c '
import sys, json
body = sys.stdin.read().strip().splitlines()[0]
d = json.loads(body)
def keys(o, acc):
    if isinstance(o, dict):
        for k, v in o.items(): acc.add(k); keys(v, acc)
    elif isinstance(o, list):
        for v in o: keys(v, acc)
    return acc
seen = keys(d["data"], set())
banned = ("answerIdx", "exp", "tip", "knowledgeTag", "optionsJson", "answer_idx")
hit = sorted(k for k in banned if k in seen)
print("data 下出现过的键：", sorted(seen))
print("禁字段命中（按 JSON 键判定）：", hit if hit else "无 ✅")
' < "$EVID/resp-paper-25-3.json"
} > "$EVID/03-paper.log" 2>&1

# ================================================================ 04 进关预告 + 解锁链 + 分套（验收⑥）
{
  step "04 验收⑥：关卡列表带「题量 + 预计分钟」，解锁链线性，分套过滤正确"
  dump_levels() { # dump_levels 学生 username token
    python -c '
import sys, json
d = json.loads(sys.stdin.read().strip().splitlines()[0])["data"]
print("xpTotal =", d["xpTotal"], "| recommendedLevelId =", d["recommendedLevelId"], "| 关卡数 =", d["total"])
print("  周   序  关卡                            题量  预告分钟  解锁  通关   星  打过  首刷")
for it in d["items"]:
    fr = it["firstResult"]
    first = "—" if fr is None else str(fr["correct"]) + "/" + str(fr["total"]) + " " + str(fr["stars"]) + "星 #" + str(fr["attemptId"])
    fb = "✅" if it["unlocked"] else "🔒"
    ok = "是" if it["cleared"] else "否"
    print("  %3d  %3d  %-28s  %4d  %8d  %4s  %4s  %3d  %4d  %s"
          % (it["weekNo"], it["seq"], it["name"], it["questionCount"], it["estimatedMinutes"], fb, ok, it["stars"], it["attempts"], first))
print("--- 单元合计（题目量 / 预告分钟）---")
for u in d["units"]:
    print("  第 %2d 周 %s：%d 关 / %d 题 / 约 %d 分钟 / 已通关 %d"
          % (u["weekNo"], u["name"], u["levelCount"], u["questionCount"], u["estimatedMinutes"], u["clearedCount"]))
' "$1"
  }
  echo "--- 04-0 四级学生 $STU4（第 3 周 6 关 + 9/10/11 周四级真题）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-before.json"
  head -1 "$EVID/resp-levels-$STU4-before.json" | dump_levels "$STU4"
  echo
  echo "--- 04-1 六级学生 $STU6（同一批关卡，题量按自身分套算：9/10/11 周只有四级题 → 0 题）---"
  api GET /api/quiz/levels "$TOKEN6" > "$EVID/resp-levels-$STU6-before.json"
  head -1 "$EVID/resp-levels-$STU6-before.json" | dump_levels "$STU6"
  echo
  echo "--- 04-2 逐条校验（四级学生）---"
  jq() { python -c '
import sys, json
d = json.loads(sys.stdin.read().strip().splitlines()[0])["data"]
path = sys.argv[1].split(".")
for p in path:
    d = d[int(p)] if p.isdigit() else d[p]
print(d)
' "$1"; }
  echo "第 3 周第 1 关（题量 5 / 预告 7 分钟 / 解锁 / 未通关 / 无首刷）："
  head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.0.questionCount > /dev/null
  check "第 1 关题量=5" "5" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.0.questionCount)"
  check "第 1 关预告=7 分钟（题数+2）" "7" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.0.estimatedMinutes)"
  check "第 1 关已解锁" "True" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.0.unlocked)"
  check "第 2 关锁着（线性链：前一关未通关）" "False" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.1.unlocked)"
  check "Boss 关题量=8、预告=10 分钟" "8/10" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.5.questionCount)/$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.5.estimatedMinutes)"
  check "开局 xpTotal=0" "0" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq xpTotal)"
  check "第 1 关首刷成绩为空（还没打过，python 空值显示 None）" "None" "$(head -1 "$EVID/resp-levels-$STU4-before.json" | jq items.0.firstResult)"
  echo
  echo "--- 04-3 逐条校验（六级学生：第 3 周每关 5 题，9/10/11 周 0 题不参与链条）---"
  check "六级学生第 3 周第 1 关题量=5" "5" "$(head -1 "$EVID/resp-levels-$STU6-before.json" | jq items.0.questionCount)"
  check "六级学生第 9 周第 1 关题量=0（该套无六级题）" "0" "$(head -1 "$EVID/resp-levels-$STU6-before.json" | jq items.6.questionCount)"
  check "空关卡不解锁（地图置灰，不参与链条）" "False" "$(head -1 "$EVID/resp-levels-$STU6-before.json" | jq items.6.unlocked)"
  check "六级学生的第 3 周第 2 关仍锁着" "False" "$(head -1 "$EVID/resp-levels-$STU6-before.json" | jq items.1.unlocked)"
  echo
  echo "第 3 周单元合计（四级 33 题 / 约 45 分钟）："
  head -1 "$EVID/resp-levels-$STU4-before.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
u = d["units"][0]
print("  weekNo =", u["weekNo"], "| name =", u["name"], "| 关卡数 =", u["levelCount"],
      "| 题目量 =", u["questionCount"], "| 预告 =", u["estimatedMinutes"], "分钟 | 已通关 =", u["clearedCount"])
'
} > "$EVID/04-levels-forecast.log" 2>&1

# ================================================================ 05 账本权威 + 首刷（验收② + ⑤ 前半）
{
  step "05 验收②：XP 只认账本 —— 直改 attempts 不动总分；往账本塞一行，总分立刻动"
  echo "--- 05-0 用第 9 周「阅读 · 段落匹配」（match：展示序=题库序）跑一次 8/10 的首刷 ---"
  echo "        首刷口径：前 8 题答对、后 2 题答错（展示下标 = 题库 answer_idx，错项取 (answer+1) mod 选项数）"
  sql "SELECT id, answer_idx FROM cet46.questions WHERE level_id=$LV_MATCH ORDER BY id;" > "$EVID/answerkey-37.tsv"
  echo "  题库答案下标：$(tr '\n' ' ' < "$EVID/answerkey-37.tsv")"
  api GET "/api/quiz/paper?level=$LV_MATCH" "$TOKEN4" > "$EVID/resp-paper-37-1.json"
  head -1 "$EVID/resp-paper-37-1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("attemptId =", d["attemptId"], "| seed =", d["shuffleSeed"], "| 题数 =", len(d["questions"]),
      "| 题序 =", [q["id"] for q in d["questions"]])
print("第 1 题选项数 =", len(d["questions"][0]["options"]), "（段落匹配的 A~L 段）")
'
  { echo "==PAPER=="; cat "$EVID/resp-paper-37-1.json"; echo "==KEY=="; cat "$EVID/answerkey-37.tsv"; } | python -c '
import sys, json
mode = None; paper = None; key = {}
for line in sys.stdin.read().split("\n"):
    if line == "==PAPER==": mode = "paper"; continue
    if line == "==KEY==": mode = "key"; continue
    if mode == "paper" and line.startswith("{"): paper = json.loads(line)["data"]
    elif mode == "key" and "\t" in line:
        qid, ans = line.split("\t")[:2]; key[int(qid)] = [int(x) for x in ans.split(",")]
answers = []
for i, q in enumerate(paper["questions"]):
    correct = key[q["id"]]
    picks = correct if i < 8 else [ (correct[0] + 1) % len(q["options"]) ]
    answers.append({"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)})
print(json.dumps({"attemptId": paper["attemptId"], "answers": answers}, ensure_ascii=False))
' > "$EVID/body-submit-37-round1.json"
  echo "  作答体：$(head -c 200 "$EVID/body-submit-37-round1.json")…"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-37-round1.json" > "$EVID/resp-submit-37-round1.json"
  head -1 "$EVID/resp-submit-37-round1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| 进度 =", d["progress"])
print("结算：正确率 =", s["ratio"], "| 星级 =", s["stars"], "| 710 分制 =", s["score710"],
      "| 本次 XP =", s["xpTotal"], "| 总分 =", s["xpTotalAll"], "| 首刷 =", s["firstClear"], "| 重刷 =", s["replay"])
print("XP 明细：", [(r["label"], r["delta"]) for r in s["xpRows"]])
print("后两题回执（应 false + 带正确项展示下标）：", [(f["questionId"], f["isCorrect"], f["correctIdx"]) for f in d["feedback"][-2:]])
'
  R1_STARS=$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.settlement.stars)
  R1_SCORE=$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.settlement.score710)
  R1_XP=$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.settlement.xpTotal)
  R1_ALL=$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.settlement.xpTotalAll)
  A_FIRST=$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.attemptId)
  check "首刷 8/10 → 两星" "2" "$R1_STARS"
  check "首刷 8/10 → 正确率 0.8" "0.8" "$(head -1 "$EVID/resp-submit-37-round1.json" | pyget data.settlement.ratio)"
  check "非 Boss 关不发 710 分制成绩单（任务书 §6：仅 Boss 卷 round(正确率×710)）" "0" "$R1_SCORE"
  check "首刷 XP = 160(基础)+140(连击)+30(通关) = 330" "330" "$R1_XP"
  check "总 XP（账本聚合）= 330" "330" "$R1_ALL"
  echo
  echo "--- 05-1 关卡列表立刻反映：xpTotal / 星级 / 首刷成绩 ---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-after1.json"
  head -1 "$EVID/resp-levels-$STU4-after1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
it = [x for x in d["items"] if x["id"] == int(sys.argv[1])][0]
print("xpTotal =", d["xpTotal"], "| 该关：通关 =", it["cleared"], "| 星 =", it["stars"], "| 打过 =", it["attempts"],
      "| 首刷 =", it["firstResult"])
' "$LV_MATCH"
  check "关卡列表 xpTotal=330" "330" "$(head -1 "$EVID/resp-levels-$STU4-after1.json" | pyget data.xpTotal)"
  echo
  echo "--- 05-2 验收② 动作一：直接改 attempts.xp_earned = 999999（绕过账本刷分）---"
  sql "UPDATE cet46.attempts SET xp_earned = 999999 WHERE id = $A_FIRST;"
  echo "库里这条 attempt 现在是："
  sql "SELECT id, level_id, correct, total, stars, score710, xp_earned, status, shuffle_seed FROM cet46.attempts WHERE id = $A_FIRST;"
  echo "接口读到的总分（应纹丝不动 = 330）："
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-cheat.json"
  check "改 attempts 后 xpTotal 不变" "330" "$(head -1 "$EVID/resp-levels-$STU4-cheat.json" | pyget data.xpTotal)"
  check "账本 SUM(delta) 不变" "330" "$(sql "SELECT COALESCE(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');")"
  echo
  echo "--- 05-3 验收② 动作二（反向）：往账本塞一行 +7 → 总分立刻变 337，删掉又回到 330 ---"
  sql "INSERT INTO cet46.xp_ledger (user_id, delta, reason, ref_type, ref_id, created_at)
       SELECT id, 7, 'answer_base', 'attempt', $A_FIRST, NOW(3) FROM cet46.users WHERE username='$STU4';"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-cheat2.json"
  check "账本 +7 → xpTotal=337" "337" "$(head -1 "$EVID/resp-levels-$STU4-cheat2.json" | pyget data.xpTotal)"
  sql "DELETE FROM cet46.xp_ledger WHERE reason='answer_base' AND delta=7 AND user_id=(SELECT id FROM cet46.users WHERE username='$STU4') ORDER BY id DESC LIMIT 1;"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-cheat3.json"
  check "删掉那行 → xpTotal 回到 330" "330" "$(head -1 "$EVID/resp-levels-$STU4-cheat3.json" | pyget data.xpTotal)"
  echo
  echo "--- 05-4 账本落库明细（本次闯关逐条可解释）---"
  sql "SELECT l.id, l.delta, l.reason, l.ref_type, l.ref_id, l.created_at FROM cet46.xp_ledger l
       WHERE l.user_id=(SELECT id FROM cet46.users WHERE username='$STU4') ORDER BY l.id;"
  sql "SELECT id, attempt_id, question_id, picked_idx, is_correct FROM cet46.attempt_answers
       WHERE attempt_id=$A_FIRST ORDER BY id;"
  echo
  echo "--- 05-5 解锁链推进：第 9 周第 5 关（段落匹配）通关后，同单元第 6 关应变为「已解锁」---"
  head -1 "$EVID/resp-levels-$STU4-after1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
for it in d["items"]:
    if it["weekNo"] == 9 and it["seq"] in (4, 5, 6, 7):
        print("  第 9 周第", it["seq"], "关", it["name"], "：解锁=", it["unlocked"], "通关=", it["cleared"], "首刷=", it["firstResult"] is not None)
'
  check "通关第 5 关后同单元第 6 关解锁（线性链真推进，不是只看置灰）" "True" \
    "$(head -1 "$EVID/resp-levels-$STU4-after1.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["weekNo"]==9 and x["seq"]==6][0]["unlocked"])')"
  check "第 6 关自己还没通关（解锁 ≠ 通关）" "False" \
    "$(head -1 "$EVID/resp-levels-$STU4-after1.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["weekNo"]==9 and x["seq"]==6][0]["cleared"])')"
} > "$EVID/05-ledger-authority.log" 2>&1

# ================================================================ 06 重刷不覆盖首刷（验收⑤）+ 错题变掌握（验收④）
{
  step "06 验收⑤：重刷 10/10 刷新星级，但首刷成绩（联赛/平时成绩口径）仍是 8/10"
  api GET "/api/quiz/paper?level=$LV_MATCH" "$TOKEN4" > "$EVID/resp-paper-37-2.json"
  head -1 "$EVID/resp-paper-37-2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("重刷 attemptId =", d["attemptId"], "| seed =", d["shuffleSeed"], "| resumed =", d["resumed"], "（新 attempt、新 seed）")
'
  A_SECOND=$(pyget data.attemptId < "$EVID/resp-paper-37-2.json")
  { echo "==PAPER=="; cat "$EVID/resp-paper-37-2.json"; echo "==KEY=="; cat "$EVID/answerkey-37.tsv"; } | python -c '
import sys, json
mode = None; paper = None; key = {}
for line in sys.stdin.read().split("\n"):
    if line == "==PAPER==": mode = "paper"; continue
    if line == "==KEY==": mode = "key"; continue
    if mode == "paper" and line.startswith("{"): paper = json.loads(line)["data"]
    elif mode == "key" and "\t" in line:
        qid, ans = line.split("\t")[:2]; key[int(qid)] = ans
answers = [{"questionId": q["id"], "pickedIdx": key[q["id"]]} for q in paper["questions"]]
print(json.dumps({"attemptId": paper["attemptId"], "answers": answers}, ensure_ascii=False))
' > "$EVID/body-submit-37-round2.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-37-round2.json" > "$EVID/resp-submit-37-round2.json"
  head -1 "$EVID/resp-submit-37-round2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| 星级 =", s["stars"], "| 710 分制 =", s["score710"], "| 本次 XP =", s["xpTotal"],
      "| 总分 =", s["xpTotalAll"], "| 首刷 =", s["firstClear"], "| 重刷 =", s["replay"])
print("XP 明细：", [(r["label"], r["delta"]) for r in s["xpRows"]])
print("验收④ 铺垫：4 道原本没答对的题，重刷后回执 learned（原本是错题 → 已掌握）：",
      [(f["questionId"], f["learned"]) for f in d["feedback"] if f["learned"]])
'
  check "重刷 10/10 → 三星" "3" "$(head -1 "$EVID/resp-submit-37-round2.json" | pyget data.settlement.stars)"
  check "重刷 10/10 → 正确率 1（首刷 0.8 → 重刷 1.0，成绩单口径的 80/100）" "1" "$(head -1 "$EVID/resp-submit-37-round2.json" | pyget data.settlement.ratio)"
  check "重刷本次 XP = 200+225+30+20 = 475" "475" "$(head -1 "$EVID/resp-submit-37-round2.json" | pyget data.settlement.xpTotal)"
  check "两次合计总分 = 805" "805" "$(head -1 "$EVID/resp-submit-37-round2.json" | pyget data.settlement.xpTotalAll)"
  check "重刷标记 replay=true" "True" "$(head -1 "$EVID/resp-submit-37-round2.json" | pyget data.settlement.replay)"
  echo
  echo "--- 06-1 验收⑤ 核心：首刷成绩仍是最小 id 的那条 finished（8/10、两星、568 分口径）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-after2.json"
  head -1 "$EVID/resp-levels-$STU4-after2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
it = [x for x in d["items"] if x["id"] == int(sys.argv[1])][0]
fr = it["firstResult"]
print("该关：通关 =", it["cleared"], "| 星级 =", it["stars"], "（取历史最好）| 打过 =", it["attempts"], "次")
print("首刷成绩（联赛/平时成绩只认这条）：attemptId =", fr["attemptId"], "|", fr["correct"], "/", fr["total"],
      "|", fr["stars"], "星 | 结束于", fr["finishedAt"])
print("xpTotal =", d["xpTotal"])
' "$LV_MATCH"
  check "星级刷新到 3（max 口径）" "3" "$(head -1 "$EVID/resp-levels-$STU4-after2.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["id"]==37][0]["stars"])')"
  check "首刷仍是第一条 finished（8/10）" "8/10" "$(head -1 "$EVID/resp-levels-$STU4-after2.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; fr=[x for x in d["items"] if x["id"]==37][0]["firstResult"]; print(str(fr["correct"])+"/"+str(fr["total"]))')"
  check "首刷 attemptId 仍是第一次那条" "$A_FIRST" "$(head -1 "$EVID/resp-levels-$STU4-after2.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["id"]==37][0]["firstResult"]["attemptId"])')"
  check "重刷是另一条 attempt" "True" "$([ "$A_FIRST" != "$A_SECOND" ] && echo True || echo False)"
  echo
  echo "--- 06-2 验收④：错题本收录 + 重刷答对后标记已掌握 ---"
  sql "SELECT w.id, w.question_id, w.wrong_count, w.mastered, w.last_at FROM cet46.wrong_book w
       WHERE w.user_id=(SELECT id FROM cet46.users WHERE username='$STU4') ORDER BY w.question_id;"
  sql "SELECT COUNT(*) AS 错题本条目数, SUM(wrong_count) AS 累计错误次数, SUM(mastered) AS 已掌握数
       FROM cet46.wrong_book WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');"
  WRONG_QIDS=$(sql "SELECT GROUP_CONCAT(question_id) FROM cet46.attempt_answers WHERE attempt_id=$A_FIRST AND is_correct=0;")
  echo "首刷答错的题目 id：$WRONG_QIDS（03 号日志的断点探针也答错 1 题，所以错题本总条目 = 这两题 + 探针那题）"
  check "首刷答错的 2 题都进了错题本" "2" "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4') AND question_id IN ($WRONG_QIDS);")"
  check "重刷全对后这 2 题标记已掌握" "2" "$(sql "SELECT COALESCE(SUM(mastered),0) FROM cet46.wrong_book WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4') AND question_id IN ($WRONG_QIDS);")"
} > "$EVID/06-rebrush-first.log" 2>&1

# ================================================================ 07 失败（爱心扣完）净得 0
{
  step "07 失败口径：爱心扣完 → attempt 记 failed、星级不产、得分当场作废（账本留撤销行，净得 0）"
  A_THIRD=$(api GET "/api/quiz/paper?level=$LV_MATCH" "$TOKEN4" > "$EVID/resp-paper-37-3.json"; pyget data.attemptId < "$EVID/resp-paper-37-3.json")
  echo "第三次闯关 attemptId = $A_THIRD（前 2 题答对，后 3 题连错把爱心扣完）"
  { echo "==PAPER=="; cat "$EVID/resp-paper-37-3.json"; echo "==KEY=="; cat "$EVID/answerkey-37.tsv"; } | python -c '
import sys, json
mode = None; paper = None; key = {}
for line in sys.stdin.read().split("\n"):
    if line == "==PAPER==": mode = "paper"; continue
    if line == "==KEY==": mode = "key"; continue
    if mode == "paper" and line.startswith("{"): paper = json.loads(line)["data"]
    elif mode == "key" and "\t" in line:
        qid, ans = line.split("\t")[:2]; key[int(qid)] = int(ans.split(",")[0])
answers = []
for i, q in enumerate(paper["questions"]):
    picks = key[q["id"]] if i < 2 else (key[q["id"]] + 1) % len(q["options"])
    answers.append({"questionId": q["id"], "pickedIdx": str(picks)})
print(json.dumps({"attemptId": paper["attemptId"], "answers": answers}, ensure_ascii=False))
' > "$EVID/body-submit-37-round3.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-37-round3.json" > "$EVID/resp-submit-37-round3.json"
  head -1 "$EVID/resp-submit-37-round3.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| 进度 =", d["progress"], "| 回执条数 =", len(d["feedback"]), "（爱心扣完当题即结束）")
print("结算：星级 =", s["stars"], "| 710 分制 =", s["score710"], "| 本次净得 =", s["xpTotal"], "| 总分 =", s["xpTotalAll"])
print("XP 明细（含作废行）：", [(r["label"], r["delta"]) for r in s["xpRows"]])
'
  check "爱心扣完 → status=failed" "failed" "$(pyget data.status < "$EVID/resp-submit-37-round3.json")"
  check "失败本次净得 0" "0" "$(head -1 "$EVID/resp-submit-37-round3.json" | pyget data.settlement.xpTotal)"
  check "失败后总分不变（805）" "805" "$(head -1 "$EVID/resp-submit-37-round3.json" | pyget data.settlement.xpTotalAll)"
  check "失败 attempt 星级 0" "0" "$(head -1 "$EVID/resp-submit-37-round3.json" | pyget data.settlement.stars)"
  echo
  echo "--- 07-1 落库：failed 行 + 账本净额 0（撤销行看得见，账本只增不删）---"
  sql "SELECT id, correct, total, stars, score710, xp_earned, status, finished_at FROM cet46.attempts WHERE id=$A_THIRD;"
  sql "SELECT id, delta, reason, ref_type, ref_id FROM cet46.xp_ledger WHERE ref_id=$A_THIRD ORDER BY id;"
  sql "SELECT COALESCE(SUM(delta),0) AS 本次净额 FROM cet46.xp_ledger WHERE ref_type='attempt' AND ref_id=$A_THIRD;"
  check "失败 attempt 落 status=failed" "failed" "$(sql "SELECT status FROM cet46.attempts WHERE id=$A_THIRD;")"
  check "失败 attempt xp_earned=0" "0" "$(sql "SELECT xp_earned FROM cet46.attempts WHERE id=$A_THIRD;")"
  check "失败本次账本净额 0" "0" "$(sql "SELECT COALESCE(SUM(delta),0) FROM cet46.xp_ledger WHERE ref_type='attempt' AND ref_id=$A_THIRD;")"
  check "撤销行已落库 1 条" "1" "$(sql "SELECT COUNT(*) FROM cet46.xp_ledger WHERE ref_id=$A_THIRD AND reason='attempt_voided';")"
  echo
  echo "--- 07-2 失败不覆盖历史：星级仍 3、首刷仍第一次那条 ---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-after3.json"
  head -1 "$EVID/resp-levels-$STU4-after3.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
it = [x for x in d["items"] if x["id"] == 37][0]
print("该关：通关 =", it["cleared"], "| 星级 =", it["stars"], "| 打过 =", it["attempts"], "次 | 首刷 =", it["firstResult"], "| xpTotal =", d["xpTotal"])
'
  check "失败后星级仍 3" "3" "$(head -1 "$EVID/resp-levels-$STU4-after3.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["id"]==37][0]["stars"])')"
  check "失败后首刷仍是第一条" "$A_FIRST" "$(head -1 "$EVID/resp-levels-$STU4-after3.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["id"]==37][0]["firstResult"]["attemptId"])')"
  check "失败后总分仍 805" "805" "$(head -1 "$EVID/resp-levels-$STU4-after3.json" | pyget data.xpTotal)"
} > "$EVID/07-fail-void.log" 2>&1

# ================================================================ 08 诊断卷 + 学情画像（推荐制）
{
  step "08 诊断卷：下发（10 题 / 按题型抽样）→ 判分 → 学情画像 → 推荐起点；不建 attempt、不改进度"
  echo "--- 08-0 诊断前：关卡列表的解锁状态快照（诊断后要比对不变）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-before-diag.json"
  head -1 "$EVID/resp-levels-$STU4-before-diag.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("解锁快照：", [(it["weekNo"], it["seq"], it["unlocked"], it["cleared"]) for it in d["items"]])
print("recommendedLevelId =", d["recommendedLevelId"])
'
  A_BEFORE=$(sql "SELECT COUNT(*) FROM cet46.attempts WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');")
  echo
  echo "--- 08-1 取诊断卷 ---"
  api GET /api/diag/paper "$TOKEN4" > "$EVID/resp-diag-paper.json"
  head -1 "$EVID/resp-diag-paper.json" | python -c '
import sys, json, collections
d = json.loads(sys.stdin.read())["data"]
print("seed =", d["seed"], "| 题数 =", d["total"], "| 预告分钟 =", d["estimatedMinutes"])
print("抽样构成（按题型）：", [(s["type"], s["count"]) for s in d["sampling"]])
print("题型分布（实到）：", dict(collections.Counter(q["type"] for q in d["questions"])))
print("题目 id：", [q["id"] for q in d["questions"]])
print("首题题干（前 70 字）：", d["questions"][0]["stem"][:70])
'
  check "诊断卷 10 题" "10" "$(pyget data.total < "$EVID/resp-diag-paper.json")"
  check "诊断卷预告 10 分钟" "10" "$(pyget data.estimatedMinutes < "$EVID/resp-diag-paper.json")"
  check "抽样构成按权重收口：词汇 4 / 语法 3 / 阅读 3（权重是下限，缺口才走补齐池）" "grammar=3,reading=3,vocab=4" \
    "$(head -1 "$EVID/resp-diag-paper.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print(",".join(sorted(s["type"] + "=" + str(s["count"]) for s in d["sampling"])))
')"
  python -c '
import sys, json
d = json.loads(sys.stdin.read().strip().splitlines()[0])["data"]
def keys(o, acc):
    if isinstance(o, dict):
        for k, v in o.items(): acc.add(k); keys(v, acc)
    elif isinstance(o, list):
        for v in o: keys(v, acc)
    return acc
seen = keys(d, set())
hit = sorted(k for k in ("answerIdx", "exp", "tip", "knowledgeTag") if k in seen)
print("诊断卷响应禁字段命中：", hit if hit else "无 ✅")
' < "$EVID/resp-diag-paper.json"
  echo
  echo "--- 08-2 交诊断卷（脚本按展示序第 0 项作答：判分正确性由 router 测试 TestDiagPaperProfileAndRecommendation 保证，这里实录完整链路）---"
  head -1 "$EVID/resp-diag-paper.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print(json.dumps({"answers": [{"questionId": q["id"], "pickedIdx": "0"} for q in d["questions"]]}, ensure_ascii=False))
' > "$EVID/body-diag-submit.json"
  api POST /api/diag/submit "$TOKEN4" "$EVID/body-diag-submit.json" > "$EVID/resp-diag-submit.json"
  head -1 "$EVID/resp-diag-submit.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
r = d["result"]
print("判分：", r["correct"], "/", r["total"], "正确率 =", r["accuracy"], "| 学情档次 =", r["level"])
print("按题型：", {k: (v["correct"], v["total"], v["accuracy"]) for k, v in r["byType"].items()})
print("按知识点：", {k: (v["correct"], v["total"], v["accuracy"]) for k, v in r["byKnowledge"].items()})
print("推荐起点 levelId =", d["recommendedLevelId"], "| 建议起跳 =", d["skipSuggestionLevelId"])
print("推荐说明：", d["recommendationNote"])
print("诊断记录 id =", d["diagnosisId"], "| 回执条数 =", len(d["feedback"]))
'
  check "诊断判分题数 = 10" "10" "$(head -1 "$EVID/resp-diag-submit.json" | pyget data.result.total)"
  echo
  echo "--- 08-3 落库：diagnoses 一行（result_json 含画像/抽样/推荐），且不新增 attempt ---"
  sql "SELECT id, user_id, start_level, CHAR_LENGTH(result_json) AS result_json长度, created_at FROM cet46.diagnoses
       WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');"
  sql "SELECT JSON_EXTRACT(result_json, '$.accuracy') AS 正确率, JSON_EXTRACT(result_json, '$.level') AS 档次,
              JSON_EXTRACT(result_json, '$.skipSuggestion') AS 建议起跳, JSON_UNQUOTE(JSON_EXTRACT(result_json, '$.recommendNote')) AS 推荐说明
       FROM cet46.diagnoses WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');"
  A_AFTER=$(sql "SELECT COUNT(*) FROM cet46.attempts WHERE user_id=(SELECT id FROM cet46.users WHERE username='$STU4');")
  check "诊断不建 attempt" "$A_BEFORE" "$A_AFTER"
  echo
  echo "--- 08-4 诊断前后解锁链/进度不变（推荐制，不强制起始关卡）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-$STU4-after-diag.json"
  head -1 "$EVID/resp-levels-$STU4-after-diag.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("解锁快照：", [(it["weekNo"], it["seq"], it["unlocked"], it["cleared"]) for it in d["items"]])
print("recommendedLevelId =", d["recommendedLevelId"], "| xpTotal =", d["xpTotal"])
'
  check "诊断后解锁状态不变" \
    "$(head -1 "$EVID/resp-levels-$STU4-before-diag.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([(i["weekNo"],i["seq"],i["unlocked"],i["cleared"]) for i in d["items"]])')" \
    "$(head -1 "$EVID/resp-levels-$STU4-after-diag.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([(i["weekNo"],i["seq"],i["unlocked"],i["cleared"]) for i in d["items"]])')"
  check "诊断不改总分" "805" "$(head -1 "$EVID/resp-levels-$STU4-after-diag.json" | pyget data.xpTotal)"
} > "$EVID/08-diag.log" 2>&1

# ================================================================ 08b 自建演示单元：线性解锁链 + Boss 卷 710 分制
# 这两条要「脚本能预知正确答案」才演示得动，所以用教师接口自建一个第 12 周的演示单元：
# 全部 match 题型（S3 决策「段落编号带语义 → match 不洗选项」，正确项永远停在题库下标那个展示位），
# 答案下标恒 0 → 脚本知道点哪项对。跑完在 99 号日志里把这个单元连同关卡、题目一起删掉。
{
  step "08b 实清：自建第 12 周演示单元（匹配关 5 题 + Boss 卷 8 题）→ 线性解锁链 + 710 分制 + 速度加成三边界"
  echo "--- 08b-0 建单元 + 2 关 + 13 题（band=4、match、答案下标 0）---"
  printf '{"classId":%s,"weekNo":12,"name":"S3验收演示单元"}' "$CLASS_ID" > "$EVID/body-demo-unit.json"
  api POST /api/admin/units "$TOKEN" "$EVID/body-demo-unit.json" > "$EVID/resp-demo-unit.json"
  DEMO_UNIT=$(pyget data.id < "$EVID/resp-demo-unit.json")
  mk_level() { # mk_level seq 名称 关卡类型 限时秒 isBoss → 打印 levelId
    printf '{"unitId":%s,"seq":%s,"name":"%s","type":"%s","timeLimit":%s,"isBoss":%s}' \
      "$DEMO_UNIT" "$1" "$2" "$3" "$4" "$5" > "$EVID/body-demo-level-$1.json"
    api POST /api/admin/levels "$TOKEN" "$EVID/body-demo-level-$1.json" > "$EVID/resp-demo-level-$1.json"
    pyget data.id < "$EVID/resp-demo-level-$1.json"
  }
  LV_D1=$(mk_level 1 "演示关 · 匹配热身" reading 300 false)
  LV_D2=$(mk_level 2 "演示 Boss 卷" boss 720 true)
  mk_demo_questions() { # mk_demo_questions levelId 题数
    local lid="$1" n="$2" i
    for i in $(seq 1 "$n"); do
      printf '{"levelId":%s,"band":"4","type":"match","stem":"演示题 %s（段落匹配）：第 %s 段的主题是？","options":["场景说明（演示项 A）","观点论证（演示项 B）","数据支撑（演示项 C）","结论建议（演示项 D）"],"answerIdx":"0","exp":"演示用解析：match 不洗选项，正确项恒在展示下标 0","tip":"演示用考点","knowledgeTag":"演示考点"}' \
        "$lid" "$i" "$i" > "$EVID/body-demo-q.json"
      api POST /api/admin/questions "$TOKEN" "$EVID/body-demo-q.json" > "$EVID/resp-demo-q.json"
    done
  }
  mk_demo_questions "$LV_D1" 5
  mk_demo_questions "$LV_D2" 8
  printf '%s %s %s\n' "$DEMO_UNIT" "$LV_D1" "$LV_D2" > "$EVID/fixture-ids.txt"
  echo "演示单元 unitId=$DEMO_UNIT；匹配关（第 1 关）=$LV_D1，5 题、限时 300 秒；Boss 卷（第 2 关）=$LV_D2，8 题、限时 720 秒"
  echo
  echo "--- 08b-1 学生视角：演示单元出现，第 1 关开放、第 2 关还锁着（同一单元内的线性链）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-demo-before.json"
  head -1 "$EVID/resp-levels-demo-before.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
for it in d["items"]:
    if it["weekNo"] == 12:
        print("  第 12 周第", it["seq"], "关", it["name"], "：题量=", it["questionCount"], "预告=", it["estimatedMinutes"], "分 解锁=", it["unlocked"], "通关=", it["cleared"])
print("  xpTotal =", d["xpTotal"])
'
  w12() { head -1 "$EVID/resp-levels-demo-before.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print([x for x in d["items"] if x["weekNo"] == 12 and x["seq"] == int(sys.argv[1])][0][sys.argv[2]])
' "$1" "$2"; }
  check "演示单元第 1 关开放" "True" "$(w12 1 unlocked)"
  check "演示单元第 2 关锁着（前一关没通关）" "False" "$(w12 2 unlocked)"
  check "演示单元第 1 关题量 5、预告 7 分钟" "5/7" "$(w12 1 questionCount)/$(w12 1 estimatedMinutes)"
  check "演示单元 Boss 关题量 8、预告 10 分钟" "8/10" "$(w12 2 questionCount)/$(w12 2 estimatedMinutes)"
  echo
  echo "--- 08b-2 真通关第 1 关 5/5，并按 §6 上报三组耗时：秒答 0ms→速度+10、压线 60000ms→0、超时 90000ms→0 ---"
  echo "        （本题限时 = time_limit 300 ÷ 题数 5 = 60 秒；第 4、5 题不上报耗时 → nil，按 0 分算）"
  api GET "/api/quiz/paper?level=$LV_D1" "$TOKEN4" > "$EVID/resp-paper-demo1.json"
  head -1 "$EVID/resp-paper-demo1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
elapsed = [0, 60000, 90000, None, None]
answers = []
for i, q in enumerate(d["questions"]):
    a = {"questionId": q["id"], "pickedIdx": "0"}  # match：正确项展示下标 = 题库下标 0
    if elapsed[i] is not None:
        a["elapsedMs"] = elapsed[i]
    answers.append(a)
print(json.dumps({"attemptId": d["attemptId"], "answers": answers}, ensure_ascii=False))
' > "$EVID/body-submit-demo1.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-demo1.json" > "$EVID/resp-submit-demo1.json"
  head -1 "$EVID/resp-submit-demo1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| 星级 =", s["stars"], "| 正确率 =", s["ratio"], "| 本次 XP =", s["xpTotal"], "| 总分 =", s["xpTotalAll"])
print("XP 明细：", [(r["label"], r["delta"]) for r in s["xpRows"]])
print("期望：基础 100 + 速度 10（只有秒答那题给分）+ 连击 50 + 通关 30 + 三星 20 = 210；总分 805+210 = 1015")
'
  check "演示关 5/5 → 三星" "3" "$(head -1 "$EVID/resp-submit-demo1.json" | pyget data.settlement.stars)"
  check "速度加成合计 = 10（秒答 +10、压线 0、超时 0、未上报 0）" "10" \
    "$(head -1 "$EVID/resp-submit-demo1.json" | python -c 'import sys,json; s=json.loads(sys.stdin.read())["data"]["settlement"]; print(sum(r["delta"] for r in s["xpRows"] if r["reason"]=="answer_speed"))')"
  check "本次 XP = 210" "210" "$(head -1 "$EVID/resp-submit-demo1.json" | pyget data.settlement.xpTotal)"
  check "通关后总分 = 805+210 = 1015" "1015" "$(head -1 "$EVID/resp-submit-demo1.json" | pyget data.settlement.xpTotalAll)"
  echo
  echo "--- 08b-3 通关后同单元第 2 关解锁（真通关驱动的线性链）---"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-demo-after.json"
  head -1 "$EVID/resp-levels-demo-after.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
for it in d["items"]:
    if it["weekNo"] == 12:
        fr = it["firstResult"]
        print("  第 12 周第", it["seq"], "关", it["name"], "：解锁=", it["unlocked"], "通关=", it["cleared"], "星=", it["stars"], "打过=", it["attempts"],
      "首刷=", "—" if fr is None else str(fr["correct"]) + "/" + str(fr["total"]))
'
  check "通关后第 2 关解锁" "True" \
    "$(head -1 "$EVID/resp-levels-demo-after.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["weekNo"]==12 and x["seq"]==2][0]["unlocked"])')"
  echo
  echo "--- 08b-4 Boss 卷满分 8/8：710 分制成绩单 + 答对×25 + 满分 50（Boss 不重复计基础/速度/连击/三星）---"
  api GET "/api/quiz/paper?level=$LV_D2" "$TOKEN4" > "$EVID/resp-paper-boss1.json"
  head -1 "$EVID/resp-paper-boss1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print(json.dumps({"attemptId": d["attemptId"],
                  "answers": [{"questionId": q["id"], "pickedIdx": "0"} for q in d["questions"]]}, ensure_ascii=False))
' > "$EVID/body-submit-boss1.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-boss1.json" > "$EVID/resp-submit-boss1.json"
  A_BOSS1=$(pyget data.attemptId < "$EVID/resp-submit-boss1.json")
  head -1 "$EVID/resp-submit-boss1.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| isBoss =", s["isBoss"], "| 星级 =", s["stars"], "| 正确率 =", s["ratio"], "| 710 分制 =", s["score710"],
      "| 本次 XP =", s["xpTotal"], "| 总分 =", s["xpTotalAll"])
print("XP 明细：", [(r["label"], r["delta"]) for r in s["xpRows"]], "（8 题×25=200 + 满分 50 = 250）")
'
  check "Boss 满分 → 710 分制成绩单 710" "710" "$(head -1 "$EVID/resp-submit-boss1.json" | pyget data.settlement.score710)"
  check "Boss 满分 → 本次 XP 250" "250" "$(head -1 "$EVID/resp-submit-boss1.json" | pyget data.settlement.xpTotal)"
  check "Boss 满分后总分 = 1015+250 = 1265" "1265" "$(head -1 "$EVID/resp-submit-boss1.json" | pyget data.settlement.xpTotalAll)"
  echo
  echo "--- 08b-5 Boss 卷二刷 6/8：710×0.75 = 532.5 → 533；答题分 6×25 = 150；没有满分奖励 ---"
  api GET "/api/quiz/paper?level=$LV_D2" "$TOKEN4" > "$EVID/resp-paper-boss2.json"
  head -1 "$EVID/resp-paper-boss2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
answers = [{"questionId": q["id"], "pickedIdx": "0" if i < 6 else "1"} for i, q in enumerate(d["questions"])]
print(json.dumps({"attemptId": d["attemptId"], "answers": answers}, ensure_ascii=False))
' > "$EVID/body-submit-boss2.json"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-boss2.json" > "$EVID/resp-submit-boss2.json"
  head -1 "$EVID/resp-submit-boss2.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
s = d["settlement"]
print("status =", d["status"], "| 星级 =", s["stars"], "| 正确率 =", s["ratio"], "| 710 分制 =", s["score710"],
      "| 本次 XP =", s["xpTotal"], "| 总分 =", s["xpTotalAll"], "| 首刷 =", s["firstClear"], "| 重刷 =", s["replay"])
print("XP 明细：", [(r["label"], r["delta"]) for r in s["xpRows"]])
'
  check "Boss 6/8 → 533 分（0.75×710 四舍五入）" "533" "$(head -1 "$EVID/resp-submit-boss2.json" | pyget data.settlement.score710)"
  check "Boss 6/8 → 本次 XP 150（无满分奖励）" "150" "$(head -1 "$EVID/resp-submit-boss2.json" | pyget data.settlement.xpTotal)"
  check "Boss 6/8 → 两星" "2" "$(head -1 "$EVID/resp-submit-boss2.json" | pyget data.settlement.stars)"
  check "Boss 二刷标记 replay=true" "True" "$(head -1 "$EVID/resp-submit-boss2.json" | pyget data.settlement.replay)"
  check "Boss 二刷后总分 = 1265+150 = 1415" "1415" "$(head -1 "$EVID/resp-submit-boss2.json" | pyget data.settlement.xpTotalAll)"
  check "Boss 首刷仍是满分那条（重刷不覆盖首刷）" "$A_BOSS1" \
    "$(api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-demo-final.json"; head -1 "$EVID/resp-levels-demo-final.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print([x for x in d["items"] if x["weekNo"]==12 and x["seq"]==2][0]["firstResult"]["attemptId"])')"
} > "$EVID/08b-unlock-and-boss.log" 2>&1

# ================================================================ 09 数据模型红线
{
  step "09 红线核对：S3 涉及的五张表列定义必须与开发方案 v1.0 §4 一致（未加表、未改字段）"
  for tbl in attempts attempt_answers xp_ledger wrong_book diagnoses; do
    "${MYSQL[@]}" -e "SHOW CREATE TABLE cet46.$tbl\G"
  done
  echo
  echo "--- 逐表列清单对照（脚本内置期望值，来自开发方案 §4）---"
  SCHEMA_VERDICT=$(
    {
      for tbl in attempts attempt_answers xp_ledger wrong_book diagnoses; do
        echo "==$tbl=="
        sql "SELECT COLUMN_NAME FROM information_schema.columns
             WHERE table_schema='cet46' AND table_name='$tbl' ORDER BY ordinal_position;"
      done
    } | python -c '
import sys
expect = {
 "attempts": ["id","user_id","level_id","unit_id","correct","total","stars","score710","xp_earned","shuffle_seed","status","started_at","finished_at"],
 "attempt_answers": ["id","attempt_id","question_id","picked_idx","is_correct","created_at"],
 "xp_ledger": ["id","user_id","delta","reason","ref_type","ref_id","created_at"],
 "wrong_book": ["id","user_id","question_id","wrong_count","last_at","mastered"],
 "diagnoses": ["id","user_id","result_json","start_level","created_at"],
}
actual = {}
cur = None
for line in sys.stdin.read().split("\n"):
    line = line.strip()
    if not line:
        continue
    if line.startswith("=="):
        cur = line.strip("=")
        actual[cur] = []
    elif cur:
        actual[cur].append(line)
fail = 0
for tbl, cols in expect.items():
    got = actual.get(tbl, [])
    ok = got == cols
    fail += (not ok)
    print("  " + tbl + " : " + ("✅ 一致" if ok else "❌ 不一致"))
    print("      实际 = " + repr(got))
    if not ok:
        print("      期望 = " + repr(cols))
print("红线核对结果：" + ("全部一致 ✅" if fail == 0 else str(fail) + " 张表不一致 ❌"))
sys.exit(1 if fail else 0)
'
    echo "exit=$?"
  )
  echo "$SCHEMA_VERDICT"
  check "五张表列定义与开发方案 §4 完全一致（未加表、未改字段）" "exit=0" "$(echo "$SCHEMA_VERDICT" | tail -1)"
} > "$EVID/09-schema-redline.log" 2>&1

# ================================================================ 10/11 测试与一键校验
{
  step "10 go test ./...（服务层 + router 层 HTTP 全链路）"
  go test ./... 2>&1 | tr -d '\000'
  echo
  step "10b S3 相关用例逐个列出（quiz 数值引擎 + router 全链路）"
  go test ./internal/quiz/ ./internal/service/ ./internal/router/ -v 2>&1 | tr -d '\000' | grep -E '^(--- PASS|--- FAIL)' | grep -v '/'
} > "$EVID/10-gotest.log" 2>&1

{
  step "11 scripts/verify.sh（gofmt + go vet + go test + go build + eslint + 前端构建）"
} > "$EVID/11-verify-sh.log" 2>&1
bash "$ROOT/scripts/verify.sh" >> "$EVID/11-verify-sh.log" 2>&1
echo "verify.sh 退出码: $?" >> "$EVID/11-verify-sh.log"

# ================================================================ 清理：演示数据删干净，题库与真实账号不动
{
  step "99 清理：删演示学生 $STU4/$STU6 及其流水 + 删 08b 自建演示单元（教师接口级联删关卡与题目）"
  sql "SELECT COUNT(*) AS 删除前_attempts FROM cet46.attempts;
       SELECT COUNT(*) AS 删除前_ledger FROM cet46.xp_ledger;"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6')));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.wrong_book WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.diagnoses WHERE user_id IN (SELECT id FROM cet46.users WHERE username IN ('$STU4','$STU6'));
       DELETE FROM cet46.users WHERE username IN ('$STU4','$STU6');"
  echo
  echo "--- 删自建演示单元（DELETE /api/admin/units/:id 会连带删掉它的关卡与题目）---"
  DEMO_UNIT=$(cut -d' ' -f1 "$EVID/fixture-ids.txt")
  if [ -n "$DEMO_UNIT" ]; then
    api DELETE "/api/admin/units/$DEMO_UNIT" "$TOKEN" > "$EVID/resp-demo-unit-del.json"
    tail -1 "$EVID/resp-demo-unit-del.json"
  else
    echo "（没有 fixture-ids.txt，跳过）"
  fi
  sql "SELECT
        (SELECT COUNT(*) FROM cet46.users WHERE username IN ('$STU4','$STU6')) AS 演示学生,
        (SELECT COUNT(*) FROM cet46.attempts)        AS attempts,
        (SELECT COUNT(*) FROM cet46.attempt_answers) AS attempt_answers,
        (SELECT COUNT(*) FROM cet46.xp_ledger)       AS xp_ledger,
        (SELECT COUNT(*) FROM cet46.wrong_book)      AS wrong_book,
        (SELECT COUNT(*) FROM cet46.diagnoses)       AS diagnoses,
        (SELECT COUNT(*) FROM cet46.units)           AS units,
        (SELECT COUNT(*) FROM cet46.levels)          AS levels,
        (SELECT COUNT(*) FROM cet46.questions)       AS questions;"
  echo
  echo "--- 清理断言 ---"
  check "演示学生已删净" "0" "$(sql "SELECT COUNT(*) FROM cet46.users WHERE username IN ('$STU4','$STU6');")"
  check "五张 S3 表全空（attempts/attempt_answers/xp_ledger/wrong_book/diagnoses）" "0/0/0/0/0" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts),'/',(SELECT COUNT(*) FROM cet46.attempt_answers),'/',(SELECT COUNT(*) FROM cet46.xp_ledger),'/',(SELECT COUNT(*) FROM cet46.wrong_book),'/',(SELECT COUNT(*) FROM cet46.diagnoses));")"
  check "演示单元已删" "0" "$(sql "SELECT COUNT(*) FROM cet46.units WHERE week_no=12 AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME');")"
  check "单元数回到 4" "4" "$(sql "SELECT COUNT(*) FROM cet46.units;")"
  check "关卡数回到 24" "24" "$(sql "SELECT COUNT(*) FROM cet46.levels;")"
  check "题目数回到 206（题库一题没动）" "206" "$(sql "SELECT COUNT(*) FROM cet46.questions;")"
} > "$EVID/99-cleanup.log" 2>&1

kill "$SERVER_PID" 2>/dev/null
printf '\n--- 服务已停（PID %s）---\n' "$SERVER_PID" >> "$EVID/02-server-start.log"
echo
echo "==== S3 验收实跑结束：校验失败项 = $FAILS（详见各日志 [CHECK] 行）===="
echo "日志目录：$EVID"
exit "$([ "$FAILS" -eq 0 ] && echo 0 || echo 1)"