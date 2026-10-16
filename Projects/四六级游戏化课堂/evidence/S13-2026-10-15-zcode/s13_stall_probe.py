# -*- coding: utf-8 -*-
# 口令口径：压测口令字面量不进 evidence 副本（验收侧 2026-10-16 复验发现后处置为占位符）。
# 运行原文只留本机运行目录；真值口径见 deploy/loadtest/s13_locust.py 的 LOAD_PWD_SUFFIX。
"""S13 压测毛刺定位：检测到业务接口 >2s 时，立刻 dump MySQL 全量 processlist。

背景：40 并发下 paper/submit/live/dashboard 会周期性掉进 10~40s 的坑，而同期
  · /api/health（不落库）始终 3~30ms；
  · MySQL 行锁等待 / log 等待均为 0；
  · 全机 CPU 平均 37%，cet46-server 只吃掉 0.3~0.6 核。
所以既不是 CPU 打满，也不是库在等锁。本脚本要回答的是：**掉坑的那一瞬间，库那头到底在干什么。**

判读方法：
  · 若 dump 里出现 20 条（=连接池上限）长期 executing 的语句 → 库/连接池是瓶颈；
  · 若 import 里语句寥寥、多为 Sleep，而客户端仍在等 → 瓶颈在 Go 进程内部（等连接/等锁/等写）。
"""
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

PILOT = r'D:\cet46-pilot'
SEC = json.load(io.open(os.path.join(PILOT, 'sql', 'pilot_secrets.json'), encoding='utf-8'))
CMD = [SEC['mysql_bin'], '--protocol=tcp', '-h', '127.0.0.1', '-P', str(SEC['db_port']),
       '-u', SEC['db_user'], '-D', SEC['db_name'], '-N', '-B']
ENV = dict(os.environ)
ENV['MYSQL_PWD'] = SEC['db_password']

API = 'http://127.0.0.1:8090'


def sql(q):
    r = subprocess.run(CMD + ['-e', q], capture_output=True, env=ENV)
    if r.returncode:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace'))
    return r.stdout.decode('utf-8', 'replace').strip()


def login(u, p):
    r = urllib.request.Request(API + '/api/auth/login', method='POST',
                               data=json.dumps({'username': u, 'password': p}).encode())
    r.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())['data']['token']


def dump(tag, canary_ms):
    rows = sql("select id, user, time, state, command, "
               "left(replace(replace(coalesce(info,''), char(10), ' '), char(9), ' '), 90) "
               "from information_schema.processlist order by time desc")
    lines = [ln.split('\t') for ln in rows.splitlines() if ln.strip()]
    running = [l for l in lines if l[4] != 'Sleep']
    print('\n=== %s：canary %.0fms · 连接 %d（活跃 %d）===' % (tag, canary_ms, len(lines), len(running)))
    for l in lines[:22]:
        print('  id=%-6s time=%-5s state=%-16s cmd=%-8s %s' % (l[0], l[2], l[3][:16], l[4], l[5]))
    sys.stdout.flush()


def main():
    ttok = login('T2024001', __LOAD_TCH_PWD__)
    stok = login('2405510104', __LOAD_STU_PWD__)
    stop = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 240)

    def canary():
        hit = 0
        while time.time() < stop:
            for name, path, tok in (('live', '/api/admin/live?classId=1', ttok),
                                    ('paper', '/api/quiz/paper?level=1', stok)):
                r = urllib.request.Request(API + path)
                r.add_header('Authorization', 'Bearer ' + tok)
                t = time.time()
                try:
                    with urllib.request.urlopen(r, timeout=90) as resp:
                        resp.read()
                    ms = (time.time() - t) * 1000
                except Exception as e:
                    ms = (time.time() - t) * 1000
                    print('[canary] %s 异常 %.0fms %s' % (name, ms, e))
                if ms > 2000:
                    hit += 1
                    if hit <= 6:
                        dump('STALL %s #%d' % (name, hit), ms)
                time.sleep(0.4)

    def light():
        """轻度业务流量，保证库里有并发在跑（4 个 read 客户端）。"""
        while time.time() < stop:
            for path, tok in (('/api/quiz/levels', stok), ('/api/admin/live?classId=1', ttok)):
                r = urllib.request.Request(API + path)
                r.add_header('Authorization', 'Bearer ' + tok)
                try:
                    with urllib.request.urlopen(r, timeout=90) as resp:
                        resp.read()
                except Exception:
                    pass
            time.sleep(0.1)

    threads = [threading.Thread(target=canary), threading.Thread(target=light)]
    for _ in range(6):
        threads.append(threading.Thread(target=light))
    for t in threads:
        t.daemon = True
        t.start()
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()