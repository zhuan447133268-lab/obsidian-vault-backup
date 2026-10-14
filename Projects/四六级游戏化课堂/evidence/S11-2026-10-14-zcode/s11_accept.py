"""S11 验收：课中实时大屏（三指标 + 实时易错题榜 + 10s 可配置 + 防压力）。

验收标准（任务书 v2.0 §S11 原文 + 开工说明）逐条落在这里：
  ① 三指标 + 易错题榜与手算一致 —— 手算（PLAN）× SQL 直算 × 接口回执，三方逐项对拍
  ② 学生端 JWT 访问大屏接口 403 —— 连发 10 次，同时看 HTTP 码 / 业务码 / 断连数
  ③ 大屏 10s 自动刷新（可配置）—— 8080 默认 10；8081 实例以 LIVE_REFRESH_SECONDS=3 起，
     同一接口必须回 3（间隔只有服务端一处定义）
  ④ 易错题榜无学生身份信息字段 —— 键集合完全相等 + 整段 JSON 字节级不含任何学生标识

外加回归区：底账红线（17 表/128 列）、别人题库 CRC、评分关键文件未被本阶段改动、
既有教师端只读接口仍正常（新增一条路由没搅乱命名空间）。

手算底稿（PLAN_*）在下面，与 s11_setup.py 的落库计划同表——改一处必须改两处，
交卷报告里的"手算过程"就是按这张表算的。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s11_lib import BASE, Harness, code_of, data_of, probe_many, req, say, sql, sql1  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "s11-env.json")
ALT_BASE = os.environ.get("S11_ALT_BASE", "")   # 8081（LIVE_REFRESH_SECONDS=3）实例，空则跳过该断言并如实记失败
REPO = "D:/claude-work/cet46-game"

# 别人题库（本题库）的排除清单：所有历史验收班 + 我的 S11 班。理由是"别人的题库未被动过"，
# 验收班自己造的题本来就在名单外。CRC 口径与 S9/S10 完全同式。
OTHERS = ("('S9商城验收班','S9售罄验收班','S10验收1班','S10验收2班','S10验收3班',"
          "'S10.5验收1班','S10.5验收2班','S10.5验收3班','S105复验1班','S105复验2班',"
          "'T2私有班','S11验收1班')")
BANK_CRC_S9 = 3897258111    # S9 交卷报告里的 bank_crc；S10/S10.5/S11 三次交卷都应保持这个读数
# 数值对拍表的实现文件：本阶段（只加大屏读接口）不允许碰它们
SCORING_FILES = ["server/internal/quiz/engine.go", "server/internal/service/quiz_service.go"]

# ---------------------------------------------------------------------------
# 手算底稿：今天 10 条 attempt，每一条错在哪里都写在纸面上
#   (学生键, 关卡 seq, status, [(题号 seq, 是否答对)])
PLAN_TODAY = [
    ("A1", 1, "finished", [(1, False), (2, True)]),
    ("A1", 1, "finished", [(1, True), (2, True)]),
    ("A1", 2, "failed",   [(3, False), (4, True)]),
    ("A2", 1, "finished", [(1, False), (2, True)]),
    ("A2", 1, "finished", [(1, True), (2, True)]),
    ("A2", 3, "finished", [(5, True), (6, False)]),
    ("A3", 1, "finished", [(1, True), (2, False)]),
    ("A3", 2, "failed",   [(3, False), (4, False)]),
    ("A4", 1, "failed",   [(1, False), (2, True)]),
    ("A4", 2, "in_progress", []),
]
PLAN_YESTERDAY = [("A5", 1, "finished", [(1, False), (2, True)])]

h = Harness("S11")
env = {}
lv = {}          # seq → {"id","name"}
q = {}           # 题号 seq → {"id",...}
sid = {}         # 学生键 → user_id


def load_env():
    global env, lv, q, sid
    with open(ENV_PATH, encoding="utf-8") as f:
        env = json.load(f)
    lv = {int(k): v for k, v in env["levels"].items()}
    q = {int(x["seq"]): x for x in env["questions"]}
    sid = {k: v["id"] for k, v in env["students"].items()}
    say("读夹具 %s：班 %s(id=%d) 学生 %d 人 关 %d 个 题 %d 道"
        % (os.path.basename(ENV_PATH), env["class"]["name"], env["class"]["id"],
           len(env["students"]), len(lv), len(q)))
    say("  手算底稿：今天 %d 条 attempt + 昨天 1 条对照（A5）" % len(PLAN_TODAY))


# ============================================================ 手算（纯纸面，不碰 DB/接口）
def hand_calc():
    """按 PLAN 在纸面上算：三条指标 + 易错题榜。不读库、不调接口，纯按计划推。"""
    total = len(env["students"])
    order = sorted(lv)                       # 班内关卡顺序：seq 升序（本单元只有 week 9 一档）
    rank = {seq: i for i, seq in enumerate(order)}

    started = sorted({stu for stu, _, _, _ in PLAN_TODAY})
    # 进度分布：每人今天到的最远关（关卡顺序里的最大 seq）
    buckets = {}
    furthest = {}
    for stu, seq, _, _ in PLAN_TODAY:
        furthest[stu] = max(furthest.get(stu, seq), seq)
    for stu in env["students"]:
        if stu in furthest:
            buckets[furthest[stu]] = buckets.get(furthest[stu], 0) + 1
        else:
            buckets[0] = buckets.get(0, 0) + 1
    progress = [{"levelId": 0, "count": buckets.get(0, 0)}]
    for seq in order:
        if buckets.get(seq):
            progress.append({"levelId": lv[seq]["id"], "count": buckets[seq]})

    # 卡关热点：按关聚合 fails（status=failed）与 attempts（全部 attempt）
    stat = {}
    for stu, seq, status, _ in PLAN_TODAY:
        row = stat.setdefault(seq, {"attempts": 0, "fails": 0})
        row["attempts"] += 1
        if status == "failed":
            row["fails"] += 1
    stuck = [{"levelId": lv[s]["id"], "fails": v["fails"], "attempts": v["attempts"]}
             for s, v in stat.items() if v["fails"] > 0]
    stuck.sort(key=lambda x: (-x["fails"], -x["attempts"], x["levelId"]))
    stuck = stuck[:3]

    # 易错题榜：逐题 wrongCount / wrongStudents / answerCount
    qs = {}
    for stu, seq, _, answers in PLAN_TODAY:
        for qseq, ok in answers:
            row = qs.setdefault(qseq, {"answerCount": 0, "wrongCount": 0, "students": set()})
            row["answerCount"] += 1
            if not ok:
                row["wrongCount"] += 1
                row["students"].add(stu)
    wrong = [{"questionId": q[n]["id"], "answerCount": v["answerCount"],
              "wrongCount": v["wrongCount"], "wrongStudents": len(v["students"])}
             for n, v in qs.items() if v["wrongCount"] > 0]
    wrong.sort(key=lambda x: (-x["wrongStudents"], -x["wrongCount"], x["questionId"]))

    return {
        "participation": {"started": len(started), "total": total,
                          "rate": round(len(started) * 100.0 / total, 1)},
        "progress": progress,
        "stuckLevels": stuck,
        "wrongQuestions": wrong[:10],
    }


# ============================================================= SQL 直算（独立于服务端）
def sql_calc():
    """另写一套聚合直接问库（口径同 dto/live.go 的文件头），当"真值"用。"""
    ids = ",".join(str(v) for v in sid.values())
    win = "a.started_at >= CURDATE() and a.started_at < NOW(3)"

    total = sql1("select count(*) from users where class_id=%d and role='student'" % env["class"]["id"])
    started = sql1("select count(distinct a.user_id) from attempts a where %s and a.user_id in (%s)"
                   % (win, ids))
    rate = round(int(started) * 100.0 / int(total), 1)

    # 每人今天到的最远关：按（单元周次, 关卡 seq）排序取最后一条
    rows = sql("select a.user_id, l.id from attempts a join levels l on l.id=a.level_id "
               "join units u on u.id=l.unit_id where %s and a.user_id in (%s) "
               "order by a.user_id, u.week_no, l.seq" % (win, ids))
    furthest = {}
    for uid, lid in rows:
        furthest[uid] = int(lid)          # 有序流，最后一条即最远
    buckets = {0: 0}
    for uid in sid.values():
        lid = furthest.get(str(uid))
        if lid is None:
            buckets[0] += 1
        else:
            buckets[lid] = buckets.get(lid, 0) + 1
    progress = [{"levelId": 0, "count": buckets[0]}]
    for seq in sorted(lv):
        lid = lv[seq]["id"]
        if buckets.get(lid):
            progress.append({"levelId": lid, "count": buckets[lid]})

    srows = sql("select l.id, sum(a.status='failed'), count(*) from attempts a "
                "join levels l on l.id=a.level_id where %s and a.user_id in (%s) group by l.id"
                % (win, ids))
    stuck = [{"levelId": int(r[0]), "fails": int(r[1]), "attempts": int(r[2])} for r in srows]
    stuck = [x for x in stuck if x["fails"] > 0]
    stuck.sort(key=lambda x: (-x["fails"], -x["attempts"], x["levelId"]))

    wrows = sql("select aa.question_id, count(*), sum(aa.is_correct=0), "
                "count(distinct case when aa.is_correct=0 then a.user_id end) "
                "from attempt_answers aa join attempts a on a.id=aa.attempt_id "
                "where %s and a.user_id in (%s) group by aa.question_id" % (win, ids))
    wrong = [{"questionId": int(r[0]), "answerCount": int(r[1]), "wrongCount": int(r[2]),
              "wrongStudents": int(r[3])} for r in wrows]
    wrong = [x for x in wrong if x["wrongCount"] > 0]
    wrong.sort(key=lambda x: (-x["wrongStudents"], -x["wrongCount"], x["questionId"]))

    return {"participation": {"started": int(started), "total": int(total), "rate": rate},
            "progress": progress, "stuckLevels": stuck, "wrongQuestions": wrong[:10]}


def api_calc():
    st, p = req("GET", "/admin/live", token=env["teacher"]["token"])
    if st != 200 or code_of(p) != 0:
        raise SystemExit("大屏接口没回成功：HTTP %s / %s" % (st, p))
    d = data_of(p)
    return {
        "participation": {"started": d["participation"]["started"],
                          "total": d["participation"]["total"],
                          "rate": d["participation"]["rate"]},
        "progress": [{"levelId": x["levelId"], "count": x["count"]} for x in d["progress"]],
        "stuckLevels": [{"levelId": x["levelId"], "fails": x["fails"], "attempts": x["attempts"]}
                        for x in d["stuckLevels"]],
        "wrongQuestions": [{"questionId": x["questionId"], "answerCount": x["answerCount"],
                            "wrongCount": x["wrongCount"], "wrongStudents": x["wrongStudents"]}
                           for x in d["wrongQuestions"]],
    }, d


def show_hand_table():
    """把手算过程原样打在日志里：交卷报告直接引用这段。"""
    say("\n---- 手算过程（纸面推导，供报告引用）----")
    say("① 参与率：已开始闯关 = %s（A1~A4 各至少 1 条 attempt）→ %d/%d = %.1f%%"
        % ("、".join(sorted({s for s, _, _, _ in PLAN_TODAY})), 4, len(env["students"]), 80.0))
    say("② 进度分布（每人今天到的最远关）：A1→L2、A2→L3、A3→L2、A4→L2、A5→未开始")
    say("   → 未开始 1 · L1 0（没人停在 L1）· L2 3 · L3 1，合计 5 = 班级人数")
    say("③ 卡关热点：L2 失败 2 次（A1#3、A3#8）/ 今天共 3 次尝试；"
        "L1 失败 1 次（A4#9）/ 今天共 6 次尝试 → 榜序 L2 > L1")
    say("④ 易错题榜：Q1 错 3 人（A1/A2/A4，作答 6 次）· Q3 错 2 人（A1/A3，作答 2 次）·"
        " Q2 错 1 人（A3，作答 6 次）· Q4 错 1 人（A3，作答 2 次）· Q6 错 1 人（A2，作答 1 次）")
    say("   → 榜序 Q1 > Q3 > Q2 > Q4 > Q6（先答错人数、再答错次数、最后题号）；Q5 无人错，不上榜")
    say("   窗口对照：A5 昨天 23:59:59 那条若被算进来，Q1 会变成错 4 人 / 作答 7 次")
    say("   （这条是「窗口 = 今天 00:00 → 现在」的反证；A4 今天 00:00:00 整那条必须被算进 L2 的尝试数）")


# ================================================================ 00 底账
def section_baseline():
    h.section("⓪ 底账：表/列红线、别人题库 CRC、评分关键文件未被本阶段改动")
    tables = sql1("select count(*) from information_schema.tables where table_schema='cet46'")
    cols = sql1("select count(*) from information_schema.columns where table_schema='cet46'")
    h.eq(int(tables), 17, "表数仍是 17（S11 零改表：大屏全是读现成表）")
    h.eq(int(cols), 128, "列数仍是 128（S11 零改列）")

    j = (" from questions qq join levels ll on ll.id=qq.level_id "
         "join units uu on uu.id=ll.unit_id join classes cc on cc.id=uu.class_id")
    crc = int(sql1("select sum(crc32(concat(qq.id, 0x1f, coalesce(qq.stem,''), 0x1f, "
                  "coalesce(qq.options_json,'')))) % 4294967296" + j +
                  " where cc.name not in " + OTHERS))
    nq = int(sql1("select count(*)" + j + " where cc.name not in " + OTHERS))
    h.eq(crc, BANK_CRC_S9, "别人题库逐题 CRC 仍是 S9 那把尺子的读数（%d 题）" % nq)

    # 评分/结算的关键文件本阶段一字未改：git status 这两条路径必须是空的
    os.chdir(REPO)
    import subprocess
    out = subprocess.run(["git", "status", "--porcelain"] + SCORING_FILES,
                         capture_output=True, text=True).stdout.strip()
    h.eq(out, "", "数值对拍表的实现文件（engine.go / quiz_service.go）本阶段未改动")


# ================================================================ ① 三指标对拍
def section_metrics():
    h.section("① 三指标 + 易错题榜：手算 × SQL 直算 × 接口回执，三方逐项一致")
    hand = hand_calc()
    sq = sql_calc()
    api, raw = api_calc()

    for name, key in (("参与率", "participation"), ("进度分布", "progress"),
                      ("卡关热点", "stuckLevels"), ("易错题榜", "wrongQuestions")):
        h.eq(sq[key], hand[key], "%s：SQL 直算 == 手算" % name)
        h.eq(api[key], hand[key], "%s：接口回执 == 手算" % name)

    h.eq(api["participation"]["rate"], 80.0, "参与率是 80.0%（4/5，一位小数）")
    h.eq(sum(x["count"] for x in api["progress"]), api["participation"]["total"],
         "进度分布各桶之和 == 班级总人数（不重不漏）")
    h.eq(len(api["wrongQuestions"]), 5, "易错题榜 5 条（Q5 无人错，不上榜）")
    h.eq(api["stuckLevels"][0]["levelId"], lv[2]["id"], "卡关热点第一名是「词汇二」（失败 2 次）")
    h.eq(api["wrongQuestions"][0]["questionId"], q[1]["id"], "易错题榜第一名是 Q1（错 3 人）")

    # 名字与预览也要对得上：大屏要显示"哪一关/哪道题"，不能只有 id
    names = {x["levelId"]: x["levelName"] for x in raw["progress"]}
    h.eq(names.get(lv[2]["id"]), "词汇二", "进度分布带出关卡名（词汇二）")
    h.eq(raw["stuckLevels"][0]["unitName"], "S11验收单元", "卡关热点带出单元名")
    h.eq(raw["wrongQuestions"][0]["stemPreview"], q[1]["stem"][:120],
         "易错题榜的题干预览与题库原文一致")

    # 明细打印：报告里的"逐条对账"就引用这段
    say("  参与率：%s" % json.dumps(api["participation"], ensure_ascii=False))
    for x in raw["progress"]:
        say("  进度桶：levelId=%s %s → %d 人" % (x["levelId"], x["levelName"], x["count"]))
    for x in raw["stuckLevels"]:
        say("  卡关：%s · %s 失败 %d / 尝试 %d" % (x["unitName"], x["levelName"], x["fails"], x["attempts"]))
    for x in raw["wrongQuestions"]:
        say("  易错题：Q#%s %s | 错 %d 人 / 错 %d 次 / 作答 %d 次"
            % (x["questionId"], x["stemPreview"], x["wrongStudents"], x["wrongCount"], x["answerCount"]))
    return raw


# ================================================================ 窗口边界
def section_window(raw):
    h.section("② 窗口 = 今天 00:00 → 现在：左边界计入、昨天 23:59:59 排除")
    ids = ",".join(str(v) for v in sid.values())
    inwin = int(sql1("select count(*) from attempts where started_at >= CURDATE() "
                     "and started_at < NOW(3) and user_id in (%s)" % ids))
    h.eq(inwin, 10, "窗口内 attempt 恰是今天那 10 条（昨天那条不在内）")
    boundary = int(sql1("select count(*) from attempts a join users u on u.id=a.user_id "
                        "where u.username='S11A04' and a.started_at = CURDATE()"))
    h.eq(boundary, 1, "A4 那条 started_at = 今天 00:00:00 整的 attempt 确实落在左边界上")
    q1 = [x for x in raw["wrongQuestions"] if x["questionId"] == q[1]["id"]][0]
    h.eq((q1["wrongStudents"], q1["answerCount"]), (3, 6),
         "Q1 仍是错 3 人 / 作答 6 次（若昨天那条被算进来会变成 4/7）")
    l2 = [x for x in raw["stuckLevels"] if x["levelId"] == lv[2]["id"]][0]
    h.eq(l2["attempts"], 3, "「词汇二」今天尝试 3 次（含 00:00:00 那条 in_progress）")


# ================================================================ ③ 权限
def section_auth():
    h.section("③ 权限：学生 403（连发 10 次无断连）、无 token 401、他师 404、学生侧无出口")
    stu_tok = env["students"]["A1"]["token"]
    probes = probe_many("GET", "/admin/live?classId=%d" % env["class"]["id"], token=stu_tok, times=10)
    codes = sorted({st for st, _ in probes})
    biz = sorted({c for _, c in probes if c is not None})
    h.eq(len(probes), 10, "学生越权请求连发 10 次全部拿到回执（无断连）")
    h.eq(codes, [403], "10 次 HTTP 码全是 403")
    h.eq(biz, [40301], "10 次业务码全是 40301（无权访问）")

    st, p = req("GET", "/admin/live")
    h.eq((st, code_of(p)), (401, 40101), "不带 token → 401/40101")

    other = env["otherTeacher"]["token"]
    st, p = req("GET", "/admin/live?classId=%d" % env["class"]["id"], token=other)
    h.eq((st, code_of(p)), (404, 40401), "别的老师指名我的班 → 404（不给可枚举信号）")
    st, p = req("GET", "/admin/live", token=other)
    h.eq((st, code_of(p)), (400, 40001), "他师名下无班且不给 classId → 400「请指定班级」（不猜班）")

    st, p = req("GET", "/admin/live", token=env["teacher"]["token"])
    h.eq((st, code_of(p)), (200, 0), "任课教师不给 classId → 200（落到自己第一个班，冷启动口径）")
    h.eq(data_of(p)["classId"], env["class"]["id"], "缺省落到的班就是 S11验收1班")
    st, p = req("GET", "/admin/live?classId=%d" % env["class"]["id"], token=env["admin"]["token"])
    h.eq((st, code_of(p)), (200, 0), "校级看任意班 → 200")

    # 学生侧白名单：大屏数据在 /api/admin/* 之外一处都不给（防压力设计是硬要求）
    for path in ("/live", "/quiz/live", "/student/live", "/me/live"):
        st, _ = req("GET", path, token=stu_tok)
        h.eq(st, 404, "学生端 %s 不存在（404，白名单外）" % path)


# ================================================================ ④ 防压力：无身份字段
#
# 两条互补的机械检查：
#   1. 白名单：整段 JSON 的**键路径集合**必须与下面这张表完全相等——将来谁往 DTO 里加
#      一个字段（哪怕叫 victimName），这条断言立刻红。这是最强的一条。
#   2. 黑名单：递归扫身份类键名（classes 子树除外——班级切换带的是班名，不是学生），
#      再加字节级：5 个学号/姓名一个字都不许出现在响应里。
EXPECTED_KEYS = sorted([
    ("root.classId"), ("root.className"), ("root.generatedAt"), ("root.dayStart"),
    ("root.refreshSeconds"),
    # 五个容器键也要在位：键路径集合是"完全相等"的口径，多一个对象层同样会红
    ("root.participation"), ("root.progress"), ("root.stuckLevels"),
    ("root.wrongQuestions"), ("root.classes"),
    ("root.participation.started"), ("root.participation.total"), ("root.participation.rate"),
    ("root.progress[].levelId"), ("root.progress[].levelName"), ("root.progress[].unitName"),
    ("root.progress[].count"),
    ("root.stuckLevels[].levelId"), ("root.stuckLevels[].levelName"), ("root.stuckLevels[].unitName"),
    ("root.stuckLevels[].attempts"), ("root.stuckLevels[].fails"),
    ("root.wrongQuestions[].questionId"), ("root.wrongQuestions[].type"),
    ("root.wrongQuestions[].stemPreview"), ("root.wrongQuestions[].knowledgeTag"),
    ("root.wrongQuestions[].answerCount"), ("root.wrongQuestions[].wrongCount"),
    ("root.wrongQuestions[].wrongStudents"),
    ("root.classes[].id"), ("root.classes[].name"), ("root.classes[].studentCount"),
    ("root.classes[].term"),
])
WRONG_KEYS = {"questionId", "type", "stemPreview", "knowledgeTag",
              "answerCount", "wrongCount", "wrongStudents"}
BANNED_KEYS = {"userId", "user_id", "studentId", "student_id", "students", "username",
               "userName", "realName", "name", "nickname", "avatar", "avatarUrl", "uid"}
# classes 子树是「顶栏班级切换」，与看板同一处带出：里面有 id/name，但那是班级，不是学生。
CLASS_BRIEF_KEYS = {"id", "name", "studentCount", "term"}


def key_paths(node, path="root"):
    """把整段 JSON 的键路径归一化成 root.a.b[] 形式（数组下标抹平成 []）。"""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = path + "." + k
            out.append(p)
            out.extend(key_paths(v, p))
    elif isinstance(node, list):
        for v in node:
            out.extend(key_paths(v, path + "[]"))
    return out


def walk_keys(node, path="root"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield path + "." + k, k
            yield from walk_keys(v, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_keys(v, "%s[%d]" % (path, i))


def section_privacy(raw):
    h.section("④ 防压力设计：大屏 JSON 里没有任何学生身份字段")
    st, buf = req("GET", "/admin/live?classId=%d" % env["class"]["id"],
                  token=env["teacher"]["token"], raw=True)
    text = buf.decode("utf-8")

    got = sorted(set(key_paths(raw)))
    h.eq(got, EXPECTED_KEYS, "整段 JSON 的键路径集合与白名单完全相等（多一个字段就红）")

    # 黑名单扫描跳过 classes 子树（班级切换件里 name=班级名，与"不点名"无关）
    hits = [(p, k) for p, k in walk_keys(raw) if k in BANNED_KEYS and not p.startswith("root.classes")]
    h.eq(hits, [], "递归扫全 JSON：没有学生身份类键名（%s）" % "、".join(sorted(BANNED_KEYS)))

    briefs = raw.get("classes") or []
    h.check(all(set(b.keys()) == CLASS_BRIEF_KEYS for b in briefs),
            "班级切换件只带 {id,name,studentCount,term}（班名而已）",
            "实际 %r" % (sorted(briefs[0].keys()) if briefs else None,))

    keysets = [set(x.keys()) for x in raw["wrongQuestions"]]
    h.check(all(s == WRONG_KEYS for s in keysets),
            "易错题榜每条的键集合完全相等且只有 7 个题/数字字段",
            "实际 %r" % (sorted(keysets[0]) if keysets else None,))

    # 字节级：5 个学号与 5 个姓名一个字都不许出现（夹具姓名刻意带「测试S11A」前缀）
    leaks = [u for u, info in env["students"].items() if u in text]
    leaks += [info["name"] for info in env["students"].values() if info["name"] in text]
    leaks += ["测试S11A"] if "测试S11A" in text else []
    h.eq(leaks, [], "整段响应字节里不含任何学号/姓名（含共有前缀「测试S11A」）")
    h.eq(text.count("S11A"), 0, "「S11A」这个学号片段在响应里出现 0 次")


# ================================================================ ⑤ 刷新间隔可配置
def section_config(raw):
    h.section("⑤ 刷新间隔：默认 10s，且由服务端配置（LIVE_REFRESH_SECONDS）")
    h.eq(raw["refreshSeconds"], 10, "8080 默认实例下发 refreshSeconds=10")
    if not ALT_BASE:
        h.check(False, "第二实例（8081）未起，无法证明「可配置」", "S11_ALT_BASE 为空")
        return
    st, p = req("GET", "/admin/live", token=env["teacher"]["token"], base=ALT_BASE)
    h.eq((st, code_of(p)), (200, 0), "8081 实例（LIVE_REFRESH_SECONDS=3）接口可用")
    h.eq(data_of(p)["refreshSeconds"], 3, "8081 下发 refreshSeconds=3（环境变量真的生效）")
    h.eq(data_of(p)["participation"], raw["participation"], "两台实例对同一个班读数一致（同一份数据）")


# ================================================================ ⑥ 回归：既有接口与不变量
def section_regression():
    h.section("⑥ 回归：新增一条路由没搅乱教师端命名空间（S10/S10.5 的接口仍正常）")
    tok = env["teacher"]["token"]
    cid = env["class"]["id"]
    probe = [
        ("GET", "/admin/dashboard?classId=%d" % cid),
        ("GET", "/admin/students?classId=%d" % cid),
        ("GET", "/admin/papers?classId=%d" % cid),
        ("GET", "/admin/bank/questions?classId=%d&source=mine" % cid),
        ("GET", "/admin/bank/units?classId=%d&source=mine" % cid),
        ("GET", "/admin/audit-logs?page=1&pageSize=5"),
    ]
    for method, path in probe:
        st, p = req(method, path, token=tok)
        h.eq((st, code_of(p)), (200, 0), "%s %s 仍 200" % (method, path))

    st, p = req("GET", "/admin/school/overview", token=env["admin"]["token"])
    h.eq((st, code_of(p)), (200, 0), "校级汇总（admin）仍 200")

    # 我的班没有野卷：S11 只加大屏，不该有 week_no>=100 的卷单元冒出来
    papers = data_of(req("GET", "/admin/papers?classId=%d" % cid, token=tok)[1])
    h.eq(papers["total"], 0, "S11验收1班名下没有卷（大屏不产生卷单元）")

    # 大屏读接口不改任何东西：连打两次，库里 attempt/answer 行数与底账一致
    a0 = sql1("select count(*) from attempts")
    b0 = sql1("select count(*) from attempt_answers")
    for _ in range(2):
        req("GET", "/admin/live?classId=%d" % cid, token=tok)
    h.eq((sql1("select count(*) from attempts"), sql1("select count(*) from attempt_answers")),
         (a0, b0), "连打两次大屏接口后 attempt/attempt_answers 行数没变（纯读）")


# ================================================================ ⑨ 收尾
def section_final():
    h.section("⑨ 收尾：底账与留库清单")
    tables = int(sql1("select count(*) from information_schema.tables where table_schema='cet46'"))
    cols = int(sql1("select count(*) from information_schema.columns where table_schema='cet46'"))
    h.eq((tables, cols), (17, 128), "收尾时表/列红线仍是 17/128")
    j = (" from questions qq join levels ll on ll.id=qq.level_id "
         "join units uu on uu.id=ll.unit_id join classes cc on cc.id=uu.class_id")
    crc = int(sql1("select sum(crc32(concat(qq.id, 0x1f, coalesce(qq.stem,''), 0x1f, "
                  "coalesce(qq.options_json,'')))) % 4294967296" + j +
                  " where cc.name not in " + OTHERS))
    h.eq(crc, BANK_CRC_S9, "收尾时别人题库 CRC 仍是 %d" % BANK_CRC_S9)

    say("  ---- 留库清单（供 Claude 复验点名）----")
    say("  班 %s id=%d；单元 id=%s；关 %s；题 %s"
        % (env["class"]["name"], env["class"]["id"],
           sql1("select id from units where class_id=%d" % env["class"]["id"]),
           [v["id"] for v in lv.values()], [v["id"] for v in q.values()]))
    say("  学生：%s" % "、".join("%s(id=%d)" % (u, sid[k]) for k, u in
                               [(k, v["username"]) for k, v in env["students"].items()]))
    say("  今天 attempt：%s 条 / 其中昨天的对照：%s 条"
        % (sql1("select count(*) from attempts where started_at >= CURDATE()"),
           sql1("select count(*) from attempts where started_at < CURDATE() and user_id in (%s)"
                % ",".join(str(v) for v in sid.values()))))
    h.check(True, "留库清单已打印（夹具故意留着：三指标的证据在库里）")


def main():
    load_env()
    show_hand_table()
    section_baseline()
    raw = section_metrics()
    section_window(raw)
    section_auth()
    section_privacy(raw)
    section_config(raw)
    section_regression()
    section_final()
    total, failed = h.result()
    with open(os.path.join(HERE, "99-summary.txt"), "w", encoding="utf-8") as f:
        f.write("%d %d\n" % (total, failed))
    say("写出 99-summary.txt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())