#!/usr/bin/env bash
# S12 走查证据清点：截图逐张校验 + 走查 JSON 的断言数 + 券状态与审计留痕的**库侧对拍**。
# 用法：bash run-shots-check.sh   （在真浏览器走查跑完之后）
#
# 为什么单独一个脚本：截图与浏览器走查是走查子代理的产物，s12_accept.py 跑在它之前。
# 把"图是不是真图、两两是否不同、券状态是不是真落库了、留痕三要素是不是真写进去了"
# 这类清点独立出来，谁来跑都同一把尺子——**子代理自己写的结论不算数，库里的行才算**。
#
# 踩过的坑（都写在这里当尺子）：
#   · 截图必须从 PNG 头读真实尺寸并进 check（打印出来的数字不算断言）；
#   · 多张截图必须 md5 两两不同（字节一样 = 只有一张证据）；
#   · 整页截图高必须等于文档实测 scrollHeight（±4px），并用 noInnerScroll 排掉
#     "内层滚动容器让 fullPage 只剩一屏"这个坑（S10.5 踩过）；
#   · 断言数必须与预期条数核对（分桶函数写错会让整段断言从未执行）；
#   · 学生页面文本里不许出现别的学生姓名与教师姓名（页面侧脱敏证据）。
set -uo pipefail
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONDONTWRITEBYTECODE=1

EVID="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EWIN="$(cygpath -w "$EVID")"
FAILS=0
check() {
  if [ "$2" = "$3" ]; then
    echo "[CHECK] $1 ✅ 期望=$2 实际=$3"
  else
    echo "[CHECK] $1 ❌ 期望=$2 实际=$3"
    FAILS=$((FAILS + 1))
  fi
}

echo "S12 走查证据清点开始：$(date '+%Y-%m-%d %H:%M:%S')"
# stdout 同时落到 shots-check-out.txt（归档用）；结论以 Python 段退出码为准（见下 PIPESTATUS）
python - "$EWIN" <<'PY' 2>&1 | tee "$EVID/shots-check-out.txt"
import hashlib
import io
import json
import os
import struct
import subprocess
import sys

ev = sys.argv[1]
shots = os.path.join(ev, "shots")
bad = []
VIEW_W = 1280          # 教师/学生页面都是桌面视口（走查用 1440×900，放宽到 1280 只挡"手机截图冒充"）

DB = ["mysql", "--protocol=tcp", "-h", "127.0.0.1", "-P", "3307", "-uroot", "cet46",
      "--default-character-set=utf8mb4", "-N", "-B"]


def sql(q):
    out = subprocess.run(DB + ["-e", q], capture_output=True)
    if out.returncode != 0:
        bad.append("SQL 失败：%s" % out.stderr.decode("utf-8", "replace")[:200])
        return []
    text = out.stdout.decode("utf-8", "replace").replace("\r", "")
    return [ln.split("\t") for ln in text.split("\n") if ln.strip()]


# ---- 图清单：走查要拍到的每一帧（缺一张就是缺证据，不能靠"文件数>0"糊过去）----
WANT = [
    ("01-t-redeem-empty",         "核销页首屏：券码输入框 + 检索按钮 + 说明"),
    ("02-t-lookup-pending",       "输码检索出待确认的券（学生/班级/券价/余额 + 两个按钮可按）"),
    ("03-t-reject-dialog",        "驳回确认弹窗（写清：券退回券包、兑换积分不退）"),
    ("04-t-rejected",             "驳回后：已退回 pill + 留痕号 + 本次会话处理记录"),
    ("05-t-lookup-rejected",      "重新检索被驳回的券：已退回、只剩「确认核销」可按"),
    ("06-t-reconfirmed",          "改判核销后：已核销 + 处理记录里驳回与核销两条"),
    ("07-t-confirm-dialog",       "确认确认弹窗（写清：终态不可改判 + 余额不动）"),
    ("08-t-confirmed",            "核销后：已核销 + 两个按钮都灰 + 留痕号"),
    ("09-t-repeat-confirm-40904", "重复确认被拒：40904 文案带处理人与时间"),
    ("10-t-audit-confirm",        "审计日志页筛「核销确认」：动作/操作人/时间三要素"),
    ("11-t-audit-reject",         "审计日志页筛「核销驳回」：动作/操作人/时间三要素"),
    ("12-s-wallet",               "学生券包：已核销与已退回并存 + 口径句 + 「还能用」提示"),
    ("13-t-redeem-page",          "核销页整页"),
    ("14-s-wallet-page",          "学生券包整页"),
]
sizes, md5s = {}, {}

print("--- 截图逐张校验（%d 张）---" % len(WANT))
for name, desc in WANT:
    p = os.path.join(shots, name + ".png")
    if not os.path.exists(p):
        bad.append("缺截图 %s.png（%s）" % (name, desc))
        print("%-28s 缺失（%s）" % (name, desc))
        continue
    with open(p, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    m = hashlib.md5(open(p, "rb").read()).hexdigest()
    sizes[name], md5s[name] = (w, h), m
    print("%-28s %sx%s  md5 %s  %s" % (name, w, h, m[:8], desc))
    if w < VIEW_W:
        bad.append("%s 宽 %d < %d（不像桌面页截图）" % (name, w, VIEW_W))
    if h < 300:
        bad.append("%s 高度 %s 太小，不像一块内容" % (name, h))

dup = {}
for name, m in md5s.items():
    dup.setdefault(m, []).append(name)
for m, names in dup.items():
    if len(names) > 1:
        bad.append("有 %d 张截图字节完全相同（%s）：等于只有一张证据" % (len(names), "、".join(names)))
print("去重后 %d 张（应有 %d 张）" % (len(set(md5s.values())), len(WANT)))

# ---- 走查 JSON ----
print()
print("--- 走查 JSON ---")
walk_path = os.path.join(ev, "walkthrough.json")
d = {}
if not os.path.exists(walk_path):
    bad.append("缺 walkthrough.json（走查子代理没落盘断言与对拍记录）")
else:
    with io.open(walk_path, encoding="utf-8") as f:
        d = json.load(f)
    checks = d.get("checks") or []
    fails = d.get("fails") or []
    print("断言 %d 条 / 失败 %d 条" % (len(checks), len(fails)))
    if len(checks) < 30:
        bad.append("走查断言只有 %d 条（<30）：核销全链路（检索/驳回/改判/确认/重复确认/审计/券包）都要覆盖" % len(checks))
    if bool(d.get("all_ok")) != (len(fails) == 0):
        bad.append("all_ok 与 fails 条数不自洽（all_ok=%r / fails=%d）" % (d.get("all_ok"), len(fails)))
    if fails:
        bad.append("走查有失败断言：%r" % ([f.get("name", "")[:70] if isinstance(f, dict) else str(f)[:70] for f in fails][:5],))

    def ok_checks(*needles, must_all=True):
        out = []
        for c in checks:
            if not isinstance(c, dict):
                continue
            n = c.get("name", "")
            hit = all(k in n for k in needles) if must_all else any(k in n for k in needles)
            if hit:
                out.append(c)
        return out

    # 关键行为必须有**ok=true** 的断言在册（走查子代理自己写的"我做过了"不算，要有名字能查）
    REQUIRED = [
        ("40904", "重复确认被拒的业务码"),
        ("积分不退", "驳回不退分的口径"),
        ("已退回", "学生端/教师端看到「已退回」"),
        ("核销", "核销调用链"),
        ("留痕", "留痕号回到页面"),
        ("审计", "审计页可筛"),
        ("限购", "驳回占着限购名额"),
    ]
    for kw, why in REQUIRED:
        got = [c for c in ok_checks(kw) if c.get("ok")]
        if not got:
            bad.append("走查里没有 ok=true 的「%s」断言（%s）" % (kw, why))
        else:
            print("在册：%s —— %s" % (kw, got[0]["name"][:78]))

    # ---- 券状态对拍：页面上看到的 == 接口回执 == 库里的行 ----
    print()
    print("--- 券状态三方对拍（页面 / 接口 / 库）---")
    cc = d.get("codeCompare") or []
    print("对拍 %d 条" % len(cc))
    if len(cc) < 6:
        bad.append("codeCompare 少于 6 条：待确认/已退回/改判核销/已核销/重复确认/券包回显都要落到页面上")
    cbad = [r for r in cc if not r.get("ok")]
    if cbad:
        bad.append("券状态对拍有不一致的行：%r" % ([r.get("item") for r in cbad][:4],))
    ctext = " ".join((r.get("page") or "") + (r.get("api") or "") for r in cc)
    for kw in ("待老师确认", "已退回", "已核销", "40904", "积分不退", "300"):
        if kw not in ctext:
            bad.append("券状态对拍里没有出现「%s」" % kw)

    # ---- 审计三要素对拍（动作 / 操作人 / 时间）----
    print()
    print("--- 审计留痕对拍（动作/操作人/时间）---")
    ac = d.get("auditCompare") or []
    print("对拍 %d 条" % len(ac))
    if len(ac) < 2:
        bad.append("auditCompare 少于 2 条：核销与驳回两条留痕都要在页面上对到")
    for r in ac:
        blob = (r.get("page") or "") + " " + (r.get("api") or "")
        if not r.get("ok"):
            bad.append("留痕对拍不一致：%r" % (r.get("action"),))
        if "S12验收教师" not in blob:
            bad.append("留痕对拍里没写操作人（%r）" % (r.get("action"),))
        if not any(x in blob for x in ("2026-10-14", "2026-")):
            bad.append("留痕对拍里没写时间（%r）" % (r.get("action"),))

    # ---- 库侧独立对拍：不信子代理的叙述，直接查库 ----
    print()
    print("--- 库侧独立对拍（券行 + audit_log）---")
    env = {}
    with io.open(os.path.join(ev, "s12-env.json"), encoding="utf-8") as f:
        env = json.load(f)
    tea_id = env["teacher"]["id"]
    stu = (d.get("studentUsername") or "").strip()
    if not stu:
        bad.append("walkthrough.json 缺 studentUsername（走查用的那个学生学号）")
    else:
        uid_rows = sql("select id, class_id from users where username='%s'" % stu)
        if not uid_rows:
            bad.append("走查学生 %s 不在库里" % stu)
            uid = None
        else:
            uid = int(uid_rows[0][0])
            cid = int(uid_rows[0][1])
            cls = sql("select name from classes where id=%d" % cid)
            print("走查学生 %s（id=%d，班=%s）" % (stu, uid, cls[0][0] if cls else "?"))
        if uid:
            rows = sql("select code, status, coalesce(confirmed_by,0), "
                       "coalesce(date_format(confirmed_at,'%%Y-%%m-%%d'),'') "
                       "from coupon_redeems where user_id=%d order by id" % uid)
            print("该生券行 %d 条：" % len(rows))
            for c, st, by, at in rows:
                print("   %s %s by=%s at=%s" % (c, st, by, at))
            if len(rows) != 3:
                bad.append("走查学生应有 3 张券（驳回一张、改判一张、核销一张），实际 %d 张" % len(rows))
            states = sorted(r[1] for r in rows)
            if states and states != ["confirmed", "confirmed", "rejected"]:
                bad.append("3 张券的状态组合应是 2 confirmed + 1 rejected，实际 %r" % (states,))
            for c, st, by, at in rows:
                if st in ("confirmed", "rejected") and int(by) != tea_id:
                    bad.append("券 %s 的处理人不是走查教师（by=%s 应为 %d）" % (c, by, tea_id))
            # 页面/JSON 里声明的终态必须与库一致
            for code, want in (d.get("codeStates") or {}).items():
                got = [r[1] for r in rows if r[0] == code]
                if not got or got[0] != want:
                    bad.append("券 %s 声明 %s，库里是 %r" % (code, want, got))
            # 4 条留痕：驳回+改判核销（同一张券两次动作）+ 核销 + 驳回；actor 必须是走查教师
            codes = [r[0] for r in rows]
            if codes:
                inlist = ",".join("'%s'" % c for c in codes)
                au = sql("select action, actor, date_format(created_at,'%%Y-%%m-%%d %%H:%%i:%%s'), "
                         "coalesce(detail,'') from audit_log where detail like '%%%s%%' or "
                         "detail like '%%%s%%' or detail like '%%%s%%' order by id"
                         % (codes[0], codes[1] if len(codes) > 1 else codes[0],
                            codes[2] if len(codes) > 2 else codes[0]))
                mine = [r for r in au if r[0] in ("redeem_confirm", "redeem_reject")]
                print("这四个券码上的核销/驳回留痕 %d 条：" % len(mine))
                for a, actor, at, _det in mine:
                    print("   %s actor=%s at=%s" % (a, actor, at))
                if len(mine) < 4:
                    bad.append("核销/驳回留痕少于 4 条（应有：驳回、改判核销、核销、驳回），实际 %d" % len(mine))
                today = "2026-10-14"
                for a, actor, at, _det in mine:
                    if int(actor) != tea_id:
                        bad.append("留痕 %s 的操作人不是走查教师（actor=%s）" % (a, actor))
                    if not at.startswith(today):
                        bad.append("留痕 %s 的时间不是今天（%s）" % (a, at))
                acts = [r[0] for r in mine]
                for need in ("redeem_confirm", "redeem_reject"):
                    if need not in acts:
                        bad.append("留痕里缺 action=%s" % need)
                # 同一张券"驳回 → 改判核销"两条痕：detail 的 from/to 必须对得上
                first = codes[0]
                seq = [r for r in mine if first in r[3]]
                if len(seq) >= 2:
                    ok_pair = ("\"to\":\"rejected\"" in seq[0][3] or "\"to\":\"rejected\"" in seq[0][3]
                               or "rejected" in seq[0][3]) and "confirmed" in seq[1][3]
                    if not ok_pair:
                        bad.append("第一张券的两条留痕不是「驳回 → 改判核销」：%r" % ([r[3][:60] for r in seq[:2]],))
                else:
                    bad.append("第一张券 %s 上没有两条留痕（驳回 + 改判核销）" % first)

    # ---- 学生页面脱敏：别的学生与老师的姓名不许出现 ----
    stext = d.get("studentPageText") or ""
    leaks = [x for x in (d.get("studentTokens") or []) if x and x in stext]
    if leaks:
        bad.append("学生页面上出现了别人的姓名/教师姓名：%r" % (leaks,))
    else:
        print()
        print("学生页面文本里 0 处他人姓名（页面侧脱敏）")
    for kw in ("已核销", "已退回", "积分不退", "还能用"):
        if kw not in stext:
            bad.append("学生券包页面上没看到「%s」" % kw)
    if not d.get("leftRejectedInWallet"):
        bad.append("walkthrough 没声明券包里真留了一张「已退回」的券")

    # ---- 整页截图是不是"真整页" ----
    # 两条口径：①图高 == 该页文档实测 scrollHeight（±4px，放宽到 8px 容忍视口取整）；
    # ②noInnerScroll=true，排掉"内层滚动容器让整页只剩一屏"（S10.5 踩过）。
    print()
    print("--- 整页截图 ---")
    phs = d.get("pageHeights") or {}
    if not isinstance(phs, dict) or not phs:
        bad.append("walkthrough.json 缺 pageHeights（各整页的 document.scrollHeight 实测值）")
    for nm in ("13-t-redeem-page", "14-s-wallet-page"):
        ph = phs.get(nm)
        h = (sizes.get(nm) or (0, 0))[1]
        if not isinstance(ph, int) or ph <= 0:
            bad.append("pageHeights 缺 %s 的文档实测高（拿不到就没法证明它是整页）" % nm)
            continue
        print("%s 图高 %d px / 文档实测高 %d px" % (nm, h, ph))
        if h and abs(h - ph) > 8:
            bad.append("%s 图高 %d 与文档真实高 %d 对不上（±8px）：这张不是整页" % (nm, h, ph))
    if not d.get("noInnerScroll", False):
        bad.append("walkthrough.json 的 noInnerScroll 不是 true：没有机器证据说明页面没有内层滚动容器截断")
    rects = d.get("sectionRects") or []
    print("板块矩形 %d 条" % len(rects))
    if len(rects) < 3:
        bad.append("sectionRects 少于 3 条（检索区/结果卡/处理记录 都要量到）")
    else:
        for r in rects:
            page = r.get("page") or "13-t-redeem-page"
            ph = phs.get(page)
            if isinstance(ph, int) and (r.get("bottom") or 0) > ph + 2:
                bad.append("板块「%s」底边 %s 超过 %s 的文档高 %d（会被截断）"
                           % (r.get("name"), r.get("bottom"), page, ph))

result = "SHOTS_OK" if not bad else "SHOTS_MISMATCH " + "；".join(bad)
print()
print(result)
sys.exit(1 if bad else 0)
PY
rc=${PIPESTATUS[0]}
check "证据清点结论 SHOTS_OK（Python 段退出码）" "0" "$rc"

echo
echo "S12 走查证据清点结束：$(date '+%Y-%m-%d %H:%M:%S')  失败数=$FAILS"
exit $(( FAILS > 0 ? 1 : 0 ))