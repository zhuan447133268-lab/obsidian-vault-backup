# -*- coding: utf-8 -*-
"""隔离「登录那 200ms 花在哪」：空闲无并发下连打 3 次登录，把服务端 gin 耗时取出来。

判据：登录只做两件事 —— 按 username 查一行（有唯一索引）+ bcrypt 校验（DefaultCost=10）。
GORM 只记录 >=200ms 的 SQL；如果 DB 查询是瓶颈，3 次登录就该配 3 条 SLOW SQL。
用法：python s13_idle_login.py <日志路径> <用户名> <口令> <登录次数>
"""
import io
import json
import re
import subprocess
import sys
import time
import urllib.request

LOG, USER, PWD, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
BASE = 'http://127.0.0.1:8090'


def gin_lines(path):
    with io.open(path, 'rb') as f:
        return [l for l in f.read().split(b'\n') if b'[GIN]' in l]


def login():
    body = json.dumps({'username': USER, 'password': PWD}).encode('utf-8')
    req = urllib.request.Request(BASE + '/api/auth/login', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()
    return (time.time() - t0) * 1000.0


before = len(gin_lines(LOG))
print('基线 [GIN] 行数：%d' % before)
print('%-6s %12s' % ('第n次', '客户端 ms'))
client = []
for i in range(1, N + 1):
    ms = login()
    client.append(ms)
    print('%-6d %12.1f' % (i, ms))

time.sleep(1.0)
after = gin_lines(LOG)[before:]
print()
print('本次新增 [GIN] 行（服务端口径）：')
for l in after:
    s = l.decode('utf-8', 'replace')
    if '/api/auth/login' in s:
        m = re.search(r'\|\s*(\d{3})\s*\|\s*([0-9.a-zµu]+)\s*\|', s)
        print('  %s  → HTTP %s · 服务端 %s' % (s.split('|')[1].strip() + ' ' + s.split('|')[0].split(' - ')[-1].strip(),
                                              m.group(1), m.group(2)))
print()
print('客户端中位 %.1f ms · 服务端见上（差值=python 单线程客户端 + HTTP 往返开销）'
      % sorted(client)[len(client) // 2])
print('提示：若上面没有出现任何 SQL 行，说明按 username 的那次查询 < 200ms（未达 GORM 慢日志阈值）。')