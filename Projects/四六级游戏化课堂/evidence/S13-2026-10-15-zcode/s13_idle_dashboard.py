# -*- coding: utf-8 -*-
"""教师看板那 400ms 花在哪：空闲无并发下单发一次 /api/admin/dashboard，量三件事——
客户端耗时 / 服务端 gin 耗时 / 这次请求在 MySQL 里造成的逻辑页读与扫过行数增量。

判据与 S13 那次缺陷同源：逻辑页读（Innodb_buffer_pool_read_requests）不受并发噪声影响。
若增量只有几十页却仍耗几百 ms，说明时间花在 Go 侧而非 SQL；若又是几万页，就是还有全表扫。
用法：python s13_idle_dashboard.py <日志路径> <教师用户名> <教师口令> [次数]
"""
import io
import json
import re
import subprocess
import sys
import time
import urllib.request

LOG, USER, PWD = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 1
BASE = 'http://127.0.0.1:8090'
SECRETS = json.load(io.open(r'D:\cet46-pilot\sql\pilot_secrets.json', encoding='utf-8'))


def mysql(sql):
    p = subprocess.run([SECRETS['mysql_bin'], '--default-character-set=utf8mb4',
                        '-u' + SECRETS['db_user'], '-p' + SECRETS['db_password'],
                        '-h127.0.0.1', '-P3306', '-N', '-B', '-e', sql, SECRETS['db_name']],
                       capture_output=True)
    return p.stdout.decode('utf-8', 'replace').strip()


def counters():
    out = mysql("SHOW GLOBAL STATUS WHERE Variable_name IN "
                "('Innodb_rows_read','Innodb_buffer_pool_read_requests','Questions')")
    d = {}
    for line in out.splitlines():
        k, v = line.split('\t')
        d[k] = int(v)
    return d


def call(path, body=None, tok=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    h = {'Content-Type': 'application/json'}
    if tok:
        h['Authorization'] = 'Bearer ' + tok
    req = urllib.request.Request(BASE + path, data=data, headers=h)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return (time.time() - t0) * 1000.0, raw


def gin_tail(path, n=6):
    with io.open(path, 'rb') as f:
        lines = [l for l in f.read().split(b'\n') if b'[GIN]' in l]
    return [l.decode('utf-8', 'replace') for l in lines[-n:]]


print('== 空闲态教师看板单发测量 ==')
ms, _ = call('/api/auth/login', {'username': USER, 'password': PWD})
print('教师登录客户端 %.1f ms（含 bcrypt）' % ms)
tok = json.loads(_.decode('utf-8'))['data']['token']

for i in range(1, N + 1):
    c0 = counters()
    t0 = time.time()
    ms, raw = call('/api/admin/dashboard', tok=tok)
    wr = (time.time() - t0) * 1000.0
    c1 = counters()
    print()
    print('第 %d 次：客户端 %.1f ms · 响应 %d 字节' % (i, wr, len(raw)))
    print('  MySQL 增量：扫过行 %d · 逻辑页读 %d · Questions %d'
          % (c1['Innodb_rows_read'] - c0['Innodb_rows_read'],
             c1['Innodb_buffer_pool_read_requests'] - c0['Innodb_buffer_pool_read_requests'],
             c1['Questions'] - c0['Questions']))
    try:
        d = json.loads(raw.decode('utf-8'))['data']
        print('  响应顶层字段：%s' % ', '.join(list(d.keys())))
        for k, v in d.items():
            if isinstance(v, list):
                print('    %s：list(%d)' % (k, len(v)))
    except Exception as e:
        print('  解析失败：%s' % e)

print()
print('本次尾部 [GIN] 行：')
for l in gin_tail(LOG, 8):
    if '/api/admin/dashboard' in l or '/api/auth/login' in l:
        m = re.search(r'\|\s*(\d{3})\s*\|\s*([0-9.a-zµu]+)\s*\|', l)
        stamp = l.split(' - ')[-1].split('|')[0].strip()
        print('  %s → HTTP %s · 服务端 %s' % (stamp, m.group(1), m.group(2)))