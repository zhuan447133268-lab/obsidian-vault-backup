#!/usr/bin/env bash
# S12 验收实跑（兑换码核销：教师输码检索 → 确认/驳回；学生端回显；audit_log 留痕；
#               外加 S8 遗留两条——赛季自动开新 / 名额名次线文案——的本阶段结论）。
# 一键复现：  bash run-acceptance.sh
#
# 前置：MySQL 127.0.0.1:3307 在跑；8080 上原来是哪个版本不重要，本脚本会重编 S12 二进制
#       并把它换上去（旧进程按端口杀，不按进程名猜）。
#
# 会动什么：只建/重建自己的四个班（S12验收1班 6 人 / S12隔壁班 1 人 / S12赛季验收班 12 人 /
#       S12一人班 1 人）与三个夹具账号（T1201/T1202/A1201），以及它们名下的题库/券种/首刷底账。
#       别人的班、别人的题库一行不碰——底账与"别人题库 CRC"在 99 步对拍。
#       联赛班会被 ops CLI 复算两次结算（上周日 23:00 的赛季结算 + 本周日 23:00 的周结算）：
#       这是拿 cron 的同一条代码路径在历史时刻上重放，不需要等到周日。
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
VITE=http://127.0.0.1:5174
# S10.5 套件的落点（本轮拿它当"D1~D5 未被 S12 破坏"的回归证据）；可通过环境变量改到别处
S105_DIR="${S105_DIR:-/c/Users/dfjq/Documents/Obsidian Vault/Projects/四六级游戏化课堂/evidence/S10.5-2026-10-13-zcode}"

BUILD="$(mktemp -d)"
BUILDW="$(cygpath -w "$BUILD")"
SRV_EXE_W="$BUILDW\\cet46-server-s12.exe"
SEED_EXE_W="$BUILDW\\seed-teacher.exe"
SETTLE_EXE_W="$BUILDW\\cet46-league-settle.exe"

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
  step "00 前置：重编 S12 二进制（server / seed-teacher / league-settle）+ 换掉 8080 上的旧服务"
  echo "--- 00-1 编译（三个产物都编进临时目录，不往仓库里丢）---"
  ( cd "$SRV" && go build -o "$SRV_EXE_W" ./cmd/server ) || { echo "!! 编译失败"; return 1; }
  ( cd "$SRV" && go build -o "$SEED_EXE_W" ./cmd/seed-teacher ) || { echo "!! 编译 seed-teacher 失败"; return 1; }
  ( cd "$SRV" && go build -o "$SETTLE_EXE_W" ./cmd/league-settle ) || { echo "!! 编译 league-settle 失败"; return 1; }
  echo "二进制：$SRV_EXE_W"

  echo "--- 00-2 换服务（按端口杀旧进程）---"
  local old; old="$(pid_on_port 8080)"
  echo "8080 上的旧进程：${old:-（无）}"
  kill_port 8080
  start_server 8080 "00-server.txt"
  check "8080 新服务起来（/api/health）" "ok" "$(wait_health 8080 && echo ok || echo no)"
  check "MySQL 3307 可连" "1" "$(mysql --protocol=tcp -h 127.0.0.1 -P 3307 -uroot -N -B -e 'select 1' 2>/dev/null | tr -d '\r')"
  check "Vite 5174 可达（走查用）" "200" "$(curl -s -o /dev/null -w '%{http_code}' "$VITE/")"
  # 联赛结算按进程本地时区（周日 23:00 本地）：时区不是 +0800 的话，cron 那一格的含义就变了
  check "本机时区 = +0800（联赛结算的那把尺子）" "+0800" "$(date +%z)"

  echo "--- 00-3 S12 三条核销路由已挂上（未带 token 是 401，不是 404）---"
  local CODE="C46-XXXXXXXX"
  check "GET /api/admin/redeems/lookup 无 token → 401" "401" \
    "$(curl -s -o /dev/null -w '%{http_code}' "$API/admin/redeems/lookup?code=$CODE")"
  check "POST /api/admin/redeems/confirm 无 token → 401" "401" \
    "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
       -d '{"code":"'"$CODE"'"}' "$API/admin/redeems/confirm")"
  check "POST /api/admin/redeems/reject 无 token → 401" "401" \
    "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
       -d '{"code":"'"$CODE"'"}' "$API/admin/redeems/reject")"
  # 三段回执拼在一行（curl 不带换行）：数**出现次数**，不能数行数（grep -c 会把 3 段当成 1 行）
  check "三条路由都是 JSON 回执（不是路由未匹配的纯文本）" "3" \
    "$( { curl -s "$API/admin/redeems/lookup?code=$CODE"; \
          curl -s -X POST -H 'Content-Type: application/json' -d '{"code":"'"$CODE"'"}' "$API/admin/redeems/confirm"; \
          curl -s -X POST -H 'Content-Type: application/json' -d '{"code":"'"$CODE"'"}' "$API/admin/redeems/reject"; } \
        | grep -ao '"code"' | wc -l | tr -d ' ')"
  # 到这里 8080 的启动输出已经产生：冻结一份快照进 evidence（联赛 cron 的注册行就在里面）
  snapshot_server_log "00-server.txt" "00-server-boot.txt"
  check "启动日志里有联赛结算 cron 的注册行" "1" \
    "$(grep -ac '定时任务已启动：0 23 \* \* 0' "$EVID/00-server-boot.txt" || true)"
}

# ================================================================ 01 夹具
step_01_fixture() {
  step "01 夹具：四个班 + 三名教师 + 二十名学生 + 题库 + 券种 + 联赛两条首刷底账"
  cd "$EVID" || return 1
  S12_SEED_EXE="$SEED_EXE_W" python s12_setup.py
}

# ================================================================ 02 验收断言
step_02_accept() {
  step "02 验收：全链路 E2E + 退券不退分 + 审计三要素 + 越权 + 赛季自动开新 + 名次线手算"
  cd "$EVID" || return 1
  S12_BASE="$API" S12_SETTLE_EXE="$SETTLE_EXE_W" S12_BOOT_LOG="$EWIN\\00-server-boot.txt" \
    python s12_accept.py
}

# ================================================================ 03 go test
step_03_gotest() {
  step "03 go test ./... -count=1（全包；S12 新增券状态机/越权/审计留痕断言）"
  cd "$SRV" || return 1
  local out
  out=$(go test ./... -count=1 2>&1)
  echo "$out"
  echo
  echo "--- 统计 ---"
  check "go test 无 FAIL" "0" "$(printf '%s\n' "$out" | grep -ac '^FAIL' || true)"
  check "go test 无构建错误" "0" "$(printf '%s\n' "$out" | grep -ac 'build failed' || true)"
  check "quiz / router / service 三个包在通过列表里" "3" \
    "$(printf '%s\n' "$out" | grep -aE 'internal/(quiz|router|service)[[:space:]]' | grep -ac '^ok' || true)"
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
  step "05 回归：复跑 S10.5 验收套件（D1~D5 未被 S12 破坏的机器证据）"
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
  step "99 收尾：编号日志清点 + 底账回归 + 留库清单"
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
  # 排除清单：历轮验收班 + 本轮的四个班（名字硬比是因为代码名与库名一一对应，改动这里必须同步改夹具）
  local crc
  crc=$("${M[@]}" -e "select sum(crc32(concat(q.id,0x1f,coalesce(q.stem,''),0x1f,coalesce(q.options_json,'')))) % 4294967296 from questions q join levels l on l.id=q.level_id join units u on u.id=l.unit_id join classes c on c.id=u.class_id where c.name not in ('S9商城验收班','S9售罄验收班','S10验收1班','S10验收2班','S10验收3班','S10.5验收1班','S10.5验收2班','S10.5验收3班','S105复验1班','S105复验2班','T2私有班','S11验收1班','S12验收1班','S12隔壁班','S12赛季验收班','S12一人班')" | tr -d '\r')
  check "别人题库 CRC 仍是 3897258111" "3897258111" "$crc"

  echo
  echo "--- 99-3 留库清单（Claude 复验点名用）---"
  "${M[@]}" -e "select u.username, u.real_name, u.class_id, (select count(*) from attempts a where a.user_id=u.id) attempts, (select coalesce(sum(delta),0) from xp_ledger x where x.user_id=u.id) xp from users u where u.username like 'S12A%' or u.username like 'S12B%' or u.username like 'S12L%' or u.username like 'S12C%' order by u.username" | tr -d '\r'
}

# ================================================================ 主流程
echo "S12 验收实跑开始：$(date '+%Y-%m-%d %H:%M:%S')"
run_step 00-precheck step_00_precheck
run_step 01-fixture step_01_fixture
run_step 02-accept step_02_accept
run_step 03-gotest step_03_gotest
run_step 04-verify step_04_verify
run_step 05-regression-s105 step_05_regression
run_step 99-summary step_99_summary

echo
echo "############################################################"
echo "# S12 验收实跑结束：$(date '+%Y-%m-%d %H:%M:%S')"
echo "# 失败断言总数：$FAILS（不含 S10.5 套件自身的计数，见 99-regression-s105.txt）"
echo "# 编号日志：${STEP_NAMES[*]}"
echo "############################################################"
exit $(( FAILS > 0 ? 1 : 0 ))