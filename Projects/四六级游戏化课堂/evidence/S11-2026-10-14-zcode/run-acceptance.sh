#!/usr/bin/env bash
# S11 验收实跑（课中实时大屏：三指标 + 实时易错题榜 + 10s 可配置 + 防压力）。
# 一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑；Vite :5174 已起（走查用）；8080 上原来是哪个版本不重要，
#       本脚本会重编 S11 二进制并把它换上去（旧进程按端口杀掉，不按进程名猜）。
#
# 会动什么：只建/重建自己的「S11验收1班」（连带 5 名学生、1 单元 3 关 6 题、今天 10 条 attempt）
#       与三个夹具账号（T1101/T1102/A1101）。别人的班、别人的题库一行不碰——底账与
#       "别人题库 CRC"在 00 与 99 各算一次对拍。夹具故意留库（三指标的证据在库里）。
#
# 日志命名用 .txt（仓库 .gitignore 忽略 *.log，而本轮 evidence 要交付进仓库）。
set -uo pipefail
export PYTHONUTF8=1          # Windows 控制台默认 GBK：python 打印中文会 UnicodeEncodeError
export PYTHONIOENCODING=utf-8
export PYTHONDONTWRITEBYTECODE=1   # 别在 evidence 目录里留 __pycache__

ROOT=/d/claude-work/cet46-game
SRV="$ROOT/server"
EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"       # python 是原生程序：喂 Windows 路径，别喂 /c/... 形式的 MSYS 路径
API=http://127.0.0.1:8080/api
ALT=http://127.0.0.1:8081/api
VITE=http://127.0.0.1:5174
# S10.5 套件的落点（本轮拿它当"D1~D5 未被破坏"的回归证据）；可通过环境变量改到别处
S105_DIR="${S105_DIR:-/c/Users/dfjq/Documents/Obsidian Vault/Projects/四六级游戏化课堂/evidence/S10.5-2026-10-13-zcode}"

BUILD="$(mktemp -d)"
BUILDW="$(cygpath -w "$BUILD")"
SRV_EXE_W="$BUILDW\\cet46-server-s11.exe"
SEED_EXE_W="$BUILDW\\seed-teacher.exe"

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
pid_on_port() { netstat -ano | grep -E ":$1[[:space:]]" | grep LISTENING | awk '{print $NF}' | head -1; }
kill_port() {
  local pid; pid="$(pid_on_port "$1")"
  if [ -n "${pid:-}" ]; then
    taskkill //PID "$pid" //F >/dev/null 2>&1 || true
    local i
    for i in $(seq 1 20); do [ -z "$(pid_on_port "$1")" ] && break; sleep 0.5; done
  fi
}
start_server() { # start_server 端口 日志文件（写在 BUILD 临时目录）[附加环境 KEY=VAL]
  # 服务进程的 stdout 不能直接写进 evidence：它是**活句柄**，跑完还会一直写，
  # 交卷后的工作区会被它反复弄脏（Windows 下还删不掉）。所以先写临时目录，
  # 需要留档时用 snapshot_server_log 复制一份"冻结快照"进 evidence。
  local port="$1" log="$2" extra="${3:-}"
  ( cd "$SRV" && env HTTP_PORT="$port" ${extra:+$extra} "$SRV_EXE_W" > "$BUILD/$log" 2>&1 & )
}
snapshot_server_log() { # snapshot_server_log 临时日志名 evidence名
  cp "$BUILD/$1" "$EVID/$2"
}
wait_health() { # wait_health 端口
  local i
  for i in $(seq 1 40); do
    curl -sf "http://127.0.0.1:$1/api/health" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}
run_step() { # run_step 03-xxx step_03_xxx
  local name="$1" fn="$2" log="$EVID/$1.txt"
  : > "$log"
  "$fn" >> "$log" 2>&1
  local rc=$?
  local nf
  nf=$(grep -ac '\[FAIL\]\|❌' "$log" || true)
  STEP_NAMES+=("$name"); STEP_RC+=("$rc"); STEP_FAILS+=("$nf")
  FAILS=$((FAILS + nf))
  echo "== $name：退出码 $rc · 失败标记 ${nf} 条 =="
  if [ "$rc" != 0 ] || [ "$nf" != 0 ]; then tail -40 "$log"; fi
}

# ================================================================ 00 环境、重编、换服务
step_00_precheck() {
  step "00 前置：重编 S11 二进制 + 换掉 8080 上的旧服务 + 路由已挂上"
  echo "--- 00-1 编译（server 与 seed-teacher 都编进临时目录，不往仓库里丢产物）---"
  ( cd "$SRV" && go build -o "$SRV_EXE_W" ./cmd/server ) || { echo "!! 编译失败"; return 1; }
  ( cd "$SRV" && go build -o "$SEED_EXE_W" ./cmd/seed-teacher ) || { echo "!! 编译 seed-teacher 失败"; return 1; }
  echo "二进制：$SRV_EXE_W"

  echo "--- 00-2 换服务（按端口杀旧进程）---"
  local old; old="$(pid_on_port 8080)"
  echo "8080 上的旧进程：${old:-（无）}"
  kill_port 8080
  start_server 8080 "00-server.txt"
  check "8080 新服务起来（/api/health）" "ok" "$(wait_health 8080 && echo ok || echo no)"
  check "MySQL 3307 可连" "1" "$(mysql --protocol=tcp -h 127.0.0.1 -P 3307 -uroot -N -B -e 'select 1' 2>/dev/null | tr -d '\r')"
  check "Vite 5174 可达（大屏走查用）" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/")"

  echo "--- 00-3 大屏路由已挂上（未带 token 是 401，不是 404）---"
  check "GET /api/admin/live 无 token → 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' "$API/admin/live")"
  check "GET /api/admin/live 是 JSON 回执（不是路由未匹配的纯文本）" "1" \
    "$(curl -s "$API/admin/live" | grep -c '\"code\"')"
  # 到这里 8080 的启动输出已经产生：冻结一份快照进 evidence（铁证"服务确实是本轮新二进制起的"）
  snapshot_server_log "00-server.txt" "00-server-boot.txt"

  echo "--- 00-4 8081 第二实例（LIVE_REFRESH_SECONDS=3：证明刷新间隔可配置）---"
  kill_port 8081
  start_server 8081 "00-server-alt.txt" "LIVE_REFRESH_SECONDS=3"
  check "8081 实例起来" "ok" "$(wait_health 8081 && echo ok || echo no)"
  check "8081 实例带的是 S11 的 /admin/live" "401" "$(curl -s -o /dev/null -w '%{http_code}' "$ALT/admin/live")"
  snapshot_server_log "00-server-alt.txt" "00-server-alt-boot.txt"
}

# ================================================================ 01 夹具
step_01_fixture() {
  step "01 夹具：教师/班级/5 名学生/题库 + 按手算计划落今天 10 条 attempt（+昨天 1 条对照）"
  cd "$EVID" || return 1
  S11_SEED_EXE="$SEED_EXE_W" python s11_setup.py
}

# ================================================================ 02 验收断言
step_02_accept() {
  step "02 验收：三指标三方对拍 + 403 + 无身份字段 + 10s 可配置 + 回归"
  cd "$EVID" || return 1
  S11_ALT_BASE="$ALT" S11_BASE="$API" python s11_accept.py
}

# ================================================================ 03 go test
step_03_gotest() {
  step "03 go test ./... -count=1（全包；S11 新增 live 纯函数/路由/分组安全断言）"
  cd "$SRV" || return 1
  local out
  out=$(go test ./... -count=1 2>&1)
  echo "$out"
  echo
  echo "--- 统计 ---"
  check "go test 无 FAIL" "0" "$(printf '%s\n' "$out" | grep -ac '^FAIL' || true)"
  check "go test 无构建错误" "0" "$(printf '%s\n' "$out" | grep -ac 'build failed' || true)"
  check "router 与 service 两个包在通过列表里" "2" \
    "$(printf '%s\n' "$out" | grep -aE 'internal/(router|service)[[:space:]]' | grep -ac '^ok' || true)"
}

# ================================================================ 04 verify.sh（等价 CI）
step_04_verify() {
  step "04 scripts/verify.sh（gofmt / go vet / go test / go build / eslint / 前端 build）"
  cd "$ROOT" || return 1
  bash scripts/verify.sh 2>&1 | tail -50
  local rc=${PIPESTATUS[0]}
  check "verify.sh 退出码 0" "0" "$rc"
}

# ================================================================ 05 回归：S10.5 套件复跑
step_05_regression() {
  step "05 回归：复跑 S10.5 验收套件（D1~D5 未被 S11 破坏的机器证据）"
  if [ ! -f "$S105_DIR/s105_accept.py" ]; then
    echo "!! 找不到 S10.5 套件（$S105_DIR）——本轮无法出这条回归证据，如实记录而非静默跳过"
    check "S10.5 套件存在（$S105_DIR）" "yes" "no"
    return 0
  fi
  cd "$S105_DIR" || return 1
  python s105_accept.py
  local rc=$?
  echo
  echo "--- S10.5 套件自己的收尾计数 ---"
  cat "$S105_DIR/99-summary.txt" 2>/dev/null || echo "(没写出 99-summary.txt)"
  cp "$S105_DIR/99-summary.txt" "$EVID/99-regression-s105.txt" 2>/dev/null || true
  local nf
  nf=$(grep -ac '\[FAIL\]' "$EVID/05-regression-s105.txt" || true)
  echo "S10.5 套件本次扫描到的失败标记：$nf 条（该套件的断言数以其自身 99-summary.txt 为准）"
  echo "S10.5 套件退出码：$rc"
  return 0
}

# ================================================================ 99 汇总
step_99_summary() {
  step "99 收尾：编号日志清点 + 底账回归"
  echo "--- 99-1 编号日志 ---"
  local i
  for i in "${!STEP_NAMES[@]}"; do
    local n="${STEP_NAMES[$i]}"
    case "$n" in 99-*) continue;; esac
    if [ ! -f "$EVID/$n.txt" ]; then echo "$(printf '%-22s' "$n") [NG] 日志缺失"; continue; fi
    if [ "${STEP_RC[$i]}" = 0 ] && [ "${STEP_FAILS[$i]}" = 0 ]; then
      echo "$(printf '%-22s' "$n") [OK] 退出码 0 · 失败标记 0"
    else
      echo "$(printf '%-22s' "$n") [NG] 退出码 ${STEP_RC[$i]} · 失败标记 ${STEP_FAILS[$i]}"
    fi
  done

  echo
  echo "--- 99-2 底账回归（表结构 + 别人题库 CRC 必须与开跑前一致）---"
  local M=(mysql --protocol=tcp -h 127.0.0.1 -P 3307 -uroot cet46 --default-character-set=utf8mb4 -N -B)
  check "表/列仍是 17/128" "17/128" \
    "$("${M[@]}" -e "select concat((select count(*) from information_schema.tables where table_schema='cet46'),'/',(select count(*) from information_schema.columns where table_schema='cet46'))" | tr -d '\r')"
  local crc
  crc=$("${M[@]}" -e "select sum(crc32(concat(q.id,0x1f,coalesce(q.stem,''),0x1f,coalesce(q.options_json,'')))) % 4294967296 from questions q join levels l on l.id=q.level_id join units u on u.id=l.unit_id join classes c on c.id=u.class_id where c.name not in ('S9商城验收班','S9售罄验收班','S10验收1班','S10验收2班','S10验收3班','S10.5验收1班','S10.5验收2班','S10.5验收3班','S105复验1班','S105复验2班','T2私有班','S11验收1班')" | tr -d '\r')
  check "别人题库 CRC 仍是 3897258111" "3897258111" "$crc"

  echo
  echo "--- 99-3 留库清单（Claude 复验点名用）---"
  "${M[@]}" -e "select u.username, u.real_name, u.class_id, (select count(*) from attempts a where a.user_id=u.id) attempts from users u where u.username like 'S11A%' order by u.username" | tr -d '\r'
}

# ================================================================ 主流程
echo "S11 验收实跑开始：$(date '+%Y-%m-%d %H:%M:%S')"
run_step 00-precheck step_00_precheck
run_step 01-fixture step_01_fixture
run_step 02-accept step_02_accept
run_step 03-gotest step_03_gotest
run_step 04-verify step_04_verify
run_step 05-regression-s105 step_05_regression
run_step 99-summary step_99_summary

echo
echo "--- 关掉 8081 第二实例（8080 留着：走查与复验要用）---"
kill_port 8081

echo
echo "############################################################"
echo "# S11 验收实跑结束：$(date '+%Y-%m-%d %H:%M:%S')"
echo "# 失败断言总数：$FAILS（不含 S10.5 套件自身的计数，见 99-regression-s105.txt）"
echo "# 编号日志：${STEP_NAMES[*]}"
echo "############################################################"
exit $(( FAILS > 0 ? 1 : 0 ))