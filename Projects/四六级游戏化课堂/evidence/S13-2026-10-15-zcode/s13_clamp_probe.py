# -*- coding: utf-8 -*-
"""S13 探针：速度加成限幅（elapsedMs）在真实试点环境上的一端到端取证。

打的是试点栈本身：http://127.0.0.1/api（Nginx 80 → Go 8090 → MySQL 3306/cet46_pilot）。
三段取证：
  ① 首登强制改密门（40302）+ 改密后旧令牌作废——探针自己走一遍，免得把「被门拦住」误读成失败；
  ② 限幅生效：隔 55 秒才交第 1 题却上报 elapsedMs=0，速度分必须掉到按窗口算出来的那个数
     （限幅前会白拿 10）；
  ③ 诚实上报不被误伤：隔 14 秒报 13000ms，速度分必须等于公式算出来的值，一个字都不许改；
  ④ 没上报耗时（elapsedMs 缺省）仍是 0，且不会被「抬」成一个具体数字；
  ⑤ 整关打完 → 结算 → attempts.xp_earned == sum(xp_ledger.delta) == 逐题分 + 通关 30 + 三星 20。

反复可跑：每次自动挑一个「还没改过初始密码」的学生（pwd_hash 带 init$ 前缀），
所以每次都从首登门开始；试点 41 人够跑，整库复位后重新生成。
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = 'http://127.0.0.1/api'
PILOT = r'D:\cet46-pilot'
FAILS = []
NCHECK = [0]


def check(desc, want, got):
    NCHECK[0] += 1
    ok = str(want) == str(got)
    print('[%s] %s（期望=%s 实际=%s）' % ('OK  ' if ok else 'FAIL', desc, want, got))
    if not ok:
        FAILS.append('%s（期望=%s 实际=%s）' % (desc, want, got))
    return ok


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header('Content-Type', 'application/json')
    if token:
        r.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {'raw': raw}


_ENV = {}
with io.open(os.path.join(PILOT, 'server', '.env'), encoding='utf-8') as f:
    for _line in f:
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            _ENV[_k.strip()] = _v.strip()


def sql(q):
    """直连试点库（探针只读；写操作全走 HTTP）。"""
    cmd = ['mysql', '--protocol=tcp', '-h', '127.0.0.1', '-P', _ENV['DB_PORT'],
           '-u', _ENV['DB_USER'], '-D', _ENV['DB_NAME'], '-N', '-B',
           '--default-character-set=utf8mb4', '-e', q]
    e = dict(os.environ)
    e['MYSQL_PWD'] = _ENV['DB_PASSWORD']
    out = subprocess.run(cmd, capture_output=True, env=e)
    if out.returncode != 0:
        raise RuntimeError('mysql 查询失败：%s' % out.stderr.decode('utf-8', 'replace'))
    return out.stdout.decode('utf-8', 'replace').strip()


def main():
    print('== S13 速度加成限幅探针 开始 %s ==' % time.strftime('%Y-%m-%d %H:%M:%S'))
    print('   落点：%s（Nginx 80 → Go 8090 → cet46_pilot）' % API)

    # ---------- 探针学生 ----------
    probe_user = sql("select username from users where role='student' and pwd_hash like 'init$%' "
                     "order by username desc limit 1")
    if not probe_user:
        print('!! 没有「未改初始密码」的学生了（41 人全改过），无法复现首登门；先做整库复位')
        return 1
    print('   探针学生：%s（仍持初始口令）' % probe_user)

    with io.open(os.path.join(PILOT, 'data', '学生初始口令-分发后删除.csv'), encoding='utf-8-sig') as f:
        rows = [ln for ln in f.read().splitlines() if ln.strip()]
    head = rows[0].split(',')
    init_pwd = None
    for ln in rows[1:]:
        cells = ln.split(',')
        if len(cells) != len(head):
            continue
        d = dict(zip(head, cells))
        if d.get('学号') == probe_user:
            init_pwd = d.get('初始密码')
            break
    if not init_pwd:
        print('!! 名单文件里没有 %s 的初始口令，探针无法登录' % probe_user)
        return 1

    # ---------- ① 首登门 ----------
    print('\n-- ① 首登强制改密门（40302）与改密后旧令牌作废 --')
    st, env = req('POST', '/auth/login', body={'username': probe_user, 'password': init_pwd})
    check('初始口令登录成功', 200, st)
    r = env.get('data') or env
    check('回执带 mustChangePwd=true', 'True', r.get('mustChangePwd'))
    token = r.get('token')
    st, env = req('GET', '/quiz/levels', token=token)
    check('未改密时业务接口被门挡住（40302）', '403/40302', '%s/%s' % (st, env.get('code')))
    new_pwd = 'S13Probe-%d-Kx7' % int(time.time())
    st, env = req('POST', '/auth/chpwd', token=token,
                  body={'oldPassword': init_pwd, 'newPassword': new_pwd})
    check('改密成功', 200, st)
    st, env = req('GET', '/quiz/levels', token=token)
    check('改密后旧令牌即作废（再访问 401）', 401, st)
    st, env = req('POST', '/auth/login', body={'username': probe_user, 'password': new_pwd})
    check('用新口令重新登录', 200, st)
    r = env.get('data') or env
    check('重新登录后不再要求改密', 'False', str(r.get('mustChangePwd')))
    token = r.get('token')
    st, env = req('GET', '/quiz/levels', token=token)
    check('业务接口放行', 200, st)

    # ---------- ② 挑一关：全单选、正确项文本唯一（探针才敢全答对，好把整关打完看结算） ----------
    items = (env.get('data') or env).get('items') or []
    win = [x for x in items if x.get('unlocked') and not x.get('cleared')]
    print('   已解锁未通关：%s' % [(x['id'], x['name'], x['questionCount']) for x in win[:6]])
    if not win:
        print('!! 地图上没有「已解锁未通关」的关卡')
        return 1
    ids = ','.join(str(x['id']) for x in win)
    qrows = sql("select l.id, q.id, q.answer_idx, q.options_json from levels l "
                "join questions q on q.level_id = l.id "
                "where l.id in (%s) and q.enabled = 1 order by l.id, q.id" % ids)
    per = {}
    for ln in qrows.splitlines():
        lid, qid, aidx, opts = ln.split('\t', 3)
        per.setdefault(int(lid), []).append((int(qid), aidx, json.loads(opts)))

    def usable(qs):
        if not qs:
            return False
        for _qid, aidx, opts in qs:
            if ',' in aidx:
                return False        # 多空题：展示坐标是逗号序列，探针不为难自己
            i = int(aidx)
            if i >= len(opts):
                return False
            if opts.count(opts[i]) != 1:
                return False        # 正确项文本不唯一：按文本定位会认错人
        return True

    lv = next((x for x in win if usable(per.get(x['id']))), None)
    if lv is None:
        print('!! 没有「全单选且正确项唯一」的已解锁关卡，探针无法在没有答案下发的前提下全答对')
        return 1
    lid = lv['id']
    limit_sec = int(sql("select time_limit from levels where id=%d" % lid) or 0) // max(len(per[lid]), 1)
    print('   选关：#%s %s（%d 题 · 每题限时 %d 秒）' % (lid, lv['name'], len(per[lid]), limit_sec))

    st, env = req('GET', '/quiz/paper?level=%d' % lid, token=token)
    check('取卷 200', 200, st)
    paper = env.get('data') or env
    at = paper['attemptId']
    qs = paper['questions']
    check('本关是一次全新 attempt（不是断点续答，观测窗口才干净）', 'False', str(paper.get('resumed')))
    check('卷面题数 = 题库题数', len(per[lid]), len(qs))

    # 展示坐标下正确项的位置：题库里的正确项文本 → 卷面 options 里的下标
    disp = {}
    for q in qs:
        want = next(t for _qid, aidx, opts in per[lid] if _qid == q['id'] for t in [opts[int(aidx)]])
        disp[q['id']] = q['options'].index(want)
    check('每道题都定位到了正确项', len(qs), len(disp))

    def submit(qid, elapsed, tag):
        ans = {'questionId': qid, 'pickedIdx': str(disp[qid])}
        if elapsed is not None:
            ans['elapsedMs'] = elapsed
        st, env = req('POST', '/quiz/submit', token=token,
                      body={'attemptId': at, 'answers': [ans]})
        data = env.get('data') or env
        fb = (data.get('feedback') or [{}])[0]
        xp = fb.get('xp') or {}
        print('   %-28s HTTP %s · 答对=%s · xp=%s · 上报=%s' % (
            tag, st, fb.get('isCorrect'), json.dumps(xp, ensure_ascii=False), elapsed))
        return st, data, fb, xp

    order = [q['id'] for q in qs]

    # ---------- ③ 限幅生效：隔 55 秒才交第 1 题，却上报 0 ----------
    print('\n-- ② 限幅生效（真的隔了 55 秒，却上报 elapsedMs=0）--')
    print('   等待 55 秒，让服务端观测窗口明显大于 0……')
    time.sleep(55)
    st, data, fb, xp = submit(order[0], 0, '撒谎：窗口 55 秒 / 报 0')
    want = max(0, min(10, round(10 * (1 - (55000 - 2000) / 1000.0 / limit_sec))))
    check('速度分按观测窗口算（%d），不是白拿的 10' % want, want, xp.get('speed'))
    check('基础分不受影响（答对 20）', 20, xp.get('base'))

    # ---------- ④ 诚实上报不被误伤 ----------
    print('\n-- ③ 诚实上报不被误伤（隔 14 秒，报 13000ms）--')
    time.sleep(14)
    st, data, fb, xp = submit(order[1], 13000, '诚实：窗口 14 秒 / 报 13000')
    want = max(0, min(10, round(10 * (1 - 13000 / 1000.0 / limit_sec))))
    check('诚实上报拿到它应得的速度分 %d（一字未改）' % want, want, xp.get('speed'))

    # ---------- ⑤ 没上报耗时 ----------
    print('\n-- ④ 没上报耗时（elapsedMs 缺省）--')
    st, data, fb, xp = submit(order[2], None, '无数据：不上报')
    check('没上报时速度分为 0（不给「没数据」送满分）', 0, xp.get('speed'))

    # ---------- ⑥ 打完剩下的题，让它结算 ----------
    print('\n-- ⑤ 打完剩下的 %d 题，触发结算 --' % (len(order) - 3))
    for qid in order[3:]:
        st, data, fb, xp = submit(qid, 5000, '补完：报 5000')
        check('补完的题答对（0 失误才有三星）', True, fb.get('isCorrect'))
    check('本次闯关最终状态 finished', 'finished', data.get('status'))
    stt = data.get('settlement')
    check('结算回执存在', 'yes', 'yes' if stt else 'no')
    if stt:
        print('   结算：%s' % json.dumps(stt, ensure_ascii=False))

    # ---------- ⑦ 对账 ----------
    print('\n-- ⑥ 账本对账（结算后）--')
    rows = sql("select reason, delta from xp_ledger where ref_type='attempt' and ref_id=%d order by id" % at)
    detail = [ln.split('\t') for ln in rows.splitlines()]
    ledger_sum = sum(int(d) for _, d in detail)
    earned = int(sql("select coalesce(xp_earned,0) from attempts where id=%d" % at) or 0)
    by_reason = {}
    for reason, d in detail:
        by_reason[reason] = by_reason.get(reason, 0) + int(d)
    print('   账本明细（按 reason 合并）：%s' % json.dumps(by_reason, ensure_ascii=False))
    print('   账本逐条流水：')
    for reason, d in detail:
        print('     %-18s %+d' % (reason, int(d)))
    check('attempts.xp_earned == 账本求和', earned, ledger_sum)
    check('答题行数 = 题数', len(qs), int(sql(
        "select count(*) from attempt_answers where attempt_id=%d" % at) or 0))
    expect_answer = len(qs) * 20
    check('基础分合计 = 题数 × 20', expect_answer, by_reason.get('answer_base'))
    check('通关分 30', 30, by_reason.get('level_clear'))
    check('三星奖励 20', 20, by_reason.get('star3_bonus'))

    print('\n== 探针结束：断言 %d 条 / 失败 %d ==' % (NCHECK[0], len(FAILS)))
    for f in FAILS:
        print('  [FAIL] ' + f)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())