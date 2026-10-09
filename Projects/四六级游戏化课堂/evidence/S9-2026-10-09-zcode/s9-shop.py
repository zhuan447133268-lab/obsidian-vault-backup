#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9 验收（个人中心 + 福利商城 + 宠物养成 + 错题复盘 + 积分明细）真库实跑辅助。

真 MySQL :3307 + 真服务 :8080 + 真 Vite :5174；三类数据面分开对拍：
  ① 手算表（本文件常量：券价 880/300、限购 1/3、宠物 30 XP 一块、宝箱 2000）—— 人肉按规则算的期望；
  ② SQL 独立聚合（本文件另写一份 SQL，不进 service 代码）—— 底账侧的事实；
  ③ 接口回执（/api/me/*、/api/shop/redeem、/api/pet/feed）。
三方一致才算过。

自建自清：只动 S9 自建的三个班（S9商城验收班 5 人 / S9售罄验收班 1 人）与它们名下的
units/levels/questions/attempts/attempt_answers/wrong_book/xp_ledger/coupons/coupon_redeems/
teams/team_members/reminders 行，不动 1/2/7/8/9 班，不动别人的题库（题库指纹在 baseline 里比对）。

  python s9-shop.py baseline before|after   # 底账快照：17 表 / 128 列 / 别人的题库 CRC
  python s9-shop.py cleanup                 # 清掉 S9 自建数据（要重跑从这儿开始）
  python s9-shop.py seed                    # 建班/单元/关卡/题/小队 + 摆底账（写 plan-s9.json）
  python s9-shop.py redeem                  # 验收① 兑换闭环 E2E（扣分/券码唯一/超库存/超限购/积分不足）
  python s9-shop.py review                  # 验收② 复盘卡只从错题组卷（清空错题后为空）
  python s9-shop.py ledger                  # 验收④ 明细页与 SELECT * FROM xp_ledger 逐条一致
  python s9-shop.py chestpet                # 验收⑤ 宝箱发奖 2022 真题卷 + 消费不回锁 + 宠物阶段
  python s9-shop.py demo                    # 给浏览器截图摆位（S9B 重新攒错题、S9A 喂一次宠物）
  python s9-shop.py verify                  # 收尾复核：明细再对一次 + 宝箱仍解锁 + baseline after
"""
import datetime as dt
import io
import json
import os
import re
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

CLASS9 = 'S9商城验收班'   # 主验收班：兑换 / 复盘 / 明细 / 宝箱 / 宠物
CLASSZ = 'S9售罄验收班'   # 售罄班：1 人班，真配置下把券兑穿，看「已兑完」
CLASSES = (CLASS9, CLASSZ)

STU_INIT = 'S9init2026'   # 名单里填的初始密码（显式填，避免默认用学号时撞长度规则）
STU_PWD = 'S9demo2026'    # 演示学生首登改密后的密码
TEACHER = 'T0001'
TEACHER_PWDS = ('Teacher@456', 'Teacher@123')

# ---------------- 手算表：券种（与 cmd/shop-seed 的默认口径一致） ----------------
# 免旷课券：880 分 / 每人限 1 张 / 库存 = 班级人数 × 1
# 免迟到券：300 分 / 每人限 3 张 / 库存 = 班级人数 × 3
COUPON_ABSENT = ('免旷课券', 880, 1)
COUPON_LATE = ('免迟到券', 300, 3)
# 宠物：30 XP 一块奶酪；阶段 幼崽 0 / 活泼 300 / 强壮 900 / 王者 1800（累计喂养 XP）
PET_FEED_COST = 30
PET_STAGES = [('baby', '幼崽', 0), ('lively', '活泼', 300), ('strong', '强壮', 900), ('king', '王者', 1800)]
# 小队宝箱：小队本周经验（成员本周「学习所得」，ref_type 只认 attempt/review）满 2000 解锁
CHEST_THRESHOLD = 2000
# 复盘基础分（与闯关的单题基础分同一个数：20）
REVIEW_BASE_XP = 20
# 复盘卷一次最多组几题
REVIEW_PAPER_MAX = 10
# 流水码 → 人话（手抄一份，不复用生产代码的 map：两边一致才算过）
REASON_LABELS = {
    'answer_base': '答题基础分', 'answer_speed': '速度加成', 'answer_combo': '连击加成',
    'level_clear': '通关奖励', 'star3_bonus': '三星奖励', 'boss_correct': 'Boss 答对',
    'boss_perfect': 'Boss 满分奖励', 'attempt_voided': '本次闯关未通过，得分作废',
    'shop_redeem': '兑换福利券', 'pet_feed': '喂养宠物消耗',
}
# 券码：C46- + 8 位，字符集去掉易混字符
CODE_RE = re.compile(r'^C46-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{8}$')

# ---------------- 名单 ----------------
# S9A 兑换生：验收①主角（真打关 + 兑换 + 限购 + 明细）
# S9B 复盘生：验收②主角（真打关攒错题 + 复盘清空）
# S9C 队友：宝箱/宠物主角（与 S9E 组双人队，本周经验刻意摆成正好 2000）
# S9D 边界生：售罄边界探针（有余额、没超限购、就是没货）
# S9E 穷学生：积分不足探针（余额 0）+ 宝箱队队员（0 分，便于把队内经验摆成 2000 整）
ROSTER9 = [('S9A', '兑换生'), ('S9B', '复盘生'), ('S9C', '队友'), ('S9D', '边界生'), ('S9E', '穷学生')]
ROSTERZ = [('S9Z', '售罄生')]
# 底账摆位（直写 attempts + xp_ledger；真实链路一关只挣 ~150，买不起 880 的券，也撞不到限购边界）
SEED_XP = {'S9A': 2400, 'S9B': 600, 'S9C': 2000, 'S9D': 600, 'S9Z': 1000}

LEVEL_NAME = 'S9 验收第 1 关'
UNIT_NAME = 'S9 验收单元'
# 题干里每题的正确项都在 0 号位（建题时 answerIdx='0'）；卷面选项被 shuffle_seed 洗过序，
# 所以作答时要按**题干文本**把正确项对回卷面下标，不假设它还在第一位。
QUESTION_SET = [
    ('vocab', 'S9 验收第 1 题：选出与 acquire 意思最接近的词', ['获得', '放弃', '燃烧', '测量']),
    ('vocab', 'S9 验收第 2 题：选出与 fragile 意思最接近的词', ['易碎的', '沉重的', '宽敞的', '干燥的']),
    ('vocab', 'S9 验收第 3 题：选出与 reluctant 意思最接近的词', ['不情愿的', '最近的', '可靠的', '响亮的']),
    ('vocab', 'S9 验收第 4 题：选出与 abundant 意思最接近的词', ['充足的', '模糊的', '昂贵的', '抽象的']),
    ('vocab', 'S9 验收第 5 题：选出与 deliberate 意思最接近的词', ['故意的', '美味的', '稀有的', '紧急的']),
    ('vocab', 'S9 验收第 6 题：选出与 transparent 意思最接近的词', ['透明的', '坚固的', '潮湿的', '遥远的']),
]

CHECKS = []
FAILS = []


# ---------------------------------------------------------------- 基础工具

def check(desc, want, got):
    ok = str(want) == str(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[S9] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


def head(msg):
    print()
    print('--- ' + msg + ' ---')


def fmt_map(d):
    return '{' + ', '.join('{}={}'.format(k, d[k]) for k in d) + '}'


def check_row(desc, want, got):
    """逐字段对拍：一个字段一条比对，失败时把不一致的字段单列一行。"""
    got = {k: got.get(k) for k in want} if isinstance(got, dict) else got
    diffs = [k for k in want if str(want[k]) != str(got.get(k))]
    ok = not diffs
    CHECKS.append({'desc': desc, 'want': fmt_map(want), 'got': fmt_map(got), 'ok': ok})
    print('[S9] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', fmt_map(want), fmt_map(got)))
    if not ok:
        FAILS.append(desc)
        for k in diffs:
            print('      ↳ 字段 {} 期望={} 实际={}'.format(k, want[k], got.get(k)))


def finish(step):
    bad = len(FAILS)
    print('[S9] 本步断言 {} 条，失败 {} 条 —— {}'.format(len(CHECKS), bad, step))
    if not CHECKS:
        raise SystemExit('{} 一条断言都没跑，脚本有问题'.format(step))


def dump(name, obj):
    path = os.path.join(HERE, name)
    with io.open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    note('写出 {}'.format(name))


# ---------------------------------------------------------------- 连接与请求

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
                           autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def api(method, path, token=None, body=None, raw_body=None, content_type=None):
    """统一信封：返回 (http_code, json_or_text)。"""
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        code = e.code
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


def student_token(username):
    """演示学生登录：名单里的初始密码首登必改密，改到 STU_PWD 后业务口才放行。"""
    got = login(username, STU_PWD)
    if got and not got.get('mustChangePwd'):
        return got['token']
    got = login(username, STU_INIT)
    if got and got.get('mustChangePwd'):
        code, body = api('POST', '/api/auth/chpwd', got['token'],
                         {'oldPassword': STU_INIT, 'newPassword': STU_PWD})
        if code != 200:
            raise SystemExit('{} 改密失败：{}'.format(username, body))
        got = login(username, STU_PWD)
        if got and not got.get('mustChangePwd'):
            return got['token']
    raise SystemExit('{} 登录失败或仍在未改密状态（{} / {}）'.format(username, STU_PWD, STU_INIT))


def teacher_token():
    for pwd in TEACHER_PWDS:
        got = login(TEACHER, pwd)
        if got and got.get('token'):
            return got['token']
    raise SystemExit('教师账号 {} 登录失败'.format(TEACHER))


# ---------------------------------------------------------------- 独立 SQL（期望值另算一份）

def q(db, sql, args=None):
    with db.cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def one(db, sql, args=None):
    rows = q(db, sql, args)
    return rows[0] if rows else None


def scalar(db, sql, args=None, default=0):
    row = one(db, sql, args)
    if not row:
        return default
    val = list(row.values())[0]
    return default if val is None else val


def sql_balance(db, uid):
    return int(scalar(db, 'SELECT COALESCE(SUM(delta), 0) AS v FROM xp_ledger WHERE user_id = %s', (uid,)))


def sql_week_learn_xp(db, uids, week_start):
    """「学习所得」口径：本周 ref_type ∈ (attempt, review) 的净得（消费负流水不算）。"""
    if not uids:
        return 0
    fmt = ','.join(['%s'] * len(uids))
    return int(scalar(db,
        'SELECT COALESCE(SUM(delta), 0) AS v FROM xp_ledger '
        'WHERE user_id IN ({}) AND created_at >= %s AND ref_type IN (%s, %s)'.format(fmt),
        tuple(uids) + (week_start, 'attempt', 'review')))


def sql_ledger_rows(db, uid, limit=None, offset=0):
    sql = ('SELECT id, delta, reason, ref_type, ref_id, DATE_FORMAT(created_at, %s) AS created_at '
           'FROM xp_ledger WHERE user_id = %s ORDER BY id DESC')
    args = ['%Y-%m-%d %H:%i', uid]
    if limit is not None:
        sql += ' LIMIT %s OFFSET %s'
        args += [limit, offset]
    return q(db, sql, tuple(args))


def sql_uid(db, username):
    row = one(db, 'SELECT id FROM users WHERE username = %s', (username,))
    return int(row['id']) if row else 0


def sql_cid(db, name):
    row = one(db, 'SELECT id FROM classes WHERE name = %s', (name,))
    return int(row['id']) if row else 0


def sql_coupon(db, class_id, name):
    return one(db, 'SELECT id, class_id, name, cost_xp, stock, per_user_limit, enabled FROM coupons '
                   'WHERE class_id = %s AND name = %s', (class_id, name))


def sql_student_count(db, class_id):
    return int(scalar(db, 'SELECT COUNT(*) AS v FROM users WHERE class_id = %s AND role = %s',
                      (class_id, 'student')))


def sql_redeem_rows(db, uid):
    return q(db, 'SELECT id, coupon_id, code, status FROM coupon_redeems WHERE user_id = %s ORDER BY id',
             (uid,))


def week_start_of(day):
    return day - dt.timedelta(days=day.weekday())


def ymd(d):
    return d.strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------- 自建自清

def cleanup(db):
    head('自建自清：删掉 S9 自建班级与它们名下的一切')
    ids = [cid for cid in (sql_cid(db, n) for n in CLASSES) if cid]
    if not ids:
        note('没有 S9 自建班级，跳过')
        return
    fmt = ','.join(['%s'] * len(ids))
    with db.cursor() as cur:
        cur.execute('SELECT id FROM users WHERE class_id IN ({})'.format(fmt), tuple(ids))
        uids = [int(r['id']) for r in cur.fetchall()]
        cur.execute('SELECT id FROM units WHERE class_id IN ({})'.format(fmt), tuple(ids))
        unit_ids = [int(r['id']) for r in cur.fetchall()]
        level_ids = []
        if unit_ids:
            uf = ','.join(['%s'] * len(unit_ids))
            cur.execute('SELECT id FROM levels WHERE unit_id IN ({})'.format(uf), tuple(unit_ids))
            level_ids = [int(r['id']) for r in cur.fetchall()]
        cur.execute('SELECT id FROM coupons WHERE class_id IN ({})'.format(fmt), tuple(ids))
        coupon_ids = [int(r['id']) for r in cur.fetchall()]
        if uids:
            uf = ','.join(['%s'] * len(uids))
            cur.execute('SELECT id FROM attempts WHERE user_id IN ({})'.format(uf), tuple(uids))
            att_ids = [int(r['id']) for r in cur.fetchall()]
            if att_ids:
                af = ','.join(['%s'] * len(att_ids))
                cur.execute('DELETE FROM attempt_answers WHERE attempt_id IN ({})'.format(af), tuple(att_ids))
                cur.execute('DELETE FROM xp_ledger WHERE ref_type = %s AND ref_id IN ({})'.format(af),
                            tuple(['attempt'] + att_ids))
                cur.execute('DELETE FROM attempts WHERE id IN ({})'.format(af), tuple(att_ids))
            cur.execute('DELETE FROM xp_ledger WHERE user_id IN ({})'.format(uf), tuple(uids))
            cur.execute('DELETE FROM wrong_book WHERE user_id IN ({})'.format(uf), tuple(uids))
            cur.execute('DELETE FROM reminders WHERE from_user IN ({0}) OR to_user IN ({0})'.format(uf),
                        tuple(uids) + tuple(uids))
            cur.execute('SELECT id FROM teams WHERE class_id IN ({})'.format(fmt), tuple(ids))
            tids = [int(r['id']) for r in cur.fetchall()]
            if tids:
                tf = ','.join(['%s'] * len(tids))
                cur.execute('DELETE FROM team_members WHERE team_id IN ({})'.format(tf), tuple(tids))
                cur.execute('DELETE FROM teams WHERE id IN ({})'.format(tf), tuple(tids))
        if coupon_ids:
            cf = ','.join(['%s'] * len(coupon_ids))
            cur.execute('DELETE FROM coupon_redeems WHERE coupon_id IN ({})'.format(cf), tuple(coupon_ids))
            cur.execute('DELETE FROM coupons WHERE id IN ({})'.format(cf), tuple(coupon_ids))
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
    note('已删除班级 {} 及其学生/单元/关卡/题目/成绩/券/小队行'.format(ids))


# ---------------------------------------------------------------- 建数据

def import_class(db, tok, class_name, rows):
    """建班 + 导学生（multipart CSV）——与教师真实操作同一条链路。"""
    if sql_cid(db, class_name):
        note('班级「{}」已存在，跳过导入'.format(class_name))
        return
    buf = io.StringIO()
    buf.write('班级,学号,姓名,初始密码\n')
    for username, real in rows:
        buf.write('{},{},{},{}\n'.format(class_name, username, real, STU_INIT))
    content = buf.getvalue().encode('utf-8-sig')
    boundary = '----s9boundary' + uuid.uuid4().hex
    body = b''.join([
        ('--{}\r\n'.format(boundary)).encode('utf-8'),
        'Content-Disposition: form-data; name="file"; filename="roster.csv"\r\n'.encode('utf-8'),
        b'Content-Type: text/csv\r\n\r\n',
        content,
        ('\r\n--{}--\r\n'.format(boundary)).encode('utf-8'),
    ])
    code, resp = api('POST', '/api/admin/import-users', tok, raw_body=body,
                     content_type='multipart/form-data; boundary=' + boundary)
    if code != 200:
        raise SystemExit('导入 {} 失败（HTTP {}）：{}'.format(class_name, code, resp))
    note('导入班级「{}」{} 人（初始密码 {}）'.format(class_name, len(rows), STU_INIT))


def ensure_unit(tok, cid, week_no, unit_name):
    db = db_conn()
    row = one(db, 'SELECT id FROM units WHERE class_id = %s AND name = %s', (cid, unit_name))
    db.close()
    if row:
        return int(row['id'])
    code, body = api('POST', '/api/admin/units', tok,
                     {'classId': cid, 'weekNo': week_no, 'name': unit_name})
    if code != 200:
        raise SystemExit('建单元失败：{}'.format(body))
    return int(body['data']['id'])


def ensure_level(tok, unit_id, seq, name, typ='vocab', limit=300):
    db = db_conn()
    row = one(db, 'SELECT id FROM levels WHERE unit_id = %s AND name = %s', (unit_id, name))
    db.close()
    if row:
        return int(row['id'])
    code, body = api('POST', '/api/admin/levels', tok,
                     {'unitId': unit_id, 'seq': seq, 'name': name, 'type': typ,
                      'timeLimit': limit, 'isBoss': False})
    if code != 200:
        raise SystemExit('建关卡失败：{}'.format(body))
    return int(body['data']['id'])


def ensure_questions(tok, level_id):
    """往关卡里塞整套题（幂等：按题干查重）。exp（解析）是后台建题的必填项。"""
    db = db_conn()
    out = []
    for typ, stem, opts in QUESTION_SET:
        row = one(db, 'SELECT id FROM questions WHERE level_id = %s AND stem = %s', (level_id, stem))
        if row:
            out.append(int(row['id']))
            continue
        exp = 'S9 验收用题解析：正确答案是「{}」。'.format(opts[0])
        code, body = api('POST', '/api/admin/questions', tok,
                         {'levelId': level_id, 'band': '4', 'type': typ, 'stem': stem,
                          'options': opts, 'answerIdx': '0', 'exp': exp, 'enabled': True})
        if code != 200:
            raise SystemExit('建题目失败：{}'.format(body))
        out.append(int(body['data']['id']))
    db.close()
    return out


def seed_ledger_row(db, uid, level_id, unit_id, xp, when):
    """直写一行「已交卷」底账：attempts + xp_ledger。

    只用于**把分摆到指定位置**（真实链路一关 ~150 XP，买不起 880 的券、也撞不到限购/售罄边界）。
    行本身是真的：attempt 是 finished 的真行，xp_ledger 的 ref 指向它，
    所以明细页照样解析得出关卡名——「每一分来源可查」这条验收不受影响。
    """
    with db.cursor() as cur:
        cur.execute(
            'INSERT INTO attempts (user_id, level_id, unit_id, correct, total, stars, score710, '
            'xp_earned, shuffle_seed, status, started_at, finished_at) '
            'VALUES (%s, %s, %s, 6, 6, 3, 710, %s, 0, %s, %s, %s)',
            (uid, level_id, unit_id, xp, 'finished', when, when))
        att_id = int(cur.lastrowid)
        cur.execute(
            'INSERT INTO xp_ledger (user_id, delta, reason, ref_type, ref_id, created_at) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (uid, xp, 'answer_base', 'attempt', att_id, when))
    return att_id


# ---------------------------------------------------------------- 打关（真实链路）

def bank_of(db, qids):
    fmt = ','.join(['%s'] * len(qids))
    rows = q(db, 'SELECT id, options_json, answer_idx FROM questions WHERE id IN ({})'.format(fmt),
             tuple(qids))
    out = {}
    for r in rows:
        opts = json.loads(r['options_json'] or '[]')
        idx = int(r['answer_idx'])
        out[int(r['id'])] = opts[idx]
    return out


def play_level(token, level_id, wrong_ids=(), elapsed_ms=2000):
    """真打一关：取卷 → 按对错逐题作答 → 交卷。

    wrong_ids 里的题目**故意答错**（选一个不是正确项的卷面下标），其余全对。
    返回 (settlement, paper, feedbacks)：feedbacks 按题 id 索引。
    """
    code, body = api('GET', '/api/quiz/paper?level={}'.format(level_id), token)
    paper = unwrap(code, body, '取卷 L{}'.format(level_id))
    qids = [int(x['id']) for x in paper['questions']]
    db = db_conn()
    correct_text = bank_of(db, qids)
    db.close()
    answers = []
    for item in paper['questions']:
        qid = int(item['id'])
        want = correct_text[qid]
        disp = item['options'].index(want)
        picked = disp
        if qid in wrong_ids:
            picked = (disp + 1) % len(item['options'])
        answers.append({'questionId': qid, 'pickedIdx': str(picked), 'elapsedMs': elapsed_ms})
    code, body = api('POST', '/api/quiz/submit', token,
                     {'attemptId': paper['attemptId'], 'answers': answers})
    data = unwrap(code, body, '交卷 L{}'.format(level_id))
    if not data.get('settlement'):
        raise SystemExit('交卷回执没有 settlement：{}'.format(data))
    return data['settlement'], paper, data


# ---------------------------------------------------------------- 底账快照

def cmd_baseline(out='before'):
    head('底账快照：表 / 列 / 别人的题库指纹（S9 只写数据行，不动表结构、不动别人的题库）')
    db = db_conn()
    # S9 自己会建单元/关卡/题（那正是它要证明的写入），所以底账比对要**排除自建班**，
    # 只盯「别人家的题库有没有被动过」。三条都要经 classes 回连，别拿单元名硬比班名。
    fmt = ','.join(['%s'] * len(CLASSES))
    others = tuple(CLASSES)
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS v FROM information_schema.tables WHERE table_schema = DATABASE()')
        tables = int(cur.fetchone()['v'])
        cur.execute('SELECT COUNT(*) AS v FROM information_schema.columns WHERE table_schema = DATABASE()')
        cols = int(cur.fetchone()['v'])
        counts = {}
        for t, clause in (('units', 'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({})'.format(fmt)),
                          ('levels', 'JOIN units u ON u.id = l.unit_id JOIN classes c ON c.id = u.class_id '
                                     'WHERE c.name NOT IN ({})'.format(fmt)),
                          ('questions', 'JOIN levels l ON l.id = q.level_id JOIN units u ON u.id = l.unit_id '
                                        'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({})'.format(fmt))):
            alias = {'units': 'units u', 'levels': 'levels l', 'questions': 'questions q'}[t]
            cur.execute('SELECT COUNT(*) AS v FROM {} {}'.format(alias, clause), others)
            counts[t] = int(cur.fetchone()['v'])
        cur.execute('SELECT q.id, q.stem, q.options_json FROM questions q '
                    'JOIN levels l ON l.id = q.level_id JOIN units u ON u.id = l.unit_id '
                    'JOIN classes c ON c.id = u.class_id WHERE c.name NOT IN ({}) '
                    'ORDER BY q.id'.format(fmt), others)
        qs = cur.fetchall()
    db.close()
    crc = 0
    for row in qs:
        crc = (crc + zlib.crc32('{}\x1f{}\x1f{}'.format(row['id'], row['stem'] or '',
                                                        row['options_json'] or '').encode('utf-8'))) & 0xffffffff
    lines = ['tables={}'.format(tables), 'columns={}'.format(cols),
             'units={}'.format(counts['units']), 'levels={}'.format(counts['levels']),
             'questions={}'.format(counts['questions']), 'bank_crc={}'.format(crc)]
    with io.open(os.path.join(HERE, 'baseline-{}.txt'.format(out)), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    note('别人的底账（表/列/单元/关/题/题库 CRC）：{}'.format(
        '/'.join(x.split('=')[1] for x in lines)))
    check('表数仍是 17（S9 不加表）', 17, tables)
    check('列数仍是 128（S9 不改列）', 128, cols)
    if out == 'before':
        note('before 快照已落盘（units/levels/questions 数 + 题库 CRC），收尾用 after 比')
    finish('底账快照 ' + out)


# ---------------------------------------------------------------- 步骤：seed

def cmd_seed():
    db = db_conn()
    cleanup(db)
    head('建班 / 单元 / 关卡 / 题 / 小队 + 摆底账')
    tok = teacher_token()
    import_class(db, tok, CLASS9, ROSTER9)
    import_class(db, tok, CLASSZ, ROSTERZ)
    cid9 = sql_cid(db, CLASS9)
    cidz = sql_cid(db, CLASSZ)
    check('主验收班在库且 5 人（库存 = 人数 × 限购 的基数）', 5, sql_student_count(db, cid9))
    check('售罄班在库且 1 人', 1, sql_student_count(db, cidz))

    unit_id = ensure_unit(tok, cid9, 1, UNIT_NAME)
    level_id = ensure_level(tok, unit_id, 1, LEVEL_NAME)
    qids = ensure_questions(tok, level_id)
    check('验收单元/关卡建成', 1, 1 if (unit_id and level_id) else 0)
    check('关卡里 6 道题（3 次打关的错题基数）', len(QUESTION_SET), len(qids))
    check('题都在 band=4（学生 target 是四级）', 6,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM questions WHERE level_id = %s AND band = %s',
                     (level_id, '4'))))

    # 小队：宝箱口径是「队内成员本周学习所得」，所以两支队伍分开摆——
    # S9 宝箱队 = S9C + S9E（C 2000 + E 0 = 正好 2000，喂宠物把余额压到 2000 以下才好验「不回锁」）。
    tokens = {u: student_token(u) for u, _ in ROSTER9 + ROSTERZ}
    rec, body = api('POST', '/api/team/create', tokens['S9C'], {'name': 'S9 宝箱队', 'emoji': '🐹'})
    if rec != 200:
        raise SystemExit('建队失败：{}'.format(body))
    team_id = int(body['data'].get('id') or 0)
    if not team_id:
        team_id = int(scalar(db, 'SELECT id FROM teams WHERE class_id = %s AND name = %s ORDER BY id DESC',
                             (cid9, 'S9 宝箱队')))
    # 队员 S9E 入队（队号即邀请码）
    rec, body = api('POST', '/api/team/join', tokens['S9E'], {'teamId': team_id})
    if rec != 200:
        raise SystemExit('入队失败：{}'.format(body))
    members = int(scalar(db, 'SELECT COUNT(*) AS v FROM team_members WHERE team_id = %s AND left_at IS NULL',
                         (team_id,)))
    check('宝箱队 2 人（不是单人队，单人队不解锁宝箱）', 2, members)

    # 底账摆位：本周（周一 00:00 之后）写 attempts + xp_ledger
    ws = ymd(dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)))
    for username, xp in SEED_XP.items():
        uid = sql_uid(db, username)
        # 2000 分成两行：明细页里一行看不出"摆位"，两行更像真账
        half = xp // 2
        seed_ledger_row(db, uid, level_id, unit_id, half, ws)
        seed_ledger_row(db, uid, level_id, unit_id, xp - half, ws)
    for username, xp in sorted(SEED_XP.items()):
        uid = sql_uid(db, username)
        check('底账摆位 {} 余额 {}'.format(username, xp), xp, sql_balance(db, uid))
    check('没摆位的 S9E 余额 0（积分不足探针）', 0, sql_balance(db, sql_uid(db, 'S9E')))
    team_members = [sql_uid(db, 'S9C'), sql_uid(db, 'S9E')]
    check('宝箱队本周学习所得正好 {}'.format(CHEST_THRESHOLD), CHEST_THRESHOLD,
          sql_week_learn_xp(db, team_members, ws))

    plan = {
        'class9': cid9, 'classz': cidz, 'unit': unit_id, 'level': level_id, 'questions': qids,
        'team': team_id, 'week_start': ws, 'seed_xp': SEED_XP,
        'users': {u: sql_uid(db, u) for u, _ in ROSTER9 + ROSTERZ},
        'hand': {
            'absent': '{} {} / 限 {} 张 / 库存 5'.format(COUPON_ABSENT[0], COUPON_ABSENT[1], COUPON_ABSENT[2]),
            'late': '{} {} / 限 {} 张 / 库存 15'.format(COUPON_LATE[0], COUPON_LATE[1], COUPON_LATE[2]),
            'pet_feed_cost': PET_FEED_COST, 'chest_threshold': CHEST_THRESHOLD,
        },
    }
    dump('plan-s9.json', plan)
    db.close()
    finish('建数据')


# ---------------------------------------------------------------- 步骤：redeem（验收①）

def cmd_redeem():
    db = db_conn()
    head('验收① 兑换闭环 E2E：真打关挣分 → 兑券 → 扣分/券码唯一/超库存/超限购/积分不足')
    cid9 = sql_cid(db, CLASS9)
    cidz = sql_cid(db, CLASSZ)
    level_id = int(scalar(db, 'SELECT id FROM levels WHERE name = %s', (LEVEL_NAME,)))
    tok = {u: student_token(u) for u, _ in ROSTER9 + ROSTERZ}
    absent = sql_coupon(db, cid9, COUPON_ABSENT[0])
    late = sql_coupon(db, cid9, COUPON_LATE[0])
    if not absent or not late:
        raise SystemExit('券种还没上架：先跑 03-shop-seed（cmd/shop-seed）')
    check('免旷课券上架（{} 分 / 限 {} 张）'.format(COUPON_ABSENT[1], COUPON_ABSENT[2]),
          [COUPON_ABSENT[1], COUPON_ABSENT[2], 1], [absent['cost_xp'], absent['per_user_limit'], absent['enabled']])
    check('免迟到券上架（{} 分 / 限 {} 张）'.format(COUPON_LATE[1], COUPON_LATE[2]),
          [COUPON_LATE[1], COUPON_LATE[2], 1], [late['cost_xp'], late['per_user_limit'], late['enabled']])
    check('免旷课券库存 = 人数 × 限购（5×1）', 5, absent['stock'])
    check('免迟到券库存 = 人数 × 限购（5×3）', 15, late['stock'])

    uid_a = sql_uid(db, 'S9A')
    seed_balance = sql_balance(db, uid_a)

    # ---- 真实链路先挣一次分：全对通关，账本上的每一行都由引擎写 ----
    settle, paper, data = play_level(tok['S9A'], level_id, wrong_ids=())
    attempt_xp = int(scalar(db, 'SELECT COALESCE(SUM(delta), 0) AS v FROM xp_ledger '
                                'WHERE user_id = %s AND ref_type = %s AND ref_id = %s',
                            (uid_a, 'attempt', paper['attemptId'])))
    check('首通结算 XP 与账本该次闯关净得一致', settle['xpTotal'], attempt_xp)
    note('S9A：摆位 {} + 真打关 {} = {}'.format(seed_balance, attempt_xp, seed_balance + attempt_xp))
    check('余额 = 摆位 + 真打关净得（余额唯一来源是账本）', seed_balance + attempt_xp, sql_balance(db, uid_a))

    ov = unwrap(*api('GET', '/api/me/overview', tok['S9A']), 'S9A 个人中心')
    check('用户卡 XP = 账本聚合', sql_balance(db, uid_a), ov['user']['xp'])
    check('商城只上架本班 2 张券（系统奖励券 cost_xp=0 不算商品）', 2, len(ov['shop']['items']))
    check('商城按券价升序：先 300 的免迟到券', COUPON_LATE[0], ov['shop']['items'][0]['name'])
    check('券包初始为空', 0, ov['wallet']['total'])
    shop = {it['name']: it for it in ov['shop']['items']}
    check_row('免迟到券的可兑状态（余额够 → 能兑）',
              {'costXp': 300, 'perUserLimit': 3, 'owned': 0, 'canRedeem': True, 'reject': ''},
              shop[COUPON_LATE[0]])

    # ---- 积分不足：S9E 余额 0，券有货、没超限购 → 40011 ----
    code, body = api('POST', '/api/shop/redeem', tok['S9E'], {'couponId': absent['id']})
    check('积分不足 → HTTP 400', 400, code)
    check('积分不足 → 业务码 40011', 40011, body['code'])
    note('回执文案：{}'.format(body['message']))
    check('被拒的兑换不落券', 0, len(sql_redeem_rows(db, sql_uid(db, 'S9E'))))
    ov_e = unwrap(*api('GET', '/api/me/overview', tok['S9E']), 'S9E 个人中心')
    shop_e = {it['name']: it for it in ov_e['shop']['items']}
    check_row('S9E 的商城按钮口径（前端灰按钮的依据）',
              {'canRedeem': False, 'reject': 'not_enough_xp', 'rejectText': '还差 880 分'},
              shop_e[COUPON_ABSENT[0]])

    # ---- 越权：别班的券一律当作不存在（404，不承认它存在过） ----
    z_coupon = sql_coupon(db, cidz, COUPON_LATE[0])
    if z_coupon:
        code, body = api('POST', '/api/shop/redeem', tok['S9A'], {'couponId': z_coupon['id']})
        check('兑别班的券 → HTTP 404（不承认存在过）', 404, code)
        check('兑别班的券 → 业务码 40401', 40401, body['code'])

    # ---- 兑换成功：扣分正确 + 券码唯一 ----
    before = sql_balance(db, uid_a)
    before_stock = int(absent['stock'])
    code, body = api('POST', '/api/shop/redeem', tok['S9A'], {'couponId': absent['id']})
    rb = unwrap(code, body, 'S9A 兑免旷课券')
    check('兑换回执扣分 = 券价', COUPON_ABSENT[1], rb['costXp'])
    check('兑换回执余额 = 扣前 − 券价', before - COUPON_ABSENT[1], rb['balance'])
    check('兑换回执余额 = 账本聚合（当场可验）', sql_balance(db, uid_a), rb['balance'])
    check('兑换回执库存 = 扣前 − 1', before_stock - 1, rb['stockLeft'])
    check('券码格式 C46-XXXXXXXX（去掉易混字符）', True, bool(CODE_RE.match(rb['coupon']['code'])))
    check('回执状态 pending（待老师确认，系统不自动承诺）', 'pending', rb['coupon']['status'])
    check('回执状态文案「待老师确认」', '待老师确认', rb['coupon']['statusText'])
    check('回执来源「商城兑换」', '商城兑换', rb['coupon']['source'])
    led = one(db, 'SELECT delta, reason, ref_type, ref_id FROM xp_ledger WHERE user_id = %s '
                  'ORDER BY id DESC LIMIT 1', (uid_a,))
    check_row('兑换写出的负流水（ref 指向券种）',
              {'delta': -COUPON_ABSENT[1], 'reason': 'shop_redeem', 'ref_type': 'coupon',
               'ref_id': absent['id']},
              led)

    # ---- 超每人限购：同一张券再兑一次 → 40903（限购挡在积分之前） ----
    code, body = api('POST', '/api/shop/redeem', tok['S9A'], {'couponId': absent['id']})
    check('超每人限购 → HTTP 409', 409, code)
    check('超每人限购 → 业务码 40903', 40903, body['code'])
    note('回执文案：{}'.format(body['message']))

    # ---- 再兑一张 300 的（券码必须与上一张不同） ----
    code, body = api('POST', '/api/shop/redeem', tok['S9A'], {'couponId': late['id']})
    rb2 = unwrap(code, body, 'S9A 兑免迟到券')
    check('第二张券的券码与第一张不同', True, rb2['coupon']['code'] != rb['coupon']['code'])
    check('两张券在用同一个券种的不同张数上（owned=1）', 1, rb2['owned'])

    # ---- 券码唯一：全库范围去重后条数不变 ----
    total_codes = int(scalar(db, 'SELECT COUNT(*) AS v FROM coupon_redeems'))
    uniq_codes = int(scalar(db, 'SELECT COUNT(DISTINCT code) AS v FROM coupon_redeems'))
    check('券码全库唯一（条数 = 去重后条数）', total_codes, uniq_codes)
    a_rows = sql_redeem_rows(db, uid_a)
    check('S9A 券包 2 张（pending）', 2, len(a_rows))
    check('两张券码都合规', 2, sum(1 for r in a_rows if CODE_RE.match(r['code'])))

    # ---- 超库存边界：把免迟到券库存摆到 1（真配置下 stock = 人数 × 限购，全班兑满才售罄，
    #      要观测「有余额、没超限购、就是没货」这一条，得先把库存摆到 1） ----
    with db.cursor() as cur:
        cur.execute('UPDATE coupons SET stock = 1 WHERE id = %s', (late['id'],))
    note('免迟到券库存摆到 1（其余不动）')
    code, body = api('POST', '/api/shop/redeem', tok['S9B'], {'couponId': late['id']})
    rb3 = unwrap(code, body, 'S9B 买走最后一张免迟到券')
    check('买走最后一张后库存为 0', 0, rb3['stockLeft'])
    code, body = api('POST', '/api/shop/redeem', tok['S9D'], {'couponId': late['id']})
    check('超库存 → HTTP 409', 409, code)
    check('超库存 → 业务码 40902', 40902, body['code'])
    note('回执文案：{}'.format(body['message']))
    check('被拒的兑换不落券（S9D 无券）', 0, len(sql_redeem_rows(db, sql_uid(db, 'S9D'))))
    check('被拒的兑换不扣分（S9D 无 shop_redeem 流水）', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM xp_ledger WHERE user_id = %s AND reason = %s',
                     (sql_uid(db, 'S9D'), 'shop_redeem'))))
    left = int(one(db, 'SELECT stock FROM coupons WHERE id = %s', (late['id'],))['stock'])
    check('库存没有被扣成负数', 0, left)
    ov_d = unwrap(*api('GET', '/api/me/overview', tok['S9D']), 'S9D 个人中心')
    shop_d = {it['name']: it for it in ov_d['shop']['items']}
    check_row('S9D 的商城按钮口径（售罄）',
              {'canRedeem': False, 'reject': 'out_of_stock', 'rejectText': '已兑完', 'stock': 0},
              shop_d[COUPON_LATE[0]])

    # ---- 真配置售罄：售罄班 1 人，限 3 张、库存 3 张，学生把券兑穿 → 状态与再兑都售罄 ----
    z_coupon = sql_coupon(db, cidz, COUPON_LATE[0])
    if z_coupon:
        check('售罄班库存 = 1 人 × 限购 3', 3, z_coupon['stock'])
        lefts = []
        for i in range(3):
            code, body = api('POST', '/api/shop/redeem', tok['S9Z'], {'couponId': z_coupon['id']})
            if code != 200:
                raise SystemExit('第 {} 张应该买到，实际 {}：{}'.format(i + 1, code, body))
            lefts.append(body['data']['stockLeft'])
        check('连买 3 张的剩余库存 2/1/0（真配置兑穿）', [2, 1, 0], lefts)
        code, body = api('POST', '/api/shop/redeem', tok['S9Z'], {'couponId': z_coupon['id']})
        check('兑穿后再兑 → 业务码 40902', 40902, body['code'])
        ov_z = unwrap(*api('GET', '/api/me/overview', tok['S9Z']), 'S9Z 个人中心')
        shop_z = {it['name']: it for it in ov_z['shop']['items']}
        check_row('S9Z 的商城按钮口径（真配置售罄、且自己已到限购）',
                  {'canRedeem': False, 'reject': 'out_of_stock', 'owned': 3, 'stock': 0},
                  shop_z[COUPON_LATE[0]])

    # ---- 券包/账本 1:1：每张券都有一笔对应的负流水 ----
    spells = int(scalar(db, 'SELECT COUNT(*) AS v FROM xp_ledger WHERE user_id = %s AND reason = %s',
                        (uid_a, 'shop_redeem')))
    check('S9A 券数与兑换负流水条数一致', len(a_rows), spells)
    spent = int(scalar(db, 'SELECT COALESCE(SUM(-delta), 0) AS v FROM xp_ledger '
                           'WHERE user_id = %s AND reason = %s', (uid_a, 'shop_redeem')))
    check('S9A 累计支出 = 880 + 300（手算表）', COUPON_ABSENT[1] + COUPON_LATE[1], spent)
    check('S9A 余额 = 收入 − 支出（账本自洽）',
          int(scalar(db, 'SELECT COALESCE(SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END),0) AS v '
                         'FROM xp_ledger WHERE user_id = %s', (uid_a,))) - spent,
          sql_balance(db, uid_a))

    dump('redeem-s9a.json', {'overview': ov, 'redeem_absent': rb, 'redeem_late': rb2,
                             'settlement': settle})
    db.close()
    finish('验收①')


# ---------------------------------------------------------------- 步骤：review（验收②）

def cmd_review():
    db = db_conn()
    head('验收② 复盘卡只从错题组卷（读 wrong_book 动态组卷 → 答对出本子 → 清空后为空）')
    level_id = int(scalar(db, 'SELECT id FROM levels WHERE name = %s', (LEVEL_NAME,)))
    tok = student_token('S9B')
    uid_b = sql_uid(db, 'S9B')
    qids = [int(r['id']) for r in q(db, 'SELECT id FROM questions WHERE level_id = %s ORDER BY id',
                                    (level_id,))]
    q1, q2 = qids[0], qids[1]

    # 前两关：q1/q2 错（第 3 次打关再把两道都打错，q2 从"已掌握"回到"未掌握"）
    # ——顺带把「错得多、错得近的在前」这条排序也摆出来：q1 错 3 次、q2 错 2 次。
    settle1, paper1, _ = play_level(tok, level_id, wrong_ids=(q1, q2))
    note('第 1 次打关：q1/q2 故意答错（结算 XP {}）'.format(settle1['xpTotal']))
    settle2, paper2, _ = play_level(tok, level_id, wrong_ids=(q1,))
    note('第 2 次打关：只错 q1、q2 答对（结算 XP {}）'.format(settle2['xpTotal']))
    settle3, paper3, _ = play_level(tok, level_id, wrong_ids=(q1, q2))
    note('第 3 次打关：q1/q2 又都答错（结算 XP {}）'.format(settle3['xpTotal']))

    book = q(db, 'SELECT question_id, wrong_count, mastered FROM wrong_book WHERE user_id = %s '
                 'ORDER BY question_id', (uid_b,))
    check('错题本只收了错过的 2 题', [q1, q2], [int(r['question_id']) for r in book])
    check_row('q1 错 3 次未掌握', {'wrong_count': 3, 'mastered': 0},
              {'wrong_count': int(book[0]['wrong_count']), 'mastered': int(book[0]['mastered'])})
    check_row('q2 错 2 次未掌握（第 2 次答对被收回本子，第 3 次又错变回未掌握）',
              {'wrong_count': 2, 'mastered': 0},
              {'wrong_count': int(book[1]['wrong_count']), 'mastered': int(book[1]['mastered'])})

    code, body = api('GET', '/api/me/review-paper', tok)
    paper = unwrap(code, body, 'S9B 复盘卷')
    check('复盘卷题数 = 未掌握错题数', len(book), paper['count'])
    check('复盘卷只收未掌握的错题（题号集合逐条一致）', [q1, q2],
          [int(it['question']['id']) for it in paper['items']])
    check('排序：错得多的在前（q1 错 3 次 → 第 1 题）', q1, int(paper['items'][0]['question']['id']))
    check('排序：错得少的在后（q2 错 2 次 → 第 2 题）', q2, int(paper['items'][1]['question']['id']))
    check('题目自带错了几次', [3, 2], [it['wrongCount'] for it in paper['items']])
    check('题目带得出自哪一关', [LEVEL_NAME, LEVEL_NAME],
          [it['levelName'] for it in paper['items']])
    check('复盘卷上限口径（≤{} 题）'.format(REVIEW_PAPER_MAX), True, paper['count'] <= REVIEW_PAPER_MAX)

    ov = unwrap(*api('GET', '/api/me/overview', tok), 'S9B 个人中心')
    check_row('复盘卡摘要（2 题待收、0 题已收、共 2 题）',
              {'pending': 2, 'mastered': 0, 'total': 2}, ov['review'])
    check('复盘卡指向错得最多的那一关', LEVEL_NAME, ov['review']['levelName'])

    # 不属于复盘卡的题（本关第 3 题，从没错过）→ 拒绝，防刷分
    code, body = api('POST', '/api/me/review-submit', tok, {'questionId': qids[2], 'pickedIdx': '0'})
    check('提交不在复盘卡里的题 → HTTP 409', 409, code)
    check('提交不在复盘卡里的题 → 业务码 40901', 40901, body['code'])
    check('被拒的复盘不落账本', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM xp_ledger WHERE user_id = %s AND ref_type = %s',
                     (uid_b, 'review'))))

    # 答对 q2（按复盘卷下发的正确项答）→ 出本子 + 只给基础分
    balance_before = sql_balance(db, uid_b)
    pick = correct_pick_of(paper['items'][1]['question'])
    code, body = api('POST', '/api/me/review-submit', tok, {'questionId': q2, 'pickedIdx': pick})
    sub = unwrap(code, body, 'S9B 复盘 q2')
    check('复盘答对 → isCorrect true', True, sub['isCorrect'])
    check('复盘答对 → 出本子（mastered true）', True, sub['mastered'])
    check('复盘卷剩 1 题', 1, sub['remaining'])
    check_row('复盘只给基础分（无速度/连击加成）', {'base': REVIEW_BASE_XP, 'speed': 0, 'combo': 0}, sub['xp'])
    check('复盘加分后余额 = 加前 + 基础分', balance_before + REVIEW_BASE_XP, sub['balance'])
    led = one(db, 'SELECT delta, reason, ref_type, ref_id FROM xp_ledger WHERE user_id = %s '
                  'ORDER BY id DESC LIMIT 1', (uid_b,))
    check_row('复盘流水（ref 指向题目，reason 沿用答题基础分）',
              {'delta': REVIEW_BASE_XP, 'reason': 'answer_base', 'ref_type': 'review', 'ref_id': q2}, led)

    code, body = api('GET', '/api/me/review-paper', tok)
    paper2 = unwrap(code, body, 'S9B 复盘卷（1 题）')
    check('出本子后复盘卷只剩 q1', [q1], [int(it['question']['id']) for it in paper2['items']])

    code, body = api('POST', '/api/me/review-submit', tok, {'questionId': q2, 'pickedIdx': pick})
    check('已掌握的题再复盘 → 409（防刷分）', 409, code)

    # 复盘又答错：错次 +1、本子里的题不会因为复盘而消失
    wrong_pick = wrong_pick_of(paper2['items'][0]['question'])
    code, body = api('POST', '/api/me/review-submit', tok, {'questionId': q1, 'pickedIdx': wrong_pick})
    sub_w = unwrap(code, body, 'S9B 复盘 q1 答错')
    check('复盘答错 → 没有分', 0, sub_w['xp']['base'])
    check('复盘答错 → 仍在卷里（remaining 1）', 1, sub_w['remaining'])
    book_q1 = one(db, 'SELECT wrong_count, mastered FROM wrong_book WHERE user_id = %s AND question_id = %s',
                  (uid_b, q1))
    check_row('复盘答错 → 错次 +1、仍未掌握', {'wrong_count': 4, 'mastered': 0},
              {'wrong_count': int(book_q1['wrong_count']), 'mastered': int(book_q1['mastered'])})

    # 清空错题：把最后一题也答对 → 复盘卡必须为空
    code, body = api('GET', '/api/me/review-paper', tok)
    paper3 = unwrap(code, body, 'S9B 复盘卷（再取一次）')
    pick1 = correct_pick_of(paper3['items'][0]['question'])
    code, body = api('POST', '/api/me/review-submit', tok, {'questionId': q1, 'pickedIdx': pick1})
    sub3 = unwrap(code, body, 'S9B 复盘 q1 答对')
    check('清空后剩余 0 题', 0, sub3['remaining'])
    code, body = api('GET', '/api/me/review-paper', tok)
    empty = unwrap(code, body, 'S9B 复盘卷（清空后）')
    check('清空错题后复盘卷为空（count 0）', 0, empty['count'])
    check('清空错题后复盘卷为空（items 空）', 0, len(empty['items']))
    check('空卷带一句人话（前端直接展示）', True, bool(empty['note']))
    ov2 = unwrap(*api('GET', '/api/me/overview', tok), 'S9B 个人中心（清空后）')
    check_row('复盘卡摘要（0 待收 / 2 已收 / 共 2）',
              {'pending': 0, 'mastered': 2, 'total': 2}, ov2['review'])
    check('复盘卷只从错题组卷：SQL 未掌握数 = 复盘卷题数', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM wrong_book WHERE user_id = %s AND mastered = 0',
                     (uid_b,))))

    dump('review-s9b.json', {'paper': paper, 'paper_after_empty': empty, 'overview': ov2,
                             'settlements': [settle1['xpTotal'], settle2['xpTotal'], settle3['xpTotal']]})
    db.close()
    finish('验收②')


def correct_pick_of(question):
    """按题干文本把正确项对回卷面下标（建题时正确项在 0 号位）。"""
    db = db_conn()
    row = one(db, 'SELECT options_json, answer_idx FROM questions WHERE id = %s', (int(question['id']),))
    db.close()
    want = json.loads(row['options_json'])[int(row['answer_idx'])]
    return str(question['options'].index(want))


def wrong_pick_of(question):
    db = db_conn()
    row = one(db, 'SELECT options_json, answer_idx FROM questions WHERE id = %s', (int(question['id']),))
    db.close()
    want = json.loads(row['options_json'])[int(row['answer_idx'])]
    return str((question['options'].index(want) + 1) % len(question['options']))


# ---------------------------------------------------------------- 步骤：ledger（验收④）

def ledger_of(tok, limit=500, offset=0, who=''):
    code, body = api('GET', '/api/me/ledger?limit={}&offset={}'.format(limit, offset), tok)
    return unwrap(code, body, '{} 积分明细'.format(who or '我'))


def cmd_ledger():
    db = db_conn()
    head('验收④ 明细页与 SELECT * FROM xp_ledger WHERE user_id=? 逐条一致')
    tok = student_token('S9A')
    uid_a = sql_uid(db, 'S9A')
    data = ledger_of(tok, 500, 0, 'S9A')
    rows = sql_ledger_rows(db, uid_a)
    check('明细条数 = SQL 条数', len(rows), len(data['items']))
    check('明细 total = SQL COUNT(*)', len(rows), data['total'])
    check('明细条数 = 本页条数（limit 500 装得下）', data['total'], len(data['items']))
    check('余额 = SUM(delta)', sql_balance(db, uid_a), data['balance'])
    check('累计入账 = SUM(delta>0)', int(scalar(db, 'SELECT COALESCE(SUM(CASE WHEN delta > 0 THEN delta '
                                                   'ELSE 0 END),0) AS v FROM xp_ledger WHERE user_id = %s',
                                               (uid_a,))), data['earned'])
    check('累计支出 = SUM(-delta<0)', int(scalar(db, 'SELECT COALESCE(SUM(CASE WHEN delta < 0 THEN -delta '
                                                   'ELSE 0 END),0) AS v FROM xp_ledger WHERE user_id = %s',
                                               (uid_a,))), data['spent'])

    mismatched = []
    empty_detail = []
    bad_label = []
    for i, item in enumerate(data['items']):
        want = rows[i]
        got = {'id': item['id'], 'delta': item['delta'], 'reason': item['reason'],
               'ref_type': item['refType'], 'ref_id': item['refId'], 'created_at': item['createdAt']}
        exp = {'id': int(want['id']), 'delta': int(want['delta']), 'reason': want['reason'],
               'ref_type': want['ref_type'], 'ref_id': int(want['ref_id']),
               'created_at': want['created_at']}
        if got != exp:
            mismatched.append((i, exp, got))
        if not item['detail']:
            empty_detail.append(item['id'])
        if REASON_LABELS.get(item['reason']) != item['label']:
            bad_label.append((item['reason'], item['label']))
    check('逐条一致（id/delta/reason/ref_type/ref_id/时间，按 id DESC 一条不漏）', 0, len(mismatched))
    for i, exp, got in mismatched[:5]:
        note('第 {} 行不一致：SQL {} vs 回执 {}'.format(i, exp, got))
    check('每行都有「来源人话」（每一分来源可查）', 0, len(empty_detail))
    check('每行的 reason 都翻译成人话（码表两边一致）', 0, len(bad_label))
    for reason, label in bad_label[:5]:
        note('码 {} 期望文案 {}，回执 {}'.format(reason, REASON_LABELS.get(reason), label))

    details = {it['refType'] + ':' + str(it['refId']): it['detail'] for it in data['items']}
    late = sql_coupon(db, sql_cid(db, CLASS9), COUPON_LATE[0])
    absent = sql_coupon(db, sql_cid(db, CLASS9), COUPON_ABSENT[0])
    check('兑换来源显示券名（免迟到券）', '商城兑换 · ' + COUPON_LATE[0],
          details.get('coupon:{}'.format(late['id'])))
    check('兑换来源显示券名（免旷课券）', '商城兑换 · ' + COUPON_ABSENT[0],
          details.get('coupon:{}'.format(absent['id'])))
    check('闯关来源显示关卡名', True,
          any(v == LEVEL_NAME for k, v in details.items() if k.startswith('attempt:')))

    # 分页：offset 翻页不许改变汇总，第一页第一行必须是最新一行
    page1 = ledger_of(tok, 3, 0, 'S9A')
    page2 = ledger_of(tok, 3, 3, 'S9A')
    check('分页 limit 生效', 3, len(page1['items']))
    check('第二页条数', 3, len(page2['items']))
    check('第一页第一行 = SQL 第一行', int(rows[0]['id']), page1['items'][0]['id'])
    check('第二页第一行 = SQL 第 4 行', int(rows[3]['id']), page2['items'][0]['id'])
    check('翻页不改变余额', data['balance'], page2['balance'])
    check('offset 回执如实', 3, page2['offset'])
    check('两页无重复行', 0, len({it['id'] for it in page1['items']} & {it['id'] for it in page2['items']}))

    # 负数行与扣分一一对应（验收①的账本侧复核）
    neg = [it for it in data['items'] if it['delta'] < 0]
    check('负数行都是消费（shop_redeem / pet_feed）', True,
          all(it['reason'] in ('shop_redeem', 'pet_feed') for it in neg))
    check('消费行数 = 券 + 奶酪（S9A 此刻只兑了 2 张券）', 2, len(neg))

    dump('ledger-s9a.json', {'response': data, 'sql_rows': [
        {'id': int(r['id']), 'delta': int(r['delta']), 'reason': r['reason'], 'ref_type': r['ref_type'],
         'ref_id': int(r['ref_id']), 'created_at': r['created_at']} for r in rows]})
    db.close()
    finish('验收④')


# ---------------------------------------------------------------- 步骤：chestpet（验收⑤）

def cmd_chestpet():
    db = db_conn()
    head('验收⑤ 宝箱发奖（2022 年真题卷）+ 消费不回锁 + 宠物喂养/阶段')
    cid9 = sql_cid(db, CLASS9)
    ws = ymd(dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)))
    tok = {u: student_token(u) for u, _ in ROSTER9}
    uid_c, uid_e = sql_uid(db, 'S9C'), sql_uid(db, 'S9E')
    members = [uid_c, uid_e]
    team_xp = sql_week_learn_xp(db, members, ws)
    check('宝箱队本周学习所得 = 门槛（正好压线）', CHEST_THRESHOLD, team_xp)

    # ---- 解锁即发奖：第一次打开个人中心就发（懒发奖） ----
    ov = unwrap(*api('GET', '/api/me/overview', tok['S9C']), 'S9C 个人中心')
    chest = ov['chest']
    # 宝箱经验是 S8 的老公式：计入进度的小队经验 = 学习净得 + 组队加成（多人队 10%）。
    # overview 的 chest 只吐合计 xp（rawXp/bonusXp 在小队页的 DTO 上），所以这里用
    # 独立 SQL 算出的学习净得 + 手推 10% 加成反推它；口径若被改成钱包余额，这里立刻对不上。
    BONUS = int(team_xp * 0.1 + 0.5)
    check_row('宝箱状态（解锁/压线/进度 100；xp = SQL 学习净得 + 10% 组队加成）',
              {'threshold': CHEST_THRESHOLD, 'xp': team_xp + BONUS, 'remain': 0, 'progress': 100,
               'unlocked': True, 'solo': False, 'granted': True, 'justGranted': True}, chest)
    check('奖励名 = S7 拍板口径「2022 年真题卷」', '2022 年真题卷', chest['rewardName'])
    rewards = [it for it in ov['wallet']['items'] if it['name'] == '2022 年真题卷']
    check('券包里出现奖励券', 1, len(rewards))
    reward = rewards[0]
    check_row('奖励券口径（0 分 / 待确认 / 宝箱来源 / 刚发）',
              {'costXp': 0, 'status': 'pending', 'statusText': '待老师确认',
               'source': '小队宝箱解锁奖励', 'justGranted': True},
              {k: reward[k] for k in ('costXp', 'status', 'statusText', 'source', 'justGranted')})
    check('奖励券券码合规', True, bool(CODE_RE.match(reward['code'])))
    reward_coupon = one(db, 'SELECT id, cost_xp, per_user_limit, stock, enabled FROM coupons '
                           'WHERE class_id = %s AND name = %s', (cid9, '2022 年真题卷'))
    check_row('奖励券种（系统券：0 分 / 限 1 张 / 库存 = 人数 / 下架态=不是商品）',
              {'cost_xp': 0, 'per_user_limit': 1, 'stock': 5, 'enabled': 0}, reward_coupon)

    # ---- 幂等：第二次打开不再发 ----
    ov2 = unwrap(*api('GET', '/api/me/overview', tok['S9C']), 'S9C 个人中心（第二次）')
    check('第二次打开不再标「刚发」', False, ov2['chest']['justGranted'])
    check('第二次打开宝箱仍是已发状态', True, ov2['chest']['granted'])
    check('奖励券只有 1 张（幂等，不重复发）', 1,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM coupon_redeems WHERE coupon_id = %s AND user_id = %s',
                     (reward_coupon['id'], uid_c))))

    # ---- 奖励券不是商品：不进商城、也不能被兑（下架态 → 409/40901） ----
    names = [it['name'] for it in ov2['shop']['items']]
    check('商城不出现系统奖励券', 0, names.count('2022 年真题卷'))
    check('商城仍只有 2 张可兑券种', 2, len(names))
    code, body = api('POST', '/api/shop/redeem', tok['S9D'], {'couponId': reward_coupon['id']})
    check('兑系统奖励券 → HTTP 409', 409, code)
    check('兑系统奖励券 → 业务码 40901（下架 = 不是商品）', 40901, body['code'])
    check('被拒的兑换不落券（S9D 仍无券）', 0, len(sql_redeem_rows(db, sql_uid(db, 'S9D'))))

    # ---- 消费不回锁：把余额喂到门槛以下，宝箱必须仍然解锁 ----
    bal_before = sql_balance(db, uid_c)
    code, body = api('POST', '/api/pet/feed', tok['S9C'])
    fed1 = unwrap(code, body, 'S9C 喂第 1 块')
    check_row('喂第 1 块奶酪（30 分 / 幼崽 / 阶段内 30/300）',
              {'fedXp': 30, 'feeds': 1, 'feedCost': PET_FEED_COST, 'stageName': '幼崽', 'stageIndex': 0,
               'inStage': 30, 'stageSpan': 300, 'progress': 10, 'isMax': False, 'stageChanged': False,
               'balance': bal_before - PET_FEED_COST}, fed1)
    check_row('喂养负流水（ref 指向第几块奶酪）',
              {'delta': -PET_FEED_COST, 'reason': 'pet_feed', 'ref_type': 'pet', 'ref_id': 1},
              one(db, 'SELECT delta, reason, ref_type, ref_id FROM xp_ledger WHERE user_id = %s '
                      'ORDER BY id DESC LIMIT 1', (uid_c,)))
    bal_after = sql_balance(db, uid_c)
    learn_xp = sql_week_learn_xp(db, members, ws)
    check('队友余额已低于宝箱门槛（若按余额口径，此刻应回锁）', True, bal_after < CHEST_THRESHOLD)
    check('小队学习所得不受消费影响', CHEST_THRESHOLD, learn_xp)
    ov3 = unwrap(*api('GET', '/api/me/overview', tok['S9C']), 'S9C 个人中心（消费后）')
    check_row('消费后宝箱仍解锁（口径是学习所得，不是钱包余额）',
              {'unlocked': True, 'xp': learn_xp + BONUS, 'remain': 0, 'granted': True,
               'justGranted': False}, ov3['chest'])
    check('消费后个人余额确实少了（消费真的扣了分）', True, ov3['user']['xp'] < bal_before)

    # ---- 宠物阶段进阶：喂到 300 累计 → 「活泼」（阶段换分的里程碑） ----
    last = fed1
    for i in range(2, 11):
        code, body = api('POST', '/api/pet/feed', tok['S9C'])
        last = unwrap(code, body, 'S9C 喂第 {} 块'.format(i))
    check_row('喂满 10 块（累计 300 / 进阶「活泼」/ 新阶段内 0/600）',
              {'fedXp': 300, 'feeds': 10, 'stageName': '活泼', 'stageIndex': 1, 'inStage': 0,
               'stageSpan': 600, 'progress': 0, 'stageChanged': True, 'isMax': False,
               'balance': bal_before - 300}, last)
    pet_rows = q(db, 'SELECT ref_id, delta FROM xp_ledger WHERE user_id = %s AND reason = %s '
                     'ORDER BY ref_id', (uid_c, 'pet_feed'))
    check('喂养流水 10 条，ref_id 从 1 到 10（第几块奶酪可查）',
          list(range(1, 11)), [int(r['ref_id']) for r in pet_rows])
    check('喂养流水合计 = 300 分', -300, int(sum(int(r['delta']) for r in pet_rows)))
    ov4 = unwrap(*api('GET', '/api/me/overview', tok['S9C']), 'S9C 个人中心（喂满后）')
    check_row('个人中心的宠物态与喂养回执一致',
              {'fedXp': 300, 'feeds': 10, 'stageName': '活泼', 'stageIndex': 1, 'feedCost': PET_FEED_COST},
              {k: ov4['pet'][k] for k in ('fedXp', 'feeds', 'stageName', 'stageIndex', 'feedCost')})
    bag = {it['key']: it for it in ov4['bag']}
    check('背包奶酪数 = 喂了几块', 10, bag['cheese']['count'])
    check('背包券数 = 券包张数（奖励券 1 张）', ov4['wallet']['total'], bag['coupon']['count'])
    check('宠物区说明含「额度规则」提示（一期不承诺折算）', True, '额度规则' in ov4['pet']['note'])

    # ---- 积分不够喂：S9E 余额 0 → 40011 ----
    code, body = api('POST', '/api/pet/feed', tok['S9E'])
    check('积分不足喂养 → HTTP 400', 400, code)
    check('积分不足喂养 → 业务码 40011', 40011, body['code'])
    check('被拒的喂养不落账本', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM xp_ledger WHERE user_id = %s AND reason = %s',
                     (uid_e, 'pet_feed'))))

    # ---- 派生口径：徽章 / 连续周数 / 等级 ----
    check('徽章含连课（本周有学习流水 → 连课 1 周）', '连课 1 周',
          next((b['text'] for b in ov4['badges'] if b['key'] == 'streak'), ''))
    check('徽章含等级（LV. = 1 + 余额 // 300）', 'LV.{}'.format(1 + ov4['user']['xp'] // 300),
          next((b['text'] for b in ov4['badges'] if b['key'] == 'level'), ''))
    check('用户卡等级与余额自洽', 1 + ov4['user']['xp'] // ov4['user']['xpPerLevel'], ov4['user']['lv'])
    check('用户卡级内进度 = 余额 % 300', ov4['user']['xp'] % ov4['user']['xpPerLevel'],
          ov4['user']['xpInLevel'])
    stats = {s['key']: s for s in ov4['stats']}
    check('三格「我的积分」= 账本聚合', sql_balance(db, uid_c), stats['xp']['value'])
    check('目标文案（四级）', '英语四级冲关中', ov4['user']['targetText'])

    dump('chest-pet.json', {'overview_first': ov, 'pet_after_10': last, 'overview_after': ov4,
                            'reward_coupon': reward_coupon})
    db.close()
    finish('验收⑤')


# ---------------------------------------------------------------- 步骤：demo（给截图摆位）

def cmd_demo():
    db = db_conn()
    head('给浏览器截图摆位（S9B 重新攒 2 道错题；S9A 喂一次宠物、券包保持 2 张）')
    level_id = int(scalar(db, 'SELECT id FROM levels WHERE name = %s', (LEVEL_NAME,)))
    qids = [int(r['id']) for r in q(db, 'SELECT id FROM questions WHERE level_id = %s ORDER BY id',
                                    (level_id,))]
    tok_b = student_token('S9B')
    settle, _, _ = play_level(tok_b, level_id, wrong_ids=(qids[0], qids[1]))
    check('S9B 重新攒到 2 道未掌握错题', 2,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM wrong_book WHERE user_id = %s AND mastered = 0',
                     (sql_uid(db, 'S9B'),))))
    code, body = api('GET', '/api/me/review-paper', tok_b)
    paper = unwrap(code, body, 'S9B 复盘卷（截图前）')
    check('复盘卷有 2 题（截图里不是空态）', 2, paper['count'])

    tok_a = student_token('S9A')
    code, body = api('POST', '/api/pet/feed', tok_a)
    fed = unwrap(code, body, 'S9A 喂第 1 块（截图用）')
    check('S9A 宠物有 1 块奶酪（截图里有进度可看）', 1, fed['feeds'])
    ov_a = unwrap(*api('GET', '/api/me/overview', tok_a), 'S9A 个人中心（截图前）')
    check('S9A 券包 2 张（商城/券包截图非空态）', 2, ov_a['wallet']['total'])
    check('S9A 积分明细非空', True, ov_a['user']['xp'] > 0)

    # 令牌交给浏览器子代理用（学生端把 token 放在 localStorage，登录页也能过一遍真链路）
    dump('demo-tokens.json', {'S9A': tok_a, 'S9B': tok_b, 'password': STU_PWD,
                              'settlement': settle['xpTotal']})
    db.close()
    finish('截图摆位')


# ---------------------------------------------------------------- 步骤：verify（收尾复核）

def cmd_verify():
    db = db_conn()
    head('收尾复核：明细再逐条对一次（覆盖后续步骤写的行）+ 宝箱仍解锁 + 底账 after')
    tok_a = student_token('S9A')
    uid_a = sql_uid(db, 'S9A')
    data = ledger_of(tok_a, 500, 0, 'S9A')
    rows = sql_ledger_rows(db, uid_a)
    same = all(
        data['items'][i]['id'] == int(rows[i]['id'])
        and data['items'][i]['delta'] == int(rows[i]['delta'])
        and data['items'][i]['reason'] == rows[i]['reason']
        and data['items'][i]['refType'] == rows[i]['ref_type']
        and data['items'][i]['refId'] == int(rows[i]['ref_id'])
        and data['items'][i]['createdAt'] == rows[i]['created_at']
        for i in range(len(rows))
    )
    check('明细仍与 SQL 逐条一致（含后续步骤新写的行）', True, same)
    check('明细条数 = SQL 条数', len(rows), len(data['items']))
    check('余额 = SUM(delta)', sql_balance(db, uid_a), data['balance'])

    ws = ymd(dt.datetime.combine(week_start_of(dt.date.today()), dt.time(0, 0)))
    members = [sql_uid(db, 'S9C'), sql_uid(db, 'S9E')]
    ov = unwrap(*api('GET', '/api/me/overview', student_token('S9C')), 'S9C 个人中心（收尾）')
    check('宝箱仍解锁（喂了 10 块也没回锁）', True, ov['chest']['unlocked'])
    check('小队学习所得不变', CHEST_THRESHOLD, sql_week_learn_xp(db, members, ws))
    check('奖励券库内仍只 1 张', 1,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM coupon_redeems WHERE user_id = %s AND coupon_id IN '
                         '(SELECT id FROM coupons WHERE name = %s)', (sql_uid(db, 'S9C'), '2022 年真题卷'))))
    check('券码全库仍唯一', 0, int(scalar(db, 'SELECT COUNT(*) AS v FROM (SELECT code FROM coupon_redeems '
                                               'GROUP BY code HAVING COUNT(*) > 1) t')))
    check('没有任何券把库存扣成负数', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM coupons WHERE stock < 0')))
    check('没有任何班级的学生余额为负', 0,
          int(scalar(db, 'SELECT COUNT(*) AS v FROM (SELECT user_id, SUM(delta) AS s FROM xp_ledger '
                         'GROUP BY user_id HAVING s < 0) t')))
    db.close()
    cmd_baseline('after')


# ---------------------------------------------------------------- 入口

CMDS = {
    'seed': cmd_seed, 'redeem': cmd_redeem, 'review': cmd_review, 'ledger': cmd_ledger,
    'chestpet': cmd_chestpet, 'demo': cmd_demo, 'verify': cmd_verify,
}


def main():
    if len(sys.argv) < 2 or (sys.argv[1] not in CMDS and sys.argv[1] not in ('baseline', 'cleanup')):
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
    print('[S9] 合计断言 {} 条，失败 {} 条'.format(len(CHECKS), len(FAILS)))
    for f in FAILS:
        print('[S9] 失败：{}'.format(f))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())