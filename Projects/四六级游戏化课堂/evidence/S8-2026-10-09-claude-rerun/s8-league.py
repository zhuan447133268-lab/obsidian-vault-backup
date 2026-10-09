#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8 验收（班级联赛）真库实跑辅助：真 MySQL :3307 + 真服务 :8080。

三类数据面，口径分开对拍：
  ① 手算表（本文件里的 ROSTER12 / PLAN4 常量）—— 人肉按规则算出的期望值；
  ② SQL 独立聚合（本文件另写一份 SQL，不进 service 代码）—— 底账侧的事实；
  ③ 接口回执（GET /api/league/board、/api/league/me、POST /api/league/pk/check）。
三方一致才算过；浏览器 DOM 由 shell 侧另跑一轮（页面上必须真画出这些数）。

自建自清：只动 S8 自建的两个班（S8联赛验收班 / S8实跑班）、三个 PK 班与它们的学生，
以及这些班下的 units/levels/questions/attempts/xp_ledger/teams/seasons/audit 行。
不动 1 班/2 班/7 班/8 班，不动题库（1 班的题库指纹在 baseline 里比对）。

  python s8-league.py baseline     # 变量底账：17 表 / 128 列 / 1 班题库指纹
  python s8-league.py seed12       # 用例①：12 人班底账 + 小队（写 plan-hand12.json）
  python s8-league.py check12      # 用例①：逐字段对拍（写 board-hand12.json / me-*.json）
  python s8-league.py seed4        # 用例②③：4 人班与实跑关（写 plan-e2e4.json）
  python s8-league.py check4       # 用例②③：首刷/重刷混合 + 名额缩放 + 0 分不上榜
  python s8-league.py pk           # 验收③：同卷 / 异卷 / 无卷 / 班内（写 pk-*.json）
  python s8-league.py hidden       # 验收②：关闭排行 → 脱敏实录 → 打开（写 hidden-*.json）
  python s8-league.py settle       # 周结算 / 赛季结算 / 幂等（写 settle-*.json）
  python s8-league.py demo         # 整链收尾：把 12 人班拨回第 1 赛季 + 公开（对齐浏览器截图那一帧）
  python s8-league.py cleanup      # 清掉 S8 自建数据（要重跑就从这里开始）
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zlib

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'
# 库连接一律走 pymysql + server/.env（见 db_conn），不走 mysql CLI：CLI 要多一份密码环境变量，
# 且本机 curl/mysql 的编码与路径转码都会给中文验收添乱。

# 赛季网格的锚点：2026-01-05（周一）。测试侧独立一份，故意不从 quiz 包 import。
WEEK_EPOCH = dt.date(2026, 1, 5)
SEASON_WEEKS = 2

CLASS12 = 'S8联赛验收班'
CLASS4 = 'S8实跑班'
CLASS6 = 'S8并列验收班'
CLASSPK_SAME = 'S8-PK同卷班'
CLASSPK_DIFF = 'S8-PK异卷班'
CLASSPK_NOPAPER = 'S8-PK无卷班'
CLASSES = (CLASS12, CLASS4, CLASS6, CLASSPK_SAME, CLASSPK_DIFF, CLASSPK_NOPAPER)

STU_INIT = 'S8init2026'  # 名单里填的初始密码（显式填，避免默认用学号时撞长度规则）
STU_PWD = 'S8demo2026'   # 演示学生首登改密后的密码
TEACHER = 'T0001'
TEACHER_PWDS = ('Teacher@456', 'Teacher@123')

# ---------------- 用例①：12 人班的手算表（XP 数值刻意与原型 rank.html 同档） ----------------
# 名次（本周 XP 降序，竞争式并列不跳号）：1 陈940 / 2 李905 / 3 赵880 / 4 刘855 / 5 孙830 /
#   6 王790（我，差 40 XP 晋级线，与原型同数）/ 7 周760 / 8 吴720 / 9 郑660 / 10 林615 / 11 黄540 / 12 徐480
# 本周 12 人的 XP 与名次刻意**逐格照抄原型 rank.html 的 mock**，截图与原型同框可比；
# 并列的覆盖放在用例②（两人并列第 1）与用例③（并列压在晋级线上）。
# 升降级区（12 人档 → 前 5 晋级 / 后 4 降级）：晋级 1~5、保级 6~8、降级 9~12
# → 边界四个人：孙（第 5，压线晋级）、王（第 6，压线保级）、吴（第 8，保级末位）、郑（第 9，降级首位）
# 上周 XP（决定名次变化，±1 不报 → flat）：陈1200(1) 李1150(2) 赵1100(3) 刘1050(4) 孙1000(5)
#   周950(6) 吴900(7) 林850(8) 王800(9) 黄700(10) 徐600(11) 郑500(12)
# → 王 9→6 涨 3（↑ 猛冲）；郑 12→9 涨 3（↑）；林 8→10 跌 2（↓ 危险）；其余 0/±1（不报）
# 首刷重刷混合：郑本周再打一次**上周首刷过的那一关**（重刷，450 XP 只进账本不进榜）
ROSTER12 = [
    # 学号   姓名     本周XP 上周XP 队伍      队内角色  本周重刷XP（挂上周首刷那一关）
    ('S8A', '陈一帆', 940, 1200, '汪汪队', 'leader', 0),
    ('S8B', '李晓萌', 905, 1150, '喵喵教', 'leader', 0),
    ('S8C', '赵梓豪', 880, 1100, '汪汪队', 'member', 0),
    ('S8D', '刘思远', 855, 1050, '干饭人', 'leader', 0),
    ('S8E', '孙可欣', 830, 1000, '喵喵教', 'member', 0),
    ('S8F', '王小鱼', 790, 800, '加油鸭', 'leader', 0),      # 我
    ('S8G', '周子墨', 760, 950, '孤狼', 'leader', 0),        # 单人队（solo）
    ('S8H', '吴雨桐', 720, 900, '喵喵教', 'member', 0),
    ('S8I', '郑凯文', 660, 500, '干饭人', 'member', 450),    # 首刷重刷混合：重刷 450
    ('S8J', '林晓雯', 615, 850, '加油鸭', 'member', 0),
    ('S8K', '黄子轩', 540, 700, '孤狼', 'leader', 0),        # 单人队（同队名不同队，各自 solo）
    ('S8L', '徐若曦', 480, 600, '喵喵教', 'member', 0),
]
# 小队建队顺序（名字与原型一致；「孤狼」是两支单人队，点名单列两行）
TEAMS12 = [
    ('汪汪队', ['陈一帆', '赵梓豪']),
    ('喵喵教', ['李晓萌', '孙可欣', '吴雨桐', '徐若曦']),
    ('干饭人', ['刘思远', '郑凯文']),
    ('加油鸭', ['王小鱼', '林晓雯']),
    ('孤狼', ['周子墨']),
    ('孤狼', ['黄子轩']),
]

# ---------------- 用例②③：4 人实跑班（真实链路打关） ----------------
# 4 人档名额 = round(4×5/12)=2 晋级 / round(4×4/12)=1 降级（原型比例等比折算）
# 计划：Alice 首刷 + 重刷（重刷分数照进账本、不进榜）；Bob 同参数首刷（与 Alice 并列第 1）；
#       Carol 一关不打（0 分不上榜，但自己那行保留、晋升线 = 榜上最高分）；
#       Dave 上周首刷过 → 本周再打是同一次重刷（本周 0 分、榜上无名）
ROSTER4 = [('S8R1', '实跑Alice'), ('S8R2', '实跑Bob'), ('S8R3', '实跑Carol'), ('S8R4', '实跑Dave')]
QUESTION_SET = [
    ('vocab', 'S8 实跑卷第 1 题：选出与 acquire 意思最接近的词', ['获得', '放弃', '燃烧', '测量'], '0'),
    ('vocab', 'S8 实跑卷第 2 题：选出与 fragile 意思最接近的词', ['易碎的', '沉重的', '宽敞的', '干燥的'], '0'),
]

CHECKS = []
FAILS = []


# ---------------------------------------------------------------- 基础工具

def check(desc, want, got):
    ok = str(want) == str(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[S8] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


def fmt_map(d):
    return '{' + ', '.join('{}={}'.format(k, d[k]) for k in d) + '}'


def check_row(desc, want, got):
    """逐字段对拍：一个字段一条比对，失败时把不一致的字段单列一行。"""
    got = {k: got.get(k) for k in want} if isinstance(got, dict) else got
    diffs = [k for k in want if str(want[k]) != str(got.get(k))]
    ok = not diffs
    CHECKS.append({'desc': desc, 'want': fmt_map(want), 'got': fmt_map(got), 'ok': ok})
    print('[S8] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', fmt_map(want), fmt_map(got)))
    if not ok:
        FAILS.append(desc)
        for k in diffs:
            print('      ↳ 字段 {} 期望={} 实际={}'.format(k, want[k], got.get(k)))


def finish(step):
    bad = len(FAILS)
    print('[S8] 本步断言 {} 条，失败 {} 条 —— {}'.format(len(CHECKS), bad, step))
    if not CHECKS:
        raise SystemExit('{} 一条断言都没跑，脚本有问题'.format(step))


def leaked_xps(raw, xps):
    """响应体里是否出现了这些 XP 数字（键名 xp；紧凑与缩进两种 JSON 都认）。"""
    return [xp for xp in xps if re.search('"xp"\\s*:\\s*{}'.format(xp), raw)]


def head(msg):
    print()
    print('--- ' + msg + ' ---')


def dump(name, obj):
    path = os.path.join(HERE, name)
    with io.open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    note('写出 {}'.format(name))


def db_conn():
    cfg = {}
    with io.open(os.path.join(REPO, 'server', '.env'), encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return pymysql.connect(host=cfg['DB_HOST'], port=int(cfg['DB_PORT']), user=cfg['DB_USER'],
                           password=cfg['DB_PASSWORD'], database=cfg['DB_NAME'], charset='utf8mb4',
                           autocommit=True)


def api(method, path, token=None, body=None, raw_path=None, raw_body=None, content_type=None,
        tolerate_reset=False):
    """统一信封：返回 (http_code, json_or_text)。raw_path 非空时把原始体写到该文件。

    raw_body 用于自带编码的请求体（如 multipart 上传），此时 body 忽略。
    tolerate_reset 给「预期会被拒」的探针用：连接被 RST 时返回 0（而不是抛异常），
    调用方才能把「几次拿到回执 / 几次只看到断连」记成断言。
    """
    data = None
    headers = {}
    if raw_body is not None:
        data = raw_body
        headers['Content-Type'] = content_type or 'application/octet-stream'
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    raw = ''
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        code = e.code
    except (ConnectionResetError, urllib.error.URLError) as e:
        if not tolerate_reset:
            raise
        code = 0
        raw = '连接被重置：{}'.format(e)
    if raw_path:
        with io.open(raw_path, 'w', encoding='utf-8') as fh:
            fh.write(raw)
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, {'raw': raw}


def unwrap(code, body, what):
    if code != 200:
        raise SystemExit('{} 失败（HTTP {}）：{}'.format(what, code, body))
    return body['data']


def login(user, password):
    code, body = api('POST', '/api/auth/login', body={'username': user, 'password': password})
    return (body.get('data') or {}) if code == 200 else None


def chpwd(token, old, new):
    return api('POST', '/api/auth/chpwd', token, {'oldPassword': old, 'newPassword': new})


def student_token(db, username):
    """演示学生登录：名单里的初始密码 STU_INIT 首登必改密，改到 STU_PWD 后业务口才放行。

    「要不要改密」按登录回执的 mustChangePwd 判定，不按用的是哪一档密码猜——
    初始密码带「未改密」标记，不改密业务口全被 40302 挡着。
    """
    got = login(username, STU_PWD)
    if got and not got.get('mustChangePwd'):
        return got['token']
    got = login(username, STU_INIT)
    if got and got.get('mustChangePwd'):
        code, body = chpwd(got['token'], STU_INIT, STU_PWD)
        if code != 200:
            raise SystemExit('{} 改密失败：{}'.format(username, body))
        got = login(username, STU_PWD)
        if got and not got.get('mustChangePwd'):
            return got['token']
    raise SystemExit('{} 登录失败或仍在未改密状态（{} / {}）'.format(username, STU_PWD, STU_INIT))


def teacher_token():
    for pwd in TEACHER_PWDS:
        got = login(TEACHER, pwd)
        if got:
            if pwd != TEACHER_PWDS[0]:  # 还在初始密码上：打回下一档，后续脚本一律用第二档
                code, body = chpwd(got['token'], pwd, TEACHER_PWDS[0])
                if code != 200:
                    raise SystemExit('教师改密失败：{}'.format(body))
                got = login(TEACHER, TEACHER_PWDS[0])
            return got['token']
    raise SystemExit('教师 {} 登录失败'.format(TEACHER))


def user_id(db, username):
    with db.cursor() as cur:
        cur.execute('SELECT id FROM users WHERE username = %s', (username,))
        row = cur.fetchone()
    return int(row[0]) if row else 0


def class_id(db, name):
    with db.cursor() as cur:
        cur.execute('SELECT id FROM classes WHERE name = %s', (name,))
        row = cur.fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------- 日期口径（测试侧独立复算）

def week_start_of(day):
    """周一（与 service 的 WeekStart 同一口径：本地时区）。"""
    return day - dt.timedelta(days=day.weekday())


def week_index(day):
    return (week_start_of(day) - WEEK_EPOCH).days // 7


def season_window_of(day):
    """固定奇偶网格：赛季号 = 连周序 // 2；窗口 = 第 2k、2k+1 周。"""
    idx = week_index(day) // 2
    begin = WEEK_EPOCH + dt.timedelta(days=7 * 2 * idx)
    return begin, begin + dt.timedelta(days=7 * SEASON_WEEKS - 1), idx


def days_left(season_end, now):
    at = dt.datetime.combine(season_end, dt.time(23, 0))
    if at <= now:
        return 0
    delta = at - now
    return int(delta.total_seconds() // 86400) + (1 if delta.total_seconds() % 86400 else 0)


def week_label(day):
    return '{}/{}'.format(day.month, day.day)


def ymd(d):
    return d.strftime('%Y-%m-%d')


# ---------------------------------------------------------------- 自建自清

def cleanup(db):
    head('自建自清：删掉 S8 自建班级与它们名下的一切')
    ids = [cid for cid in (class_id(db, n) for n in CLASSES) if cid]
    if not ids:
        note('没有 S8 自建班级，跳过')
        return
    fmt = ','.join(['%s'] * len(ids))
    with db.cursor() as cur:
        cur.execute('SELECT id FROM users WHERE class_id IN ({})'.format(fmt), tuple(ids))
        uids = [int(r[0]) for r in cur.fetchall()]
        cur.execute('SELECT id FROM units WHERE class_id IN ({})'.format(fmt), tuple(ids))
        unit_ids = [int(r[0]) for r in cur.fetchall()]
        level_ids = []
        if unit_ids:
            uf = ','.join(['%s'] * len(unit_ids))
            cur.execute('SELECT id FROM levels WHERE unit_id IN ({})'.format(uf), tuple(unit_ids))
            level_ids = [int(r[0]) for r in cur.fetchall()]
        # 先删子表（attempts → attempt_answers/wrong_book/xp_ledger；units → levels → questions）
        if uids:
            uf = ','.join(['%s'] * len(uids))
            cur.execute('SELECT id FROM attempts WHERE user_id IN ({})'.format(uf), tuple(uids))
            att_ids = [int(r[0]) for r in cur.fetchall()]
            if att_ids:
                af = ','.join(['%s'] * len(att_ids))
                cur.execute('DELETE FROM attempt_answers WHERE attempt_id IN ({})'.format(af), tuple(att_ids))
                cur.execute('DELETE FROM xp_ledger WHERE ref_type = %s AND ref_id IN ({})'.format(af),
                            tuple(['attempt'] + att_ids))
                cur.execute('DELETE FROM attempts WHERE id IN ({})'.format(af), tuple(att_ids))
            cur.execute('DELETE FROM xp_ledger WHERE user_id IN ({})'.format(uf), tuple(uids))
            cur.execute('DELETE FROM wrong_book WHERE user_id IN ({})'.format(uf), tuple(uids))
            cur.execute('DELETE FROM reminders WHERE from_user IN ({0}) OR to_user IN ({0})'.format(uf),
                        tuple(uids) + tuple(uids))  # {0} 出现两次 → 参数也要给两遍
            cur.execute('SELECT id FROM teams WHERE class_id IN ({})'.format(fmt), tuple(ids))
            tids = [int(r[0]) for r in cur.fetchall()]
            if tids:
                tf = ','.join(['%s'] * len(tids))
                cur.execute('DELETE FROM team_members WHERE team_id IN ({})'.format(tf), tuple(tids))
                cur.execute('DELETE FROM teams WHERE id IN ({})'.format(tf), tuple(tids))
        if level_ids:
            lf = ','.join(['%s'] * len(level_ids))
            cur.execute('DELETE FROM questions WHERE level_id IN ({})'.format(lf), tuple(level_ids))
            cur.execute('DELETE FROM levels WHERE id IN ({})'.format(lf), tuple(level_ids))
        if unit_ids:
            uf2 = ','.join(['%s'] * len(unit_ids))
            cur.execute('DELETE FROM units WHERE id IN ({})'.format(uf2), tuple(unit_ids))
        cur.execute('DELETE FROM seasons WHERE class_id IN ({})'.format(fmt), tuple(ids))
        for name in CLASSES:
            cur.execute('DELETE FROM audit_log WHERE detail LIKE %s', ('%{}%'.format(name),))
        cur.execute('DELETE FROM users WHERE class_id IN ({})'.format(fmt), tuple(ids))
        cur.execute('DELETE FROM classes WHERE id IN ({})'.format(fmt), tuple(ids))
    note('已删除班级 {} 及其学生/单元/关卡/题目/成绩/小队/赛季行'.format(ids))


def import_class(db, teacher_tok, class_name, rows):
    """建班 + 导学生（multipart CSV）——与教师真实操作同一条链路。

    自己拼 multipart 而不过 curl：本机 curl 按 GBK 转码中文，且 -F 会把 Windows
    路径里的 \\U/\\d 当转义吃掉（见 memory: windows-curl-encoding）。
    CSV 里显式填初始密码：留空会默认用学号，4 字学号会撞「初始密码不能少于 6 位」。
    """
    if class_id(db, class_name):
        return
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['班级', '学号', '姓名', '初始密码'])
    for username, real in rows:
        w.writerow([class_name, username, real, STU_INIT])
    content = buf.getvalue().encode('utf-8-sig')

    boundary = '----s8boundary' + uuid.uuid4().hex
    body = b''.join([
        ('--{}\r\n'.format(boundary)).encode('utf-8'),
        'Content-Disposition: form-data; name="file"; filename="roster.csv"\r\n'.encode('utf-8'),
        b'Content-Type: text/csv\r\n\r\n',
        content,
        ('\r\n--{}--\r\n'.format(boundary)).encode('utf-8'),
    ])
    code, resp = api('POST', '/api/admin/import-users', teacher_tok, raw_body=body,
                     content_type='multipart/form-data; boundary=' + boundary)
    if code != 200:
        raise SystemExit('导入 {} 失败（HTTP {}）：{}'.format(class_name, code, resp))
    note('导入班级「{}」{} 人（初始密码 {}）'.format(class_name, len(rows), STU_INIT))


def ensure_unit(teacher_tok, cid, week_no, unit_name):
    """单元按名字复用（重复跑不会一次一次地堆单元），返回 (id, 是否新建)。"""
    db = db_conn()
    with db.cursor() as cur:
        cur.execute('SELECT id FROM units WHERE class_id = %s AND name = %s', (cid, unit_name))
        row = cur.fetchone()
    if row:
        return int(row[0]), False
    code, body = api('POST', '/api/admin/units', teacher_tok,
                     {'classId': cid, 'weekNo': week_no, 'name': unit_name})
    if code != 200:
        raise SystemExit('建单元失败：{}'.format(body))
    return int(body['data']['id']), True


def ensure_level(teacher_tok, unit_id, seq, name, typ='vocab', limit=300):
    db = db_conn()
    with db.cursor() as cur:
        cur.execute('SELECT id FROM levels WHERE unit_id = %s AND name = %s', (unit_id, name))
        row = cur.fetchone()
    if row:
        return int(row[0]), False
    code, body = api('POST', '/api/admin/levels', teacher_tok,
                     {'unitId': unit_id, 'seq': seq, 'name': name, 'type': typ,
                      'timeLimit': limit, 'isBoss': False})
    if code != 200:
        raise SystemExit('建关卡失败：{}'.format(body))
    return int(body['data']['id']), True


def seed_paper(teacher_tok, unit_id, level_id, questions):
    """往一个关卡里塞一整套题（单元的套题内容就是指纹比对的对象）。"""
    for typ, stem, opts, ans in questions:
        ensure_question(teacher_tok, level_id, typ, stem, opts, ans)
    return unit_id


def ensure_question(teacher_tok, level_id, typ, stem, options, answer_idx):
    # exp（解析）是后台建题的必填项，缺了就是 40001 参数错误。
    exp = 'S8 验收用题解析：正确答案是「{}」。'.format(options[int(answer_idx)])
    code, body = api('POST', '/api/admin/questions', teacher_tok,
                     {'levelId': level_id, 'band': '4', 'type': typ, 'stem': stem,
                      'options': options, 'answerIdx': answer_idx, 'exp': exp, 'enabled': True})
    if code != 200:
        raise SystemExit('建题目失败：{}'.format(body))
    return body['data']['id']


def seed_ledger_row(db, user_id, level_id, unit_id, xp, finished_at):
    """直写一行「已交卷」底账：attempts + xp_ledger。

    只给「上周的首刷」和「本周的重刷」用这两条路——真实链路能造的时刻（本周）
    一律走接口打；要把分摆在**上周**，接口没法回填 finished_at，只能直写。
    """
    with db.cursor() as cur:
        cur.execute(
            'INSERT INTO attempts (user_id, level_id, unit_id, correct, total, stars, score710, '
            'xp_earned, shuffle_seed, status, started_at, finished_at) '
            'VALUES (%s, %s, %s, 2, 2, 3, 710, %s, 0, %s, %s, %s)',
            (user_id, level_id, unit_id, xp, 'finished', finished_at, finished_at))
        att_id = int(cur.lastrowid)
        if xp:
            cur.execute(
                'INSERT INTO xp_ledger (user_id, delta, reason, ref_type, ref_id, created_at) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (user_id, xp, 'answer_base', 'attempt', att_id, finished_at))
    return att_id


# ---------------------------------------------------------------- 打关（真实链路）

def submit_correct(token, level_id):
    """全对交卷（真实链路：取卷 → 交卷）。

    题库里每题的正确选项都在 0 号位（见 QUESTION_SET 的约定），但卷面选项被 shuffle_seed
    洗过序，所以先按**题干文本**把正确项对回卷面下标，不假设它还在第一位。
    返回 (settlement, paper)：settlement.xpTotal 是本次净得，xpTotalAll 是账本聚合。
    """
    code, body = api('GET', '/api/quiz/paper?level={}'.format(level_id), token)
    paper = unwrap(code, body, '取卷 L{}'.format(level_id))
    qids = [int(q['id']) for q in paper['questions']]
    with db_conn() as db:
        fmt = ','.join(['%s'] * len(qids))
        with db.cursor() as cur:
            cur.execute('SELECT id, options_json FROM questions WHERE id IN ({})'.format(fmt), tuple(qids))
            bank = {int(r[0]): json.loads(r[1] or '[]') for r in cur.fetchall()}
    answers = []
    for q in paper['questions']:
        correct_text = bank[int(q['id'])][0]
        answers.append({'questionId': q['id'], 'pickedIdx': str(q['options'].index(correct_text)),
                        'elapsedMs': 2000})
    code, body = api('POST', '/api/quiz/submit', token,
                     {'attemptId': paper['attemptId'], 'answers': answers})
    data = unwrap(code, body, '交卷 L{}'.format(level_id))
    if not data.get('settlement'):
        raise SystemExit('交卷回执没有 settlement：{}'.format(data))
    return data['settlement'], paper


# ---------------------------------------------------------------- SQL 独立聚合

def sql_first_clear_xp(db, user_ids, begin, end):
    """首刷口径：每个 (user, level) 取 id 最小的 finished attempt，按 finished_at 落窗，账本净得求和。"""
    if not user_ids:
        return {}
    fmt = ','.join(['%s'] * len(user_ids))
    sql = (
        'SELECT a.user_id, COALESCE(SUM(x.delta), 0), COUNT(*) FROM attempts a '
        'JOIN (SELECT user_id, level_id, MIN(id) AS first_id FROM attempts '
        '      WHERE status = %s AND user_id IN ({}) GROUP BY user_id, level_id) f '
        '  ON f.first_id = a.id '
        'LEFT JOIN xp_ledger x ON x.ref_type = %s AND x.ref_id = a.id '
        'WHERE a.finished_at >= %s AND a.finished_at < %s GROUP BY a.user_id'
    ).format(fmt)
    with db.cursor() as cur:
        cur.execute(sql, tuple(['finished'] + list(user_ids) + ['attempt', begin, end]))
        return {int(r[0]): (int(r[1]), int(r[2])) for r in cur.fetchall()}


def sql_ledger_sum(db, user_id):
    with db.cursor() as cur:
        cur.execute('SELECT COALESCE(SUM(delta),0) FROM xp_ledger WHERE user_id = %s', (user_id,))
        return int(cur.fetchone()[0])


def sql_ledger_counts(db, uids, cur_begin, cur_end, last_day):
    """这批学生的「本周窗内 attempts 条数 / 上周那一天条数」——独立 SQL，校验底账摆位。"""
    fmt = ','.join(['%s'] * len(uids))
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM attempts WHERE user_id IN ({}) '
                    'AND finished_at >= %s AND finished_at < %s'.format(fmt),
                    tuple(uids) + (cur_begin, cur_end))
        this_week = int(cur.fetchone()[0])
        cur.execute('SELECT COUNT(*) FROM attempts WHERE user_id IN ({}) AND DATE(finished_at) = %s'.format(fmt),
                    tuple(uids) + (last_day,))
        last_week = int(cur.fetchone()[0])
    return '{}/{}'.format(this_week, last_week)


def sql_replay_count(db, user_id, begin, end):
    """本周重刷数 = 本周 finished 数 − 本周首刷行数（与服务端口径同式，但 SQL 另一份）。"""
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM attempts WHERE user_id = %s AND status = %s '
                    'AND finished_at >= %s AND finished_at < %s',
                    (user_id, 'finished', begin, end))
        total = int(cur.fetchone()[0])
        cur.execute('SELECT COUNT(*) FROM attempts a JOIN (SELECT user_id, level_id, MIN(id) AS fid '
                    'FROM attempts WHERE status = %s AND user_id = %s GROUP BY user_id, level_id) f '
                    'ON f.fid = a.id WHERE a.finished_at >= %s AND a.finished_at < %s',
                    ('finished', user_id, begin, end))
        firsts = int(cur.fetchone()[0])
    return total - firsts


def sql_audit_count(db, action, class_name):
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM audit_log WHERE action = %s AND detail LIKE %s',
                    (action, '%{}%'.format(class_name)))
        return int(cur.fetchone()[0])


def sql_setting(db, class_name, key):
    with db.cursor() as cur:
        cur.execute('SELECT settings_json FROM classes WHERE name = %s', (class_name,))
        row = cur.fetchone()
    try:
        raw = json.loads(row[0]) if row and row[0] else {}
    except ValueError:
        raw = {}
    return raw.get(key)


def wipe_activity(db, usernames):
    """把一个班学生的成绩清空（重跑单个用例时的自净，不碰班级/账号/小队）。"""
    uids = [u for u in (user_id(db, u) for u in usernames) if u]
    if not uids:
        return
    fmt = ','.join(['%s'] * len(uids))
    with db.cursor() as cur:
        cur.execute('SELECT id FROM attempts WHERE user_id IN ({})'.format(fmt), tuple(uids))
        att = [int(r[0]) for r in cur.fetchall()]
        if att:
            af = ','.join(['%s'] * len(att))
            cur.execute('DELETE FROM attempt_answers WHERE attempt_id IN ({})'.format(af), tuple(att))
            cur.execute('DELETE FROM xp_ledger WHERE ref_type = %s AND ref_id IN ({})'.format(af),
                        tuple(['attempt'] + att))
            cur.execute('DELETE FROM attempts WHERE id IN ({})'.format(af), tuple(att))
        cur.execute('DELETE FROM xp_ledger WHERE user_id IN ({})'.format(fmt), tuple(uids))


# ---------------------------------------------------------------- 手算口径（人肉期望）

def round_half_up(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def promote_count(n):
    """晋级名额 = round(n × 5/12)；12 人 → 5（原型那句「前 5 名」）。"""
    return round_half_up(n * 5 / 12.0)


def demote_count(n):
    """降级名额 = round(n × 4/12)；12 人 → 4。名额和超过在册人数时收缩到 n - 晋级名额。"""
    d = round_half_up(n * 4 / 12.0)
    p = promote_count(n)
    return n - p if p + d > n else d


def zone_of(rank, n, promote, demote):
    """rank<=晋级名额 → 晋级区；rank>n-降级名额 → 降级区；其余保级；rank=0（没计分）不涂色。"""
    if rank <= 0:
        return ''
    if rank <= promote:
        return 'promote'
    if rank > n - demote:
        return 'demote'
    return 'keep'


def trend_of(delta):
    """徽标口径：涨/跌 2 名以上才报（±1 名不报）。"""
    if delta >= 2:
        return 'up'
    if delta <= -2:
        return 'down'
    return 'flat'


def competition_ranks(xp_by_key):
    """竞争式并列名次：XP 降序，同 XP 同名次且不跳号（1,2,2,4…）。"""
    ordered = sorted(xp_by_key.items(), key=lambda kv: -kv[1])
    out, prev, rank = {}, None, 0
    for i, (key, xp) in enumerate(ordered):
        if xp != prev:
            rank, prev = i + 1, xp
        out[key] = rank
    return out, ordered


def hand_board(names_xp_cur, names_xp_last, me_name, team_of, solo_of, n=None):
    """按上面几条规则把一张榜整张算出来（用例①②③共用）。

    n = 班级在册人数（名额基数是它，不是「有分的人数」）；缺省取名单长度。
    """
    n = n or len(names_xp_cur)
    promote, demote = promote_count(n), demote_count(n)
    cur_rank, order = competition_ranks(names_xp_cur)
    # 上周 0 分 = 上周不在榜：与实现同一口径（没上周名次的人 lastRank=0、delta=0、trend=flat），
    # 而不是「0 分排第 N 名」。
    last_rank, _ = competition_ranks({k: v for k, v in names_xp_last.items() if v > 0})
    rows, participants = [], 0
    for name, xp in order:
        rank = cur_rank[name] if xp > 0 else 0   # 没计分的人不上榜（rank=0、不涂色带）
        if xp > 0:
            participants += 1
        last = last_rank.get(name, 0)
        rows.append({
            'realName': name, 'xp': xp, 'rank': rank,
            'zone': zone_of(rank, n, promote, demote),
            'lastRank': last if xp > 0 else 0,
            'delta': (last - rank) if (xp > 0 and last > 0) else 0,
            'trend': trend_of(last - rank) if (xp > 0 and last > 0) else 'flat',
            'teamName': team_of.get(name, ''), 'solo': solo_of.get(name, False),
            'isMe': name == me_name,
        })
    cut = min([r['xp'] for r in rows if r['zone'] == 'promote'], default=0)
    me_xp = names_xp_cur[me_name]
    me = [r for r in rows if r['isMe']][0]
    return {
        'promoteCount': promote, 'demoteCount': demote, 'classSize': n,
        'participants': participants, 'cut': cut,
        'rows': rows, 'me': me,
        'meGap': (cut - me_xp) if (cut > 0 and me_xp < cut) else 0,
    }


EMOJI12 = {
    '陈一帆': '🐯', '李晓萌': '🐰', '赵梓豪': '🦁', '刘思远': '🐼', '孙可欣': '🦊', '王小鱼': '🦉',
    '周子墨': '🐺', '吴雨桐': '🐱', '郑凯文': '🐸', '林晓雯': '🐹', '黄子轩': '🐨', '徐若曦': '🦄',
}
PAPER_H12 = [
    ('vocab', 'S8 验收套题第 1 题：选出与 constant 意思最接近的词', ['持续的', '稀有的', '模糊的', '狭窄的'], '0'),
    ('vocab', 'S8 验收套题第 2 题：选出与 abandon 意思最接近的词', ['放弃', '收集', '修补', '炫耀'], '0'),
]
PAPER_DIFF = [
    ('vocab', 'S8 异卷班套题第 1 题：选出与 release 意思最接近的词', ['释放', '逮捕', '折叠', '测量'], '0'),
]


def cmd_baseline(out='before'):
    head('底账快照：表 / 列 / 题库指纹（S8 只写数据行，不动表结构、不动别人的题库）')
    db = db_conn()
    # S8 自己会建单元/关卡/题（那正是它要证明的写入），底账比对要**排除自建班**，
    # 只盯「别人家的题库有没有被动过」——否则自己造数会让 before/after 必然不等。
    fmt = ','.join(['%s'] * len(CLASSES))
    others = tuple(CLASSES)
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()')
        tables = int(cur.fetchone()[0])
        cur.execute('SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE()')
        cols = int(cur.fetchone()[0])
        n_units = n_levels = n_questions = 0
        # 三条都要经 classes 回连：units 这一条曾经写成「FROM units c WHERE c.name NOT IN(班名)」——
        # 那是拿**单元名**去比班名，等于把全库单元都算成"别人的"，S8 自己建的单元一多就假红。
        # 真口径是「不属于 S8 自建班的单元」。（2026-10-08 整链复跑踩到，修的就是这个。）
        for t, clause in (('units', 'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({})'.format(fmt)),
                          ('levels', 'JOIN units u ON u.id = l.unit_id JOIN classes c ON c.id = u.class_id '
                                     'WHERE c.name NOT IN ({})'.format(fmt)),
                          ('questions', 'JOIN levels l ON l.id = q.level_id JOIN units u ON u.id = l.unit_id '
                                        'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({})'.format(fmt))):
            alias = {'units': 'units u', 'levels': 'levels l', 'questions': 'questions q'}[t]
            cur.execute('SELECT COUNT(*) FROM {} {}'.format(alias, clause), others)
            if t == 'units':
                n_units = int(cur.fetchone()[0])
            elif t == 'levels':
                n_levels = int(cur.fetchone()[0])
            else:
                n_questions = int(cur.fetchone()[0])
        cur.execute('SELECT q.id, q.stem, q.options_json FROM questions q '
                    'JOIN levels l ON l.id = q.level_id JOIN units u ON u.id = l.unit_id '
                    'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({}) '
                    'ORDER BY q.id'.format(fmt), others)
        qs = cur.fetchall()
    crc = 0
    for qid, stem, opts in qs:
        crc = (crc + zlib.crc32('{}\x1f{}\x1f{}'.format(qid, stem or '', opts or '').encode('utf-8'))) & 0xffffffff
    lines = ['tables={}'.format(tables), 'columns={}'.format(cols),
             'units={}'.format(n_units), 'levels={}'.format(n_levels),
             'questions={}'.format(n_questions), 'bank_crc={}'.format(crc)]
    with io.open(os.path.join(HERE, 'baseline-{}.txt'.format(out)), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    note('别人的底账（表/列/单元/关/题/题库 CRC）：{}'.format('/'.join(lines[i].split('=')[1] for i in range(6))))
    check('表数仍是 17（S8 不加表）', 17, tables)
    check('列数仍是 128（S8 不改列）', 128, cols)
    if out == 'before':
        globals()['BASE'] = {'tables': tables, 'columns': cols, 'units': n_units,
                             'levels': n_levels, 'questions': n_questions, 'bank_crc': crc}
    else:
        before = {}
        path = os.path.join(HERE, 'baseline-before.txt')
        if os.path.exists(path):
            for line in io.open(path, encoding='utf-8'):
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    before[k] = v
        if before:
            check('别人的题库指纹与跑前一致（没改别人的题）', before['bank_crc'], crc)
            check('别人的单元/关/题数与跑前一致', '{}/{}/{}'.format(before['units'], before['levels'], before['questions']),
                  '{}/{}/{}'.format(n_units, n_levels, n_questions))
            check('表/列数与跑前一致', '{}/{}'.format(before['tables'], before['columns']),
                  '{}/{}'.format(tables, cols))
    finish('底账快照')


# ---------------------------------------------------------------- 用例① 12 人班

def team_plan():
    """建队计划：第一人建队、其余入队。

    「孤狼」按原型是两支各自单人的小队（同名不同队，都挂「单人队」徽标），
    所以这里点名写死成员表——用队员数判定 solo，同名不会串。
    """
    out = []
    for tname, members in TEAMS12:
        out.append({'name': tname, 'leader': members[0], 'members': list(members)})
    return out


def solo_of12(name):
    for _, members in TEAMS12:
        if name in members:
            return len(members) == 1
    return False


def cmd_seed12():
    head('用例①：建「{}」（12 人，XP 与原型 rank.html 同档）+ 两周底账 + 5 支小队'.format(CLASS12))
    db = db_conn()
    cleanup(db)
    tok = teacher_token()
    import_class(db, tok, CLASS12, [(r[0], r[1]) for r in ROSTER12])
    cid = class_id(db, CLASS12)
    if not cid:
        raise SystemExit('班级「{}」没建起来'.format(CLASS12))
    for username, real in [(r[0], r[1]) for r in ROSTER12]:
        if EMOJI12.get(real):
            with db.cursor() as cur:
                cur.execute('UPDATE users SET avatar = %s WHERE username = %s', (EMOJI12[real], username))
    note('12 个头像按原型的 emoji 写进 users.avatar（用户资料字段，不改表）')
    tids = {}
    for username, real in [(r[0], r[1]) for r in ROSTER12]:
        tids[real] = student_token(db, username)

    unit, _ = ensure_unit(tok, cid, 8, 'S8 验收·第 1 套')
    l_last, made_last = ensure_level(tok, unit, 1, 'S8 验收关 1（上周底账）')
    l_this, made_this = ensure_level(tok, unit, 2, 'S8 验收关 2（本周底账）')
    if made_last:
        seed_paper(tok, unit, l_last, [(t, s + '（上周关）', o, a) for t, s, o, a in PAPER_H12])
    if made_this:
        seed_paper(tok, unit, l_this, [(t, s + '（本周关）', o, a) for t, s, o, a in PAPER_H12])
    check('用例① 单元/关卡就位', True, bool(unit and l_last and l_this))

    now = dt.datetime.now()
    week_start = week_start_of(now.date())
    week_end = week_start + dt.timedelta(days=7)
    last_at = dt.datetime.combine(week_start - dt.timedelta(days=1), dt.time(20, 0))  # 上周日 20:00
    this_at = now - dt.timedelta(minutes=5)
    if this_at.date() < week_start:
        raise SystemExit('现在是周一 00:05 之内，本周底账摆不进本周窗，稍后再跑')
    check('底账时刻落位（上周日在上一周窗内 / 本周在本周窗内）', True,
          week_start - dt.timedelta(days=7) <= last_at.date() < week_start <= this_at.date() < week_end)

    seeded = {}
    for username, real, xp, lastxp, team, role, replay in ROSTER12:
        uid = user_id(db, username)
        if not uid:
            raise SystemExit('学生 {} 不在库里'.format(username))
        seed_ledger_row(db, uid, l_last, unit, lastxp, last_at)
        seed_ledger_row(db, uid, l_this, unit, xp, this_at)
        if replay:  # 首刷重刷混合：重刷上周首刷过的那一关
            seed_ledger_row(db, uid, l_last, unit, replay, this_at + dt.timedelta(minutes=1))
        seeded[real] = {'uid': uid, 'xp': xp, 'lastXp': lastxp, 'replayXp': replay}

    made = {}
    for plan in team_plan():
        lead = plan['leader']
        code, body = api('POST', '/api/team/create', tids[lead], {'name': plan['name'], 'emoji': ''})
        if code != 200:
            raise SystemExit('建队 {} 失败：{}'.format(plan['name'], body))
        team_id = int(body['data']['id'])
        made[plan['name']] = team_id
        for member in plan['members']:
            if member == lead:
                continue
            code, body = api('POST', '/api/team/join', tids[member], {'teamId': team_id})
            if code != 200:
                raise SystemExit('{} 入队 {} 失败：{}'.format(member, plan['name'], body))
    check('5 支小队（含 2 支单人队）组队完成', True, len(made) >= 5)

    dump('plan-hand12.json', {
        'classId': cid, 'className': CLASS12, 'unitId': unit, 'levelLast': l_last, 'levelThis': l_this,
        'weekStart': ymd(week_start), 'weekEnd': ymd(week_end),
        'lastAt': last_at.isoformat(), 'thisAt': this_at.isoformat(),
        'students': seeded, 'teams': made,
    })
    finish('用例① 造数')


def cmd_check12():
    head('用例①：12 人榜逐字段对拍（手算 vs 接口 vs SQL 底账）')
    db = db_conn()
    cid = class_id(db, CLASS12)
    if not cid:
        raise SystemExit('先跑 seed12')
    plan = json.load(io.open(os.path.join(HERE, 'plan-hand12.json'), encoding='utf-8'))
    names_xp_cur = {r[1]: r[2] for r in ROSTER12}
    names_xp_last = {r[1]: r[3] for r in ROSTER12}
    team_of = {r[1]: r[4] for r in ROSTER12}
    solo_of = {r[1]: solo_of12(r[1]) for r in ROSTER12}
    want = hand_board(names_xp_cur, names_xp_last, '王小鱼', team_of, solo_of)

    tok = student_token(db, 'S8F')
    code, body = api('GET', '/api/league/board', tok, raw_path=os.path.join(HERE, 'board-hand12.json'))
    board = unwrap(code, body, 'GET /league/board')

    now = dt.datetime.now()
    s_begin, s_end, s_idx = season_window_of(now.date())
    week_start = week_start_of(now.date())
    check_row('榜单头部（班名/开关/赛季/周窗）', {
        'className': CLASS12, 'rankPublic': True, 'hidden': False,
        'season.no': 1, 'season.name': '第 1 赛季', 'season.id': 0,
        'season.divisionLabel': '翡翠联赛', 'season.upDivision': '钻石', 'season.downDivision': '白银',
        'season.start': ymd(s_begin), 'season.end': ymd(s_end),
        'season.daysLeft': days_left(s_end, now),
        'week.start': ymd(week_start), 'week.end': ymd(week_start + dt.timedelta(days=6)),
        'week.label': week_label(week_start),
    }, {
        'className': board['className'], 'rankPublic': board['rankPublic'], 'hidden': board['hidden'],
        'season.no': board['season']['no'], 'season.name': board['season']['name'],
        'season.id': board['season']['id'], 'season.divisionLabel': board['season']['divisionLabel'],
        'season.upDivision': board['season']['upDivision'], 'season.downDivision': board['season']['downDivision'],
        'season.start': board['season']['start'], 'season.end': board['season']['end'],
        'season.daysLeft': board['season']['daysLeft'],
        'week.start': board['week']['start'], 'week.end': board['week']['end'],
        'week.label': board['week']['label'],
    })
    check_row('名额与文案（前 5 晋级 / 后 4 降级）', {
        'promoteCount': want['promoteCount'], 'demoteCount': want['demoteCount'],
        'promoteText': '前 5 名晋级钻石联赛 · 后 4 名降级白银联赛',
        'classSize': want['classSize'], 'participants': want['participants'], 'count': 12,
    }, {
        'promoteCount': board['promoteCount'], 'demoteCount': board['demoteCount'],
        'promoteText': board['promoteText'], 'classSize': board['classSize'],
        'participants': board['participants'], 'count': board['count'],
    })
    check('努力值口径文案含「首刷」', True, '首刷' in board['xpText'])
    note('xpText = {}'.format(board['xpText']))

    items = board['items']
    check('榜上行数 = 12（无 0 分学生，不留额外行）', 12, len(items))
    for i, (w, got) in enumerate(zip(want['rows'], items)):
        check_row('榜第 {} 行 {}'.format(i + 1, w['realName']), w, got)
    check_row('我那一行（第 6 名 / 差 40 XP）', {
        'rank': want['me']['rank'], 'xp': want['me']['xp'], 'zone': want['me']['zone'],
        'lastRank': want['me']['lastRank'], 'delta': want['me']['delta'], 'trend': want['me']['trend'],
        'promoteCutXp': want['cut'], 'gapToPromote': want['meGap'],
    }, {
        'rank': board['me']['rank'], 'xp': board['me']['xp'], 'zone': board['me']['zone'],
        'lastRank': board['me']['lastRank'], 'delta': board['me']['delta'], 'trend': board['me']['trend'],
        'promoteCutXp': board['me']['promoteCutXp'], 'gapToPromote': board['me']['gapToPromote'],
    })

    # 接口 vs SQL 底账（另一份独立聚合）
    uids = [plan['students'][r[1]]['uid'] for r in ROSTER12]
    sql_xp = sql_first_clear_xp(db, uids, dt.datetime.combine(week_start, dt.time(0, 0)),
                                dt.datetime.combine(week_start + dt.timedelta(days=7), dt.time(0, 0)))
    sql_map = {int(k): v[0] for k, v in sql_xp.items()}
    diffs = {r[1]: (r[2], sql_map.get(plan['students'][r[1]]['uid'], 0)) for r in ROSTER12
             if sql_map.get(plan['students'][r[1]]['uid'], 0) != r[2]}
    check('SQL 首刷口径逐人等于手算 XP（12 人）', 0, len(diffs))
    if diffs:
        note('不一致：{}'.format(diffs))

    # 我的努力值明细（/league/me）
    code, body = api('GET', '/api/league/me', tok, raw_path=os.path.join(HERE, 'me-hand12.json'))
    mine = unwrap(code, body, 'GET /league/me')
    check_row('我的明细合计（1 条首刷 / 0 次重刷 / 合计=790）', {
        'xp': 790, 'rows': 1, 'replayAttempts': 0, 'rowXp': 790, 'rowLevel': 'S8 验收关 2（本周底账）',
    }, {
        'xp': mine['xp'], 'rows': len(mine['rows']), 'replayAttempts': mine['replayAttempts'],
        'rowXp': mine['rows'][0]['xp'] if mine['rows'] else None,
        'rowLevel': mine['rows'][0]['levelName'] if mine['rows'] else None,
    })
    check('明细合计 == 榜上 XP（同一口径）', mine['xp'], board['me']['xp'])

    # 郑凯文：首刷重刷混合那一例（榜取首刷、账本全都要）
    tok_z = student_token(db, 'S8I')
    code, body = api('GET', '/api/league/me', tok_z, raw_path=os.path.join(HERE, 'me-hand12-zheng.json'))
    zheng = unwrap(code, body, 'GET /league/me（郑凯文）')
    uid_z = plan['students']['郑凯文']['uid']
    ledger_z = sql_ledger_sum(db, uid_z)
    check_row('郑凯文：榜 660 / 重刷 1 次 / 账本 500+660+450=1610', {
        'rankXp': 660, 'replayAttempts': 1, 'ledger': 1610,
        'replayNotInBoard': ledger_z > zheng['xp'],
    }, {
        'rankXp': zheng['xp'], 'replayAttempts': zheng['replayAttempts'], 'ledger': ledger_z,
        'replayNotInBoard': ledger_z > zheng['xp'],
    })
    check('郑凯文 SQL 账本聚合 = 1610（重刷的 450 只在账本里）', 1610, ledger_z)
    dump('check12-hand-table.json', {'hand': want, 'board': board, 'me': mine, 'zheng': zheng})
    finish('用例① 对拍')


# ---------------------------------------------------------------- 用例② 4 人实跑班（真实链路）

ROSTER6 = [
    # 学号   姓名    本周XP 上周XP
    ('S8T1', '边界甲', 500, 100),
    ('S8T2', '边界乙', 400, 200),
    ('S8T3', '边界丙', 300, 250),
    ('S8T4', '边界丁', 300, 300),   # 与丙并列第 3（并列压在晋级线上：名额 3，区内 4 人）
    ('S8T5', '边界戊', 100, 900),
    ('S8T6', '边界己', 0, 0),       # 我：一关没打，不上榜但保留自己那一行
]


def cmd_seed4():
    head('用例②：建「{}」4 人 + 真实链路打关（首刷 / 重刷 / 并列 / 0 分）'.format(CLASS4))
    db = db_conn()
    if not class_id(db, CLASS12):
        note('提醒：用例① 的底账不在库里（先跑 seed12 才能对拍 12 人榜）')
    tok = teacher_token()
    import_class(db, tok, CLASS4, ROSTER4)
    cid = class_id(db, CLASS4)
    if not cid:
        raise SystemExit('班级「{}」没建起来'.format(CLASS4))
    wipe_activity(db, [r[0] for r in ROSTER4])
    tk = {r[1]: student_token(db, r[0]) for r in ROSTER4}

    unit, _ = ensure_unit(tok, cid, 8, 'S8 实跑·第 1 套')
    lvl, made = ensure_level(tok, unit, 1, 'S8 实跑关 1')
    if made:
        seed_paper(tok, unit, lvl, QUESTION_SET)

    now = dt.datetime.now()
    week_start = week_start_of(now.date())
    last_at = dt.datetime.combine(week_start - dt.timedelta(days=1), dt.time(20, 0))
    # Dave：上周已经首刷过这一关 → 本周再打就是重刷（本周不上榜、账本照进）
    uid_dave = user_id(db, 'S8R4')
    seed_ledger_row(db, uid_dave, lvl, unit, 300, last_at)

    # Alice：首刷 + 重刷；Bob：同参数首刷（与 Alice 并列）；Carol：一关不打
    first, _ = submit_correct(tk['实跑Alice'], lvl)
    replay, _ = submit_correct(tk['实跑Alice'], lvl)
    bob, _ = submit_correct(tk['实跑Bob'], lvl)
    dave, _ = submit_correct(tk['实跑Dave'], lvl)

    check('Alice 首刷/重刷标记正确（首次 firstClear=true，重刷 replay=true）',
          'True/True', '{}/{}'.format(first['firstClear'], replay['replay']))
    check('Alice 重刷不再发通关奖励（重刷净得 < 首刷净得）', True, replay['xpTotal'] < first['xpTotal'])
    check('Alice 与 Bob 同参数同分（并列前提）', first['xpTotal'], bob['xpTotal'])
    check('Dave 本周这一次是重刷（首刷在上周）', True, bool(dave['replay']))

    dump('plan-e2e4.json', {
        'classId': cid, 'className': CLASS4, 'unitId': unit, 'levelId': lvl,
        'weekStart': ymd(week_start), 'weekEnd': ymd(week_start + dt.timedelta(days=7)),
        'lastAt': last_at.isoformat(),
        'aliceFirstXp': first['xpTotal'], 'aliceReplayXp': replay['xpTotal'],
        'aliceLedger': replay['xpTotalAll'], 'bobXp': bob['xpTotal'], 'bobLedger': bob['xpTotalAll'],
        'daveReplayXp': dave['xpTotal'], 'daveLedger': dave['xpTotalAll'],
        'daveSeededXp': 300, 'carolXp': 0,
    })
    finish('用例② 造数')


def open_board(token, raw_name):
    code, body = api('GET', '/api/league/board', token, raw_path=os.path.join(HERE, raw_name))
    return unwrap(code, body, 'GET /league/board')


def open_mine(token, raw_name):
    code, body = api('GET', '/api/league/me', token, raw_path=os.path.join(HERE, raw_name))
    return unwrap(code, body, 'GET /league/me')


def cmd_check4():
    head('用例②：4 人实跑班——并列第 1 / 首刷口径 / 0 分不上榜 / 名额缩放 2:1')
    db = db_conn()
    plan = json.load(io.open(os.path.join(HERE, 'plan-e2e4.json'), encoding='utf-8'))
    tk = {r[1]: student_token(db, r[0]) for r in ROSTER4}
    a_xp, b_xp = plan['aliceFirstXp'], plan['bobXp']
    promote, demote = promote_count(4), demote_count(4)

    board = open_board(tk['实跑Alice'], 'board-e2e4-alice.json')
    check_row('4 人档名额（round(4×5/12)=2 / round(4×4/12)=1）+ 计分 2 人', {
        'promoteCount': promote, 'demoteCount': demote, 'classSize': 4,
        'participants': 2, 'count': 2,
    }, {
        'promoteCount': board['promoteCount'], 'demoteCount': board['demoteCount'],
        'classSize': board['classSize'], 'participants': board['participants'], 'count': board['count'],
    })
    names_xp = {'实跑Alice': a_xp, '实跑Bob': b_xp}
    want = hand_board(names_xp, {'实跑Alice': 0, '实跑Bob': 0}, '实跑Alice', {}, {}, n=4)
    by_name = {r['realName']: r for r in board['items']}
    for w in want['rows']:
        check_row('榜上 {}（并列第 1，都在晋级区）'.format(w['realName']), w, by_name.get(w['realName'], {}))
    check('榜按 XP 降序（并列相邻不跳号）', True,
          all(board['items'][i]['xp'] >= board['items'][i + 1]['xp'] for i in range(len(board['items']) - 1)))
    check('并列第 1：两行同 XP 同名次（1/1，不跳号）', '1/1',
          '{}/{}'.format(board['items'][0]['rank'], board['items'][1]['rank']))
    check_row('我（Alice）：榜首 / 已在晋级区 / 晋升线=榜上最高分', {
        'rank': 1, 'xp': a_xp, 'zone': 'promote', 'promoteCutXp': min(a_xp, b_xp), 'gapToPromote': 0,
    }, {
        'rank': board['me']['rank'], 'xp': board['me']['xp'], 'zone': board['me']['zone'],
        'promoteCutXp': board['me']['promoteCutXp'], 'gapToPromote': board['me']['gapToPromote'],
    })

    mine_a = open_mine(tk['实跑Alice'], 'me-e2e4-alice.json')
    check_row('Alice 明细：1 次首刷计入 / 1 次重刷不计入', {
        'xp': a_xp, 'rows': 1, 'replayAttempts': 1, 'ledger': plan['aliceLedger'],
    }, {
        'xp': mine_a['xp'], 'rows': len(mine_a['rows']), 'replayAttempts': mine_a['replayAttempts'],
        'ledger': sql_ledger_sum(db, user_id(db, 'S8R1')),
    })
    check('榜上 XP = 首刷那一次（重刷的 {} XP 没进榜）'.format(plan['aliceReplayXp']),
          True, board['me']['xp'] == a_xp and board['me']['xp'] != plan['aliceLedger'])

    mine_b = open_mine(tk['实跑Bob'], 'me-e2e4-bob.json')
    check_row('Bob 明细：1 次首刷 / 0 次重刷', {'xp': b_xp, 'rows': 1, 'replayAttempts': 0},
              {'xp': mine_b['xp'], 'rows': len(mine_b['rows']),
               'replayAttempts': mine_b['replayAttempts']})

    board_c = open_board(tk['实跑Carol'], 'board-e2e4-carol.json')
    last = board_c['items'][-1]
    check_row('Carol（0 分）：不上榜但保留自己那一行，晋升线 = 榜上最高分', {
        'participants': 2, 'count': 3,
        'lastRealName': '实跑Carol', 'lastRank': 0, 'lastXP': 0, 'lastZone': '', 'lastIsMe': True,
        'promoteCutXp': min(a_xp, b_xp), 'gapToPromote': min(a_xp, b_xp),
    }, {
        'participants': board_c['participants'], 'count': board_c['count'],
        'lastRealName': last['realName'], 'lastRank': last['rank'], 'lastXP': last['xp'],
        'lastZone': last['zone'], 'lastIsMe': last['isMe'],
        'promoteCutXp': board_c['me']['promoteCutXp'], 'gapToPromote': board_c['me']['gapToPromote'],
    })
    check('0 分学生看到的是「整条晋升线」的差距（与原型同一句文案）', True,
          board_c['me']['gapToPromote'] == min(a_xp, b_xp) > 0)

    board_d = open_board(tk['实跑Dave'], 'board-e2e4-dave.json')
    mine_d = open_mine(tk['实跑Dave'], 'me-e2e4-dave.json')
    check_row('Dave：上周首刷 + 本周重刷 → 本周 0 分不上榜，明细 0 行 / 重刷 1 次', {
        'boardXp': 0, 'boardRank': 0, 'count': 3, 'rows': 0, 'replayAttempts': 1,
        'ledger': plan['daveLedger'],
    }, {
        'boardXp': mine_d['xp'], 'boardRank': mine_d['rank'], 'count': board_d['count'],
        'rows': len(mine_d['rows']), 'replayAttempts': mine_d['replayAttempts'],
        'ledger': sql_ledger_sum(db, user_id(db, 'S8R4')),
    })
    check('Dave 账本 = 上周 300 + 本周重刷 {}（都在账本里、都不在本周榜上）'.format(plan['daveReplayXp']),
          True, sql_ledger_sum(db, user_id(db, 'S8R4')) == 300 + plan['daveReplayXp'])

    # SQL 独立聚合对拍
    uids = [user_id(db, r[0]) for r in ROSTER4]
    cur_xp = sql_first_clear_xp(db, uids, dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)),
                                dt.datetime.combine(week_start_of(dt.date.today()) + dt.timedelta(days=7), dt.time(0, 0)))
    got = {u: v[0] for u, v in cur_xp.items()}
    id_of = {r[1]: user_id(db, r[0]) for r in ROSTER4}
    check_row('SQL 首刷口径（4 人）', {
        'alice': a_xp, 'bob': b_xp, 'carol': 0, 'dave': 0,
    }, {
        'alice': got.get(id_of['实跑Alice'], 0), 'bob': got.get(id_of['实跑Bob'], 0),
        'carol': got.get(id_of['实跑Carol'], 0), 'dave': got.get(id_of['实跑Dave'], 0),
    })
    check_row('SQL 重刷次数（Alice 1 / Bob 0 / Dave 1）', {'alice': 1, 'bob': 0, 'dave': 1}, {
        'alice': sql_replay_count(db, id_of['实跑Alice'], dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)),
                                  dt.datetime.combine(week_start_of(dt.date.today()) + dt.timedelta(days=7), dt.time(0, 0))),
        'bob': sql_replay_count(db, id_of['实跑Bob'], dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)),
                                dt.datetime.combine(week_start_of(dt.date.today()) + dt.timedelta(days=7), dt.time(0, 0))),
        'dave': sql_replay_count(db, id_of['实跑Dave'], dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)),
                                 dt.datetime.combine(week_start_of(dt.date.today()) + dt.timedelta(days=7), dt.time(0, 0))),
    })
    finish('用例② 对拍')


# ---------------------------------------------------------------- 用例③ 6 人并列班

def cmd_seed6():
    head('用例③：建「{}」6 人——并列压在晋级线上（名额 3，区内 4 人）'.format(CLASS6))
    db = db_conn()
    tok = teacher_token()
    import_class(db, tok, CLASS6, [(r[0], r[1]) for r in ROSTER6])
    cid = class_id(db, CLASS6)
    if not cid:
        raise SystemExit('班级「{}」没建起来'.format(CLASS6))
    wipe_activity(db, [r[0] for r in ROSTER6])

    unit, _ = ensure_unit(tok, cid, 8, 'S8 并列·第 1 套')
    l_last, made_last = ensure_level(tok, unit, 1, 'S8 并列关 1（上周底账）')
    l_this, made_this = ensure_level(tok, unit, 2, 'S8 并列关 2（本周底账）')
    if made_last:
        seed_paper(tok, unit, l_last, [(t, s + '（上周关）', o, a) for t, s, o, a in PAPER_H12])
    if made_this:
        seed_paper(tok, unit, l_this, [(t, s + '（本周关）', o, a) for t, s, o, a in PAPER_H12])

    now = dt.datetime.now()
    week_start = week_start_of(now.date())
    last_at = dt.datetime.combine(week_start - dt.timedelta(days=1), dt.time(20, 0))
    this_at = now - dt.timedelta(minutes=5)
    if this_at.date() < week_start:
        raise SystemExit('现在是周一 00:05 之内，本周底账摆不进本周窗，稍后再跑')
    for username, real, xp, lastxp in ROSTER6:
        uid = user_id(db, username)
        if not uid:
            raise SystemExit('学生 {} 不在库里'.format(username))
        seed_ledger_row(db, uid, l_last, unit, lastxp, last_at)
        if xp:
            seed_ledger_row(db, uid, l_this, unit, xp, this_at)
    # 底账确实在两周窗里：本周条数 = 有分的 5 人（己 0 分不写本周行），上周 6 人全写。
    counts = sql_ledger_counts(db, [user_id(db, r[0]) for r in ROSTER6],
                               dt.datetime.combine(week_start, dt.time(0, 0)),
                               dt.datetime.combine(week_start + dt.timedelta(days=7), dt.time(0, 0)),
                               last_at.date())
    check('用例③ 底账就位（本周 5 条 / 上周 6 条）', '5/6', counts)
    dump('plan-hand6.json', {'classId': cid, 'className': CLASS6, 'unitId': unit,
                             'levelLast': l_last, 'levelThis': l_this})
    finish('用例③ 造数')


def cmd_check6():
    head('用例③：6 人并列班逐字段对拍（并列跨过晋级线 / 0 分留行 / 趋势四态）')
    db = db_conn()
    cid = class_id(db, CLASS6)
    if not cid:
        raise SystemExit('先跑 seed6')
    names_xp_cur = {r[1]: r[2] for r in ROSTER6}
    names_xp_last = {r[1]: r[3] for r in ROSTER6}
    want = hand_board(names_xp_cur, names_xp_last, '边界己', {}, {})
    tok = student_token(db, 'S8T6')
    board = open_board(tok, 'board-hand6.json')

    check_row('6 人档名额（round(6×5/12)=3 / round(6×4/12)=2）+ 头部', {
        'promoteCount': 3, 'demoteCount': 2, 'classSize': 6, 'participants': 5, 'count': 6,
    }, {
        'promoteCount': board['promoteCount'], 'demoteCount': board['demoteCount'],
        'classSize': board['classSize'], 'participants': board['participants'], 'count': board['count'],
    })
    for w in want['rows'][:5]:
        check_row('榜上 {}'.format(w['realName']), w, {r['realName']: r for r in board['items']}.get(w['realName'], {}))
    check('榜按 XP 降序', True,
          all(board['items'][i]['xp'] >= board['items'][i + 1]['xp'] for i in range(len(board['items']) - 1)))
    me_row = board['items'][-1]
    check_row('我（边界己，0 分）那一行：rank 0 / 不涂色带 / 排在最后', {
        'realName': '边界己', 'rank': 0, 'xp': 0, 'zone': '', 'isMe': True,
    }, me_row)
    check_row('我那一行给的是「整条晋升线」的距离', {
        'promoteCutXp': 300, 'gapToPromote': 300,
    }, {'promoteCutXp': board['me']['promoteCutXp'], 'gapToPromote': board['me']['gapToPromote']})

    zones = [r['zone'] for r in board['items']]
    check('并列把晋级区撑成 4 人（名额 3 是「名次线」不是「人数上限」）', 4, zones.count('promote'))
    check('降级区只有 1 人（名额 2 但只有 1 人掉在区里：没分的人不占降级位）', 1, zones.count('demote'))
    check('并列第 3 的两行同 XP 同名次（300/300）', '3/3',
          '{}/{}'.format(board['items'][2]['rank'], board['items'][3]['rank']))
    check('趋势四态齐了（up/down/flat 三种徽标口径都在）',
          'up,up,flat,flat,down',
          ','.join(r['trend'] for r in board['items'][:5]))
    check('名次变化（甲 +4 / 乙 +2 / 丙 0 / 丁 -1 / 戊 -4）',
          '4,2,0,-1,-4',
          ','.join(str(r['delta']) for r in board['items'][:5]))

    uids = [user_id(db, r[0]) for r in ROSTER6]
    ws = week_start_of(dt.date.today())
    sql_xp = sql_first_clear_xp(db, uids, dt.datetime.combine(ws, dt.time(0, 0)),
                                dt.datetime.combine(ws + dt.timedelta(days=7), dt.time(0, 0)))
    got = {r[1]: (sql_xp.get(user_id(db, r[0]), (0, 0))[0]) for r in ROSTER6}
    check_row('SQL 首刷口径（6 人）', names_xp_cur, got)
    finish('用例③ 对拍')


# ---------------------------------------------------------------- 验收③ 班间 PK 同卷约束

def cmd_pk():
    head('验收③：班间 PK 同卷约束——同卷放行 / 异卷拒绝 / 无卷拒绝 / 班内直接放行')
    db = db_conn()
    tok = teacher_token()
    import_class(db, tok, CLASSPK_SAME, [('S8P1', '同卷班学生')])
    import_class(db, tok, CLASSPK_DIFF, [('S8P2', '异卷班学生')])
    import_class(db, tok, CLASSPK_NOPAPER, [('S8P3', '无卷班学生')])
    cid_same, cid_diff, cid_none = class_id(db, CLASSPK_SAME), class_id(db, CLASSPK_DIFF), class_id(db, CLASSPK_NOPAPER)
    plan4 = json.load(io.open(os.path.join(HERE, 'plan-e2e4.json'), encoding='utf-8'))
    my_cid, my_unit = plan4['classId'], plan4['unitId']

    u_same, _ = ensure_unit(tok, cid_same, 8, 'S8 实跑·第 1 套')
    l_same, made_same = ensure_level(tok, u_same, 1, 'S8 实跑关 1')
    if made_same:
        seed_paper(tok, u_same, l_same, QUESTION_SET)          # 题面内容与实跑班一模一样
    u_diff, _ = ensure_unit(tok, cid_diff, 8, 'S8 异卷·第 1 套')
    l_diff, made_diff = ensure_level(tok, u_diff, 1, 'S8 异卷关 1')
    if made_diff:
        seed_paper(tok, u_diff, l_diff, PAPER_DIFF)            # 题面内容不同
    check('陪练班就位（同卷班有同内容套题 / 异卷班有不同内容套题 / 无卷班没有单元）',
          'True/True/0', '{}/{}/{}'.format(bool(u_same), bool(u_diff),
                                           len(units_of(db, cid_none))))

    alice = student_token(db, 'S8R1')
    nopaper_stu = student_token(db, 'S8P3')
    cases = []

    code, body = api('POST', '/api/league/pk/check', alice, {'opponentClassId': my_cid, 'unitId': my_unit},
                     raw_path=os.path.join(HERE, 'pk-same-class.json'))
    cases.append(('班内对战（对手=我班）', code, unwrap(code, body, 'PK 班内')))
    code, body = api('POST', '/api/league/pk/check', alice, {'opponentClassId': cid_same, 'unitId': my_unit},
                     raw_path=os.path.join(HERE, 'pk-same-paper.json'))
    cases.append(('同卷（两班套题内容一致）', code, unwrap(code, body, 'PK 同卷')))
    code, body = api('POST', '/api/league/pk/check', alice, {'opponentClassId': cid_diff, 'unitId': my_unit},
                     raw_path=os.path.join(HERE, 'pk-diff-paper.json'))
    cases.append(('异卷（两班套题内容不同）', code, unwrap(code, body, 'PK 异卷')))
    code, body = api('POST', '/api/league/pk/check', alice, {'opponentClassId': cid_none, 'unitId': my_unit},
                     raw_path=os.path.join(HERE, 'pk-opponent-no-paper.json'))
    cases.append(('对手班没有套题', code, unwrap(code, body, 'PK 对手无卷')))
    code, body = api('POST', '/api/league/pk/check', nopaper_stu, {'opponentClassId': my_cid},
                     raw_path=os.path.join(HERE, 'pk-my-no-paper.json'))
    cases.append(('我班没有套题（不带 unitId）', code, unwrap(code, body, 'PK 我班无卷')))
    code, body = api('POST', '/api/league/pk/check', alice, {'opponentClassId': cid_same},
                     raw_path=os.path.join(HERE, 'pk-default-unit.json'))
    cases.append(('不带 unitId（默认取本班最新单元）', code, unwrap(code, body, 'PK 默认单元')))

    got = {name: (c['allowed'], c['code']) for name, _, c in cases}
    check_row('PK 六种情形结论', {
        '班内对战（对手=我班）': 'True/SAME_CLASS',   # 同班不用比卷：直接放行，samePaper 恒 false
        '同卷（两班套题内容一致）': 'True/OK',
        '异卷（两班套题内容不同）': 'False/PK_PAPER_MISMATCH',
        '对手班没有套题': 'False/PK_OPPONENT_NO_PAPER',
        '我班没有套题（不带 unitId）': 'False/PK_NO_PAPER',
        '不带 unitId（默认取本班最新单元）': 'True/OK',
    }, {k: '{}/{}'.format(v[0], v[1]) for k, v in got.items()})

    by_name = {name: data for name, _, data in cases}
    same = by_name['同卷（两班套题内容一致）']
    diff = by_name['异卷（两班套题内容不同）']
    in_class = by_name['班内对战（对手=我班）']
    check('班内对战：放行且不比卷（samePaper 恒 false）', 'True/False',
          '{}/{}'.format(in_class['allowed'], in_class['samePaper']))
    check('同卷：双方指纹一致（内容 MD5），且命中对手班那套单元', 'True/True',
          '{}/{}'.format(same['myFingerprint'] == same['opponentFingerprint'] and bool(same['myFingerprint']),
                         same['opponentUnitId'] == u_same))
    check('异卷：请求里带出了双方指纹与单元名（拒得有理有据）', 'True/True',
          '{}/{}'.format(bool(diff['myFingerprint']) and diff['myFingerprint'] != diff['opponentFingerprint'],
                         'S8 异卷·第 1 套' in diff['reason']))
    note('班内放行话术：{}'.format(in_class['reason']))
    note('同卷放行话术：{}'.format(same['reason']))
    note('异卷拒绝话术：{}'.format(diff['reason']))
    note('对手无卷话术：{}'.format(by_name['对手班没有套题']['reason']))
    note('我班无卷话术：{}'.format(by_name['我班没有套题（不带 unitId）']['reason']))
    dump('pk-cases.json', by_name)
    finish('验收③ PK')


def units_of(db, cid):
    with db.cursor() as cur:
        cur.execute('SELECT id FROM units WHERE class_id = %s', (cid,))
        return [int(r[0]) for r in cur.fetchall()]


# ---------------------------------------------------------------- 验收② 教师隐藏开关

def cmd_hidden():
    head('验收②：教师关闭排行 → 学生端脱敏（不返回，而不是返回了再由前端藏）')
    db = db_conn()
    cid = class_id(db, CLASS12)
    if not cid:
        raise SystemExit('先跑 seed12')
    tok_t = teacher_token()
    tok = student_token(db, 'S8F')
    mine_xp = {r[1]: r[2] for r in ROSTER12}['王小鱼']

    # 先埋一个"别人的"键：证明开关是合并写，不会把 settings_json 里的其他键抹掉
    with db.cursor() as cur:
        cur.execute("UPDATE classes SET settings_json = JSON_SET("
                    "CASE WHEN settings_json IS NULL OR settings_json = '' THEN '{}' ELSE settings_json END, "
                    "'$.s8_foreign_key', 'keep-me') WHERE id = %s", (cid,))

    code, body = api('POST', '/api/admin/rank-toggle', tok_t, {'classId': cid, 'public': False},
                     raw_path=os.path.join(HERE, 'hidden-toggle-off.json'))
    off = unwrap(code, body, '关闭排行')
    check_row('教师关闭回执（含留痕 id）', {'className': CLASS12, 'rankPublic': False},
              {'className': off['className'], 'rankPublic': off['rankPublic']})
    check('留痕：audit_log 里 rank_toggle 条数 ≥ 1', True,
          sql_audit_count(db, 'rank_toggle', CLASS12) >= 1)
    check_row('settings_json 合并写（rank_public=false，别人的键还在）', {'rank_public': 'False', 'foreign': 'keep-me'},
              {'rank_public': str(sql_setting(db, CLASS12, 'rank_public')),
               'foreign': str(sql_setting(db, CLASS12, 's8_foreign_key'))})

    board = open_board(tok, 'hidden-board-closed.json')
    check_row('关闭态榜头：榜单清空、名次与参与人数归零、我自己的数还在', {
        'rankPublic': False, 'hidden': True, 'items': 0, 'count': 0, 'participants': 0,
        'classSize': 12, 'meXp': mine_xp, 'meRank': 0, 'meZone': '', 'meCut': 0, 'meGap': 0,
        'hiddenTextNotEmpty': True,
    }, {
        'rankPublic': board['rankPublic'], 'hidden': board['hidden'], 'items': len(board['items']),
        'count': board['count'], 'participants': board['participants'], 'classSize': board['classSize'],
        'meXp': board['me']['xp'], 'meRank': board['me']['rank'], 'meZone': board['me']['zone'],
        'meCut': board['me']['promoteCutXp'], 'meGap': board['me']['gapToPromote'],
        'hiddenTextNotEmpty': bool(board['hiddenText'].strip()),
    })
    note('降级文案：{}'.format(board['hiddenText']))

    raw = io.open(os.path.join(HERE, 'hidden-board-closed.json'), encoding='utf-8').read()
    others = [r[1] for r in ROSTER12 if r[1] != '王小鱼']
    leaked_names = [n for n in others if n in raw]
    leaked_keys = [k for k in ('"realName"', '"teamName"', '"solo"') if k in raw]
    leaked_xp = leaked_xps(raw, [r[2] for r in ROSTER12 if r[2] != mine_xp])
    check_row('关闭态响应体不泄露他人数据', {
        '他人姓名': 0, '他人 XP': 0, '榜单键(realName/teamName/solo)': 0, 'userId 出现次数': 1,
    }, {
        '他人姓名': len(leaked_names), '他人 XP': len(leaked_xp), '榜单键(realName/teamName/solo)': len(leaked_keys),
        'userId 出现次数': raw.count('"userId"'),
    })
    if leaked_names or leaked_xp or leaked_keys:
        note('泄露明细：names={} xp={} keys={}'.format(leaked_names, leaked_xp, leaked_keys))

    mine_closed = open_mine(tok, 'hidden-me-closed.json')
    raw_mine = io.open(os.path.join(HERE, 'hidden-me-closed.json'), encoding='utf-8').read()
    check_row('关闭态「我的努力值明细」仍然只给我自己的数', {
        'xp': mine_xp, 'rows': 1, 'replayAttempts': 0,
        '他人姓名': 0, '他人 XP': 0,
    }, {
        'xp': mine_closed['xp'], 'rows': len(mine_closed['rows']),
        'replayAttempts': mine_closed['replayAttempts'],
        '他人姓名': len([n for n in others if n in raw_mine]),
        '他人 XP': len(leaked_xps(raw_mine, [r[2] for r in ROSTER12 if r[2] != mine_xp])),
    })

    # 越权探针打 10 发：不只验"拦住了"，还验"回执真的到了客户端手里"。
    # 修复前这条会红：Go 的 http server 在"请求体没读完就关连接"时会 RST，
    # 实测 30 发 3 中，客户端只看到 ConnectionReset 而看不到那条 403
    # （修在 response.Fail / FailWithData 的 drainBody；router 侧有对应单测）。
    denied = [api('POST', '/api/admin/rank-toggle', tok, {'classId': cid, 'public': False},
                  tolerate_reset=True) for _ in range(10)]
    with io.open(os.path.join(HERE, 'hidden-toggle-student-denied.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(denied[0][1], ensure_ascii=False))
    check_row('学生 token 调教师开关：10 发全被拦、且回执都拿到了（无 RST 断连）', {
        '403': 10, '40301': 10, '断连': 0,
    }, {
        '403': len([c for c, _ in denied if c == 403]),
        '40301': len([b for c, b in denied if isinstance(b, dict) and b.get('code') == 40301]),
        '断连': len([c for c, _ in denied if c == 0]),
    })
    note('学生调开关返回：HTTP {} {}'.format(denied[0][0], json.dumps(denied[0][1], ensure_ascii=False)[:120]))

    code, body = api('POST', '/api/admin/rank-toggle', tok_t, {'classId': cid, 'public': True},
                     raw_path=os.path.join(HERE, 'hidden-toggle-on.json'))
    on = unwrap(code, body, '重新公开排行')
    board_on = open_board(tok, 'hidden-board-open.json')
    check_row('重新打开后榜恢复（开关可逆）', {
        'toggleRankPublic': True, 'rankPublic': True, 'hidden': False, 'items': 12, 'participants': 12,
    }, {
        'toggleRankPublic': on['rankPublic'], 'rankPublic': board_on['rankPublic'],
        'hidden': board_on['hidden'], 'items': len(board_on['items']),
        'participants': board_on['participants'],
    })
    finish('验收② 隐藏开关')


# ---------------------------------------------------------------- 周 / 赛季结算

def build_cli():
    exe = os.path.join(REPO, 'server', 'bin', 'league-settle-s8.exe')
    out = subprocess.run(['go', 'build', '-o', exe, './cmd/league-settle'],
                         cwd=os.path.join(REPO, 'server'), capture_output=True, text=True,
                         encoding='utf-8', errors='replace')
    if out.returncode != 0:
        raise SystemExit('构建 league-settle 失败：\n{}'.format(out.stderr))
    return exe


def run_cli(exe, cid, at=None, raw_name=None):
    cmd = [exe, '-class', str(cid), '-json']
    if at:
        # 本机在 +08:00，-at 要 RFC3339 带时区（naive isoformat 会被 CLI 拒）。
        cmd += ['-at', at.strftime('%Y-%m-%dT%H:%M:%S+08:00')]
    out = subprocess.run(cmd, cwd=os.path.join(REPO, 'server'), capture_output=True, text=True,
                         encoding='utf-8', errors='replace')
    raw = out.stdout or ''
    if raw_name:
        io.open(os.path.join(HERE, raw_name), 'w', encoding='utf-8').write(raw)
    i, j = raw.find('{'), raw.rfind('}')
    if i < 0 or j < 0:
        raise SystemExit('CLI 没吐 JSON：stdout={}\nstderr={}'.format(raw[:400], out.stderr[:400]))
    data = json.loads(raw[i:j + 1])
    return data[0] if isinstance(data, list) else data


def cmd_settle():
    head('周结算 / 赛季结算 / 幂等重跑（cmd/league-settle，与 cron 同一个 SettleClass）')
    db = db_conn()
    cid = class_id(db, CLASS12)
    if not cid:
        raise SystemExit('先跑 seed12')
    exe = build_cli()
    now = dt.datetime.now()
    ws = week_start_of(now.date())
    names_xp_cur = {r[1]: r[2] for r in ROSTER12}
    names_xp_last = {r[1]: r[3] for r in ROSTER12}
    want_week = hand_board(names_xp_cur, names_xp_last, '王小鱼', {}, {})

    out1 = run_cli(exe, cid, raw_name='settle-week.json')
    check_row('周结算（cron 日常路径）：scope=week / 窗口=本周 / 12 人计分', {
        'scope': 'week', 'participants': 12, 'windowStart': ymd(ws),
        'windowEnd': ymd(ws + dt.timedelta(days=6)), 'weekLabel': week_label(ws),
        'promoteCount': want_week['promoteCount'], 'demoteCount': want_week['demoteCount'],
    }, {
        'scope': out1['scope'], 'participants': out1['participants'], 'windowStart': out1['windowStart'],
        'windowEnd': out1['windowEnd'], 'weekLabel': out1['weekLabel'],
        'promoteCount': len(out1['promote']), 'demoteCount': len(out1['demote']),
    })
    check_row('周结算名单 = 手算（晋级 5 人 / 降级 4 人，名次与 XP 逐字段一致）', {
        'promote': [(r['rank'], r['realName'], r['xp']) for r in want_week['rows'] if r['zone'] == 'promote'],
        'demote': [(r['rank'], r['realName'], r['xp']) for r in want_week['rows'] if r['zone'] == 'demote'],
    }, {
        'promote': [(r['rank'], r['realName'], r['xp']) for r in out1['promote']],
        'demote': [(r['rank'], r['realName'], r['xp']) for r in out1['demote']],
    })
    check('周结算不建赛季行（周榜只是走势快照）', 0, len(seasons_of(db, cid)))

    s_begin, s_end, _ = season_window_of(now.date())
    settle_at = dt.datetime.combine(s_end, dt.time(23, 0))
    check('赛季结算时刻还没到（本用例前提：跑在赛季最后一周的周日 23:00 前）', True, settle_at > now)
    out2 = run_cli(exe, cid, at=settle_at, raw_name='settle-season.json')
    in_season_last = s_begin <= (ws - dt.timedelta(days=1))
    season_xp = {r[1]: r[2] + (r[3] if in_season_last else 0) for r in ROSTER12}
    want_season = hand_board(season_xp, {r[1]: 0 for r in ROSTER12}, '王小鱼', {}, {})
    check_row('赛季结算：scope=season / 窗口=本赛季两周 / 归档并开出下一赛季', {
        'scope': 'season', 'participants': 12, 'windowStart': ymd(s_begin), 'windowEnd': ymd(s_end),
        'closedSeasonId': 0, 'nextSeasonIdGt0': True,
    }, {
        'scope': out2['scope'], 'participants': out2['participants'], 'windowStart': out2['windowStart'],
        'windowEnd': out2['windowEnd'], 'closedSeasonId': out2['closedSeasonId'],
        'nextSeasonIdGt0': out2['nextSeasonId'] > 0,
    })
    check_row('赛季名单 = 手算（赛季窗内累计，重刷的 450 不算）', {
        'promote': [(r['rank'], r['realName'], r['xp']) for r in want_season['rows'] if r['zone'] == 'promote'],
        'demote': [(r['rank'], r['realName'], r['xp']) for r in want_season['rows'] if r['zone'] == 'demote'],
    }, {
        'promote': [(r['rank'], r['realName'], r['xp']) for r in out2['promote']],
        'demote': [(r['rank'], r['realName'], r['xp']) for r in out2['demote']],
    })
    rows = seasons_of(db, cid)
    check_row('赛季行落库（1 行 active，名字「第 2 赛季」）', {'行数': 1, 'name': '第 2 赛季', 'status': 'active'},
              {'行数': len(rows), 'name': rows[0][1] if rows else None,
               'status': rows[0][2] if rows else None})
    check('settings_json 里的赛季号跟着走（league_season_no=2）', 2,
          int(sql_setting(db, CLASS12, 'league_season_no') or 0))

    out3 = run_cli(exe, cid, at=settle_at, raw_name='settle-rerun.json')
    check_row('同一时刻重跑：不重复开赛季（scope 掉回 week / 不建新行）', {
        'scope': 'week', 'nextSeasonId': 0, '赛季行数': 1,
    }, {'scope': out3['scope'], 'nextSeasonId': out3['nextSeasonId'], '赛季行数': len(seasons_of(db, cid))})

    tok = student_token(db, 'S8F')
    board = open_board(tok, 'board-after-settle.json')
    nb = s_end + dt.timedelta(days=1)
    check_row('结算后 GET：赛季行生效（第 2 赛季 / 下一窗 / 天数往上取整）', {
        'id': out2['nextSeasonId'], 'no': 2, 'name': '第 2 赛季',
        'start': ymd(nb), 'end': ymd(nb + dt.timedelta(days=13)),
        'daysLeft': days_left(nb + dt.timedelta(days=13), dt.datetime.now()),
        'items': 12,
    }, {
        'id': board['season']['id'], 'no': board['season']['no'], 'name': board['season']['name'],
        'start': board['season']['start'], 'end': board['season']['end'],
        'daysLeft': board['season']['daysLeft'], 'items': len(board['items']),
    })
    check_row('留痕：league_settle / league_season_settle 都在 audit_log 里', {
        'league_settle': True, 'league_season_settle': True,
    }, {
        'league_settle': sql_audit_count(db, 'league_settle', CLASS12) >= 2,
        'league_season_settle': sql_audit_count(db, 'league_season_settle', CLASS12) >= 1,
    })
    finish('周/赛季结算')


def seasons_of(db, cid):
    with db.cursor() as cur:
        cur.execute('SELECT id, name, status FROM seasons WHERE class_id = %s ORDER BY id', (cid,))
        return [(int(r[0]), r[1], r[2]) for r in cur.fetchall()]


def cmd_demo():
    """把 12 人班从「赛季结算后」拨回「第 1 赛季 + 公开」——与 4 张浏览器截图同一状态。

    整链跑完时 08-settle 会把 class12 推到第 2 赛季（那是结算用例要证明的事），
    演示态要留的是截图里那一眼能对上的状态，所以最后拨回来并**当场验一遍**：
    拨回去的不是"看起来差不多"，而是头部字段与榜上 12 行逐条等于截图那一帧。
    """
    head('回到演示态：「{}」拨回第 1 赛季 + 公开排行'.format(CLASS12))
    db = db_conn()
    cid = class_id(db, CLASS12)
    if not cid:
        raise SystemExit('先跑 seed12')
    with db.cursor() as cur:
        cur.execute('DELETE FROM seasons WHERE class_id = %s', (cid,))
        cur.execute("UPDATE classes SET settings_json = JSON_SET("
                    "CASE WHEN settings_json IS NULL OR settings_json = '' THEN '{}' ELSE settings_json END, "
                    "'$.league_season_no', 1, '$.rank_public', true) WHERE id = %s", (cid,))
    check('赛季行清空（回到「无赛季行 = 第 1 赛季」的原点）', 0, len(seasons_of(db, cid)))
    check_row('settings_json 复位（赛季号 1 / 公开，别人的键不动）', {
        'league_season_no': '1', 'rank_public': 'True', 'foreign': 'keep-me',
    }, {
        'league_season_no': str(sql_setting(db, CLASS12, 'league_season_no')),
        'rank_public': str(sql_setting(db, CLASS12, 'rank_public')),
        'foreign': str(sql_setting(db, CLASS12, 's8_foreign_key')),
    })

    tok = student_token(db, 'S8F')
    board = open_board(tok, 'demo-reset.json')
    now = dt.datetime.now()
    s_begin, s_end, _ = season_window_of(now.date())
    ws = week_start_of(now.date())
    names_xp_cur = {r[1]: r[2] for r in ROSTER12}
    names_xp_last = {r[1]: r[3] for r in ROSTER12}
    team_of = {r[1]: r[4] for r in ROSTER12}
    solo_of = {r[1]: solo_of12(r[1]) for r in ROSTER12}
    want = hand_board(names_xp_cur, names_xp_last, '王小鱼', team_of, solo_of)
    check_row('复位后榜头 = 截图那一帧（第 1 赛季 / 公开 / 剩余天数 / 5+4 名额）', {
        'rankPublic': True, 'hidden': False, 'seasonId': 0, 'no': 1, 'name': '第 1 赛季',
        'start': ymd(s_begin), 'end': ymd(s_end), 'daysLeft': days_left(s_end, now),
        'promoteCount': 5, 'demoteCount': 4, 'count': 12, 'weekLabel': week_label(ws),
    }, {
        'rankPublic': board['rankPublic'], 'hidden': board['hidden'], 'seasonId': board['season']['id'],
        'no': board['season']['no'], 'name': board['season']['name'], 'start': board['season']['start'],
        'end': board['season']['end'], 'daysLeft': board['season']['daysLeft'],
        'promoteCount': board['promoteCount'], 'demoteCount': board['demoteCount'],
        'count': board['count'], 'weekLabel': board['week']['label'],
    })
    for i, (w, got) in enumerate(zip(want['rows'], board['items'])):
        check_row('复位后榜第 {} 行 {}'.format(i + 1, w['realName']), w, got)
    check_row('复位后「我」= 截图里的第 6 名 / 差 40 XP（王小鱼）', {
        'rank': want['me']['rank'], 'xp': want['me']['xp'], 'gapToPromote': want['meGap'],
    }, {
        'rank': board['me']['rank'], 'xp': board['me']['xp'],
        'gapToPromote': board['me']['gapToPromote'],
    })
    finish('回到演示态')


# ---------------------------------------------------------------- 入口

CMDS = {
    'baseline': cmd_baseline, 'cleanup': None, 'seed12': cmd_seed12, 'check12': cmd_check12,
    'seed4': cmd_seed4, 'check4': cmd_check4, 'seed6': cmd_seed6, 'check6': cmd_check6,
    'pk': cmd_pk, 'hidden': cmd_hidden, 'settle': cmd_settle, 'demo': cmd_demo,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return 2
    name = sys.argv[1]
    if name == 'cleanup':
        cleanup(db_conn())
        finish('自建自清')
    elif name == 'baseline':
        cmd_baseline(sys.argv[2] if len(sys.argv) > 2 else 'before')
    else:
        CMDS[name]()
    print()
    print('[S8] 合计断言 {} 条，失败 {} 条'.format(len(CHECKS), len(FAILS)))
    for f in FAILS:
        print('[S8] 失败：{}'.format(f))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())