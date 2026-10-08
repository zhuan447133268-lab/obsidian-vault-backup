#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S6.5 验收：真浏览器（390×844）打开档案页，逐项核对页面上画出来的数与接口回执一致，并留存截图。

四个模式：
  mastery  只走接口——把错题补回来（重刷计划里那几关并答对），断言 wrong_book 的 mastered 语义
           （答对只置 mastered，不改 last_at）与「专题结束推送」的熄灭；
  full     真浏览器——登录 S65A → /s/me：六边形/曲线/错题本/提醒条/红点逐个与接口回执对齐 + 截图；
  empty    真浏览器——新学生（S65B）空态：六维全「暂无数据」、错题本空态、曲线空态、无红点；
  auth     只走接口——未登录 401、首登未改密 40302、同学之间数据互不串。

页面断言的原则：页面上必须**真的画出**接口下发的数（不是只看接口自洽）。
"""
import argparse
import io
import json
import os
import struct
import sys
import urllib.error
import urllib.request

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r'D:\claude-work\cet46-game'
BASE = 'http://127.0.0.1:8080'
VITE = 'http://127.0.0.1:5174'
SHOTS = os.path.join(HERE, 'shots')

CHECKS = []
FAILS = []
CONSOLE_ERRORS = []

# 题型中文名（页面自己的标签表：错题本题型徽标用它本地化）。独立写一份，不从 web 源码抄。
TYPE_ZH = {'vocab': '词汇', 'grammar': '语法', 'reading': '阅读', 'cloze': '选词填空',
           'match': '段落匹配', 'listening': '听力', 'translation': '翻译', 'writing': '写作'}


def _norm(v):
    """比较前归一：Go 的 float64(1) 序列化成 1，别让 1.0 / 1 的写法差异变成假失败；
    布尔转字符串——Python 里 True == 1，但「有红点」和「1 条」不是一回事。"""
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
    print('[E2E] {} {} 期望={} 实际={}'.format(desc, '✅' if ok else '❌', want, got))
    if not ok:
        FAILS.append(desc)


def note(msg):
    print('    · ' + msg)


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


def api_call(method, path, token=None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    headers = {'Content-Type': 'application/json; charset=utf-8'} if body is not None else {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8', 'replace'))
        except ValueError:
            return e.code, {}


def login(user, password):
    code, body = api_call('POST', '/api/auth/login', body={'username': user, 'password': password})
    if code != 200:
        raise SystemExit('登录失败 {}：{}'.format(user, body))
    return body['data']['token']


def write(name, extra=None):
    path = os.path.join(HERE, name)
    with io.open(path, 'w', encoding='utf-8') as fh:
        json.dump({'checks': CHECKS, 'fails': FAILS, 'consoleErrors': CONSOLE_ERRORS,
                   'extra': extra or {}}, fh, ensure_ascii=False, indent=1)
    return path


# ================================================================ mastery：补回错题

def mode_mastery(args, cur, token, uid):
    """重刷计划里那几关并全部答对：错题 → 已掌握；专题推送随之熄灭。"""
    import re

    def load_bank2(qids):
        fmt = ','.join(['%s'] * len(qids))
        cur.execute('SELECT id, answer_idx, options_json FROM questions WHERE id IN ({})'.format(fmt),
                    tuple(qids))
        return {int(q): {'answer_idx': a, 'options': json.loads(o or '[]')} for q, a, o in cur.fetchall()}

    def picks_of(q, meta):
        ans = [int(x) for x in re.split(r'[，,]', meta['answer_idx'].strip()) if x.strip()]
        if q['type'] == 'cloze':
            words = [w['text'] for w in q['cloze']['wordBank']]
            return [words.index(meta['options'][i]) for i in ans]
        if q['type'] == 'match':
            label = str(meta['options'][ans[0]]).strip().upper()
            return [p['idx'] for p in q['match']['paragraphs'] if p['label'].strip().upper() == label]
        return [q['options'].index(meta['options'][ans[0]])]

    cur.execute('SELECT question_id, wrong_count, last_at, mastered FROM wrong_book'
                ' WHERE user_id=%s ORDER BY question_id', (uid,))
    before = {int(q): {'wrongCount': int(w), 'lastAt': la, 'mastered': bool(m)}
              for q, w, la, m in cur.fetchall()}
    plan = json.load(io.open(os.path.join(HERE, 'plan-{}.json'.format(args.tag)), encoding='utf-8'))
    name_of = {l['levelId']: l['levelName'] for l in plan['levels']}
    replay_ids = list(plan['wrongLevelIds'])
    masteried = []
    replay_answers = []

    for lid in replay_ids:
        name = name_of[lid]
        code, body = api_call('GET', '/api/quiz/paper?level={}'.format(lid), token)
        if code != 200:
            raise SystemExit('取卷失败 {}：{}'.format(name, body))
        paper = body['data']
        meta = load_bank2([q['id'] for q in paper['questions']])
        answers = [{'questionId': q['id'], 'pickedIdx': ','.join(str(p) for p in picks_of(q, meta[q['id']])),
                    'elapsedMs': 3000} for q in paper['questions']]
        code, body = api_call('POST', '/api/quiz/submit', token,
                              {'attemptId': paper['attemptId'], 'answers': answers})
        if code != 200:
            raise SystemExit('重刷交卷失败 {}：{}'.format(name, body))
        data = body['data']
        fby = {f['questionId']: f for f in data['feedback']}
        learned = [f['questionId'] for f in data['feedback'] if f.get('learned')]
        masteried.extend(learned)
        wrong_again = [f['questionId'] for f in data['feedback'] if not f['isCorrect']]
        note('重刷「{}」：attempt={} 对 {}/{} 标为已掌握 {} 条 仍答错 {} 题'.format(
            name, data['attemptId'], data['settlement']['correct'], data['settlement']['total'],
            len(learned), len(wrong_again)))
        check('重刷「{}」全对（错题补回的前提）'.format(name), '[]', str(wrong_again))
        check('重刷「{}」回执标出 learned（答对且原本是错题）'.format(name), True, len(learned) >= 1)
        for q in paper['questions']:
            replay_answers.append({'questionId': q['id'], 'type': q['type'],
                                   'correct': bool(fby[q['id']]['isCorrect']),
                                   'plannedWrong': False, 'replay': name})

    check('补回的错题号 = 计划里 {} 道'.format(len(before)), sorted(before.keys()), sorted(masteried))
    cur.execute('SELECT question_id, wrong_count, last_at, mastered FROM wrong_book'
                ' WHERE user_id=%s ORDER BY question_id', (uid,))
    after = {int(q): {'wrongCount': int(w), 'lastAt': la, 'mastered': bool(m)}
             for q, w, la, m in cur.fetchall()}
    for qid in before:
        check('题 {} 补回后 mastered=1（wrong_book）'.format(qid), 1, int(after[qid]['mastered']))
        check('题 {} 错过次数不因答对清零（wrong_count 仍是历史次数）'.format(qid),
              before[qid]['wrongCount'], after[qid]['wrongCount'])
        check('题 {} 答对不刷新 last_at（S6 定：答对只置 mastered）'.format(qid),
              before[qid]['lastAt'].strftime('%Y-%m-%d %H:%M:%S'),
              after[qid]['lastAt'].strftime('%Y-%m-%d %H:%M:%S'))

    ov = api_call('GET', '/api/profile/overview', token)[1]['data']
    check('错题全部补回后 hasPending=false（提醒条熄灭）', False, ov['push']['hasPending'])
    check('推送单元列表清空', '[]', str(ov['push']['pendingUnits']))
    check('推送文案清空（没有待复盘就不说话）', '', ov['push']['message'])
    check('错题本：待复盘 0 / 已掌握 {}'.format(len(before)), (0, len(before)),
          (ov['wrongBook']['pendingCount'],
                                                ov['wrongBook']['masteredCount']))
    check('错题本仍留条（已掌握的题不删，学生看得到进步）', len(before),
          sum(len(g['items']) for g in ov['wrongBook']['groups']))
    check('概览四格「待复盘」同步归零', 0, ov['summary']['pendingWrong'])
    # 计划侧同步：这次重刷的作答也要进手算底稿（对拍脚本据此重算六维与曲线）
    plan['answers'].extend(replay_answers)
    plan.setdefault('replays', []).extend(replay_ids)
    with io.open(os.path.join(HERE, 'plan-{}.json'.format(args.tag)), 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=1)
    note('plan-{}.json 已追加 {} 条重刷作答（手算底稿跟上）'.format(args.tag, len(replay_answers)))
    write('e2e-profile-mastery.json', {'masteried': masteried, 'replays': replay_ids})
    return 0


# ================================================================ full：真浏览器全量核对

def open_student(page, user, password):
    page.goto(VITE + '/s/login', wait_until='domcontentloaded')
    page.wait_for_selector('input', timeout=20000)
    inputs = page.locator('input')
    inputs.nth(0).fill(user)
    inputs.nth(1).fill(password)
    page.locator('button').first.click()
    page.wait_for_url(lambda u: '/s/login' not in u, timeout=20000)


def goto_profile(page, expect_api=True):
    with page.expect_response(lambda r: '/api/profile/overview' in r.url and r.status == 200,
                              timeout=25000) as ri:
        page.goto(VITE + '/s/me', wait_until='domcontentloaded')
    return ri.value.json()['data']


def dom_snapshot(page):
    """把档案页上「画出来的字」抓下来（只读 DOM，不碰接口）。"""
    return page.evaluate("""() => {
      const txt = (el) => el ? el.innerText.replace(/\\s+/g, ' ').trim() : null;
      const cards = [...document.querySelectorAll('section.card, div.card')];
      const byHead = (head) => cards.find(c => (c.querySelector('.card-head b')||{}).innerText === head);
      const radarCard = cards.find(c => c.querySelector('.radar'));
      const bookCard = byHead('错题本');
      const trendCard = byHead('成长曲线');
      return {
        xpLabel: txt(document.querySelector('.xpbar .label')),
        pushbar: document.querySelector('.pushbar')
          ? {b: txt(document.querySelector('.pushbar b')), p: txt(document.querySelector('.pushbar p'))} : null,
        diag: document.querySelector('.card.diag') ? {
          level: txt(document.querySelector('.card.diag .level-tag')),
          sub: txt(document.querySelector('.card.diag .card-sub')) } : null,
        tiles: [...document.querySelectorAll('.tile')].map(t => ({
          v: txt(t.querySelector('.tile-value')), k: txt(t.querySelector('.tile-label')),
          h: txt(t.querySelector('.tile-hint')) })),
        hex: {
          level: txt(radarCard && radarCard.querySelector('.level-tag')),
          sub: txt(radarCard && radarCard.querySelector('.card-sub')),
          rows: [...(radarCard ? radarCard.querySelectorAll('.dims li') : [])].map(li => ({
            name: txt(li.querySelector('.dim-name')), num: txt(li.querySelector('.dim-num')),
            width: li.querySelector('.dim-track i').style.width })),
          pcts: radarCard ? [...radarCard.querySelectorAll('.axis-pct')].map(t => t.textContent.trim()) : [],
          labels: radarCard ? [...radarCard.querySelectorAll('.axis-label')].map(t => t.textContent.trim()) : [],
        },
        trend: {
          sub: txt(trendCard && trendCard.querySelector('.card-sub')),
          empty: txt(trendCard && trendCard.querySelector('.empty')),
          xLabels: trendCard ? (() => {
            const svgs = [...trendCard.querySelectorAll('svg')];
            const xp = svgs[svgs.length - 1];
            return [...xp.querySelectorAll('text')].map(t => t.textContent.trim());
          })() : [],
          bars: trendCard ? [...trendCard.querySelectorAll('rect.bar')].map(r => ({
            h: r.getAttribute('height'), cls: r.getAttribute('class') })) : [],
        },
        book: {
          tag: txt(bookCard && bookCard.querySelector('.level-tag, .done-tag')),
          sub: txt(bookCard && bookCard.querySelector('.card-sub')),
          empty: txt(bookCard && bookCard.querySelector('.empty')),
          groups: [...(bookCard ? bookCard.querySelectorAll('.group') : [])].map(g => ({
            name: txt(g.querySelector('.group-name')),
            chips: [...g.querySelectorAll('.group-head .chip')].map(c => txt(c)),
            sub: txt(g.querySelector('.group-sub')),
            items: [...g.querySelectorAll('.items li')].map(li => ({
              mastered: li.className.includes('mastered'),
              type: txt(li.querySelector('.chip.type')),
              state: txt(li.querySelector('.chip.warn, .chip.done')),
              when: txt(li.querySelector('.when')),
              stem: txt(li.querySelector('.stem')),
              tag: txt(li.querySelector('.tag')),
            })),
            more: txt(g.querySelector('.more')),
          })),
        },
        nav: {
          tabs: [...document.querySelectorAll('.navbar a')].map(a => ({
            text: txt(a), on: a.className.includes('on'),
            dot: !!a.querySelector('.dot') })),
        },
      };
    }""")


def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path)
    note('截图 {} {}'.format(name, png_size(path)))
    return name


def png_size(path):
    """直接从 PNG 头读真实尺寸（不依赖 PIL）。"""
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24])


def tag_cards(page):
    """按页面自己的卡头文字给四张卡打 data-ev 标记，供逐卡截图定位。

    为什么不用滚动 + 视口截图：档案页真正的滚动发生在内层 .wrap（overflow:auto），
    文档高度只有一屏。Playwright 的 scrollIntoViewIfNeeded 只看元素是否落在**视口矩形**内、
    不看内层容器的裁剪，于是「曲线/错题本/底栏」常常判定成「已经可见」→ 三张截图是同一帧。
    S6.5 首跑就踩了这个：4 张 full 截图字节完全一样，等于没有证据。改成元素级截图。
    """
    return page.evaluate("""() => {
      const cards = [...document.querySelectorAll('section.card, div.card')];
      const byHead = (h) => cards.find(c => (c.querySelector('.card-head b')||{}).innerText === h);
      const marks = {ability: cards.find(c => c.querySelector('.radar')),
                     trend: byHead('成长曲线'), wrongbook: byHead('错题本')};
      const out = {};
      for (const k in marks) { if (marks[k]) { marks[k].setAttribute('data-ev', k); out[k] = true; }
                               else { out[k] = false; } }
      return out; }""")


def shot_el(page, sel, name, shots, required=True):
    """元素级截图：Playwright 把元素滚进容器并把画面裁到元素边界（对错位滚动免疫）。"""
    loc = page.locator(sel).first
    if loc.count() == 0:
        note('跳过 {}：页面上没有 {}（空态/结构差异）'.format(name, sel))
        if required:
            check('截图 {} 的区块在页面上存在（选择器 {}）'.format(name, sel), True, False)
        return None
    loc.scroll_into_view_if_needed(timeout=8000)
    page.wait_for_timeout(250)
    path = os.path.join(SHOTS, name)
    loc.screenshot(path=path)
    w, h = png_size(path)
    note('截图 {}（元素级）{}'.format(name, (w, h)))
    check('截图 {} 尺寸合理（宽 ≤ 390 且不为空条）'.format(name), True,
          w <= 390 and h >= 40)
    shots.append(name)
    return name


def shot_full_page(page, name, shots):
    """整页截图：文档高度只有一屏，full_page=True 拍不到下面的内容——
    把视口临时撑到内层 .wrap 的内容高度再拍，拍完还原成 390×844。"""
    content_h = int(page.evaluate(
        "() => { const w = document.querySelector('.wrap');"
        " return w ? w.scrollHeight : document.documentElement.scrollHeight; }"))
    page.set_viewport_size({'width': 390, 'height': content_h + 120})
    page.wait_for_timeout(400)
    page.evaluate("() => { const w = document.querySelector('.wrap'); if (w) { w.scrollTop = 0; }"
                  " window.scrollTo(0, 0); }")
    page.wait_for_timeout(200)
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path)
    w, h = png_size(path)
    note('截图 {}（整页）{}'.format(name, (w, h)))
    check('整页截图 {} 宽 390（一屏宽的阅读面）'.format(name), 390, w)
    check('整页截图 {} 比一屏高（真的拍全了内容，不是只拍一屏）'.format(name), True, h > 844)
    shots.append(name)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(150)
    return name


def mode_full(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    api_ov = api_call('GET', '/api/profile/overview', token)[1]['data']

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))

        open_student(page, args.user, args.password)
        note('已登录 {} 并进入学生端'.format(args.user))
        page.wait_for_url(lambda u: '/s/' in u, timeout=20000)
        page.wait_for_selector('.navbar', timeout=20000)
        shot(page, 'shot-{}-map.png'.format(args.tag))

        ov = goto_profile(page)
        check('页面加载时真的请求了 /api/profile/overview 并 200', True, 'hexagon' in ov)
        page.wait_for_selector('.dims li', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)

        # --- 提醒条（专题结束推送的一期形态）---
        check('页面上出现提醒条（专题已结束 + 有未掌握错题）', True, dom['pushbar'] is not None)
        if dom['pushbar']:
            check('提醒条文案 = 接口 push.message', api_ov['push']['message'], dom['pushbar']['p'])
            check('提醒条标题是「该复盘了」', '📌 该复盘了', dom['pushbar']['b'])
        check('底部「我的」Tab 有红点（hasPending=true）', True,
              next(tab['dot'] for tab in dom['nav']['tabs'] if '我的' in tab['text']))
        check('底部导航四项且「我的」高亮', True,
              next(tab['on'] for tab in dom['nav']['tabs'] if '我的' in tab['text']))

        # --- XP 条与四格 ---
        check('XP 条写明总额与级内进度', True,
              all(x in dom['xpLabel'] for x in [str(api_ov['summary']['xpTotal']),
                                                '{}/{}'.format(api_ov['summary']['xpInLevel'],
                                                               api_ov['summary']['xpPerLevel'])]))
        want_tiles = [('{}'.format(api_ov['summary']['xpTotal']), '总 XP'),
                      ('{}/{}'.format(api_ov['summary']['unitsCleared'], api_ov['summary']['unitsTotal']), '已通关'),
                      ('{}'.format(api_ov['summary']['answersTotal']), '作答'),
                      ('{}%'.format(round(api_ov['summary']['accuracy'] * 100)), '正确率')]
        got_tiles = [(tile['v'], tile['k']) for tile in dom['tiles']]
        check('概览四格（数值+标题）= 接口 summary', want_tiles, got_tiles)

        # --- 六边形（验收①的页面侧）---
        check('六边形六根轴都有中文名', ['词汇', '语法', '阅读', '听力', '翻译', '写作'], dom['hex']['labels'])
        want_rows = [(d['label'], ('{}/{}'.format(d['correct'], d['total']) if d['total'] else '暂无数据'))
                     for d in api_ov['hexagon']['dims']]
        got_rows = [(r['name'], r['num']) for r in dom['hex']['rows']]
        check('六维明细（名称+对/总）= 接口 dims', want_rows, got_rows)
        check('已覆盖维度数写在副标题上', '已覆盖 {}/6 维'.format(api_ov['hexagon']['coverage']),
              dom['hex']['sub'].split('·')[1].strip())
        check('画像档次标签 = 接口 level', api_ov['hexagon']['level'], dom['hex']['level'])
        check('无数据维在雷达图上标「—」（不是 0%）', '—',
              dom['hex']['pcts'][[d['key'] for d in api_ov['hexagon']['dims']].index('writing')])
        for i, d in enumerate(api_ov['hexagon']['dims']):
            want = '—' if d['total'] == 0 else '{}%'.format(round(d['accuracy'] * 100))
            check('雷达轴「{}」百分比 = 接口正确率'.format(d['label']), want, dom['hex']['pcts'][i])
            want_w = 0 if d['total'] == 0 else round(min(1, max(0, d['accuracy'])) * 100)
            check('维度条「{}」宽度 = 正确率'.format(d['label']), '{}%'.format(want_w),
                  dom['hex']['rows'][i]['width'])

        # --- 成长曲线（验收③的页面侧）---
        weeks = api_ov['trend']['weeks']
        check('曲线横轴 8 个标签 = 接口 week.label', [w['label'] for w in weeks], dom['trend']['xLabels'])
        tot_ans = sum(w['answers'] for w in weeks)
        tot_cor = sum(w['correct'] for w in weeks)
        tot_xp = sum(w['xp'] for w in weeks)
        tot_att = sum(w['attempts'] for w in weeks)
        want_sub = '近 8 周：闯关 {} 次 · 作答 {} 题 · 正确率 {}% · 净得 {} XP'.format(
            tot_att, tot_ans, round(tot_cor / tot_ans * 100) if tot_ans else 0, tot_xp)
        check('曲线副标题（近 8 周汇总）= 接口每周数据求和', want_sub, dom['trend']['sub'])
        check('每周 XP 柱 8 根（含 0 值的周也画）', 8, len(dom['trend']['bars']))
        neg_weeks = [w['weekStart'] for w in weeks if w['xp'] < 0]
        check('有负值周时柱子用 neg 样式（失败撤销那一周要看得出来）', True,
              all('neg' in b['cls'] for i, b in enumerate(dom['trend']['bars'])
                  if weeks[i]['xp'] < 0) if neg_weeks else True)
        zero_cols = [i for i, w in enumerate(weeks) if w['xp'] == 0 and w['answers'] == 0]
        check('没有练习的周柱子高度为 0（画 0 而不是不画）', True,
              all(dom['trend']['bars'][i]['h'] == '0' for i in zero_cols) if zero_cols else True)

        # --- 错题本（验收②的页面侧）---
        groups = api_ov['wrongBook']['groups']
        check('错题本分组数 = 接口 groups', len(groups), len(dom['book']['groups']))
        check('错题本角标 = 待复盘题数', '{} 题待复盘'.format(api_ov['wrongBook']['pendingCount'])
              if api_ov['wrongBook']['pendingCount'] else '全部补回 ✓', dom['book']['tag'])
        for i, g in enumerate(groups):
            dg = dom['book']['groups'][i]
            check('组「{}」标题 = UNIT 周次 · 单元名'.format(g['unitName']),
                  'UNIT {} · {}'.format(g['weekNo'], g['unitName']), dg['name'])
            check('组「{}」状态 chip = {}'.format(g['unitName'],
                                                '本专题已结束' if g['unitCleared'] else '进行中'),
                  '本专题已结束' if g['unitCleared'] else '进行中', dg['chips'][0])
            check('组「{}」计数行 = 未掌握/已掌握'.format(g['unitName']),
                  '未掌握 {} · 已掌握 {}'.format(g['pendingCount'], g['masteredCount']), dg['sub'])
            preview = g['items'][:3]
            check('组「{}」默认只展开前 3 条（长专题不撑爆一屏）'.format(g['unitName']),
                  min(3, len(g['items'])), len(dg['items']))
            check('组「{}」展开按钮文案'.format(g['unitName']),
                  '展开全部 {} 条'.format(len(g['items'])) if len(g['items']) > 3 else None,
                  dg['more'])
            for j, it in enumerate(preview):
                di = dg['items'][j]
                check('组「{}」第 {} 条题型徽标 = 中文题型名（页面按自己的标签表本地化）'.format(
                        g['unitName'], j + 1), TYPE_ZH.get(it['type'], it['type']), di['type'])
                # 题干里可能有换行（词汇复盘类题面是多行的）：DOM innerText 必然把连续空白
                # 折叠成一个空格，比之前两边都折叠一次，否则是拿渲染差异当缺陷。
                check('组「{}」第 {} 条题干摘要 = 接口 stem'.format(g['unitName'], j + 1),
                      ' '.join(it['stem'].split()), di['stem'])
                check('组「{}」第 {} 条出错日期 = lastAt 前 10 位'.format(g['unitName'], j + 1),
                      it['lastAt'][:10], di['when'])
                if it['knowledgeTag']:
                    check('组「{}」第 {} 条考点行'.format(g['unitName'], j + 1),
                          '考点：' + it['knowledgeTag'], di['tag'])
                if it['mastered']:
                    check('组「{}」第 {} 条显示「已掌握 ✓」'.format(g['unitName'], j + 1),
                          '已掌握 ✓', di['state'])
                else:
                    check('组「{}」第 {} 条显示「错 N 次」'.format(g['unitName'], j + 1),
                          '错 {} 次'.format(it['wrongCount']), di['state'])

        # --- 截图（首屏视口 / 逐卡元素级 / 错题本展开态 / 底栏红点 / 真整页）---
        marks = tag_cards(page)
        check('四张卡都按用途定位到了（能力画像 / 成长曲线 / 错题本）', True,
              all(marks[k] for k in ('ability', 'trend', 'wrongbook')))
        page.evaluate("() => { const w = document.querySelector('.wrap'); if (w) { w.scrollTop = 0; }"
                      " window.scrollTo(0, 0); }")
        page.wait_for_timeout(250)
        shots = [shot(page, 'shot-{}-top.png'.format(args.tag))]
        for name, sel in [('ability', '[data-ev=ability]'), ('trend', '[data-ev=trend]'),
                          ('wrongbook', '[data-ev=wrongbook]'), ('navbar', '.navbar')]:
            shot_el(page, sel, 'shot-{}-{}.png'.format(args.tag, name), shots)
        # 展开全部错题再看一眼（4 条错题时这个按钮才会出现）
        more = page.locator('.group .more').first
        if more.count():
            more.click()
            page.wait_for_timeout(300)
            shot_el(page, '[data-ev=wrongbook]',
                    'shot-{}-wrongbook-expanded.png'.format(args.tag), shots)
            expanded = dom_snapshot(page)
            check('点「展开全部」后条目数变为全部', len(groups[0]['items']),
                  len(expanded['book']['groups'][0]['items']))
            check('展开后按钮变「收起」', '收起', expanded['book']['groups'][0]['more'])
        else:
            check('错题 ≤3 条时不出现「展开全部」按钮（页面上确实没有）', True,
                  len(groups[0]['items']) <= 3)
        shot_full_page(page, 'shot-{}-page.png'.format(args.tag), shots)

        check('浏览器控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()

    print()
    print('真机核对完成：{} 条断言 · 失败 {} 条'.format(len(CHECKS), len(FAILS)))
    write('e2e-profile-{}.json'.format(args.tag), {'shots': shots, 'user': args.user})
    return 1 if FAILS else 0


# ================================================================ empty / auth

def mode_empty(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    api_ov = api_call('GET', '/api/profile/overview', token)[1]['data']
    check('新学生：六维覆盖 0 维', 0, api_ov['hexagon']['coverage'])
    check('新学生：作答 0 题 / 正确率 0', (0, 0.0), (api_ov['summary']['answersTotal'],
                                                  api_ov['summary']['accuracy']))
    check('新学生：错题本为空', (0, 0), (api_ov['wrongBook']['pendingCount'],
                                       api_ov['wrongBook']['masteredCount']))
    check('新学生：无提醒（没东西可复盘）', False, api_ov['push']['hasPending'])
    check('新学生：无诊断卡（没做过诊断不占位）', None, api_ov['latestDiag'])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))
        open_student(page, args.user, args.password)
        goto_profile(page)
        page.wait_for_selector('.dims li', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)

        check('空态：没有提醒条', None, dom['pushbar'])
        check('空态：没有诊断卡', None, dom['diag'])
        check('空态：六维全「暂无数据」', ['暂无数据'] * 6, [r['num'] for r in dom['hex']['rows']])
        check('空态：雷达图百分比全「—」', ['—'] * 6, dom['hex']['pcts'])
        check('空态：画像档次留空（没有数据就不打分）', None, dom['hex']['level'])
        check('空态：错题本文案', True, (dom['book']['empty'] or '').startswith('还没有错题'))
        check('空态：曲线空态文案（引导去打第一关）', True, '去地图打一关' in (dom['trend']['empty'] or ''))
        check('空态：曲线仍是 8 个时间轴点（缺周不缺轴）', 8, len(dom['trend']['xLabels']))
        check('空态：底部「我的」Tab 无红点', False,
              next(tab['dot'] for tab in dom['nav']['tabs'] if '我的' in tab['text']))
        check('空态：顶栏仍是 LV.1', True, 'LV.1' in (page.locator('.username').inner_text() or ''))

        marks = tag_cards(page)
        check('空态下四张卡也都在（空态是卡内文案，不是把卡删掉）', True,
              all(marks[k] for k in ('ability', 'trend', 'wrongbook')))
        page.evaluate("() => { const w = document.querySelector('.wrap'); if (w) { w.scrollTop = 0; }"
                      " window.scrollTo(0, 0); }")
        page.wait_for_timeout(250)
        shots = [shot(page, 'shot-{}-top.png'.format(args.tag))]
        for name, sel in [('ability', '[data-ev=ability]'), ('trend', '[data-ev=trend]'),
                          ('wrongbook', '[data-ev=wrongbook]'), ('navbar', '.navbar')]:
            shot_el(page, sel, 'shot-{}-{}.png'.format(args.tag, name), shots)
        shot_full_page(page, 'shot-{}-page.png'.format(args.tag), shots)
        check('空态：控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()
    write('e2e-profile-{}.json'.format(args.tag), {'shots': shots, 'user': args.user})
    return 1 if FAILS else 0


def mode_auth(args):
    code, body = api_call('GET', '/api/profile/overview')
    check('未登录访问档案接口 → 401 + 40101', (401, 40101), (code, body.get('code')))
    # 首登未改密（seed-teacher / admin 建的账号 must_change_pwd=1）→ 40302
    if args.init_user:
        t = login(args.init_user, args.init_password)
        code, body = api_call('GET', '/api/profile/overview', t)
        check('首登未改密的学生访问档案接口 → 403 + 40302（改密门禁对学生业务接口一致）',
              (403, 40302), (code, body.get('code')))
    code, body = api_call('GET', '/api/profile/overview', login(args.user, args.password))
    check('已改密的学生访问档案接口 → 200', 200, code)
    # 同学隔离：拿别人的 token 看不到我的数据；接口也不收 user_id 入参
    t_a = login(args.user, args.password)
    t_b = login(args.peer, args.peer_password)
    ov_a = api_call('GET', '/api/profile/overview', t_a)[1]['data']
    ov_b = api_call('GET', '/api/profile/overview', t_b)[1]['data']
    check('同一接口、两个学生拿到各自的档案（A 有作答）', True, ov_a['summary']['answersTotal'] > 0)
    check('同学 B 看到的不是 A 的数据（B 作答 0）', 0, ov_b['summary']['answersTotal'])
    check('同学 B 的错题本为空（隔离）', 0, sum(len(g['items']) for g in ov_b['wrongBook']['groups']))
    code, body = api_call('GET', '/api/profile/overview?user_id=1', t_b)
    check('接口不收 user_id 入参（加参数也只能看自己）', 0,
          body['data']['summary']['answersTotal'])
    # 现状记录（不是 S6.5 的验收项，如实记一笔挂账）：取卷接口不校验解锁状态，
    # 跳关约束目前只在地图页 UI 上——学生绕过前端直接请求就能拿到未解锁关的卷。
    levels = api_call('GET', '/api/quiz/levels', t_b)[1]['data']['items']
    locked = [l for l in levels if not l['unlocked']]
    check('零进度学生的地图：24 关里只有每个单元第 1 关解锁', 4, len([l for l in levels if l['unlocked']]))
    code, body = api_call('GET', '/api/quiz/paper?level={}'.format(locked[0]['id']), t_b)
    note('观察：S65B（零进度）取未解锁关 L{} 的卷 → HTTP {} code={}（服务端不校验解锁，'
         '地图侧约束；已记入交卷报告「观察与债务」）'.format(locked[0]['id'], code, body.get('code')))
    # 取卷被放行会留下一张 in_progress attempt：探完就清掉，别让这个观察动作污染空态学生的档案
    conn = db_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM attempts WHERE user_id=(SELECT id FROM users WHERE username=%s)'
                ' AND level_id=%s AND status=%s', (args.peer, locked[0]['id'], 'in_progress'))
    conn.close()
    write('e2e-profile-{}.json'.format(args.tag), {'mode': 'auth'})
    return 1 if FAILS else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=True, choices=['mastery', 'full', 'empty', 'auth'])
    ap.add_argument('--user', default='S65A')
    ap.add_argument('--password', default='S65demo2026')
    ap.add_argument('--peer', default='S65B')
    ap.add_argument('--peer-password', default='S65demo2026')
    ap.add_argument('--init-user', default='S65C')
    ap.add_argument('--init-password', default='S65Cinit')
    ap.add_argument('--tag', default='s65')
    args = ap.parse_args()

    if args.mode == 'mastery':
        cur = db_conn().cursor()
        token = login(args.user, args.password)
        cur.execute('SELECT id FROM users WHERE username=%s', (args.user,))
        return mode_mastery(args, cur, token, int(cur.fetchone()[0]))
    if args.mode == 'full':
        return mode_full(args)
    if args.mode == 'empty':
        return mode_empty(args)
    return mode_auth(args)


if __name__ == '__main__':
    sys.exit(main())