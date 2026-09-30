#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6 验收 · 学生端答题页「一镜到底」（真实环境：Go :8080 + Vite :5174 + MySQL :3307）。

答案为什么是「反算」的：卷面选项按 (shuffleSeed, questionID) 用 Go 的 math/rand 洗过序，
Python 复刻不了这个排列。所以脚本先从浏览器抓 /api/quiz/paper 的响应（学生真正拿到的卷面），
再到 MySQL 读题库坐标的正确答案（questions.options_json + answer_idx），
按**选项文本**把正确答案换算成展示坐标，然后点它——判分完全交给服务端。

脚本自身记录（写进 e2e-<tag>.json，供 run-acceptance.sh 对账）：
  · 每个关卡：卷面 questionIds / attemptId / 每题的提交与判分回执 / 结算 settlement
  · DOM 实测值：爱心文案、连击文案、反馈条文案、结算星级与 XP 明细三列文本
  · 断言结果：卷面展示序 == DOM 渲染序（证明洗序下发与前端渲染一致）、
    反馈条答对答错都带解析、爱心随扣、连击文案与回执 streak 一致、结算明细 == 服务端明细

用法（一般由 run-acceptance.sh 调）：
  python e2e-quiz.py --user S6V6A --password S6demo2026 --tag chain --levels 25,26,27,28,29,30
  python e2e-quiz.py --user S6V6B --password S6demo2026 --tag wrong --levels 25 --answer wrong
  python e2e-quiz.py --user S6V6C --password S6demo2026 --tag target6 --levels 25 --switch-target 6
  python e2e-quiz.py --user S6V6A --password S6demo2026 --tag realpaper --levels 34,37
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request

import pymysql
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:5174'
VIEW = {'width': 390, 'height': 844}  # 验收③的截图口径：390px 宽（iPhone 12/13/14）

FAILS = []
CHECKS = []


def check(desc, want, got):
    ok = str(want) == str(got)
    CHECKS.append({'desc': desc, 'want': str(want), 'got': str(got), 'ok': ok})
    print('[CHECK] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


# 混合路：第 1 题故意错，第 2/3 题答对（先真的挣到分），第 4/5 题再错到爱心扣完——
# 这样失败时账本里既有已入账的答题分，也有「本次得分作废」的冲回行（净 0），
# 才真正验到数值表那条「爱心扣完 → 已入账答题分当场作废」。
MIXED_WRONG = {0, 3, 4}


def answer_mode(args):
    """mixed 在断点续答时按卷面序号判断对错，所以统一走 answer_mode() 而不是直接读 args。"""
    return args.answer


def note(*a):
    print(*a)


# ---------------------------------------------------------------- MySQL（判分基准）

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


def load_meta(conn, qids):
    """题库坐标的原始题面：band / answer_idx / options_json。"""
    ph = ','.join(['%s'] * len(qids))
    out = {}
    with conn.cursor() as cur:
        cur.execute('SELECT id, type, band, answer_idx, options_json FROM questions WHERE id IN (' + ph + ')',
                    list(qids))
        for qid, qtype, band, aidx, oj in cur.fetchall():
            out[int(qid)] = {'type': qtype, 'band': str(band), 'answer_idx': aidx,
                             'options': json.loads(oj or '[]')}
    return out


def bank_answer_idx(meta):
    """题库 answer_idx 是字符串，多空形态用逗号（半角/全角都可能）分隔。"""
    return [int(x) for x in re.split(r'[，,]', (meta['answer_idx'] or '').strip()) if x.strip() != '']


def correct_picks(q, meta):
    """把正确答案从题库坐标换算成卷面展示坐标（= 前端提交的 pickedIdx）。"""
    m = meta[q['id']]
    idxs = bank_answer_idx(m)
    if not idxs:
        raise AssertionError('题 {} 没有 answer_idx'.format(q['id']))
    if q['type'] == 'cloze':
        bank = m['options']
        words = [w['text'] for w in q['cloze']['wordBank']]
        picks = []
        for i in idxs:
            word = bank[i]
            if bank.count(word) != 1:
                raise AssertionError('题 {} 词表里「{}」出现多次，按文本定位不可靠'.format(q['id'], word))
            picks.append(words.index(word))
        return picks
    if q['type'] == 'match':
        label = str(m['options'][idxs[0]]).strip().upper()
        hit = [p for p in q['match']['paragraphs'] if str(p['label']).strip().upper() == label]
        if len(hit) != 1:
            raise AssertionError('题 {} 段表里找不到标号 {}（找到 {} 个）'.format(q['id'], label, len(hit)))
        return [hit[0]['idx']]
    bank = m['options']
    word = bank[idxs[0]]
    if bank.count(word) != 1:
        raise AssertionError('题 {} 题库选项文本重复（{}），按文本定位不可靠'.format(q['id'], word))
    disp = q['options']
    if disp.count(word) != 1:
        raise AssertionError('题 {} 卷面选项文本重复（{}）'.format(q['id'], word))
    return [disp.index(word)]


def attempt_answer_count(conn, attempt_id):
    """库里这条 attempt 已落库的作答行数（脚本外的写入会让它和脚本计数对不上）。"""
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM attempt_answers WHERE attempt_id=%s', (attempt_id,))
        return int(cur.fetchone()[0])


def paper_display_texts(q):
    """卷面**展示序**的选项文本（选词填空=词表，段落匹配=段落正文，其余=选项）。"""
    if q['type'] == 'cloze':
        return [w['text'] for w in q['cloze']['wordBank']]
    if q['type'] == 'match':
        paras = sorted(q['match']['paragraphs'], key=lambda p: p['idx'])
        return [p['text'] for p in paras]
    return list(q['options'])


# ---------------------------------------------------------------- HTTP（拿 levels 元数据）

def api_get(path, token):
    req = urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


# ---------------------------------------------------------------- 浏览器侧小工具

def norm(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\u00a0', ' ')).strip()


def sign(n):
    return ('+' if n > 0 else '') + str(n)


def dom_options(page):
    """选项区 DOM 的 (标号, 文本) 列表——顺序即展示下标。"""
    return page.eval_on_selector_all(
        '.optzone .opt',
        "els => els.map(e => ({key: e.querySelector('.key').textContent.trim(),"
        " text: e.querySelector('.wtext').textContent.replace(/\\s+/g,' ').trim()}))")


def path_in(shot_dir, name):
    return os.path.join(shot_dir, name)


def shot(page, shot_dir, name):
    path = path_in(shot_dir, name)
    page.screenshot(path=path)
    note('    · 截图 {}'.format(name))
    return os.path.basename(path)


# ---------------------------------------------------------------- 一关的答题流程

def enter_from_map(page, level):
    """从地图点关卡卡片进入（解锁链由前端把关，这里不绕接口）。"""
    unit = level.get('unitName') or ''
    name = level['name']
    unit_box = page.locator('.unit').filter(has_text=unit).first
    node = unit_box.locator('.node').filter(has_text=name).first
    if node.count() == 0:
        raise AssertionError('地图上找不到关卡卡片：单元「{}」关卡「{}」'.format(unit, name))
    node.scroll_into_view_if_needed()
    node.click()
    page.wait_for_selector('.pvcard', timeout=15000)


def run_level(page, conn, level, args, log, shots):
    """进关 → 逐题作答 → 结算。返回本关记录。"""
    rec = {'levelId': level['id'], 'levelName': level['name'], 'isBoss': bool(level.get('isBoss')),
           'questionCount': level['questionCount'], 'estimatedMinutes': level.get('estimatedMinutes'),
           'shots': []}

    # --- 进关预告（本关 X 题 / 约 X 分钟）---
    pv = norm(page.locator('.pvcard').inner_text())
    log('  [进关预告] ' + pv)
    check('L{} 进关预告写明「本关 X 题」'.format(level['id']), True,
          '本关 {} 题'.format(level['questionCount']) in pv)
    check('L{} 进关预告写明「约 X 分钟」'.format(level['id']), True,
          '约 {} 分钟'.format(level.get('estimatedMinutes')) in pv)
    rec['previewText'] = pv
    rec['shots'].append(shot(page, shots, 'shot-{}-L{}-preview.png'.format(args.tag, level['id'])))
    if args.expect_replay:
        check('L{} 重刷进关预告写明「重刷模式」'.format(level['id']), True, '重刷模式' in pv)

    # --- 取卷：抓浏览器真正拿到的卷面 ---
    with page.expect_response(lambda r: '/api/quiz/paper' in r.url and r.status == 200, timeout=20000) as ri:
        page.locator('.pvcard .act').click()
    paper = ri.value.json()['data']
    rec['attemptId'] = paper['attemptId']
    rec['resumed'] = paper['resumed']
    rec['shuffleSeed'] = paper['shuffleSeed']
    rec['questionIds'] = [q['id'] for q in paper['questions']]
    rec['livesOnPaper'] = paper['lives']
    check('L{} 卷面题数 == 进关预告题数'.format(level['id']), level['questionCount'], len(paper['questions']))
    check('L{} 卷面不下发答案/解析/原文'.format(level['id']), True,
          all(('tip' not in q and 'exp' not in q and 'script' not in q) for q in paper['questions']))

    meta = load_meta(conn, rec['questionIds'])
    rec['bands'] = sorted({meta[q]['band'] for q in rec['questionIds']})
    log('  [卷面] attempt={} seed={} 题数={} band={} 首题={} {}'.format(
        paper['attemptId'], paper['shuffleSeed'], len(paper['questions']), rec['bands'],
        rec['questionIds'][0], meta[rec['questionIds'][0]]['type']))

    page.wait_for_selector('.optzone .opt', timeout=15000)
    # 题面图别把上一屏的 toast 拍进去（「已切换到英语四级」会挡在选项上）
    if page.locator('.van-toast').count():
        try:
            page.locator('.van-toast').wait_for(state='hidden', timeout=4000)
        except Exception:
            pass
    rec['shots'].append(shot(page, shots, 'shot-{}-L{}-question.png'.format(args.tag, level['id'])))
    rec['submits'] = []
    n = len(paper['questions'])

    # 断点续答：前端会跳到第一道没作答的题，脚本必须跟着跳，否则会「以为在答第 1 题、
    # 实际在答第 2 题」。顺带把库里的作答行数与卷面 answered 对齐（防止有脚本外的写入）。
    answered_ids = [a['questionId'] for a in paper.get('answered', [])]
    start = next((i for i, q in enumerate(paper['questions']) if q['id'] not in set(answered_ids)), 0)
    rec['startIdx'] = start
    rec['answeredBefore'] = answered_ids
    db_rows_before = attempt_answer_count(conn, paper['attemptId'])
    check('L{} 库里作答行数 == 卷面 answered 数（无脚本外写入）'.format(level['id']),
          len(answered_ids), db_rows_before)
    if start > 0:
        log('  [断点续答] 前 {} 题已作答，从第 {} 题接着答'.format(start, start + 1))

    for i, q in enumerate(paper['questions'][start:], start=start):
        # 定位：先读 DOM 选项，断言渲染序 == 卷面展示序（洗序下发 → 前端渲染一致）
        dom = dom_options(page)
        want_texts = paper_display_texts(q)
        if q['type'] == 'match':
            # 段落匹配：DOM 的 .opt 是段表，标号按展示位 A/B/C…，文本按展示坐标对齐段表
            for p in q['match']['paragraphs']:
                if norm(dom[p['idx']]['key']) != str(p['label']).strip().upper():
                    raise AssertionError('题 {} 展示坐标 {} 的 DOM 标号是 {}，段表标号是 {}'.format(
                        q['id'], p['idx'], dom[p['idx']]['key'], p['label']))
        else:
            got = [norm(o['text']) for o in dom]
            if got != [norm(t) for t in want_texts]:
                raise AssertionError('题 {} DOM 选项序与卷面展示序不一致\nDOM={}\n卷面={}'.format(q['id'], got, want_texts))
        picks = correct_picks(q, meta)
        if answer_mode(args) == 'wrong' or (answer_mode(args) == 'mixed' and i in MIXED_WRONG):
            wrong = (picks[0] + 1) % len(dom)   # 错路：挑一个非正确项（相邻展示位）
            if wrong == picks[0]:
                raise AssertionError('选项只有 1 项，无法答错')
            picks = [wrong]
        if len(picks) != 1:
            raise AssertionError('当前脚本只驱动单击提交的题（本题需 {} 空）'.format(len(picks)))

        hearts_before = norm(page.locator('.heart').inner_text())
        with page.expect_response(lambda r: '/api/quiz/submit' in r.url, timeout=20000) as ri2:
            page.locator('.optzone .opt').nth(picks[0]).click()
        submit_data = ri2.value.json()['data']
        fb = submit_data['feedback'][0]
        page.wait_for_selector('.feedback.show', timeout=10000)
        time.sleep(0.15)

        # 反馈条：答对答错都展示 💡 解析
        fb_box = page.locator('.feedback')
        fb_text = norm(fb_box.inner_text())
        klass = 'fbok' if fb['isCorrect'] else 'fbno'
        check('L{} 第{}题 反馈条样式与判分一致（{}）'.format(level['id'], i + 1, klass),
              True, fb_box.locator('.' + klass).count() == 1)
        check('L{} 第{}题 反馈条带 💡 解析'.format(level['id'], i + 1), True, '💡' in fb_text)
        want_body = '💡 ' + (norm(fb['exp']) or norm(fb['tip']))
        check('L{} 第{}题 反馈条解析与服务端回执逐字一致'.format(level['id'], i + 1), True,
              want_body in fb_text)
        if fb['isCorrect']:
            check('L{} 第{}题 判分=答对'.format(level['id'], i + 1), True, fb['isCorrect'])
        else:
            letters = ' / '.join(chr(65 + int(x)) for x in str(fb['correctIdx']).split(','))
            check('L{} 第{}题 答错回执带正确项展示坐标 {}'.format(level['id'], i + 1, letters), True,
                  letters in fb_text)

        # 爱心：DOM 显示的剩余爱心 == 服务端回执；答对不减、答错扣 1
        hearts_after = norm(page.locator('.heart').inner_text())
        check('L{} 第{}题 爱心文案 == 服务端 livesLeft'.format(level['id'], i + 1),
              '❤️ {}'.format(fb['livesLeft']), hearts_after)
        if fb['isCorrect']:
            check('L{} 第{}题 答对不减心'.format(level['id'], i + 1), hearts_before, hearts_after)
        else:
            check('L{} 第{}题 答错扣一颗心（{} → {}）'.format(level['id'], i + 1, hearts_before, hearts_after),
                  int(hearts_before.split()[-1]) - 1, int(hearts_after.split()[-1]))

        # 连击：DOM 文案与服务端 streak 一致
        combo_txt = norm(page.locator('.combo').inner_text())
        if fb['streak'] >= 2:
            check('L{} 第{}题 连击文案（🔥 {} 连击）'.format(level['id'], i + 1, fb['streak']),
                  True, '🔥 {}'.format(fb['streak']) in combo_txt)
        else:
            check('L{} 第{}题 无连击文案'.format(level['id'], i + 1), True, combo_txt in ('', ''))

        rec['submits'].append({'no': i + 1, 'questionId': q['id'], 'pickedIdx': str(picks[0]),
                               'isCorrect': fb['isCorrect'], 'correctIdx': fb['correctIdx'],
                               'xp': fb['xp'], 'streak': fb['streak'], 'livesLeft': fb['livesLeft'],
                               'matched': fb['matched'], 'seqLen': fb['seqLen'],
                               'type': fb['type'], 'tip': fb['tip'], 'exp': fb['exp'],
                               'progress': submit_data['progress'], 'status': submit_data['status']})
        if submit_data.get('settlement'):
            rec['settlement'] = submit_data['settlement']
            rec['settleStatus'] = submit_data['status']

        if i == 0:
            rec['shots'].append(shot(page, shots, 'shot-{}-L{}-feedback-{}.png'.format(
                args.tag, level['id'], 'ok' if fb['isCorrect'] else 'no')))

        if answer_mode(args) != 'correct' and fb['livesLeft'] <= 0:
            log('  [爱心扣完] 第 {} 题答错后归零，点「继续」进失败结算'.format(i + 1))
            rec['failedAt'] = i + 1
            page.locator('.fbbtn').click()
            page.wait_for_selector('.overlay .result', timeout=15000)
            break

        page.locator('.fbbtn').click()
        page.wait_for_selector('.feedback.show', state='hidden', timeout=10000)

        # --- 断点续答实录（--resume-after N：答完第 N 题后刷新页面）---
        # 口径：刷新后回预告页 → 再点「开始答题」拿卷；服务端必须复用同一 in_progress attempt
        # （同一 attemptId / 同一 shuffleSeed / 同一题序），前端跳到第一道没作答的题，
        # 已作答的题既不能在卷面上重来、也不能在库里被重复写。
        if args.resume_after and not rec.get('resume') and (i + 1) == int(args.resume_after) and i + 1 < n:
            rows_before_reload = attempt_answer_count(conn, paper['attemptId'])
            with page.expect_response(
                    lambda r: '/api/quiz/paper' in r.url and r.status == 200, timeout=20000) as ri3:
                page.reload()
                page.wait_for_selector('.pvcard', timeout=15000)
                page.locator('.pvcard .act').click()
            p2 = ri3.value.json()['data']
            page.wait_for_selector('.optzone .opt', timeout=15000)
            rec['resume'] = {
                'attemptId': p2['attemptId'], 'resumed': p2['resumed'], 'shuffleSeed': p2['shuffleSeed'],
                'answered': len(p2['answered']), 'questionIds': [q['id'] for q in p2['questions']],
                'progress': norm(page.locator('.prog .nums').inner_text()),
                'toast': norm(page.locator('.van-toast').inner_text())
                if page.locator('.van-toast').count() else ''}
            rec['shots'].append(shot(page, shots, 'shot-{}-L{}-resume.png'.format(args.tag, level['id'])))
            check('L{} 断点续答：刷新后复用同一 attempt'.format(level['id']),
                  paper['attemptId'], p2['attemptId'])
            check('L{} 断点续答：卷面 resumed=True'.format(level['id']), True, p2['resumed'])
            check('L{} 断点续答：shuffleSeed 不变（同一套卷同一洗牌）'.format(level['id']),
                  paper['shuffleSeed'], p2['shuffleSeed'])
            check('L{} 断点续答：题目集合与顺序不变'.format(level['id']),
                  rec['questionIds'], rec['resume']['questionIds'])
            check('L{} 断点续答：卷面 answered == 已答 {} 题（不重复计）'.format(level['id'], i + 1),
                  i + 1, len(p2['answered']))
            check('L{} 断点续答：库里作答行数没被重复写'.format(level['id']),
                  rows_before_reload, attempt_answer_count(conn, paper['attemptId']))
            check('L{} 断点续答：DOM 落到第 {} 题'.format(level['id'], i + 2),
                  True, '第 {} '.format(i + 2) in rec['resume']['progress'])
            check('L{} 断点续答：toast 提示「接着上次答」'.format(level['id']),
                  True, '接着上次答' in rec['resume']['toast'])
            log('  [断点续答] 答完第 {} 题刷新页面 → attempt={} resumed={} 进度={} toast={}'.format(
                i + 1, p2['attemptId'], p2['resumed'], rec['resume']['progress'], rec['resume']['toast']))

    # --- 结算层（通关 / Boss 成绩单 / 失败）---
    page.wait_for_selector('.overlay .result', timeout=15000)
    time.sleep(0.2)
    rec['overlay'] = 'fail' if page.locator('.overlay .emoji').inner_text().strip() == '💫' else (
        'boss' if page.locator('.overlay .scorenum').count() else 'clear')
    rec['overlayText'] = norm(page.locator('.overlay .result').inner_text())
    rec['overlayStars'] = norm(page.locator('.overlay .bigstars').inner_text()) if \
        page.locator('.overlay .bigstars').count() else ''
    rec['overlayXpDetail'] = page.eval_on_selector_all(
        '.overlay .xpdetail span', "els => els.map(e => e.textContent.replace(/\\s+/g,' ').trim())")
    rec['overlayReview'] = page.eval_on_selector_all(
        '.overlay .qsrow', "els => els.map(e => e.textContent.replace(/\\s+/g,' ').trim())")
    rec['overlayScore710'] = norm(page.locator('.overlay .scorenum').inner_text()) if \
        page.locator('.overlay .scorenum').count() else ''
    rec['shots'].append(shot(page, shots, 'shot-{}-L{}-settlement-{}.png'.format(
        args.tag, level['id'], rec['overlay'])))
    log('  [结算] type={} stars={} 710={} 明细={}'.format(
        rec['overlay'], rec['overlayStars'], rec['overlayScore710'], rec['overlayXpDetail']))

    # 结算层 DOM 与服务端回执交叉核对（账本对账在 run-acceptance.sh 里做）
    rows_now = attempt_answer_count(conn, paper['attemptId'])
    check('L{} 通关后作答行数 == 卷面已答 + 本次脚本提交数'.format(level['id']),
          len(answered_ids) + len(rec['submits']), rows_now)
    st = rec.get('settlement')
    if not st:
        raise AssertionError('L{} 最后一题回执里没有 settlement（结算只在 attempt 走完时下发）'.format(level['id']))
    check('L{} 结算层类型 == 服务端回执推导'.format(level['id']),
          'fail' if rec.get('settleStatus') == 'failed' else ('boss' if st['isBoss'] else 'clear'),
          rec['overlay'])
    want_rows = ['{} {}'.format(r['label'], sign(r['delta'])) for r in st['xpRows']]
    if rec['overlay'] == 'fail':
        # 失败层 1:1 抄原型：只有一句「已作废」，既不列逐题回顾也不列 XP 明细三列
        # （明细仍在账本里，服务端照旧下发 settlement.xpRows，只是原型没有这一屏）。
        check('L{} 失败层不列逐题回顾（与原型 failOverlay 一致）'.format(level['id']), 0,
              len(rec['overlayReview']))
        check('L{} 失败层不列 XP 明细三列（与原型 failOverlay 一致）'.format(level['id']), [],
              rec['overlayXpDetail'])
        check('L{} 失败层写明本次得分已作废（净得 0）'.format(level['id']), True,
              '已作废' in rec['overlayText'] and st['xpTotal'] == 0)
    else:
        check('L{} 结算明细三列 == 服务端 xpRows（{}）'.format(level['id'], '/'.join(want_rows)),
              want_rows, rec['overlayXpDetail'])
        check('L{} 结算逐题回顾行数 == 服务端 review 行数'.format(level['id']),
              len(st['review']), len(rec['overlayReview']))
    if rec['overlay'] == 'clear':
        check('L{} 结算星级 == 服务端 stars'.format(level['id']),
              '★' * st['stars'] + '☆' * (3 - st['stars']), rec['overlayStars'])
    if rec['overlay'] == 'boss':
        check('L{} Boss 成绩单分数 == 服务端 score710'.format(level['id']), st['score710'],
              int(rec['overlayScore710']))
    if args.expect_replay:
        # 拍板必改项回归：重刷已通关关卡不再重复发通关/三星奖励（首通才发），答题分照发。
        check('L{} 重刷：回执 replay=True'.format(level['id']), True, st['replay'])
        check('L{} 重刷：回执 firstClear=False'.format(level['id']), False, st['firstClear'])
        bonus = [r for r in st['xpRows'] if ('通关' in r['label'] or '三星' in r['label']
                                            or '满分' in r['label'])]
        check('L{} 重刷：明细里没有通关/三星/满分奖励行'.format(level['id']), [], bonus)
        check('L{} 重刷：答题分照发（基础+速度两条都在）'.format(level['id']), True,
              any('基础' in r['label'] for r in st['xpRows'])
              and any('速度' in r['label'] for r in st['xpRows']))
    return rec


# ---------------------------------------------------------------- 场景

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--levels', default='')
    ap.add_argument('--answer', default='correct', choices=['correct', 'wrong', 'mixed'])
    ap.add_argument('--switch-target', default='')
    ap.add_argument('--skip-first-level', default='')  # 目标切换场景：先只切目标不进关
    ap.add_argument('--expect-replay', action='store_true')  # 重刷场景：断言奖励只在首通发
    ap.add_argument('--resume-after', type=int, default=0)  # 答完第 N 题刷新页面，验证断点续答
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--headless', default='1')
    args = ap.parse_args()

    shot_dir = os.path.join(args.out, 'shots')
    os.makedirs(shot_dir, exist_ok=True)
    logs = []

    def log(*a):
        line = ' '.join(str(x) for x in a)
        print(line)
        logs.append(line)

    conn = db_conn()
    result = {'tag': args.tag, 'user': args.user, 'answer': args.answer, 'levels': []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless == '1')
        # DPR=1：验收③要的是「390px 截图」，落盘就是 390×844 像素，跟原型截图同分辨率好并排
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=1)
        page = ctx.new_page()
        papers = []
        page.on('response', lambda r: papers.append(r) if '/api/quiz/paper' in r.url else None)

        # 1) 登录（首登强制改密的账号在 shell 侧先改密）
        log('== 登录 {} =='.format(args.user))
        page.goto(BASE + '/s/login')
        page.wait_for_selector('.van-field input', timeout=20000)
        fields = page.locator('.van-field input')
        fields.nth(0).fill(args.user)
        fields.nth(1).fill(args.password)
        page.locator('button:has-text("登 录")').click()
        page.wait_for_selector('.mapwrap', timeout=25000)

        # 首进必选目标（设备本地标记，S5 拍板）：本机第一次跑会弹
        if page.locator('.tgt-overlay').count() > 0:
            page.locator('.tgt-card.c4').click()
            page.wait_for_selector('.tgt-overlay', state='detached', timeout=15000)
            log('  · 首进必选：已选英语四级')
        page.wait_for_selector('.unit', timeout=20000)
        token = page.evaluate("localStorage.getItem('cet46_token')")
        levels = api_get('/api/quiz/levels', token)['data']['items']
        by_id = {it['id']: it for it in levels}
        result['targetBefore'] = norm(page.locator('.userinfo .sub').inner_text())
        log('  · 顶栏：' + result['targetBefore'])

        # 2) 目标切换（四级 → 六级）
        if args.switch_target:
            log('== 切换备考目标 → 六级 ==')
            result['shots'] = [shot(page, shot_dir, 'shot-{}-map-{}.png'.format(args.tag, 'band4'))]
            page.locator('.tgt-swap').click()
            page.wait_for_selector('.tgt-overlay', timeout=10000)
            with page.expect_response(lambda r: '/api/auth/target' in r.url, timeout=15000) as rt:
                page.locator('.tgt-card.c6').click()
            result['targetPatch'] = rt.value.json()['data']
            page.wait_for_selector('.tgt-overlay', state='detached', timeout=15000)
            time.sleep(0.8)
            result['targetAfter'] = norm(page.locator('.userinfo .sub').inner_text())
            check('顶栏目标已切到英语六级', True, '英语六级' in result['targetAfter'])
            levels = api_get('/api/quiz/levels', token)['data']['items']
            by_id = {it['id']: it for it in levels}
            result['shots'] = [shot(page, shot_dir, 'shot-{}-map-{}.png'.format(args.tag, 'band6'))]

        if args.skip_first_level:
            log('  · 目标切换场景：只验证切换后的卷面，不在切换前进关')
        else:
            result['shots'] = result.get('shots', [])
            ids = [int(x) for x in args.levels.split(',') if x.strip()]
            standing_at = None   # 已经站在哪一关的预告上（点了「下一关」就不用再回地图点）
            for pos, lid in enumerate(ids):
                lv = by_id.get(lid)
                if lv is None:
                    raise AssertionError('levels 接口里没有关卡 {}'.format(lid))
                log('== 关卡 {} {}（{} 题）=='.format(lid, lv['name'], lv['questionCount']))
                if standing_at != lid:
                    enter_from_map(page, lv)
                rec = run_level(page, conn, lv, args, log, shot_dir)
                result['levels'].append(rec)

                if args.answer == 'wrong':
                    break
                # 结算后走「下一关 →」继续（一镜到底，不回地图）
                if pos + 1 < len(ids):
                    nxt = ids[pos + 1]
                    btn = page.locator('.overlay .result .act')
                    check('L{} 结算页有「下一关」按钮'.format(lid), 'next', 'next' if btn.count() else 'missing')
                    btn.click()
                    page.wait_for_selector('.pvcard', timeout=15000)
                    land = by_id.get(nxt)
                    pv = norm(page.locator('.pvcard').inner_text())
                    check('下一关落到 L{} {}'.format(nxt, land['name']), True, land['name'].split(' · ')[-1] in pv)
                    standing_at = nxt

        # 3) 目标切换后的卷面（band 必须来自六级题库）
        if args.switch_target and args.levels:
            log('== 切到六级后进关取卷（L1 首题必须来自六级题库）==')
            lv = by_id[int(args.levels.split(',')[0])]
            enter_from_map(page, lv)
            with page.expect_response(lambda r: '/api/quiz/paper' in r.url and r.status == 200, timeout=20000) as ri:
                page.locator('.pvcard .act').click()
            paper = ri.value.json()['data']
            meta = load_meta(conn, [q['id'] for q in paper['questions']])
            result['target6Paper'] = {
                'levelId': lv['id'], 'attemptId': paper['attemptId'],
                'questionIds': [q['id'] for q in paper['questions']],
                'bands': sorted({meta[q['id']]['band'] for q in paper['questions']}),
                'firstQuestion': {
                    'id': paper['questions'][0]['id'], 'band': meta[paper['questions'][0]['id']]['band'],
                    'type': paper['questions'][0]['type'], 'stem': paper['questions'][0]['stem'][:80],
                    'domText': norm(page.locator('.qcard').inner_text())[:120],
                },
            }
            check('切到六级后卷面题数={}'.format(lv['questionCount']), lv['questionCount'],
                  len(paper['questions']))
            check('切到六级后卷面题目全部来自六级题库', ['6'],
                  result['target6Paper']['bands'])
            check('切到六级后第一题来自六级题库', '6', result['target6Paper']['firstQuestion']['band'])
            check('切到六级后第一题题干与卷面一致', True,
                  norm(paper['questions'][0]['stem'])[:40] in result['target6Paper']['firstQuestion']['domText'])
            result.setdefault('shots', []).append(shot(page, shot_dir,
                                                       'shot-{}-first-question-band6.png'.format(args.tag)))
            log('  [六级首题] id={} band={} type={}'.format(
                result['target6Paper']['firstQuestion']['id'],
                result['target6Paper']['firstQuestion']['band'],
                result['target6Paper']['firstQuestion']['type']))

        browser.close()

    conn.close()
    result['checks'] = CHECKS
    result['fails'] = FAILS
    result['log'] = logs
    with io.open(os.path.join(args.out, 'e2e-{}.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    print()
    print('== E2E {} 汇总：{} 条断言，失败 {} 条 =='.format(args.tag, len(CHECKS), len(FAILS)))
    for f in FAILS:
        print('   ❌ ' + f)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())