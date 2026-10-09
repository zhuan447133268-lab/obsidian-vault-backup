#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S7 验收主脚本（小队：组队/单人队 · 成员互见成绩 · 互相提醒 · 小队宝箱）。

两相：
  pre   验收①②③的接口侧主体——建队/加入/单人队/宝箱条件/提醒落库/阈值边界/护栏，
        与「手算 × SQL 独立聚合 × 接口回执」三方对拍；
  post  补打把小队经验推过 2000 之后：宝箱解锁、弱标记翻转、提醒不变式仍然成立。

对拍口径（和 S6.5 一样，期望值**不 import 生产代码**）：
  · 手算：team-seed.py 的 plan-*.json（每一步计划答了什么、服务端结算回执是多少）；
  · SQL ：自己重写一份周一分桶 + 聚合（attempts/attempt_answers/xp_ledger/reminders）；
  · 接口：/api/team/overview 的回执必须与上面两方逐项一致。
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'

# PRD v2.0 §6 + 原型 team.html 的数值口径：验收里独立写死，不从 server/internal/quiz/team.go import
BONUS_RATE = 0.1
CHEST_XP = 2000
WEAK_ACC = 0.7
DEFAULT_MSG = '这周一起冲两关？小队宝箱就差你了 💪'
TEAM_NAME = '加油鸭'
TEAM_EMOJI = '🦆'
TMP_TEAM = '摆摊队'
STUDENTS = ('S7A', 'S7B', 'S7C', 'S7D', 'S7E')
PASSWORD = 'S7demo2026'
INIT_USER, INIT_PWD = 'S65C', 'S65Cinit'   # 首登未改密的学生（S6.5 留档）→ 验 40302 门禁
TEACHER_INIT_USER, TEACHER_INIT_PWD = 'T0001', 'Teacher@123'

CHECKS = []
FAILS = []


def _norm(v):
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
    print('[REC] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


def section(title):
    print()
    print('---------- {} ----------'.format(title))


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


def ov(token):
    code, body = api('GET', '/api/team/overview', token)
    if code != 200:
        raise SystemExit('取小队总览失败（{}）：{}'.format(code, body))
    return body['data']


# ---------------------------------------------------------------- 独立复算（周一分桶 + 聚合）

def week_start(now=None):
    now = now or datetime.now()
    d = now - timedelta(days=now.weekday())
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def sql_week_xp(cur, uid, ws):
    cur.execute('SELECT COALESCE(SUM(delta),0) FROM xp_ledger WHERE user_id=%s AND created_at>=%s', (uid, ws))
    return int(cur.fetchone()[0])


def sql_week_stats(cur, uid, ws):
    cur.execute("SELECT COUNT(*) FROM attempts WHERE user_id=%s AND status='finished' AND finished_at>=%s",
                (uid, ws))
    clears = int(cur.fetchone()[0])
    cur.execute('SELECT COUNT(*), COALESCE(SUM(aa.is_correct),0) FROM attempt_answers aa'
                ' JOIN attempts a ON a.id=aa.attempt_id WHERE a.user_id=%s AND aa.created_at>=%s', (uid, ws))
    answers, correct = cur.fetchone()
    return clears, int(answers), int(correct)


def sql_xp_total(cur, uid):
    cur.execute('SELECT COALESCE(SUM(delta),0) FROM xp_ledger WHERE user_id=%s', (uid,))
    return int(cur.fetchone()[0])


def sql_reminder_count(cur, frm, to, ws):
    cur.execute('SELECT COUNT(*) FROM reminders WHERE from_user=%s AND to_user=%s AND created_at>=%s',
                (frm, to, ws))
    return int(cur.fetchone()[0])


def sql_reminder_rows(cur, frm, to):
    cur.execute('SELECT id, team_id, msg, read_at FROM reminders WHERE from_user=%s AND to_user=%s'
                ' ORDER BY id', (frm, to))
    return cur.fetchall()


def round10(raw):
    """组队加成：×10% 四舍五入（0.5 的加成不该被抹成 0）。独立复算，不调服务端。"""
    return int(float(raw) * BONUS_RATE + 0.5)


def progress_of(xp):
    if xp <= 0:
        return 0
    if xp >= CHEST_XP:
        return 100
    p = xp * 100 // CHEST_XP
    return p + 1 if xp * 100 % CHEST_XP else p


def remain_of(xp):
    if xp >= CHEST_XP:
        return 0
    return CHEST_XP if xp <= 0 else CHEST_XP - xp


def acc_of(correct, answers):
    return 0.0 if answers == 0 else round(correct / answers, 2)


def hand_stats(*plans):
    """手算：把若干份 plan 里某学生的每关结算回执加起来（clear=finished 的关数）。"""
    out = {}
    for p in plans:
        if not p:
            continue
        for user, rec in p['students'].items():
            cell = out.setdefault(user, {'clears': 0, 'answers': 0, 'correct': 0, 'levels': 0})
            for lv in rec['levels']:
                cell['levels'] += 1
                if lv['status'] == 'finished':
                    cell['clears'] += 1
                cell['answers'] += lv['total']
                cell['correct'] += lv['correct']
    return out


def load_plan(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with io.open(path, encoding='utf-8') as fh:
        return json.load(fh)


# ---------------------------------------------------------------- 成员卡逐项核对

def check_member(cur, user, m, ws):
    """一名队员的卡片必须等于 SQL 独立聚合。"""
    uid = m['userId']
    clears, answers, correct = sql_week_stats(cur, uid, ws)
    xp = sql_week_xp(cur, uid, ws)
    check('{}（{}）成员卡本周 XP = 账本 SUM(delta)'.format(m['realName'], user), xp, m['xp'])
    check('{} 成员卡通关关数 = SQL 计 finished'.format(user), clears, m['clears'])
    check('{} 成员卡作答数 = SQL 计 attempt_answers'.format(user), answers, m['answers'])
    check('{} 成员卡答对数 = SQL 计 is_correct=1'.format(user), correct, m['correct'])
    check('{} 成员卡正确率 = 对/答（两位小数）'.format(user), acc_of(correct, answers), m['accuracy'])
    check('{} 需加油标记 = 正确率<70% 或 0 通关（原型 isWeak）'.format(user), True,
          m['weak'] == (m['accuracy'] < WEAK_ACC or m['clears'] < 1))
    return {'xp': xp, 'clears': clears, 'answers': answers, 'correct': correct}


def check_chest(view, members):
    """宝箱进度：阈值 2000、加成 10%（单人队 0）——全部独立复算。"""
    team, chest = view['team'], view['team']['chest']
    raw = sum(m['xp'] for m in members)
    bonus = 0 if team['solo'] else round10(raw)
    xp = raw + bonus
    check('宝箱 rawXp = 成员卡本周 XP 之和', raw, chest['rawXp'])
    check('宝箱加成 = 单人队 0 / 多人队 rawXp×10%（四舍五入）', bonus, chest['bonusXp'])
    check('宝箱小队经验 = rawXp + 加成', xp, chest['xp'])
    check('宝箱加成比例 = 单人队 0 / 多人队 0.1', 0 if team['solo'] else BONUS_RATE, chest['bonusRate'])
    check('宝箱阈值 = 2000（PRD §6）', CHEST_XP, chest['threshold'])
    check('宝箱进度百分比 = 向上取整', progress_of(xp), chest['progress'])
    check('宝箱还差多少 = 2000 − 小队经验（不为负）', remain_of(xp), chest['remain'])
    if team['solo']:
        check('单人队宝箱恒不解锁（原型 .solo：单人队没有小队宝箱）', False, chest['unlocked'])
    else:
        check('宝箱解锁 = 小队经验 ≥ 2000', xp >= CHEST_XP, chest['unlocked'])
    return raw, bonus, xp


# ---------------------------------------------------------------- pre 相

def phase_pre(args, cur, tokens, uid_of, plans):
    ws = week_start()
    check('本周一 00:00 分桶（起点）', week_start().strftime('%Y-%m-%d %H:%M:%S'), ws.strftime('%Y-%m-%d %H:%M:%S'))

    section('pre-1 手算 × SQL：作答/通关/正确率三方对齐')
    hand = hand_stats(*plans)
    for u in STUDENTS:
        clears, answers, correct = sql_week_stats(cur, uid_of[u], ws)
        h = hand.get(u, {'clears': 0, 'answers': 0, 'correct': 0})
        check('{} 手算通关 {} 关 = SQL {}'.format(u, h['clears'], clears), h['clears'], clears)
        check('{} 手算作答 {} 题 = SQL {}'.format(u, h['answers'], answers), h['answers'], answers)
        check('{} 手算答对 {} 题 = SQL {}'.format(u, h['correct'], correct), h['correct'], correct)

    section('pre-2 未入队与建队：队伍号即邀请码 + 单人队语义')
    v = ov(tokens['S7C'])
    check('S7C 未入队时 team = null', None, v['team'])
    code, body = api('POST', '/api/team/create', tokens['S7C'], {'name': TMP_TEAM, 'emoji': '🐼'})
    check('S7C 建队 HTTP 200 + code 0', '200/0', '{}/{}'.format(code, body.get('code')))
    tmp_id = body['data']['id']
    check('建完即单人队（memberCount=1 / solo=true / 我是队长）', (1, True, True),
          (body['data']['memberCount'], body['data']['solo'], body['data']['isLeader']))
    tmp_view = ov(tokens['S7C'])
    check('单人队：无加成比例（bonusRate=0）', 0, tmp_view['team']['chest']['bonusRate'])
    check('单人队：加成 XP 恒 0', 0, tmp_view['team']['chest']['bonusXp'])
    check('单人队：宝箱标记 solo=true', True, tmp_view['team']['chest']['solo'])
    check('单人队：rawXp = 自己本周账本（没作答 → 0）', 0, tmp_view['team']['chest']['rawXp'])
    check('S7C 单人队时宝箱未解锁', False, tmp_view['team']['chest']['unlocked'])
    check('S7C 自己看：候选小队里没有自己的队', [], [c['id'] for c in tmp_view['candidates'] if c['id'] == tmp_id])

    v = ov(tokens['S7A'])
    check('S7A 还没入队 → team = null', None, v['team'])
    cands = {c['id']: c for c in v['candidates']}
    check('未入队者能看到本班已有小队（{}）'.format(TMP_TEAM), True, tmp_id in cands)
    if tmp_id in cands:
        check('候选卡口径 = 队名/队徽/人数/队长/队伍号', (TMP_TEAM, '🐼', 1, 'S7演示学生C', tmp_id),
              (cands[tmp_id]['name'], cands[tmp_id]['emoji'], cands[tmp_id]['memberCount'],
               cands[tmp_id]['leaderName'], cands[tmp_id]['id']))
    check('别班（S7D）候选列表为空：跨班不互见小队', [], ov(tokens['S7D'])['candidates'])
    code, body = api('POST', '/api/team/join', tokens['S7D'], {'teamId': tmp_id})
    check('S7D 加入别班小队 → 404 不存在（不泄露别班队名）', (404, 40401), (code, body.get('code')))

    code, body = api('POST', '/api/team/leave', tokens['S7C'])
    check('单人队的队长可以退队（队伍随之解散）', (200, 0), (code, body.get('code')))
    check('S7C 退队后回到未入队', None, ov(tokens['S7C'])['team'])
    check('解散的队不再出现在候选列表', False, tmp_id in {c['id'] for c in ov(tokens['S7A'])['candidates']})
    code, body = api('POST', '/api/team/join', tokens['S7B'], {'teamId': tmp_id})
    check('加入已解散的队 → 404', (404, 40401), (code, body.get('code')))

    section('pre-3 单人队 → 收人 → 加成 10%：验收②（单人队无加成但 XP 照计）')
    code, body = api('POST', '/api/team/create', tokens['S7A'], {'name': TEAM_NAME, 'emoji': TEAM_EMOJI})
    check('S7A 建队 200', (200, 0), (code, body.get('code')))
    team_id = body['data']['id']
    solo_view = ov(tokens['S7A'])
    solo_raw = sql_week_xp(cur, uid_of['S7A'], ws)
    check('建完是单人队（solo=true / 1 人）', (True, 1), (solo_view['team']['solo'], solo_view['team']['memberCount']))
    check('单人队 rawXp = 账本净得（照常计 XP：{} > 0）'.format(solo_raw), solo_raw, solo_view['team']['chest']['rawXp'])
    check('单人队 rawXp > 0（确实有本周成绩，不是空转）', True, solo_raw > 0)
    check('单人队加成 = 0（XP 一分不改）', 0, solo_view['team']['chest']['bonusXp'])
    code, prof = api('GET', '/api/profile/overview', tokens['S7A'])
    check('个人档案页总 XP = 账本 SUM(delta)（队伍不参与个人 XP 计算）',
          sql_xp_total(cur, uid_of['S7A']), prof['data']['summary']['xpTotal'])
    code, body = api('POST', '/api/team/join', tokens['S7B'], {'teamId': team_id})
    check('S7B 用队伍号加入 200', (200, 0), (code, body.get('code')))
    two = ov(tokens['S7A'])
    check('两人队：solo=false / memberCount=2', (False, 2), (two['team']['solo'], two['team']['memberCount']))
    check('两人队：加成比例 = 0.1', BONUS_RATE, two['team']['chest']['bonusRate'])
    check('成员次序：队长在第一位', (uid_of['S7A'], True), (two['team']['members'][0]['userId'], two['team']['members'][0]['isLeader']))
    check('视图里的 isMe 只挂在自己身上', [uid_of['S7A']],
          [m['userId'] for m in two['team']['members'] if m['isMe']])
    code, body = api('POST', '/api/team/join', tokens['S7C'], {'teamId': team_id})
    check('S7C 用队伍号加入 200', (200, 0), (code, body.get('code')))
    view = ov(tokens['S7A'])
    check('三人队 memberCount=3', 3, view['team']['memberCount'])
    members = view['team']['members']
    check('队伍号 = 邀请码（S7A 拿到的 id 与实际入队的 id 一致）', team_id, view['team']['id'])

    section('pre-4 成员互见成绩：每人一张卡 = SQL 独立聚合')
    stats = {}
    for m in members:
        u = next(k for k, v in uid_of.items() if v == m['userId'])
        stats[u] = check_member(cur, u, m, ws)

    section('pre-5 本周小结 × 宝箱条件（阈值 2000 / 加成 10%）')
    wk = view['team']['week']
    tot = {'clears': sum(s['clears'] for s in stats.values()),
           'answers': sum(s['answers'] for s in stats.values()),
           'correct': sum(s['correct'] for s in stats.values())}
    check('本周总通关 = 各成员通关之和', tot['clears'], wk['clears'])
    check('本周作答 = 各成员之和', tot['answers'], wk['answers'])
    check('本周答对 = 各成员之和', tot['correct'], wk['correct'])
    check('小队平均正确率 = 全员合计正确率（不是各人正确率的平均）', acc_of(tot['correct'], tot['answers']),
          wk['accuracy'])
    check('周起点 = 本机独立算出的周一（YYYY-MM-DD）', ws.strftime('%Y-%m-%d'), wk['weekStart'])
    check('周标签 = M/D', '{}/{}'.format(ws.month, ws.day), wk['label'])
    raw, bonus, xp = check_chest(view, members)
    check('前置：此刻小队经验未满 2000（宝箱锁定态可断言）', True, xp < CHEST_XP)
    note('小队经验 = {}+{}={} / {}（进度 {}%）'.format(raw, bonus, xp, CHEST_XP, view['team']['chest']['progress']))

    section('pre-6 需加油阈值：与原型 isWeak 同口径（含 70% 边界）')
    by_user = {next(k for k, v in uid_of.items() if v == m['userId']): m for m in members}
    check('S7A 正确率正好 70%（边界值）', 0.7, by_user['S7A']['accuracy'])
    check('S7A 70% + 通关 2 关 → **不**算需加油（阈值是严格小于）', False, by_user['S7A']['weak'])
    check('S7B 60% → 算需加油（正确率低）', True, by_user['S7B']['weak'])
    check('S7C 0 通关 → 算需加油（即使正确率不是判定依据）', True, by_user['S7C']['weak'])
    check('S7C 正确率 0 且作答 0（「本周还没闯关」）', (0.0, 0), (by_user['S7C']['accuracy'], by_user['S7C']['answers']))
    check('面板「需要加油 N 人」= 挂徽标人数（原型静态文案与 JS 不一致，这里以 JS 口径为准）', 2, wk['weakCount'])
    check('队长视角可提醒人数 = 弱队员里排除队长与自己（2 人）', 2, wk['nudgeCount'])
    weak_view = ov(tokens['S7B'])
    check('队员视角可提醒人数 = 1（另一名弱队员；队长卡没有提醒按钮）', 1, weak_view['team']['week']['nudgeCount'])
    check('另一名队员（S7C）视角可提醒人数 = 1（队长 + 自己都排除）', 1,
          ov(tokens['S7C'])['team']['week']['nudgeCount'])

    section('pre-7 互相提醒：落库 / 幂等 / 只在自己队里')
    before = sql_reminder_count(cur, uid_of['S7B'], uid_of['S7C'], ws)
    code, body = api('POST', '/api/team/remind', tokens['S7B'], {'toUserId': uid_of['S7C']})
    check('队员提醒另一名队员 200（谁都能提醒）', (200, 0), (code, body.get('code')))
    rm = body['data']['reminder']
    check('默认话术 = 原型那句（服务端兜底）', DEFAULT_MSG, rm['msg'])
    check('提醒回执：发起人 / 收件人正确', (uid_of['S7B'], uid_of['S7C']), (rm['fromUser'], rm['toUser']))
    check('提醒回执：发起人姓名带上（提醒条要显示谁喊的）', 'S7演示学生B', rm['fromName'])
    check('队员发起 → fromLeader=false', False, rm['fromLeader'])
    check('提醒落库：reminders 多了一行', before + 1, sql_reminder_count(cur, uid_of['S7B'], uid_of['S7C'], ws))
    rows = sql_reminder_rows(cur, uid_of['S7B'], uid_of['S7C'])
    check('落库内容 = 回执（msg 一致、read_at 未读）', (DEFAULT_MSG, None), (rows[-1][2], rows[-1][3]))
    code, body2 = api('POST', '/api/team/remind', tokens['S7B'], {'toUserId': uid_of['S7C'], 'msg': '这周还差两关'})
    check('本周重复提醒同一个人 → alreadySent=true（幂等）', True, body2['data']['alreadySent'])
    check('重复提醒不再新增行', before + 1, sql_reminder_count(cur, uid_of['S7B'], uid_of['S7C'], ws))
    check('重复提醒返回同一行、话术仍是最初那条', (rm['id'], DEFAULT_MSG),
          (body2['data']['reminder']['id'], body2['data']['reminder']['msg']))
    code, body = api('POST', '/api/team/remind', tokens['S7B'], {'toUserId': uid_of['S7B']})
    check('自己提醒自己 → 400', (400, 40001), (code, body.get('code')))
    code, body = api('POST', '/api/team/remind', tokens['S7B'], {'toUserId': uid_of['S7D']})
    check('提醒别班同学（非队友）→ 404', (404, 40401), (code, body.get('code')))

    section('pre-8 收得到：未读提醒条 + 已提醒态 + 已读回执')
    c_view = ov(tokens['S7C'])
    check('S7C 收到 1 条未读提醒', 1, c_view['unreadCount'])
    check('提醒条内容 = 发送人姓名 + 话术', ('S7演示学生B', DEFAULT_MSG),
          (c_view['received'][0]['fromName'], c_view['received'][0]['msg']))
    check('队员发起 → 提醒条不带队长标记', False, c_view['received'][0]['fromLeader'])
    b_view = ov(tokens['S7B'])
    check('S7B 视角：S7C 那张卡已经是「已提醒」态（原型按钮文案的服务端依据）', True,
          next(m['reminded'] for m in b_view['team']['members'] if m['userId'] == uid_of['S7C']))
    check('S7B 视角：对队长没有「已提醒」态可挂（队长卡没有按钮）', False,
          next(m['reminded'] for m in b_view['team']['members'] if m['userId'] == uid_of['S7A']))
    rid = c_view['received'][0]['id']
    code, body = api('POST', '/api/team/reminders/ack', tokens['S7B'], {'ids': [rid]})
    check('别人的提醒标不了已读（发起人也不行）→ acked=0', (200, 0), (code, body['data']['acked']))
    code, body = api('POST', '/api/team/reminders/ack', tokens['S7C'], {'ids': [rid]})
    check('收件人标已读 → acked=1', (200, 1), (code, body['data']['acked']))
    check('已读后未读清零', 0, ov(tokens['S7C'])['unreadCount'])
    check('已读落库（read_at 非空）', True, sql_reminder_rows(cur, uid_of['S7B'], uid_of['S7C'])[-1][3] is not None)
    code, body = api('POST', '/api/team/reminders/ack', tokens['S7C'], {'ids': [rid]})
    check('重复标已读 → acked=0（幂等）', (200, 0), (code, body['data']['acked']))

    section('pre-9 一键提醒：队长专属（本项目在浏览器阶段实点，这里先验护栏）')
    code, body = api('POST', '/api/team/remind-all', tokens['S7B'])
    check('非队长一键提醒 → 403 无权', (403, 40301), (code, body.get('code')))
    check('被拒后没有任何新提醒落库', before + 1, sql_reminder_count(cur, uid_of['S7B'], uid_of['S7C'], ws))
    code, body = api('POST', '/api/team/remind-all', tokens['S7D'])
    check('没入队的人一键提醒 → 409（没有小队可提醒）', (409, 40901), (code, body.get('code')))

    section('pre-10 退队语义：队员随时能退、队长只能独自退（留痕不删行）')
    code, body = api('POST', '/api/team/leave', tokens['S7A'])
    check('队长还有队友时退队 → 409 冲突（一期不做队长移交）', (409, 40901), (code, body.get('code')))
    code, body = api('POST', '/api/team/leave', tokens['S7C'])
    check('队员退队 → 200', (200, 0), (code, body.get('code')))
    check('退队后回到未入队态', None, ov(tokens['S7C'])['team'])
    check('退队留痕：team_members 行还在，left_at 非空（不物理删）', 1,
          sql_count(cur, 'SELECT COUNT(*) FROM team_members tm JOIN users u ON u.id=tm.user_id'
                         ' WHERE u.username=%s AND tm.team_id=%s AND tm.left_at IS NOT NULL',
                    ('S7C', team_id)))
    check('退队后队伍人数回到 2', 2, ov(tokens['S7A'])['team']['memberCount'])
    code, body = api('POST', '/api/team/join', tokens['S7C'], {'teamId': team_id})
    check('退队后还能再入队（队伍号仍有效）', (200, 0), (code, body.get('code')))
    back = ov(tokens['S7A'])
    check('重新入队后人数回到 3', 3, back['team']['memberCount'])
    check('本周新入队 → 原型「新入队」标记（joined_at 落在本周）', True,
          next(m['newJoin'] for m in back['team']['members'] if m['userId'] == uid_of['S7C']))

    section('pre-11 护栏：未登录 / 首登未改密 / 重复建队 / 参数')
    code, body = api('GET', '/api/team/overview')
    check('未登录 → 401', 401, code)
    t = login(INIT_USER, INIT_PWD)
    code, body = api('GET', '/api/team/overview', t)
    check('首登未改密 → 403 + 40302（Ready 门禁）', (403, 40302), (code, body.get('code')))
    code, body = api('POST', '/api/team/create', tokens['S7A'], {'name': '再来一队', 'emoji': '🐹'})
    check('已在队里再建队 → 409', (409, 40901), (code, body.get('code')))
    code, body = api('POST', '/api/team/create', tokens['S7D'], {'name': '   ', 'emoji': '🐹'})
    check('队名全空白 → 400', (400, 40001), (code, body.get('code')))
    code, body = api('POST', '/api/team/join', tokens['S7D'], {'teamId': 999999})
    check('加入不存在的队伍 → 404', (404, 40401), (code, body.get('code')))
    code, body = api('POST', '/api/team/join', tokens['S7B'], {'teamId': team_id})
    check('已在队里再入队 → 409', (409, 40901), (code, body.get('code')))
    code, body = api('POST', '/api/team/join', tokens['S7D'], {})
    check('不传队伍号 → 400', (400, 40001), (code, body.get('code')))
    code, body = api('POST', '/api/team/remind', tokens['S7A'], {})
    check('不传提醒对象 → 400', (400, 40001), (code, body.get('code')))
    code, body = api('GET', '/api/team/overview', tokens['S7D'])
    check('没入队的学生也能打开小队页（team=null，不是报错）', (200, None), (code, body['data']['team']))

    section('pre-12 SQL 不变式（提醒与成员关系的形状）')
    n_dup = sql_count(cur, 'SELECT COUNT(*) FROM (SELECT from_user, to_user FROM reminders'
                           ' WHERE created_at>=%s GROUP BY from_user, to_user HAVING COUNT(*)>1) x', (ws,))
    check('同一对 (发起人,收件人) 本周最多 1 行提醒（幂等的库层面证据）', 0, n_dup)
    n_cross = sql_count(cur, 'SELECT COUNT(*) FROM reminders r WHERE r.team_id<>0 AND NOT EXISTS'
                             ' (SELECT 1 FROM team_members a JOIN team_members b ON a.team_id=b.team_id'
                             '  WHERE a.user_id=r.from_user AND b.user_id=r.to_user)', ())
    check('提醒双方必须同队（跨队提醒一行都不许有）', 0, n_cross)
    n_active = sql_count(cur, "SELECT COUNT(*) FROM (SELECT user_id FROM team_members WHERE left_at IS NULL"
                              " GROUP BY user_id HAVING COUNT(*)>1) y", ())
    check('一个人同时只能在一个活跃小队（无并行重复成员行）', 0, n_active)


def sql_count(cur, sql, params=()):
    cur.execute(sql, params)
    return int(cur.fetchone()[0])


# ---------------------------------------------------------------- post 相

def phase_post(args, cur, tokens, uid_of, plans):
    ws = week_start()
    section('post-1 宝箱跨过 2000：解锁态 + 进度满格')
    view = ov(tokens['S7A'])
    if view['team'] is None:
        raise SystemExit('post：S7A 不在队里（pre 是否没跑完）')
    members = view['team']['members']
    check('补打后队伍仍是 3 人', 3, view['team']['memberCount'])
    raw, bonus, xp = check_chest(view, members)
    check('补打后小队经验 ≥ 2000（跨过阈值）', True, xp >= CHEST_XP)
    check('补打后宝箱解锁（多人队）', True, view['team']['chest']['unlocked'])
    check('解锁后进度 = 100%', 100, view['team']['chest']['progress'])
    check('解锁后「还差」= 0', 0, view['team']['chest']['remain'])

    section('post-2 手算 × SQL 再对拍一次（数据变了，口径不能变）')
    hand = hand_stats(*plans)
    for u in STUDENTS[:3]:
        clears, answers, correct = sql_week_stats(cur, uid_of[u], ws)
        h = hand[u]
        check('{} 补打后手算通关 = SQL'.format(u), (h['clears'], h['answers'], h['correct']),
              (clears, answers, correct))
    stats = {}
    for m in members:
        u = next(k for k, v in uid_of.items() if v == m['userId'])
        stats[u] = check_member(cur, u, m, ws)

    section('post-3 弱标记翻转：全员达标 → 需要加油 0 人')
    wk = view['team']['week']
    check('补打后「需要加油 N 人」= 0（三人都 ≥1 通关且 ≥70%）', 0, wk['weakCount'])
    check('队长视角可提醒人数 = 0', 0, wk['nudgeCount'])
    check('没有人再挂 ⚠ 需加油', [], [m['realName'] for m in members if m['weak']])
    check('S7C 从「0 通关」变成达标（本周通关 ≥1）', True,
          next(m['clears'] for m in members if m['userId'] == uid_of['S7C']) >= 1)

    section('post-4 提醒不变式（浏览器里点的那些也要在库里）')
    n_dup = sql_count(cur, 'SELECT COUNT(*) FROM (SELECT from_user, to_user FROM reminders'
                           ' WHERE created_at>=%s GROUP BY from_user, to_user HAVING COUNT(*)>1) x', (ws,))
    check('同一对本周仍最多 1 行（浏览器点过一键提醒后依然幂等）', 0, n_dup)
    a_from = sql_count(cur, 'SELECT COUNT(*) FROM reminders WHERE from_user=%s AND created_at>=%s',
                       (uid_of['S7A'], ws))
    check('队长本周发过提醒（浏览器阶段点出来的行）', True, a_from >= 1)
    b_view = ov(tokens['S7B'])
    check('S7B 收到的提醒标了队长发起（来自浏览器的「一键提醒」）', True,
          all(r['fromLeader'] for r in b_view['received']) if b_view['received'] else
          sql_count(cur, 'SELECT COUNT(*) FROM reminders WHERE from_user=%s AND to_user=%s',
                    (uid_of['S7A'], uid_of['S7B'])) >= 1)

    section('post-5 单人队（S7E 在浏览器里建的）：XP 照计、加成 0、无宝箱')
    e = ov(tokens['S7E'])
    check('S7E 在浏览器里建成了自己的队', True, e['team'] is not None)
    if e['team']:
        check('S7E 的队是单人队（1 人 / solo）', (True, 1), (e['team']['solo'], e['team']['memberCount']))
        check('S7E 单人队：加成比例 0 / 加成 XP 0 / 宝箱 solo 且未解锁', (0, 0, True, False),
              (e['team']['chest']['bonusRate'], e['team']['chest']['bonusXp'],
               e['team']['chest']['solo'], e['team']['chest']['unlocked']))
        e_xp = sql_week_xp(cur, uid_of['S7E'], ws)
        check('S7E 单人队 rawXp = 账本净得（XP 照计）', e_xp, e['team']['chest']['rawXp'])
        check('S7E 单人队 rawXp > 0（本周真打过 5/5 的一关）', True, e_xp > 0)
        code, prof = api('GET', '/api/profile/overview', tokens['S7E'])
        check('S7E 个人总 XP = 账本 SUM(delta)（组队不改个人账本）',
              sql_xp_total(cur, uid_of['S7E']), prof['data']['summary']['xpTotal'])
        check('S7E 单人队不产生任何提醒（没人可提醒）', 0,
              sql_count(cur, 'SELECT COUNT(*) FROM reminders WHERE from_user=%s OR to_user=%s',
                        (uid_of['S7E'], uid_of['S7E'])))

    section('post-6 跨班隔离（S7D 在 2 班）：看不到、也进不了 1 班的队')
    d = ov(tokens['S7D'])
    check('S7D 始终没有加入任何小队（跨班加入被 404 拦住）', None, d['team'])
    a_team = ov(tokens['S7A'])['team']['id']
    check('S7D 候选列表里没有 1 班的队（跨班不互见）', [], [c['id'] for c in d['candidates']])
    code, body = api('POST', '/api/team/join', tokens['S7D'], {'teamId': a_team})
    check('S7D 直接拿队伍号也进不去 1 班的队 → 404', (404, 40401), (code, body.get('code')))


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=('pre', 'post'), required=True)
    args = ap.parse_args()

    conn = db_conn()
    cur = conn.cursor()
    tokens, uid_of = {}, {}
    for u in STUDENTS:
        tokens[u] = login(u, PASSWORD)
        cur.execute('SELECT id FROM users WHERE username=%s', (u,))
        uid_of[u] = int(cur.fetchone()[0])
    note('演示学生：' + ' / '.join('{}={}'.format(u, uid_of[u]) for u in STUDENTS))

    plans = [load_plan('plan-seed.json')] if args.phase == 'pre' else \
        [load_plan('plan-seed.json'), load_plan('plan-topup.json')]
    check('手算底稿已就位（plan-*.json）', True, all(p is not None for p in plans))

    if args.phase == 'pre':
        phase_pre(args, cur, tokens, uid_of, plans)
    else:
        phase_post(args, cur, tokens, uid_of, plans)

    with io.open(os.path.join(HERE, 'team-reconcile-{}.json'.format(args.phase)), 'w', encoding='utf-8') as fh:
        json.dump({'phase': args.phase, 'checks': CHECKS, 'fails': FAILS, 'weekStart': ws_str()},
                  fh, ensure_ascii=False, indent=1)
    print()
    print('{} 相：{} 条断言 · 失败 {} 条'.format(args.phase, len(CHECKS), len(FAILS)))
    return 1 if FAILS else 0


def ws_str():
    return week_start().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
    sys.exit(main())