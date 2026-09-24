#!/usr/bin/env bash
# S4 验收实跑（新题型：选词填空 cloze / 段落匹配 match 的存取格式、判分、XP 口径 + 听力原文 script 列接通）。
# 产出同目录编号日志，一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑（S0 建），8080 端口空闲，班级 2024级英语1班 存在（S1 建）。
# 自建自清：只建自己的演示学生（S4V4）与第 13/14 周演示单元（13=真题读数演示、14=听力原文演示），
# 真题数据只读不改——第 10 周 20 道阅读真题（10 选词填空 + 10 段落匹配）的题库指纹在 00 与 99 各算一次对比。
#（T0001 会被 seed-teacher 打回初始密码再改密，这是 S2 就在用的惯例，复跑前重跑一次即可）。
set -uo pipefail
# 固定 Python 的 UTF-8 输出：Windows 控制台默认 GBK 时，print 中文/✅ 会抛 UnicodeEncodeError。
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"   # Python 是原生程序：给它 Windows 路径，别喂 /c/... 形式的 MSYS 路径
BASE=http://127.0.0.1:8080
CLASS_NAME='2024级英语1班'
TEACHER=T0001
TEACHER_PWD='Teacher@123'
TEACHER_PWD2='Teacher@456'
STU=S4V4
STU_PWD='Student@2024'
STU_PWD2='Student@2025'
WEEK_DEMO=13   # 真题读数演示单元：seq1=选词填空、seq2=段落匹配（题目本体来自第 10 周真题）
WEEK_LIS=14    # 听力原文演示单元：seq1=19 列带「听力原文」、seq2=老 18 列把原文塞解析、seq3=老 18 列普通题
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
# bank_dump 关卡的题库底账（id / answer_idx / 选项 JSON 的 hex）：hex 走管道不会被改写，
# 换行与中文都原样还原——脚本据此扮演「知道答案的学生」算展示坐标。
bank_dump() { sql "SELECT id, answer_idx, HEX(options_json) FROM cet46.questions WHERE level_id=$1 ORDER BY id;" > "$EVID/bank-$1.tsv"; }
upload() { # upload 文件路径 → 打印响应
  curl -sS -X POST "$BASE/api/admin/import-questions" -H "Authorization: Bearer $TOKEN" \
    -F "file=@$(cygpath -w "$1")" -w $'\n[HTTP %{http_code}]\n'
}
# md5_of 从响应文件第一行取题目字段的 MD5 集合（用来证明往返无损）
paper_stem_md5() { # paper_stem_md5 响应文件 题型
  python -c '
import sys, json, hashlib, io
p, qtype = sys.argv[1], sys.argv[2]
d = json.loads(io.open(p, encoding="utf-8").readline())["data"]
h = [hashlib.md5(q["stem"].encode("utf-8")).hexdigest() for q in d["questions"] if q["type"] == qtype]
print(" ".join(sorted(h)))
' "$(cygpath -w "$1")" "$2"
}
db_stem_md5() { # db_stem_md5 SQL 条件 → 同口径的 MD5 集合
  # mysql 客户端逐行输出 CRLF，行内的 \r 不会被 $( ) 去掉——先 tr -d '\r' 再拼行，
  # 否则集合里混着 \r，跟 Python 侧按 \n 拼出来的集合永远不相等（2026-09-24 踩过）。
  sql "SELECT MD5(stem) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE $1 ORDER BY MD5(stem);" | tr -d '\r' | tr '\n' ' ' | sed 's/ $//'
}

cd "$SRV" || exit 1
if curl -sS -o /dev/null "$BASE/api/health" 2>/dev/null; then
  echo "!! $BASE 已被占用（可能上一轮的服务还在跑），先停掉再复跑" >&2
  exit 1
fi

# ================================================================ 00 动库前现状
{
  step "00 前置：MySQL 3307 现状 + 本阶段要动的表起点 + 第 10 周真题指纹"
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
  echo "--- 表清单（§7 红线：17 张，S4 不加表不改列）---"
  sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cet46';"
  sql "SELECT table_name FROM information_schema.tables WHERE table_schema='cet46' ORDER BY table_name;" | tr '\n' ' '
  echo
  echo "--- 第 10 周真题底账：本次要读出来做「入库+取题往返」的样题来源（只读）---"
  sql "SELECT q.type AS 题型, COUNT(*) AS 题数, MIN(CHAR_LENGTH(q.stem)) AS 最短题干, MAX(CHAR_LENGTH(q.stem)) AS 最长题干,
         MIN(JSON_LENGTH(q.options_json)) AS 最少选项, MAX(JSON_LENGTH(q.options_json)) AS 最多选项
       FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
       WHERE u.week_no=10 AND q.type IN ('cloze','match') GROUP BY q.type;"
  BASELINE_W10=$(sql "SELECT MD5(GROUP_CONCAT(CONCAT_WS('|', q.id, q.type, CHAR_LENGTH(q.stem), MD5(q.stem), q.answer_idx, MD5(q.options_json)) ORDER BY q.id SEPARATOR ';'))
    FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
    WHERE u.week_no=10 AND q.type IN ('cloze','match');")
  printf '%s\n' "$BASELINE_W10" > "$EVID/baseline-week10-md5.txt"
  echo "第 10 周 20 道阅读真题的题库指纹（题号/题型/题干长度/题干 MD5/答案/选项 MD5 一起算）= $BASELINE_W10"
  echo
  echo "--- 幂等清理：删上一轮可能残留的演示学生与新建的演示单元（真题与真实账号一律不动）---"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU'));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.wrong_book WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.diagnoses WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.users WHERE username='$STU';"
  sql "DELETE FROM cet46.questions WHERE level_id IN (SELECT id FROM cet46.levels WHERE unit_id IN (SELECT id FROM cet46.units WHERE week_no IN ($WEEK_DEMO,$WEEK_LIS) AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME')));
       DELETE FROM cet46.levels WHERE unit_id IN (SELECT id FROM cet46.units WHERE week_no IN ($WEEK_DEMO,$WEEK_LIS) AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME'));
       DELETE FROM cet46.units WHERE week_no IN ($WEEK_DEMO,$WEEK_LIS) AND class_id=(SELECT id FROM cet46.classes WHERE name='$CLASS_NAME');"
  echo
  echo "--- 清理断言 ---"
  check "演示学生已删净" "0" "$(sql "SELECT COUNT(*) FROM cet46.users WHERE username='$STU';")"
  check "基线：单元/关卡/题目" "4/24/206" "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.units),'/',(SELECT COUNT(*) FROM cet46.levels),'/',(SELECT COUNT(*) FROM cet46.questions));")"
  check "第 10 周真题指纹已记录（32 位 MD5）" "32" "$(printf '%s' "$BASELINE_W10" | wc -c | tr -d ' ')"
} > "$EVID/00-db-before.log" 2>&1

# ================================================================ 01 判分单测（验收①）
{
  step "01 验收①：两题型各 3 组判分单测（全对 / 半对 / 全错）+ 形状解析 + 格式校验"
  go test ./internal/quiz/ -run 'TestJudge' -v 2>&1 | tr -d '\000' | grep -E '^(=== RUN|--- PASS|--- FAIL|ok|FAIL)'
  echo
  echo "--- 判分三组逐一列出（cloze 3 组 + match 3 组）---"
  go test ./internal/quiz/ -run 'TestJudge' -v 2>&1 | tr -d '\000' | grep -E '^--- (PASS|FAIL)'
  echo
  echo "--- 半对明细用例（matched 回报对了几个空，但 isCorrect=false、XP=0）---"
  go test ./internal/quiz/ -run 'TestJudgeClozeHalfCorrect|TestJudgeMatchHalfCorrect|TestJudgeClozeShorterPicked' -v 2>&1 | tr -d '\000' | grep -E '^--- (PASS|FAIL)'
  echo
  echo "--- 形状解析与格式校验（标记形态①/整篇形态②/越界/重复词/空答案）---"
  go test ./internal/quiz/ -run 'TestParseCloze|TestParseMatch|TestParseTypesOnPlainStem|TestShapeError' -v 2>&1 | tr -d '\000' | grep -E '^--- (PASS|FAIL)'
  JUDGE_PASS=$(go test ./internal/quiz/ -run 'TestJudge' -v 2>&1 | tr -d '\000' | grep -c '^--- PASS')
  JUDGE_FAIL=$(go test ./internal/quiz/ -run 'TestJudge' -v 2>&1 | tr -d '\000' | grep -c '^--- FAIL')
  HALF_CNT=$(go test ./internal/quiz/ -run 'TestJudge' -v 2>&1 | tr -d '\000' | grep -cE '^--- PASS: TestJudge(Cloze|Match)HalfCorrect')
  echo
  echo "--- 断言 ---"
  echo "（-run TestJudge 命中 8 条：S3 既有引擎用例 TestJudge 1 条 + S4 新题型 7 条；"
  echo "  S4 的 7 条 = cloze 全对/半对/全错/短提交 + match 全对/半对/全错，验收①要求的两题型各 3 组都在其中）"
  check "判分用例全绿（S3 引擎 1 + S4 新题型 7 = 8 条，零失败）" "8/0" "$JUDGE_PASS/$JUDGE_FAIL"
  check "半对用例两题型各一条（in 上一步的 8 条里）" "2" "$HALF_CNT"
  check "形状解析 + 格式校验用例全绿" "0" "$(go test ./internal/quiz/ -run 'TestParseCloze|TestParseMatch|TestParseTypesOnPlainStem|TestShapeError' -v 2>&1 | tr -d '\000' | grep -c '^--- FAIL')"
} > "$EVID/01-judge-unit-tests.log" 2>&1

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
  echo "--- S4 相关路由（启动日志里的路由表）---"
  grep -E 'admin|quiz|diag' "$EVID/02-server-start.log" | grep -E 'GET|POST|DELETE' | head -40 || true
} >> "$EVID/02-server-start.log" 2>&1

# ---- 教师登录 + 自建演示学生（与 S2/S3 同口径：seed-teacher 幂等重置密码 → 首登改密 → 再登录）
go run ./cmd/seed-teacher -username "$TEACHER" -name 张老师 -password "$TEACHER_PWD" > /dev/null 2>&1
TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD")
chpwd "$TEACHER" "$TOKEN" "$TEACHER_PWD" "$TEACHER_PWD2"
TOKEN=$(login_token "$TEACHER" "$TEACHER_PWD2")
CLASS_ID=$(sql "SELECT id FROM cet46.classes WHERE name='$CLASS_NAME';")
printf '{"username":"%s","realName":"S4演示学生","password":"%s","role":"student","classId":%s,"target":"4"}' \
  "$STU" "$STU_PWD" "$CLASS_ID" > "$EVID/body-user-$STU.json"
api POST /api/admin/users "$TOKEN" "$EVID/body-user-$STU.json" > "$EVID/resp-user-$STU.json"
T=$(login_token "$STU" "$STU_PWD")
chpwd "$STU" "$T" "$STU_PWD" "$STU_PWD2"
TOKEN4=$(login_token "$STU" "$STU_PWD2")
UID4=$(sql "SELECT id FROM cet46.users WHERE username='$STU';")

# ================================================================ 03 真题读数 → 19 列导入（验收④入库侧 + ⑤导入侧）
{
  step "03 从第 10 周真题读 20 道阅读题（10 选词填空 + 10 段落匹配）→ 生成 19 列 CSV → 导入第 $WEEK_DEMO 周演示单元"
  echo "--- 03-0 按 HEX 从库里导出样题（hex 过管道不改写中文/换行）---"
  sql "SELECT q.id, q.type, q.band, q.answer_idx, HEX(q.options_json), HEX(q.stem), HEX(IFNULL(q.exp,'')), IFNULL(q.tip,''), q.difficulty
       FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
       WHERE u.week_no=10 AND q.type IN ('cloze','match') ORDER BY q.id;" > "$EVID/week10-questions.tsv"
  echo "导出 $(wc -l < "$EVID/week10-questions.tsv" | tr -d ' ') 行样题底账"
  echo
  echo "--- 03-1 组装 19 列 CSV（表头列序 = 模板列序；正确答案写选项字母 A~P）---"
  python - "$EWIN/week10-questions.tsv" "$EWIN/fixture-bank-week10.csv" "$WEEK_DEMO" "$CLASS_NAME" <<'PYEOF'
import csv, io, json, sys
tsv, out, week, cls = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
head = ['班级','单元序号','单元名称','关卡序号','关卡名称','关卡类型','限时(分钟)','是否Boss','备考目标','题型',
        '题干','选项','正确答案','考点','解析','听力原文','知识点','难度','启用']
rows = []
for line in io.open(tsv, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, qtype, band, ans, hex_opts, hex_stem, hex_exp, tip, diff = line.split('\t')
    opts = json.loads(bytes.fromhex(hex_opts).decode('utf-8'))
    stem = bytes.fromhex(hex_stem).decode('utf-8')
    exp = bytes.fromhex(hex_exp).decode('utf-8')
    cloze = (qtype == 'cloze')
    letters = ','.join(chr(65 + int(x)) for x in ans.split(','))
    rows.append([cls, week, 'S4验收演示单元', 1 if cloze else 2,
                 '阅读 · 选词填空（第 10 周真题）' if cloze else '阅读 · 段落匹配（第 10 周真题）',
                 '阅读', 8 if cloze else 10, '否', '四级', '选词填空' if cloze else '段落匹配',
                 stem, '|'.join(opts), letters, tip, exp, '', '演示', diff, '是'])
with io.open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(head)
    w.writerows(rows)
print('写出 %d 行数据（选词填空 %d + 段落匹配 %d），表头 %d 列，最大题干 %d 字'
      % (len(rows), sum(1 for r in rows if r[4].endswith('选词填空（第 10 周真题）')),
         sum(1 for r in rows if r[4].endswith('段落匹配（第 10 周真题）')), len(head),
         max(len(r[10]) for r in rows)))
PYEOF
  echo "CSV 表头（19 列，列序 = 模板列序）："
  python -c '
import csv, io, sys
r = next(csv.reader(io.open(sys.argv[1], encoding="utf-8-sig")))
print("  " + " | ".join("%d:%s" % (i + 1, h) for i, h in enumerate(r)))
' "$(cygpath -w "$EVID/fixture-bank-week10.csv")"
  # 真题的段落匹配题干自带换行（A)..P) 段落），CSV 里是被引号包住的多行单元格，
  # 所以「数据行数」必须按 csv 记录数算，wc -l 数的是物理行（实测 301 行 ≠ 20 条）。
  check "CSV 记录数 20 条（不含表头，按 csv 记录数算而非物理行数）" "20" \
    "$(python -c '
import csv, io, sys
print(len(list(csv.reader(io.open(sys.argv[1], encoding="utf-8-sig")))) - 1)
' "$(cygpath -w "$EVID/fixture-bank-week10.csv")")"
  echo
  echo "--- 03-2 上传导入（POST /api/admin/import-questions，multipart 字段 file）---"
  upload "$EVID/fixture-bank-week10.csv" > "$EVID/resp-import-bank.json"
  head -1 "$EVID/resp-import-bank.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("created =", d["created"], "| skipped =", d["skipped"], "| total =", d["total"],
      "| 坏行 =", len(d["errors"]), "| 新建单元 =", d["unitCreated"], "| 新建关卡 =", d["levelCreated"],
      "| 该班可玩题数 =", d["enabledQuestions"])
'
  check "导入成功 20 题、零坏行、自动建 1 单元 2 关卡" "20|0|1|2" \
    "$(head -1 "$EVID/resp-import-bank.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("%d|%d|%d|%d" % (d["created"], len(d["errors"]), d["unitCreated"], d["levelCreated"]))
')"
  echo
  echo "--- 03-3 学生视角：演示单元与两个关卡（题目本体来自真题，题量 10/10）---"
  sql "SELECT l.seq AS 关卡序号, l.name AS 关卡, COUNT(*) AS 题数, MIN(CHAR_LENGTH(q.stem)) AS 最短题干, MAX(CHAR_LENGTH(q.stem)) AS 最长题干
       FROM cet46.levels l JOIN cet46.questions q ON q.level_id=l.id JOIN cet46.units u ON u.id=l.unit_id
       WHERE u.week_no=$WEEK_DEMO GROUP BY l.id ORDER BY l.seq;"
  LV_CLOZE=$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO AND u.class_id=$CLASS_ID AND l.seq=1;")
  LV_MATCH=$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO AND u.class_id=$CLASS_ID AND l.seq=2;")
  printf '%s %s\n' "$LV_CLOZE" "$LV_MATCH" > "$EVID/fixture-ids.txt"
  echo "演示关卡：选词填空 levelId=$LV_CLOZE，段落匹配 levelId=$LV_MATCH"
  check "入库 20 题：题型分布（选词填空/段落匹配）" "10/10" \
    "$(sql "SELECT CONCAT(SUM(q.type='cloze'),'/',SUM(q.type='match')) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO;")"
  check "入库 20 题：分套全是四级" "20" \
    "$(sql "SELECT COUNT(*) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO AND q.band='4';")"
  echo
  echo "--- 03-4 验收④入库无损：本题库与第 10 周真题逐题比对（题干 MD5 / 答案序列 / 选项 MD5）---"
  MISMATCH=$(sql "SELECT COUNT(*) FROM
      (SELECT MD5(stem) h, answer_idx a, MD5(options_json) o FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO) n
      LEFT JOIN
      (SELECT MD5(stem) h, answer_idx a, MD5(options_json) o FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=10 AND q.type IN ('cloze','match')) r
      ON r.h=n.h AND r.a=n.a AND r.o=n.o
      WHERE r.h IS NULL;")
  check "20 题逐题与真题一致（题干/答案/选项三项 MD5 全等）" "0" "$MISMATCH"
  check "最长题干 >= 5800 字（任务书口径，实为真题最长的一条）" "1" \
    "$(sql "SELECT IF(MAX(CHAR_LENGTH(q.stem))>=5800,1,0) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO AND q.type='match';")"
  check "最长题干与原题完全等长" \
    "$(sql "SELECT MAX(CHAR_LENGTH(q.stem)) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=10 AND q.type='match';")" \
    "$(sql "SELECT MAX(CHAR_LENGTH(q.stem)) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_DEMO AND q.type='match';")"
} > "$EVID/03-real-bank-import.log" 2>&1

# ================================================================ 04 验收③：paper 下发结构（报告贴样例）
{
  step "04 验收③：paper 接口下发 JSON 结构（选词填空整篇形态 + 段落匹配），并证明取题往返无损"
  bank_dump "$LV_CLOZE"
  bank_dump "$LV_MATCH"
  echo "--- 04-0 学生取选词填空关（level=$LV_CLOZE）---"
  api GET "/api/quiz/paper?level=$LV_CLOZE" "$TOKEN4" > "$EVID/resp-paper-cloze.json"
  last=$(tail -1 "$EVID/resp-paper-cloze.json")
  check "取卷 200" "[HTTP 200]" "$last"
  echo
  echo "--- 04-1 cloze 视图样例（前端拿到的就是这一份）---"
  head -1 "$EVID/resp-paper-cloze.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
q = d["questions"][0]
print("attemptId =", d["attemptId"], "| shuffleSeed =", d["shuffleSeed"], "| 题数 =", len(d["questions"]))
print("题目键 =", list(q.keys()))
c = q.get("cloze") or {}
print("cloze.passage 开头 120 字 =", repr(c["passage"][:120]))
print("cloze.passage 结尾 60 字  =", repr(c["passage"][-60:]))
print("cloze.blankNo =", c["blankNo"], "| blankSpan =", c["blankSpan"], "| blanks =", c["blanks"])
print("cloze.wordBank[0..2] =", json.dumps(c["wordBank"][:3], ensure_ascii=False))
print("cloze.wordBank 末项 =", json.dumps(c["wordBank"][-1], ensure_ascii=False), "（共", len(c["wordBank"]), "项）")
print("options（展示序，前端直接渲染）= ", json.dumps(q["options"], ensure_ascii=False))
print("stem 尾 40 字 =", repr(q["stem"][-40:]))
'
  echo
  echo "--- 04-2 取卷侧断言：视图字段、卷面不泄露答案、不提前下发听力原文 ---"
  head -1 "$EVID/resp-paper-cloze.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
qs = d["questions"]
bad = []
for q in qs:
    # 视图字段是 omitempty：不适用的那个键根本不出现，只能用 .get 取。
    c = q.get("cloze")
    if c is None or q.get("match") is not None:
        bad.append("题 %d 视图字段不对" % q["id"]); continue
    if c["blankSpan"] != 1:
        bad.append("题 %d blankSpan=%d（真题是「本题第 N 空」形态①）" % (q["id"], c["blankSpan"]))
    if len(c["blanks"]) != 10:
        bad.append("题 %d blanks=%s（篇内应有 10 个空号）" % (q["id"], c["blanks"]))
    if not (26 <= c["blankNo"] <= 35):
        bad.append("题 %d blankNo=%d" % (q["id"], c["blankNo"]))
    if len(c["wordBank"]) != 15 or [w["idx"] for w in c["wordBank"]] != list(range(15)):
        bad.append("题 %d 词表 idx 不是 0..14" % q["id"])
    if [w["label"] for w in c["wordBank"]] != [chr(65+i) for i in range(15)]:
        bad.append("题 %d 词表标号不是 A..O" % q["id"])
    if any(w["text"] != q["options"][w["idx"]] for w in c["wordBank"]):
        bad.append("题 %d 词表文本与展示序选项不一致" % q["id"])
print("选词填空 10 题的 cloze 视图检查：" + ("全部符合" if not bad else " / ".join(bad)))
print("blankNo 序列 =", [q.get("cloze", {}).get("blankNo") for q in qs])
'
  check "选词填空 10 题的 cloze 视图全部符合（A..O 词表 / 空号 26..35 / 词表=展示序）" "全部符合" \
    "$(head -1 "$EVID/resp-paper-cloze.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
qs = d["questions"]
bad = []
for q in qs:
    c = q.get("cloze")
    if c is None or q.get("match") is not None: bad.append("视图字段不对")
    elif c["blankSpan"] != 1 or len(c["blanks"]) != 10 or not (26 <= c["blankNo"] <= 35): bad.append("空号解析不对")
    elif len(c["wordBank"]) != 15 or [w["idx"] for w in c["wordBank"]] != list(range(15)): bad.append("词表 idx 不对")
    elif [w["label"] for w in c["wordBank"]] != [chr(65+i) for i in range(15)]: bad.append("词表标号不对")
    elif any(w["text"] != q["options"][w["idx"]] for w in c["wordBank"]): bad.append("词表文本与选项不一致")
print("全部符合" if not bad else " / ".join(sorted(set(bad))))
')"
  check "卷面不含答案字段（answerIdx / correctIdx / exp）" "0" \
    "$(head -1 "$EVID/resp-paper-cloze.json" | grep -c -E '\"answerIdx\"|\"correctIdx\"|\"exp\"')"
  check "卷面不含听力原文（S4 起 script 只在提交回执里给）" "0" \
    "$(head -1 "$EVID/resp-paper-cloze.json" | grep -c '\"script\"')"
  echo
  echo "--- 04-3 学生取段落匹配关（level=$LV_MATCH）：match 视图 + 段号带语义不洗牌 ---"
  api GET "/api/quiz/paper?level=$LV_MATCH" "$TOKEN4" > "$EVID/resp-paper-match.json"
  last=$(tail -1 "$EVID/resp-paper-match.json")
  check "取卷 200" "[HTTP 200]" "$last"
  head -1 "$EVID/resp-paper-match.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
q = d["questions"][0]
print("attemptId =", d["attemptId"], "| 题数 =", len(d["questions"]))
print("题目键 =", list(q.keys()))
m = q.get("match") or {}
print("match.title     =", repr(m["title"]))
print("match.statement =", repr(m["statement"]), "| statementNo =", m["statementNo"])
print("match.paragraphs 共", len(m["paragraphs"]), "段；第 1 段 =", json.dumps(m["paragraphs"][0], ensure_ascii=False)[:220], "…")
print("段落标号序列 =", [p["label"] for p in m["paragraphs"]])
print("段落 idx 序列 =", [p["idx"] for p in m["paragraphs"]])
print("options（展示序）= ", json.dumps(q["options"], ensure_ascii=False))
print("stem 尾 90 字 =", repr(q["stem"][-90:]))
'
  check "段落匹配 10 题的 match 视图全部符合（标题/16 段/陈述句）" "全部符合" \
    "$(head -1 "$EVID/resp-paper-match.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
bad = []
for q in d["questions"]:
    m = q.get("match")
    if m is None or q.get("cloze") is not None: bad.append("视图字段不对")
    elif len(m["paragraphs"]) != 16: bad.append("段数=%d" % len(m["paragraphs"]))
    elif not m["title"] or not m["statement"]: bad.append("标题/陈述句为空")
    elif [p["label"] for p in m["paragraphs"]] != [chr(65+i) for i in range(16)]: bad.append("段号不是 A..P")
    elif [p["idx"] for p in m["paragraphs"]] != list(range(16)): bad.append("段 idx 不是 0..15")
print("全部符合" if not bad else " / ".join(sorted(set(bad))))
')"
  check "match 不洗选项（展示序 == 题库序 A..P）" "A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P" \
    "$(head -1 "$EVID/resp-paper-match.json" | python -c 'import sys,json; print(",".join(json.loads(sys.stdin.read())["data"]["questions"][0]["options"]))')"
  check "卷面不含听力原文" "0" "$(head -1 "$EVID/resp-paper-match.json" | grep -c '\"script\"')"
  echo
  echo "--- 04-4 验收④取题侧：下发的 20 条题干 MD5 与第 10 周真题逐条相等（往返无损）---"
  CLOZE_EQ=$( [ "$(paper_stem_md5 "$EVID/resp-paper-cloze.json" cloze)" = "$(db_stem_md5 "u.week_no=10 AND q.type='cloze'")" ] && echo 一致 || echo 不一致 )
  MATCH_EQ=$( [ "$(paper_stem_md5 "$EVID/resp-paper-match.json" match)" = "$(db_stem_md5 "u.week_no=10 AND q.type='match'")" ] && echo 一致 || echo 不一致 )
  echo "选词填空 10 条题干 MD5 集合比对：$CLOZE_EQ"
  echo "段落匹配 10 条题干 MD5 集合比对：$MATCH_EQ"
  check "选词填空：卷面题干与真题逐条一致" "一致" "$CLOZE_EQ"
  check "段落匹配：卷面题干与真题逐条一致（含 6380 字长文）" "一致" "$MATCH_EQ"
  check "卷面最长题干 = 真题最长题干（6380 字）" \
    "$(sql "SELECT MAX(CHAR_LENGTH(q.stem)) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=10 AND q.type='match';")" \
    "$(head -1 "$EVID/resp-paper-match.json" | python -c 'import sys,json; print(max(len(q["stem"]) for q in json.loads(sys.stdin.read())["data"]["questions"]))')"
} > "$EVID/04-paper-shape.log" 2>&1

# ================================================================ 05 验收②：选词填空判分落库 + 错题本
{
  step "05 验收②-a：选词填空作答（4 题：2 对 2 错）→ 判分落 attempt_answers（题库坐标）+ 进错题本"
  A_CLOZE=$(pyget data.attemptId < "$EVID/resp-paper-cloze.json")
  echo "--- 05-0 组作答：正确答案用「真题答案词在展示数组里的下标」定位（前 2 题答对、后 2 题故意答错）---"
  python - "$EWIN/resp-paper-cloze.json" "$EWIN/bank-$LV_CLOZE.tsv" "$EWIN" <<'PYEOF'
import json, io, sys, hashlib
paper_p, bank_p, evid = sys.argv[1], sys.argv[2], sys.argv[3]
paper = json.loads(io.open(paper_p, encoding='utf-8').readline())["data"]
bank = {}
for line in io.open(bank_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, ans, hexopt = line.split('\t')
    bank[int(qid)] = ([int(x) for x in ans.split(',')], json.loads(bytes.fromhex(hexopt).decode('utf-8')))
answers, expect = [], []
for i, q in enumerate(paper["questions"][:4]):
    ans, opts = bank[q["id"]]
    right = [q["options"].index(opts[k]) for k in ans]
    if i < 2:
        picks = right
    else:
        picks = [(right[0] + 1) % len(q["options"])]
    answers.append({"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)})
    orig = [opts.index(q["options"][p]) for p in picks]
    expect.append("%d|%s|%d" % (q["id"], ",".join(str(o) for o in orig), 1 if i < 2 else 0))
io.open(evid + r"\body-submit-cloze.json", "w", encoding="utf-8").write(
    json.dumps({"attemptId": paper["attemptId"], "answers": answers}, ensure_ascii=False))
io.open(evid + r"\expect-cloze.txt", "w", encoding="utf-8").write("\n".join(expect) + "\n")
print("组好 4 题作答（题号 %s），期望落库（题库坐标|对错）：" % [a["questionId"] for a in answers])
for e in expect:
    print("   ", e)
PYEOF
  echo
  echo "--- 05-1 提交（POST /api/quiz/submit）---"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-cloze.json" > "$EVID/resp-submit-cloze.json"
  last=$(tail -1 "$EVID/resp-submit-cloze.json")
  check "提交 200" "[HTTP 200]" "$last"
  head -1 "$EVID/resp-submit-cloze.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("status =", d["status"], "| 进度 =", d["progress"])
print("逐题回执：")
for f in d["feedback"]:
    print("  题", f["questionId"], "| 对=", f["isCorrect"], "| 对了几空 =", f["matched"], "/", f["seqLen"],
          "| 我提交（展示坐标）=", f["pickedIdx"], "| 正确（展示坐标）=", f["correctIdx"],
          "| 基础/速度/连击 =", f["xp"]["base"], f["xp"]["speed"], f["xp"]["combo"], "| 连击数 =", f["streak"])
'
  echo
  echo "--- 05-2 判分口径断言 ---"
  check "feedback 4 条：2 对 2 错" "2/2" \
    "$(head -1 "$EVID/resp-submit-cloze.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"]; print("%d/%d"%(sum(1 for x in f if x["isCorrect"]), sum(1 for x in f if not x["isCorrect"])))')"
  check "单空题型：seqLen 恒为 1，答对 matched=1、答错 matched=0" "2/2:1,1:0,0" \
    "$(head -1 "$EVID/resp-submit-cloze.json" | python -c '
import sys, json
f = json.loads(sys.stdin.read())["data"]["feedback"]
right = [x for x in f if x["isCorrect"]]
wrong = [x for x in f if not x["isCorrect"]]
print("%d/%d:%s:%s" % (len(right), len(wrong), ",".join(str(x["matched"]) for x in right), ",".join(str(x["matched"]) for x in wrong)))
')"
  check "XP 三段：基础 2×20=40、速度 0（未上报耗时）、连击 0+5=5" "40/0/5" \
    "$(head -1 "$EVID/resp-submit-cloze.json" | python -c '
import sys, json
f = json.loads(sys.stdin.read())["data"]["feedback"]
print("%d/%d/%d" % (sum(x["xp"]["base"] for x in f), sum(x["xp"]["speed"] for x in f), sum(x["xp"]["combo"] for x in f)))
')"
  check "答错不给基础分（半对/全错 0 分口径与阅读题一致）" "0" \
    "$(head -1 "$EVID/resp-submit-cloze.json" | python -c '
import sys, json
f = json.loads(sys.stdin.read())["data"]["feedback"]
print(sum(x["xp"]["base"] for x in f if not x["isCorrect"]))
')"
  echo
  echo "--- 05-3 落库断言：attempt_answers 用题库坐标（跨学生可比）---"
  sql "SELECT question_id AS 题号, picked_idx AS 落库下标, is_correct AS 判对 FROM cet46.attempt_answers WHERE attempt_id=$A_CLOZE ORDER BY id;"
  GOT=$(sql "SELECT CONCAT(question_id,'|',picked_idx,'|',is_correct) FROM cet46.attempt_answers WHERE attempt_id=$A_CLOZE ORDER BY id;")
  WANT=$(cat "$EVID/expect-cloze.txt")
  if [ "$GOT" = "$WANT" ]; then
    check "attempt_answers 4 行与期望逐行一致（题库坐标 + 对错）" "一致 ✅" "一致 ✅"
  else
    check "attempt_answers 4 行与期望逐行一致（题库坐标 + 对错）" "与期望一致" "不一致：期望=$(echo "$WANT" | tr '\n' ' ') 实际=$(echo "$GOT" | tr '\n' ' ')"
  fi
  echo
  echo "--- 05-4 错题本断言：只有答错的 2 题进本、答对的 2 题不进 ---"
  sql "SELECT w.question_id AS 题号, q.type AS 题型, w.wrong_count AS 错次, w.mastered AS 已掌握
       FROM cet46.wrong_book w JOIN cet46.questions q ON q.id=w.question_id WHERE w.user_id=$UID4 ORDER BY w.question_id;"
  WRONG_QIDS=$(head -1 "$EVID/resp-submit-cloze.json" | python -c 'import sys,json; print(",".join(str(x["questionId"]) for x in json.loads(sys.stdin.read())["data"]["feedback"] if not x["isCorrect"]))')
  check "错题本 2 行、合计错次 2、已掌握 0" "2/2/0" \
    "$(sql "SELECT CONCAT(COUNT(*),'/',IFNULL(SUM(wrong_count),0),'/',IFNULL(SUM(mastered),0)) FROM cet46.wrong_book WHERE user_id=$UID4;")"
  check "错题本里的题号 = 我答错的那 2 题" "$WRONG_QIDS" \
    "$(sql "SELECT GROUP_CONCAT(question_id ORDER BY question_id) FROM cet46.wrong_book WHERE user_id=$UID4;")"
  check "答对的 2 题不在错题本" "0" \
    "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$UID4 AND question_id IN ($(head -1 "$EVID/resp-submit-cloze.json" | python -c 'import sys,json; print(",".join(str(x["questionId"]) for x in json.loads(sys.stdin.read())["data"]["feedback"] if x["isCorrect"]))'));")"
  echo
  echo "--- 05-5 账本权威：学生总分 == SELECT SUM(delta) FROM xp_ledger ---"
  check "本次入账 45 分（2 题基础 40 + 连击 5）" "45" \
    "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$UID4;")"
  api GET /api/quiz/levels "$TOKEN4" > "$EVID/resp-levels-after-cloze.json"
  check "接口回执的学生总分 == 账本求和" \
    "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$UID4;")" \
    "$(pyget data.xpTotal < "$EVID/resp-levels-after-cloze.json")"
} > "$EVID/05-cloze-judge.log" 2>&1

# ================================================================ 06 验收②：段落匹配判分落库 + 错题本
{
  step "06 验收②-b：段落匹配作答（3 题：2 对 1 错）→ 判分落 attempt_answers + 进错题本"
  A_MATCH=$(pyget data.attemptId < "$EVID/resp-paper-match.json")
  echo "--- 06-0 组作答：正确答案用「段落字母在展示数组里的下标」定位（match 不洗牌 → 展示坐标=题库坐标）---"
  python - "$EWIN/resp-paper-match.json" "$EWIN/bank-$LV_MATCH.tsv" "$EWIN" <<'PYEOF'
import json, io, sys
paper_p, bank_p, evid = sys.argv[1], sys.argv[2], sys.argv[3]
paper = json.loads(io.open(paper_p, encoding='utf-8').readline())["data"]
bank = {}
for line in io.open(bank_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, ans, hexopt = line.split('\t')
    bank[int(qid)] = ([int(x) for x in ans.split(',')], json.loads(bytes.fromhex(hexopt).decode('utf-8')))
answers, expect = [], []
for i, q in enumerate(paper["questions"][:3]):
    ans, opts = bank[q["id"]]
    right = [q["options"].index(opts[k]) for k in ans]
    picks = right if i < 2 else [(right[0] + 1) % len(q["options"])]
    answers.append({"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)})
    orig = [opts.index(q["options"][p]) for p in picks]
    expect.append("%d|%s|%d" % (q["id"], ",".join(str(o) for o in orig), 1 if i < 2 else 0))
io.open(evid + r"\body-submit-match.json", "w", encoding="utf-8").write(
    json.dumps({"attemptId": paper["attemptId"], "answers": answers}, ensure_ascii=False))
io.open(evid + r"\expect-match.txt", "w", encoding="utf-8").write("\n".join(expect) + "\n")
print("组好 3 题作答（题号 %s），期望落库（题库坐标|对错）：" % [a["questionId"] for a in answers])
for e in expect:
    print("   ", e)
PYEOF
  echo
  echo "--- 06-1 提交 ---"
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-match.json" > "$EVID/resp-submit-match.json"
  last=$(tail -1 "$EVID/resp-submit-match.json")
  check "提交 200" "[HTTP 200]" "$last"
  head -1 "$EVID/resp-submit-match.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("status =", d["status"], "| 进度 =", d["progress"])
for f in d["feedback"]:
    print("  题", f["questionId"], "| 对=", f["isCorrect"], "| 对了几空 =", f["matched"], "/", f["seqLen"],
          "| 我提交（展示坐标）=", f["pickedIdx"], "| 正确（展示坐标）=", f["correctIdx"],
          "| 基础/速度/连击 =", f["xp"]["base"], f["xp"]["speed"], f["xp"]["combo"], "| 连击数 =", f["streak"])
'
  echo
  echo "--- 06-2 断言：判分 / 落库 / 错题本 ---"
  check "feedback 3 条：2 对 1 错" "2/1" \
    "$(head -1 "$EVID/resp-submit-match.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"]; print("%d/%d"%(sum(1 for x in f if x["isCorrect"]), sum(1 for x in f if not x["isCorrect"])))')"
  check "段落匹配 XP 与阅读题同口径：基础 40、速度 0、连击 5" "40/0/5" \
    "$(head -1 "$EVID/resp-submit-match.json" | python -c '
import sys, json
f = json.loads(sys.stdin.read())["data"]["feedback"]
print("%d/%d/%d" % (sum(x["xp"]["base"] for x in f), sum(x["xp"]["speed"] for x in f), sum(x["xp"]["combo"] for x in f)))
')"
  check "match 不洗牌：正确项展示坐标 == 题库存的 answer_idx（段号带语义）" "一致" \
    "$(python -c '
import sys, json, io
paper = json.loads(io.open(sys.argv[1], encoding="utf-8").readline())["data"]
sub = json.loads(io.open(sys.argv[2], encoding="utf-8").readline())["data"]
bank = {}
for line in io.open(sys.argv[3], encoding="utf-8"):
    line = line.rstrip("\n")
    if not line.strip():
        continue
    qid, ans, _ = line.split("\t")
    bank[int(qid)] = ans
bad = []
for f in sub["feedback"]:
    if f["correctIdx"] != bank[f["questionId"]]:
        bad.append("题 %d：回执 %s vs 题库 %s" % (f["questionId"], f["correctIdx"], bank[f["questionId"]]))
print("一致" if not bad else " / ".join(bad))
' "$(cygpath -w "$EVID/resp-paper-match.json")" "$(cygpath -w "$EVID/resp-submit-match.json")" "$(cygpath -w "$EVID/bank-$LV_MATCH.tsv")")"
  GOT=$(sql "SELECT CONCAT(question_id,'|',picked_idx,'|',is_correct) FROM cet46.attempt_answers WHERE attempt_id=$A_MATCH ORDER BY id;")
  WANT=$(cat "$EVID/expect-match.txt")
  if [ "$GOT" = "$WANT" ]; then
    check "attempt_answers 3 行与期望逐行一致（题库坐标 + 对错）" "一致 ✅" "一致 ✅"
  else
    check "attempt_answers 3 行与期望逐行一致（题库坐标 + 对错）" "与期望一致" "不一致：期望=$(echo "$WANT" | tr '\n' ' ') 实际=$(echo "$GOT" | tr '\n' ' ')"
  fi
  WRONG_QIDS=$(head -1 "$EVID/resp-submit-match.json" | python -c 'import sys,json; print(",".join(str(x["questionId"]) for x in json.loads(sys.stdin.read())["data"]["feedback"] if not x["isCorrect"]))')
  check "错题本累计 3 行（选词填空 2 + 段落匹配 1）" "3" "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$UID4;")"
  check "本轮错的那 1 题进了错题本" "1" "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$UID4 AND question_id IN ($WRONG_QIDS);")"
  check "账本累计 45+45=90 分" "90" "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$UID4;")"
} > "$EVID/06-match-judge.log" 2>&1

# ================================================================ 07 整篇多空形态 + 半对口径（HTTP 实测）
{
  step "07 整篇形态（3 空一题）+ 半对口径实测：对 2 空错 1 空 → 判不对、0 分、但回执回报 2/3"
  echo "--- 07-0 教师建演示关（第 $WEEK_DEMO 周演示单元第 3 关）+ 一道整篇 3 空选词填空 ---"
  DEMO_UNIT=$(sql "SELECT id FROM cet46.units WHERE week_no=$WEEK_DEMO AND class_id=$CLASS_ID;")
  printf '{"unitId":%s,"seq":3,"name":"演示关 · 整篇选词填空（3 空）","type":"reading","timeLimit":300,"isBoss":false}' "$DEMO_UNIT" > "$EVID/body-demo-level.json"
  api POST /api/admin/levels "$TOKEN" "$EVID/body-demo-level.json" > "$EVID/resp-demo-level.json"
  LV_W3=$(pyget data.id < "$EVID/resp-demo-level.json")
  printf '{"levelId":%s,"band":"4","type":"cloze","stem":"The team (26) the village and the road had been (27) by the storm, so trucks had to (28) a longer route.","options":["village","reached","blocked","take","damaged","seen","decided","supplies","cleared","appeared","taught","became","rose","told","found"],"answerIdx":"0,1,2","exp":"演示用解析：整篇形态（无中文标记）一次答 3 空，答案序列按空号顺序。","tip":"演示用考点","knowledgeTag":"演示考点"}' "$LV_W3" > "$EVID/body-demo-q.json"
  api POST /api/admin/questions "$TOKEN" "$EVID/body-demo-q.json" > "$EVID/resp-demo-q.json"
  last=$(tail -1 "$EVID/resp-demo-q.json")
  check "教师建整篇选词填空题 200（格式校验放行合法序列）" "[HTTP 200]" "$last"
  bank_dump "$LV_W3"
  echo
  echo "--- 07-1 学生取卷：整篇形态的 cloze 视图（blankNo=0、blankSpan=3）---"
  api GET "/api/quiz/paper?level=$LV_W3" "$TOKEN4" > "$EVID/resp-paper-w3-1.json"
  head -1 "$EVID/resp-paper-w3-1.json" | python -c '
import sys, json
q = json.loads(sys.stdin.read())["data"]["questions"][0]
c = q.get("cloze") or {}
print("blankNo =", c["blankNo"], "| blankSpan =", c["blankSpan"], "| blanks =", c["blanks"], "| 词表", len(c["wordBank"]), "项")
print("passage =", repr(c["passage"][:80]))
'
  check "整篇形态视图：blankNo=0 / blankSpan=3 / blanks=[26,27,28]" "0/3/[26, 27, 28]" \
    "$(head -1 "$EVID/resp-paper-w3-1.json" | python -c 'import sys,json; c=json.loads(sys.stdin.read())["data"]["questions"][0]["cloze"]; print("%d/%d/%s" % (c["blankNo"], c["blankSpan"], c["blanks"]))')"
  echo
  echo "--- 07-2 半对提交：[对,对,错] → isCorrect=false、matched=2/3、XP 全 0 ---"
  python - "$EWIN/resp-paper-w3-1.json" "$EWIN/bank-$LV_W3.tsv" "$EWIN" <<'PYEOF'
import json, io, sys
paper_p, bank_p, evid = sys.argv[1], sys.argv[2], sys.argv[3]
paper = json.loads(io.open(paper_p, encoding='utf-8').readline())["data"]
q = paper["questions"][0]
ans, opts = None, None
for line in io.open(bank_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, a, hexopt = line.split('\t')
    if int(qid) == q["id"]:
        ans, opts = [int(x) for x in a.split(',')], json.loads(bytes.fromhex(hexopt).decode('utf-8'))
right = [q["options"].index(opts[k]) for k in ans]
picks = right[:2] + [(right[2] + 1) % len(q["options"])]
body = {"attemptId": paper["attemptId"], "answers": [{"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)}]}
io.open(evid + r"\body-submit-w3-half.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
expect = "%d|%s|0" % (q["id"], ",".join(str(opts.index(q["options"][p])) for p in picks))
io.open(evid + r"\expect-w3-half.txt", "w", encoding="utf-8").write(expect + "\n")
print("提交（展示坐标）=", picks, "正确（展示坐标）=", right)
print("期望落库（题库坐标|对错）：", expect)
PYEOF
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-w3-half.json" > "$EVID/resp-submit-w3-half.json"
  head -1 "$EVID/resp-submit-w3-half.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
f = d["feedback"][0]
print("status =", d["status"], "| isCorrect =", f["isCorrect"], "| 对了几空 =", f["matched"], "/", f["seqLen"],
      "| XP =", f["xp"], "| 结算 =", "无（本关已答完）" if d["settlement"] is None else d["settlement"])
print("我还剩的爱心 =", d["progress"]["livesLeft"], "（半对算错，扣 1 颗）")
'
  check "半对：判不对（isCorrect=false）" "False" "$(pyget data.feedback.0.isCorrect < "$EVID/resp-submit-w3-half.json")"
  check "半对：回执如实回报 2/3（前端可显示「10 空对了 7 空」）" "2/3" \
    "$(head -1 "$EVID/resp-submit-w3-half.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"][0]; print("%d/%d"%(f["matched"],f["seqLen"]))')"
  check "半对：0 分（基础/速度/连击全 0）" "0/0/0" \
    "$(head -1 "$EVID/resp-submit-w3-half.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"][0]; print("%d/%d/%d"%(f["xp"]["base"],f["xp"]["speed"],f["xp"]["combo"]))')"
  A_W3_HALF=$(pyget data.attemptId < "$EVID/resp-paper-w3-1.json")
  check "半对落库：attempt_answers 存题库坐标序列（三个空一行）" "$(cat "$EVID/expect-w3-half.txt")" \
    "$(sql "SELECT CONCAT(question_id,'|',picked_idx,'|',is_correct) FROM cet46.attempt_answers WHERE attempt_id=$A_W3_HALF ORDER BY id;")"
  check "半对进错题本（累计 4 行）" "4" "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$UID4;")"
  check "半对本题 0 分入账（本关答完按 S3「完成即通关」另结 30，总分 90+30=120）" "120" "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$UID4;")"
  echo
  echo "--- 07-3 同一题全对：matched=3/3、+20 分、本关 1/1 通关给通关 30 + 三星 20（通关奖励 = S3 既有口径：非 Boss 关每次结算都发，含 0 对通关与重刷）---"
  api GET "/api/quiz/paper?level=$LV_W3" "$TOKEN4" > "$EVID/resp-paper-w3-2.json"
  python - "$EWIN/resp-paper-w3-2.json" "$EWIN/bank-$LV_W3.tsv" "$EWIN" <<'PYEOF'
import json, io, sys
paper_p, bank_p, evid = sys.argv[1], sys.argv[2], sys.argv[3]
paper = json.loads(io.open(paper_p, encoding='utf-8').readline())["data"]
q = paper["questions"][0]
for line in io.open(bank_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, a, hexopt = line.split('\t')
    if int(qid) == q["id"]:
        ans, opts = [int(x) for x in a.split(',')], json.loads(bytes.fromhex(hexopt).decode('utf-8'))
picks = [q["options"].index(opts[k]) for k in ans]
body = {"attemptId": paper["attemptId"], "answers": [{"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)}]}
io.open(evid + r"\body-submit-w3-full.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
print("全对提交（展示坐标）=", picks, "| 二次取卷 attemptId =", paper["attemptId"], "| resumed =", paper["resumed"])
PYEOF
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-w3-full.json" > "$EVID/resp-submit-w3-full.json"
  head -1 "$EVID/resp-submit-w3-full.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
f = d["feedback"][0]
s = d["settlement"]
print("status =", d["status"], "| isCorrect =", f["isCorrect"], "| 对了几空 =", f["matched"], "/", f["seqLen"], "| XP =", f["xp"])
print("结算：星级 =", s["stars"], "| 正确率 =", s["ratio"], "| 本次 XP =", s["xpTotal"], "| 总分 =", s["xpTotalAll"],
      "| 首刷 =", s["firstClear"], "| 明细 =", [(r["label"], r["delta"]) for r in s["xpRows"]])
'
  check "全对：matched=3/3" "True/3/3" \
    "$(head -1 "$EVID/resp-submit-w3-full.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"][0]; print("%s/%d/%d"%(f["isCorrect"],f["matched"],f["seqLen"]))')"
  check "全对：本题 +20（基础 20、速度 0、连击 0）" "20/0/0" \
    "$(head -1 "$EVID/resp-submit-w3-full.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"][0]; print("%d/%d/%d"%(f["xp"]["base"],f["xp"]["speed"],f["xp"]["combo"]))')"
  check "本关 1/1 通关：本次入账 20+30+20=70（二次结算仍按 S3 口径发通关 30），总分 120+70=190" "70/190" \
    "$(head -1 "$EVID/resp-submit-w3-full.json" | python -c 'import sys,json; s=json.loads(sys.stdin.read())["data"]["settlement"]; print("%d/%d"%(s["xpTotal"], s["xpTotalAll"]))')"
  check "账本求和 == 回执总分（权威口径）" \
    "$(sql "SELECT IFNULL(SUM(delta),0) FROM cet46.xp_ledger WHERE user_id=$UID4;")" \
    "$(pyget data.settlement.xpTotalAll < "$EVID/resp-submit-w3-full.json")"
  check "全对之后该题仍是错题（不会自动移出错题本，答对才置已掌握）" "1" \
    "$(sql "SELECT COUNT(*) FROM cet46.wrong_book WHERE user_id=$UID4 AND question_id=$(pyget data.feedback.0.questionId < "$EVID/resp-submit-w3-full.json");")"
  check "错题本里该题已标记掌握（mastered=1）" "1" \
    "$(sql "SELECT mastered FROM cet46.wrong_book WHERE user_id=$UID4 AND question_id=$(pyget data.feedback.0.questionId < "$EVID/resp-submit-w3-full.json");")"
} > "$EVID/07-whole-passage-half.log" 2>&1

# ================================================================ 08 听力原文 script 列接通（19 列 / 老 18 列）
{
  step "08 听力原文闭环：19 列带「听力原文」入库 → 卷面不下发 → 答完回执下发；老 18 列把原文塞解析也能自动拆列"
  echo "--- 08-0 生成并导入 19 列听力题（第 $WEEK_LIS 周演示单元第 1 关）---"
  python - "$EWIN/fixture-listening-19.csv" "$WEEK_LIS" "$CLASS_NAME" <<'PYEOF'
import csv, io, sys
out, week, cls = sys.argv[1], int(sys.argv[2]), sys.argv[3]
head = ['班级','单元序号','单元名称','关卡序号','关卡名称','关卡类型','限时(分钟)','是否Boss','备考目标','题型',
        '题干','选项','正确答案','考点','解析','听力原文','知识点','难度','启用']
script = "W: Good morning. I'd like to open a savings account, please.\nM: Certainly. May I see your ID card and a proof of address?"
row = [cls, week, 'S4听力演示单元', 1, '听力 · 脚本演示', '阅读', 8, '否', '四级', '听力',
       'What does the woman want to do?', 'Open a savings account|Close her account|Ask for a loan|Change her address', 'A',
       '听力细节题：抓 woman 的第一句诉求', 'W 开头想开储蓄账户，M 请她出示证件与地址证明。',
       script, '演示', 1, '是']
with io.open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(head)
    w.writerow(row)
print('19 列听力题 fixture 写出：%s（听力原文 %d 字）' % (out, len(script)))
PYEOF
  upload "$EVID/fixture-listening-19.csv" > "$EVID/resp-import-lis19.json"
  head -1 "$EVID/resp-import-lis19.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("created =", d["created"], "| 坏行 =", len(d["errors"]), "| 新建单元 =", d["unitCreated"], "| 新建关卡 =", d["levelCreated"])
'
  LV_LIS=$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_LIS AND u.class_id=$CLASS_ID AND l.seq=1;")
  BANK_LIS=$(sql "SELECT id FROM cet46.questions WHERE level_id=$LV_LIS;")
  check "19 列文件导入成功（有「听力原文」列）" "1|0" \
    "$(head -1 "$EVID/resp-import-lis19.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print("%d|%d"%(d["created"], len(d["errors"])))')"
  check "听力原文落库（与 CSV 里的原文逐字节一致）" \
    "$(python -c '
import hashlib, io
s = "W: Good morning. I\u0027d like to open a savings account, please.\nM: Certainly. May I see your ID card and a proof of address?"
print(hashlib.md5(s.encode("utf-8")).hexdigest())')" \
    "$(sql "SELECT MD5(script) FROM cet46.questions WHERE level_id=$LV_LIS;")"
  check "19 列导入：解析列原样入库（没有被原文块污染）" "MD5一致" \
    "$(sql "SELECT IF(MD5(exp)=MD5('W 开头想开储蓄账户，M 请她出示证件与地址证明。'),'MD5一致','不一致') FROM cet46.questions WHERE level_id=$LV_LIS;")"
  echo
  echo "--- 08-1 卷面不下发原文（取卷时看不到 script 字段）---"
  bank_dump "$LV_LIS"
  api GET "/api/quiz/paper?level=$LV_LIS" "$TOKEN4" > "$EVID/resp-paper-lis.json"
  last=$(tail -1 "$EVID/resp-paper-lis.json")
  check "取卷 200" "[HTTP 200]" "$last"
  echo "卷面题目键 = $(head -1 "$EVID/resp-paper-lis.json" | python -c 'import sys,json; print(list(json.loads(sys.stdin.read())["data"]["questions"][0].keys()))')"
  check "卷面不含 script 字段（答前下发等于送答案）" "0" "$(head -1 "$EVID/resp-paper-lis.json" | grep -c '\"script\"')"
  echo
  echo "--- 08-2 答完回执下发原文（与解析一起给）---"
  python - "$EWIN/resp-paper-lis.json" "$EWIN/bank-$LV_LIS.tsv" "$EWIN" <<'PYEOF'
import json, io, sys
paper_p, bank_p, evid = sys.argv[1], sys.argv[2], sys.argv[3]
paper = json.loads(io.open(paper_p, encoding='utf-8').readline())["data"]
q = paper["questions"][0]
for line in io.open(bank_p, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    qid, a, hexopt = line.split('\t')
    if int(qid) == q["id"]:
        ans, opts = [int(x) for x in a.split(',')], json.loads(bytes.fromhex(hexopt).decode('utf-8'))
picks = [q["options"].index(opts[k]) for k in ans]
body = {"attemptId": paper["attemptId"], "answers": [{"questionId": q["id"], "pickedIdx": ",".join(str(p) for p in picks)}]}
io.open(evid + r"\body-submit-lis.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
print("答对听力题（展示坐标）=", picks)
PYEOF
  api POST /api/quiz/submit "$TOKEN4" "$EVID/body-submit-lis.json" > "$EVID/resp-submit-lis.json"
  head -1 "$EVID/resp-submit-lis.json" | python -c '
import sys, json
f = json.loads(sys.stdin.read())["data"]["feedback"][0]
print("isCorrect =", f["isCorrect"], "| 回执里的听力原文 =", repr(f["script"]))
print("回执里的解析 =", repr(f["exp"]))
'
  check "答完回执带着听力原文（与库里一致）" \
    "$(sql "SELECT MD5(script) FROM cet46.questions WHERE level_id=$LV_LIS;")" \
    "$(head -1 "$EVID/resp-submit-lis.json" | python -c 'import sys,json,hashlib; print(hashlib.md5(json.loads(sys.stdin.read())["data"]["feedback"][0]["script"].encode("utf-8")).hexdigest())')"
  check "答完回执带着解析（即时反馈口径不变）" "1" \
    "$(head -1 "$EVID/resp-submit-lis.json" | python -c 'import sys,json; f=json.loads(sys.stdin.read())["data"]["feedback"][0]; print(1 if f["exp"] else 0)')"
  echo
  echo "--- 08-3 老 18 列文件（无「听力原文」列，原文塞在解析开头）→ 自动拆列 ---"
  python - "$EWIN/fixture-legacy18.csv" "$WEEK_LIS" "$CLASS_NAME" <<'PYEOF'
import csv, io, sys
out, week, cls = sys.argv[1], int(sys.argv[2]), sys.argv[3]
head = ['班级','单元序号','单元名称','关卡序号','关卡名称','关卡类型','限时(分钟)','是否Boss','备考目标','题型',
        '题干','选项','正确答案','考点','解析','知识点','难度','启用']   # 18 列：S4 之前的模板
exp = ("【听力原文】\nM: The train leaves at eight, so we should be at the station by half past seven.\n"
       "【解析】\n男孩说八点发车、七点半到站，故选 B。")
row = [cls, week, 'S4听力演示单元', 2, '听力 · 老文件演示', '阅读', 8, '否', '四级', '听力',
       'When should they get to the station?', 'At 7:00|At 7:30|At 8:00|At 8:30', 'B',
       '听力时间细节题', exp, '演示', 1, '是']
with io.open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(head)
    w.writerow(row)
print('18 列老文件 fixture 写出：%s（表头 %d 列，解析列以「【听力原文】」开头）' % (out, len(head)))
PYEOF
  upload "$EVID/fixture-legacy18.csv" > "$EVID/resp-import-legacy.json"
  head -1 "$EVID/resp-import-legacy.json" | python -c '
import sys, json
d = json.loads(sys.stdin.read())["data"]
print("created =", d["created"], "| 坏行 =", len(d["errors"]), "| 新建关卡 =", d["levelCreated"], "（老文件少一列不该报错）")
'
  LV_LIS2=$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_LIS AND u.class_id=$CLASS_ID AND l.seq=2;")
  check "老 18 列文件照常导入（缺「听力原文」列不报错）" "1|0" \
    "$(head -1 "$EVID/resp-import-legacy.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print("%d|%d"%(d["created"], len(d["errors"])))')"
  echo "拆列结果："
  sql "SELECT IFNULL(script,'(空)') AS 听力原文, exp AS 解析 FROM cet46.questions WHERE level_id=$LV_LIS2\G"
  check "解析列开头的【听力原文】块被拆进 script 列" "1" \
    "$(sql "SELECT IF(script LIKE 'M: The train leaves at eight%','1','0') FROM cet46.questions WHERE level_id=$LV_LIS2;")"
  check "解析列只剩【解析】块（没有原文重复）" "1" \
    "$(sql "SELECT IF(exp LIKE '【解析】%' AND exp NOT LIKE '%The train leaves at eight%','1','0') FROM cet46.questions WHERE level_id=$LV_LIS2;")"
  echo
  echo "--- 08-4 老 18 列普通题（解析里没有原文块）→ 不报错、script 留空 ---"
  python - "$EWIN/fixture-legacy18-plain.csv" "$WEEK_LIS" "$CLASS_NAME" <<'PYEOF'
import csv, io, sys
out, week, cls = sys.argv[1], int(sys.argv[2]), sys.argv[3]
head = ['班级','单元序号','单元名称','关卡序号','关卡名称','关卡类型','限时(分钟)','是否Boss','备考目标','题型',
        '题干','选项','正确答案','考点','解析','知识点','难度','启用']
row = [cls, week, 'S4听力演示单元', 3, '阅读 · 老文件演示', '阅读', 8, '否', '四级', '阅读',
       'What is the main idea of the passage?', 'A|B|C|D', 'C', '主旨题', '首段点题，故选 C。', '演示', 1, '是']
with io.open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(head)
    w.writerow(row)
print('18 列普通题 fixture 写出：%s' % out)
PYEOF
  upload "$EVID/fixture-legacy18-plain.csv" > "$EVID/resp-import-legacy-plain.json"
  LV_LIS3=$(sql "SELECT l.id FROM cet46.levels l JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no=$WEEK_LIS AND u.class_id=$CLASS_ID AND l.seq=3;")
  check "老 18 列普通题导入成功、script 留空" "1|0|1" \
    "$(head -1 "$EVID/resp-import-legacy-plain.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]; print("%d|%d|"%(d["created"], len(d["errors"])), end="")')$(sql "SELECT IF(IFNULL(script,'')='','1','0') FROM cet46.questions WHERE level_id=$LV_LIS3;")"
} > "$EVID/08-listening-script.log" 2>&1

# ================================================================ 09 验收⑤：模板 19 列 + 导出往返
{
  step "09 验收⑤：模板下载（19 列，含「听力原文」）+ 导出 xlsx 往返 + 导入侧举证（08 已实跑）"
  curl -sS -o "$EVID/fixture-template.xlsx" -w '[HTTP %{http_code}]\n' "$BASE/api/admin/import-questions/template" -H "Authorization: Bearer $TOKEN"
  echo "模板落盘：fixture-template.xlsx（$(stat -c%s "$EVID/fixture-template.xlsx") 字节）"
  python -c '
import openpyxl, sys
wb = openpyxl.load_workbook(sys.argv[1])
print("工作表 =", wb.sheetnames)
ws = wb["题库"]
head = [c.value for c in ws[1] if c.value]
expect = ["班级","单元序号","单元名称","关卡序号","关卡名称","关卡类型","限时(分钟)","是否Boss","备考目标","题型",
          "题干","选项","正确答案","考点","解析","听力原文","知识点","难度","启用"]
print("模板表头（%d 列）= %s" % (len(head), head))
print("与 qbank.TemplateHeaders 期望列序一致：" + ("是 ✅" if head == expect else "否 ❌ 期望=%s" % expect))
print("「听力原文」在第 %d 列（1 基）" % (head.index("听力原文") + 1))
help_ws = wb["填写说明"]
rows = [tuple(str(c.value) for c in r) for r in help_ws.iter_rows()]
print("填写说明里提到「听力原文」的行：")
for r in rows:
    if any("听力原文" in c for c in r if c):
        print("   ", " | ".join(c for c in r if c)[:200])
' "$(cygpath -w "$EVID/fixture-template.xlsx")"
  HEAD_EQ=$(python -c '
import openpyxl, sys
ws = openpyxl.load_workbook(sys.argv[1])["题库"]
head = [c.value for c in ws[1] if c.value]
expect = ["班级","单元序号","单元名称","关卡序号","关卡名称","关卡类型","限时(分钟)","是否Boss","备考目标","题型",
          "题干","选项","正确答案","考点","解析","听力原文","知识点","难度","启用"]
print("19|是" if head == expect else "%d|否" % len(head))
' "$(cygpath -w "$EVID/fixture-template.xlsx")")
  check "模板 19 列且列序与 qbank.TemplateHeaders 一致" "19|是" "$HEAD_EQ"
  check "「听力原文」列在模板第 16 列（解析列之后）" "16" \
    "$(python -c '
import openpyxl, sys
ws = openpyxl.load_workbook(sys.argv[1])["题库"]
head = [c.value for c in ws[1] if c.value]
print(head.index("听力原文") + 1)
' "$(cygpath -w "$EVID/fixture-template.xlsx")")"
  check "我的 fixture CSV 表头 == 模板表头（导入导出同列序）" "一致" \
    "$(python -c '
import csv, io, openpyxl, sys
head_csv = next(csv.reader(io.open(sys.argv[1], encoding="utf-8-sig")))
ws = openpyxl.load_workbook(sys.argv[2])["题库"]
head_xlsx = [c.value for c in ws[1] if c.value]
print("一致" if head_csv == head_xlsx else "不一致：%s vs %s" % (head_csv, head_xlsx))
' "$(cygpath -w "$EVID/fixture-bank-week10.csv")" "$(cygpath -w "$EVID/fixture-template.xlsx")")"
  echo
  echo "--- 09-1 导出侧（qbank.WriteXLSX 往返）与老文件兼容的 Go 单测举证 ---"
  go test ./internal/qbank/ -run 'TestTemplate|TestScript|TestAnswerIndexes' -v 2>&1 | tr -d '\000' | grep -E '^(=== RUN|--- PASS|--- FAIL|ok|FAIL)'
  check "qbank 模板/script/答案序列用例全绿" "0" \
    "$(go test ./internal/qbank/ -run 'TestTemplate|TestScript|TestAnswerIndexes' -v 2>&1 | tr -d '\000' | grep -c '^--- FAIL')"
  go test ./internal/service/ -run 'TestImportWritesScriptAndChecksNewTypeShapes|TestImportAcceptsLongMatchStem' -v 2>&1 | tr -d '\000' | grep -E '^--- (PASS|FAIL)'
  check "导入服务：script 落库 + 老 18 列兼容 + 长文放行（2 条用例）" "2" \
    "$(go test ./internal/service/ -run 'TestImportWritesScriptAndChecksNewTypeShapes|TestImportAcceptsLongMatchStem' -v 2>&1 | tr -d '\000' | grep -c '^--- PASS')"
} > "$EVID/09-template-script-column.log" 2>&1

# ================================================================ 10 题干上限 8000（maxStemLen 并入本阶段提交）
{
  step "10 题干上限实测：教师建题 8000 字放行、8001 字拒绝（maxStemLen=8000 随 S4 入库）"
  python - "$EWIN" "$LV_LIS3" <<'PYEOF'
import io, json, sys
evid, level = sys.argv[1], int(sys.argv[2])
def body(n):
    head = "Exercise and Dementia\nA) "
    unit = "long paragraph text "
    k, r = divmod(n - len(head), len(unit))
    stem = head + unit * k + "x" * r
    assert len(stem) == n, len(stem)
    return {"levelId": level, "band": "4", "type": "match", "stem": stem,
            "options": ["A", "B", "C", "D"], "answerIdx": "0", "exp": "上限实测", "tip": "上限实测"}
for n in (8000, 8001):
    io.open(evid + r"\body-stem%d.json" % n, "w", encoding="utf-8").write(json.dumps(body(n), ensure_ascii=False))
print("写好两具请求体：题干 8000 字 / 8001 字（同一演示关卡）")
PYEOF
  api POST /api/admin/questions "$TOKEN" "$EVID/body-stem8000.json" > "$EVID/resp-stem8000.json"
  api POST /api/admin/questions "$TOKEN" "$EVID/body-stem8001.json" > "$EVID/resp-stem8001.json"
  echo "8000 字：" ; tail -1 "$EVID/resp-stem8000.json"
  echo "8001 字：" ; head -1 "$EVID/resp-stem8001.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read()); print("code =", d["code"], "| message =", d["message"], "| data =", d["data"])'
  tail -1 "$EVID/resp-stem8001.json"
  check "8000 字题干放行" "[HTTP 200]" "$(tail -1 "$EVID/resp-stem8000.json")"
  check "8001 字题干拒绝（400）" "[HTTP 400]" "$(tail -1 "$EVID/resp-stem8001.json")"
  # 统一信封的字段是 code/message/data（不是 msg）——S4 起 maxStemLen 由 2000 放宽到 8000，报错文案带上限值。
  check "拒绝文案说明上限" "题干超过 8000 字" \
    "$(head -1 "$EVID/resp-stem8001.json" | python -c 'import sys,json; d=json.loads(sys.stdin.read()); print(d["message"])')"
  check "8000 字题落库（题干长度一致）" "8000" \
    "$(sql "SELECT CHAR_LENGTH(stem) FROM cet46.questions WHERE level_id=$LV_LIS3 AND type='match';")"
} > "$EVID/10-stem-limit.log" 2>&1

# ================================================================ 11 数据模型红线
{
  step "11 红线核对：§7 的 17 张表一张不多；questions 列定义与开发方案 §4 一致（S4 靠已有 script 列，不加列）"
  for tbl in questions levels units; do
    "${MYSQL[@]}" -e "SHOW CREATE TABLE cet46.$tbl\G"
  done
  echo
  echo "--- 表清单对照（脚本内置期望）---"
  TABLES_VERDICT=$(sql "SELECT table_name FROM information_schema.tables WHERE table_schema='cet46' ORDER BY table_name;" | python -c '
import sys
expect = ["attempt_answers","attempts","audit_log","classes","coupon_redeems","coupons","diagnoses","levels",
          "questions","reminders","seasons","team_members","teams","units","users","wrong_book","xp_ledger"]
got = [l.strip() for l in sys.stdin.read().split("\n") if l.strip()]
ok = got == expect
print("17 张表与开发方案 §4 完全一致 ✅" if ok else "表清单不一致 ❌")
if not ok:
    print("  实际 =", got)
    print("  期望 =", expect)
sys.exit(0 if ok else 1)
')
  echo "$TABLES_VERDICT"
  check "表清单：17 张，一张不多一张不少" "17 张表与开发方案 §4 完全一致 ✅" "$TABLES_VERDICT"
  SCHEMA_VERDICT=$(
    sql "SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema='cet46' AND table_name='questions' ORDER BY ordinal_position;" | python -c '
import sys
expect = ["id","level_id","band","type","stem","script","options_json","answer_idx","tip","exp","knowledge_tag",
          "difficulty","enabled","listen_subtype","created_at"]
got = [l.strip() for l in sys.stdin.read().split("\n") if l.strip()]
ok = got == expect
print("questions 列定义与 §4 一致（含已有 script 列）✅" if ok else "questions 列定义不一致 ❌")
if not ok:
    print("  实际 =", got)
    print("  期望 =", expect)
'
  )
  echo "$SCHEMA_VERDICT"
  check "questions 列定义一致（S4 未加列，script 是既有字段）" "questions 列定义与 §4 一致（含已有 script 列）✅" "$SCHEMA_VERDICT"
} > "$EVID/11-schema-redline.log" 2>&1

# ================================================================ 12/13 测试与一键校验
{
  step "12 go test ./...（服务层 + router 层 HTTP 全链路）"
  go test ./... 2>&1 | tr -d '\000'
  echo
  step "12b S4 相关用例逐个列出（判分引擎 + 导入服务 + router 全链路）"
  go test ./internal/quiz/ ./internal/qbank/ ./internal/service/ ./internal/router/ -v 2>&1 | tr -d '\000' \
    | grep -E '^--- (PASS|FAIL)' | grep -v '/'
  echo
  echo "PASS 行数 = $(go test ./... -v 2>&1 | tr -d '\000' | grep -c '^--- PASS')，FAIL 行数 = $(go test ./... -v 2>&1 | tr -d '\000' | grep -c '^--- FAIL')"
} > "$EVID/12-gotest.log" 2>&1

{
  step "13 scripts/verify.sh（gofmt + go vet + go test + go build + eslint + 前端构建）"
} > "$EVID/13-verify-sh.log" 2>&1
bash "$ROOT/scripts/verify.sh" >> "$EVID/13-verify-sh.log" 2>&1
echo "verify.sh 退出码: $?" >> "$EVID/13-verify-sh.log"

# ================================================================ 清理：演示数据删干净，真题与真实账号不动
{
  step "99 清理：删演示学生 $STU 及其流水 + 删第 $WEEK_DEMO/$WEEK_LIS 周演示单元（教师接口级联删关卡与题目）"
  sql "SELECT COUNT(*) AS 删除前_attempts FROM cet46.attempts;
       SELECT COUNT(*) AS 删除前_ledger FROM cet46.xp_ledger;"
  sql "DELETE FROM cet46.attempt_answers WHERE attempt_id IN (SELECT id FROM cet46.attempts WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU'));
       DELETE FROM cet46.attempts  WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.xp_ledger WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.wrong_book WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.diagnoses WHERE user_id IN (SELECT id FROM cet46.users WHERE username='$STU');
       DELETE FROM cet46.users WHERE username='$STU';"
  echo
  echo "--- 删演示单元（DELETE /api/admin/units/:id 会连带删掉它的关卡与题目）---"
  for wk in "$WEEK_DEMO" "$WEEK_LIS"; do
    unit=$(sql "SELECT id FROM cet46.units WHERE week_no=$wk AND class_id=$CLASS_ID;")
    if [ -n "$unit" ]; then
      api DELETE "/api/admin/units/$unit" "$TOKEN" > "$EVID/resp-demo-unit-del-$wk.json"
      echo "第 $wk 周演示单元（id=$unit）：$(tail -1 "$EVID/resp-demo-unit-del-$wk.json")"
    else
      echo "第 $wk 周没有演示单元（跳过）"
    fi
  done
  echo
  sql "SELECT
        (SELECT COUNT(*) FROM cet46.users WHERE username='$STU') AS 演示学生,
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
  check "演示学生已删净" "0" "$(sql "SELECT COUNT(*) FROM cet46.users WHERE username='$STU';")"
  check "五张表全空（attempts/attempt_answers/xp_ledger/wrong_book/diagnoses）" "0/0/0/0/0" \
    "$(sql "SELECT CONCAT((SELECT COUNT(*) FROM cet46.attempts),'/',(SELECT COUNT(*) FROM cet46.attempt_answers),'/',(SELECT COUNT(*) FROM cet46.xp_ledger),'/',(SELECT COUNT(*) FROM cet46.wrong_book),'/',(SELECT COUNT(*) FROM cet46.diagnoses));")"
  check "演示单元已删（第 13/14 周）" "0" \
    "$(sql "SELECT COUNT(*) FROM cet46.units WHERE week_no IN ($WEEK_DEMO,$WEEK_LIS) AND class_id=$CLASS_ID;")"
  check "单元数回到 4" "4" "$(sql "SELECT COUNT(*) FROM cet46.units;")"
  check "关卡数回到 24" "24" "$(sql "SELECT COUNT(*) FROM cet46.levels;")"
  check "题目数回到 206（题库一题没动）" "206" "$(sql "SELECT COUNT(*) FROM cet46.questions;")"
  echo
  echo "--- 真题指纹回归：第 10 周 20 道阅读真题与 00 号日志比对 ---"
  NOW_W10=$(sql "SELECT MD5(GROUP_CONCAT(CONCAT_WS('|', q.id, q.type, CHAR_LENGTH(q.stem), MD5(q.stem), q.answer_idx, MD5(q.options_json)) ORDER BY q.id SEPARATOR ';'))
    FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id
    WHERE u.week_no=10 AND q.type IN ('cloze','match');")
  echo "00 号基线 = $(cat "$EVID/baseline-week10-md5.txt")"
  echo "99 号现况 = $NOW_W10"
  check "第 10 周真题未被本次验收改动（题量/题干/答案/选项指纹一致）" "$(cat "$EVID/baseline-week10-md5.txt")" "$NOW_W10"
  check "题库里没有残留演示题（第 13/14 周单元为空）" "0" \
    "$(sql "SELECT COUNT(*) FROM cet46.questions q JOIN cet46.levels l ON l.id=q.level_id JOIN cet46.units u ON u.id=l.unit_id WHERE u.week_no IN ($WEEK_DEMO,$WEEK_LIS);")"
} > "$EVID/99-cleanup.log" 2>&1

kill "$SERVER_PID" 2>/dev/null
printf '\n--- 服务已停（PID %s）---\n' "$SERVER_PID" >> "$EVID/02-server-start.log"
echo
# 只数脚本自己的编号日志（00~99）。用 "$EVID"/*.log 会把外部重定向进来的
# run-transcript.log（整场会话的原始输出，含本脚本打印的摘要行）一起数进去，
# 复跑时计数器就对不上了——2026-09-24 复跑报过一次「计数自检不一致」就是这个假阳性。
CHECK_TOTAL=$(grep -ah '\[CHECK\]' "$EVID"/[0-9][0-9]-*.log | wc -l | tr -d ' ')
CHECK_FAIL=$(grep -ah '❌' "$EVID"/[0-9][0-9]-*.log | wc -l | tr -d ' ')
# 自检：计数器必须和日志里数出来的 ❌ 行数相等——不相等说明有 check 输出没落进日志
# （2026-09-24 踩过一次：某个日志里混进一个非法字节，grep 把它当二进制文件跳过，失败行被漏数）。
echo "==== S4 验收实跑结束：校验失败项 = $FAILS，断言 $CHECK_TOTAL 行（其中 ❌ $CHECK_FAIL 行）===="
if [ "$FAILS" = "$CHECK_FAIL" ]; then
  echo "计数自检：计数器与日志行数一致 ✅"
else
  echo "计数自检：计数器=$FAILS 与日志 ❌ 行数=$CHECK_FAIL 不一致 ❌（有失败行没写进日志，需人工看）"
fi
echo "日志目录：$EVID"