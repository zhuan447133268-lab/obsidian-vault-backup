"""S10 验收环境搭建：账号 / 班级学生 / 题库 / 学生真实闯关数据。

为什么不用现成的 dev 数据：S10 验收要「逐字段对账」（导出 xlsx 的每一列都能被独立算出），
需要一个自己完全掌握底账的班——几个学生、答对几题、错在哪个知识点，全都是我自己放进去的数，
对账时才能一分不差地核对，而不是"看起来差不多"。

产物落 s10-env.json（账号 / 班级 / 关卡 / 学生 token），后续验收脚本读它。
"""
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s10_lib import NEWPWD, Fail, code_of, data_of, login, multipart, req, say, sql, sql1, sql_int  # noqa: E402
import s10_bank  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "s10-env.json")

ADMIN = ("A9001", "校级教务")
TEA = ("T9001", "张老师A")     # 验收教师 A（两个班）
TEB = ("T9002", "李老师B")     # 验收教师 B（跨员越权测试用）
INIT = "Init@2026"

CLASS_A = "S10验收1班"
CLASS_A2 = "S10验收2班"
CLASS_B = "S10验收3班"

STUDENTS_A = [("S10A01", "陈一帆"), ("S10A02", "李晓萌"), ("S10A03", "赵梓豪"),
              ("S10A04", "刘思远"), ("S10A05", "孙可欣"), ("S10A06", "王小鱼")]
STUDENTS_A2 = [("S10A11", "周子墨"), ("S10A12", "吴雨桐"), ("S10A13", "郑凯文")]
STUDENTS_B = [("S10B01", "黄子轩"), ("S10B02", "徐若曦")]

# 每生的作答计划：level_seq → 答对题数（None=不做）。留白的学生天然命中「预警」。
# 通关口径：整卷答满即 finished（≥60% 两星、≥90% 三星），所以这里都算通关。
PLAN = {
    "S10A01": {1: 5, 2: 5, 3: 4},
    "S10A02": {1: 5, 2: 3},
    "S10A03": {1: 4},
    "S10A04": {1: 3},
    "S10A05": {},
    "S10A06": {},
}
PLAN_A2 = {"S10A11": {1: 5}}


SERVER_DIR = r"D:\claude-work\cet46-game\server"   # 原生 python 不认 MSYS 的 /d/... 路径
SEED_EXE = os.path.join(HERE, "s10-seed-teacher.exe")


def sh(args):
    out = subprocess.run(args, capture_output=True, cwd=SERVER_DIR)
    text = out.stdout.decode("utf-8", "replace") + out.stderr.decode("utf-8", "replace")
    if out.returncode != 0:
        raise Fail("命令失败 %s\n%s" % (" ".join(args), text))
    return text


def seed_accounts():
    """建 admin / 两个教师：admin 只能由 CLI 造（教师 API 不允许建 admin）。

    跑的是事先编好的 bin（bash 侧 `go build ./cmd/seed-teacher`），
    不在 python 里调 `go run`——原生 python 既找不到 MSYS 的 go，也不认 cwd 里的 /d/... 路径。
    """
    for (u, name), role in ((ADMIN, "admin"), (TEA, "teacher"), (TEB, "teacher")):
        sh([SEED_EXE, "-username", u, "-name", name, "-password", INIT, "-role", role])
        say("  建账号 %s(%s) role=%s" % (u, name, role))


def import_roster(token, class_name, students):
    """导入名单（班级不存在时自动建）。初始密码整列写死，避免依赖"默认取学号"的隐式口径。

    已有同名学号时跳过——setup 要能反复跑（首跑中途失败是常态），
    否则第二次跑会被「学号已存在」整份驳回。
    """
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
    s10_bank.main(xlsx, class_name)
    st, p = multipart("/admin/import-questions", token, xlsx)
    if st != 200 or code_of(p) != 0:
        raise Fail("导入题库失败 %s: %s" % (class_name, p))
    d = data_of(p)
    say("  导入题库 %s：单元 %s / 关卡 %s / 题 %s（跳过重复 %s）"
        % (class_name, d.get("units"), d.get("levels"), d.get("questions"), d.get("skipped")))
    return d


def student_id(username):
    return sql_int("select id from users where username='%s'" % username)


def class_id(name):
    return sql_int("select id from classes where name='%s' order by id desc limit 1" % name)


def level_map(clss_id):
    """该班的关卡：seq → (id, name, question_count)。"""
    rows = sql("select lv.seq,lv.id,lv.name,(select count(*) from questions q where q.level_id=lv.id) "
               "from levels lv join units un on un.id=lv.unit_id "
               "where un.class_id=%d order by lv.seq" % clss_id)
    return {int(r[0]): (int(r[1]), r[2], int(r[3])) for r in rows}


def answers_for(paper, correct_n):
    """按题库底账作答：前 correct_n 题答对（选正确项的展示坐标），其余故意选错项。

    正确项的展示坐标：DB 里 answer_idx 是原卷下标（本题库全是 0=A），
    取原选项文本，再在卷面下发（已洗序）的 options 里找它的位置——
    前端也是这么定位的，服务端不认"第几个选项"，只认展示坐标。
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
    """学生登录：先试初始密码（首登会要求改密 → 改到统一口令），再试已改过的口令。

    允许重跑：seed 出来的账号密码是 INIT，跑过一次的学生是 NEWPWD，两种都要认。
    """
    st, p = req("POST", "/auth/login", body={"username": username, "password": INIT})
    if st == 200 and code_of(p) == 0:
        token = data_of(p)["token"]
        if data_of(p)["user"].get("mustChangePwd"):
            st2, p2 = req("POST", "/auth/chpwd", token=token,
                          body={"oldPassword": INIT, "newPassword": NEWPWD})
            if st2 != 200 or code_of(p2) != 0:
                raise Fail("学生首登改密失败 %s: %s" % (username, p2))
        else:
            st2, p2 = req("POST", "/auth/chpwd", token=token,
                          body={"oldPassword": INIT, "newPassword": NEWPWD})
            if st2 != 200:
                raise Fail("学生改密失败 %s: %s" % (username, p2))
        st3, p3 = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
        if st3 != 200 or code_of(p3) != 0:
            raise Fail("学生改密后登录失败 %s: %s" % (username, p3))
        return data_of(p3)["token"], data_of(p3)["user"]
    st, p = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
    if st == 200 and code_of(p) == 0:
        return data_of(p)["token"], data_of(p)["user"]
    raise Fail("学生登录失败 %s: %s" % (username, p))


def main():
    say("== S10 验收环境搭建 ==")
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

    say("-- 学生真实闯关（产生看板/趋势/薄弱点数据）--")
    lv_a = level_map(class_id(CLASS_A))
    done = sql_int("select count(*) from attempts a join users su on su.id=a.user_id "
                   "where su.username in (%s) and a.status='finished'"
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
        "students": {},
        "passwd": {"init": INIT, "now": NEWPWD},
    }
    for u, n in STUDENTS_A + STUDENTS_A2 + STUDENTS_B:
        env["students"][u] = {"id": student_id(u), "name": n, "token": stokens[u]}

    with io.open(ENV, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    say("\n环境就绪 → %s" % ENV)
    say("班级 id：%s=%d / %s=%d / %s=%d"
        % (CLASS_A, env["classes"][CLASS_A]["id"], CLASS_A2, env["classes"][CLASS_A2]["id"],
           CLASS_B, env["classes"][CLASS_B]["id"]))
    return env


if __name__ == "__main__":
    main()