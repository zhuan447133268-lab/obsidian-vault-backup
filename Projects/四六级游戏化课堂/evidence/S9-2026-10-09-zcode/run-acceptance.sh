#!/usr/bin/env bash
# S9（个人中心 + 福利商城 + 宠物养成 + 错题复盘 + 积分明细）真库验收：一条龙跑完，
# 每步一份日志，最后汇总断言数与失败数。
#
#   bash run-acceptance.sh            # 00~10 全跑（09 核对浏览器截图产物），末尾出汇总
#   bash run-acceptance.sh 04 06      # 只跑指定步（重跑单步用；注意 02 会清掉旧的自建数据）
#   bash run-acceptance.sh 99         # 只看汇总
#
# 环境（保持运行）：MySQL 3307 / Go :8080 / Vite :5174（学生端 base=/s/）。
# 自建自清：只写 S9 自己的两个班（S9商城验收班 / S9售罄验收班），不动 1/2/7/8/9 班，
# 不加表不加列（17 表 / 128 列红线）。
set -u
cd "$(dirname "$0")"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
PY=python
API=http://127.0.0.1:8080
WEB=http://127.0.0.1:5174
SRV=/d/claude-work/cet46-game/server
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)
# 密码从服务端 .env 取（不打印、不落盘）：下面的 sql() 才有数据可查。
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | tr -d '\r' | cut -d= -f2-)"

ok=0 fail=0

say() { printf '\n########## %s ##########\n' "$*"; }

# check <描述> <期望> <实际>：写进当前步骤日志，同时累计全局计数
check() {
  local d="$1" w="$2" g="$3"
  if [ "$w" = "$g" ]; then ok=$((ok+1)); printf '[CHECK] %s ✅ 期望=%s 实际=%s\n' "$d" "$w" "$g"
  else fail=$((fail+1)); printf '[CHECK] %s ❌ 期望=%s 实际=%s\n' "$d" "$w" "$g"; fi
}

# grep -q 风格的小判据：命中记 1，否则 0（期望写 1）
hits() { local n; n=$(printf '%s' "$2" | grep -acE "$1" || true); echo "$n"; }

sql() { "${MYSQL[@]}" -e "$1" 2>/dev/null | tr -d '\r'; }

# run_py <步骤名> <子命令...>：跑 python 段，把「本步断言 N 条，失败 M 条」收进汇总
run_py() {
  local step="$1"; shift
  say "$step"
  local log="${step}.log"
  $PY s9-shop.py "$@" 2>&1 | tee "$log"
  local n m
  n=$(grep -ac '^\[S9\].*✅' "$log" || true)
  m=$(grep -ac '^\[S9\].*❌' "$log" || true)
  ok=$((ok+n)); fail=$((fail+m))
  echo "[SUM] $step 断言 $n 条，失败 $m 条"
}

run_sh() {  # run_sh <步骤名> <函数名>：把一段 shell 包进同名日志
  local step="$1"; shift
  say "$step"
  { "$@"; } 2>&1 | tee "${step}.log"
}

class_id_of() { sql "SELECT id FROM classes WHERE name='$1'" | head -1; }

step_00() {
  say "S9 验收前置：服务可达 + S9 接口挂载 + 前端源码已是 S9"
  local t; t=$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()")
  check "MySQL 3307 可连（表数 17）" 17 "$t"
  check "Go 服务 /api/health 200" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/health")"
  check "Vite 5174 可达" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/s/")"
  check "积分明细页路由 /s/ledger 可达" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/s/ledger")"
  check "复盘页路由 /s/review 可达" 200 "$(curl -s -o /dev/null -w '%{http_code}' "$WEB/s/review")"
  # 「已挂载」的判据：无 token 回 401（不是 404）——404 说明路由根本没注册。
  check "S9 /api/me/overview 已挂（401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/me/overview")"
  check "S9 /api/me/ledger 已挂（401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/me/ledger")"
  check "S9 /api/me/review-paper 已挂（401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/me/review-paper")"
  check "S9 /api/shop/redeem 已挂（401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/api/shop/redeem" -H 'Content-Type: application/json' -d '{}')"
  check "S9 /api/pet/feed 已挂（401）" 401 "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/api/pet/feed")"
  # Vite 的模块 URL 是根相对（不带 /s/ base），/s/src/... 会被 SPA 兜底成 index.html。
  local pv; pv=$(curl -s "$WEB/src/student/views/ProfileView.vue")
  check "Vite 吐的是 S9 之后的 ProfileView（含商城/宠物）" 1 "$([ "$(hits '宠物|redeemCoupon|feedPet' "$pv")" -ge 3 ] && echo 1 || echo 0)"
  local api_src; api_src=$(curl -s "$WEB/src/student/api.ts")
  check "api.ts 三个 S9 接口都在" 1 \
    "$([ "$(hits 'fetchMeLedger' "$api_src")" -ge 1 ] && [ "$(hits 'redeemCoupon' "$api_src")" -ge 1 ] && [ "$(hits 'feedPet' "$api_src")" -ge 1 ] && echo 1 || echo 0)"
  local rt; rt=$(curl -s "$WEB/src/student/router.ts")
  check "路由表里有 /ledger 与 /review 两条路由" 1 \
    "$([ "$(hits 'path: .*/ledger' "$rt")" -ge 1 ] && [ "$(hits 'path: .*/review' "$rt")" -ge 1 ] && echo 1 || echo 0)"
  check "底部导航「我的」把明细/复盘算进同一格" 1 \
    "$([ "$(hits 'ME_ROUTES' "$(curl -s "$WEB/src/student/components/BottomNav.vue")")" -ge 1 ] && echo 1 || echo 0)"
  check "班级「2024级英语1班」在库（题库指纹的比对基准）" 1 "$(sql "SELECT COUNT(*) FROM classes WHERE name='2024级英语1班'" | head -1)"
  check "券种铺库命令在位（cmd/shop-seed）" 1 "$([ -f "$SRV/cmd/shop-seed/main.go" ] && echo 1 || echo 0)"
}

step_01() {
  say "后端单测 + 路由集成测试（S9 四条验收 + 宝箱发奖 + 越权隔离）+ gofmt/vet"
  local log="$PWD/01-go-raw.log"   # 原始输出单独落盘：别和 run_sh 的 tee 抢同一个文件
  # -count=1：别让 go test 的缓存把「真跑过」变成本次没跑的绿。
  ( cd "$SRV" && go test -count=1 ./... ) > "$log" 2>&1
  local code=$?
  cat "$log"
  local pass bad
  pass=$(grep -ac '^ok ' "$log" || true)
  bad=$(grep -acE '^(FAIL|--- FAIL)' "$log" || true)
  check "go test ./... 退出码 0" 0 "$code"
  check "全绿包数 > 0" 1 "$([ "$pass" -gt 0 ] && echo 1 || echo 0)"
  check "FAIL 行 0 条" 0 "$bad"
  check "router 包有测试且全绿" 1 "$([ "$(grep -ac 'ok .*internal/router' "$log" || true)" -ge 1 ] && echo 1 || echo 0)"
  check "商城口径（internal/quiz）有测试跑过" 1 "$([ "$(grep -ac 'ok .*internal/quiz' "$log" || true)" -ge 1 ] && echo 1 || echo 0)"
  local fmt; fmt=$( cd "$SRV" && gofmt -l . 2>&1 | tr -d '\r' )
  check "gofmt 无待整理文件" "" "$fmt"
  local vet
  ( cd "$SRV" && go vet ./... ) > "$PWD/01-go-vet-raw.log" 2>&1
  vet=$(grep -acE '.' "$PWD/01-go-vet-raw.log" || true)
  check "go vet 无输出" 0 "$vet"
}

step_01b() {
  say "前端静态检查：vue-tsc 类型检查 + eslint（S9 新页面与接口声明不能是红的）"
  local log="$PWD/01b-web-raw.log"  # 同上：原始输出另存
  ( cd /d/claude-work/cet46-game/web && npm run typecheck && npm run lint ) > "$log" 2>&1
  local code=$?
  cat "$log"
  check "npm run typecheck + lint 退出码 0" 0 "$code"
  check "输出里没有 error 行" 0 "$(grep -acE '\berror\b' "$log" || true)"
  check "确实跑了 vue-tsc（不是空转）" 1 "$([ "$(grep -ac 'vue-tsc --noEmit' "$log" || true)" -ge 1 ] && echo 1 || echo 0)"
  check "确实跑了 eslint（不是空转）" 1 "$([ "$(grep -ac 'eslint \.' "$log" || true)" -ge 1 ] && echo 1 || echo 0)"
}

step_03() {
  say "券种铺库：dry-run 不落库 → 真跑建 2 张 → 重跑幂等（无需改动）"
  local cid9 cidz
  cid9=$(class_id_of 'S9商城验收班')
  cidz=$(class_id_of 'S9售罄验收班')
  check "自建班在库（02 步建过）" 1 "$([ -n "$cid9" ] && [ -n "$cidz" ] && echo 1 || echo 0)"

  local pre; pre=$(sql "SELECT COUNT(*) FROM coupons WHERE class_id=$cid9")
  local dry; dry=$( cd "$SRV" && go run ./cmd/shop-seed -class "$cid9" -dry-run 2>&1 | tr -d '\r' )
  echo "$dry"
  check "dry-run 计划里免旷课券 880/限1/库存5（5 人班）" 1 "$(hits '免旷课券：880 XP / 限 1 张 / 库存 5' "$dry")"
  check "dry-run 计划里免迟到券 300/限3/库存15" 1 "$(hits '免迟到券：300 XP / 限 3 张 / 库存 15' "$dry")"
  check "dry-run 没落库（券种数与跑之前一样）" "$pre" "$(sql "SELECT COUNT(*) FROM coupons WHERE class_id=$cid9")"

  local first; first=$( cd "$SRV" && go run ./cmd/shop-seed -class "$cid9" 2>&1 | tr -d '\r' )
  echo "$first"
  if [ "$pre" = "0" ]; then
    check "真跑：新建 2 张（首次铺库）" 1 "$(hits '完成：新建 2，更新 0，无需改动 0' "$first")"
  else
    # 单跑 03 时库里已有券（02 重建过班但没重建券），此时只该是「无需改动」。
    echo "[note] 库里已有 $pre 张券（03 之前跑过一次），这一步只验幂等与配置。"
    check "真跑：无需改动 2 张（重复铺库幂等）" 1 "$(hits '完成：新建 0，更新 0，无需改动 2' "$first")"
  fi
  check "库内券种 2 张" 2 "$(sql "SELECT COUNT(*) FROM coupons WHERE class_id=$cid9")"
  check "库内库存/限购/上架状态（300/3/15 与 880/1/5）" "300|3|15|1
880|1|5|1" "$(sql "SELECT CONCAT_WS('|', cost_xp, per_user_limit, stock, enabled) FROM coupons WHERE class_id=$cid9 ORDER BY cost_xp")"

  local second; second=$( cd "$SRV" && go run ./cmd/shop-seed -class "$cid9" 2>&1 | tr -d '\r' )
  echo "$second"
  check "重跑幂等：无需改动 2 张" 1 "$(hits '完成：新建 0，更新 0，无需改动 2' "$second")"
  check "重跑没多出券种" 2 "$(sql "SELECT COUNT(*) FROM coupons WHERE class_id=$cid9")"

  # 售罄班（1 人）：库存 = 1×限购，真配置下学生能把券兑穿
  local z; z=$( cd "$SRV" && go run ./cmd/shop-seed -class "$cidz" 2>&1 | tr -d '\r' )
  echo "$z"
  check "售罄班券种：1 人班库存 1 / 3" "300|3
880|1" "$(sql "SELECT CONCAT_WS('|', cost_xp, stock) FROM coupons WHERE class_id=$cidz ORDER BY cost_xp")"
  check "售罄班只铺了自己的班（主班券数没变）" 2 "$(sql "SELECT COUNT(*) FROM coupons WHERE class_id=$cid9")"
}

step_09() {
  say "浏览器实测截图（委派子代理跑真页面；这一步核对产物在位、真实尺寸、互不同帧）"
  local files=(s9-browser-01-me-top.png s9-browser-02-shop.png s9-browser-03-pet.png \
               s9-browser-04-review.png s9-browser-05-ledger.png)
  local i=1 md5s=()
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
  # 别拿 1×1 的占位图或缩略图冒充，也别让内层滚动容器把 5 张拍成同一帧。
  local dims; dims=$($PY - "$PWD" "${files[@]}" <<'PY' 2>/dev/null || echo 0
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
  check "五张截图都是 390×844 整屏（不是占位/缩略图）" 5 "$dims"
  local uniq; uniq=$(printf '%s\n' "${md5s[@]}" | sort -u | wc -l | tr -d ' \r')
  check "五张截图两两不同帧（MD5 去重后仍是 5）" 5 "$uniq"
}

step_10() {
  run_py 10-verify verify
}

run_step_by_name() {
  case "$1" in
    00) run_sh 00-precheck step_00 ;;
    01) run_sh 01-go-test step_01 ;;
    01b) run_sh 01b-web-check step_01b ;;
    02) run_py 02-baseline baseline before && run_py 02b-seed seed ;;
    03) run_sh 03-shop-seed step_03 ;;
    04) run_py 04-redeem redeem ;;
    05) run_py 05-review review ;;
    06) run_py 06-ledger ledger ;;
    07) run_py 07-chest-pet chestpet ;;
    08) run_py 08-demo demo ;;
    09) run_sh 09-browser step_09 ;;
    10) step_10 ;;
    99) return 0 ;;
    *) echo "未知步骤：$1" ;;
  esac
}

summarize() {
  say "S9 验收汇总（按目录里全部步骤日志统计，不只看本次跑的那几步）"
  printf '%-24s %8s %8s\n' 步骤 断言 失败
  ok=0; fail=0
  local log n m
  for log in $(ls -1 [0-9][0-9]*.log 2>/dev/null | sort); do
    case "$log" in *-raw.log) continue ;; esac   # -raw 是工具原始输出，不是断言日志
    n=$(grep -ac '✅' "$log" || true)
    m=$(grep -ac '❌' "$log" || true)
    [ -z "$n" ] && n=0
    [ -z "$m" ] && m=0
    printf '%-24s %8s %8s\n' "${log%.log}" "$n" "$m"
    ok=$((ok+n)); fail=$((fail+m))
  done
  echo
  echo "S9 验收汇总：断言 $ok 条，失败 $fail 条"
  if [ "$fail" -eq 0 ]; then echo "结论：全绿 ✅"; else echo "结论：有失败 ❌"; fi
  echo "$ok $fail" > 99-summary.txt
}

if [ $# -gt 0 ]; then
  for s in "$@"; do run_step_by_name "$s"; done
else
  for s in 00 01 01b 02 03 04 05 06 07 08 09 10; do run_step_by_name "$s"; done
fi

if [ $# -eq 0 ] || [[ " $* " == *" 99 "* ]] || [[ " $* " == *" 10 "* ]]; then
  summarize
fi