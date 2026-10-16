"""S12 验收环境搭建：四个班 / 三名教师 / 二十名学生 / 题库 / 券种 / 联赛底账。

四个班各有分工（每个班都只碰自己的数据）：
  S12验收1班（6 人）  —— 主验收班：学生真兑券（走 POST /api/shop/redeem），教师输码确认/驳回。
                        6 人也是"名额等比折算"的第二个样本（roundHalfUp(6×5/12)=3、×4/12=2）。
  S12隔壁班（1 人）   —— 别的老师名下的班：越权 404 的**正向对照**（隔壁老师看自己的码是 200，
                        看我的码是 404，证明 404 不是"接口恒 404"）。
  S12赛季验收班（12 人）—— S8 遗留①赛季自动开新 + 遗留②名次线手算（原型 12 人榜 → 5/4）。
                        每人两条首刷：L1 摆在**上个赛季窗口内**（赛季结算名单用它），
                        L2 摆在**本周窗口内**（周榜/名次线用它）。两窗口的 XP 都是手算过的。
  S12一人班（1 人）   —— n≤1 的边界：两个名额都是 0，文案必须说"人数不足"而不是"最低赛区"
                        （S12 复查 S8 遗留②时修的那句）。

为什么直接写 attempts + xp_ledger 而不走"打关"链路：要把分摆在**上个赛季**（2026-09-28~10-11）、
以及要让 12 个人的名次正好落在手算的那张表上，接口没法回填 finished_at、也造不出并列第 5。
主验收班的 1200 XP 同理（券价 300/500 是手算的起点），兑换之后的每一步都走真实接口。

产物 s12-env.json（账号 / 班级 / 券 / token / 学生 id / 手算表），验收脚本读它。
可反复跑：每次先把上一轮自己的四个班连同其数据清干净再重建（先清后算）。
"""
import datetime
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s12_lib import (Fail, NEWPWD, code_of, data_of, fmt, login, multipart, rfc, say, sql,  # noqa: E402
                     sql1, sql_int, week_grid)
import s12_bank  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "s12-env.json")

ADMIN = ("A1201", "校级教务S12")
TEA = ("T1201", "S12验收教师")
TEB = ("T1202", "S12无关教师")      # 名下有 S12隔壁班：越权用例的正向对照
INIT = "Init@2026"

CLASS_MAIN = "S12验收1班"
CLASS_NEXT = "S12隔壁班"
CLASS_LEAGUE = "S12赛季验收班"
CLASS_SOLO = "S12一人班"

STUDENTS = {
    CLASS_MAIN: [("S12A01", "测试S12A一号"), ("S12A02", "测试S12A二号"), ("S12A03", "测试S12A三号"),
                 ("S12A04", "测试S12A四号"), ("S12A05", "测试S12A五号"), ("S12A06", "测试S12A六号")],
    CLASS_NEXT: [("S12B01", "隔壁班学生")],
    CLASS_LEAGUE: [("S12L%02d" % i, "S12榜上%02d号" % i) for i in range(1, 13)],
    CLASS_SOLO: [("S12C01", "独苗同学")],
}
CLASS_OWNER = {CLASS_MAIN: TEA, CLASS_NEXT: TEB, CLASS_LEAGUE: TEA, CLASS_SOLO: TEA}

# 券种：(班级, 券名, 券价, 库存, 每人限兑)
COUPONS = [
    (CLASS_MAIN, "免迟到券", 300, 10, 3),
    (CLASS_MAIN, "双免卡", 500, 3, 1),
    (CLASS_NEXT, "隔壁班券", 200, 2, 1),
]

# 主验收班的起步积分（手算起点）：1200 XP 够买 1 张双免卡（500）或 4 张免迟到券（300×4）
SEED_XP_MAIN = 1200
# 隔壁班：600 XP 够买 1 张隔壁班券（200）
SEED_XP_NEXT = 600

# 联赛班手算表：学生 →（上个赛季窗口内的 XP，本周窗口内的 XP）
# 两列都是"两条并列第 5"的结构：名次 1,2,3,4,5,5,7,8,9,10,11,12
# → 晋级区（rank≤roundHalfUp(12×5/12)=5）有 6 行、降级区（rank>12−roundHalfUp(12×4/12)=8）有 4 行。
LEAGUE_XP = {
    "S12L01": (450, 900), "S12L02": (425, 850), "S12L03": (400, 800), "S12L04": (375, 750),
    "S12L05": (350, 700), "S12L06": (350, 700), "S12L07": (325, 650), "S12L08": (300, 600),
    "S12L09": (275, 550), "S12L10": (250, 500), "S12L11": (225, 450), "S12L12": (200, 400),
}
# 上个赛季窗口内的首刷落点；本周窗口内的首刷落点 —— 都相对"今天"算，脚本换周跑也成立。
# 本周那条要落在 [本周一 00:00, 现在) 里（联赛窗口右端是 now），所以取 max(周一 01:00, now−3h)。
GRID = week_grid()
PAST_SEASON_AT = fmt(datetime.datetime.combine(GRID["prevBegin"] + datetime.timedelta(days=9),
                                               datetime.time(20, 0)))
CUR_WEEK_AT = fmt(max(datetime.datetime.combine(GRID["weekStart"], datetime.time(1, 0)),
                      datetime.datetime.now() - datetime.timedelta(hours=3)))
# 两个结算复算时刻：上个赛季末（周日 23:00）与本周日 23:00
PAST_SEASON_SETTLE = rfc(datetime.datetime.combine(GRID["prevEnd"], datetime.time(23, 0)))
WEEK_SETTLE = rfc(datetime.datetime.combine(GRID["weekStart"] + datetime.timedelta(days=6),
                                            datetime.time(23, 0)))

SERVER_DIR = r"D:\claude-work\cet46-game\server"   # 原生 python 不认 MSYS 的 /d/... 路径
SEED_EXE = os.environ.get("S12_SEED_EXE", "")


def sh(args):
    out = subprocess.run(args, capture_output=True, cwd=SERVER_DIR)
    text = out.stdout.decode("utf-8", "replace") + out.stderr.decode("utf-8", "replace")
    if out.returncode != 0:
        raise Fail("命令失败 %s\n%s" % (" ".join(args), text))
    return text


def class_id(name):
    return sql_int("select id from classes where name='%s' order by id desc limit 1" % name)


def clean_previous():
    """先清后算：把上一轮自己的四个班连同它们的整条数据链删掉（别人的班一律不碰）。

    audit_log 不删（只增不删是纪律）：留下的旧留痕按 actor/券码过滤，不会污染本轮断言。
    """
    for name in (CLASS_MAIN, CLASS_NEXT, CLASS_LEAGUE, CLASS_SOLO):
        cid = class_id(name)
        if cid == 0:
            continue
        uids = [r[0] for r in sql("select id from users where class_id=%d" % cid)]
        coupon_ids = [r[0] for r in sql("select id from coupons where class_id=%d" % cid)]
        if coupon_ids:
            sql("delete from coupon_redeems where coupon_id in (%s)" % ",".join(coupon_ids))
            sql("delete from coupons where id in (%s)" % ",".join(coupon_ids))
        if uids:
            inlist = ",".join(uids)
            sql("delete from xp_ledger where user_id in (%s)" % inlist)
            sql("delete aa from attempt_answers aa join attempts a on a.id=aa.attempt_id "
                "where a.user_id in (%s)" % inlist)
            sql("delete from attempts where user_id in (%s)" % inlist)
            sql("delete from wrong_book where user_id in (%s)" % inlist)
            sql("delete from users where id in (%s)" % inlist)
        unit_ids = [r[0] for r in sql("select id from units where class_id=%d" % cid)]
        if unit_ids:
            inlist = ",".join(unit_ids)
            lvids = [r[0] for r in sql("select id from levels where unit_id in (%s)" % inlist)]
            if lvids:
                sql("delete from questions where level_id in (%s)" % ",".join(lvids))
                sql("delete from levels where id in (%s)" % ",".join(lvids))
            sql("delete from units where id in (%s)" % inlist)
        sql("delete from seasons where class_id=%d" % cid)
        sql("delete from classes where id=%d" % cid)
        say("  清掉上一轮的 %s（id=%d）与其 %d 名学生、%d 个券种、%d 个单元"
            % (name, cid, len(uids), len(coupon_ids), len(unit_ids)))


def seed_accounts():
    for (u, name), role in ((ADMIN, "admin"), (TEA, "teacher"), (TEB, "teacher")):
        if sql_int("select count(*) from users where username='%s'" % u) == 0:
            if not SEED_EXE:
                raise Fail("缺 S12_SEED_EXE（seed-teacher 可执行文件路径）")
            sh([SEED_EXE, "-username", u, "-name", name, "-password", INIT, "-role", role])
        say("  账号 %s(%s) role=%s 就绪" % (u, name, role))


def import_roster(token, class_name):
    """导入名单（班级不存在就建；teacher_id 为空则归到导入者名下）。"""
    path = os.path.join(HERE, "_roster_%s.csv" % class_name)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("班级,学号,姓名,初始密码\r\n")
        for u, n in STUDENTS[class_name]:
            f.write("%s,%s,%s,%s\r\n" % (class_name, u, n, INIT))
    st, p = multipart("/admin/import-users", token, path)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入名单失败（%s）: %s" % (class_name, p))
    d = data_of(p)
    os.remove(path)
    say("  %s：新建 %s / 更新 %s（%s）" % (class_name, d.get("created"), d.get("updated"),
                                          d.get("className")))


def import_bank(token, class_name):
    path = os.path.join(HERE, "_bank_%s.xlsx" % class_name)
    s12_bank.main(path, class_name)
    st, p = multipart("/admin/import-questions", token, path)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入题库失败（%s）: %s" % (class_name, p))
    d = data_of(p)
    os.remove(path)
    say("  题库：单元 %s / 关 %s / 题 %s（共 %s 行）" % (d.get("unitCreated"), d.get("levelCreated"),
                                                    d.get("created"), d.get("total")))


def create_coupons():
    """直接落券种（券种表没有写接口，教师端配置券走的是 S9 的 cmd/shop-seed）。"""
    out = {}
    for cls, name, cost, stock, limit in COUPONS:
        cid = class_id(cls)
        sql("insert into coupons (class_id, name, cost_xp, stock, per_user_limit, enabled, created_at) "
            "values (%d, '%s', %d, %d, %d, 1, NOW(3))" % (cid, name, cost, stock, limit))
        out[name] = sql_int("select id from coupons where class_id=%d and name='%s' "
                            "order by id desc limit 1" % (cid, name))
        say("  券种「%s」→ %s：%d XP / 库存 %d / 限兑 %d 张（id=%d）"
            % (cls, name, cost, stock, limit, out[name]))
    return out


def seed_attempt_with_xp(uid, level_id, xp, finished_at, who):
    """直写一行「已交卷」底账：attempts（finished）+ xp_ledger（ref_type=attempt）。

    联赛榜/结算都按「每关第一条 finished attempt 的账本净得」取数，所以这一对行
    必须同时落库、ref_id 必须指向那条 attempt——这就是 firstClearRows 的取数口径。
    """
    sql("insert into attempts (user_id, level_id, unit_id, correct, total, stars, score710, "
        "xp_earned, shuffle_seed, status, started_at, finished_at) values "
        "(%d, %d, (select unit_id from levels where id=%d), 2, 2, 3, 710, %d, 0, 'finished', '%s', '%s')"
        % (uid, level_id, level_id, xp, finished_at, finished_at))
    aid = sql_int("select id from attempts where user_id=%d and level_id=%d order by id desc limit 1"
                  % (uid, level_id))
    sql("insert into xp_ledger (user_id, delta, reason, ref_type, ref_id, created_at) "
        "values (%d, %d, 'level_clear', 'attempt', %d, '%s')" % (uid, xp, aid, finished_at))
    say("    %s → L%d 首刷 %d XP @ %s（attempt#%d）" % (who, level_id, xp, finished_at, aid))


def levels_of(cid):
    rows = sql("select l.seq, l.id, l.name from levels l join units u on u.id=l.unit_id "
               "where u.class_id=%d order by l.seq" % cid)
    return {int(seq): {"id": int(lid), "seq": int(seq), "name": name} for seq, lid, name in rows}


def main():
    say("== S12 验收环境搭建 ==")
    seed_accounts()
    tea_token = login(TEA[0], INIT, must_change=True)
    say("  教师 %s 登录成功（首登已改密 → %s）" % (TEA[0], NEWPWD))
    teb_token = login(TEB[0], INIT, must_change=True)
    admin_token = login(ADMIN[0], INIT, must_change=True)
    say("  隔壁教师 %s / 校级 %s 登录成功" % (TEB[0], ADMIN[0]))

    clean_previous()

    say("-- 班级与名单（四个班，各归各的老师）--")
    for name in (CLASS_MAIN, CLASS_LEAGUE, CLASS_SOLO):
        import_roster(tea_token, name)
    import_roster(teb_token, CLASS_NEXT)
    classes = {name: class_id(name) for name in (CLASS_MAIN, CLASS_NEXT, CLASS_LEAGUE, CLASS_SOLO)}
    for name, cid in classes.items():
        owner = sql1("select coalesce(teacher_id, 0) from classes where id=%d" % cid)
        say("  %s id=%d teacher_id=%s" % (name, cid, owner))

    say("-- 题库（四个班各一套 3 关 6 题；隔壁班的题库归隔壁老师）--")
    for name in (CLASS_MAIN, CLASS_LEAGUE, CLASS_SOLO):
        import_bank(tea_token, name)
    import_bank(teb_token, CLASS_NEXT)

    say("-- 券种 --")
    coupons = create_coupons()

    say("-- 联赛班设置（额外键 s12_note 用来验结算只改联赛段、不覆盖别人）--")
    settings = json.dumps({"league_division": "翡翠", "league_season_no": 1,
                           "rank_public": True, "s12_note": "keep-me"}, ensure_ascii=False)
    sql("update classes set settings_json='%s' where id=%d" % (settings, classes[CLASS_LEAGUE]))
    say("  %s.settings_json = %s" % (CLASS_LEAGUE, settings))

    say("-- 学生首登改密（%d 人）--" % sum(len(v) for v in STUDENTS.values()))
    stu_tokens = {}
    for name, rows in STUDENTS.items():
        for u, _n in rows:
            stu_tokens[u] = login(u, INIT, must_change=True)
    say("  %d 名学生完成首登改密" % len(stu_tokens))

    say("-- 主验收班：每人 %d XP 底账（兑券的手算起点）--" % SEED_XP_MAIN)
    lv = levels_of(classes[CLASS_MAIN])
    for u, _n in STUDENTS[CLASS_MAIN]:
        uid = sql_int("select id from users where username='%s'" % u)
        seed_attempt_with_xp(uid, lv[3]["id"], SEED_XP_MAIN, CUR_WEEK_AT, u)

    say("-- 隔壁班：600 XP 底账（隔壁老师那条正向对照的兑券起点）--")
    lv_next = levels_of(classes[CLASS_NEXT])
    for u, _n in STUDENTS[CLASS_NEXT]:
        uid = sql_int("select id from users where username='%s'" % u)
        seed_attempt_with_xp(uid, lv_next[3]["id"], SEED_XP_NEXT, CUR_WEEK_AT, u)

    say("-- 联赛班：12 人 × 两条首刷（上个赛季窗口 / 本周窗口）--")
    lv_league = levels_of(classes[CLASS_LEAGUE])
    for u, _n in STUDENTS[CLASS_LEAGUE]:
        past, week = LEAGUE_XP[u]
        uid = sql_int("select id from users where username='%s'" % u)
        seed_attempt_with_xp(uid, lv_league[1]["id"], past, PAST_SEASON_AT, "%s（上赛季）" % u)
        seed_attempt_with_xp(uid, lv_league[2]["id"], week, CUR_WEEK_AT, "%s（本周）" % u)

    env = {
        "base": "http://127.0.0.1:8080/api",
        "teacher": {"username": TEA[0], "name": TEA[1],
                    "id": sql_int("select id from users where username='%s'" % TEA[0]), "token": tea_token},
        "otherTeacher": {"username": TEB[0], "name": TEB[1],
                         "id": sql_int("select id from users where username='%s'" % TEB[0]),
                         "token": teb_token},
        "admin": {"username": ADMIN[0], "token": admin_token},
        "classes": classes,
        "classOwner": {k: v[0] for k, v in CLASS_OWNER.items()},
        "coupons": coupons,            # 券名 → 券种 id
        "couponSpec": {c[1]: {"class": c[0], "cost": c[2], "stock": c[3], "limit": c[4]} for c in COUPONS},
        "levels": {str(k): v for k, v in lv_league.items()},
        "leagueXP": LEAGUE_XP,
        "leaguePlan": {
            "weekStart": GRID["weekStart"].isoformat(), "weekIndex": GRID["weekIndex"],
            "seasonBegin": GRID["seasonBegin"].isoformat(), "seasonEnd": GRID["seasonEnd"].isoformat(),
            "prevBegin": GRID["prevBegin"].isoformat(), "prevEnd": GRID["prevEnd"].isoformat(),
            "seedPastAt": PAST_SEASON_AT, "seedWeekAt": CUR_WEEK_AT,
            "pastSeasonSettle": PAST_SEASON_SETTLE, "weekSettle": WEEK_SETTLE,
        },
        "students": {u: {"name": n, "id": sql_int("select id from users where username='%s'" % u),
                         "token": stu_tokens[u], "class": name}
                     for name, rows in STUDENTS.items() for u, n in rows},
        "seedXP": {"main": SEED_XP_MAIN, "next": SEED_XP_NEXT},
        "passwd": {"init": INIT, "now": NEWPWD},
    }
    with io.open(ENV, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    say("\n环境就绪 → %s" % ENV)
    for name, cid in classes.items():
        say("  %s（id=%d）：学生 %d 人" % (name, cid, len(STUDENTS[name])))
    return env


if __name__ == "__main__":
    main()