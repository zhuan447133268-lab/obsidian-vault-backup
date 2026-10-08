#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6.5 验收数据准备：把演示学生的数据按**计划**打出来（真库 :3307 + 真服务 :8080）。

口径：所有作答都走真实链路（GET /api/quiz/paper → 服务端洗序 → POST /api/quiz/submit
服务端判分写流水），脚本只决定「答什么」——不直接往表里插 attempt_answers。
唯一的直写是「把几关的流水回拨到过去几周」（attempts.finished_at / attempt_answers.created_at /
xp_ledger.created_at 同步平移），用来验证 8 周分桶：生产里这三张表的时间由服务端写，
不搬时间就没法在真库里验出「跨周」这一面。

产物 plan.json = 本次作答的全量底稿（题号/题型/对错/关卡/attempt）：它是验收①「手算对拍」的
手算那一侧，profile-reconcile.py 会拿它跟 SQL 聚合、接口回执三方对。
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'
API = BASE + '/api'

CHECKS = []
FAILS = []


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

def load_bank(cur, ids):
    """题库原始答案（questions.answer_idx / options_json）：只用来反算「正确项长什么样」。"""
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
    """把题库坐标换算成卷面展示坐标（= 提交的 pickedIdx）。"""
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
    """故意答错：换掉其中一个空，且换成一个**不等于正确项**的合法下标。"""
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


# ---------------------------------------------------------------- 关卡 / 诊断

def level_list(token):
    code, body = api('GET', '/api/quiz/levels', token)
    if code != 200:
        raise SystemExit('取关卡列表失败：{}'.format(body))
    return body['data']['items']


def play_level(cur, token, level, wrong_level_ids, tag):
    """打一关：取卷 → 按计划作答（默认全对）→ 整关提交。返回本关的作答底稿。"""
    code, body = api('GET', '/api/quiz/paper?level={}'.format(level['id']), token)
    if code != 200:
        raise SystemExit('取卷失败 L{}：{}'.format(level['id'], body))
    paper = body['data']
    meta = load_bank(cur, [q['id'] for q in paper['questions']])

    planned_wrong = level['id'] in wrong_level_ids
    answers = []
    intend = []
    for i, q in enumerate(paper['questions']):
        correct = correct_picks(q, meta[q['id']])
        picks = correct
        # 只在指定的关卡里制造错题，且每关只错第一题（爱心 3 颗，留足余量）
        if planned_wrong and i == 0:
            picks = wrong_picks(q, meta[q['id']])
        answers.append({'questionId': q['id'], 'pickedIdx': fmt_picks(picks), 'elapsedMs': 3000})
        intend.append({'questionId': q['id'], 'type': q['type'],
                       'correct': picks == correct, 'plannedWrong': picks != correct})

    code, body = api('POST', '/api/quiz/submit', token,
                     {'attemptId': paper['attemptId'], 'answers': answers})
    if code != 200:
        raise SystemExit('交卷失败 L{}：{}'.format(level['id'], body))
    data = body['data']
    settled = data.get('settlement')
    if settled is None:
        raise SystemExit('L{} 整关提交后没结算，attempt 状态={}'.format(level['id'], data['status']))

    # 服务端判分与计划必须逐题一致：不一致说明我的坐标换算错了（不是服务端错），
    # 那种情况下后面的「手算对拍」全是错的，必须当场停。
    fb = {f['questionId']: f for f in data['feedback']}
    for it in intend:
        f = fb[it['questionId']]
        if bool(f['isCorrect']) != it['correct']:
            raise SystemExit('题 {} 判分与计划不符：计划 correct={} 服务端={}（type={}）'
                             .format(it['questionId'], it['correct'], f['isCorrect'], it['type']))
        it['serverCorrect'] = bool(f['isCorrect'])
        it['fdbkType'] = f['type']
        if it['fdbkType'] != it['type']:
            raise SystemExit('题 {} 回执题型与卷面题型不符'.format(it['questionId']))

    note('L{:<3} {:<22} 状态={:<8} 对 {:>2}/{:<2} 星 {} XP {} attempt={}'.format(
        level['id'], level['name'], data['status'], settled['correct'], settled['total'],
        settled['stars'], settled['xpTotal'], data['attemptId']))
    return {
        'levelId': level['id'], 'levelName': level['name'], 'unitName': level['unitName'],
        'attemptId': data['attemptId'], 'status': data['status'], 'tag': tag,
        'correct': settled['correct'], 'total': settled['total'],
        'answers': intend,
    }


def run_diag(cur, token, mode):
    """打一次入学诊断：mode=wrong 全错 / mode=right 全对。返回诊断回执（含 byType）。"""
    code, body = api('GET', '/api/diag/paper', token)
    if code != 200:
        raise SystemExit('取诊断卷失败：{}'.format(body))
    paper = body['data']
    meta = load_bank(cur, [q['id'] for q in paper['questions']])
    answers = []
    for q in paper['questions']:
        picks = correct_picks(q, meta[q['id']]) if mode == 'right' else wrong_picks(q, meta[q['id']])
        answers.append({'questionId': q['id'], 'pickedIdx': fmt_picks(picks), 'elapsedMs': 4000})
    code, body = api('POST', '/api/diag/submit', token, {'answers': answers})
    if code != 200:
        raise SystemExit('提交诊断失败：{}'.format(body))
    data = body['data']
    note('诊断（{}）：答对 {}/{} · 档次 {} · diagnosisId={}'.format(
        mode, data['result']['correct'], data['result']['total'], data['result']['level'],
        data['diagnosisId']))
    return {
        'mode': mode,
        'diagnosisId': data['diagnosisId'],
        'correct': data['result']['correct'],
        'total': data['result']['total'],
        'accuracy': data['result']['accuracy'],
        'level': data['result']['level'],
        'byType': data['result']['byType'],
    }


# ---------------------------------------------------------------- 时间平移（验 8 周分桶）

def backdate(cur, uid, attempt_id, days):
    cur.execute('UPDATE attempts SET finished_at = finished_at - INTERVAL %s DAY,'
                ' started_at = started_at - INTERVAL %s DAY WHERE id=%s AND user_id=%s',
                (days, days, attempt_id, uid))
    n_ans = cur.execute('UPDATE attempt_answers SET created_at = created_at - INTERVAL %s DAY'
                        ' WHERE attempt_id=%s', (days, attempt_id))
    n_xp = cur.execute("UPDATE xp_ledger SET created_at = created_at - INTERVAL %s DAY"
                       " WHERE user_id=%s AND ref_type='attempt' AND ref_id=%s",
                       (days, uid, attempt_id))
    return {'attemptId': attempt_id, 'days': days, 'answers': int(n_ans), 'ledger': int(n_xp)}


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--tag', default='seed')
    args = ap.parse_args()

    token = login(args.user, args.password)
    cur = db_conn().cursor()
    cur.execute('SELECT id FROM users WHERE username=%s', (args.user,))
    uid = int(cur.fetchone()[0])
    note('学生 {} id={}'.format(args.user, uid))

    # 计划：在这 4 关各留一道错题（都落在第 1 个专题「校园生活」里，好让「专题结束推送」只有 1 个单元，
    # 也够触发错题本「默认只展开前 3 条 + 展开全部」那条 UI 路径——只有 2 条错题时那个按钮根本不出现）。
    # 关名在题库里会重名（三套真题各有一模一样的「听力 · 新闻 3 篇」），一律按关卡 id 定位。
    wrong_level_ids = [25, 26, 29, 30]

    levels = level_list(token)
    check('可玩关卡数 = 24（4 单元 × 四级题库）', 24, len(levels))
    check('每关都带题量（进关预告口径）', True, all(l['questionCount'] > 0 for l in levels))

    levels_out = []
    answers_out = []
    for lv in levels:
        # 解锁链：一关关开。**每关开打前重新取一次列表**——开跑前那次快照是「零进度」状态，
        # 除了每个单元的第 1 关其余都还是锁定，拿它当断言会误报（上一版就踩过）。
        fresh = {l['id']: l for l in level_list(token)}
        check('L{} 开打前已解锁（线性解锁链）'.format(lv['id']), True, fresh[lv['id']]['unlocked'])
        rec = play_level(cur, token, lv, wrong_level_ids, args.tag)
        levels_out.append({k: rec[k] for k in ('levelId', 'levelName', 'unitName', 'attemptId',
                                              'status', 'correct', 'total')})
        answers_out.extend(rec['answers'])

    check('24 关全部通关（status=finished）', 24, len([l for l in levels_out if l['status'] == 'finished']))
    wrongs = [a['questionId'] for a in answers_out if not a['correct']]
    check('计划内的故意错题数 = {}'.format(len(wrong_level_ids)), len(wrong_level_ids), len(wrongs))
    note('错题题号：{}'.format(wrongs))

    # 诊断两次：最近一次才算数（第一次全错、第二次全对，任何「两次混算」都会被对拍抓出来）
    diag1 = run_diag(cur, token, 'wrong')
    diag2 = run_diag(cur, token, 'right')

    # 把几关的流水回拨到过去几周（含一个 9 周前 → 必须落在 8 周窗口外）
    by_id = {l['levelId']: l for l in levels_out}
    shifts = [(27, 7), (28, 14), (31, 21), (32, 28), (36, 63)]
    backdates = []
    for lid, days in shifts:
        lv = by_id[lid]
        bd = backdate(cur, uid, lv['attemptId'], days)
        backdates.append(dict(bd, levelId=lv['levelId'], levelName=lv['levelName']))
        note('回拨 {} 天：L{}（{}）attempt={} 平移 answers={} ledger={}'.format(
            days, lv['levelId'], lv['levelName'], lv['attemptId'], bd['answers'], bd['ledger']))

    plan = {
        'user': args.user, 'userId': uid, 'tag': args.tag,
        'levels': levels_out, 'answers': answers_out,
        'diags': [diag1, diag2],
        'backdates': backdates,
        'wrongLevelIds': wrong_level_ids,
        'wrongLevelNames': [by_id[i]['levelName'] for i in wrong_level_ids],
    }
    with io.open(os.path.join(HERE, 'plan-{}.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(HERE, 'profile-{}-seed.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump({'checks': CHECKS, 'fails': FAILS, 'plan': 'plan-{}.json'.format(args.tag)},
                  fh, ensure_ascii=False, indent=1)

    print()
    print('作答合计 {} 题 · 错 {} 题 · 诊断 {} 次'.format(
        len(answers_out), len(wrongs), len(plan['diags'])))
    print('plan-{}.json 已写出（手算对拍的底稿）'.format(args.tag))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())