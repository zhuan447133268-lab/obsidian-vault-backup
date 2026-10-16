"""S10.5 验收（教师组卷：选题 → 组卷 → 发布 → 学生端可见可打）。

对着真实环境跑：MySQL 3307 + Go :8080 + 已 seed 的验收班（s105-env.json）。
四块验收 + 边界/越权/公共题库权限，全部走真 HTTP 与真 DB，不做假绿。

用法：python s105_accept.py   （在 evidence/S10.5-2026-10-13-zcode 目录下）
输出末尾写 99-summary.txt（`<断言数> <失败数>`），与 S8/S9/S10 同构。
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s105_lib import Fail, Harness, code_of, data_of, login, multipart, req, say, sql, sql1, sql_int

ENV = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s105-env.json"),
                     encoding="utf-8"))
H = Harness("S10.5")
PAPER_WEEK_BASE = 100
TITLE1 = "26年6月真题第1次练习"
TITLE2 = "到期验收·第2次练习"
TITLE3 = "26年6月真题第1次练习（班间PK版）"


# ---------------------------------------------------------------- 小工具

def iso_after(sec):
    """当前时间 + sec 秒的 RFC3339（带本地时区偏移，服务端 time.Parse(time.RFC3339) 吃这个）。"""
    t = datetime.now().astimezone() + timedelta(seconds=sec)
    return t.isoformat(timespec="seconds")


def collapse(s):
    return " ".join((s or "").split())


def levels_of(token):
    st, p = req("GET", "/quiz/levels", token)
    if st != 200 or code_of(p) != 0:
        raise Fail("取地图失败: %s %s" % (st, p))
    return data_of(p)


def unit_levels(token, unit_id):
    d = levels_of(token)
    return [x for x in d["items"] if x["unitId"] == unit_id]


def unit_summary(token, unit_id):
    d = levels_of(token)
    for u in d["units"]:
        if u["unitId"] == unit_id:
            return u
    return None


def league(token):
    st, p = req("GET", "/league/me", token)
    if st != 200 or code_of(p) != 0:
        raise Fail("取联赛明细失败: %s %s" % (st, p))
    return data_of(p)


def token_of(username, init=None):
    """登录拿 token；首登改密时先走一遍改密（与 setup 同口径）。

    must_change 传 True：账号要是还挂着初始口令，登录接口会让我们改，改完再登一次——
    否则后续教师接口会被 mustChangePwdGate 拦成 40302（setup 之前踩过）。
    """
    tok, user, _ = login(username, init or ENV["passwd"]["init"], must_change=True)
    return tok


def correct_pick(qid, options):
    """按题目在库里的正确项文本，回推它在展示序里的坐标。

    answer_idx 在库里两种写法都出现过：导入的题库写数字下标（'0'），
    手工在内容维护口建的题写选项字母（'A'）——两种都要认。
    """
    row = sql("select answer_idx, options_json from questions where id=%d" % qid)
    if not row:
        raise Fail("题目 %d 不存在" % qid)
    raw, opts_json = row[0][0].strip(), row[0][1]
    opts = json.loads(opts_json)
    idx = int(raw) if raw.isdigit() else ord(raw[0].upper()) - 65
    if idx < 0 or idx >= len(opts):
        raise Fail("题目 %d 的 answer_idx=%r 对不上选项" % (qid, raw))
    text = opts[idx]
    if text not in options:
        raise Fail("题目 %d 正确项文本 %r 不在展示选项里 %r" % (qid, text, options))
    return str(options.index(text))


def wrong_pick(qid, options):
    good = correct_pick(qid, options)
    n = len(options)
    for i in range(n):
        if str(i) != good:
            return str(i)
    raise Fail("题目 %d 没有可选的错误项" % qid)


def take_paper(token, level_id):
    st, p = req("GET", "/quiz/paper?level=%d" % level_id, token)
    return st, p, data_of(p)


def play(token, level_id, correct_n, pattern=None):
    """取卷 → 交卷（一次整关交）。pattern 给每题的期望对错，缺省前 correct_n 题对。

    返回 (提交 status, payload, 取卷 data)。取卷失败时 payload 是错误体、data=None。
    """
    st, p, d = take_paper(token, level_id)
    if st != 200 or code_of(p) != 0:
        return st, p, None
    qs = d["questions"]
    flags = pattern if pattern is not None else [i < correct_n for i in range(len(qs))]
    answers = []
    for q, want in zip(qs, flags):
        pick = correct_pick(q["id"], q["options"]) if want else wrong_pick(q["id"], q["options"])
        answers.append({"questionId": q["id"], "pickedIdx": pick, "elapsedMs": 2500})
    st2, p2 = req("POST", "/quiz/submit", token,
                  {"attemptId": d["attemptId"], "answers": answers})
    return st2, p2, d


def local_fp(unit_id):
    """本地复算套题内容指纹（与 server LeaguePaperFingerprint 同规格：排序后 md5）。"""
    rows = sql(
        "select l.seq, q.type, "
        "replace(replace(replace(q.stem,char(9),' '),char(10),' '),char(13),' '), "
        "replace(replace(replace(q.options_json,char(9),' '),char(10),' '),char(13),' '), "
        "replace(replace(replace(q.answer_idx,char(9),' '),char(10),' '),char(13),' ') "
        "from units u join levels l on l.unit_id=u.id join questions q on q.level_id=l.id "
        "where u.id=%d order by l.seq asc, l.id asc, q.id asc" % unit_id)
    lines = ["\x1f".join([r[0], collapse(r[1]), collapse(r[2]), collapse(r[3]), collapse(r[4])])
             for r in rows]
    return hashlib.md5("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def unit_question_ids(unit_id):
    rows = sql("select q.id from units u join levels l on l.unit_id=u.id "
               "join questions q on q.level_id=l.id where u.id=%d order by q.id" % unit_id)
    return [int(r[0]) for r in rows]


def attempt_state(unit_id, user_id):
    rows = sql("select id, status from attempts where unit_id=%d and user_id=%d "
               "order by id asc" % (unit_id, user_id))
    return [(int(r[0]), r[1]) for r in rows]


def paper_metas():
    """所有班的 papers 元数据：{unit_id: (class_id, status)}。"""
    out = {}
    for cid, sj in sql("select id, coalesce(nullif(settings_json,''),'{}') from classes"):
        try:
            obj = json.loads(sj)
        except Exception:
            continue
        for k, m in (obj.get("papers") or {}).items():
            out[int(k)] = (int(cid), (m or {}).get("status"))
    return out


def shared_marks():
    """所有班的 bank_units 分享标记：{unit_id: [class_id, ...]}。"""
    out = {}
    for cid, sj in sql("select id, coalesce(nullif(settings_json,''),'{}') from classes"):
        try:
            obj = json.loads(sj)
        except Exception:
            continue
        for uid in (obj.get("bank_units") or []):
            out.setdefault(int(uid), []).append(int(cid))
    return out


def schema_counts():
    tables = sql_int("select count(*) from information_schema.tables where table_schema='cet46'")
    cols = sql_int("select count(*) from information_schema.columns where table_schema='cet46'")
    return tables, cols


def reset_papers():
    """清掉上一轮验收留下的卷（保留带单元 + 作答 + 账本 + 元数据 + 分享标记）。

    为什么要清：验收脚本要能反复跑，上一轮的卷会把「私有单元候选几个」「尝试留几条」
    这类计数带偏；留库留的是这一轮的结果。只动 week_no>=100 的卷，教学单元一根汗毛都不碰。
    """
    units = [int(r[0]) for r in sql("select id from units where week_no >= %d" % PAPER_WEEK_BASE)]
    if not units:
        return 0
    ids = ",".join(str(u) for u in units)
    att = [int(r[0]) for r in sql("select id from attempts where unit_id in (%s)" % ids)]
    if att:
        sql("delete from xp_ledger where ref_type='attempt' and ref_id in (%s)"
            % ",".join(str(a) for a in att))
        sql("delete from attempts where unit_id in (%s)" % ids)
    sql("delete q from questions q join levels l on l.id=q.level_id where l.unit_id in (%s)" % ids)
    sql("delete from levels where unit_id in (%s)" % ids)
    sql("delete from units where id in (%s)" % ids)
    gone = set(units)
    for cid, sj in sql("select id, coalesce(nullif(settings_json,''),'{}') from classes"):
        try:
            obj = json.loads(sj)
        except Exception:
            continue
        papers = obj.get("papers") or {}
        banks = obj.get("bank_units") or []
        keep = {k: v for k, v in papers.items() if int(k) not in gone}
        keepb = [x for x in banks if int(x) not in gone]
        if keep != papers or keepb != banks:
            obj["papers"], obj["bank_units"] = keep, keepb
            clean = json.dumps(obj, ensure_ascii=False).replace("'", "''")
            sql("update classes set settings_json='%s' where id=%d" % (clean, int(cid)))
    return len(units)


def compose(tok, class_id, title, question_ids=None, source_unit=None,
            mode=None, tlm=10):
    body = {"classId": class_id, "title": title}
    if question_ids is not None:
        body["questionIds"] = question_ids
    if source_unit is not None:
        body["sourceUnitId"] = source_unit
    if mode is not None:
        body["mode"] = mode
    if tlm is not None:
        body["timeLimitMin"] = tlm
    st, p = req("POST", "/admin/papers", tok, body)
    return st, p, data_of(p)


def publish(tok, class_id, unit_id, class_ids, mode=None, due=None, share=False, title=None):
    body = {"classIds": class_ids}
    if mode is not None:
        body["mode"] = mode
    if due is not None:
        body["dueAt"] = due
    if share:
        body["shareToBank"] = True
    if title is not None:
        body["title"] = title
    st, p = req("POST", "/admin/papers/%d/publish?classId=%d" % (unit_id, class_id), tok, body)
    return st, p, data_of(p)


def bank_questions(tok, source=None, class_id=None, page_size=50):
    q = "/admin/bank/questions?pageSize=%d" % page_size
    if source:
        q += "&source=" + source
    if class_id:
        q += "&classId=%d" % class_id
    st, p = req("GET", q, tok)
    return st, p, data_of(p)


def bank_units(tok, source=None, class_id=None):
    q = "/admin/bank/units"
    parts = []
    if source:
        parts.append("source=" + source)
    if class_id:
        parts.append("classId=%d" % class_id)
    if parts:
        q += "?" + "&".join(parts)
    st, p = req("GET", q, tok)
    return st, p, data_of(p)


def no_answer_leak(payload):
    """题面/池子响应里不许出现答案与解析字段（键级判定，不看文本）。"""
    def keys_of(o, acc):
        if isinstance(o, dict):
            for k, v in o.items():
                acc.add(k)
                keys_of(v, acc)
        elif isinstance(o, list):
            for v in o:
                keys_of(v, acc)
        return acc
    keys = keys_of(payload, set())
    return not ({"answerIdx", "answer_idx", "exp", "script", "correctIdx"} & keys)


# ---------------------------------------------------------------- ⓪ 基线

def section_baseline(ctx):
    H.section("⓪ 基线：结构红线 + 无野卷 + 学生 token 越权")
    tables, cols = schema_counts()
    H.eq(tables, 17, "表数仍是 17（零改表方案）")
    H.eq(cols, 128, "列数仍是 128（零改表方案）")

    metas, marks = paper_metas(), shared_marks()
    units = sql("select id, class_id, week_no from units where week_no >= %d" % PAPER_WEEK_BASE)
    orphan = [u[0] for u in units if int(u[0]) not in metas]
    H.eq(orphan, [], "保留带里的单元都有组卷元数据（没有野卷）")
    ghost = []
    for uid, (cid, _st) in metas.items():
        n = sql_int("select count(*) from units where id=%d and class_id=%d" % (uid, cid))
        if n == 0:
            ghost.append(uid)
    H.eq(ghost, [], "组卷元数据都指向真实存在的卷单元（没有悬空元数据）")
    bad_share = [uid for uid in marks
                 if sql_int("select count(*) from units where id=%d" % uid) == 0]
    H.eq(bad_share, [], "公共题库分享标记都指向真实单元")

    stu = ctx["students"]["S105A01"]["token"]
    st, p = req("GET", "/admin/papers?classId=%d" % ctx["classes"]["S10.5验收1班"]["id"], stu)
    H.eq(st, 403, "学生 token 打教师组卷接口 → 403")
    H.eq(code_of(p), 40301, "学生越权错误码 40301")


# ---------------------------------------------------------------- ① 选题→组卷→发布→学生可见可打

def section_e2e(ctx):
    H.section("① 选题 → 组卷 → 发布 → 学生端可见可打（E2E）")
    A = ctx["teacherA"]
    c1 = ctx["classes"]["S10.5验收1班"]["id"]
    bank = ctx["bank"]["S10.5验收1班"]
    start_unit = bank["units"]["1|61"]["unitId"]

    # --- 选题池：私有池 = 我名下班级的教学单元 ---
    st, p, d = bank_questions(A, source="mine", class_id=c1)
    H.eq(st, 200, "选题池（我的题库）返回 200")
    H.eq(d["mineTotal"], 13, "私有池 13 道（起跑线 11 + 六级加练 2）")
    H.eq(d["publicTotal"], 0, "此时公共题库 0 道（没人分享）")
    H.eq(len(d["items"]), 13, "私有池一页取全 13 道")
    H.check(no_answer_leak(d), "选题池不下发答案/解析字段")
    H.eq(sorted({i["source"] for i in d["items"]}), ["mine"], "私有池 source 全是 mine")
    H.eq(sorted({i["className"] for i in d["items"]}), ["S10.5验收1班"], "按班级过滤只出本班题")
    H.check(all(i["tip"] for i in d["items"]), "每道题都带考点（tip）供教师选题判读")

    st, p, d = bank_units(A, source="mine")
    mine_ids = sorted(i["unitId"] for i in d["items"])
    H.eq(len(mine_ids), 4, "私有单元候选 4 个（我两个班的各 2 个教学单元）")
    H.check(all(i["unitKind"] == "unit" for i in d["items"]), "私有候选全是教学单元（卷不进选题池）")

    # --- 组卷：整单元引用（一键引用已切片真题单元） ---
    st, p, paper = compose(A, c1, TITLE1, source_unit=start_unit, mode="class", tlm=10)
    H.eq(st, 200, "整单元引用组卷成功")
    ctx["paper1"] = paper
    H.check(paper["weekNo"] >= PAPER_WEEK_BASE, "卷落在保留带（week_no=%d）" % paper["weekNo"])
    H.eq(paper["status"], "draft", "新卷是草稿")
    H.eq(paper["questionCount"], 11, "整单元引用带上全部 11 题")
    H.eq(paper["levelCount"], 5, "按题型自动分 5 关")
    H.eq([lv["type"] for lv in paper["levels"]],
         ["listening", "vocab", "grammar", "reading", "translation"], "分关按考试顺序：听力→词汇→语法→阅读→翻译")
    H.eq([lv["questionCount"] for lv in paper["levels"]], [2, 3, 2, 2, 2], "各关题数对得上")
    H.eq(paper["timeLimit"], 600, "每关限时 10 分钟落成 600 秒")
    H.eq(paper["open"], False, "草稿对学生不开")
    H.eq(paper["mode"], "class", "形态=课内带打")
    H.eq([t["classId"] for t in paper["targets"]], [c1], "宿主班只有一个落点")
    H.check(no_answer_leak(paper), "教师端卷详情不下发答案字段")

    # --- 草稿对学生不存在 ---
    stu = ctx["students"]["S105A01"]["token"]
    H.eq(len(unit_levels(stu, paper["unitId"])), 0, "草稿卷的下发关卡为空（地图上看不到）")
    lv0 = paper["levels"][0]["id"]
    st, p, _ = take_paper(stu, lv0)
    H.eq(st, 404, "草稿卷取卷 → 404（不承认存在）")

    # --- 发布（课内带打，2 小时到期） ---
    st, p, pub = publish(A, c1, paper["unitId"], [c1], mode="class", due=iso_after(7200))
    H.eq(st, 200, "发布成功")
    H.eq(pub["status"], "published", "状态=已发布")
    H.eq(pub["open"], True, "发布后 open=true")
    H.eq(pub["expired"], False, "还没到期")
    H.eq(len(pub["targets"]), 1, "落点 1 个（宿主班）")
    H.eq(pub["targets"][0]["dueAt"], pub["dueAt"], "落点到期时间与卷一致")

    # --- 学生端：入口出现、练习口径、全关解锁 ---
    lvls = unit_levels(stu, paper["unitId"])
    H.eq(len(lvls), 5, "学生地图下发卷的 5 个分关")
    H.check(all(x["practice"] for x in lvls), "5 关都标 practice=true")
    H.check(all(x["paperMode"] == "class" for x in lvls), "5 关都带 paperMode=class")
    H.check(all(x["dueAt"] for x in lvls), "5 关都带到期时间（前端可显示倒计时）")
    H.check(all(x["unlocked"] for x in lvls), "练习卷分关之间无链条：5 关全 unlocked")
    H.check(all(not x["cleared"] for x in lvls), "还没人打过：cleared 全 false")
    us = unit_summary(stu, paper["unitId"])
    H.check(us is not None and us["practice"], "单元汇总里这份卷标 practice（「本周练习」区块）")
    H.eq(us["name"], TITLE1, "「本周练习」显示卷名")
    H.eq(us["paperMode"], "class", "单元汇总带 paperMode")
    before_rec = levels_of(stu)["recommendedLevelId"]

    # --- 取卷：只有题面与选项，无答案 ---
    st, p, d = take_paper(stu, lv0)
    H.eq(st, 200, "发布后学生取卷 200")
    H.eq(len(d["questions"]), 2, "听力关 2 题")
    H.check(no_answer_leak(d), "取卷不下发答案/解析/听力原文")
    H.check(all(len(q["options"]) >= 2 for q in d["questions"]), "题目都带选项（可作答）")

    # --- 交卷（练习口径） ---
    lg0 = league(stu)
    st, p, _ = play(stu, lv0, correct_n=1)
    H.eq(st, 200, "交卷成功")
    sub = data_of(p)
    stl = sub["settlement"]
    H.eq(sub["status"], "finished", "答完全部题即完成")
    H.eq(stl["practice"], True, "结算标 practice=true")
    H.eq(stl["stars"], 0, "练习不发星（stars=0）")
    H.eq(stl["score710"], 0, "练习不发 710 估分（=0）")
    H.eq(stl["firstClear"], False, "练习不算首刷")
    H.eq(stl["replay"], False, "练习也不算重刷")
    reasons = sorted({r["reason"] for r in stl["xpRows"]})
    H.check(set(reasons) <= {"answer_base", "answer_speed", "answer_combo"},
            "练习只发逐题分，不发通关/三星奖励（reasons=%r）" % (reasons,))
    H.check(stl["xpTotal"] > 0, "答对 1 题就有逐题分（xpTotal=%d）" % stl["xpTotal"])

    # --- 全错也不作废（练习无爱心失败） ---
    lv1 = paper["levels"][1]["id"]
    st, p, _ = play(stu, lv1, correct_n=0)
    H.eq(st, 200, "全错提交仍然 200")
    stl2 = data_of(p)["settlement"]
    H.eq(data_of(p)["status"], "finished", "全错也 finished（练习没有爱心作废）")
    H.eq(stl2["correct"], 0, "全错 correct=0")
    H.eq(stl2["practice"], True, "全错那份仍是 practice 口径")

    lg1 = league(stu)
    H.eq(lg1["rows"], lg0["rows"], "练习不改变联赛首刷明细（rows 一致）")
    H.eq(lg1["clears"], lg0["clears"], "练习不增加首刷通关数")
    H.eq(lg1["replayAttempts"], lg0["replayAttempts"], "练习不计重刷次数")
    H.eq(lg1["xp"], lg0["xp"], "练习不进榜：联赛 XP 一分不涨（逐题分只进个人账本）")
    H.eq(stl2["xpTotalAll"], stl["xpTotalAll"] + stl2["xpTotal"],
         "个人账本聚合按逐题分累加（xpTotalAll 对得上）")
    H.eq(levels_of(stu)["recommendedLevelId"], before_rec, "练习不影响推荐起点")

    # --- 重练：同一关再打一次，账本继续涨，但联赛口径仍然不变 ---
    st, p, _ = play(stu, lv0, correct_n=2)
    H.eq(st, 200, "重练同一关 200")
    stl3 = data_of(p)["settlement"]
    H.eq(len(attempt_state(paper["unitId"], ctx["students"]["S105A01"]["id"])), 3,
         "这份卷留 3 条 attempt（听力关 2 次 + 词汇关 1 次）")
    H.eq(stl3["xpTotalAll"], stl2["xpTotalAll"] + stl3["xpTotal"],
         "重练的逐题分照进个人账本（xpTotalAll 继续累加）")
    lg2 = league(stu)
    H.eq(lg2["rows"], lg0["rows"], "重练也不进联赛明细")
    H.eq(lg2["replayAttempts"], lg0["replayAttempts"], "练习重练不计重刷")
    H.eq(lg2["xp"], lg0["xp"], "重练同样不进榜（XP 仍不变）")


# ---------------------------------------------------------------- ② 生命周期

def section_lifecycle(ctx):
    H.section("② 关闭 / 重开 / 到期：入口消失 + 40305")
    A = ctx["teacherA"]
    c1 = ctx["classes"]["S10.5验收1班"]["id"]
    paper1 = ctx["paper1"]
    stu = ctx["students"]["S105A02"]["token"]
    uid = paper1["unitId"]
    lv0 = paper1["levels"][0]["id"]

    # 先留一个没交卷的 attempt，用来验证"关闭后交卷被拒且 attempt 不落地"
    st, p, d = take_paper(stu, lv0)
    H.eq(st, 200, "关闭前取卷成功（留下未交卷 attempt）")
    attempt_id = d["attemptId"]

    st, p = req("POST", "/admin/papers/%d/close?classId=%d" % (uid, c1), A)
    d = data_of(p)
    H.eq(st, 200, "教师关闭成功")
    H.eq(d["status"], "closed", "状态=closed")
    H.eq(d["open"], False, "关闭后 open=false")

    H.eq(len(unit_levels(stu, uid)), 0, "关闭后学生地图上入口消失")
    H.check(unit_summary(stu, uid) is None, "「本周练习」区块也消失")
    st, p, _ = take_paper(stu, lv0)
    H.eq(st, 403, "关闭后旧 URL 取卷 → 403")
    H.eq(code_of(p), 40305, "取卷被拒错误码 40305（练习已结束）")

    st, p, _ = play(stu, lv0, correct_n=2)
    H.eq(st, 403, "关闭后交卷 → 403")
    H.eq(code_of(p), 40305, "交卷被拒错误码 40305")
    row = sql_int("select count(*) from attempts where id=%d and status='in_progress'" % attempt_id)
    H.eq(row, 1, "被拒的交卷没有落地：attempt 仍 in_progress")

    st, p = req("POST", "/admin/papers/%d/reopen?classId=%d" % (uid, c1), A)
    d = data_of(p)
    H.eq(st, 200, "重新开放成功")
    H.eq(d["open"], True, "重开后 open=true")
    H.eq(len(unit_levels(stu, uid)), 5, "入口回来了（5 关重新可见）")
    st, p, d = take_paper(stu, lv0)
    H.eq(st, 200, "重开后取卷 200")
    H.eq(d["attemptId"], attempt_id, "复用了原来那个未完成的 attempt（seed 不变）")
    H.eq(d["resumed"], True, "resumed=true")
    st, p, d = play(stu, lv0, correct_n=2)
    H.eq(st, 200, "续答交卷成功")
    H.eq(data_of(p)["status"], "finished", "续答后完成")

    # --- 到期：第二份卷 dueAt=+6s，睡 7 秒 ---
    bank = ctx["bank"]["S10.5验收1班"]
    start_unit = bank["units"]["1|61"]["unitId"]
    st, p, paper2 = compose(A, c1, TITLE2, source_unit=start_unit, mode="practice", tlm=0)
    H.eq(st, 200, "第二份卷（到期验收）组卷成功")
    ctx["paper2"] = paper2
    deadline = iso_after(6)
    st, p, pub2 = publish(A, c1, paper2["unitId"], [c1], mode="practice", due=deadline)
    H.eq(st, 200, "第二份卷发布成功（6 秒后到期）")
    H.eq(pub2["open"], True, "刚发布时仍 open")
    H.eq(len(unit_levels(stu, paper2["unitId"])), 5, "到期前入口在")
    say("  … 等 7 秒让它过头 …")
    time.sleep(7)

    st, p = req("GET", "/admin/papers/%d?classId=%d" % (paper2["unitId"], c1), A)
    d = data_of(p)
    H.eq(d["open"], False, "到期后 open=false")
    H.eq(d["expired"], True, "到期后 expired=true")
    H.eq(len(unit_levels(stu, paper2["unitId"])), 0, "到期后学生端入口消失")
    st, p, _ = take_paper(stu, paper2["levels"][0]["id"])
    H.eq(st, 403, "到期后取卷 → 403")
    H.eq(code_of(p), 40305, "到期取卷错误码 40305")

    st, p = req("POST", "/admin/papers/%d/reopen?classId=%d" % (paper2["unitId"], c1), A)
    H.eq(st, 409, "已过期的卷不给重开（假开放没意义）")
    H.eq(code_of(p), 40901, "过期重开错误码 40901")
    H.eq(len(unit_levels(stu, paper2["unitId"])), 0, "重开被拒后入口仍然没有")


# ---------------------------------------------------------------- ③ 同卷跨班

def section_cross_class(ctx):
    H.section("③ 同卷发布到两个班：各打各的 + 班间 PK 判同卷")
    A = ctx["teacherA"]
    c1 = ctx["classes"]["S10.5验收1班"]["id"]
    c2 = ctx["classes"]["S10.5验收2班"]["id"]
    start_unit = ctx["bank"]["S10.5验收1班"]["units"]["1|61"]["unitId"]

    st, p, paper3 = compose(A, c1, TITLE3, source_unit=start_unit, mode="class", tlm=10)
    H.eq(st, 200, "第三份卷组卷成功")
    ctx["paper3"] = paper3
    st, p, pub = publish(A, c1, paper3["unitId"], [c1, c2], mode="class", due=iso_after(7200))
    H.eq(st, 200, "一次发给两个班成功")
    H.eq(len(pub["targets"]), 2, "两个落点（宿主班 + 副本）")
    H.eq({t["classId"] for t in pub["targets"]}, {c1, c2}, "落点班级正确")
    origin = [t for t in pub["targets"] if t["isOrigin"]]
    H.eq(len(origin), 1, "只有一个宿主班")
    copy_t = [t for t in pub["targets"] if not t["isOrigin"]][0]
    H.check(copy_t["unitId"] != paper3["unitId"], "副本在 2 班是另一个 unitId（实体不同）")
    H.check(all(t["open"] for t in pub["targets"]), "两个班的落点都可见可打")
    H.eq(local_fp(paper3["unitId"]), local_fp(copy_t["unitId"]), "两班副本内容指纹一致（逐字复制）")
    copy_levels = sql("select l.id from levels l where l.unit_id=%d order by l.seq" % copy_t["unitId"])
    H.eq(len(copy_levels), 5, "副本也自动分了 5 关")
    sig = ("select l.seq, l.name, l.type, l.time_limit from levels l "
           "where l.unit_id=%d order by l.seq asc")
    H.eq(sql(sig % copy_t["unitId"]), sql(sig % paper3["unitId"]), "副本的分关结构逐字一致（序号/关名/题型/限时）")
    cnt = ("select l.seq, count(q.id) from levels l left join questions q on q.level_id=l.id "
           "where l.unit_id=%d group by l.seq order by l.seq asc")
    H.eq(sql(cnt % copy_t["unitId"]), sql(cnt % paper3["unitId"]), "副本每关题数与源卷一致")

    # PK 判同卷（学生侧）
    s1 = ctx["students"]["S105A01"]["token"]
    s2 = ctx["students"]["S105A11"]["token"]
    st, p = req("POST", "/league/pk/check", s1,
                {"opponentClassId": c2, "unitId": paper3["unitId"]})
    H.eq(st, 200, "pk/check 是业务结论（200）")
    d = data_of(p)
    H.eq(d["allowed"], True, "同卷 → 放行")
    H.eq(d["samePaper"], True, "samePaper=true")
    H.eq(d["code"], "OK", "code=OK")
    H.check(d["myFingerprint"] and d["myFingerprint"] == d["opponentFingerprint"],
            "双方指纹一致（服务端口径）")
    H.eq(d["myFingerprint"], local_fp(paper3["unitId"]), "服务端指纹与本地复算一致")
    H.check("同卷" in d["reason"], "理由里写明同卷")

    # 异卷必拒：拿另一份不同内容的卷（第二份卷是 0 限时的同题？内容相同——用第一份卷的听力关所在单元）
    st, p, d5 = compose(A, c1, "异卷对照", question_ids=[ctx["bank"]["S10.5验收1班"]["units"]["2|62"]["questions"][0]], tlm=5)
    H.eq(st, 200, "单选题组卷成功（异卷对照）")
    ctx["paper_diff"] = d5
    st, p = req("POST", "/league/pk/check", s1,
                {"opponentClassId": c2, "unitId": d5["unitId"]})
    d = data_of(p)
    H.eq(d["allowed"], False, "异卷不给开战")
    H.eq(d["code"], "PK_PAPER_MISMATCH", "异卷 code=PK_PAPER_MISMATCH")
    H.eq(d["samePaper"], False, "异卷 samePaper=false")

    # 各打各的：同序号关卡分别作答，attempt / 题目 id 都不交集
    lvA = paper3["levels"][0]["id"]
    lvB = int(copy_levels[0][0])
    st, p, dA = take_paper(s1, lvA)
    H.eq(st, 200, "1 班学生取本班卷成功")
    st, p, dB = take_paper(s2, lvB)
    H.eq(st, 200, "2 班学生取本班副本成功")
    qA = {q["id"] for q in dA["questions"]}
    qB = {q["id"] for q in dB["questions"]}
    H.eq(qA & qB, set(), "两个班的题目 id 无交集（各是各的实体）")
    H.eq(sorted(q["stem"] for q in dA["questions"]), sorted(q["stem"] for q in dB["questions"]),
         "题干逐字一致（同卷）")
    H.check(dA["attemptId"] != dB["attemptId"], "两次取卷是各自的 attempt")
    st, p, _ = play(s1, lvA, correct_n=2)
    H.eq(st, 200, "1 班学生交卷成功")
    st, p, _ = play(s2, lvB, correct_n=1)
    H.eq(st, 200, "2 班学生交卷成功")
    H.eq(sql_int("select count(*) from attempts where unit_id=%d and user_id=%d"
                 % (paper3["unitId"], ctx["students"]["S105A01"]["id"])), 1,
         "1 班的作答记在 1 班的卷上")
    H.eq(sql_int("select count(*) from attempts where unit_id=%d and user_id=%d"
                 % (copy_t["unitId"], ctx["students"]["S105A11"]["id"])), 1,
         "2 班的作答记在 2 班的副本上")
    H.eq(sql_int("select count(*) from attempts where unit_id=%d and user_id=%d"
                 % (copy_t["unitId"], ctx["students"]["S105A01"]["id"])), 0,
         "1 班学生的作答不会落在 2 班副本上")

    # 跨班关卡一律 404
    st, p, _ = take_paper(s1, lvB)
    H.eq(st, 404, "1 班学生取 2 班的关卡 → 404（跨班关卡当不存在）")
    H.eq(len(unit_levels(s1, copy_t["unitId"])), 0, "1 班学生地图上也没有 2 班的卷")


# ---------------------------------------------------------------- ④ 公共题库与权限

def section_bank_and_auth(ctx):
    H.section("④ 公共题库：权限边界 / 分享 / 引用")
    A, B = ctx["teacherA"], ctx["teacherB"]
    AN, BN = ENV["teacherA"]["name"], ENV["teacherB"]["name"]
    c1 = ctx["classes"]["S10.5验收1班"]["id"]
    c3 = ctx["classes"]["S10.5验收3班"]["id"]
    a_ids = set(ctx["bank"]["S10.5验收1班"]["questions"])

    # 教师 B 的池子与 A 完全隔离
    st, p, d = bank_questions(B, source="mine", class_id=c3)
    H.eq(st, 200, "B 的私有池返回 200")
    H.eq(d["mineTotal"], 13, "B 自己也有 13 道（各班的导入互不可见）")
    b_ids = {i["id"] for i in d["items"]}
    H.eq(a_ids & b_ids, set(), "A、B 的私有题零交集")
    H.eq(d["publicTotal"], 0, "分享前公共池为空")
    H.eq(sorted({i["ownerName"] for i in d["items"]}), [BN],
         "自己的题也带出题教师真名（前端 mine tab 不展示这一列）")

    # 引用别人的私有题 / 私有单元 → 404
    st, p, _ = compose(B, c3, "偷题的卷", question_ids=[sorted(a_ids)[0]], tlm=5)
    H.eq(st, 404, "引用他师私有题 → 404")
    H.eq(code_of(p), 40401, "拒绝码 40401")
    st, p, _ = compose(B, c3, "偷单元的卷",
                       source_unit=ctx["bank"]["S10.5验收1班"]["units"]["1|61"]["unitId"], tlm=5)
    H.eq(st, 404, "整单元引用他师私有单元 → 404")
    H.eq(sql_int("select count(*) from units where class_id=%d and week_no>=%d and name in "
                 "('偷题的卷','偷单元的卷')" % (c3, PAPER_WEEK_BASE)), 0,
         "被拒的组卷没有在 B 的班留下残留卷")

    # 看他师的班 / 发布到他师的班
    st, p = req("GET", "/admin/papers?classId=%d" % c1, B)
    H.eq(st, 404, "B 看 A 的班卷列表 → 404")
    st, p, d = bank_questions(B, source="mine", class_id=c1)
    H.eq(d["mineTotal"], 0, "按他师班级过滤选题池 → 0（筛不到别人的题）")
    st, p = req("POST", "/admin/papers/%d/publish?classId=%d"
                   % (ctx["paper1"]["unitId"], c1), B, {"classIds": [c1, c3]})
    H.eq(st, 404, "B 发布/关闭 A 的卷 → 404")

    # A 分享第一份卷 → 公共池可见（跨教师）
    st, p = req("POST", "/admin/papers/%d/share?classId=%d" % (ctx["paper1"]["unitId"], c1),
                A, {"shared": True})
    d = data_of(p)
    H.eq(st, 200, "A 分享卷到教研室公共题库")
    H.eq(d["shared"], True, "卷详情里 shared=true")

    st, p, du = bank_units(B, source="public")
    H.eq(du["total"], 1, "B 的公共单元候选 1 个")
    it = du["items"][0]
    H.eq(it["unitKind"], "paper", "公共候选是「已组卷」性质")
    H.eq(it["ownerName"], AN, "公共候选带出题教师真名")
    H.eq(it["name"], TITLE1, "公共候选就是那份卷")
    H.eq(it["paperStatus"], "published", "带出源的发布状态（草稿/已发布/已关闭）")
    H.eq(it["questionCount"], 11, "公共候选带题量")

    st, p, d = bank_questions(B, source="public", page_size=50)
    H.eq(d["publicTotal"], 11, "公共池 11 道")
    H.eq(len(d["items"]), 11, "公共池一页取全")
    H.eq(sorted({i["source"] for i in d["items"]}), ["public"], "公共池 source 全是 public")
    H.eq(sorted({i["unitKind"] for i in d["items"]}), ["paper"], "公共题的出处性质=已组卷")
    H.eq(sorted({i["ownerName"] for i in d["items"]}), [AN],
         "公共题带出题教师名（可认领/致谢）")
    H.check(no_answer_leak(d), "公共池不下发答案/解析")
    pub_ids = {i["id"] for i in d["items"]}
    H.eq(pub_ids & set(ctx["bank"]["S10.5验收3班"]["questions"]), set(), "公共池与 B 自己的题无重叠")

    # Tab 角标：两个总数是「两栏各有多少题」，切栏不该把另一栏角标压成 0（走查撞出）。
    H.eq(d["mineTotal"], 13, "站在公共池这一栏，我的题库角标仍是 13（不被 source 分池吃掉）")
    st, p, dm = bank_questions(B, source="mine")   # 公共池的题出处是别人班，不带班过滤
    H.eq(dm["publicTotal"], 11, "切回我的题库，公共池角标仍是 11")
    H.eq(dm["mineTotal"], 13, "我的题库总数不受公共池影响")
    H.eq(dm["total"], 13, "我的题库这一页只有私有题（13 条）")

    # B 整单元引用公共卷 → 内容一致、指纹一致、独立实体
    st, p, borrow = compose(B, c3, "引用公共卷的练习", source_unit=it["unitId"], mode="practice", tlm=15)
    H.eq(st, 200, "B 整单元引用公共卷成功")
    H.eq(borrow["questionCount"], 11, "引用后 11 题")
    H.eq(borrow["levelCount"], 5, "引用后 5 关（分关结构一起复制）")
    H.eq(local_fp(borrow["unitId"]), local_fp(ctx["paper1"]["unitId"]), "引用副本与源卷指纹一致")
    H.eq(borrow["classId"], c3, "引用副本落在 B 自己的班")
    H.eq(sql_int("select count(*) from questions q join levels l on l.id=q.level_id "
                 "where l.unit_id=%d" % borrow["unitId"]), 11, "引用是真复制（B 班里有 11 条题目行）")

    # 取消分享 → 公共池归零；已引用的副本不受影响
    st, p = req("POST", "/admin/papers/%d/share?classId=%d" % (ctx["paper1"]["unitId"], c1),
                A, {"shared": False})
    d = data_of(p)
    H.eq(st, 200, "A 取消分享")
    H.eq(d["shared"], False, "卷详情里 shared=false")
    st, p, d = bank_questions(B, source="public")
    H.eq(d["publicTotal"], 0, "取消分享后公共池归 0")
    H.eq(bank_units(B, source="public")[2]["total"], 0, "公共单元候选也归 0")
    st, p = req("GET", "/admin/papers/%d?classId=%d" % (borrow["unitId"], c3), B)
    d = data_of(p)
    H.eq(st, 200, "已经引用的副本不受影响（内容复制，各自独立）")
    H.eq(d["questionCount"], 11, "副本内容还在")
    H.eq(sql_int("select count(*) from units where id=%d" % ctx["paper1"]["unitId"]), 1,
         "源卷也还在（取消分享不删卷）")


# ---------------------------------------------------------------- ⑤ 守卫与边界

def section_guards(ctx):
    H.section("⑤ 参数守卫 / 生命周期冲突 / 越权 / 保留带")
    A, B = ctx["teacherA"], ctx["teacherB"]
    c1 = ctx["classes"]["S10.5验收1班"]["id"]
    start_unit = ctx["bank"]["S10.5验收1班"]["units"]["1|61"]["unitId"]
    six_unit = ctx["bank"]["S10.5验收1班"]["units"]["2|62"]["unitId"]

    # --- 草稿编辑闭环：卷里的题要能读回购物车，再用它保存回去（浏览器走查撞出 0 题） ---
    st, p, pool = bank_questions(A, source="mine", class_id=c1)
    band = pool["items"][0]["band"]          # 单一分套是硬规则：挑题先锁定同一个 band
    three = [i["id"] for i in pool["items"] if i["band"] == band][:3]
    H.eq(len(three), 3, "编辑闭环：先备好同分套的 3 道题")
    st, p, tir = compose(A, c1, "编辑闭环用卷", question_ids=three, mode="practice", tlm=5)
    H.eq(st, 200, "编辑闭环：组一份 3 题草稿")
    tir_id = tir["unitId"]
    q = "/admin/bank/questions?classId=%d&unitId=%d&pageSize=200" % (c1, tir_id)
    st, p = req("GET", q, A)
    rd = data_of(p)
    H.eq(st, 200, "按单元取卷里的题：200")
    H.eq(rd["total"], 3, "草稿回显取回 3 题（编辑草稿不能读成 0 题）")
    H.eq(sorted({i["unitKind"] for i in rd["items"]}), ["paper"], "回显的题带出处性质=已组卷")
    H.eq(sorted({i["unitId"] for i in rd["items"]}), [tir_id], "回显的题都来自这份卷单元")
    H.eq(sorted({i["source"] for i in rd["items"]}), ["mine"], "回显走的是私有池（我的卷）")
    readback = sorted(i["id"] for i in rd["items"])
    st, p = req("POST", "/admin/papers/%d/rebuild?classId=%d" % (tir_id, c1), A,
                {"questionIds": readback, "timeLimitMin": 5})
    rb = data_of(p)
    H.eq(st, 200, "用回显的题重选保存：200（编辑→保存是闭环）")
    H.eq(rb["questionCount"], 3, "重选后仍是 3 题")
    H.eq(rb["status"], "draft", "重选保存不改变草稿身份")
    st, p = req("DELETE", "/admin/papers/%d?classId=%d" % (tir_id, c1), A)
    H.eq(st, 200, "编辑闭环的草稿用完即删（不留野卷）")

    cases = [
        ("空选题（既不给题也不给单元）", {"classId": c1, "title": "空卷"}, 400),
        ("空卷名", {"classId": c1, "title": "  ", "sourceUnitId": start_unit}, 400),
        ("卷名超 100 字", {"classId": c1, "title": "卷" * 101, "sourceUnitId": start_unit}, 400),
        ("发布方式非法", {"classId": c1, "title": "怪形态", "sourceUnitId": start_unit,
                       "mode": "homework"}, 400),
        ("限时 -1", {"classId": c1, "title": "负限时", "sourceUnitId": start_unit,
                    "timeLimitMin": -1}, 400),
        ("限时 999（>180 分钟）", {"classId": c1, "title": "超长限时",
                              "sourceUnitId": start_unit, "timeLimitMin": 999}, 400),
        ("classId 缺省", {"title": "没班", "sourceUnitId": start_unit}, 400),
        ("别人的班", {"classId": ctx["classes"]["S10.5验收3班"]["id"], "title": "串班",
                    "sourceUnitId": start_unit}, 404),
    ]
    for name, body, want in cases:
        st, p = req("POST", "/admin/papers", A, body)
        H.eq(st, want, "组卷守卫：%s → %d" % (name, want))

    # 混合分套：四级 + 六级各一道
    four = ctx["bank"]["S10.5验收1班"]["units"]["1|61"]["questions"][0]
    six = ctx["bank"]["S10.5验收1班"]["units"]["2|62"]["questions"][0]
    st, p = req("POST", "/admin/papers", A,
                {"classId": c1, "title": "混套卷", "questionIds": [four, six], "timeLimitMin": 5})
    H.eq(st, 400, "混合分套组卷 → 400")
    H.check("分套" in (p.get("message") or ""), "错误信息说明分套问题")

    # 纯六级卷发四级班：班里没有备考六级的学生
    st, p, six_paper = compose(A, c1, "六级加练卷", source_unit=six_unit, tlm=10)
    H.eq(st, 200, "六级内容组卷本身可以（教师先组出来）")
    st, p, _ = publish(A, c1, six_paper["unitId"], [c1], mode="class")
    H.eq(st, 400, "纯六级卷发到没有六级学生的班 → 400（挡住静默空卷）")
    H.check("六级" in (p.get("message") or ""), "错误信息点明分套不匹配")
    st, p = req("DELETE", "/admin/papers/%d?classId=%d" % (six_paper["unitId"], c1), A)
    H.eq(st, 200, "守卫用例留下的草稿可以删掉（不污染留库）")

    # 到期时间守卫
    for name, due, want in [("到期时间已过", iso_after(-60), 400),
                            ("到期时间格式错", "2026/10/20 23:59", 400)]:
        st, p, tmp = compose(A, c1, "到期守卫", source_unit=start_unit, tlm=5)
        H.eq(st, 200, "临时卷组好（%s）" % name)
        st2, p2, _ = publish(A, c1, tmp["unitId"], [c1], due=due)
        H.eq(st2, want, "发布守卫：%s → %d" % (name, want))
        st3, p3 = req("DELETE", "/admin/papers/%d?classId=%d" % (tmp["unitId"], c1), A)
        H.eq(st3, 200, "被判拒的草稿随即删掉（%s）" % name)

    st, p, empty_pub = compose(A, c1, "空发守卫", source_unit=start_unit, tlm=5)
    H.eq(st, 200, "空发守卫的草稿组好")
    st2, p2, _ = publish(A, c1, empty_pub["unitId"], [], mode="class")
    H.eq(st2, 400, "不选任何班发布 → 400")
    st2, p2 = req("POST", "/admin/papers/%d/close?classId=%d" % (empty_pub["unitId"], c1), A)
    H.eq(st2, 409, "草稿不能关闭（还没发布）")
    st2, p2 = req("DELETE", "/admin/papers/%d?classId=%d" % (empty_pub["unitId"], c1), A)
    dd = data_of(p2)
    H.eq(st2, 200, "草稿可以删除")
    H.eq(dd["deleted"], True, "删除回执 deleted=true")
    H.eq(sql_int("select count(*) from units where id=%d" % empty_pub["unitId"]), 0,
         "删草稿把单元行也带走了（不留下野卷）")
    H.eq(sql_int("select count(*) from levels where unit_id=%d" % empty_pub["unitId"]), 0,
         "删草稿把分关也带走了（没有孤儿关卡）")

    # 生命周期冲突：已发布的不能重编/不能删
    pub_unit = ctx["paper1"]["unitId"]
    st, p = req("POST", "/admin/papers/%d/rebuild?classId=%d" % (pub_unit, c1), A,
                   {"sourceUnitId": start_unit, "timeLimitMin": 5})
    H.eq(st, 409, "已发布的卷不能重编题（改了就不是同一份卷）")
    st, p = req("DELETE", "/admin/papers/%d?classId=%d" % (pub_unit, c1), A)
    H.eq(st, 409, "已发布的卷不能删（学生作答要留档）")

    # 改卷名：学生端立刻跟着变
    stu = ctx["students"]["S105A01"]["token"]
    new_title = TITLE1 + "（改名后）"
    st, p = req("PATCH", "/admin/papers/%d?classId=%d" % (pub_unit, c1), A,
                {"title": new_title})
    d = data_of(p)
    H.eq(st, 200, "改卷名成功")
    H.eq(d["title"], new_title, "卷详情里的新名")
    H.eq(unit_summary(stu, pub_unit)["name"], new_title, "学生端「本周练习」立刻显示新名")
    H.eq(sql1("select name from units where id=%d" % pub_unit), new_title, "单元行本身也改名了")
    st, p = req("PATCH", "/admin/papers/%d?classId=%d" % (pub_unit, c1), A, {"title": " "})
    H.eq(st, 400, "改成空名 → 400")

    # 缺班级参数（写接口不猜班）
    for path, method in [("/admin/papers/%d/close" % pub_unit, "POST"),
                         ("/admin/papers/%d/reopen" % pub_unit, "POST"),
                         ("/admin/papers/%d" % pub_unit, "DELETE"),
                         ("/admin/papers", "GET")]:
        st, p = req(method, path, A)
        H.eq(st, 400, "写/读接口缺 classId → 400（%s %s）" % (method, path))

    # 内容维护口不能碰保留带
    st, p = req("PATCH", "/admin/units/%d" % pub_unit, A, {"name": "偷改卷单元"})
    H.eq(st, 409, "内容维护口改卷单元 → 409")
    H.check("组卷" in (p.get("message") or ""), "409 文案指向组卷工作台")
    st, p = req("DELETE", "/admin/units/%d" % pub_unit, A)
    H.eq(st, 409, "内容维护口删卷单元 → 409")
    lvl = sql1("select id from levels where unit_id=%d order by seq limit 1" % pub_unit)
    st, p = req("PATCH", "/admin/levels/%s" % lvl, A, {"name": "偷改分关"})
    H.eq(st, 409, "内容维护口改卷的分关 → 409")
    qid = sql1("select q.id from questions q join levels l on l.id=q.level_id "
               "where l.unit_id=%d limit 1" % pub_unit)
    st, p = req("DELETE", "/admin/questions/%s" % qid, A)
    H.eq(st, 409, "内容维护口删卷里的题 → 409")

    # 他师不能动我的卷
    st, p = req("POST", "/admin/papers/%d/close?classId=%d" % (pub_unit, c1), B)
    H.eq(st, 404, "他师关闭我的卷 → 404（不承认存在）")
    st, p = req("GET", "/admin/papers/%d?classId=%d" % (pub_unit, c1), B)
    H.eq(st, 404, "他师看我的卷 → 404")


# ---------------------------------------------------------------- ⑥ 收尾

def section_final(ctx):
    H.section("⑥ 收尾：结构红线与留库清单")
    tables, cols = schema_counts()
    H.eq(tables, 17, "收尾表数仍是 17")
    H.eq(cols, 128, "收尾列数仍是 128")
    metas = paper_metas()
    units = sql("select id, week_no, name from units where week_no >= %d order by week_no" % PAPER_WEEK_BASE)
    orphan = [u[0] for u in units if int(u[0]) not in metas]
    H.eq(orphan, [], "收尾没有野卷")
    by_status = {}
    for _uid, (_cid, st) in metas.items():
        by_status[st] = by_status.get(st, 0) + 1
    say("  全库卷共 %d 份：%r" % (len(metas), by_status))
    say("  验收留库的卷单元 id：%r" % ([int(u[0]) for u in units],))
    pub = sql("select count(*) from attempts a join units u on u.id=a.unit_id where u.week_no>=%d"
              % PAPER_WEEK_BASE)
    say("  练习卷上的作答记录 %s 条（留档）" % pub[0][0])
    H.check(len(metas) > 0 and len(units) > 0, "组卷链路确实在库里留了痕（可复查）")


def main():
    say("S10.5 验收开始：教师组卷 → 发布 → 学生端（真环境 MySQL 3307 / Go 8080）")
    n = reset_papers()
    say("  清掉上一轮验收的卷 %d 份（本轮从干净状态开跑；教学单元不动）" % n)
    ctx = {
        "teacherA": token_of(ENV["teacherA"]["username"]),
        "teacherB": token_of(ENV["teacherB"]["username"]),
        "students": {},
        "classes": {k: {"id": v["id"]} for k, v in ENV["classes"].items()},
        "bank": ENV["bank"],
    }
    # 学生 token 尽量现登；登不上（口令被别的脚本改过）就用 env 里 seed 时留下的
    for u, info in ENV["students"].items():
        try:
            tok = token_of(u)
        except Fail:
            tok = info["token"]
        ctx["students"][u] = {"id": info["id"], "classId": info["classId"], "token": tok}

    for fn in (section_baseline, section_e2e, section_lifecycle, section_cross_class,
               section_bank_and_auth, section_guards, section_final):
        fn(ctx)

    total, failed = H.result()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "99-summary.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("%d %d\n" % (total, failed))
    say("写出 %s" % out)


if __name__ == "__main__":
    main()