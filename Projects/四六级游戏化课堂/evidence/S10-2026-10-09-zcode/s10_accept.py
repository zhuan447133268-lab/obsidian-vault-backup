# -*- coding: utf-8 -*-
"""S10 六条验收实跑（打活环境 8080 + 3307 裸库，产物留本目录，不进仓库）。

验收① 导出平时成绩表：表头逐列对齐 PRD 字段表 + 每一格都能被独立算出
验收② 手动调关：学生端与教师端双端即时生效，且不动成绩与 XP
验收③ audit_log：调关 / 排行开关 / 兑换核销可查，含过滤、分页、actor 隔离
验收⑤ 改密后旧 JWT 立即失效（自助改密 + 教师重置为随机临时密码两条路径）
验收⑥ 越权：跨班写路径一律 404（不给"存在但无权"的可枚举信号），校级视图 403
验收⑦ D8 双口径：/auth/me 的 lv/streak 与看板/导出同源于 xp_ledger
验收⑨ 冷启动：classId 缺省时看板/明细/导出落到同一个班（走查撞出的缺陷回归）

验收④（1440px 截图走查）由 s10_shots.py 校验浏览器子代理产出的 PNG。
"""
import datetime
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from s10_lib import (BASE, Fail, Harness, NEWPWD, code_of, data_of,  # noqa: E402
                    req, say, sql, sql1, sql_int)

ENV = json.load(io.open(os.path.join(HERE, "s10-env.json"), encoding="utf-8"))
TA, TB, AD = ENV["teacherA"]["token"], ENV["teacherB"]["token"], ENV["admin"]["token"]
TA_ID, TB_ID = ENV["teacherA"]["id"], ENV["teacherB"]["id"]
CLS_A = ENV["classes"]["S10验收1班"]
CLS_A2 = ENV["classes"]["S10验收2班"]
CLS_B = ENV["classes"]["S10验收3班"]
A, A2, B = CLS_A["id"], CLS_A2["id"], CLS_B["id"]
STU = ENV["students"]
STU_A = ["S10A01", "S10A02", "S10A03", "S10A04", "S10A05", "S10A06"]

NEWPWD2 = "S10Accept@2026b"
COUPON = "S10 验收核销券"

h = Harness("S10-ACCEPT")
REFRESHED = []


# ---------------------------------------------------------------- 令牌自愈
#
# 为什么要有这一段：验收⑤会反复改密（自助改密 / 教师重置），改密即换签名——
# 上一轮脚本如果在改密之后就崩了，s10-env.json 里留的是作废令牌，
# 下一轮开头就会拿废令牌去跑出「莫名其妙 401」的假失败（实跑踩过）。
# 所以每轮开头先把所有角色的令牌换成当场现签的：能直接用统一口令登就登，
# 登不进（口令被人改过 / 状态没复位）就用 admin 重置成临时密码再改回统一口令。
def login_fresh(username):
    """返回现签 token；口令不对时用 admin 重置兜底。"""
    st, p = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
    if st == 200 and code_of(p) == 0:
        return data_of(p)["token"], ""
    uid = sql1("select id from users where username='%s'" % username)
    if not uid:
        raise Fail("用户不存在，环境需要重跑 s10_setup.py: " + username)
    st, p = req("POST", "/admin/users/%s/reset-pwd" % uid, token=AD)
    if st != 200 or code_of(p) != 0:
        raise Fail("admin 重置 %s 失败（admin 令牌也可能已失效）: %s" % (username, p))
    temp = data_of(p)["tempPassword"]
    st, p = req("POST", "/auth/login", body={"username": username, "password": temp})
    if st != 200 or code_of(p) != 0:
        raise Fail("临时密码登录失败 %s: %s" % (username, p))
    t = data_of(p)["token"]
    st, p = req("POST", "/auth/chpwd", token=t,
                body={"oldPassword": temp, "newPassword": NEWPWD})
    if st != 200 or code_of(p) != 0:
        raise Fail("临时密码改回统一口令失败 %s: %s" % (username, p))
    st, p = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
    if st != 200 or code_of(p) != 0:
        raise Fail("复位后登录失败 %s: %s" % (username, p))
    return data_of(p)["token"], "（上轮留下废口令，已重置复位）"


def refresh_tokens():
    global TA, TB, AD
    AD, note = login_fresh(ENV["admin"]["username"])
    TA, noteA = login_fresh(ENV["teacherA"]["username"])
    TB, noteB = login_fresh(ENV["teacherB"]["username"])
    ENV["admin"]["token"], ENV["teacherA"]["token"], ENV["teacherB"]["token"] = AD, TA, TB
    broken = []
    for name in sorted(ENV["students"]):
        try:
            t, note = login_fresh(name)
        except Fail as e:
            broken.append("%s: %s" % (name, e))
            continue
        ENV["students"][name]["token"] = t
        if note:
            REFRESHED.append(name)
    # 先落盘：中途再崩，下一轮也不会捡到废令牌。
    with io.open(os.path.join(HERE, "s10-env.json"), "w", encoding="utf-8") as f:
        json.dump(ENV, f, ensure_ascii=False, indent=2)
    say("令牌自愈：admin/教师A/教师B + %d 名学生换用现签令牌%s%s%s；异常 %d 名"
        % (len(ENV["students"]), noteA, noteB, "" if not REFRESHED else "，其中重置过 " + ",".join(REFRESHED),
           len(broken)))
    for b in broken:
        say("  [FAIL] " + b)
    return len(broken)


# ---------------------------------------------------------------- 基础工具

def req_full(path, token=None):
    """一次 GET，连响应头一起拿（导出要读 Content-Disposition）。"""
    hdr = {"Authorization": "Bearer " + token} if token else {}
    r = urllib.request.Request(BASE + path, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def me_of(payload):
    """取用户视图：/auth/login 包在 {user:...} 里，/auth/me 直接就是 UserDTO。"""
    d = data_of(payload) or {}
    return d.get("user") or d


def now():
    return datetime.datetime.now()


def week_start(t):
    return datetime.datetime.combine(t.date() - datetime.timedelta(days=t.weekday()),
                                     datetime.time.min)


def stamp(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")


def streak_of(uid):
    """连续到课周数：账本出现过的周往前数（镜像 quiz.StreakWeeks）。"""
    rows = sql("select created_at from xp_ledger where user_id=%d" % uid)
    active = [datetime.datetime.strptime(r[0][:19], "%Y-%m-%d %H:%M:%S") for r in rows]
    if not active:
        return 0
    weeks = {week_start(t) for t in active}
    cur = week_start(now())
    if cur not in weeks:
        cur -= datetime.timedelta(days=7)
    n = 0
    while cur in weeks:
        n += 1
        cur -= datetime.timedelta(days=7)
    return n


def ledger_total(uid):
    return sql_int("select coalesce(sum(delta),0) from xp_ledger where user_id=%d" % uid)


def ledger_week(uid, ws):
    return sql_int("select coalesce(sum(delta),0) from xp_ledger "
                   "where user_id=%d and created_at >= '%s'" % (uid, stamp(ws)))


def clears_of(uid):
    return sql_int("select count(distinct level_id) from attempts "
                   "where user_id=%d and status='finished' and finished_at is not null" % uid)


def clears_between(uid, a, b):
    return sql_int("select count(distinct level_id) from attempts where user_id=%d and status='finished' "
                   "and finished_at is not null and finished_at >= '%s' and finished_at < '%s'"
                   % (uid, stamp(a), stamp(b)))


def accuracy_of(uid):
    rows = sql("select coalesce(sum(correct),0), coalesce(sum(total),0) from attempts "
               "where user_id=%d and status='finished'" % uid)
    part, whole = int(rows[0][0]), int(rows[0][1])
    if whole <= 0:
        return 0.0
    return float(int(float(part) / whole * 100 * 10 + 0.5)) / 10


def warn_of(uid):
    ws = week_start(now())
    tw = clears_between(uid, ws, now() + datetime.timedelta(seconds=1))
    lw = clears_between(uid, ws - datetime.timedelta(days=7), ws)
    return "是" if (tw < 1 and lw < 1) else "否"


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


# ============================================================ ⓪ 底账（别人题库）
#
# 本阶段加了大量教师端查询与一张审计查询接口，最该证明的"没动别人东西"就是题库：
# 表数/列数没变（17/128），且别人的班（所有历史验收班之外的班）单元/关/题数与
# 逐题指纹一字不动。指纹口径与 S9 完全同式：crc32(id \x1f stem \x1f options_json) 累加。
#
# 实现放在 SQL 侧（不是 Python）：题目里有 168 行 stem/options_json 带换行或制表符，
# 走 mysql CLI 的制表符输出取行必然错位——算式搬进 SQL 就没有"取错字段"的机会。
# 等价性已交叉验证：同一集合用 S9 的 Python 算式算出的 3897258111，本算式逐位相同。
OTHERS = ("('S9商城验收班','S9售罄验收班','S10验收1班','S10验收2班','S10验收3班')")
BANK_CRC_S9 = 3897258111  # S9 交卷报告里的 bank_crc（跨阶段不变即"别人题库未被动过"）


def bank_fingerprint():
    where = " where c.name not in " + OTHERS
    q = " from questions q join levels l on l.id=q.level_id join units u on u.id=l.unit_id join classes c on c.id=u.class_id"
    return {
        "tables": sql_int("select count(*) from information_schema.tables where table_schema='cet46'"),
        "columns": sql_int("select count(*) from information_schema.columns where table_schema='cet46'"),
        "units": sql_int("select count(*) from units u join classes c on c.id=u.class_id" + where),
        "levels": sql_int("select count(*) from levels l join units u on u.id=l.unit_id join classes c on c.id=u.class_id" + where),
        "questions": sql_int("select count(*) " + q + where),
        "crc": sql_int("select sum(crc32(concat(q.id, 0x1f, coalesce(q.stem,''), 0x1f, "
                       "coalesce(q.options_json,'')))) % 4294967296 " + q + where),
    }


def accept_baseline(snap):
    h.section("⓪ 底账：表/列未变，别人的题库逐题指纹与 S9 一致")
    h.eq(snap["tables"], 17, "表数仍是 17（S10 不加表——audit_log 是 S1 就建好的）")
    h.eq(snap["columns"], 128, "列数仍是 128（S10 不改列）")
    h.check(snap["crc"] == BANK_CRC_S9,
            "别人题库 CRC 与 S9 交卷值一致（%d）" % BANK_CRC_S9,
            "实际 %d（%d 单元 / %d 关 / %d 题）" % (snap["crc"], snap["units"], snap["levels"], snap["questions"]))


# ================================================================ ① 导出 xlsx

EXPORT_HEADER = ["学号", "姓名", "班级", "累计 XP", "本周 XP", "通关数",
                 "正确率", "连续到课周数", "预警标记"]


def accept_export():
    h.section("① 导出平时成绩表：表头逐列对齐 + 九列取值逐格对账")

    st, hdrs, body = req_full("/admin/export/grade?classId=%d" % A, TA)
    h.check(st == 200 and body[:2] == b"PK", "教师导出返回 200 且是 xlsx（zip 魔数）",
            "status=%d len=%d" % (st, len(body)))
    cd = hdrs.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
    fn = urllib.parse.unquote(m.group(1).strip('"')) if m else ""
    want_fn = "平时成绩_%s_%s.xlsx" % ("S10验收1班", datetime.date.today().strftime("%Y%m%d"))
    h.eq(fn, want_fn, "下载文件名 = 平时成绩_<班级>_<YYYYMMDD>.xlsx（RFC 5987 编码）")
    h.check("attachment" in cd, "响应头带 attachment（浏览器直接下载）", cd)

    wb = openpyxl.load_workbook(io.BytesIO(body))
    h.eq(wb.sheetnames, ["平时成绩"], "工作簿只有「平时成绩」一张表（没有残留 Sheet1）")
    ws = wb["平时成绩"]
    header = [c.value for c in ws[1]]
    h.eq(header, EXPORT_HEADER, "表头九列逐字对齐 PRD 字段表（顺序也算）")

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    usernames = sql("select username from users where class_id=%d and role='student' "
                    "order by username" % A)
    h.eq(len(rows), len(usernames), "一人一行（%d 名学生）" % len(usernames))
    h.eq(sorted(r[0] for r in rows), sorted(u[0] for u in usernames), "学号集合与班级名单一致")

    # 学号按文本导（长学号不被 Excel 变科学计数法）。
    first = ws.cell(row=2, column=1)
    h.check(first.data_type == "s", "学号写成文本单元格（data_type=%s）" % first.data_type, repr(first.value))

    # 看板明细：导出必须与它同源（同一个 Students()），对不上教师就会不信任这张表。
    st2, p2 = req("GET", "/admin/students?classId=%d" % A, token=TA)
    h.check(st2 == 200 and code_of(p2) == 0, "同班学生明细接口 200", "status=%d" % st2)
    dash = {x["username"]: x for x in data_of(p2)["items"]}

    ws_now = week_start(now())
    by_user = {r[0]: r for r in rows}
    bad = []
    for u, name in [(s, None) for s in STU_A]:
        uid = STU[u]["id"]
        real = sql1("select real_name from users where id=%d" % uid) or u
        row = by_user.get(u)
        if row is None:
            bad.append("%s 缺行" % u)
            continue
        want = {
            "姓名": real,
            "班级": "S10验收1班",
            "累计 XP": ledger_total(uid),
            "本周 XP": ledger_week(uid, ws_now),
            "通关数": clears_of(uid),
            "正确率": accuracy_of(uid),
            "连续到课周数": streak_of(uid),
            "预警标记": warn_of(uid),
        }
        got = dict(zip(EXPORT_HEADER[1:], row[1:]))
        for k, v in want.items():
            g = got[k]
            ok = close(g, v) if isinstance(v, float) else g == v
            if not ok:
                bad.append("%s.%s 实际=%r 期望=%r" % (u, k, g, v))
        # 与看板明细同源核对（独立再算一遍，不是抄接口的数）
        d = dash.get(u)
        if d is None:
            bad.append("%s 不在看板明细里" % u)
        else:
            for k, gotk, wantv in (("累计 XP", "totalXp", want["累计 XP"]),
                                   ("本周 XP", "weeklyXp", want["本周 XP"]),
                                   ("通关数", "totalCleared", want["通关数"]),
                                   ("连续到课周数", "streak", want["连续到课周数"])):
                if d[gotk] != wantv:
                    bad.append("看板 %s.%s=%r 与对账值 %r 不一致" % (u, gotk, d[gotk], wantv))
            if not close(d["accuracy"], want["正确率"]):
                bad.append("看板 %s.accuracy=%r 与对账值 %r 不一致" % (u, d["accuracy"], want["正确率"]))
            if (d["warn"] and want["预警标记"] != "是") or (not d["warn"] and want["预警标记"] != "否"):
                bad.append("看板 %s.warn=%r 与导出预警标记 %r 不一致" % (u, d["warn"], want["预警标记"]))
    h.check(not bad, "每一格都能被账本/attempts 独立算出（6 生 × 9 列 + 看板同源）", "; ".join(bad[:6]))

    # 留白的学生天然踩预警线：这条同时证明"预警不是人人都有"这个负例成立。
    h.check(any(r[8] == "是" for r in rows) and any(r[8] == "否" for r in rows),
            "预警标记同时出现「是」与「否」（规则真的在算，不是整列常量）",
            str([r[8] for r in rows]))
    return body, fn


# ================================================================ ② 手动调关

def accept_adjust():
    h.section("② 手动调关：锁定中的关卡被放行 / 已开的关卡被收回，双端即时生效")

    # 目标关卡的选法：解锁链是"前一关通关才开"，所以对某个学生来说
    # 已通关的那一关是"自然解锁"，它后面紧邻的那一关就是"自然锁定"。
    # S10A02 通关了第 1、2 关 → 第 4 关（Boss）仍锁定，正好当放行样本；
    # S10A01 通关了第 1~3 关 → 第 2 关自然解锁，正好当收回样本。
    #
    # 断言一律写成"状态迁移"而不是"初始必须是 X"：调关的 override 一旦写下就留着，
    # 脚本要能反复跑（上一轮的放行不该让这一轮的前置断言失败）。
    a02, a01 = STU["S10A02"]["id"], STU["S10A01"]["id"]
    lv4 = CLS_A["levels"]["4"][0]
    lv2 = CLS_A["levels"]["2"][0]

    def levels_of(who, token):
        st, p = req("GET", "/quiz/levels", token=token)
        return {x["id"]: x for x in data_of(p)["items"]}

    def teacher_levels(who):
        st, p = req("GET", "/admin/students/%d/levels" % who, token=TA)
        return {x["levelId"]: x for x in data_of(p)["items"]}

    # ---- 放行：把一个自然锁定的关卡打开 ----
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a02, "levelId": lv4, "action": "lock"})
    h.check(st == 200 and data_of(p)["unlocked"] is False, "先把目标关归一为锁定（幂等前置）",
            str(data_of(p)))
    item = levels_of("S10A02", STU["S10A02"]["token"])[lv4]
    h.check(item["unlocked"] is False and item["cleared"] is False,
            "前置：S10A02 的第 4 关锁定且未通关", str(item))
    st, p = req("GET", "/quiz/paper?level=%d" % lv4, token=STU["S10A02"]["token"])
    h.eq((st, code_of(p)), (403, 40303), "锁定关取卷被拒（403/40303，不是「取到卷再判失败」）")
    xp_before = ledger_total(a02)

    attempts_before = sql_int("select count(*) from attempts where user_id=%d and level_id=%d"
                              % (a02, lv4))
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a02, "levelId": lv4, "action": "unlock"})
    attempts_after = sql_int("select count(*) from attempts where user_id=%d and level_id=%d"
                             % (a02, lv4))
    h.eq(attempts_after, attempts_before, "调关不写 attempts（快照紧贴调用前后，只写 audit_log）")
    h.check(st == 200 and code_of(p) == 0, "教师放行 200", "status=%d %s" % (st, p))
    d = data_of(p) or {}
    h.check(d.get("auditId", 0) > 0 and d.get("unlocked") is True and d.get("levelId") == lv4
            and d.get("studentId") == a02, "回执带 auditId/studentId/levelId 且 unlocked=true", str(d))

    item = teacher_levels(a02)[lv4]
    h.check(item["unlocked"] is True and item["adjusted"] is True and item["cleared"] is False,
            "教师端调关面板：已放行 / adjusted=true / 仍未通关", str(item))
    item = levels_of("S10A02", STU["S10A02"]["token"])[lv4]
    h.check(item["unlocked"] is True and item["adjusted"] is True,
            "学生端地图同一步看到放行（下一次拉地图即生效）", str(item))
    st, p = req("GET", "/quiz/paper?level=%d" % lv4, token=STU["S10A02"]["token"])
    h.check(st == 200 and code_of(p) == 0 and data_of(p)["level"]["id"] == lv4,
            "放行后学生能取到该关真卷（200）", "status=%d" % st)

    h.eq(ledger_total(a02), xp_before, "调关不改成绩：XP 一分未动")

    # ---- 收回：把已经放行的关再关上 ----
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a02, "levelId": lv4, "action": "lock"})
    h.check(st == 200 and code_of(p) == 0 and data_of(p)["unlocked"] is False,
            "教师收回 200 且 unlocked=false", str(data_of(p)))
    item = levels_of("S10A02", STU["S10A02"]["token"])[lv4]
    h.check(item["unlocked"] is False and item["adjusted"] is True,
            "学生端地图看到收回（adjusted 仍为真，方向由 unlocked 表达）", str(item))
    st, p = req("GET", "/quiz/paper?level=%d" % lv4, token=STU["S10A02"]["token"])
    h.eq((st, code_of(p)), (403, 40303), "收回后取卷再次被拒（403/40303）")

    # ---- 反向：把本来自然解锁的关卡锁掉 ----
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a01, "levelId": lv2, "action": "unlock"})
    h.check(st == 200 and data_of(p)["unlocked"] is True, "先把自然解锁的关卡归一为可用（幂等前置）",
            str(data_of(p)))
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a01, "levelId": lv2, "action": "lock"})
    h.check(st == 200 and data_of(p)["unlocked"] is False, "锁掉自然解锁的关卡 200", str(data_of(p)))
    item = levels_of("S10A01", STU["S10A01"]["token"])[lv2]
    h.check(item["unlocked"] is False and item["adjusted"] is True and item["cleared"] is True,
            "已通关的关卡也能被收回（cleared 不变，只是打不开）", str(item))
    st, p = req("GET", "/quiz/paper?level=%d" % lv2, token=STU["S10A01"]["token"])
    h.eq((st, code_of(p)), (403, 40303), "被收回的关卡学生立刻打不了（403/40303）")
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a01, "levelId": lv2, "action": "unlock"})
    h.check(st == 200 and data_of(p)["unlocked"] is True, "再放行回来 200", str(data_of(p)))
    st, p = req("GET", "/quiz/paper?level=%d" % lv2, token=STU["S10A01"]["token"])
    h.check(st == 200, "放行后恢复可取卷（环境复位，学生继续正常玩）", "status=%d" % st)

    # ---- 参数与归属校验 ----
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a02, "levelId": lv4, "action": "ban"})
    h.eq((st, code_of(p)), (400, 40001), "非法 action 被拒（400/40001）")
    st, p = req("POST", "/admin/adjust-level", token=TA, body={"studentId": a02, "action": "unlock"})
    h.eq((st, code_of(p)), (400, 40001), "缺 levelId 被拒（400/40001）")
    st, p = req("POST", "/admin/adjust-level", token=TA, body={"levelId": lv4, "action": "unlock"})
    h.eq((st, code_of(p)), (400, 40001), "缺 studentId 被拒（400/40001）")

    # ---- 复位：第 4 关保持放行，作为"教师提前解锁"的演示样本（前端截图要用） ----
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": a02, "levelId": lv4, "action": "unlock"})
    h.check(st == 200 and data_of(p)["unlocked"] is True, "复位：第 4 关保持放行", "status=%d" % st)
    
# ================================================================ ③ 审计日志

def ensure_coupon():
    """给验收 1 班造一张券（核销留痕要有真实动作可查）。"""
    cid = sql1("select id from coupons where class_id=%d and name='%s'" % (A, COUPON))
    if cid:
        return int(cid)
    sql("insert into coupons (class_id,name,cost_xp,stock,per_user_limit,enabled,created_at) "
        "values (%d,'%s',5,999,999,1,now(3))" % (A, COUPON))
    return int(sql1("select id from coupons where class_id=%d and name='%s'" % (A, COUPON)))


def accept_audit():
    h.section("③ audit_log：调关 / 排行开关 / 兑换核销三类留痕可查")

    # 排行开关：关掉 → 看板 rankPublic 跟着变 → 再开回来。
    st, p = req("POST", "/admin/rank-toggle", token=TA, body={"classId": A, "public": False})
    h.check(st == 200 and code_of(p) == 0 and data_of(p)["rankPublic"] is False,
            "关闭本班公开排名 200", str(data_of(p)))
    st, p = req("GET", "/admin/dashboard?classId=%d" % A, token=TA)
    h.check(data_of(p)["rankPublic"] is False, "看板 rankPublic 同步为 false（教师端开关真的落到设置里）")
    st, p = req("POST", "/admin/rank-toggle", token=TA, body={"classId": A, "public": True})
    h.check(st == 200 and data_of(p)["rankPublic"] is True, "重新打开 200")
    st, p = req("GET", "/admin/dashboard?classId=%d" % A, token=TA)
    h.check(data_of(p)["rankPublic"] is True, "看板 rankPublic 复位为 true")

    # 兑换核销：学生本人换券 → 留痕 actor 是学生。
    cid = ensure_coupon()
    stu = STU["S10A03"]["token"]
    st, p = req("POST", "/shop/redeem", token=stu, body={"couponId": cid})
    h.check(st == 200 and code_of(p) == 0, "学生兑换验收券成功（核销动作发生）", "status=%d %s" % (st, p))
    code = (data_of(p) or {}).get("coupon", {}).get("code", "")
    h.check(len(code) > 0, "兑换回执带券码", code)
    row = sql("select actor,detail from audit_log where action='redeem' order by id desc limit 1")
    h.check(bool(row) and int(row[0][0]) == STU["S10A03"]["id"],
            "库里有 redeem 留痕且 actor=学生本人", str(row[:1]))
    h.check(bool(row) and COUPON in row[0][1], "留痕 detail 带券名（可对账）", row[0][1] if row else "")

    st, p = req("GET", "/admin/audit-logs?pageSize=200", token=TA)
    h.check(st == 200 and code_of(p) == 0, "教师查审计日志 200", "status=%d" % st)
    items = data_of(p)["items"]
    total = data_of(p)["total"]
    h.check(total == len(items) and total >= 4, "本教师留痕条数 ≥4（2 放行/收回 + 2 排行开关）", str(total))
    h.check(all(it["actor"] == TA_ID for it in items), "教师只看到自己做过的动作（actor 隔离）")

    by_action = {}
    for it in items:
        by_action.setdefault(it["action"], []).append(it)
        for k in ("actorName", "actionText", "summary", "detail", "createdAt"):
            if not it.get(k):
                h.check(False, "留痕字段 %s 不许为空" % k, str(it))
                break
    adj = by_action.get("adjust_level", [])
    rank = by_action.get("rank_toggle", [])
    h.check(len(adj) >= 2 and len(rank) >= 2,
            "调关与排行开关都有留痕（%d / %d 条）" % (len(adj), len(rank)))
    adj_text = " | ".join(it["summary"] for it in adj)
    rank_text = " | ".join(it["summary"] for it in rank)
    for want in (STU["S10A02"]["name"], CLS_A["levels"]["3"][1], "放行", "收回"):
        h.check(want in adj_text, "调关摘要含 %r" % want, adj_text)
    h.check(CLS_A["levels"]["2"][1] in adj_text, "调关摘要含被收回的关卡名",
            CLS_A["levels"]["2"][1] + " / " + adj_text)
    h.check("S10验收1班" in rank_text and "已关闭" in rank_text and "已开启" in rank_text,
            "排行开关摘要带班级名且方向正确（先关后开两个方向都在）", rank_text)
    h.check(all(it["actionText"] == "手动调关" for it in adj), "动作有中文名（手动调关）")
    h.check(all(it["actionText"] == "排行开关" for it in rank), "动作有中文名（排行开关）")
    det = json.loads(adj[0]["detail"])
    h.check(det.get("studentId") and det.get("levelId") and det.get("op"),
            "detail 原文可解析出 studentId/levelId/op（对账用）", adj[0]["detail"])

    st, p = req("GET", "/admin/audit-logs?action=adjust_level&pageSize=200", token=TA)
    only = data_of(p)["items"]
    h.check(len(only) == len(adj) and all(it["action"] == "adjust_level" for it in only),
            "按 action 过滤只回调关（%d 条）" % len(only))
    st, p = req("GET", "/admin/audit-logs?page=1&pageSize=2", token=TA)
    pg = data_of(p)
    h.check(pg["total"] == total and len(pg["items"]) == 2, "分页：total 不变、首页 2 条",
            "total=%s/%d" % (pg["total"], len(pg["items"])))

    # actor 隔离 + 校级可见全量。
    st, p = req("GET", "/admin/audit-logs?pageSize=200", token=TB)
    b_total = data_of(p)["total"]
    h.check(all(it["actor"] == TB_ID for it in data_of(p)["items"]),
            "教师 B 的日志里没有教师 A 的动作", "total=%d" % b_total)
    st, p = req("GET", "/admin/audit-logs?pageSize=200", token=AD)
    ad = data_of(p)
    h.check(ad["total"] > total and any(it["action"] == "redeem" for it in ad["items"]),
            "校级（admin）看全量：含学生的兑换核销留痕",
            "admin total=%d vs 教师 %d" % (ad["total"], total))
    h.check(any(it["actionText"] == "兑换核销" for it in ad["items"]), "核销动作有中文名")
    return total


# ============================================== ⑤ 改密后旧 JWT 立刻失效

def accept_jwt():
    h.section("⑤ 改密后旧 JWT 立即失效（自助改密 / 教师重置临时密码）")

    # a) 学生自助改密：改密前签发的 token 立刻 401。
    u = "S10A03"
    st, p = req("POST", "/auth/login", body={"username": u, "password": NEWPWD})
    h.check(st == 200 and code_of(p) == 0, "%s 用现口令登录成功" % u, "status=%d" % st)
    old_token = data_of(p)["token"]
    st, p = req("GET", "/auth/me", token=old_token)
    h.eq((st, code_of(p)), (200, 0), "改密前：旧 token 可用")

    st, p = req("POST", "/auth/chpwd", token=old_token,
                body={"oldPassword": NEWPWD, "newPassword": NEWPWD2})
    h.check(st == 200 and code_of(p) == 0, "自助改密 200", "status=%d %s" % (st, p))
    st, p = req("GET", "/auth/me", token=old_token)
    h.eq((st, code_of(p)), (401, 40101), "改密后：旧 token 打 /auth/me 立刻 401/40101")
    st, p = req("GET", "/quiz/levels", token=old_token)
    h.eq((st, code_of(p)), (401, 40101), "改密后：旧 token 打业务接口也 401（不是只挡 /me）")

    st, p = req("POST", "/auth/login", body={"username": u, "password": NEWPWD2})
    h.check(st == 200 and code_of(p) == 0, "新口令可以登录", "status=%d" % st)
    mid_token = data_of(p)["token"]
    st, p = req("POST", "/auth/chpwd", token=mid_token,
                body={"oldPassword": NEWPWD2, "newPassword": NEWPWD})
    h.check(st == 200, "改回统一口令（环境复位）", "status=%d" % st)
    st, p = req("GET", "/auth/me", token=mid_token)
    h.eq((st, code_of(p)), (401, 40101), "再改一次：上一次改密后的 token 也失效（每次都换签名）")
    st, p = req("POST", "/auth/login", body={"username": u, "password": NEWPWD})
    h.check(st == 200, "复位后统一口令可用", "status=%d" % st)
    ENV["students"][u]["token"] = data_of(p)["token"]

    # b) 教师重置为随机临时密码：旧 token 失效 + 首登必须改密。
    u2 = "S10A11"
    uid2 = STU[u2]["id"]
    st, p = req("GET", "/auth/me", token=STU[u2]["token"])
    h.eq((st, code_of(p)), (200, 0), "改密前：%s 的 token 可用" % u2)
    h.check(me_of(p)["mustChangePwd"] is False, "该生当前不在「首登改密」状态")

    st, p = req("POST", "/admin/users/%d/reset-pwd" % uid2, token=TA)
    h.check(st == 200 and code_of(p) == 0, "教师重置学生密码 200", "status=%d %s" % (st, p))
    temp = data_of(p)["tempPassword"]
    h.check(len(temp) == 8, "回执带 8 位随机临时密码", temp)
    h.check(temp != u2 and not temp.isdigit(), "临时密码不是学号、也不全是数字", temp)

    st, p = req("GET", "/auth/me", token=STU[u2]["token"])
    h.eq((st, code_of(p)), (401, 40101), "重置后：学生手上的旧 token 立刻 401/40101")
    st, p = req("POST", "/auth/login", body={"username": u2, "password": NEWPWD})
    h.eq((st, code_of(p)), (401, 40101), "重置后：老口令登不进去（登录失败也带 40101）")
    st, p = req("POST", "/auth/login", body={"username": u2, "password": temp})
    h.check(st == 200 and code_of(p) == 0, "临时密码可以登录", "status=%d" % st)
    h.check(data_of(p)["mustChangePwd"] is True, "用临时密码登录后被要求先改密（mustChangePwd=true）")
    t_token = data_of(p)["token"]
    st, p = req("GET", "/quiz/levels", token=t_token)
    h.eq((st, code_of(p)), (403, 40302), "未改密前业务接口一律 403/40302")
    st, p = req("POST", "/auth/chpwd", token=t_token,
                body={"oldPassword": temp, "newPassword": NEWPWD})
    h.check(st == 200, "用临时密码完成改密", "status=%d" % st)
    st, p = req("GET", "/quiz/levels", token=t_token)
    h.eq((st, code_of(p)), (401, 40101), "改密后：临时密码签发的 token 失效")
    st, p = req("POST", "/auth/login", body={"username": u2, "password": NEWPWD})
    h.check(st == 200, "复位后统一口令可用", "status=%d" % st)
    ENV["students"][u2]["token"] = data_of(p)["token"]


# ================================================================ ⑥ 越权

def accept_scope():
    h.section("⑥ 越权：跨班读写一律 404，校级视图 403，学生令牌 403")

    a01 = STU["S10A01"]["id"]
    lv1 = CLS_A["levels"]["1"][0]
    cases = [
        ("GET", "/admin/dashboard?classId=%d" % A, None, "看板"),
        ("GET", "/admin/students?classId=%d" % A, None, "学生明细"),
        ("GET", "/admin/students/%d/levels" % a01, None, "某人关卡状态"),
        ("GET", "/admin/export/grade?classId=%d" % A, None, "导出平时成绩"),
        ("POST", "/admin/adjust-level", {"studentId": a01, "levelId": lv1, "action": "unlock"}, "调关"),
        ("POST", "/admin/rank-toggle", {"classId": A, "public": False}, "排行开关"),
        ("GET", "/admin/classes/%d" % A, None, "班级详情"),
        ("PATCH", "/admin/classes/%d" % A, {"name": "越权改名"}, "班级改名"),
        ("GET", "/admin/users/%d" % a01, None, "学生详情"),
        ("PATCH", "/admin/users/%d" % a01, {"realName": "越权改名"}, "学生改名"),
        ("DELETE", "/admin/users/%d" % a01, None, "删学生"),
        ("POST", "/admin/users/%d/reset-pwd" % a01, None, "重置学生密码"),
    ]
    for method, path, body, label in cases:
        st, p = req(method, path, token=TB, body=body)
        h.eq((st, code_of(p)), (404, 40401), "教师B %s → 404/40401（不给「存在但无权」的信号）" % label)

    # 内容列表是另一套口径：它按可见范围过滤，不报 404（列表本来就不该泄露"有没有这个班"）。
    # 别人班的 id 混进来 = 过滤为空；admin 是全量，同一个请求要看得到。
    for path, label in (("/admin/units?classId=%d" % A, "单元"),
                        ("/admin/levels?classId=%d" % A, "关卡"),
                        ("/admin/questions?levelId=%d" % lv1, "题目")):
        st, p = req("GET", path, token=TB)
        h.check(st == 200 and code_of(p) == 0 and len(data_of(p)["items"]) == 0,
                "教师B 查别人班%s列表：200 但过滤为空（不是 404，也不泄露内容）" % label,
                "status=%d items=%s" % (st, len((data_of(p) or {}).get("items", []))))
        st, p = req("GET", path, token=AD)
        h.check(st == 200 and len(data_of(p)["items"]) >= 1,
                "admin 查同一个%s列表：全量可见（校级运维要看得到）" % label,
                "status=%d items=%s" % (st, len((data_of(p) or {}).get("items", []))))

    # 负例防误伤：跨班 404 不能顺手把自己的班也挡了。
    st, p = req("GET", "/admin/dashboard?classId=%d" % B, token=TB)
    h.check(st == 200 and code_of(p) == 0, "教师B 看自己的班 200（没被误伤）", "status=%d" % st)
    st, p = req("GET", "/admin/students?classId=%d" % B, token=TB)
    h.eq((st, code_of(p)), (200, 0), "教师B 查自己班学生明细 200")
    st, p = req("GET", "/admin/classes", token=TB)
    ids = [c["id"] for c in data_of(p)["items"]]
    h.check(A not in ids and A2 not in ids and B in ids,
            "班级列表只含自己名下的班（%s）" % ids, str(ids))
    st, p = req("GET", "/admin/dashboard?classId=%d" % A2, token=TA)
    h.eq((st, code_of(p)), (200, 0), "教师A 的第二个班也能看（多班切换）")

    # 班级/学生仍活着（跨班 DELETE 只该被拦，不该真删）。
    h.eq(sql_int("select count(*) from classes where id=%d" % A), 1, "越权 DELETE 后验收 1 班仍在")
    h.eq(sql_int("select count(*) from users where id=%d" % a01), 1, "越权 DELETE 后学生仍在")

    # 校级视图：admin 200，教师 403（不是 404——它是"没这个视图"，不是"没这个班"）。
    st, p = req("GET", "/admin/school/overview", token=AD)
    h.check(st == 200 and code_of(p) == 0, "校级汇总 admin 200", "status=%d" % st)
    ov = data_of(p)
    h.check(len(ov["items"]) >= 3 and ov["classCount"] == len(ov["items"]),
            "校级汇总含 ≥3 个班（classCount 与行数一致）", str(ov["classCount"]))
    h.check(ov["studentSum"] >= 11, "学生总数 ≥11（跨班聚合）", str(ov["studentSum"]))
    rows = {r["classId"]: r for r in ov["items"]}
    h.check(A in rows and rows[A]["attendRate"] >= 0 and rows[A]["teacherName"] != "",
            "验收 1 班出现在校级汇总里且带任课教师名", str(rows.get(A)))
    st, p = req("GET", "/admin/school/overview", token=TA)
    h.eq((st, code_of(p)), (403, 40301), "任课教师看校级汇总 → 403/40301（admin 专属口子）")

    # 学生令牌打教师接口：403（角色不够），不是 404。
    for path in ("/admin/dashboard", "/admin/students?classId=%d" % A, "/admin/school/overview",
                 "/admin/audit-logs"):
        st, p = req("GET", path, token=STU["S10A01"]["token"])
        h.eq((st, code_of(p)), (403, 40301), "学生令牌打 %s → 403/40301" % path)
    st, p = req("GET", "/admin/dashboard")
    h.eq((st, code_of(p)), (401, 40101), "不带令牌打看板 → 401/40101")

    # 教师 B 也不能靠换 classId 混进校级（它本来就不在教师组里）。
    st, p = req("GET", "/admin/audit-logs", token=TB)
    h.eq((st, code_of(p)), (200, 0), "教师B 能查自己的审计日志（这是教师组的接口）")


# ================================================================ ⑦ D8 双口径

def accept_d8():
    h.section("⑦ D8 双口径：/auth/me 与看板/导出同源于 xp_ledger（users.streak 那列不再被读）")

    st, p = req("GET", "/admin/students?classId=%d" % A, token=TA)
    dash = {x["username"]: x for x in data_of(p)["items"]}
    bad = []
    for u in STU_A:
        uid = STU[u]["id"]
        st, p = req("GET", "/auth/me", token=STU[u]["token"])
        if st != 200:
            bad.append("%s /auth/me=%d" % (u, st))
            continue
        me = me_of(p)
        total = ledger_total(uid)
        want_lv = max(1, 1 + total // 300)
        want_streak = streak_of(uid)
        if me["lv"] != want_lv or me["streak"] != want_streak:
            bad.append("%s /auth/me lv=%r streak=%r 期望 %r/%r"
                       % (u, me["lv"], me["streak"], want_lv, want_streak))
        if dash[u]["lv"] != want_lv or dash[u]["streak"] != want_streak:
            bad.append("%s 看板 lv=%r streak=%r 期望 %r/%r"
                       % (u, dash[u]["lv"], dash[u]["streak"], want_lv, want_streak))
    h.check(not bad, "6 名学生的 lv/streak 三处（账本 / /auth/me / 看板）完全一致", "; ".join(bad[:6]))
    h.check(dash["S10A01"]["lv"] > 1 and dash["S10A05"]["streak"] == 0,
            "等级随账本上涨、零流水学生连课为 0（两个方向都不是常量）",
            "A01 lv=%r / A05 streak=%r" % (dash["S10A01"]["lv"], dash["S10A05"]["streak"]))
    raw = sql("select lv, streak from users where id=%d" % STU["S10A01"]["id"])
    h.check(raw and int(raw[0][0]) == 1 and int(raw[0][1]) == 0,
            "反向证据：users 表的遗留列仍是死的 1/0，但对外口径已经不看它", str(raw))


def first_class_of(teacher_id):
    """该教师名下 id 最小的班 = 看板的默认班（服务端 order id asc 取第一个）。"""
    r = sql("select id from classes where teacher_id=%d order by id asc limit 1" % teacher_id)
    return int(r[0][0]) if r else 0


def accept_cold_start():
    """⑨ 冷启动：新浏览器（localStorage 里没有班级）首屏并发取数必须整体可用。

    这一段是 1440px 走查当场撞出来的真缺陷回归：走查时没预设
    localStorage.cet46_teacher_class，看板 + 明细是并发发的（前端 Promise.all），
    看板对 classId 缺省给了默认班（200），明细却回 400「请指定班级」，
    整页被这一条 400 打成错误态——"教师第一次登录进看板"这个主流程直接不可用
    （走查子代理是补写了 localStorage 才截到图的）。
    修法：读接口统一 defaultClass（缺省 → 该 scope 第一个班，显式 id 照常校验归属），
    写接口保持"必须指名道姓"。这里三处读 + 两处写逐个钉死。
    """
    h.section("⑨ 冷启动：classId 缺省时看板/明细/导出落到同一个班，写接口仍拒绝猜班级")

    # 走查的原始形态：一个 classId 都不带。
    st, p = req("GET", "/admin/dashboard", token=TA)
    h.check(st == 200 and code_of(p) == 0, "教师不带 classId 取看板应 200",
            "status=%d payload=%s" % (st, str(p)[:160]))
    d = data_of(p) or {}
    default_a = first_class_of(TA_ID)
    h.eq(d.get("classId"), default_a, "看板默认落到自己名下 id 最小的班")
    h.check(default_a in (A, A2), "默认班确实是自己名下的班（不是别人的班）",
            "默认 %r，自己名下 %r/%r" % (default_a, A, A2))

    st, p = req("GET", "/admin/students", token=TA)
    h.check(st == 200 and code_of(p) == 0,
            "明细不带 classId 也应 200（缺陷现场：这里回 400 请指定班级，整页被打死）",
            "status=%d payload=%s" % (st, str(p)[:200]))
    items = (data_of(p) or {}).get("items") or []
    h.check(len(items) >= 1, "明细默认班里有学生（不是空壳 200）", "%d 行" % len(items))
    cls_of_rows = []
    if items:
        cls_of_rows = sql("select distinct class_id from users where id in (%s)"
                          % ",".join(str(r["userId"]) for r in items))
    h.check([r[0] for r in cls_of_rows] == [str(default_a)],
            "明细默认班 = 看板默认班（两处并发请求落到同一个班，否则首屏自相矛盾）",
            "明细里的班 %r vs 看板 %r" % (cls_of_rows, default_a))

    st, hdrs, body = req_full("/admin/export/grade", TA)
    h.check(st == 200 and body[:2] == b"PK", "导出不带 classId 也应吐 xlsx",
            "status=%d len=%d" % (st, len(body)))
    ws = openpyxl.load_workbook(io.BytesIO(body))["平时成绩"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    cls_name = sql1("select name from classes where id=%d" % default_a)
    h.check(bool(rows) and all(r[2] == cls_name for r in rows),
            "导出的班级列全是默认班（%s），名单没串到别的班" % cls_name,
            "行数 %d，班级列 %r" % (len(rows), [r[2] for r in rows][:4]))

    # 归属范围不能因为"缺省"就放宽：另一个教师的默认班只能是自己那个班。
    st, p = req("GET", "/admin/dashboard", token=TB)
    d_b = data_of(p) or {}
    h.check(st == 200 and d_b.get("classId") == B,
            "教师 B 的默认班 = 自己名下那个班（缺省不等于全库第一个班）",
            "status=%d classId=%r 期望 %r" % (st, d_b.get("classId"), B))

    # 校级：scope=0 看全量，默认就是全库 id 最小的班。
    st, p = req("GET", "/admin/dashboard", token=AD)
    d_ad = data_of(p) or {}
    global_first = int(sql1("select id from classes order by id asc limit 1"))
    h.check(st == 200 and d_ad.get("classId") == global_first,
            "校级不带 classId 落到全库第一个班",
            "status=%d classId=%r 期望 %r" % (st, d_ad.get("classId"), global_first))

    # 写路径反过来：班级是"改哪个班"，给 0 就是参数错，不能替你猜一个。
    st, p = req("POST", "/admin/rank-toggle", token=TA, body={"public": False})
    h.check((st, code_of(p)) == (400, 40001),
            "写接口（排行开关）不给 classId → 400/40001，不接受猜一个班帮你改",
            "status=%d code=%r" % (st, code_of(p)))
    st, p = req("POST", "/admin/adjust-level", token=TA,
                body={"studentId": STU["S10A01"]["id"], "levelId": 0, "action": "unlock"})
    h.check((st, code_of(p)) == (400, 40001),
            "写接口（调关）关卡 id 给 0 → 400/40001（写路径不猜关卡）",
            "status=%d code=%r" % (st, code_of(p)))


def main():
    say("== S10 验收实跑（活环境 http://127.0.0.1:8080 + MySQL 3307）==")
    baseline = bank_fingerprint()
    accept_baseline(baseline)
    h.check(refresh_tokens() == 0, "开跑前所有角色令牌都是现签的（上一轮的废令牌已被自愈）")
    accept_export()
    accept_adjust()
    accept_audit()
    accept_jwt()
    accept_scope()
    accept_d8()
    accept_cold_start()

    # ⓪ 的 after 半边：跑完一遍验收，别人的题库与表结构必须还是原样。
    h.section("⑧ 收尾复核：跑完之后底账仍然一字未动")
    after = bank_fingerprint()
    h.eq(after, baseline, "表/列/别人题库（单元/关/题/CRC）跑前跑后完全一致")
    h.check(after["crc"] == BANK_CRC_S9, "收尾时别人题库 CRC 仍是 S9 那把尺子的读数",
            "实际 %d" % after["crc"])
    h.check(sql_int("select count(*) from audit_log where action in "
                    "('adjust_level','rank_toggle','redeem')") >= 4,
            "审计三类动作真的落库了（不是只在回执里说成功）")

    with io.open(os.path.join(HERE, "s10-env.json"), "w", encoding="utf-8") as f:
        json.dump(ENV, f, ensure_ascii=False, indent=2)

    total, failed = h.result()
    with io.open(os.path.join(HERE, "99-summary.txt"), "w", encoding="utf-8") as f:
        f.write("%d %d\n" % (total, failed))
    if failed:
        for m in h.msgs:
            say(m)
    return failed


if __name__ == "__main__":
    sys.exit(1 if main() else 0)