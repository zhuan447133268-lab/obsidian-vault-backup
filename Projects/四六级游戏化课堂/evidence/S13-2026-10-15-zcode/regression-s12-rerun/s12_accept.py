"""S12 验收断言：教师输码检索 → 确认/驳回；学生端回显；audit_log 三要素留痕；
外加 S8 遗留两条（赛季自动开新 / 名额名次线文案）的本阶段结论。

跑法：bash run-acceptance.sh（本文件由它调用，环境已在 01 步摆好）
单独跑：S12_BASE=http://127.0.0.1:8080/api python s12_accept.py

口径先写在纸面上（验收就是拿这些数去对拍）：
  · 主验收班每人 1200 XP 起步；双免卡 500 XP/限 1 张、免迟到券 300 XP/限 3 张、库存 10。
  · 驳回 ≠ 撤销兑换：券回券包（status=rejected，学生端「已退回」）但 XP 不退、库存不还。
  · 驳回来的券**还能再核销**（学生下次课再出示）；confirmed 是终态（撤销=退分，属额度政策，S12 不做）。
  · 重复确认/确认后驳回 → 409 + 40904；重复驳回 → 409 + 40905；被拒的动作不写留痕。
  · 名次线：Zone 按**名次号**划区（LeagueZone(rank, n)），并列会把区撑大——
    12 人班两个并列第 5 时，晋级区 6 行而 promoteCount 仍是 roundHalfUp(12×5/12)=5。
"""
import datetime
import io
import json
import os
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s12_lib import (BASE, Fail, Harness, code_of, data_of, fmt, req, rfc, say, sql,  # noqa: E402
                     sql1, sql_int, week_grid)

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "s12-env.json")
SETTLE_EXE = os.environ.get("S12_SETTLE_EXE", "")
BOOT_LOG = os.environ.get("S12_BOOT_LOG", "")
SERVER_DIR = r"D:\claude-work\cet46-game\server"
EPOCH = datetime.date(2026, 1, 5)   # 联赛周序锚（周一）：手算周序要与 quiz.leagueWeekEpoch 同一把尺子
H = Harness("S12")

with io.open(ENV, encoding="utf-8") as f:
    E = json.load(f)
TEA, TEB, ADMIN = E["teacher"], E["otherTeacher"], E["admin"]
CLS = E["classes"]
COUPONS = E["coupons"]
SPEC = E["couponSpec"]
STU = E["students"]
MAIN, NEXT, LEAGUE, SOLO = "S12验收1班", "S12隔壁班", "S12赛季验收班", "S12一人班"
PREFIX = "C46-"


# ---------------------------------------------------------------- 小工具
def exp_days_left(settle_date, now):
    """与 quiz.LeagueDaysLeft 同口径（向上取整；已过则 0）。"""
    at = datetime.datetime.combine(settle_date, datetime.time(23, 0))
    if at <= now:
        return 0
    d = at - now
    return d.days + (1 if d.seconds or d.microseconds else 0)


def round_half_up(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def cur_week_grid():
    return week_grid()


GRID = cur_week_grid()
WEEK_START, WEEK_INDEX, SEASON_BEGIN = GRID["weekStart"], GRID["weekIndex"], GRID["seasonBegin"]
SEASON_END = GRID["seasonEnd"]
PREV_BEGIN = GRID["prevBegin"]
PREV_END = GRID["prevEnd"]                                # 上个赛季最后一天（周日）
PREV_SETTLE = datetime.datetime.combine(PREV_END, datetime.time(23, 0))
WEEK_SETTLE = datetime.datetime.combine(WEEK_START + datetime.timedelta(days=6), datetime.time(23, 0))
NOW = datetime.datetime.now()

# 夹具摆盘用的两个落点必须与 s12_setup.py 一致：从同一份环境文件里读回来对拍。
PLAN = E["leaguePlan"]


def api(method, path, token=None, body=None):
    return req(method, path, token=token, body=body)


def overview(token):
    st, p = api("GET", "/me/overview", token)
    if st != 200 or code_of(p) != 0:
        raise Fail("取 overview 失败: %s %s" % (st, p))
    return data_of(p)


def shop_of(ov, name):
    for it in ov["shop"]["items"]:
        if it["name"] == name:
            return it
    raise Fail("商城没有券种「%s」：%s" % (name, [i["name"] for i in ov["shop"]["items"]]))


def wallet_of(ov, code):
    for it in ov["wallet"]["items"]:
        if it["code"] == code:
            return it
    return None


def redeem(token, coupon_id):
    return api("POST", "/shop/redeem", token, {"couponId": coupon_id})


def lookup_path(code):
    return "/admin/redeems/lookup?code=" + urllib.parse.quote(code)


def lookup(token, code):
    return api("GET", lookup_path(code), token)


def confirm(token, code):
    return api("POST", "/admin/redeems/confirm", token, {"code": code})


def reject(token, code):
    return api("POST", "/admin/redeems/reject", token, {"code": code})


def redeem_row(code):
    rows = sql("select id, coupon_id, user_id, status, coalesce(confirmed_by,0), "
               "coalesce(date_format(confirmed_at,'%%Y-%%m-%%d %%H:%%i:%%s'),'') "
               "from coupon_redeems where code='%s'" % code)
    if not rows:
        return None
    r = rows[0]
    return {"id": int(r[0]), "couponId": int(r[1]), "userId": int(r[2]), "status": r[3],
            "handledBy": int(r[4]), "handledAt": r[5]}


def audit_of(audit_id):
    rows = sql("select id, actor, action, coalesce(date_format(created_at,'%%Y-%%m-%%d %%H:%%i:%%s'),''), "
               "coalesce(detail,'') from audit_log where id=%d" % audit_id)
    if not rows:
        return None
    r = rows[0]
    return {"id": int(r[0]), "actor": int(r[1]), "action": r[2], "createdAt": r[3], "detail": r[4],
            "detailJSON": json.loads(r[4]) if r[4].strip().startswith("{") else {}}


def audits_for(code, actions=("redeem_confirm", "redeem_reject")):
    inlist = ",".join("'%s'" % a for a in actions)
    rows = sql("select id, actor, action from audit_log where action in (%s) and detail like '%%%s%%' "
               "order by id" % (inlist, code))
    return [{"id": int(r[0]), "actor": int(r[1]), "action": r[2]} for r in rows]


def ledger_rows(uid):
    rows = sql("select delta, reason, ref_type, ref_id from xp_ledger where user_id=%d order by id" % uid)
    return [{"delta": int(r[0]), "reason": r[1], "refType": r[2], "refId": int(r[3])} for r in rows]


def balance_of(uid):
    return sql_int("select coalesce(sum(delta),0) from xp_ledger where user_id=%d" % uid)


def stock_of(coupon_id):
    return sql_int("select stock from coupons where id=%d" % coupon_id)


def count_redeems(uid, coupon_id):
    return sql_int("select count(*) from coupon_redeems where user_id=%d and coupon_id=%d"
                   % (uid, coupon_id))


def board(token):
    st, p = api("GET", "/league/board", token)
    if st != 200 or code_of(p) != 0:
        raise Fail("取联赛榜失败: %s %s" % (st, p))
    return data_of(p)


def settle(class_id, at):
    """跑 ops CLI（与 cron 同一条 SettleClass 路径），返回那一个班的结算结果。"""
    if not SETTLE_EXE or not os.path.exists(SETTLE_EXE):
        raise Fail("缺 S12_SETTLE_EXE（league-settle 可执行文件路径）")
    out = subprocess.run([SETTLE_EXE, "-class", str(class_id), "-at", rfc(at), "-json"],
                         capture_output=True, cwd=SERVER_DIR)
    so = out.stdout.decode("utf-8", "replace")
    se = out.stderr.decode("utf-8", "replace")
    if out.returncode != 0:
        raise Fail("league-settle 失败（at=%s）: %s" % (rfc(at), se))
    try:
        return json.loads(so)[0]
    except Exception as exc:  # noqa: BLE001
        raise Fail("league-settle 输出不是 JSON（%s）：stdout=%r stderr=%s" % (exc, so[:400], se[:400]))


def settle_audits(class_id, action, at):
    ts = at.strftime("%Y-%m-%d %H:%M:%S")
    return sql("select id, actor, date_format(created_at,'%%Y-%%m-%%d %%H:%%i:%%s') from audit_log "
               "where action='%s' and detail like '%%\"classId\":%d%%' and created_at='%s'"
               % (action, class_id, ts))


def names(rows):
    return [(r["realName"] if "realName" in r else r.get("name"), r["rank"], r["xp"]) for r in rows]


# ================================================================ ① 全链路 E2E
def sec_e2e():
    H.section("① 全链路 E2E：兑券 → 输码检索（只读）→ 确认核销 → 学生端回显")
    a01 = STU["S12A01"]
    ov = overview(a01["token"])
    H.eq(ov["shop"]["balance"], E["seedXP"]["main"], "A01 起步余额 = 底账 1200 XP（手算起点）")
    H.eq(ov["wallet"]["total"], 0, "A01 起步券包为空")

    it = shop_of(ov, "双免卡")
    H.check(it["costXp"] == 500 and it["perUserLimit"] == 1 and it["owned"] == 0 and it["canRedeem"],
            "商城「双免卡」：500 XP / 限 1 张 / 已兑 0 / 可兑", json.dumps(it, ensure_ascii=False))

    st, p = redeem(a01["token"], COUPONS["双免卡"])
    H.eq((st, code_of(p)), (200, 0), "兑券 POST /shop/redeem 成功")
    d = data_of(p)
    code = d["coupon"]["code"]
    H.check(code.startswith(PREFIX) and len(code) == len(PREFIX) + 8,
            "券码格式 C46- + 8 位（%s）" % code)
    H.eq((d["coupon"]["status"], d["coupon"]["statusText"]), ("pending", "待老师确认"),
         "兑券回执：pending / 待老师确认")
    H.eq((d["balance"], d["stockLeft"], d["owned"]), (700, 2, 1), "兑券后 余额 700 / 库存 2 / 已兑 1")
    row = redeem_row(code)
    H.check(row and row["status"] == "pending" and row["handledBy"] == 0 and row["handledAt"] == "",
            "库里的兑换行是 pending、没人处理过", json.dumps(row, ensure_ascii=False))
    led = ledger_rows(a01["id"])
    H.check(len(led) == 2 and led[-1]["delta"] == -500 and led[-1]["reason"] == "shop_redeem"
            and led[-1]["refType"] == "coupon" and led[-1]["refId"] == row["couponId"],
            "A01 账本 = 底账 1 条 + 兑换 -500 一条（shop_redeem，ref 指向券种）",
            json.dumps(led, ensure_ascii=False))
    H.eq(balance_of(a01["id"]), 700, "账本聚合余额 700（与回执一致）")

    ov2 = overview(a01["token"])
    w = wallet_of(ov2, code)
    H.check(w is not None and w["status"] == "pending" and w["statusText"] == "待老师确认"
            and w["costXp"] == 500 and w["source"] == "商城兑换",
            "学生券包出现这张券：待老师确认 / 500 XP / 商城兑换", json.dumps(w, ensure_ascii=False))

    # 输码检索：与动作接口同一形状，但**只读**
    audits_before = audits_for(code)
    st, p = lookup(TEA["token"], code)
    H.eq((st, code_of(p)), (200, 0), "教师输码检索 200")
    v = data_of(p)
    H.eq((v["status"], v["statusText"]), ("pending", "待老师确认"), "检索回执：pending / 待老师确认")
    H.eq((v["studentName"], v["username"], v["className"]), ("测试S12A一号", "S12A01", MAIN),
         "检索回执带学生与班级身份（同名靠学号认人）")
    H.eq((v["couponName"], v["costXp"], v["source"]), ("双免卡", 500, "商城兑换"), "检索回执带券名/券价/来源")
    H.eq((v["canConfirm"], v["canReject"]), (True, True), "pending 两个动作都可做")
    H.check(v["actionText"] != "", "检索回执给出「该做什么」的一句话：%s" % v["actionText"])
    H.eq((v["auditId"], v["handledBy"], v["handledAt"]), (0, 0, ""), "检索自身不留痕、不带处理人")
    H.eq(v["studentBalance"], 700, "检索回执带学生当前余额（驳回不退分的对账凭据）")
    H.eq(len(audits_for(code)), len(audits_before), "检索是只读：confirm/reject 留痕条数没变")
    H.eq(redeem_row(code)["status"], "pending", "检索是只读：兑换行状态没变")

    st, p = lookup(TEA["token"], "  " + code.lower() + "  ")
    H.check(st == 200 and code_of(p) == 0 and data_of(p)["redeemId"] == v["redeemId"],
            "输码容错：前后空格 + 小写也能查到同一张券（服务端归一化）",
            "status=%s payload=%s" % (st, p))
    st, p = lookup(TEA["token"], "C46-ZZZZZZZZ")
    H.eq((st, code_of(p)), (404, 40401), "没找到的券码 → 404 且不泄露任何信息")
    st, p = lookup(TEA["token"], "   ")
    H.eq((st, code_of(p)), (400, 40001), "空券码 → 400 参数错误")

    # 确认核销
    audits_before = audits_for(code)
    st, p = confirm(TEA["token"], code)
    H.eq((st, code_of(p)), (200, 0), "确认核销 POST /admin/redeems/confirm 成功")
    v2 = data_of(p)
    H.eq((v2["status"], v2["statusText"]), ("confirmed", "已核销"), "回执：confirmed / 已核销")
    H.eq((v2["canConfirm"], v2["canReject"]), (False, False), "已核销后两个按钮都灰")
    H.eq((v2["handledBy"], v2["handlerName"]), (TEA["id"], "S12验收教师"), "回执写「谁处理的」")
    H.check(v2["handledAt"].startswith(datetime.date.today().isoformat()),
            "回执写「什么时候处理的」：%s" % v2["handledAt"])
    H.check(v2["auditId"] > 0, "回执给出本次留痕行号 audit#%s" % v2["auditId"])
    H.eq(v2["studentBalance"], 700, "核销后学生余额仍是 700（核销不动积分）")

    row = redeem_row(code)
    H.check(row["status"] == "confirmed" and row["handledBy"] == TEA["id"] and row["handledAt"] != "",
            "库里的兑换行：confirmed + 处理人 + 处理时间", json.dumps(row, ensure_ascii=False))
    led2 = ledger_rows(a01["id"])
    H.eq((balance_of(a01["id"]), len(led2)), (700, 2), "核销不产生任何积分流水（仍是底账 + 兑换两条）")

    a = audit_of(v2["auditId"])
    H.check(a and a["action"] == "redeem_confirm" and a["actor"] == TEA["id"],
            "留痕三要素①动作=redeem_confirm ②操作人=教师 id", json.dumps(a, ensure_ascii=False))
    H.check(a["createdAt"].startswith(datetime.date.today().isoformat()),
            "留痕三要素③时间=今天：%s" % a["createdAt"])
    dj = a["detailJSON"]
    H.eq((dj.get("op"), dj.get("from"), dj.get("to"), dj.get("code"), dj.get("studentName"),
          dj.get("className")),
         ("confirm", "pending", "confirmed", code, "测试S12A一号", MAIN),
         "留痕 detail：动作方向 + 券码 + 学生身份（含班级，改名转班后还认得出人）")
    H.eq(len(audits_for(code)), len(audits_before) + 1, "这次动作正好多一条留痕（里面含 redeem_confirm）")

    st, p = api("GET", "/admin/audit-logs?action=redeem_confirm&pageSize=50", TEA["token"])
    items = data_of(p)["items"]
    mine = [it for it in items if it["id"] == v2["auditId"]]
    H.check(st == 200 and len(mine) == 1, "教师审计页能按动作筛出这条：action=redeem_confirm")
    if mine:
        m = mine[0]
        H.eq((m["actionText"], m["actorName"]), ("核销确认", "S12验收教师"), "审计页三要素可读：动作文案 + 操作人")
        H.check("核销" in m["summary"] and code in m["summary"],
                "审计摘要说得清「谁核销了哪张券」：%s" % m["summary"])

    ov3 = overview(a01["token"])
    w = wallet_of(ov3, code)
    H.eq((w["status"], w["statusText"]), ("confirmed", "已核销"), "学生券包回显：已核销")
    H.check("积分不退" in ov3["wallet"]["note"], "券包口径句含「积分不退」（S12 新口径）：%s" % ov3["wallet"]["note"])
    it = shop_of(ov3, "双免卡")
    H.eq((it["owned"], it["canRedeem"], it["reject"], it["rejectText"]), (1, False, "limit_exceeded", "已兑 1 张（限 1 张）"),
         "商城：已兑 1 / 不可再兑 / 文案说清是限购")
    H.check("积分不退" in ov3["shop"]["note"] and "占着该券种的限购名额" in ov3["shop"]["note"],
            "商城口径句也同步了 S12 驳回语义：%s" % ov3["shop"]["note"])
    return code


def sec_reject(confirmed_code):
    H.section("② 驳回：券回券包、XP 不退、限购名额不放、还能再出示核销")
    a02 = STU["S12A02"]
    cid = COUPONS["免迟到券"]
    codes = []
    for i in range(3):
        st, p = redeem(a02["token"], cid)
        H.eq((st, code_of(p)), (200, 0), "A02 第 %d 次兑「免迟到券」成功" % (i + 1))
        codes.append(data_of(p)["coupon"]["code"])
    H.eq(balance_of(a02["id"]), 1200 - 900, "兑 3 张后余额 = 1200 − 300×3 = 300")
    H.eq(stock_of(cid), 7, "库存 10 → 7（券价不动库存的不是这里）")

    victim, other, third = codes[0], codes[1], codes[2]
    before_ledger = ledger_rows(a02["id"])
    st, p = reject(TEA["token"], victim)
    H.eq((st, code_of(p)), (200, 0), "驳回 POST /admin/redeems/reject 成功")
    v = data_of(p)
    H.eq((v["status"], v["statusText"]), ("rejected", "已退回"), "回执：rejected / 已退回（不是「作废」）")
    H.eq((v["canConfirm"], v["canReject"]), (True, False), "驳回后仍可确认（学生下次课再出示）、不能再驳回")
    H.eq((v["handledBy"], v["handlerName"]), (TEA["id"], "S12验收教师"), "回执写谁驳回的")
    H.check(v["auditId"] > 0, "驳回也留痕：audit#%s" % v["auditId"])
    H.eq(v["studentBalance"], 300, "驳回回执里的学生余额 = 300（退券不退分的对账凭据）")

    H.eq(balance_of(a02["id"]), 300, "★驳回后 XP 不退：账本聚合仍是 300")
    H.eq(ledger_rows(a02["id"]), before_ledger, "★驳回没有新增/回滚任何积分流水")
    H.eq(stock_of(cid), 7, "★驳回不还库存（券没被重新上架）")
    row = redeem_row(victim)
    H.check(row["status"] == "rejected" and row["handledBy"] == TEA["id"] and row["handledAt"] != "",
            "库里：rejected + 最后处理人/时间（128 列红线内复用 confirmed_by/at）",
            json.dumps(row, ensure_ascii=False))
    a = audit_of(v["auditId"])
    H.check(a["action"] == "redeem_reject" and a["actor"] == TEA["id"]
            and a["createdAt"].startswith(datetime.date.today().isoformat()),
            "驳回留痕三要素：redeem_reject / 教师 id / 今天", json.dumps(a, ensure_ascii=False))
    H.eq((a["detailJSON"].get("op"), a["detailJSON"].get("from"), a["detailJSON"].get("to")),
         ("reject", "pending", "rejected"), "驳回留痕 detail：pending → rejected")

    ov = overview(a02["token"])
    w = wallet_of(ov, victim)
    H.check(w is not None and w["status"] == "rejected" and w["statusText"] == "已退回" and w["costXp"] == 300,
            "★券回学生券包：这张券仍在券包里（已退回 / 300 XP）", json.dumps(w, ensure_ascii=False))
    keys = {"id", "code", "couponId", "name", "status", "statusText", "costXp", "source", "createdAt",
            "justGranted"}
    H.check(set(w.keys()) <= keys, "回显字段没多也没少（对齐 S9 券包结构、零新表）", sorted(w.keys()))
    H.check("积分不退" in ov["wallet"]["note"] and "再向老师出示" in ov["wallet"]["note"],
            "券包口径句说清「积分不退 + 可再出示」：%s" % ov["wallet"]["note"])
    it = shop_of(ov, "免迟到券")
    H.eq((it["owned"], it["canRedeem"], it["reject"]), (3, False, "limit_exceeded"),
         "★驳回仍占限购名额：已兑算 3 张、不可再兑")
    st, p = redeem(a02["token"], cid)
    H.eq((st, code_of(p)), (409, 40903), "第 4 次兑换被拒：409 + 40903 超出每人限购")
    H.eq(count_redeems(a02["id"], cid), 3, "被拒的兑换不落券（仍是 3 张）")
    H.eq(balance_of(a02["id"]), 300, "被拒的兑换不扣分（仍是 300）")

    # 重复驳回（40905）与确认后驳回（40904）
    st, p = reject(TEA["token"], other)
    H.eq((st, code_of(p)), (200, 0), "先正常驳回第二张（pending → rejected）")
    audits_before = audits_for(other)
    st, p = reject(TEA["token"], other)
    H.eq((st, code_of(p)), (409, 40905), "★重复驳回 → 409 + 40905（确定语义，不是 500）")
    H.check("驳回" in p["message"] and "S12验收教师" in p["message"],
            "40905 的话说得清「已经被谁驳回、什么时候」：%s" % p["message"])
    H.eq(len(audits_for(other)), len(audits_before), "被拒的重复动作不写留痕")
    H.eq(redeem_row(other)["status"], "rejected", "被拒的重复动作不改状态")

    # 驳回来的券再出示 → 能核销
    st, p = confirm(TEA["token"], victim)
    H.eq((st, code_of(p)), (200, 0), "★驳回后学生再出示：confirm 成功")
    v3 = data_of(p)
    H.eq((v3["status"], v3["statusText"]), ("confirmed", "已核销"), "再核销后是 confirmed / 已核销")
    a = audit_of(v3["auditId"])
    H.eq((a["action"], a["detailJSON"].get("from"), a["detailJSON"].get("to")),
         ("redeem_confirm", "rejected", "confirmed"), "再核销的留痕记的是 rejected → confirmed（同一张券两次动作两条痕）")
    H.eq(balance_of(a02["id"]), 300, "再核销也不涉及积分（仍是 300）")
    ov = overview(a02["token"])
    H.eq(wallet_of(ov, victim)["statusText"], "已核销", "学生券包回显跟着变：已核销")

    # 终态：重复确认 / 确认后驳回
    audits_before = audits_for(victim)
    st, p = confirm(TEA["token"], victim)
    H.eq((st, code_of(p)), (409, 40904), "★重复确认 → 409 + 40904")
    H.check("核销" in p["message"], "40904 的文案说得清已核销：%s" % p["message"])
    st, p = reject(TEA["token"], victim)
    H.eq((st, code_of(p)), (409, 40904), "★确认后再驳回 → 409 + 40904（confirmed 是终态：驳回≠撤销兑换）")
    H.eq(len(audits_for(victim)), len(audits_before), "两个被拒动作都没写留痕")
    H.eq(redeem_row(victim)["status"], "confirmed", "状态仍是 confirmed（没被改坏）")
    H.eq(redeem_row(confirmed_code)["status"], "confirmed", "①里的那张券不受影响")
    H.eq(redeem_row(third)["status"], "pending", "第 3 张仍是 pending（驳回只动指名的那张）")


def sec_scope():
    H.section("③ 越权与角色：隔壁老师 404（自有码 200 作正向对照）")
    a01 = STU["S12A01"]
    code = sql1("select code from coupon_redeems where user_id=%d order by id limit 1" % a01["id"])
    st, p = lookup(TEB["token"], code)
    H.eq((st, code_of(p)), (404, 40401), "别的老师输我的码检索 → 404（不泄露存在）")
    st, p = confirm(TEB["token"], code)
    H.eq((st, code_of(p)), (404, 40401), "别的老师确认我的码 → 404")
    st, p = reject(TEB["token"], code)
    H.eq((st, code_of(p)), (404, 40401), "别的老师驳回我的码 → 404")
    H.eq(redeem_row(code)["status"], "confirmed", "越权三连之后状态没被改")
    H.eq(len(audits_for(code, ("redeem_confirm", "redeem_reject"))), 1,
         "越权不写留痕（这张券只有①那一条 confirm 痕）")

    # 正向对照：隔壁老师处理自己班的码
    b01 = STU["S12B01"]
    st, p = redeem(b01["token"], COUPONS["隔壁班券"])
    H.eq((st, code_of(p)), (200, 0), "隔壁班学生兑自己班的券成功（越权用例的对照线）")
    bcode = data_of(p)["coupon"]["code"]
    st, p = lookup(TEB["token"], bcode)
    H.check(st == 200 and code_of(p) == 0 and data_of(p)["className"] == NEXT,
            "★隔壁老师查自己班的码 → 200（证明 404 是归属判定，不是接口恒 404）",
            "status=%s payload=%s" % (st, p))
    st, p = confirm(TEB["token"], bcode)
    H.check(st == 200 and data_of(p)["status"] == "confirmed", "★隔壁老师核销自己班的码 → 200 + 已核销")
    H.eq(redeem_row(bcode)["handledBy"], TEB["id"], "留痕/回执里的处理人是隔壁老师")
    H.eq(audit_of(data_of(p)["auditId"])["actor"], TEB["id"], "留痕 actor = 隔壁老师")
    st, p = lookup(TEA["token"], bcode)
    H.eq((st, code_of(p)), (404, 40401), "反向对称：我（不是这个班的老师）查隔壁班的码 → 404")

    st, p = lookup(ADMIN["token"], code)
    H.eq((st, code_of(p)), (200, 0), "校级（scope=0）能跨班检索")
    st, p = api("GET", lookup_path(code))
    H.eq(st, 401, "未登录检索 → 401")
    st, p = api("GET", lookup_path(code), a01["token"])
    H.eq((st, code_of(p)), (403, 40301), "学生 token 调教师接口 → 403")
    st, p = confirm(TEA["token"], "")
    H.eq((st, code_of(p)), (400, 40001), "空券码确认 → 400")
    st, p = confirm(TEA["token"], "C46-ZZZZZZZZ")
    H.eq((st, code_of(p)), (404, 40401), "不存在的券码确认 → 404")
    H.eq(len(audits_for("C46-ZZZZZZZZ")), 0, "不存在的券码不会留下任何留痕")


# ================================================================ ④ S8 遗留①：赛季自动开新
def sec_season():
    H.section("④ S8 遗留①：赛季结算自动开下一赛季（cron 周日 23:00 + 同刻重跑幂等）")
    cid = CLS[LEAGUE]
    say("    周格子：本周一 %s（周序 %d）· 本赛季 %s~%s · 上个赛季 %s~%s"
        % (WEEK_START, WEEK_INDEX, SEASON_BEGIN, SEASON_END, PREV_BEGIN, PREV_END))
    H.eq((PLAN["weekStart"], PLAN["weekIndex"], PLAN["seasonBegin"], PLAN["seasonEnd"]),
         (WEEK_START.isoformat(), WEEK_INDEX, SEASON_BEGIN.isoformat(), SEASON_END.isoformat()),
         "夹具落盘时按同一格子算（两脚本各算一遍，值必须相同）")
    H.eq((PLAN["prevBegin"], PLAN["prevEnd"]), (PREV_BEGIN.isoformat(), PREV_END.isoformat()),
         "上个赛季窗口 = 本赛季往前推两周（2026-09-28~10-11 那一格）")
    H.eq(sql_int("select count(*) from seasons where class_id=%d" % cid), 0,
         "结算前：这个班还没有赛季行（首个赛季在第一次赛季结算时才建）")
    H.eq(json.loads(sql1("select settings_json from classes where id=%d" % cid)),
         {"league_division": "翡翠", "league_season_no": 1, "rank_public": True, "s12_note": "keep-me"},
         "结算前 settings_json 是夹具摆的四个键（含无关键 s12_note）")

    # cron 注册证据：静态常量 + 启动日志里的下一次触发时刻
    if BOOT_LOG and os.path.exists(BOOT_LOG):
        with io.open(BOOT_LOG, encoding="utf-8", errors="replace") as f:
            text = f.read()
        line = [ln for ln in text.splitlines() if "定时任务已启动" in ln and "0 23 * * 0" in ln]
        H.check(len(line) == 1, "服务启动日志里有联赛结算 cron 的注册行", line[:1])
        if line:
            nxt = line[0].split("（下次 ")[-1].rstrip("）").strip()
            dt = datetime.datetime.strptime(nxt, "%Y-%m-%d %H:%M:%S")
            H.check(dt.weekday() == 6 and dt.hour == 23 and dt.minute == 0,
                    "cron 下次触发 = 周日 23:00（%s）" % nxt)
    else:
        say("    （没拿到启动日志快照 S12_BOOT_LOG，跳过 cron 注册行的断言）")

    # 周结算（cron 日常路径）：不建赛季行
    wk = settle(cid, WEEK_SETTLE)
    H.eq(wk["scope"], "week", "周中那次（本周日 23:00 复算）走的是周结算：scope=week")
    H.eq((wk["windowStart"], wk["windowEnd"]), (WEEK_START.isoformat(),
                                               (WEEK_START + datetime.timedelta(days=6)).isoformat()),
         "周结算窗口 = 本周一~本周日")
    H.eq(wk["participants"], 12, "12 人计分")
    H.eq((len(wk["promote"]), len(wk["demote"])), (6, 4), "周榜名单：晋级区 6 行（并列）/ 降级区 4 行")
    H.eq(sql_int("select count(*) from seasons where class_id=%d" % cid), 0,
         "周结算不建赛季行（周榜只是走势快照）")
    H.check(len(settle_audits(cid, "league_settle", WEEK_SETTLE)) == 1,
            "周结算留痕一条（league_settle，created_at = 结算时刻而非跑脚本的时刻）")

    # 赛季结算：归档 + 开新赛季 + 留痕
    se = settle(cid, PREV_SETTLE)
    H.eq(se["scope"], "season", "上个赛季末那次走的是赛季结算：scope=season")
    H.eq((se["windowStart"], se["windowEnd"]), (PREV_BEGIN.isoformat(), PREV_END.isoformat()),
         "赛季窗口 = 上个赛季两周")
    H.eq(se["participants"], 12, "赛季窗口内 12 人计分")
    H.eq(se["closedSeasonId"], 0, "首赛季没有旧行可归档（closedSeasonId=0）")
    H.check(se["nextSeasonId"] > 0, "★自动开出下一赛季（nextSeasonId=%s）" % se["nextSeasonId"])
    H.eq(names(se["promote"]), [("S12榜上01号", 1, 450), ("S12榜上02号", 2, 425), ("S12榜上03号", 3, 400),
                                ("S12榜上04号", 4, 375), ("S12榜上05号", 5, 350), ("S12榜上06号", 5, 350)],
         "★赛季晋级名单 = 手算（两个并列第 5 都进）")
    H.eq(names(se["demote"]), [("S12榜上09号", 9, 275), ("S12榜上10号", 10, 250),
                               ("S12榜上11号", 11, 225), ("S12榜上12号", 12, 200)],
         "★赛季降级名单 = 手算（名次 9~12）")
    H.eq(se["seasonNo"], 2, "回执里的赛季号跟到第 2 赛季")

    rows = sql("select id, name, status, start_week, end_week from seasons where class_id=%d" % cid)
    H.eq(len(rows), 1, "库里正好 1 行赛季（不重复开）")
    r = rows[0]
    H.check(r[1] == "第 2 赛季" and r[2] == "active", "新赛季行：第 2 赛季 / active", rows)
    # 手算：新赛季 = 紧接着的两周（本周一 ~ 下周日）
    idx_begin = (SEASON_BEGIN - EPOCH).days // 7
    idx_end = (SEASON_END - EPOCH).days // 7
    H.eq((int(r[3]), int(r[4])), (idx_begin, idx_end),
         "新赛季的周序 = 手算（%d~%d → %s~%s）" % (idx_begin, idx_end, SEASON_BEGIN, SEASON_END))
    st, p = api("GET", "/league/board", STU["S12L05"]["token"])
    board_season = data_of(p)["season"]
    H.eq((board_season["start"], board_season["end"]), (SEASON_BEGIN.isoformat(), SEASON_END.isoformat()),
         "★学生端看到的新赛季窗口 = 库里那行（不是靠奇偶派生的旧窗口）")
    sj = json.loads(sql1("select settings_json from classes where id=%d" % cid))
    H.check(sj.get("league_season_no") == 2 and sj.get("s12_note") == "keep-me"
            and sj.get("league_division") == "翡翠",
            "★settings_json 只改联赛段、保住无关键：%s" % json.dumps(sj, ensure_ascii=False))
    sa = settle_audits(cid, "league_season_settle", PREV_SETTLE)
    H.eq(len(sa), 1, "赛季结算留痕一条（league_season_settle）")
    if sa:
        H.eq((int(sa[0][1]), sa[0][2]), (0, PREV_SETTLE.strftime("%Y-%m-%d %H:%M:%S")),
             "留痕 actor=0（系统动作）/ created_at = 结算时刻（2026-10-11 23:00 那一格）")

    # 同刻重跑：幂等（不重复开赛季）
    again = settle(cid, PREV_SETTLE)
    H.eq((again["scope"], again["nextSeasonId"]),
         ("week", 0), "★同一时刻重跑：掉回 week 分支、不再开赛季（幂等）")
    H.eq(sql_int("select count(*) from seasons where class_id=%d" % cid), 1, "赛季行仍只有 1 行")
    H.eq(json.loads(sql1("select settings_json from classes where id=%d" % cid))["league_season_no"], 2,
         "赛季号没被重复 +1")

    # 学生端：赛季号 / 剩余天数 / 结算时刻
    st, p = api("GET", "/league/board", STU["S12L05"]["token"])
    bs = data_of(p)["season"]
    H.eq((bs["id"], bs["no"], bs["name"]), (int(r[0]), 2, "第 2 赛季"), "板上赛季 = 第 2 赛季（行生效）")
    H.eq(bs["settleAt"], rfc(datetime.datetime.combine(SEASON_END, datetime.time(23, 0))),
         "板上结算时刻 = 本赛季最后一周周日 23:00")
    H.eq(bs["daysLeft"], exp_days_left(SEASON_END, datetime.datetime.now()),
         "剩余天数 = 手算（向上取整）")
    return board_season


# ================================================================ ⑤ S8 遗留②：名额名次线
def sec_quota():
    H.section("⑤ S8 遗留②：名额是「名次线」不是「人数上限」——手算 roundHalfUp 对拍 + 文案复查")

    # n=12：手算名额
    p12, d12 = round_half_up(12 * 5 / 12), round_half_up(12 * 4 / 12)
    b = board(STU["S12L05"]["token"])
    H.eq((b["classSize"], b["promoteCount"], b["demoteCount"]), (12, p12, d12),
         "n=12：名额 = roundHalfUp(12×5/12)=%d / roundHalfUp(12×4/12)=%d" % (p12, d12))
    H.eq(b["promoteText"], "前 5 名晋级钻石联赛 · 后 4 名降级白银联赛", "★n=12 文案 = 原型那句（与字段同源）")
    H.check("前 5 名" in b["promoteText"] and "名额" not in b["promoteText"],
            "文案用「前 N 名」这条线说话、不说「名额共 N 人」（与名次线口径一致）")
    H.eq(b["participants"], 12, "本周 12 人计分")
    H.eq(b["me"]["rank"], 5, "我（L05）本周第 5 名")
    H.eq(b["me"]["zone"], "promote", "第 5 名在晋级区（名次线：rank ≤ 5）")
    H.eq(b["me"]["promoteCutXp"], 700, "晋级线 = 晋级区里最低的 XP = 700")

    # 手算整榜（12 行：名次/XP/色带）
    hand = {}
    for u, (_past, week) in E["leagueXP"].items():
        hand[u] = week
    xs = sorted(hand.values(), reverse=True)
    want_rows = []
    for u in sorted(hand, key=lambda k: (-hand[k], k)):
        rank = xs.index(hand[u]) + 1
        zone = "promote" if rank <= p12 else ("demote" if rank > 12 - d12 else "keep")
        want_rows.append((u, rank, hand[u], zone))
    got_rows = [(it["realName"], it["rank"], it["xp"], it["zone"]) for it in b["items"]]
    want_named = [(STU[u]["name"], r, x, z) for u, r, x, z in want_rows]
    H.eq(got_rows, want_named, "★整榜 12 行与手算表逐行一致（名次/XP/色带）")
    H.eq((len(b["items"]), b["count"]), (12, 12), "榜 12 行 / 计数 12")
    pro = [it for it in b["items"] if it["zone"] == "promote"]
    dem = [it for it in b["items"] if it["zone"] == "demote"]
    H.eq((len(pro), len(dem)), (6, 4),
         "★晋级区 6 行 > 名额 5（两个并列第 5 都进）：名次线不是人数上限")
    H.eq([it["rank"] for it in pro], [1, 2, 3, 4, 5, 5], "晋级区名次号 = 1,2,3,4,5,5（并列同名次）")
    H.eq([it["rank"] for it in dem], [9, 10, 11, 12], "降级区名次号 = 9,10,11,12（rank > 12−4）")
    H.check(all(it["zone"] == "promote" for it in b["items"] if it["rank"] <= p12),
            "凡 rank ≤ 5 的行都涂晋级色带（并列不会只让一个人进）")

    # n=6：第二个样本
    b6 = board(STU["S12A01"]["token"])
    p6, d6 = round_half_up(6 * 5 / 12), round_half_up(6 * 4 / 12)
    H.eq((b6["classSize"], b6["promoteCount"], b6["demoteCount"]), (6, p6, d6),
         "n=6：名额 = roundHalfUp(6×5/12)=%d / roundHalfUp(6×4/12)=%d" % (p6, d6))
    H.eq(b6["promoteText"], "前 3 名晋级钻石联赛 · 后 2 名降级白银联赛", "n=6 文案跟着名额走（3/2）")

    # n=1：两个名额都是 0 的边界（本轮修的文案）
    b1 = board(STU["S12C01"]["token"])
    H.eq((b1["classSize"], b1["promoteCount"], b1["demoteCount"]), (1, 0, 0), "n=1：两个名额都是 0")
    H.eq(b1["promoteText"], "本班人数不足（不满 2 人），本赛季不设升降级（满 2 人起按 12 人榜的 5/12、4/12 折算名额）",
         "★n=1 文案说「人数不足」（修复前会误报「翡翠是最低赛区，不设降级」）")

    # 前端不重算：文案/名额/色带全部来自服务端字段
    rv = os.path.join(SERVER_DIR, "..", "web", "src", "student", "views", "RankView.vue")
    with io.open(rv, encoding="utf-8") as f:
        src = f.read()
    H.check("promoteText" in src and "promoteCount" not in src,
            "前端只渲染服务端文案（RankView 里没有 promoteCount：名额不由前端算）")
    H.check("5/12" not in src and "4/12" not in src and "Math.round" not in src,
            "前端没有 5/12、4/12、Math.round 这类重算名额的痕迹")
    H.check('row.zone === "promote"' in src or "row.zone === 'promote'" in src,
            "色带按服务端下发的 zone 涂，不在前端按名次算")


# ================================================================ 主流程
def main():
    say("== S12 验收断言开始 ==")
    say("  环境：%s" % E["base"])
    confirmed = sec_e2e()
    sec_reject(confirmed)
    sec_scope()
    sec_season()
    sec_quota()
    total, failed = H.result()
    with io.open(os.path.join(HERE, "99-summary-s12.txt"), "w", encoding="utf-8") as f:
        f.write("%d %d\n" % (total, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        say("\n[FAIL] 环境/前置不满足，验收中断：%s" % e)
        total, failed = H.result()
        with io.open(os.path.join(HERE, "99-summary-s12.txt"), "w", encoding="utf-8") as f:
            f.write("%d %d (中断)\n" % (total, failed))
        sys.exit(2)