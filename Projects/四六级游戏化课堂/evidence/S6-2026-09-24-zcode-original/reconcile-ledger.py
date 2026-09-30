#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 验收④：结算 XP 明细 ↔ xp_ledger 逐条对账（真实 MySQL :3307）。

对账口径（PRD FR-BAS-07「每一分可追溯」）：
  前端结算明细渲染的就是服务端下发的 settlement.xpRows（e2e 已断言逐字一致），
  这里再拿同一份 xpRows（reason+delta）去比 xp_ledger 里 ref_type='attempt' AND ref_id=<attemptId> 的流水：
    ① 每个 reason 的**条数**与**金额**都要和结算明细对得上（基础/速度两条必须各一条且金额相等）；
    ② 失败（爱心扣完）的 attempt 结算净得 0 → 账本净额也必须是 0；
    ③ XP 唯一权威 = SELECT SUM(delta)：结算下发的累计值 == 库里的累计值；
    ④ 验收②补充证据：同一个关卡 id，四级目标与六级目标拿到的题目集合不相交。

用法（由 run-acceptance.sh 调用）：python reconcile-ledger.py e2e-chain.json e2e-wrong.json ...
"""
import io
import json
import os
import sys

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'

FAILS = []
CHECKS = []


def check(desc, want, got):
    ok = str(want) == str(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[LEDGER] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


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


def ledger_by_reason(cur, attempt_id):
    cur.execute("SELECT reason, COUNT(*), SUM(delta) FROM xp_ledger "
                "WHERE ref_type='attempt' AND ref_id=%s GROUP BY reason", (attempt_id,))
    return {r[0]: {'n': int(r[1]), 'sum': int(r[2])} for r in cur.fetchall()}


def ledger_rows(cur, attempt_id):
    """逐条流水（不合并）：验数值表红线用的（单题基础分 20、Boss 每题 25、速度 ≤10）。"""
    cur.execute('SELECT reason, delta FROM xp_ledger WHERE ref_type=%s AND ref_id=%s ORDER BY id',
                ('attempt', attempt_id))
    return [(r[0], int(r[1])) for r in cur.fetchall()]


def ledger_total(cur, user_id):
    cur.execute('SELECT COALESCE(SUM(delta),0) FROM xp_ledger WHERE user_id=%s', (user_id,))
    return int(cur.fetchone()[0])


def user_id_of(cur, username):
    cur.execute('SELECT id FROM users WHERE username=%s', (username,))
    row = cur.fetchone()
    return int(row[0]) if row else 0


def target_of(cur, uid):
    cur.execute('SELECT target FROM users WHERE id=%s', (uid,))
    row = cur.fetchone()
    return int(row[0]) if row else -1


def main():
    files = sys.argv[1:]
    if not files:
        print('需要 e2e-*.json 作为参数')
        return 2
    conn = db_conn()
    attempts = 0
    last_all = {}  # username -> (settlement.xpTotalAll, attemptId)
    cross = {}     # levelId -> {'4': set(qids), '6': set(qids)}
    try:
        with conn.cursor() as cur:
            for fn in files:
                path = fn if os.path.isabs(fn) else os.path.join(HERE, fn)
                if not os.path.exists(path):
                    continue
                data = json.load(io.open(path, encoding='utf-8'))
                user = data.get('user') or data.get('username') or ''
                uid = user_id_of(cur, user)
                check('账本对账：用户 {} 在 users 表里（{}）'.format(user, fn), True, uid > 0)
                for rec in data.get('levels', []):
                    st = rec.get('settlement')
                    aid = rec.get('attemptId')
                    if not st or not aid:
                        continue
                    attempts += 1
                    tag = '{} L{} attempt {}'.format(user, rec.get('levelId'), aid)
                    lib = ledger_by_reason(cur, aid)
                    rows = ledger_rows(cur, aid)
                    # 账本是**逐题流水**（答对一题一行基础分），结算是**按 reason 合并**后的明细，
                    # 所以对账比的是「同一 reason 的金额」（件数另按题数验，见下）。
                    want = {}
                    for r in st['xpRows']:
                        w = want.setdefault(r['reason'], {'n': 0, 'sum': 0})
                        w['n'] += 1
                        w['sum'] += int(r['delta'])
                    check('{} 账本 reason 集合 == 结算明细'.format(tag),
                          sorted(want.keys()), sorted(lib.keys()))
                    for reason in sorted(set(want) | set(lib)):
                        check('{} 账本 {} 金额 == 结算明细'.format(tag, reason),
                              want.get(reason, {'sum': 0})['sum'], lib.get(reason, {'sum': 0})['sum'])
                    # 验收④点名的那两条：结算的「基础分/速度加成」两行 == 账本里同名 reason 的合计
                    if rec.get('overlay') in ('clear', 'boss'):
                        for reason, name in (('answer_base', '基础分'), ('answer_speed', '速度加成')):
                            want_d = sum(int(r['delta']) for r in st['xpRows'] if r['reason'] == reason)
                            check('{} 验收④ 结算「{}」行 == 账本 {} 合计'.format(tag, name, reason),
                                  want_d, lib.get(reason, {}).get('sum', 0))
                    # 数值表红线：基础分逐题 20（题数 == 答对题数）；速度加成逐题 0..10
                    if rec.get('overlay') == 'clear':
                        base = [d for r, d in rows if r == 'answer_base']
                        speed = [d for r, d in rows if r == 'answer_speed']
                        check('{} 账本基础分逐题 20（{} 条 == 答对 {} 题）'.format(
                            tag, len(base), st['correct']), [20] * st['correct'], base)
                        check('{} 账本速度加成逐题 0..10'.format(tag), True,
                              all(0 <= d <= 10 for d in speed) and len(speed) <= st['correct'])
                    if rec.get('overlay') == 'boss':
                        boss = [d for r, d in rows if r == 'boss_correct']
                        check('{} 账本 Boss 每题答对 25（{} 条 == 答对 {} 题）'.format(
                            tag, len(boss), st['correct']), [25] * st['correct'], boss)
                    # 结算净得 == 账本净额（失败层的撤销行也一起算进来）
                    check('{} 结算净得 == 账本净额'.format(tag), int(st['xpTotal']),
                          sum(v['sum'] for v in lib.values()))
                    if rec.get('overlay') == 'fail':
                        credited = sum(d for r, d in rows if r != 'attempt_voided')
                        voided = sum(d for r, d in rows if r == 'attempt_voided')
                        check('{} 失败层账本净额归零（撤销行冲回已入账得分）'.format(tag), 0,
                              credited + voided)
                        if credited:
                            check('{} 失败层已入账被显式冲回（{} → {}）'.format(tag, credited, voided),
                                  -credited, voided)
                        check('{} 失败层不写通关/三星奖励行'.format(tag), [],
                              [r for r, _ in rows if r in ('level_clear', 'star3_bonus')])
                    last_all[user] = (int(st['xpTotalAll']), aid)
                    lvl = str(rec.get('levelId'))
                    band = (rec.get('bands') or ['?'])[0]
                    cross.setdefault(lvl, {})[band] = set(rec.get('questionIds') or [])

                # 目标切换场景：UI 顶栏显示六级 → users.target 也必须是 6
                t6 = data.get('target6Paper')
                if t6:
                    check('{} 切换后 users.target 落库为 6'.format(user), 6,
                          None if not uid else target_of(cur, uid))
                    band = (t6.get('bands') or ['?'])[0]
                    cross.setdefault(str(t6.get('levelId')), {})[band] = set(t6.get('questionIds') or [])

            # ③ XP 唯一权威 = SELECT SUM(delta)
            for user, (all_xp, aid) in sorted(last_all.items()):
                uid = user_id_of(cur, user)
                check('{} 结算累计 XP == SELECT SUM(delta)（attempt {} 结算口径）'.format(user, aid),
                      all_xp, ledger_total(cur, uid))

            # ④ 同一个关卡 id，四级/六级拿到的题目集合不相交
            for lvl, byband in sorted(cross.items()):
                if '4' in byband and '6' in byband:
                    a, b = byband['4'], byband['6']
                    check('L{} 四级卷与六级卷题目集合不相交'.format(lvl), 0, len(a & b))
    finally:
        conn.close()

    print('')
    print('【账本对账汇总】共对账 {} 次结算 · {} 条断言 · 失败 {} 条'.format(
        attempts, len(CHECKS), len(FAILS)))
    if FAILS:
        for d in FAILS:
            print('  ❌ ' + d)
    out = os.path.join(HERE, 'ledger-reconcile.json')
    with io.open(out, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'attempts': attempts, 'checks': CHECKS, 'fails': FAILS},
                            ensure_ascii=False, indent=1))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())