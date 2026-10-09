#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S7 验收：真浏览器（390×844）打开 /s/team，页面画出来的每一项都要等于接口回执，并留存截图。

四个模式（每个模式自己登录自己的学生）：
  full      队长 S7A：小队经验条 / 本周小结三格 / 成员卡（含 ⚠ 需加油、已提醒）/ 宝箱块 / 底栏红点，
            然后**真点**三处：邀请同学入队（toast 出队伍号）、提醒Ta（toast + 按钮变「已提醒 ⏰」）、
            一键提醒（toast + 变「✓ 已全部提醒」）——验收①的 E2E 侧；
  member    队员 S7B：收到队长提醒的站内到达点（页顶提醒条 + 底栏「小队」红点）→ 点「知道了」熄灭，
            刷新后仍是已读（服务端状态，不是本地藏起来）；队员看不到「一键提醒」；
  solo      别班 S7D：未入队态（建队卡 / 队伍号加入卡 / 别班候选为空）→ 真填名字点「建队」
            → 单人队态（无加成、无宝箱、XP 照计）；
  unlocked  队长 S7A（补打之后）：宝箱解锁态 + 弱标记全消后的页面样子。

页面断言的原则与 S6.5 一致：页面上必须**真的画出**接口下发的数，不是只看接口自洽。
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


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24])


def shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path)
    note('截图 {} {}'.format(name, png_size(path)))
    return name


def shot_el(page, sel, name, shots, required=True):
    loc = page.locator(sel).first
    if loc.count() == 0:
        note('跳过 {}：页面上没有 {}'.format(name, sel))
        if required:
            check('截图 {} 的区块在页面上存在（选择器 {}）'.format(name, sel), True, False)
        return None
    loc.scroll_into_view_if_needed(timeout=8000)
    page.wait_for_timeout(250)
    path = os.path.join(SHOTS, name)
    loc.screenshot(path=path)
    w, h = png_size(path)
    note('截图 {}（元素级）{}'.format(name, (w, h)))
    check('截图 {} 尺寸合理（宽 ≤ 390 且不为空条）'.format(name), True, w <= 390 and h >= 40)
    shots.append(name)
    return name


def shot_full_page(page, name, shots):
    """整页截图：小队页真正的滚动发生在内层 .content，文档高度只有一屏——
    把视口临时撑到 .content 的内容高度再拍（与 S6.5 档案页 .wrap 同一套办法）。"""
    content_h = int(page.evaluate(
        "() => { const c = document.querySelector('.content') || document.querySelector('.screen');"
        " return c ? c.scrollHeight : document.documentElement.scrollHeight; }"))
    page.set_viewport_size({'width': 390, 'height': content_h + 120})
    page.wait_for_timeout(400)
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) { c.scrollTop = 0; }"
                  " window.scrollTo(0, 0); }")
    page.wait_for_timeout(200)
    path = os.path.join(SHOTS, name)
    page.screenshot(path=path)
    w, h = png_size(path)
    note('截图 {}（整页）{} · 内层容器内容高 {}'.format(name, (w, h), content_h))
    check('整页截图 {} 宽 390'.format(name), 390, w)
    # 判据是「画面高度覆盖了内层容器的全部内容」：内容不足一屏时整页本来就矮于 844，
    # 硬比 844 会把正常页面判成失败；真正要抓的是「内层滚动容器没被拍全」（h 卡在一屏）。
    check('整页截图 {} 覆盖内层容器全部内容（内容 {} px）'.format(name, content_h), True,
          h >= content_h + 100)
    if content_h > 844:
        check('整页截图 {} 比一屏高（内容超一屏时确实拍全了）'.format(name), True, h > 844)
    shots.append(name)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.wait_for_timeout(150)
    return name


def open_student(page, user, password):
    page.goto(VITE + '/s/login', wait_until='domcontentloaded')
    page.wait_for_selector('input', timeout=20000)
    inputs = page.locator('input')
    inputs.nth(0).fill(user)
    inputs.nth(1).fill(password)
    page.locator('button').first.click()
    page.wait_for_url(lambda u: '/s/login' not in u, timeout=20000)


def goto_team(page, token):
    """进小队页，返回接口数据。

    「页面确实请求了 /api/team/overview」用响应**监听**取证（只看 url+status），
    不再用 expect_response().json() 去读响应体：那段响应体在导航时会被浏览器
    回收，读它偶发报 `Network.getResponseBody: No resource with given identifier`
    （07-browser-solo 首跑就是这么崩的，崩在取证动作上而不是页面缺陷上）。
    数据本身由脚本自己带 token 再取一次——页面证据（请求发生过 + DOM 画对了）与
    数据证据（接口回执）分开取，互不牵连。
    """
    seen = []

    def on_resp(r):
        if '/api/team/overview' in r.url:
            seen.append(r.status)

    page.on('response', on_resp)
    page.goto(VITE + '/s/team', wait_until='domcontentloaded')
    page.wait_for_selector('.navbar', timeout=25000)
    for _ in range(60):
        if seen:
            break
        page.wait_for_timeout(200)
    page.remove_listener('response', on_resp)
    check('页面加载时真的请求了 /api/team/overview 并 200', [200], seen[:1])
    return api_call('GET', '/api/team/overview', token)[1]['data']


def dom_snapshot(page):
    """把小队页上「画出来的字」抓下来（只读 DOM，不碰接口）。"""
    return page.evaluate("""() => {
      const txt = (el) => el ? el.innerText.replace(/\\s+/g, ' ').trim() : null;
      const head = document.querySelector('.head');
      const teamxp = document.querySelector('.teamxp');
      const toast = document.querySelector('.toast');
      return {
        headTitle: txt(head && head.querySelector('h2')),
        headSub: txt(head && head.querySelector('p')),
        badge: txt(head && head.querySelector('.team-badge')),
        teamxpLabel: txt(teamxp && teamxp.querySelector('.row span')),
        teamxpText: txt(teamxp && teamxp.querySelector('.row b')),
        tfill: (teamxp && teamxp.querySelector('.tfill')) ? teamxp.querySelector('.tfill').style.width : null,
        weeksum: [...document.querySelectorAll('.ws')].map(w => ({
          v: txt(w.querySelector('.v')), k: txt(w.querySelector('.k')) })),
        tipLine: txt(document.querySelector('.tip-line')),
        nudgeAll: txt(document.querySelector('.nudge-all')),
        members: [...document.querySelectorAll('.member')].map(m => ({
          cls: m.className,
          mini: txt(m.querySelector('.mini')),
          name: txt(m.querySelector('h4')),
          roles: [...m.querySelectorAll('.role')].map(r => txt(r)),
          stats: [...m.querySelectorAll('.stats span')].map(s => txt(s)),
          accLow: !!(m.querySelector('.stats .acc.low')),
          btn: txt(m.querySelector('.nudge')),
          btnDisabled: m.querySelector('.nudge') ? m.querySelector('.nudge').disabled : null })),
        solo: txt(document.querySelector('.solo')),
        invite: document.querySelector('.invite') ? {
          h4: txt(document.querySelector('.invite h4')), p: txt(document.querySelector('.invite p')),
          btn: txt(document.querySelector('.invite button')) } : null,
        quit: txt(document.querySelector('.quit')),
        pushbar: document.querySelector('.pushbar') ? {
          b: txt(document.querySelector('.pushbar b')), p: txt(document.querySelector('.pushbar p')),
          btn: txt(document.querySelector('.pushbar .ack')) } : null,
        navbar: [...document.querySelectorAll('.navbar a')].map(a => ({
          text: txt(a), on: a.className.includes('on'), dot: !!a.querySelector('.dot') })),
        toast: toast ? {show: toast.className.includes('show'), text: txt(toast.querySelector('p'))} : null,
        create: document.querySelector('.invite h4') && txt(document.querySelector('.invite h4')),
        joincard: document.querySelector('.joincard') ? {
          h4: txt(document.querySelector('.joincard h4')), btn: txt(document.querySelector('.joincard button')) } : null,
        cands: [...document.querySelectorAll('.cand')].map(c => ({
          name: txt(c.querySelector('.cand-name')), sub: txt(c.querySelector('.cand-sub')),
          btn: txt(c.querySelector('.nudge')) })),
      };
    }""")


# ---------------------------------------------------------------- full：队长视角

def mode_full(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    ov = api_call('GET', '/api/team/overview', token)[1]['data']
    if ov['team'] is None:
        raise SystemExit('{} 还没入队：先跑 04-reconcile-pre 建队'.format(args.user))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))

        open_student(page, args.user, args.password)
        note('已登录 {}'.format(args.user))
        page.wait_for_url(lambda u: '/s/' in u, timeout=20000)
        page.wait_for_selector('.navbar', timeout=20000)
        ov = goto_team(page, token)
        check('首屏接口确实回了队伍（队长视角）', True, ov['team'] is not None)
        page.wait_for_selector('.member', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)
        team = ov['team']

        # --- 头部与底栏 ---
        check('页头标题「🐹 我的小队」', '🐹 我的小队', dom['headTitle'])
        check('页头副标题 = 原型那句（小队经验全员加成 +10%）', '组队闯关 · 小队经验全员加成 +10%', dom['headSub'])
        check('队徽 = 队徽 emoji + 队名', '{} {}'.format(team['emoji'], team['name']), dom['badge'])
        tab = next(t for t in dom['navbar'] if '小队' in t['text'])
        check('底栏「小队」Tab 高亮（当前页）', True, tab['on'])
        check('底栏四个 Tab（闯关/联赛/小队/我的）', 4, len(dom['navbar']))
        check('底栏「小队」红点 = 未读提醒数 > 0（队长没收到提醒时不该有红点）',
              ov['unreadCount'] > 0, tab['dot'])

        # --- 小队经验条 ---
        check('经验条标题「小队本周经验」', '小队本周经验', dom['teamxpLabel'])
        want_text = '单人队 · 无小队加成与小队宝箱' if team['solo'] else (
            '🎁 小队宝箱已解锁' if team['chest']['unlocked'] else
            '{} / {} · 距小队宝箱还差 {}'.format(team['chest']['xp'], team['chest']['threshold'],
                                                team['chest']['remain']))
        check('经验条文案 = 接口下发的进度/阈值/还差', want_text, dom['teamxpText'])
        check('经验条填充宽度 = 接口进度百分比', '{}%'.format(team['chest']['progress']), dom['tfill'])

        # --- 本周小结三格 ---
        want_tiles = [('{}'.format(team['week']['clears']), '本周总通关'),
                      ('{}%'.format(round(team['week']['accuracy'] * 100)), '小队平均正确率'),
                      ('{} 人'.format(team['week']['weakCount']), '需要加油')]
        check('本周小结三格 = 接口 week', want_tiles, [(t['v'], t['k']) for t in dom['weeksum']])
        check('提示行 = 原型那句（成绩互相可见 · 互相提醒）', '👀 小队成绩互相可见 · 组内互相提醒，比老师点名好使',
              dom['tipLine'])

        # --- 一键提醒按钮（队长专属）---
        want_nudge = '✓ 已全部提醒' if (team['week']['nudgeCount'] == 0 and dom['nudgeAll']) else \
            '📣 一键提醒 {} 名需加油队员'.format(team['week']['nudgeCount'])
        if team['isLeader'] and team['week']['nudgeCount'] > 0:
            check('「一键提醒 N 名」按钮 = 接口 nudgeCount', want_nudge, dom['nudgeAll'])
        else:
            note('当前 nudgeCount={}：一键提醒按钮按原型规则不出现/已变灰'.format(team['week']['nudgeCount']))

        # --- 成员卡逐张 ---
        check('成员卡数量 = memberCount', team['memberCount'], len(dom['members']))
        for i, m in enumerate(team['members']):
            dm = dom['members'][i]
            check('第 {} 张卡是 {}（次序与接口一致）'.format(i + 1, m['realName']), True,
                  dm['name'].startswith(m['realName']))
            check('{}「队长」徽标 = isLeader'.format(m['realName']), m['isLeader'],
                  '队长' in dm['roles'])
            check('{}「⚠ 需加油」徽标 = weak（阈值服务端判）'.format(m['realName']), m['weak'],
                  '⚠ 需加油' in dm['roles'])
            check('{}「新入队」徽标 = newJoin'.format(m['realName']), m['newJoin'],
                  '新入队' in dm['roles'])
            check('{} 卡片底色用 weak 样式'.format(m['realName']),
                  'member weak' in dm['cls'] or (' weak' in dm['cls']), m['weak'])
            want_stats = ['本周 {} XP'.format(m['xp']), '通关 {} 关'.format(m['clears'])]
            check('{} 两个成绩项 = 接口 xp/clears'.format(m['realName']), want_stats, dm['stats'][:2])
            want_acc = '本周还没闯关' if m['answers'] == 0 else '正确率 {}%'.format(round(m['accuracy'] * 100))
            check('{} 正确率项 = 接口 accuracy'.format(m['realName']), want_acc, dm['stats'][2])
            check('{} 正确率标黄规则 = 没作答或 <70%'.format(m['realName']),
                  m['answers'] == 0 or m['accuracy'] < 0.7, dm['accLow'])
            check('{} 提醒按钮 = 非队长非本人（原型队长卡没有按钮）'.format(m['realName']),
                  not m['isLeader'] and not m['isMe'], dm['btn'] is not None)
            if m['reminded']:
                check('{} 已被我提醒过 → 按钮「已提醒 ⏰」且禁用'.format(m['realName']),
                      '已提醒 ⏰', dm['btn'])

        # --- 宝箱块 / 单人队块 ---
        check('宝箱块标题 = 进度百分比', '🎁 小队宝箱进度 {}%'.format(team['chest']['progress']), dom['invite']['h4'])
        check('宝箱块说明 = 阈值 + 奖励（免作业券已废弃，一期只承诺真题卷）',
              '小队经验满 {}，全员解锁「2022 年真题卷」'.format(team['chest']['threshold']), dom['invite']['p'])
        check('宝箱块按钮「邀请同学入队 +」', '邀请同学入队 +', dom['invite']['btn'])
        check('页尾有「退出小队」（原型没有；不加会变成只能进不能出）', '退出小队', dom['quit'])

        # --- 真点：邀请同学入队 → toast 出队伍号 ---
        page.locator('.invite button').first.click()
        page.wait_for_timeout(300)
        dom = dom_snapshot(page)
        check('点「邀请同学入队 +」后弹 toast', True, dom['toast']['show'])
        check('toast 文案 = 队伍号即邀请码', '把这句话发给同学就能入队 队伍号 {}，一起冲小队宝箱 💪'.format(team['id']),
              dom['toast']['text'].replace('「', '').replace('」', ''))
        shots = [shot(page, 'shot-{}-toast-invite.png'.format(args.tag))]

        # --- 真点：提醒Ta（队长点第一个可提醒的弱队员）---
        target = next((m for m in team['members'] if not m['isLeader'] and not m['isMe'] and not m['reminded']), None)
        if target is None:
            note('队长没有可点的提醒按钮（已全部提醒过）')
        else:
            idx = [m['userId'] for m in team['members']].index(target['userId'])
            cur = db_conn().cursor()
            cur.execute('SELECT COUNT(*) FROM reminders WHERE from_user=%s AND to_user=%s',
                        (team['members'][0]['userId'], target['userId']))
            before = int(cur.fetchone()[0])
            page.locator('.member .nudge').nth(len([m for m in team['members'][:idx + 1]
                                                   if not m['isLeader'] and not m['isMe']]) - 1).click()
            page.wait_for_timeout(400)
            dom = dom_snapshot(page)
            check('点「提醒Ta」后 toast 出「已由队长发出提醒」（队长发起才这么写）', True,
                  dom['toast']['text'].startswith('已由队长发出提醒'))
            check('toast 里带上被提醒人姓名', True, target['realName'] in dom['toast']['text'])
            want_msg = '这周一起冲两关？小队宝箱就差你了 💪'
            check('toast 里带默认话术（原型那句）', True, want_msg in dom['toast']['text'])
            check('被提醒的那张卡按钮变「已提醒 ⏰」并禁用'.format(target['realName']),
                  ('已提醒 ⏰', True),
                  (dom['members'][idx]['btn'], dom['members'][idx]['btnDisabled']))
            cur.execute('SELECT COUNT(*) FROM reminders WHERE from_user=%s AND to_user=%s',
                        (team['members'][0]['userId'], target['userId']))
            check('提醒落库：reminders 多了一行（点一次写一行）', before + 1, int(cur.fetchone()[0]))
            shots.append(shot(page, 'shot-{}-toast-remind.png'.format(args.tag)))
            after_view = api_call('GET', '/api/team/overview', token)[1]['data']
            check('「一键提醒 N 名」计数随点击减少（剩余可提醒 = 接口 nudgeCount）', True,
                  after_view['team']['week']['nudgeCount'] <= team['week']['nudgeCount'])

        # --- 真点：一键提醒（队长特权）---
        nudge_btn = page.locator('.nudge-all')
        if nudge_btn.count():
            nudge_btn.first.click()
            page.wait_for_timeout(500)
            dom = dom_snapshot(page)
            check('点「一键提醒」后按钮变「✓ 已全部提醒」', '✓ 已全部提醒', dom['nudgeAll'])
            check('一键提醒 toast 报出提醒了几人', True,
                  '名需加油队员' in (dom['toast']['text'] or '') or '已经提醒过' in (dom['toast']['text'] or ''))
            check('点完后所有非队长非本人卡都是「已提醒 ⏰」', True,
                  all(m['btn'] == '已提醒 ⏰' for i, m in enumerate(dom['members'])
                      if not team['members'][i]['isLeader'] and not team['members'][i]['isMe']))
            shots.append(shot(page, 'shot-{}-toast-nudgeall.png'.format(args.tag)))
            b_view = api_call('GET', '/api/team/overview', token)[1]['data']
            check('一键提醒后接口 nudgeCount = 0（本周提醒完了）', 0, b_view['team']['week']['nudgeCount'])
        else:
            check('队长 nudgeCount=0 时页面不出现「一键提醒」按钮（原型 hidden）', True, True)

        # --- 截图（首屏 / 各区块元素级 / 真整页）---
        page.wait_for_timeout(2400)   # 等 toast 自己收起（原型 2.2s），别把弹层拍进区块截图
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) { c.scrollTop = 0; }"
                      " window.scrollTo(0, 0); }")
        page.wait_for_timeout(250)
        shots.append(shot(page, 'shot-{}-top.png'.format(args.tag)))
        for name, sel in [('teamxp', '.teamxp'), ('weeksum', '.weeksum'), ('members', '.member'),
                          ('invite', '.invite'), ('navbar', '.navbar')]:
            shot_el(page, sel, 'shot-{}-{}.png'.format(args.tag, name), shots)
        shot_full_page(page, 'shot-{}-page.png'.format(args.tag), shots)

        check('浏览器控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()

    print()
    print('队长视角真机核对完成：{} 条断言 · 失败 {} 条'.format(len(CHECKS), len(FAILS)))
    write('e2e-team-{}.json'.format(args.tag), {'shots': shots, 'user': args.user, 'mode': 'full'})
    return 1 if FAILS else 0


# ---------------------------------------------------------------- member：队员视角

def mode_member(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    ov = api_call('GET', '/api/team/overview', token)[1]['data']
    check('{} 有未读提醒（队长在浏览器阶段点出来的）'.format(args.user), True, ov['unreadCount'] >= 1)
    leader_name = next(m['realName'] for m in ov['team']['members'] if m['isLeader'])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))
        open_student(page, args.user, args.password)
        ov = goto_team(page, token)
        page.wait_for_selector('.member', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)

        check('页顶出现提醒条（站内到达点）', True, dom['pushbar'] is not None)
        check('提醒条标题 = 谁提醒你（队长带标记）', '📣 {}（队长） 提醒你'.format(leader_name),
              dom['pushbar']['b'])
        check('提醒条正文 = 接口 msg', ov['received'][0]['msg'], dom['pushbar']['p'].split(' · ')[0])
        check('提醒条按钮「知道了」', '知道了', dom['pushbar']['btn'])
        tab = next(t for t in dom['navbar'] if '小队' in t['text'])
        check('底栏「小队」Tab 有红点（未读提醒）', True, tab['dot'])
        check('队员看不到「一键提醒」（队长特权，前端也不显示）', None, dom['nudgeAll'])
        me = next(m for m in ov['team']['members'] if m['isMe'])
        my_idx = [m['userId'] for m in ov['team']['members']].index(me['userId'])
        check('自己的卡没有「提醒Ta」（不能提醒自己）', None, dom['members'][my_idx]['btn'])
        lead_idx = [m['userId'] for m in ov['team']['members']].index(
            next(m['userId'] for m in ov['team']['members'] if m['isLeader']))
        check('队长卡没有「提醒Ta」（原型如此）', None, dom['members'][lead_idx]['btn'])
        shots = [shot(page, 'shot-{}-top.png'.format(args.tag))]
        shot_el(page, '.pushbar', 'shot-{}-pushbar-el.png'.format(args.tag), shots)
        shot_el(page, '.members, .member', 'shot-{}-members.png'.format(args.tag), shots)

        # --- 真点：知道了（标已读）---
        page.locator('.pushbar .ack').first.click()
        page.wait_for_timeout(600)
        dom = dom_snapshot(page)
        check('点「知道了」后提醒条消失', None, dom['pushbar'])
        tab = next(t for t in dom['navbar'] if '小队' in t['text'])
        check('红点随之熄灭', False, tab['dot'])
        after = api_call('GET', '/api/team/overview', token)[1]['data']
        check('已读是服务端状态（接口未读清零，不是本地藏起来）', 0, after['unreadCount'])
        page.reload(wait_until='domcontentloaded')
        page.wait_for_selector('.member', timeout=25000)
        page.wait_for_timeout(500)
        dom = dom_snapshot(page)
        check('刷新后提醒条仍然不再出现（真的已读）', None, dom['pushbar'])
        shots.append(shot(page, 'shot-{}-acked.png'.format(args.tag)))
        shot_el(page, '.navbar', 'shot-{}-navbar.png'.format(args.tag), shots)  # shot_el 自己会记账
        shot_full_page(page, 'shot-{}-page.png'.format(args.tag), shots)

        check('浏览器控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()

    print()
    print('队员视角真机核对完成：{} 条断言 · 失败 {} 条'.format(len(CHECKS), len(FAILS)))
    write('e2e-team-{}.json'.format(args.tag), {'shots': shots, 'user': args.user, 'mode': 'member'})
    return 1 if FAILS else 0


# ---------------------------------------------------------------- solo：未入队 → 建队 → 单人队

def mode_solo(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    ov = api_call('GET', '/api/team/overview', token)[1]['data']
    check('{} 还没入队（本模式要先看未入队态）'.format(args.user), None, ov['team'])
    note('未入队态候选小队：{}'.format([c['name'] for c in ov['candidates']] or '空'))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))
        open_student(page, args.user, args.password)
        ov = goto_team(page, token)
        page.wait_for_selector('.invite', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)

        check('未入队态：页头不留队徽（还不知道队名）', None, dom['badge'])
        check('未入队态：出「组一支小队」建队卡', '🐹 组一支小队', dom['create'])
        check('未入队态：出「用队伍号加入」卡', '🔑 用队伍号加入', dom['joincard']['h4'])
        # 候选列表：本班有队就必须画出来（名称/队长/人数/队伍号），本班没队就整块不显示
        check('未入队态：候选列表与接口一致（{}）'.format(
            '、'.join(c['name'] for c in ov['candidates']) or '本班无小队'), len(ov['candidates']),
              len(dom['cands']))
        for i, c in enumerate(ov['candidates']):
            check('候选项「{}」= 队名/队长/人数/队伍号'.format(c['name']),
                  (c['name'], '队长 {} · {} 人 · 队伍号 {}'.format(c['leaderName'], c['memberCount'], c['id']),
                   '加入'),
                  (dom['cands'][i]['name'], dom['cands'][i]['sub'], dom['cands'][i]['btn']))
        check('未入队态：底下就是原型 .solo 那段话（单人也能玩）', True,
              (dom['solo'] or '').startswith('💡 想一个人玩也完全可以'))
        shots = [shot(page, 'shot-{}-noteam-top.png'.format(args.tag))]
        shot_el(page, '.invite', 'shot-{}-create.png'.format(args.tag), shots)
        shot_el(page, '.joincard', 'shot-{}-joincard.png'.format(args.tag), shots)
        if ov['candidates']:
            shot_el(page, '.cands', 'shot-{}-cands.png'.format(args.tag), shots)
        shot_full_page(page, 'shot-{}-noteam-page.png'.format(args.tag), shots)

        # --- 真点：填名字 + 选队徽 + 建队 ---
        page.locator('.invite input').first.fill('独行侠')
        page.locator('.pick-btn').nth(4).click()   # 🦊
        page.wait_for_timeout(150)
        page.locator('.invite .cta').first.click()
        page.wait_for_timeout(800)
        ov2 = api_call('GET', '/api/team/overview', token)[1]['data']
        check('点「建队」后真的建成了（接口 team 非空）', True, ov2['team'] is not None)
        check('建完是单人队（solo=true / 1 人 / 我是队长）', (True, 1, True),
              (ov2['team']['solo'], ov2['team']['memberCount'], ov2['team']['isLeader']))
        check('队名与队徽 = 我在页面上填的', ('独行侠', '🦊'), (ov2['team']['name'], ov2['team']['emoji']))
        dom = dom_snapshot(page)
        check('建完页头挂上队徽', '🦊 独行侠', dom['badge'])
        check('单人队：经验条文案说明「无加成、无宝箱」', '单人队 · 无小队加成与小队宝箱', dom['teamxpText'])
        check('单人队：宝箱块换成「队里就你一个」', '🐹 队里就你一个', dom['invite']['h4'])
        check('单人队：宝箱块说明最少 2 人', '小队最少 2 人才有小队加成与小队宝箱', dom['invite']['p'])
        check('单人队：底下的 .solo 说明仍在（XP 照计）', True, (dom['solo'] or '').startswith('💡 想一个人玩也完全可以'))
        check('单人队：成员卡只有 1 张，且是自己的（没有提醒按钮）', (1, None),
              (len(dom['members']), dom['members'][0]['btn']))
        m0 = ov2['team']['members'][0]
        check('单人队：成员卡三格成绩 = 接口（本周 XP / 通关 / 正确率）',
              ['本周 {} XP'.format(m0['xp']), '通关 {} 关'.format(m0['clears']),
               '本周还没闯关' if m0['answers'] == 0 else '正确率 {}%'.format(round(m0['accuracy'] * 100))],
              dom['members'][0]['stats'])
        check('单人队：XP 照计（本周净得 {} > 0，没有被队伍抹平）'.format(m0['xp']), True, m0['xp'] > 0)
        shots.append(shot(page, 'shot-{}-solo-top.png'.format(args.tag)))
        shot_el(page, '.teamxp', 'shot-{}-solo-teamxp.png'.format(args.tag), shots)
        shot_el(page, '.member', 'shot-{}-solo-member.png'.format(args.tag), shots)
        shot_full_page(page, 'shot-{}-solo-page.png'.format(args.tag), shots)

        check('浏览器控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()

    print()
    print('未入队→单人队真机核对完成：{} 条断言 · 失败 {} 条'.format(len(CHECKS), len(FAILS)))
    write('e2e-team-{}.json'.format(args.tag), {'shots': shots, 'user': args.user, 'mode': 'solo'})
    return 1 if FAILS else 0


# ---------------------------------------------------------------- unlocked：解锁态

def mode_unlocked(args):
    from playwright.sync_api import sync_playwright

    token = login(args.user, args.password)
    ov = api_call('GET', '/api/team/overview', token)[1]['data']
    team = ov['team']
    check('补打后宝箱已解锁（进页面前的前置）', True, team['chest']['unlocked'])
    check('解锁后「需要加油」= 0 人', 0, team['week']['weakCount'])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  locale='zh-CN')
        page = ctx.new_page()
        page.on('console', lambda m: CONSOLE_ERRORS.append('console.' + m.type + ': ' + m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: CONSOLE_ERRORS.append('pageerror: ' + str(e)))
        open_student(page, args.user, args.password)
        ov = goto_team(page, token)
        page.wait_for_selector('.member', timeout=25000)
        page.wait_for_timeout(400)
        dom = dom_snapshot(page)

        check('解锁态：经验条写「🎁 小队宝箱已解锁」', '🎁 小队宝箱已解锁', dom['teamxpText'])
        check('解锁态：进度条拉满 100%', '100%', dom['tfill'])
        check('解锁态：宝箱块进度 100%', '🎁 小队宝箱进度 100%', dom['invite']['h4'])
        check('解锁态：小结里「需要加油」格 = 0 人', '0 人', dom['weeksum'][2]['v'])
        check('解锁态：没人再挂 ⚠ 需加油', [], [m['name'] for m in dom['members'] if '⚠ 需加油' in m['roles']])
        check('解锁态：队长仍看到「已提醒 ⏰」（本周提醒记录还在）', True,
              all(m['btn'] == '已提醒 ⏰' for i, m in enumerate(dom['members'])
                  if not team['members'][i]['isLeader'] and not team['members'][i]['isMe']))
        check('解锁态：nudgeCount=0 → 一键提醒按钮不再出现（原型 hidden 口径）', None, dom['nudgeAll'])
        shots = [shot(page, 'shot-{}-top.png'.format(args.tag))]
        shot_el(page, '.teamxp', 'shot-{}-unlocked-xp.png'.format(args.tag), shots)
        shot_el(page, '.invite', 'shot-{}-invite.png'.format(args.tag), shots)
        shot_el(page, '.weeksum', 'shot-{}-weeksum.png'.format(args.tag), shots)
        shot_full_page(page, 'shot-{}-page.png'.format(args.tag), shots)

        check('浏览器控制台零错误', '[]', str(CONSOLE_ERRORS))
        browser.close()

    print()
    print('解锁态真机核对完成：{} 条断言 · 失败 {} 条'.format(len(CHECKS), len(FAILS)))
    write('e2e-team-{}.json'.format(args.tag), {'shots': shots, 'user': args.user, 'mode': 'unlocked'})
    return 1 if FAILS else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('full', 'member', 'solo', 'unlocked'), required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--tag', required=True)
    args = ap.parse_args()
    if args.mode == 'full':
        return mode_full(args)
    if args.mode == 'member':
        return mode_member(args)
    if args.mode == 'solo':
        return mode_solo(args)
    return mode_unlocked(args)


if __name__ == '__main__':
    sys.exit(main())