#!/usr/bin/env bash
# S8（班级联赛）真库验收：一条龙跑完，每步一份日志，最后汇总断言数与失败数。
#
#   bash run-acceptance.sh            # 00~09 全跑（09 核对浏览器截图产物），末尾出汇总
#   bash run-acceptance.sh 03 04      # 只跑指定步（重跑单步用；注意 02 会清掉旧的自建数据）
#   bash run-acceptance.sh 99         # 只看汇总
#
# 环境（保持运行）：MySQL 3307 / Go :8080 / Vite :5174（学生端 base=/s/）。
# 自建自清：只写 S8 自己的 6 个班，不动 1/2/7/8/9 班，不加表不加列（17 表 / 128 列红线）。
set -u
cd "$(dirname "$0")"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
PY=python
API=http://127.0.0.1:8080
WEB=http://127.0.0.1:5174
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)
# 密码从服务端 .env 取（不打印、不落盘）：下面的 sql() 才有数据可查。
SRV=/d/claude-work/cet46-game/server
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | tr -d '\r' | cut -d= -f2-)"

ok=0 fail=0
declare -a STEPS=()

say() { printf '\n########## %s ##########\n' "$*"; }

# check <描述> <期望> <实际>：写进当前步骤日志，同时累计全局计数
check() {
  local d="$1" w="$2" g="$3"
  if [ "$w" = "$g" ]; then ok=$((ok+1)); printf '[CHECK] %s ✅ 期望=%s 实际=%s\n' "$d" "$w" "$g"
  else fail=$((fail+1)); printf '[CHECK] %s ❌ 期望=%s 实际=%s\n' "$d" "$w" "$g"; fi
}

sql() { "${MYSQL[@]}" -e "$1" 2>/dev/null | tr -d '\r'; }

# run_py <步骤名> <子命令...>：跑 python 段，把「本步断言 N 条，失败 M 条」收进汇总
run_py() {
  local step="$1"; shift
  say "$step"
  local log="${step}.log"
  $PY s8-league.py "$@" 2>&1 | tee "$log"
  local n m
  n=$(grep -ac '^\[S8\].*✅' "$log" || true)
  m=$(grep -ac '^\[S8\].*❌' "$log" || true)
  ok=$((ok+n)); fail=$((fail+m))
  STEPS+=("$step|$n|$m")
  echo "[SUM] $step 断言 $n 条，失败 $m 条"
}

run_sh() {  # run_sh <步骤名> <函数名>：把一段 shell 包进同名日志
  local step="$1"; shift
  say "$step"
  { "$@"; } 2>&1 | tee "${step}.log"
  STEPS+=("$step|$(grep -ac '\[CHECK\].*✅' "${step}.log" || true)|$(grep -ac '\[CHECK\].*❌' "${step}.log" || true)")
}

step_00() {
  say "S8 验收前置：服务可达 + 教师账号 + 底账快照"
  local t; t=$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()")
  check "MySQL 3307 可连（表数 17）" 17 "$t"
  check "Go 服务 /api/health 200" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/health")"
  check "Vite 5174 可达" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/s/")"
  check "联赛页路由 /s/rank 可达" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/s/rank")"
  check "S8 board 接口已挂（无 token → 401，不是 404）" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/league/board")"
  check "S8 me 接口已挂（无 token → 401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/league/me")"
  check "S8 pk/check 接口已挂（无 token → 401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/api/league/pk/check" -H 'Content-Type: application/json' -d '{}')"
  check "教师开关接口已挂（无 token → 401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/api/admin/rank-toggle" -H 'Content-Type: application/json' -d '{}')"
  # Vite 的模块 URL 是根相对（不带 /s/ base），/s/src/... 会被 SPA 兜底成 index.html。
  local rv; rv=$(curl -s "$WEB/src/student/views/RankView.vue" | grep -ac 'league' || true)
  check "Vite 吐的是 S8 之后的 RankView（含联赛接口调用）" 1 "$([ "$rv" -gt 0 ] && echo 1 || echo 0)"
  local cr; cr=$(curl -s "$WEB/src/student/router.ts" | grep -acE 'path: *"/rank"' || true)
  check "路由表里有 /rank" 1 "$([ "$cr" -gt 0 ] && echo 1 || echo 0)"
  local nav; nav=$(curl -s "$WEB/src/student/components/BottomNav.vue" | grep -acE 'to: *"rank"' || true)
  check "底部导航「联赛」格有真实落点" 1 "$([ "$nav" -gt 0 ] && echo 1 || echo 0)"
  check "班级「2024级英语1班」在库（题库指纹的比对基准）" 1 "$(sql "SELECT COUNT(*) FROM classes WHERE name='2024级英语1班'" | head -1)"
  local svlog="$TEMP/cet46-server-s8.log"
  if [ -f "$svlog" ]; then
    check "cron 已就位（服务启动日志：周日 23:00 结算）" 1 "$(grep -aqF '定时任务已启动：0 23 * * 0' "$svlog" && echo 1 || echo 0)"
  else
    check "cron 规格在源码里（$svlog 不在，退到源码级证据）" 1 "$(grep -rlqF '0 23 * * 0' /d/claude-work/cet46-game/server/internal/jobs/ 2>/dev/null && echo 1 || echo 0)"
  fi
}

step_01() {
  say "后端单测 + router 集成测试（首刷口径 / 升降级边界 / 隐藏脱敏 / PK 拒绝）"
  local log="$PWD/01-go-test.log"
  # -count=1：别让 go test 的缓存把「真跑过」变成本次没跑的绿。
  ( cd /d/claude-work/cet46-game/server && go test -count=1 ./... ) > "$log" 2>&1
  local code=$?
  cat "$log"
  local pass bad
  pass=$(grep -ac '^ok ' "$log" || true)
  bad=$(grep -acE '^(FAIL|--- FAIL)' "$log" || true)
  check "go test ./... 退出码 0" 0 "$code"
  check "全绿包数 > 0" 1 "$([ "$pass" -gt 0 ] && echo 1 || echo 0)"
  check "FAIL 行 0 条" 0 "$bad"
  local league; league=$(grep -ac 'ok .*internal/quiz' "$log" || true)
  check "league 口径单点（internal/quiz）有测试跑过" 1 "$([ "$league" -gt 0 ] && echo 1 || echo 0)"
}

step_09() {
  say "浏览器实测截图（委派子代理跑真页面；这一步核对产物在位、真实尺寸、四张互不同帧）"
  local files=(s8-browser-01-rank-public.png s8-browser-02-mine-detail.png s8-browser-03-rank-closed.png s8-browser-04-after-open.png)
  local i=1 md5s=() dims=0
  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      local sz; sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
      check "截图 $i 在位且非空白（$f，$sz 字节）" 1 "$([ "$sz" -gt 20000 ] && echo 1 || echo 0)"
      md5s+=("$(md5sum "$f" | cut -d' ' -f1)")
    else
      check "截图 $i 在位（$f）" 1 0
      md5s+=("missing")
    fi
    i=$((i+1))
  done
  # 尺寸：学生端是 390×844 的固定屏（内层滚动容器），要求每张都真是这个尺寸，
  # 别拿 1×1 的占位图或缩略图冒充。
  dims=$($PY - "$PWD" "${files[@]}" <<'PY' 2>/dev/null || echo 0
import io, os, sys
from PIL import Image
here, files = sys.argv[1], sys.argv[2:]
ok = 0
for f in files:
    p = os.path.join(here, f)
    if not os.path.isfile(p):
        continue
    w, h = Image.open(p).size
    if (w, h) == (390, 844):
        ok += 1
print(ok)
PY
)
  check "四张截图都是 390×844 整屏（不是占位/缩略图）" 4 "$dims"
  # 互不同帧：同一页面的不同状态若被拍成同一帧，等于只有一张证据。
  local uniq; uniq=$(printf '%s\n' "${md5s[@]}" | sort -u | wc -l | tr -d ' \r')
  check "四张截图两两不同帧（MD5 去重后仍是 4）" 4 "$uniq"
  check "关闭态截图与公开态截图不是同一帧" 1 "$([ "${md5s[0]}" != "${md5s[2]}" ] && echo 1 || echo 0)"
}

run_step_by_name() {
  case "$1" in
    00) run_sh 00-precheck step_00 ;;
    01) run_sh 01-go-test step_01 ;;
    02) run_py 02-seed12 seed12 ;;
    03) run_py 03-check12 check12 ;;
    04) run_py 04-seed4-and-check4 seed4 && run_py 04b-check4 check4 ;;
    05) run_py 05-seed6-and-check6 seed6 && run_py 05b-check6 check6 ;;
    06) run_py 06-pk pk ;;
    07) run_py 07-hidden hidden ;;
    08) run_py 08-settle settle ;;
    09) run_sh 09-browser step_09 ;;
    98) run_py 98-baseline-after baseline after ;;
    10) run_py 10-demo demo ;;
    99) return 0 ;;
    *) echo "未知步骤：$1" ;;
  esac
}

if [ $# -gt 0 ]; then
  for s in "$@"; do run_step_by_name "$s"; done
else
  for s in 00 01 02 03 04 05 06 07 08; do run_step_by_name "$s"; done
fi

if [ $# -eq 0 ] || [[ " $* " == *" 99 "* ]] || [[ " $* " == *" 98 "* ]]; then
  say "S8 验收汇总"
  printf '%-24s %8s %8s\n' 步骤 断言 失败
  for row in "${STEPS[@]:-}"; do
    IFS='|' read -r a b c <<< "$row"
    printf '%-24s %8s %8s\n' "$a" "$b" "$c"
  done
  echo
  echo "S8 验收汇总：断言 $ok 条，失败 $fail 条"
  if [ "$fail" -eq 0 ]; then echo "结论：全绿 ✅"; else echo "结论：有失败 ❌"; fi
  echo "$ok $fail" > 99-summary.txt
fi