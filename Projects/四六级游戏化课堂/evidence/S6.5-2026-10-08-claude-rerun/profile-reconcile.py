#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6.5 验收①②③：三个数据面「手算（plan.json）× SQL 聚合 × 接口回执」三方对拍。

三条口径全部在这里独立重写一遍（不调用 Go 侧任何东西、也不读服务端代码）：
  ① 六边形：题型→维度映射 + 正确率档次阈值 + 「最近一次诊断」叠加；
  ② 错题本：wrong_book 的逐题 wrong_count/mastered/last_at + 按专题归组 + 排序 + 题干截断 + 推送文案；
  ③ 成长曲线：周一 00:00 分桶（attempts.finished_at / attempt_answers.created_at / xp_ledger.created_at）
     与 8 周窗口裁剪。

对拍的意义：三侧只要有一边算错就会露出差异——服务端聚合错、SQL 写错、或我手算错，都会被抓到。
"""
import argparse
import io
import json
import math
import os
import sys
from datetime import datetime, timedelta

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'

# ---- 独立重写的口径（不许从服务端代码里抄） ----
DIMS = [('vocab', '词汇'), ('grammar', '语法'), ('reading', '阅读'),
        ('listening', '听力'), ('translation', '翻译'), ('writing', '写作')]
TYPE_TO_DIM = {'vocab': 'vocab', 'grammar': 'grammar', 'reading': 'reading',
               'cloze': 'reading', 'match': 'reading', 'listening': 'listening',
               'translation': 'translation', 'writing': 'writing'}
TREND_WEEKS = 8
STEM_RUNES = 160
XP_PER_LEVEL = 300

CHECKS = []
FAILS = []


def _norm(v):
    """比较前归一：Go 的 float64(1) 序列化成 1，别让 1.0 / 1 的写法差异变成假失败；
    布尔转字符串——Python 里 True == 1，但「已掌握」和「1 条」不是一回事。"""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return v


def check(desc, want, got):
    ok = _norm(want) == _norm(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[RECON] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


def dim_of(qtype):
    return TYPE_TO_DIM.get(qtype, '')


def round2(x):
    """与 Go math.Round 同口径（四舍五入远离 0），别用 Python 的银行家舍入。"""
    return math.floor(x * 100 + 0.5) / 100.0


def acc_of(correct, total):
    return 0.0 if total <= 0 else round2(float(correct) / float(total))


def level_text(acc):
    if acc >= 0.8:
        return '扎实'
    if acc >= 0.6:
        return '中等'
    return '待加强'


def week_start(dt):
    day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def week_label(dt):
    return '{}/{}'.format(dt.month, dt.day)


def rfc3339(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S')


def truncate_runes(s, n):
    if len(s) <= n:
        return s
    return s[:n] + '…'


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


def api_get(path, token):
    import urllib.request
    req = urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))['data']


def api_login(user, password):
    import urllib.request
    body = json.dumps({'username': user, 'password': password}).encode('utf-8')
    req = urllib.request.Request(BASE + '/api/auth/login', data=body,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))['data']['token']


# ================================================================ ① 六边形

def plan_hexagon(plan):
    """手算侧：只看我在计划里答了什么（含重刷），加上「最近一次」诊断。"""
    at = {k: {'correct': 0, 'total': 0} for k, _ in DIMS}
    for a in plan['answers']:
        d = dim_of(a['type'])
        if not d:
            continue
        at[d]['total'] += 1
        if a['correct']:
            at[d]['correct'] += 1
    dg = {k: {'correct': 0, 'total': 0} for k, _ in DIMS}
    latest = plan['diags'][-1]
    for qtype, v in latest['byType'].items():
        d = dim_of(qtype)
        if not d:
            continue
        dg[d]['correct'] += v['correct']
        dg[d]['total'] += v['total']
    out = {}
    for k, _ in DIMS:
        out[k] = {'attemptCorrect': at[k]['correct'], 'attemptTotal': at[k]['total'],
                  'diagCorrect': dg[k]['correct'], 'diagTotal': dg[k]['total'],
                  'correct': at[k]['correct'] + dg[k]['correct'],
                  'total': at[k]['total'] + dg[k]['total']}
        out[k]['accuracy'] = acc_of(out[k]['correct'], out[k]['total'])
    return out


def sql_hexagon(cur, uid):
    """SQL 侧：流水按题型聚合 + 最近一次诊断的 result_json 逐题型计数（映射由本脚本自己做）。"""
    cur.execute('SELECT q.type, COUNT(*), COALESCE(SUM(aa.is_correct),0)'
                ' FROM attempt_answers aa'
                ' JOIN attempts a ON a.id = aa.attempt_id'
                ' JOIN questions q ON q.id = aa.question_id'
                ' WHERE a.user_id=%s GROUP BY q.type', (uid,))
    at = {k: {'correct': 0, 'total': 0} for k, _ in DIMS}
    for qtype, total, correct in cur.fetchall():
        d = dim_of(qtype)
        if not d:
            continue
        at[d]['total'] += int(total)
        at[d]['correct'] += int(correct)
    cur.execute('SELECT result_json FROM diagnoses WHERE user_id=%s ORDER BY id DESC LIMIT 1', (uid,))
    row = cur.fetchone()
    payload = json.loads(row[0]) if row else {}
    dg = {k: {'correct': 0, 'total': 0} for k, _ in DIMS}
    for qtype, v in (payload.get('byType') or {}).items():
        d = dim_of(qtype)
        if not d:
            continue
        dg[d]['correct'] += int(v['correct'])
        dg[d]['total'] += int(v['total'])
    out = {}
    for k, _ in DIMS:
        out[k] = {'attemptCorrect': at[k]['correct'], 'attemptTotal': at[k]['total'],
                  'diagCorrect': dg[k]['correct'], 'diagTotal': dg[k]['total'],
                  'correct': at[k]['correct'] + dg[k]['correct'],
                  'total': at[k]['total'] + dg[k]['total']}
        out[k]['accuracy'] = acc_of(out[k]['correct'], out[k]['total'])
    return out, payload


def api_hexagon(ov):
    out = {}
    for d in ov['hexagon']['dims']:
        out[d['key']] = d
    return out


def check_hexagon(cur, uid, plan, ov):
    print('--- ① 六边形能力画像（手算 × SQL × 接口）---')
    ph = plan_hexagon(plan)
    sh, diag_payload = sql_hexagon(cur, uid)
    ah = api_hexagon(ov)

    print('    {:<8}{:>22}{:>22}{:>22}'.format('维度', '手算(plan.json)', 'SQL 聚合', '接口回执'))
    for k, label in DIMS:
        p, s, a = ph[k], sh[k], ah[k]
        print('    {:<8}{:>22}{:>22}{:>22}'.format(
            label,
            '{}/{} {}'.format(p['correct'], p['total'], p['accuracy']),
            '{}/{} {}'.format(s['correct'], s['total'], s['accuracy']),
            '{}/{} {}'.format(a['correct'], a['total'], a['accuracy'])))

    for k, label in DIMS:
        for field in ('correct', 'total', 'accuracy', 'attemptCorrect', 'attemptTotal',
                      'diagCorrect', 'diagTotal'):
            check('六维「{}」{}：手算=SQL'.format(label, field), ph[k][field], sh[k][field])
            check('六维「{}」{}：SQL=接口'.format(label, field), sh[k][field], ah[k][field])

    coverage = len([1 for k, _ in DIMS if ph[k]['total'] > 0])
    correct = sum(ph[k]['correct'] for k, _ in DIMS)
    total = sum(ph[k]['total'] for k, _ in DIMS)
    check('已覆盖维度数 = 有作答的维数（写作无题 → 0 数据）', coverage, ov['hexagon']['coverage'])
    check('六维合计正确率 → 档次文案', level_text(acc_of(correct, total)), ov['hexagon']['level'])
    check('接口档位与「扎实/中等/待加强」阈值一致（独立复算）', True,
          ov['hexagon']['level'] == level_text(ov['summary']['accuracy']))
    check('六维轴次序由服务端固定下发（词汇→语法→阅读→听力→翻译→写作）',
          'vocab,grammar,reading,listening,translation,writing',
          ','.join(d['key'] for d in ov['hexagon']['dims']))
    check('写作维一期无题（0 数据，不是答错）', '0/0', '{}/{}'.format(ph['writing']['total'],
                                                                  ph['writing']['total']))

    # 「只取最近一次诊断」：两次诊断混算会得到另一个数（第一次全错、第二次全对）
    both = {k: {'correct': 0, 'total': 0} for k, _ in DIMS}
    for d in plan['diags']:
        for qtype, v in d['byType'].items():
            dim = dim_of(qtype)
            if dim:
                both[dim]['correct'] += v['correct']
                both[dim]['total'] += v['total']
    mixed = {k: both[k]['total'] > ph[k]['diagTotal'] for k, _ in DIMS}
    check('诊断侧只取最近一次（两次混算会不同，选择器能分辨）', True, any(mixed.values()))
    check('最近一次诊断 = 计划里的第 2 次（全对）', plan['diags'][-1]['diagnosisId'],
          ov['latestDiag']['diagnosisId'])
    check('诊断卡的题量与 result_json 一致', '{}/{}'.format(diag_payload['correct'],
                                                          diag_payload['total']),
          '{}/{}'.format(ov['latestDiag']['correct'], ov['latestDiag']['total']))
    check('诊断卡档次 = 阈值函数(诊断正确率)', level_text(diag_payload['accuracy']),
          ov['latestDiag']['level'])
    check('第一次诊断的档次与最近一次不同（取错那次一眼能看出来）', True,
          plan['diags'][0]['level'] != plan['diags'][-1]['level'])


# ================================================================ ② 错题本

def plan_wrongbook(plan):
    """手算侧：答错→进本子并计数；之后答对→mastered（last_at 不刷新，这是 S6 定的口径）。"""
    order = {}
    for i, a in enumerate(plan['answers']):
        qid = a['questionId']
        rec = order.setdefault(qid, {'wrong': 0, 'lastWrong': -1, 'lastCorrect': -1})
        if a['correct']:
            rec['lastCorrect'] = i
        else:
            rec['wrong'] += 1
            rec['lastWrong'] = i
    out = {}
    for qid, rec in order.items():
        if rec['wrong'] == 0:
            continue
        out[qid] = {'wrongCount': rec['wrong'], 'mastered': rec['lastCorrect'] > rec['lastWrong']}
    return out


def sql_wrongbook(cur, uid):
    cur.execute('SELECT question_id, wrong_count, last_at, mastered FROM wrong_book WHERE user_id=%s'
                ' ORDER BY question_id ASC', (uid,))
    return {int(q): {'wrongCount': int(wc), 'mastered': bool(m), 'lastAt': la}
            for q, wc, la, m in cur.fetchall()}


def sql_wrong_rows(cur, uid):
    """归组与排序用：带单元与题面信息（排序由本脚本按 ORDER BY 语义自己排）。"""
    cur.execute('SELECT wb.question_id, wb.wrong_count, wb.last_at, wb.mastered, q.type,'
                ' q.knowledge_tag, q.stem, u.id, u.week_no, u.name'
                ' FROM wrong_book wb'
                ' JOIN questions q ON q.id = wb.question_id'
                ' JOIN levels l ON l.id = q.level_id'
                ' JOIN units u ON u.id = l.unit_id'
                ' WHERE wb.user_id=%s', (uid,))
    rows = []
    for qid, wc, la, m, qtype, tag, stem, uid_, week, name in cur.fetchall():
        rows.append({'questionId': int(qid), 'wrongCount': int(wc), 'lastAt': la, 'mastered': bool(m),
                     'type': qtype, 'knowledgeTag': tag or '', 'stem': stem,
                     'unitId': int(uid_), 'weekNo': int(week), 'unitName': name})
    rows.sort(key=lambda r: (r['weekNo'], r['unitId'], r['mastered'], -r['lastAt'].timestamp(),
                             r['questionId']))
    return rows


def sql_unit_cleared(cur, uid):
    """专题是否已结束：该单元有题的关全部通关（有 finished attempt）。"""
    cur.execute('SELECT u.id, COUNT(DISTINCT l.id),'
                ' COUNT(DISTINCT CASE WHEN a.status=%s THEN l.id END)'
                ' FROM units u'
                ' JOIN levels l ON l.unit_id = u.id'
                ' JOIN questions q ON q.level_id = l.id'
                ' LEFT JOIN attempts a ON a.level_id = l.id AND a.user_id=%s'
                ' WHERE u.class_id = (SELECT class_id FROM users WHERE id=%s)'
                ' GROUP BY u.id', ('finished', uid, uid))
    out = {}
    for unit_id, total, cleared in cur.fetchall():
        out[int(unit_id)] = int(total) > 0 and int(total) == int(cleared)
    return out


def check_wrongbook(cur, uid, plan, ov):
    print('--- ② 错题本（手算 × SQL × 接口）---')
    pw = plan_wrongbook(plan)
    sw = sql_wrongbook(cur, uid)
    rows = sql_wrong_rows(cur, uid)
    cleared = sql_unit_cleared(cur, uid)
    book = ov['wrongBook']

    check('错题题号集合：手算=SQL', sorted(pw.keys()), sorted(sw.keys()))
    for qid in sorted(pw.keys()):
        check('题 {} 错过次数：手算=SQL'.format(qid), pw[qid]['wrongCount'], sw[qid]['wrongCount'])
        check('题 {} 掌握标记：手算=SQL'.format(qid), pw[qid]['mastered'], sw[qid]['mastered'])
        check('题 {} 错过次数：SQL=接口'.format(qid), sw[qid]['wrongCount'],
              next((i['wrongCount'] for g in book['groups'] for i in g['items']
                    if i['questionId'] == qid), None))
        check('题 {} 掌握标记：SQL=接口'.format(qid), sw[qid]['mastered'],
              next((i['mastered'] for g in book['groups'] for i in g['items']
                    if i['questionId'] == qid), None))
        api_last = next((i['lastAt'] for g in book['groups'] for i in g['items']
                         if i['questionId'] == qid), None)
        # 接口按 RFC3339 下发（带本地偏移），SQL 侧 DATETIME 无时区：比到秒，偏移单独断言
        check('题 {} lastAt：SQL=接口（比到秒）'.format(qid), rfc3339(sw[qid]['lastAt']),
              (api_last or '')[:19])
        check('题 {} lastAt 带本地时区偏移'.format(qid),
              datetime.now().astimezone().strftime('%z')[:3] + ':' +
              datetime.now().astimezone().strftime('%z')[3:], (api_last or '')[19:])

    check('错题本条目数 = wrong_book 行数', len(rows),
          sum(len(g['items']) for g in book['groups']))
    check('待复盘数：SQL=接口', len([r for r in rows if not r['mastered']]), book['pendingCount'])
    check('已掌握数：SQL=接口', len([r for r in rows if r['mastered']]), book['masteredCount'])

    # 归组与排序：把接口给的顺序逐条比对我自己排出来的顺序
    flat = [(i['questionId'], g['unitId'], g['weekNo'], g['unitName'], i['mastered'], i['type'])
            for g in book['groups'] for i in g['items']]
    want = [(r['questionId'], r['unitId'], r['weekNo'], r['unitName'], r['mastered'], r['type'])
            for r in rows]
    check('归组与组内次序（周→单元→未掌握优先→最近出错在前→题号）与 SQL 一致', want, flat)
    for g in book['groups']:
        check('组「{}」unitCleared 与「该单元有题的关全通关」一致'.format(g['unitName']),
              cleared.get(g['unitId'], False), g['unitCleared'])
        check('组「{}」计数 = 组内条目数'.format(g['unitName']),
              (len([i for i in g['items'] if not i['mastered']]),
               len([i for i in g['items'] if i['mastered']])),
              (g['pendingCount'], g['masteredCount']))

    # 题干摘要：按字符截断到 160 + 省略号（真题段落匹配题干几千字，整篇下发会拖垮手机端）
    bad_len = [i['questionId'] for g in book['groups'] for i in g['items']
               if len(i['stem']) > STEM_RUNES + 1]
    check('题干摘要不超过 160 字 + 省略号', '[]', str(bad_len))
    for r in rows:
        api_stem = next(i['stem'] for g in book['groups'] for i in g['items']
                        if i['questionId'] == r['questionId'])
        check('题 {} 题干摘要 = 按字符截断(160)'.format(r['questionId']),
              truncate_runes(r['stem'], STEM_RUNES), api_stem)

    # 推送形态：专题结束 + 本子还有未掌握错题 → 提醒条（一期落地，无推送通道）
    cleared_pending = [(g['unitId'], g['weekNo'], g['unitName'],
                        len([i for i in g['items'] if not i['mastered']]))
                       for g in book['groups']
                       if g['unitCleared'] and g['pendingCount'] > 0]
    push = ov['push']
    check('hasPending = 存在「已结束且还有未掌握错题」的专题', len(cleared_pending) > 0, push['hasPending'])
    check('推送单元列表：SQL=接口',
          [(u[0], u[1], u[2], u[3]) for u in cleared_pending],
          [(u['unitId'], u['weekNo'], u['name'], u['pendingCount']) for u in push['pendingUnits']])
    total_pending = sum(u[3] for u in cleared_pending)
    if len(cleared_pending) == 1:
        want_msg = '「{}」已通关，还有 {} 道错题没补回来，来复盘吧'.format(cleared_pending[0][2], total_pending)
    elif len(cleared_pending) > 1:
        want_msg = '{} 个专题已通关，共 {} 道错题没补回来，来复盘吧'.format(len(cleared_pending), total_pending)
    else:
        want_msg = ''
    check('推送文案（独立拼一遍）', want_msg, push['message'])
    note('提醒条文案：{}'.format(push['message'] or '（无）'))


# ================================================================ ③ 成长曲线

def sql_week_rows(cur, uid):
    cur.execute('SELECT finished_at FROM attempts WHERE user_id=%s AND finished_at IS NOT NULL', (uid,))
    attempts = [r[0] for r in cur.fetchall()]
    cur.execute('SELECT aa.created_at, aa.is_correct FROM attempt_answers aa'
                ' JOIN attempts a ON a.id = aa.attempt_id WHERE a.user_id=%s', (uid,))
    answers = [(r[0], bool(r[1])) for r in cur.fetchall()]
    cur.execute('SELECT created_at, delta FROM xp_ledger WHERE user_id=%s', (uid,))
    ledger = [(r[0], int(r[1])) for r in cur.fetchall()]
    return attempts, answers, ledger


def bucket_all(rows, now, weeks=TREND_WEEKS):
    """把全部行按周一 00:00 落桶（**不先做时间过滤**：窗口外的行必须能被算出来，
    这样「窗口裁剪」才是被验证过的一条规则，而不是被过滤条件藏起来的）。"""
    points = {week_start(now - timedelta(days=7 * i)): {'attempts': 0, 'answers': 0, 'correct': 0, 'xp': 0}
              for i in range(weeks)}
    outside = {'attempts': 0, 'answers': 0, 'correct': 0, 'xp': 0}

    def cell_of(t):
        """取该行所属的桶：在 8 周窗口内是那一格，窗口外统一进 outside。"""
        k = week_start(t)
        return points[k] if k in points else outside

    for t in rows[0]:
        cell_of(t)['attempts'] += 1
    for t, ok in rows[1]:
        cell = cell_of(t)
        cell['answers'] += 1
        if ok:
            cell['correct'] += 1
    for t, delta in rows[2]:
        cell_of(t)['xp'] += delta
    return points, outside


def check_trend(cur, uid, plan, ov, now=None):
    print('--- ③ 成长曲线（SQL 分桶 × 接口数据点）---')
    now = now or datetime.now()
    starts = [week_start(now - timedelta(days=7 * i)) for i in range(TREND_WEEKS - 1, -1, -1)]
    points, outside = bucket_all(sql_week_rows(cur, uid), now)

    weeks = ov['trend']['weeks']
    check('曲线数据点 = 8 个（近 8 周含本周）', 8, len(weeks))
    check('横轴标签 = 8 个 M/D（升序，含本周）', [week_label(s) for s in starts],
          [w['label'] for w in weeks])
    check('周起点 = 8 个周一 00:00（升序）', [s.strftime('%Y-%m-%d') for s in starts],
          [w['weekStart'] for w in weeks])
    for i, s in enumerate(starts):
        got = weeks[i]
        want = points[s]
        check('第 {} 周（{}）attempts：SQL=接口'.format(i + 1, week_label(s)), want['attempts'], got['attempts'])
        check('第 {} 周（{}）answers：SQL=接口'.format(i + 1, week_label(s)), want['answers'], got['answers'])
        check('第 {} 周（{}）correct：SQL=接口'.format(i + 1, week_label(s)), want['correct'], got['correct'])
        check('第 {} 周（{}）accuracy：SQL=接口（两位小数）'.format(i + 1, week_label(s)),
              acc_of(want['correct'], want['answers']), got['accuracy'])
        check('第 {} 周（{}）XP：SQL=接口'.format(i + 1, week_label(s)), want['xp'], got['xp'])
    check('有数据的周数 = 8 点里非零的周数', len([1 for s in starts if points[s]['answers'] or
                                                points[s]['attempts'] or points[s]['xp']]),
          ov['trend']['weeksWithData'])

    # 窗口裁剪：9 周前那次闯关（脚本回拨 63 天）必须落在窗口外，且不影响任何一周
    check('窗口外的行确实存在（证明窗口裁剪是被算过的，不是没数据）', True,
          outside['attempts'] + outside['answers'] + outside['xp'] > 0)
    note('窗口外（9 周前）行数：attempts={} answers={} xp={}'.format(
        outside['attempts'], outside['answers'], outside['xp']))
    raw_attempts = sql_week_rows(cur, uid)[0]
    in_window = len([1 for t in raw_attempts if week_start(t) in points])
    check('8 个点的 attempts 合计 = 窗口内行数（窗口外被裁掉）', in_window,
          sum(points[s]['attempts'] for s in starts))
    check('窗口外 attempts = 全库行数 − 窗口内行数', len(raw_attempts) - in_window, outside['attempts'])

    # 回拨到第几周：手算一个（-7 天 → 上一个自然周）
    bd = {b['levelId']: b['days'] for b in plan['backdates']}
    if 27 in bd:
        check('回拨 7 天的关卡落在「上周」（第 7 个点）', 1, points[starts[6]]['attempts'])

    # XP 唯一权威：账本聚合
    cur.execute('SELECT COALESCE(SUM(delta),0) FROM xp_ledger WHERE user_id=%s', (uid,))
    xp_all = int(cur.fetchone()[0])
    check('概览总 XP = 账本 SUM(delta)（唯一权威）', xp_all, ov['summary']['xpTotal'])
    check('窗口内 8 周 XP 合计 = 账本总额 − 窗口外', xp_all - outside['xp'],
          sum(w['xp'] for w in weeks))
    check('等级换算 = 1 + XP/300（服务端不落库，独立复算）',
          (1 + max(0, xp_all) // XP_PER_LEVEL, max(0, xp_all) % XP_PER_LEVEL, XP_PER_LEVEL),
          (ov['summary']['lv'], ov['summary']['xpInLevel'], ov['summary']['xpPerLevel']))


# ================================================================ ④ 概览汇总

def check_summary(cur, uid, plan, ov):
    print('--- ④ 档案概览四格与进度（SQL × 接口）---')
    s = ov['summary']
    cur.execute('SELECT COUNT(DISTINCT l.id),'
                ' COUNT(DISTINCT CASE WHEN a.status=%s THEN l.id END)'
                ' FROM levels l JOIN questions q ON q.level_id=l.id'
                ' JOIN units u ON u.id=l.unit_id'
                ' LEFT JOIN attempts a ON a.level_id=l.id AND a.user_id=%s'
                ' WHERE u.class_id=(SELECT class_id FROM users WHERE id=%s)', ('finished', uid, uid))
    levels_total, levels_cleared = [int(x) for x in cur.fetchone()]
    cur.execute('SELECT COUNT(DISTINCT u.id) FROM units u JOIN levels l ON l.unit_id=u.id'
                ' JOIN questions q ON q.level_id=l.id'
                ' WHERE u.class_id=(SELECT class_id FROM users WHERE id=%s)', (uid,))
    units_total = int(cur.fetchone()[0])
    cleared = sql_unit_cleared(cur, uid)
    units_cleared = len([1 for k, v in cleared.items() if v])
    check('关卡总数（有题的关）', levels_total, s['levelsTotal'])
    check('已通关关卡数', levels_cleared, s['levelsCleared'])
    check('专题总数', units_total, s['unitsTotal'])
    check('已通关专题数（单元内有题的关全通关）', units_cleared, s['unitsCleared'])
    # 概览的「作答/答对」= 六维合计 = 闯关流水 + **最近一次诊断**（画像口径，见服务端注释）：
    # 诊断没有 attempt 流水，但它算进画像，所以概览这两格也必须把最近一次诊断加上。
    diag = plan['diags'][-1]
    plan_correct = len([a for a in plan['answers'] if a['correct']])
    check('作答总数（手算 = 闯关流水 + 最近一次诊断）', len(plan['answers']) + diag['total'],
          s['answersTotal'])
    check('答对总数（手算 = 闯关答对 + 最近一次诊断答对）', plan_correct + diag['correct'],
          s['correctTotal'])
    check('正确率（两位小数）', acc_of(plan_correct + diag['correct'],
                                     len(plan['answers']) + diag['total']), s['accuracy'])
    check('待复盘错题数 = 错题本 pendingCount', ov['wrongBook']['pendingCount'], s['pendingWrong'])
    check('已掌握错题数 = 错题本 masteredCount', ov['wrongBook']['masteredCount'], s['masteredWrong'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--tag', default='seed')
    ap.add_argument('--phase', default='pre', help='只用于日志与产物文件名（pre=补题前 / post=补题后）')
    args = ap.parse_args()

    with io.open(os.path.join(HERE, 'plan-{}.json'.format(args.tag)), encoding='utf-8') as fh:
        plan = json.load(fh)
    token = api_login(args.user, args.password)
    ov = api_get('/api/profile/overview', token)
    cur = db_conn().cursor()
    cur.execute('SELECT id FROM users WHERE username=%s', (args.user,))
    uid = int(cur.fetchone()[0])

    check_hexagon(cur, uid, plan, ov)
    print()
    check_wrongbook(cur, uid, plan, ov)
    print()
    check_trend(cur, uid, plan, ov)
    print()
    check_summary(cur, uid, plan, ov)

    out = 'profile-reconcile-{}.json'.format(args.phase)
    with io.open(os.path.join(HERE, out), 'w', encoding='utf-8') as fh:
        json.dump({'checks': CHECKS, 'fails': FAILS, 'user': args.user, 'phase': args.phase,
                   'overview': ov, 'plan': 'plan-{}.json'.format(args.tag)}, fh,
                  ensure_ascii=False, indent=1)
    print()
    print('对拍完成：{} 条断言 · 失败 {} 条 → {}'.format(len(CHECKS), len(FAILS), out))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())