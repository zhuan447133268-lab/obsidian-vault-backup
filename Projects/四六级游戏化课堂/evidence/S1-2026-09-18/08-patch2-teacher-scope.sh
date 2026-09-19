#!/usr/bin/env bash
# S1 补丁2 现场实录：/api/admin/users 按教师班级归属行级过滤。
# 注意：本机 curl 是 Windows 原生 curl.exe，命令行里的中文会被控制台编码转换破坏，
# 所以所有含中文的请求体都写成 UTF-8 文件、用 -d @file 发送。
set -u
B=http://127.0.0.1:8080/api
T=/tmp/cet46-accept
mkdir -p "$T"
cd /d/claude-work/cet46-game/server || exit 1

jget() { python -c "
import sys, json
d = json.load(sys.stdin)
for k in sys.argv[1:]:
    d = d[k]
print(d)" "$@"; }

say() { printf '\n=== %s ===\n' "$1"; }

# 清理上次演示数据，保证脚本可重复执行（只动本脚本自己造的账号/班级，不碰真实名单）。
# 覆盖不到的老版本产物（若某次中途失败）也一并按名字清掉。
cleanup() {
  local envf=.env
  local pass host port user dbn
  pass=$(grep '^DB_PASSWORD=' "$envf" | cut -d= -f2-)
  host=$(grep '^DB_HOST=' "$envf" | cut -d= -f2-)
  port=$(grep '^DB_PORT=' "$envf" | cut -d= -f2-)
  user=$(grep '^DB_USER=' "$envf" | cut -d= -f2-)
  dbn=$(grep '^DB_NAME=' "$envf" | cut -d= -f2-)
  if ! command -v mysql >/dev/null 2>&1; then
    echo "（未找到 mysql 客户端，跳过清理；若本步之后报 409 冲突，请手工删掉 T8001/T8002 与「补丁2-」开头的班级）"
    return
  fi
  mysql -h"$host" -P"$port" -u"$user" -p"$pass" "$dbn" --default-character-set=utf8mb4 -e "
    DELETE FROM users   WHERE username IN ('T8001','T8002','2026810001','2026820001','2026890001');
    DELETE FROM classes WHERE name LIKE '补丁2-%';" 2>&1 | grep -v "Using a password on the command line" || true
}

say "0. 清理上次演示数据（只删本脚本造的账号/班级，保证可重复执行）"
cleanup

say "0b. 造两个教师账号（seed-teacher 幂等，重复跑会把账号重置回「首次登录改密」）"
go run ./cmd/seed-teacher -username T8001 -name 张老师 -password InitT8001
go run ./cmd/seed-teacher -username T8002 -name 李老师 -password InitT8002

say "1. 两个教师各自登录并改密（改密前业务接口 403，改密后才拿到可用 token）"
for u in T8001 T8002; do
  printf '{"username":"%s","password":"Init%s"}' "$u" "$u" > "$T/login-$u.json"
  printf '{"oldPassword":"Init%s","newPassword":"%spwd2026"}' "$u" "$u" > "$T/chpwd-$u.json"
  echo "--- $u ---"
  TMP=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' -d @"$T/login-$u.json" | jget data token)
  curl -s -X POST "$B/auth/chpwd" -H 'Content-Type: application/json' -H "Authorization: Bearer $TMP" -d @"$T/chpwd-$u.json"; echo
done

printf '{"username":"T8001","password":"T8001pwd2026"}' > "$T/login-A.json"
printf '{"username":"T8002","password":"T8002pwd2026"}' > "$T/login-B.json"
TOKA=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' -d @"$T/login-A.json" | jget data token)
TOKB=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' -d @"$T/login-B.json" | jget data token)
echo "教师A token 前缀: ${TOKA:0:20}...   教师B token 前缀: ${TOKB:0:20}..."

say "2. 两个教师各建一个班，各建一名学生；再建一名「未分班」学生"
cat > "$T/class-a.json" <<'EOF'
{"name":"补丁2-教师A的班","term":"2026-2027-1"}
EOF
cat > "$T/class-b.json" <<'EOF'
{"name":"补丁2-教师B的班","term":"2026-2027-1"}
EOF
CLASSA=$(curl -s -X POST "$B/admin/classes" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKA" -d @"$T/class-a.json")
echo "教师A 建班: $CLASSA"
CLA=$(echo "$CLASSA" | jget data id)
CLASSB=$(curl -s -X POST "$B/admin/classes" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKB" -d @"$T/class-b.json")
echo "教师B 建班: $CLASSB"
CLB=$(echo "$CLASSB" | jget data id)

cat > "$T/stu-a.json" <<EOF
{"username":"2026810001","realName":"A班学生","classId":$CLA}
EOF
cat > "$T/stu-b.json" <<EOF
{"username":"2026820001","realName":"B班学生","classId":$CLB}
EOF
cat > "$T/stu-u.json" <<'EOF'
{"username":"2026890001","realName":"未分班学生"}
EOF
SA=$(curl -s -X POST "$B/admin/users" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKA" -d @"$T/stu-a.json")
echo "教师A 建学生: $SA"
IDA=$(echo "$SA" | jget data id)
SB=$(curl -s -X POST "$B/admin/users" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKB" -d @"$T/stu-b.json")
echo "教师B 建学生: $SB"
IDB=$(echo "$SB" | jget data id)
SU=$(curl -s -X POST "$B/admin/users" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKA" -d @"$T/stu-u.json")
echo "未分班学生: $SU"
IDU=$(echo "$SU" | jget data id)

echo "（便于对照）教师A班=$CLA 学生A=$IDA / 教师B班=$CLB 学生B=$IDB / 未分班学生=$IDU"

say "3. 教师A 拉全量名单 → 只有自己班的学生"
curl -s "$B/admin/users?pageSize=50" -H "Authorization: Bearer $TOKA"; echo

say "4. 教师A 显式指定教师B的班 classId=$CLB → 空"
curl -s "$B/admin/users?classId=$CLB" -H "Authorization: Bearer $TOKA"; echo

say "5. 教师A 用学号搜索教师B的学生 2026820001 → 空"
curl -s "$B/admin/users?keyword=2026820001" -H "Authorization: Bearer $TOKA"; echo

say "6. 教师A 单查教师B的学生 id=$IDB → 404（不用 403，避免暴露「该 id 存在」）"
curl -s -o "$T/getB.json" -w 'HTTP %{http_code}\n' "$B/admin/users/$IDB" -H "Authorization: Bearer $TOKA"
cat "$T/getB.json"; echo

say "7. 教师A 单查自己的学生 id=$IDA → 200"
curl -s -o "$T/getA.json" -w 'HTTP %{http_code}\n' "$B/admin/users/$IDA" -H "Authorization: Bearer $TOKA"
cat "$T/getA.json"; echo

say "8. 教师A 单查未分班学生 id=$IDU → 404（未分班不属于任何教师）"
curl -s -o "$T/getU.json" -w 'HTTP %{http_code}\n' "$B/admin/users/$IDU" -H "Authorization: Bearer $TOKA"
cat "$T/getU.json"; echo

say "9. 对称：教师B 拉全量名单 / 单查教师A的学生 id=$IDA"
curl -s "$B/admin/users?pageSize=50" -H "Authorization: Bearer $TOKB"; echo
curl -s -o "$T/getAB.json" -w 'HTTP %{http_code}\n' "$B/admin/users/$IDA" -H "Authorization: Bearer $TOKB"
cat "$T/getAB.json"; echo

say "10. 对照：不带 token → 401"
curl -s -o /dev/null -w 'HTTP %{http_code}\n' "$B/admin/users"