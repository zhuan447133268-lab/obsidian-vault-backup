#!/usr/bin/env bash
# S11 走查证据清点：截图逐张校验 + 走查 JSON 的断言数与"10s 自动刷新"证据。
# 用法：bash run-shots-check.sh   （在真浏览器走查跑完之后）
#
# 为什么单独一个脚本：截图是走查子代理的产物，验收断言脚本（s11_accept.py）跑在它之前。
# 把"图是不是真图、两两是否不同、数是不是真跑到了"这类清点独立出来，谁来跑都同一把尺子。
#
# 踩过的坑（都写在这里当尺子）：
#   · 截图必须从 PNG 头读真实尺寸并进 check（打印出来的数字不算断言）；
#   · 同一场景内多张截图必须 md5 两两不同（4 张字节一样 = 只有 1 张证据）；
#   · 大屏是桌面视口（1440×900）：整页截图高必须等于文档实测 scrollHeight（±4px），
#     并用 noInnerScroll 排掉"内层滚动容器让 fullPage 只剩一屏"这个坑——比猜一个高度阈值硬；
#   · 断言数必须与预期条数核对（分桶函数写错会让整段断言从未执行）。
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

echo "S11 走查证据清点开始：$(date '+%Y-%m-%d %H:%M:%S')"
# stdout 同时落到 shots-check-out.txt（归档用）；结论以 Python 段退出码为准（见下 PIPESTATUS）
python - "$EWIN" <<'PY' 2>&1 | tee "$EVID/shots-check-out.txt"
import hashlib
import json
import os
import struct
import sys

ev = sys.argv[1]
shots = os.path.join(ev, "shots")
bad, problems = [], []

# ---- 图清单：走查要拍到的每一帧（缺一张就是缺证据，不能靠"文件数>0"糊过去）----
WANT = [
    ("01-live-first",       "登录后首进大屏（默认班，10s 档）"),
    ("02-live-metrics",     "三指标区（参与率/进度分布/卡关热点）"),
    ("03-live-wrong-board", "易错题榜首屏"),
    ("04-live-refresh-a",   "自动刷新第 1 帧（记录『更新于』时刻）"),
    ("05-live-refresh-b",   "自动刷新第 2 帧（≥10s 后，『更新于』应已变）"),
    ("06-live-interval",    "把刷新间隔改成 30s 后的界面（可配置证据）"),
    ("07-live-fullscreen",  "全屏态大屏"),
    ("08-live-page",        "整页（本题材恰好一屏：截图高 == 文档实测高 900）"),
]
VIEW_W, VIEW_H = 1440, 900
sizes, md5s = {}, {}

print("--- 截图逐张校验（%d 张）---" % len(WANT))
for name, desc in WANT:
    p = os.path.join(shots, name + ".png")
    if not os.path.exists(p):
        bad.append("缺截图 %s.png（%s）" % (name, desc))
        print("%-22s 缺失（%s）" % (name, desc))
        continue
    with open(p, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    m = hashlib.md5(open(p, "rb").read()).hexdigest()
    sizes[name], md5s[name] = (w, h), m
    print("%-22s %sx%s  md5 %s  %s" % (name, w, h, m[:8], desc))
    if w < VIEW_W:
        bad.append("%s 宽 %d < 视口宽 %d" % (name, w, VIEW_W))
    if h < 400:
        bad.append("%s 高度 %s 太小，不像一块内容" % (name, h))
    # 08 是不是"真整页"，不靠猜一个高度阈值：下面拿 walkthrough.json 里量的
    # document.scrollHeight 与这张图的高度对齐（大屏内容恰好一屏时两者也该相等）。

# ---- 两两不同：同场景多帧必须不是同一帧 ----
dup = {}
for name, m in md5s.items():
    dup.setdefault(m, []).append(name)
for m, names in dup.items():
    if len(names) > 1:
        bad.append("有 %d 张截图字节完全相同（%s）：等于只有一张证据" % (len(names), "、".join(names)))
print("去重后 %d 张（应有 %d 张）" % (len(set(md5s.values())), len(WANT)))

# ---- 走查 JSON：断言数、失败数、自动刷新证据、无身份字段 ----
print()
print("--- 走查 JSON ---")
walk_path = os.path.join(ev, "walkthrough.json")
if not os.path.exists(walk_path):
    bad.append("缺 walkthrough.json（走查子代理没落盘断言与时间线）")
else:
    d = json.load(open(walk_path, encoding="utf-8"))
    checks = d.get("checks") or []
    fails = d.get("fails") or []
    print("断言 %d 条 / 失败 %d 条" % (len(checks), len(fails)))
    if len(checks) < 30:
        bad.append("走查断言只有 %d 条（<30）：大屏的走查至少要覆盖首屏/三指标/榜单/刷新/配置/全屏" % len(checks))
    if bool(d.get("all_ok")) != (len(fails) == 0):
        bad.append("all_ok 与 fails 条数不自洽（all_ok=%r / fails=%d）" % (d.get("all_ok"), len(fails)))
    fail_names = [f.get("name", "") if isinstance(f, dict) else str(f) for f in fails]

    def ok_checks(*needles, must_all=True):
        """名字里同时含这些关键词的 check 列表（must_all=False 只要含任意一个）。"""
        out = []
        for c in checks:
            if not isinstance(c, dict):
                continue
            n = c.get("name", "")
            hit = all(k in n for k in needles) if must_all else any(k in n for k in needles)
            if hit:
                out.append(c)
        return out

    # ---- 放行政策：只放行"环境/工具链限制"，且每条必须带补偿证据 ----
    # 写死在闸门里（不放进 walkthrough.json），谁来跑都是同一把尺子：豁免了什么、拿什么补的，一眼可见。
    # 匹配语义：某条失败断言必须**满足某条豁免的全部要求**才放行——①命中 kw_any 任一关键词；
    # ②该条自己的文案里必须写明 need_text 里的每一句（把"环境限制"当万能挡箭牌不行）；
    # ③comp 列的补偿断言必须真实存在且 ok=true。三者缺一 → 照红。
    WAIVERS = [
        # ① 自动化浏览器投不出可信输入事件 → 登录/导航由应用自身的事件处理器完成（仍是真凭据真会话）
        {"kw_any": ("环境限制", "输入通道", "isTrusted=false"),
         "need_text": ("isTrusted=false", "未注入 token", "未跳过登录"),
         "comp": [("POST /api/auth/login", "200", True),
                  ("未注入 token", "未跳过登录", True),
                  ("/t/live", True)],
         "why": "工具链投不出可信输入事件（playwright click 超时 / cua.click 无命中 / press 无 keydown）；"
                "补偿：真实 POST /api/auth/login=200 且 code=0 + URL 真到 /t/live + 断言明写未注入 token、未跳过登录"},
        # ② 自动化浏览器对首个实例的定时器节流（20s 那次是浏览器伪影）→ 补偿：重挂载后 10s、改档后 30s 都实测到了
        {"kw_any": ("环境伪影", "节流"),
         "need_text": ("节流", "10.004"),
         "comp": [("轮询", "10.004", True), ("30 秒", "30", True)],
         "why": "首个实例的 1s 心跳被自动化浏览器节流（同页裸 setInterval 探针仍 1.000s/次）；"
                "补偿：重挂载后应用真实 delay=1000ms、两轮轮询实测 10.004s（另有 8~14s 硬断言）+ 改 30 秒档实测 30.005/29.992s"},
        # ③ 自动化点击不是用户手势 → 浏览器拒绝全屏；补偿：应用确实调了 requestFullscreen 且静默 catch、控制台 0 报错
        {"kw_any": ("工具链限制", "全屏未真正生效", "Permissions check failed"),
         "need_text": ("Permissions check failed", "isTrusted=false"),
         "comp": [("requestFullscreen", True), ("console.error", "0", True)],
         "why": "自动化点击 isTrusted=false 不构成用户手势 → 浏览器拒绝全屏（真机人工点击不受影响）；"
                "补偿：包装捕获到按钮确实调用 documentElement.requestFullscreen() + 应用 catch{} 静默处理、console 报错 0 条"},
        # ④ IAB 的 fullPage 截图是 2x2 拼贴伪图 → 08 改用视口路径；补偿：文档实测无折叠以下内容
        {"kw_any": ("工具链限制", "fullPage=true", "伪图"),
         "need_text": ("scrollHeight=900", "08-live-page-fullpage-raw-artifact.png"),
         "comp": [("整页高度", "900", True)],
         "why": "fullPage 伪图属工具链缺陷（象限重复度 0.55% vs 真实视口截图 100% 对照）；"
                "补偿：scrollHeight==视口高且 noInnerScroll=true（下面另有硬断言）"},
    ]
    waived, waived_names, uncovered = [], set(), []
    for fn in fail_names:
        best_miss, matched = None, False
        for w in WAIVERS:
            if not any(k in fn for k in w["kw_any"]):
                continue
            miss = ["文案缺 %r" % t for t in w["need_text"] if t not in fn]
            for needles in w["comp"]:
                *kws, want_ok = needles
                # 注意：失败断言自己的文案里通常也含这些关键词（正是它在解释现象），
                # 所以补偿证据只认 **ok=true 的断言**——"我自己说自己没事"不算证据。
                got = [c for c in ok_checks(*kws) if c.get("ok")]
                if not got or (want_ok and not got):
                    miss.append("补偿证据缺 %s" % "+".join(kws))
            if miss:
                if best_miss is None:
                    best_miss = miss
                continue
            waived.append(w["why"])
            waived_names.add(fn)
            matched = True
            break
        if not matched:
            uncovered.append(fn[:70] + ("（%s）" % "；".join(best_miss) if best_miss else ""))
    if waived:
        print("按环境/工具链限制放行 %d 条（每条都带补偿证据）：" % len(waived))
        for w in waived:
            print("  · %s" % w)
    if uncovered:
        bad.append("走查有未被放行的失败断言：%r" % (uncovered[:5],))

    # 08 伪图的原始证据必须留档（不能只留结论）
    if any("伪图" in fn for fn in fail_names):
        art = os.path.join(shots, "08-live-page-fullpage-raw-artifact.png")
        if not os.path.exists(art):
            bad.append("声明了 fullPage 伪图，却没留原始伪图 %s（结论要有物证）" % art)

    # 全屏：必须有覆盖；若如实记了"没真进全屏"，该条失败断言必须①写清原因、②按豁免③放行（拿不出补偿证据照红）
    fs = ok_checks("全屏", must_all=False)
    if not fs:
        bad.append("走查里没有任何全屏相关断言")
    fs_fail = [c for c in fs if not c.get("ok")]
    if fs_fail:
        fs_naive = [c for c in fs_fail if any(k in c.get("name", "") for k in
                                              ("未真正进入全屏", "全屏未真正生效", "未生效"))]
        if not fs_naive:
            bad.append("有失败的全屏断言，但没如实写成『未真正进入全屏 / 未生效』（不可含糊）")
        fs_reason = [c for c in fs_fail if any(k in c.get("name", "") for k in
                                               ("Permissions check failed", "isTrusted"))]
        if not fs_reason:
            bad.append("如实记了全屏没进成，但断言里没写原因（Permissions check failed / 非用户手势）")
        else:
            print("全屏未进成的原因已写明：%s" % fs_reason[0]["name"][:90])
        if not all(c.get("name", "") in waived_names for c in fs_fail):
            bad.append("全屏失败没被豁免③放行（或豁免缺补偿证据）：『真全屏进不去』只认"
                       "『确实调了 requestFullscreen + 控制台 0 报错』这条补偿")

    # 自动刷新的机器证据：两次请求的时间差（前端按 10s 轮询）
    t1, t2 = d.get("refreshT1"), d.get("refreshT2")
    if t1 is None or t2 is None:
        bad.append("walkthrough.json 缺 refreshT1/refreshT2（两次自动刷新的时刻）")
    else:
        delta = round(float(t2) - float(t1), 1)
        print("两次自动刷新间隔：%.1fs" % delta)
        if not (8.0 <= delta <= 14.0):
            bad.append("两次自动刷新间隔 %.1fs 不在 8~14s 内（默认档应 ~10s）" % delta)

    # 大屏页面上不许出现任何学生标识（防压力设计的页面侧证据）
    text = (d.get("pageText") or "")
    leaks = [x for x in (d.get("studentTokens") or []) if x and x in text]
    if leaks:
        bad.append("大屏页面文本里出现了学生标识：%r" % (leaks,))
    else:
        print("页面文本里 0 处学生标识（防压力设计页面侧）")

    # 页面上的数必须与接口回执一致（走查子代理会把两者都记下来）
    print("--- 页面数字 vs 接口回执（由走查记录，脚本只核条数）---")
    cmp_rows = d.get("metricCompare") or []
    print("逐项对拍 %d 条" % len(cmp_rows))
    if len(cmp_rows) < 3:
        bad.append("metricCompare 少于 3 条：三指标（参与率/进度/卡关）+ 易错题榜都要落到页面上")

    # ---- 08-live-page 是不是"真整页"：图高 == 文档真实高度，且没有内层滚动容器把内容藏起来 ----
    # （S8/S10 踩过的坑：大屏若套一层 overflow 容器，fullPage 出来还是"一屏"，看着有图没证据。）
    ph = d.get("pageHeightPx")
    h08 = (sizes.get("08-live-page") or (0, 0))[1]
    if not isinstance(ph, int) or ph <= 0:
        bad.append("walkthrough.json 缺 pageHeightPx（document.scrollHeight 的实测值）")
    else:
        print("整页截图高 %d px / 文档实测高 %d px" % (h08, ph))
        if abs(h08 - ph) > 4:
            bad.append("08-live-page 高 %d 与文档真实高 %d 对不上（±4px）：说明这张不是整页" % (h08, ph))
        if h08 <= VIEW_H and not d.get("noInnerScroll"):
            bad.append("大屏恰好一屏高时，必须由 walkthrough 断言 noInnerScroll=true 才能排除"
                       "『内层容器截断、图只有一屏』的可能")
    if not d.get("noInnerScroll", False):
        bad.append("walkthrough.json 的 noInnerScroll 不是 true：没机器证据说明没有内层滚动容器")
    rects = d.get("sectionRects") or []
    print("四个板块矩形 %d 条" % len(rects))
    if len(rects) < 4:
        bad.append("sectionRects 少于 4 条（①参与率/②进度/③卡关/④易错题 都要量到）")
    elif isinstance(ph, int) and ph > 0:
        over = [r.get("name") for r in rects if (r.get("bottom") or 0) > ph + 2]
        if over:
            bad.append("这些板块的底边超过了文档高度（会被截断）：%r" % (over,))

result = "SHOTS_OK" if not bad else "SHOTS_MISMATCH " + "；".join(bad)
print()
print(result)
sys.exit(1 if bad else 0)
PY
rc=${PIPESTATUS[0]}
check "证据清点结论 SHOTS_OK（Python 段退出码）" "0" "$rc"

echo
echo "S11 走查证据清点结束：$(date '+%Y-%m-%d %H:%M:%S')  失败数=$FAILS"
exit $(( FAILS > 0 ? 1 : 0 ))