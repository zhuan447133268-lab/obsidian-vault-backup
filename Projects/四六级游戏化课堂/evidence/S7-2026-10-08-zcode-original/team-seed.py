#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S7 验收数据准备：演示学生的**本周成绩**按计划打出来（真库 :3307 + 真服务 :8080）。

口径与 S6.5 一致：所有作答都走真实链路（GET /api/quiz/paper → 服务端洗序 → POST /api/quiz/submit），
脚本只决定「答什么」，绝不直接往 attempt_answers / xp_ledger 里插行。
产物 plan-*.json 是「手算」那一侧：每关计划对错 + 服务端结算回执（correct/total/xpTotal），
team-reconcile.py 拿它跟 SQL 独立聚合、/api/team/overview 回执三方对拍。

计划（把三条阈值口径一次演示到位）：
  S7A 队长：L25 答 4/5、L26 答 3/5 → 本周合计 7/10 = 正确率**正好 70%**、通关 2 关
            → 不算需加油（阈值是严格小于 70%，70% 是边界）；
  S7B 队员：L25 答 3/5 → 60% < 70% → 需加油（「正确率低」这条路）；
  S7C 队员：一关不打 → 本周 0 通关 → 需加油（「0 通关」这条路）；
  S7D 别班同学：一关不打（2 班没有排课，看不到关卡）——只用来验跨班隔离与未入队态；
  S7E 单人队同学：L25 答 5/5 → 单人队也要能证明「XP 照计、只是没有小队加成」。

  topup 模式：S7A/S7B/S7C 按解锁链继续补打（每关全对），每补一轮查一次
  /api/team/overview；一直到「小队宝箱解锁」为止——**补几关不预写死**，
  由接口状态决定停在哪，plan-topup.json 会记下每一轮的宝箱快照（含解锁前后那一轮）。
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'

CHECKS = []
FAILS = []

# 演示学生（S7 自建自清，见 cleanup-demo.sh）
STUDENTS = ('S7A', 'S7B', 'S7C', 'S7D', 'S7E')
PASSWORD = 'S7demo2026'
# 第一阶段计划：学生 → [(关卡 id, 计划答对数)]；缺省 = 一关不打
PLAN_SEED = {
    'S7A': [(25, 4), (26, 3)],
    'S7B': [(25, 3)],
    'S7C': [],
    'S7D': [],       # 2 班没有排课（units 只挂在 1 班），看不到任何关卡 → 只验跨班隔离与未入队态
    'S7E': [(25, 5)],
}
WEAK_PAIR = ('S7B', 'S7C')  # 队里的两名需加油队员（S7D 在别班，另有用途）


def check(desc, want, got):
    ok = str(want) == str(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[SEED] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


# ---------------------------------------------------------------- 基础设施

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


def api(method, path, token=None, body=None):
    """统一信封：返回 (http_code, json)。"""
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


def login(user, password):
    code, body = api('POST', '/api/auth/login', body={'username': user, 'password': password})
    if code != 200:
        raise SystemExit('登录失败 {}：{}'.format(user, body))
    return body['data']['token']


# ---------------------------------------------------------------- 题库坐标 → 卷面展示坐标
# （与 S6.5 验收脚本同一套换算：题库存的是选项原文坐标，卷面是洗序后的下标。
#   这里独立再写一份，不从 web/server 源码 import，防止"拿生产代码验生产代码"。）

def load_bank(cur, ids):
    if not ids:
        return {}
    fmt = ','.join(['%s'] * len(ids))
    cur.execute('SELECT id, type, band, answer_idx, options_json FROM questions WHERE id IN ({})'.format(fmt),
                tuple(ids))
    out = {}
    for qid, qtype, band, aidx, oj in cur.fetchall():
        out[int(qid)] = {'type': qtype, 'band': str(band), 'answer_idx': aidx,
                         'options': json.loads(oj or '[]')}
    return out


def bank_answer_idx(meta):
    return [int(x) for x in re.split(r'[，,]', (meta['answer_idx'] or '').strip()) if x.strip() != '']


def correct_picks(q, meta):
    idxs = bank_answer_idx(meta)
    if not idxs:
        raise AssertionError('题 {} 没有 answer_idx'.format(q['id']))
    if q['type'] == 'cloze':
        bank = meta['options']
        words = [w['text'] for w in q['cloze']['wordBank']]
        picks = []
        for i in idxs:
            word = bank[i]
            if bank.count(word) != 1:
                raise AssertionError('题 {} 词表里「{}」出现多次，按文本定位不可靠'.format(q['id'], word))
            picks.append(words.index(word))
        return picks
    if q['type'] == 'match':
        label = str(meta['options'][idxs[0]]).strip().upper()
        hit = [p for p in q['match']['paragraphs'] if str(p['label']).strip().upper() == label]
        if len(hit) != 1:
            raise AssertionError('题 {} 段表里找不到标号 {}（找到 {} 个）'.format(q['id'], label, len(hit)))
        return [hit[0]['idx']]
    bank = meta['options']
    word = bank[idxs[0]]
    if bank.count(word) != 1:
        raise AssertionError('题 {} 题库选项文本重复（{}），按文本定位不可靠'.format(q['id'], word))
    disp = q['options']
    if disp.count(word) != 1:
        raise AssertionError('题 {} 卷面选项文本重复（{}）'.format(q['id'], word))
    return [disp.index(word)]


def wrong_picks(q, meta):
    """故意答错：换掉最后一个空，且换成一个不等于正确项的合法下标。"""
    picks = correct_picks(q, meta)
    if q['type'] == 'cloze':
        size = len(q['cloze']['wordBank'])
    elif q['type'] == 'match':
        size = len(q['match']['paragraphs'])
    else:
        size = len(q['options'])
    if size < 2:
        raise AssertionError('题 {} 只有一个可选项，没法答错'.format(q['id']))
    out = list(picks)
    for i in range(size):
        if i != picks[-1]:
            out[-1] = i
            break
    return out


def fmt_picks(picks):
    return ','.join(str(p) for p in picks)


# ---------------------------------------------------------------- 打关

def level_list(token):
    code, body = api('GET', '/api/quiz/levels', token)
    if code != 200:
        raise SystemExit('取关卡列表失败：{}'.format(body))
    return body['data']['items']


def play_level(cur, token, level, want_correct, tag):
    """打一关：取卷 → 前 want_correct 题按计划答对、其余答错 → 整关提交。"""
    code, body = api('GET', '/api/quiz/paper?level={}'.format(level['id']), token)
    if code != 200:
        raise SystemExit('取卷失败 L{}：{}'.format(level['id'], body))
    paper = body['data']
    meta = load_bank(cur, [q['id'] for q in paper['questions']])
    if want_correct < 0 or want_correct > len(paper['questions']):
        raise SystemExit('L{} 只有 {} 题，答不对 {} 题没法计划'.format(
            level['id'], len(paper['questions']), want_correct))

    answers, intend = [], []
    for i, q in enumerate(paper['questions']):
        picks = correct_picks(q, meta[q['id']])
        if i >= want_correct:
            picks = wrong_picks(q, meta[q['id']])
        answers.append({'questionId': q['id'], 'pickedIdx': fmt_picks(picks), 'elapsedMs': 3000})
        intend.append({'questionId': q['id'], 'type': q['type'], 'correct': picks == correct_picks(q, meta[q['id']])})

    code, body = api('POST', '/api/quiz/submit', token,
                     {'attemptId': paper['attemptId'], 'answers': answers})
    if code != 200:
        raise SystemExit('交卷失败 L{}：{}'.format(level['id'], body))
    data = body['data']
    settled = data.get('settlement')
    if settled is None:
        raise SystemExit('L{} 整关提交后没结算，attempt 状态={}'.format(level['id'], data['status']))

    # 服务端判分必须与计划逐题一致：不一致是我的坐标换算错了，后面三方对拍全不可信，当场停。
    fb = {f['questionId']: f for f in data['feedback']}
    for it in intend:
        f = fb[it['questionId']]
        if bool(f['isCorrect']) != it['correct']:
            raise SystemExit('题 {} 判分与计划不符：计划 correct={} 服务端={}（type={}）'
                             .format(it['questionId'], it['correct'], f['isCorrect'], it['type']))
        it['serverCorrect'] = bool(f['isCorrect'])

    note('L{:<3} {:<24} 状态={:<8} 计划对 {:>2}/{:<2} 服务端 {:>2}/{:<2} 星 {} XP {} attempt={}'.format(
        level['id'], level['name'], data['status'], want_correct, len(paper['questions']),
        settled['correct'], settled['total'], settled['stars'], settled['xpTotal'], data['attemptId']))
    return {
        'levelId': level['id'], 'levelName': level['name'], 'unitName': level['unitName'],
        'attemptId': data['attemptId'], 'status': data['status'], 'tag': tag,
        'plannedCorrect': want_correct,
        'correct': settled['correct'], 'total': settled['total'],
        'stars': settled['stars'], 'xpTotal': settled['xpTotal'],
        'inProgress': data['status'] != 'finished',
        'answers': intend,
    }


def overview(token):
    code, body = api('GET', '/api/team/overview', token)
    if code != 200:
        raise SystemExit('取小队总览失败：{}'.format(body))
    return body['data']


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('seed', 'topup'), default='seed')
    ap.add_argument('--tag', default='seed')
    args = ap.parse_args()

    conn = db_conn()
    cur = conn.cursor()
    tokens = {}
    for u in STUDENTS:
        tokens[u] = login(u, PASSWORD)
        cur.execute('SELECT id FROM users WHERE username=%s', (u,))
        note('学生 {} id={}'.format(u, cur.fetchone()[0]))

    plan = {'phase': args.mode, 'tag': args.tag, 'students': {}, 'rounds': []}

    if args.mode == 'seed':
        check('可玩关卡数 = 24（4 单元 × 四级题库）', 24, len(level_list(tokens['S7A'])))
        for u in STUDENTS:
            cur.execute('SELECT id FROM users WHERE username=%s', (u,))
            uid = int(cur.fetchone()[0])
            rec = {'userId': uid, 'levels': [], 'answers': []}
            for level_id, want in PLAN_SEED[u]:
                items = level_list(tokens[u])
                lv = next((l for l in items if l['id'] == level_id), None)
                if lv is None:
                    raise SystemExit('学生 {} 看不到关卡 {}（可玩关卡：{}）'.format(
                        u, level_id, [l['id'] for l in items] or '一关都没有'))
                check('{} 打 L{} 前已解锁'.format(u, level_id), True, lv['unlocked'])
                one = play_level(cur, tokens[u], lv, want, args.tag)
                rec['levels'].append({k: one[k] for k in ('levelId', 'levelName', 'attemptId', 'status',
                                                          'plannedCorrect', 'correct', 'total', 'stars', 'xpTotal')})
                rec['answers'].extend(one['answers'])
            hand = {'clears': len([l for l in rec['levels'] if l['status'] == 'finished']),
                    'answers': sum(l['total'] for l in rec['levels']),
                    'correct': sum(l['correct'] for l in rec['levels']),
                    'xpReceipts': sum(l['xpTotal'] for l in rec['levels'])}
            rec['hand'] = hand
            plan['students'][u] = rec
            note('{} 手算：通关 {} 关 · 作答 {} 题 · 对 {} 题 · 结算 XP 合计 {}'.format(
                u, hand['clears'], hand['answers'], hand['correct'], hand['xpReceipts']))

        # S7A 的边界必须是「正好 70%」：这是验收③（阈值口径）的算术前置，
        # 前置不对后面全是假绿，所以在这里断言。
        a = plan['students']['S7A']['hand']
        check('S7A 本周正确率正好 7/10 = 70%（阈值边界值）', 0.7, a['correct'] / a['answers'])
        check('S7A 本周通关 2 关（≥1，所以不因「0 通关」被判弱）', 2, a['clears'])
        b = plan['students']['S7B']['hand']
        check('S7B 本周正确率 3/5 = 60%（低于 70% 那条路）', 0.6, b['correct'] / b['answers'])
        c = plan['students']['S7C']['hand']
        check('S7C 本周一关没打（0 通关那条路）', (0, 0, 0), (c['clears'], c['answers'], c['correct']))
        e = plan['students']['S7E']['hand']
        check('S7E 本周 5/5（单人队「XP 照计」的证据）', 5, e['correct'])
        check('S7D 一关没打（2 班没有排课，跨班用例的前提）', (0, 0), (plan['students']['S7D']['hand']['clears'],
                                                                      plan['students']['S7D']['hand']['answers']))

    else:  # topup：按解锁链补打，直到小队宝箱解锁
        played = {u: set() for u in STUDENTS[:3]}
        ov = overview(tokens['S7A'])
        if ov['team'] is None:
            raise SystemExit('S7A 还没入队：先跑 04-reconcile-pre 建队')
        if ov['team']['chest']['unlocked']:
            raise SystemExit('宝箱已经解锁了，不需要补打（是不是重复跑了 topup？）')
        note('补打前小队经验 {}+{}={} / {}'.format(ov['team']['chest']['rawXp'], ov['team']['chest']['bonusXp'],
                                              ov['team']['chest']['xp'], ov['team']['chest']['threshold']))
        for rnd in range(1, 9):
            for u in STUDENTS[:3]:
                lv = next((l for l in sorted(level_list(tokens[u]), key=lambda x: x['id'])
                           if l['unlocked'] and not l['isBoss'] and l['type'] != 'boss'
                           and l['id'] not in played[u]), None)
                if lv is None:
                    note('{} 没有可补打的关卡了（解锁链到头/都是 Boss）'.format(u))
                    continue
                played[u].add(lv['id'])
                rec = plan['students'].setdefault(u, {'userId': None, 'levels': [], 'answers': []})
                one = play_level(cur, tokens[u], lv, lv['questionCount'], 'topup')
                rec['levels'].append({k: one[k] for k in ('levelId', 'levelName', 'attemptId', 'status',
                                                          'plannedCorrect', 'correct', 'total', 'stars', 'xpTotal')})
                rec['answers'].extend(one['answers'])
            ov = overview(tokens['S7A'])
            chest = ov['team']['chest']
            plan['rounds'].append({'round': rnd, 'rawXp': chest['rawXp'], 'bonusXp': chest['bonusXp'],
                                   'xp': chest['xp'], 'progress': chest['progress'], 'remain': chest['remain'],
                                   'unlocked': chest['unlocked']})
            note('第 {} 轮补打后：小队经验 {}+{}={} / {} · 进度 {}% · 解锁 {}'.format(
                rnd, chest['rawXp'], chest['bonusXp'], chest['xp'], chest['threshold'],
                chest['progress'], chest['unlocked']))
            if chest['unlocked']:
                break
        check('补打若干轮后宝箱解锁（解锁与否由接口状态决定，不预写轮数）', True,
              plan['rounds'][-1]['unlocked'] if plan['rounds'] else False)
        if len(plan['rounds']) >= 2:
            check('解锁前那一轮的进度确实没满（真的跨了阈值，不是一开始就满）', True,
                  plan['rounds'][-2]['xp'] < plan['rounds'][-1]['xp'])

    for u in STUDENTS:
        rec = plan['students'].get(u, {'userId': None, 'levels': [], 'answers': []})
        hand = {'clears': len([l for l in rec['levels'] if l['status'] == 'finished']),
                'answers': sum(l['total'] for l in rec['levels']),
                'correct': sum(l['correct'] for l in rec['levels']),
                'xpReceipts': sum(l['xpTotal'] for l in rec['levels'])}
        rec['hand'] = hand
        if rec['userId'] is None:
            cur.execute('SELECT id FROM users WHERE username=%s', (u,))
            row = cur.fetchone()
            rec['userId'] = int(row[0]) if row else None

    with io.open(os.path.join(HERE, 'plan-{}.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(HERE, 'team-seed-{}.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump({'checks': CHECKS, 'fails': FAILS, 'plan': 'plan-{}.json'.format(args.tag)},
                  fh, ensure_ascii=False, indent=1)

    print()
    print('plan-{}.json 已写出（{} 模式的手算底稿）'.format(args.tag, args.mode))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())