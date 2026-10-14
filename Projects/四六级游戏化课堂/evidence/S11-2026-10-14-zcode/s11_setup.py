"""S11 验收环境搭建：教师 / 班级 / 5 名学生 / 题库（1 单元 3 关 6 题）+ 今天 10 条 attempt。

为什么自己掌握这几条 attempt 的每一条：S11 验收①要「三指标 + 易错题榜与手算一致」——
手算的前提是数据是**我按计划摆的**，每一条错在哪里都写在纸面上（见 s11_accept.py 的 PLAN）。
所以这里不用随机数据、不走随机作答，而是按固定计划直接落 attempts / attempt_answers。

刻意的两条：
  · **不写 xp_ledger**：XP 的唯一权威是 xp_ledger（S9 口径），大屏根本不读 XP。
    夹具只碰「今天窗口里的 attempt 行」，联赛/数值口径一行不动 —— 这也让底账回归更干净。
  · 昨天 23:59:59 摆一条 A05 的 attempt、今天 00:00:00 摆一条 A04 的 attempt：
    一前一后卡住窗口的两个边界（窗口 = 今天 00:00 → 现在）。

产物 s11-env.json（账号 / 班级 / 关 / 题 / token / attempt 清单），验收脚本读它。
可反复跑：每次先把上一轮自己的数据清干净再重建（先清后算）。
"""
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s11_lib import Fail, NEWPWD, code_of, data_of, login, multipart, say, sql, sql1, sql_int  # noqa: E402
import s11_bank  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "s11-env.json")

ADMIN = ("A1101", "校级教务S11")
TEA = ("T1101", "S11验收教师")
TEB = ("T1102", "S11无关教师")   # 名下没有任何班：用来验「归属」与「缺省班」两条拒绝路径
INIT = "Init@2026"

CLASS = "S11验收1班"
STUDENTS = [("S11A01", "测试S11A一号"), ("S11A02", "测试S11A二号"), ("S11A03", "测试S11A三号"),
            ("S11A04", "测试S11A四号"), ("S11A05", "测试S11A五号")]
STU_IDS = {"A1": "S11A01", "A2": "S11A02", "A3": "S11A03", "A4": "S11A04", "A5": "S11A05"}

SERVER_DIR = r"D:\claude-work\cet46-game\server"   # 原生 python 不认 MSYS 的 /d/... 路径
SEED_EXE = os.environ.get("S11_SEED_EXE", "")

# 今天 10 条 attempt 的落库计划：(学生键, 关卡 seq, status, 作答 [(题号 seq, 是否答对)], 开始于多少分钟前)
# 与 s11_accept.py 的 PLAN 必须一致——那边是"手算"，这边是"照着手算摆数据"。
# 分钟数只影响"能不能算进今天"，不影响任何指标（指标只看 status 与对错）。
SEED_TODAY = [
    ("A1", 1, "finished", [(1, False), (2, True)], 180),
    ("A1", 1, "finished", [(1, True), (2, True)], 170),
    ("A1", 2, "failed", [(3, False), (4, True)], 150),
    ("A2", 1, "finished", [(1, False), (2, True)], 140),
    ("A2", 1, "finished", [(1, True), (2, True)], 130),
    ("A2", 3, "finished", [(5, True), (6, False)], 120),
    ("A3", 1, "finished", [(1, True), (2, False)], 100),
    ("A3", 2, "failed", [(3, False), (4, False)], 90),
    ("A4", 1, "failed", [(1, False), (2, True)], 60),
    ("A4", 2, "in_progress", [], None),          # None = 今天 00:00:00 整（窗口左边界）
]
# 昨天 23:59:59 的一条（窗口右外侧对照：被算进来就说明窗口错了）
SEED_YESTERDAY = [("A5", 1, "finished", [(1, False), (2, True)])]


def sh(args):
    out = subprocess.run(args, capture_output=True, cwd=SERVER_DIR)
    text = out.stdout.decode("utf-8", "replace") + out.stderr.decode("utf-8", "replace")
    if out.returncode != 0:
        raise Fail("命令失败 %s\n%s" % (" ".join(args), text))
    return text


def class_id(name):
    return sql_int("select id from classes where name='%s' order by id desc limit 1" % name)


def clean_previous():
    """先清后算：把上一轮自己的班级连同它的 attempt/单元整条链删掉（别人的班一律不碰）。"""
    cid = class_id(CLASS)
    if cid == 0:
        return 0
    uids = [r[0] for r in sql("select id from users where class_id=%d" % cid)]
    if uids:
        inlist = ",".join(uids)
        sql("delete aa from attempt_answers aa join attempts a on a.id=aa.attempt_id "
            "where a.user_id in (%s)" % inlist)
        sql("delete from attempts where user_id in (%s)" % inlist)
        sql("delete from users where id in (%s)" % inlist)
    uids = [r[0] for r in sql("select id from units where class_id=%d" % cid)]
    if uids:
        inlist = ",".join(uids)
        lvids = [r[0] for r in sql("select id from levels where unit_id in (%s)" % inlist)]
        if lvids:
            sql("delete from questions where level_id in (%s)" % ",".join(lvids))
            sql("delete from levels where id in (%s)" % ",".join(lvids))
        sql("delete from units where id in (%s)" % inlist)
    sql("delete from classes where id=%d" % cid)
    say("  清掉上一轮的 %s（id=%d）与其 %d 名学生、%d 个单元" % (CLASS, cid, len(uids), len(uids)))
    return 1


def seed_accounts():
    for (u, name), role in ((ADMIN, "admin"), (TEA, "teacher"), (TEB, "teacher")):
        if sql_int("select count(*) from users where username='%s'" % u) == 0:
            if not SEED_EXE:
                raise Fail("缺 S11_SEED_EXE（seed-teacher 可执行文件路径）")
            sh([SEED_EXE, "-username", u, "-name", name, "-password", INIT, "-role", role])
        say("  账号 %s(%s) role=%s 就绪" % (u, name, role))


def import_roster(token):
    path = os.path.join(HERE, "_roster_%s.csv" % CLASS)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("班级,学号,姓名,初始密码\r\n")
        for u, n in STUDENTS:
            f.write("%s,%s,%s,%s\r\n" % (CLASS, u, n, INIT))
    st, p = multipart("/admin/import-users", token, path)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入名单失败: %s" % (p,))
    d = data_of(p)
    say("  导入名单：新建 %s / 更新 %s（%s）" % (d.get("created"), d.get("updated"), d.get("className")))
    os.remove(path)


def import_bank(token):
    path = os.path.join(HERE, "_bank_%s.xlsx" % CLASS)
    s11_bank.main(path, CLASS)
    st, p = multipart("/admin/import-questions", token, path)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入题库失败: %s" % (p,))
    d = data_of(p)
    say("  导入题库：新建单元 %s / 关 %s / 题 %s（共 %s 行）"
        % (d.get("unitCreated"), d.get("levelCreated"), d.get("created"), d.get("total")))
    os.remove(path)


def insert_attempt(uid, lv, qmap, status, answers, start_expr, who):
    """落一条 attempt 与其作答行。start_expr 是 SQL 时间表达式（窗口边界由调用方写死）。"""
    correct = sum(1 for _, ok in answers if ok)
    total = len(answers)
    if status == "in_progress":
        fin = "NULL"
    else:
        # 交卷时刻固定取"开始 + 2 分钟"：只影响 finished_at，不影响任何大屏指标
        fin = "%s + INTERVAL 2 MINUTE" % start_expr
    sql("insert into attempts (user_id, level_id, unit_id, correct, total, stars, score710, "
        "xp_earned, shuffle_seed, status, started_at, finished_at) values "
        "(%d, %d, (select unit_id from levels where id=%d), %d, %d, 0, 0, 0, 7, '%s', %s, %s)"
        % (uid, lv["id"], lv["id"], correct, total, status, start_expr, fin))
    aid = sql_int("select id from attempts where user_id=%d and level_id=%d order by id desc limit 1"
                  % (uid, lv["id"]))
    for qseq, ok in answers:
        sql("insert into attempt_answers (attempt_id, question_id, picked_idx, is_correct, created_at) "
            "values (%d, %d, '0', %d, %s + INTERVAL 1 MINUTE)"
            % (aid, qmap[qseq]["id"], 1 if ok else 0, start_expr))
    say("    %s → L%d(%s) %s 答对 %d/%d @ %s" % (who, lv["seq"], lv["name"], status,
                                                correct, total, start_expr))


def main():
    say("== S11 验收环境搭建 ==")
    seed_accounts()
    tea_token = login(TEA[0], INIT, must_change=True)
    say("  教师 %s 登录成功（首登已改密 → %s）" % (TEA[0], NEWPWD))
    teb_token = login(TEB[0], INIT, must_change=True)
    admin_token = login(ADMIN[0], INIT, must_change=True)
    say("  无关教师 %s / 校级 %s 登录成功" % (TEB[0], ADMIN[0]))

    clean_previous()

    say("-- 班级与名单 --")
    import_roster(tea_token)
    cid = class_id(CLASS)
    say("  %s id=%d" % (CLASS, cid))

    say("-- 题库 --")
    import_bank(tea_token)

    lvrows = sql("select l.seq, l.id, l.name, u.name from levels l join units u on u.id=l.unit_id "
                 "where u.class_id=%d order by l.seq" % cid)
    levels = {}
    for seq, lid, lname, uname in lvrows:
        levels[int(seq)] = {"id": int(lid), "seq": int(seq), "name": lname, "unit": uname}
    qrows = sql("select l.seq, q.id, q.stem, q.knowledge_tag, q.type from questions q "
                "join levels l on l.id=q.level_id join units u on u.id=l.unit_id "
                "where u.class_id=%d order by l.seq, q.id" % cid)
    questions, qmap = [], {}
    for i, (seq, qid, stem, tag, qtype) in enumerate(qrows, start=1):
        questions.append({"seq": i, "id": int(qid), "levelSeq": int(seq), "stem": stem,
                          "tag": tag, "type": qtype})
        qmap[i] = questions[-1]
    say("  关卡 %d 个 / 题 %d 道：%s" % (len(levels), len(questions),
                                     "、".join("L%d %s" % (v["seq"], v["name"]) for v in levels.values())))

    say("-- 学生首登改密 --")
    stokens = {}
    for u, n in STUDENTS:
        stokens[u] = login(u, INIT, must_change=True)
    say("  %d 名学生完成首登改密" % len(stokens))

    say("-- 按手算计划落 attempt（今天 %d 条 + 昨天 1 条对照）--" % len(SEED_TODAY))
    sid_of = {k: sql_int("select id from users where username='%s'" % v) for k, v in STU_IDS.items()}
    for stu, seq, status, answers, mins in SEED_TODAY:
        start = "CURDATE()" if mins is None else "NOW(3) - INTERVAL %d MINUTE" % mins
        insert_attempt(sid_of[stu], levels[seq], qmap, status, answers, start,
                       "%s(%s)" % (stu, STU_IDS[stu]))
    for stu, seq, status, answers in SEED_YESTERDAY:
        insert_attempt(sid_of[stu], levels[seq], qmap, status, answers,
                       "CURDATE() - INTERVAL 1 SECOND",  # = 昨天 23:59:59，窗口右外侧
                       "%s(%s)【昨天对照】" % (stu, STU_IDS[stu]))

    env = {
        "base": "http://127.0.0.1:8080/api",
        "teacher": {"username": TEA[0], "id": sql_int("select id from users where username='%s'" % TEA[0]),
                    "token": tea_token},
        "otherTeacher": {"username": TEB[0], "token": teb_token},
        "admin": {"username": ADMIN[0], "token": admin_token},
        "class": {"name": CLASS, "id": cid, "studentTotal": len(STUDENTS)},
        "levels": {str(k): v for k, v in levels.items()},
        "questions": questions,
        "students": {k: {"username": v, "name": dict(STUDENTS)[v],
                         "id": sid_of[k], "token": stokens[v]} for k, v in STU_IDS.items()},
        "seeded": {"today": len(SEED_TODAY), "yesterday": len(SEED_YESTERDAY)},
        "passwd": {"init": INIT, "now": NEWPWD},
    }
    with io.open(ENV, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    say("\n环境就绪 → %s" % ENV)
    say("  %s：学生 %d 人 / 单元「%s」/ 关 %d 个 / 题 %d 道 / 今天 attempt %d 条"
        % (CLASS, len(STUDENTS), levels[1]["unit"], len(levels), len(questions), len(SEED_TODAY)))
    return env


if __name__ == "__main__":
    main()