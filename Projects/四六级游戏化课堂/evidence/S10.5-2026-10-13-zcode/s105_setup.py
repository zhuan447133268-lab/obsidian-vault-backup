"""S10.5 验收环境搭建：账号 / 班级学生 / 题库 / 学生真实闯关数据。

为什么不用现成的 dev 数据：S10.5 验收要「逐条对账」——
  · 卷里的每一道题都得能追回它的来源（哪个班哪个单元的哪一行）；
  · 「练习卷不进联赛」要能对比「打练习前后，本周努力值一个字没动」；
  · 「同卷不同班」要比对两班副本的每一行内容。
自己掌握底账，这些才核得动，而不是"看起来差不多"。

产物落 s105-env.json（账号 / 班级 / 关卡 / 学生 token / 题库题号），后续验收脚本读它。
"""
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s105_lib import NEWPWD, Fail, code_of, data_of, login, multipart, req, say, sql, sql1, sql_int  # noqa: E402
import s105_bank  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "s105-env.json")

ADMIN = ("A9101", "校级教务S105")
TEA = ("T9101", "王一鸣")      # 组卷教师 A（宿主班 + 第二个班）
TEB = ("T9102", "李思远")      # 组卷教师 B（跨教师权限与公共题库）
INIT = "Init@2026"

CLASS_A = "S10.5验收1班"
CLASS_A2 = "S10.5验收2班"
CLASS_B = "S10.5验收3班"

STUDENTS_A = [("S105A01", "陈一鸣"), ("S105A02", "李晓萌"), ("S105A03", "赵梓豪"), ("S105A04", "刘思远")]
STUDENTS_A2 = [("S105A11", "周子墨"), ("S105A12", "吴雨桐")]
STUDENTS_B = [("S105B01", "黄子轩"), ("S105B02", "徐若曦")]

# 教学关的作答计划：level_seq → 答对题数（None=不做）。
# 只要有「首刷」记录，联赛"本周努力值"就有底账，练习卷打完之后才有东西可比。
PLAN = {
    "S105A01": {1: 2, 2: 3},    # 2 关首刷（听力 2/2、词汇 3/3）
    "S105A02": {1: 1},          # 1 关首刷（听力 1/2）
}
PLAN_A2 = {"S105A11": {1: 2}}

SERVER_DIR = r"D:\claude-work\cet46-game\server"   # 原生 python 不认 MSYS 的 /d/... 路径
SEED_EXE = os.path.join(HERE, "s105-seed-teacher.exe")


def sh(args):
    out = subprocess.run(args, capture_output=True, cwd=SERVER_DIR)
    text = out.stdout.decode("utf-8", "replace") + out.stderr.decode("utf-8", "replace")
    if out.returncode != 0:
        raise Fail("命令失败 %s\n%s" % (" ".join(args), text))
    return text


def seed_accounts():
    """建 admin / 两个教师：admin 只能由 CLI 造（教师 API 不允许建 admin）。"""
    for (u, name), role in ((ADMIN, "admin"), (TEA, "teacher"), (TEB, "teacher")):
        if sql_int("select count(*) from users where username='%s'" % u) == 0:
            sh([SEED_EXE, "-username", u, "-name", name, "-password", INIT, "-role", role])
        say("  账号 %s(%s) role=%s 就绪" % (u, name, role))


def import_roster(token, class_name, students):
    """导入名单（班级不存在时自动建，建出来的班归导入者）。要能反复跑，已存在就跳过。"""
    existing = sql_int("select count(*) from users where username in (%s)"
                       % ",".join("'%s'" % u for u, _ in students))
    if existing == len(students):
        say("  名单 %s 已在库（%d 人），跳过" % (class_name, existing))
        return None
    path = os.path.join(HERE, "_roster_%s.csv" % class_name)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write("班级,学号,姓名,初始密码\r\n")
        for u, n in students:
            f.write("%s,%s,%s,%s\r\n" % (class_name, u, n, INIT))
    st, p = multipart("/admin/import-users", token, path)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入名单失败 %s: %s" % (class_name, p))
    d = data_of(p)
    say("  导入 %s：新建 %s / 更新 %s（%s）" % (class_name, d.get("created"), d.get("updated"),
                                                d.get("className")))
    return d


def import_bank(token, class_name):
    cid = class_id(class_name)
    if cid and sql_int("select count(*) from levels lv join units un on un.id=lv.unit_id "
                       "where un.class_id=%d" % cid) > 0:
        say("  题库 %s 已在库，跳过" % class_name)
        return None
    xlsx = os.path.join(HERE, "_bank_%s.xlsx" % class_name)
    s105_bank.main(xlsx, class_name)
    st, p = multipart("/admin/import-questions", token, xlsx)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入题库失败 %s: %s" % (class_name, p))
    d = data_of(p)
    say("  导入题库 %s：新建单元 %s / 新建关卡 %s / 新建题 %s（跳过重复 %s，共 %s 行）"
        % (class_name, d.get("unitCreated"), d.get("levelCreated"), d.get("created"),
           d.get("skipped"), d.get("total")))
    return d


def student_id(username):
    return sql_int("select id from users where username='%s'" % username)


def class_id(name):
    return sql_int("select id from classes where name='%s' order by id desc limit 1" % name)


def level_map(clss_id, band="4"):
    """该班的教学关卡：seq → (id, name, question_count)。

    只看 band 那份（默认四级）：验收班的题库里还有一份六级单元（用来撞"分套不匹配"两条规则），
    它的关卡 seq 同样从 1 起——不过滤就会把四级的 seq=1 覆盖成六级那一关（实跑踩过）。
    """
    rows = sql("select lv.seq,lv.id,lv.name,(select count(*) from questions q where q.level_id=lv.id) "
               "from levels lv join units un on un.id=lv.unit_id "
               "where un.class_id=%d and un.week_no < 100 "
               "and exists (select 1 from questions q2 where q2.level_id=lv.id and q2.band='%s') "
               "order by un.week_no, lv.seq" % (clss_id, band))
    return {int(r[0]): (int(r[1]), r[2], int(r[3])) for r in rows}


def answers_for(paper, correct_n):
    """按题库底账作答：前 correct_n 题答对（选正确项的展示坐标），其余故意选错项。

    正确项的展示坐标：DB 里 answer_idx 是原卷下标（本题库全是 0=A），
    取原选项文本，再在卷面下发（已洗序）的 options 里找它的位置——
    服务端不认"第几个选项"，只认展示坐标。
    """
    out = []
    for i, q in enumerate(paper["questions"]):
        orig = sql1("select options_json from questions where id=%d" % q["id"])
        texts = json.loads(orig)
        correct_orig = int(sql1("select answer_idx from questions where id=%d" % q["id"]) or 0)
        correct_text = texts[correct_orig]
        idx = q["options"].index(correct_text)
        if i >= correct_n:
            idx = (idx + 1) % len(q["options"])
        out.append({"questionId": q["id"], "pickedIdx": str(idx), "elapsedMs": 1500})
    return out


def run_level(token, seq_levels, seq, correct_n):
    """真跑一关：取卷 → 按计划作答 → 交卷。返回结算。"""
    lid = seq_levels[seq][0]
    st, p = req("GET", "/quiz/paper?level=%d" % lid, token=token)
    if st != 200 or code_of(p) != 0:
        raise Fail("取卷失败 level=%d: %s" % (lid, p))
    paper = data_of(p)
    ans = answers_for(paper, correct_n)
    st2, p2 = req("POST", "/quiz/submit", token=token,
                  body={"attemptId": paper["attemptId"], "answers": ans})
    if st2 != 200 or code_of(p2) != 0:
        raise Fail("交卷失败 level=%d: %s" % (lid, p2))
    s = data_of(p2).get("settlement") or {}
    say("    关 %d（%s）：答对 %s/%s，XP +%s，星级 %s"
        % (seq, seq_levels[seq][1], s.get("correct"), s.get("total"), s.get("xpTotal"), s.get("stars")))
    return s


def student_login(username):
    """学生登录：先试初始密码（首登会要求改密 → 改到统一口令），再试已改过的口令。"""
    st, p = req("POST", "/auth/login", body={"username": username, "password": INIT})
    if st == 200 and code_of(p) == 0:
        token = data_of(p)["token"]
        st2, p2 = req("POST", "/auth/chpwd", token=token,
                      body={"oldPassword": INIT, "newPassword": NEWPWD})
        if st2 != 200 or code_of(p2) != 0:
            raise Fail("学生首登改密失败 %s: %s" % (username, p2))
        st3, p3 = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
        if st3 != 200 or code_of(p3) != 0:
            raise Fail("学生改密后登录失败 %s: %s" % (username, p3))
        return data_of(p3)["token"], data_of(p3)["user"]
    st, p = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
    if st == 200 and code_of(p) == 0:
        return data_of(p)["token"], data_of(p)["user"]
    raise Fail("学生登录失败 %s: %s" % (username, p))


def main():
    say("== S10.5 验收环境搭建 ==")
    seed_accounts()

    admin_token, _, _ = login(ADMIN[0], INIT, must_change=True)
    tea_token, tea_user, _ = login(TEA[0], INIT, must_change=True)
    teb_token, teb_user, _ = login(TEB[0], INIT, must_change=True)
    say("  登录：admin/教师A/教师B 均完成首登改密 → %s" % NEWPWD)

    say("-- 导入班级与名单 --")
    import_roster(tea_token, CLASS_A, STUDENTS_A)
    import_roster(tea_token, CLASS_A2, STUDENTS_A2)
    import_roster(teb_token, CLASS_B, STUDENTS_B)

    say("-- 导入题库 --")
    import_bank(tea_token, CLASS_A)
    import_bank(tea_token, CLASS_A2)
    import_bank(teb_token, CLASS_B)

    say("-- 学生首次登录改密 --")
    stokens = {}
    for u, n in STUDENTS_A + STUDENTS_A2 + STUDENTS_B:
        tok, user = student_login(u)
        stokens[u] = tok
    say("  %d 名学生完成首登改密" % len(stokens))

    say("-- 学生真实闯关（产生首刷底账，供「练习卷不进联赛」对照）--")
    lv_a = level_map(class_id(CLASS_A))
    lv_a2 = level_map(class_id(CLASS_A2))
    done = sql_int("select count(*) from attempts a join users su on su.id=a.user_id "
                   "where su.username in (%s) and a.status='finished' and a.finished_at is not null"
                   % ",".join("'%s'" % u for u, _ in STUDENTS_A))
    if done > 0:
        say("  已有 %d 条已完成闯关，跳过（重跑不叠加数据）" % done)
    else:
        for u, plan in PLAN.items():
            say("   学生 %s：" % u)
            for seq, ok in sorted(plan.items()):
                run_level(stokens[u], lv_a, seq, ok)
        lv_a2 = level_map(class_id(CLASS_A2))
        for u, plan in PLAN_A2.items():
            say("   学生 %s：" % u)
            for seq, ok in sorted(plan.items()):
                run_level(stokens[u], lv_a2, seq, ok)

    # 题库题号：组卷时要能够指出"我引的是哪几道题"，所以把底账写进 env。
    bank = {}
    for cls, cid in ((CLASS_A, class_id(CLASS_A)), (CLASS_A2, class_id(CLASS_A2)),
                     (CLASS_B, class_id(CLASS_B))):
        rows = sql("select un.week_no, un.id, un.name, q.id from questions q "
                   "join levels lv on lv.id=q.level_id join units un on un.id=lv.unit_id "
                   "where un.class_id=%d order by un.week_no, lv.seq, q.id" % cid)
        bank[cls] = {
            "units": {},
            "questions": [int(r[3]) for r in rows],
        }
        for r in rows:
            bank[cls]["units"].setdefault("%s|%s" % (r[0], r[1]), {"weekNo": int(r[0]),
                                                                  "unitId": int(r[1]), "name": r[2],
                                                                  "questions": []})
            bank[cls]["units"]["%s|%s" % (r[0], r[1])]["questions"].append(int(r[3]))

    env = {
        "admin": {"username": ADMIN[0], "token": admin_token},
        "teacherA": {"username": TEA[0], "name": TEA[1], "id": tea_user["id"], "token": tea_token},
        "teacherB": {"username": TEB[0], "name": TEB[1], "id": teb_user["id"], "token": teb_token},
        "classes": {
            CLASS_A: {"id": class_id(CLASS_A), "levels": {str(k): list(v) for k, v in lv_a.items()}},
            CLASS_A2: {"id": class_id(CLASS_A2), "levels": {str(k): list(v) for k, v in lv_a2.items()}},
            CLASS_B: {"id": class_id(CLASS_B),
                      "levels": {str(k): list(v) for k, v in level_map(class_id(CLASS_B)).items()}},
        },
        "bank": bank,
        "students": {},
        "passwd": {"init": INIT, "now": NEWPWD},
    }
    for u, n in STUDENTS_A + STUDENTS_A2 + STUDENTS_B:
        env["students"][u] = {"id": student_id(u), "name": n, "token": stokens[u],
                              "classId": sql_int("select class_id from users where username='%s'" % u)}

    with io.open(ENV, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    say("\n环境就绪 → %s" % ENV)
    for cls in (CLASS_A, CLASS_A2, CLASS_B):
        say("  %s id=%d 教学关 %d 个 / 题库题 %d 道"
            % (cls, env["classes"][cls]["id"], len(env["classes"][cls]["levels"]),
               len(bank[cls]["questions"])))
    return env


if __name__ == "__main__":
    main()