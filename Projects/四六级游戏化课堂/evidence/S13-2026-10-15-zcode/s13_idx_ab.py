# -*- coding: utf-8 -*-
"""S13 压测缺陷修复的「前后对比」测量（试点库，只读，不改数据）。

量的是压测里真正拖慢系统的三条查询。每条都给三样东西：
  1) EXPLAIN 的 type/key/rows —— 看它走不走索引；
  2) 服务端耗时（SET @t=CURRENT_TIMESTAMP(6) 前后夹住，客户端开销不计入）；
  3) 同一连接内的 Innodb_buffer_pool_read_requests 增量 —— 逻辑页访问次数，
     这一项不受并发噪声影响，是"回表/全表扫"最直接的证据。

索引建好之后还能用 IGNORE INDEX 把"没有索引时的行为"在同一份数据、同一时刻
再跑一遍：这样前后对比不是跨时间的两次采样，而是同秒内的 A/B。

用法：python s13_idx_ab.py before|after <输出json路径>
"""
import json
import os
import subprocess
import sys

PILOT = r'D:\cet46-pilot'
SEP = '=' * 72


def conn_args(sec):
    return [sec['mysql_bin'], '--protocol=tcp', '-h', sec['db_host'], '-P', str(sec['db_port']),
            '-u', sec['db_user'], '-p' + sec['db_password'], sec['db_name'],
            '--default-character-set=utf8mb4', '-N', '-B']


def run(sec, sql, timeout=120):
    r = subprocess.run(conn_args(sec) + ['-e', sql], capture_output=True, timeout=timeout)
    out = r.stdout.decode('utf-8', 'replace').strip()
    err = r.stderr.decode('utf-8', 'replace').strip()
    err = '\n'.join(l for l in err.splitlines() if 'Using a password' not in l).strip()
    return out, err


def last_line(out):
    lines = [l for l in out.splitlines() if l.strip()]
    return lines[-1] if lines else ''


def measure(sec, q, reps=5, note=''):
    """跑 reps 次：返回服务端耗时列表（ms）与逻辑页增量。"""
    block = [
        "SHOW SESSION STATUS LIKE 'Innodb_buffer_pool_read_requests';",
        "SHOW SESSION STATUS LIKE 'Innodb_rows_read';",
    ]
    for _ in range(reps):
        block.append('SET @t = CURRENT_TIMESTAMP(6);')
        block.append(q.rstrip(';') + ';')
        block.append("SELECT ROUND(TIMESTAMPDIFF(MICROSECOND, @t, CURRENT_TIMESTAMP(6)) / 1000, 2);")
    block.append("SHOW SESSION STATUS LIKE 'Innodb_buffer_pool_read_requests';")
    block.append("SHOW SESSION STATUS LIKE 'Innodb_rows_read';")
    out, err = run(sec, '\n'.join(block))
    if err:
        return {'ok': False, 'error': err, 'note': note}
    lines = out.splitlines()
    # 前两行 = 起点状态，最后两行 = 终点状态
    pre_pages = int(lines[0].split('\t')[-1])
    pre_rows = int(lines[1].split('\t')[-1])
    post_pages = int(lines[-2].split('\t')[-1])
    post_rows = int(lines[-1].split('\t')[-1])
    ms = []
    for l in lines[2:-2]:
        try:
            ms.append(float(l))
        except ValueError:
            pass
    ms.sort()
    return {
        'ok': True, 'note': note,
        'ms_med': ms[len(ms) // 2] if ms else None,
        'ms_min': ms[0] if ms else None,
        'ms_max': ms[-1] if ms else None,
        'pages_per_query': round((post_pages - pre_pages) / float(reps), 1),
        'rows_per_query': round((post_rows - pre_rows) / float(reps), 1),
        'reps': reps,
    }


# mysql -N -B 下 EXPLAIN 不出表头，只能按列序取：
# id, select_type, table, partitions, type, possible_keys, key, key_len, ref, rows, filtered, Extra
EXPLAIN_COLS = ['id', 'select_type', 'table', 'partitions', 'type', 'possible_keys', 'key',
                'key_len', 'ref', 'rows', 'filtered', 'Extra']


def explain(sec, q):
    out, err = run(sec, 'EXPLAIN ' + q.rstrip(';'))
    if err:
        return {'error': err}
    rows = []
    for line in out.splitlines():
        f = line.split('\t')
        if len(f) < 12:
            continue
        d = dict(zip(EXPLAIN_COLS, f))
        rows.append({k: d[k] for k in ('table', 'type', 'key', 'rows', 'Extra')})
    return rows if len(rows) > 1 else (rows[0] if rows else {})


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'before'
    outpath = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get('TEMP', '.'), 's13_idx_ab.json')
    sec = json.load(open(os.path.join(PILOT, 'sql', 'pilot_secrets.json'), encoding='utf-8'))

    ids_out, err = run(sec, "select group_concat(id order by id) from users where role='student'")
    if err or not ids_out:
        print('取学生 id 失败：' + (err or '空'))
        return 1
    ids = ids_out.strip()
    n_students = len(ids.split(','))
    aid, _ = run(sec, 'select max(id) from attempts')

    idx_out, _ = run(sec, "select index_name from information_schema.statistics "
                          "where table_schema='cet46_pilot' and table_name='xp_ledger' "
                          "and index_name in ('idx_xp_ledger_user_delta','idx_xp_ledger_user_created','idx_xp_ledger_ref') "
                          "group by index_name order by index_name")
    have = [x for x in idx_out.split() if x]

    q_sum = ("SELECT user_id, SUM(delta) AS xp FROM xp_ledger WHERE user_id IN (%s) GROUP BY user_id" % ids)
    q_streak_old = "SELECT user_id, created_at FROM xp_ledger WHERE user_id IN (%s)" % ids
    q_streak_new = ("SELECT user_id AS user_id, DATE(created_at) AS day FROM xp_ledger "
                    "WHERE user_id IN (%s) GROUP BY user_id, DATE(created_at)" % ids)
    q_ref = ("SELECT reason, COALESCE(SUM(delta), 0) AS delta FROM xp_ledger "
             "WHERE ref_type = 'attempt' AND ref_id = %s GROUP BY reason" % aid)

    cases = [
        ('看板·按用户求和 XP（覆盖索引 user_id,delta）', q_sum, 'idx_xp_ledger_user_delta'),
        ('登录/地图·连续周派生-旧写法（整本账搬回 Go）', q_streak_old, None),
        ('登录/地图·连续周派生-新写法（按天分组）', q_streak_new, 'idx_xp_ledger_user_created'),
        ("交卷·按单据查流水（索引 ref_type,ref_id）", q_ref, 'idx_xp_ledger_ref'),
    ]

    report = {'label': label, 'students': n_students, 'indexes_present': have, 'cases': []}
    print(SEP)
    print('试点库 xp_ledger 前后对比测量 · 阶段=%s · 学生数=%d · 已在索引=%s'
          % (label, n_students, have or '无'))
    print(SEP)
    for title, q, idxname in cases:
        entry = {'title': title, 'explain': explain(sec, q), 'as_is': measure(sec, q, note='按当前索引状态')}
        if idxname and idxname in have:
            qi = q.replace('FROM xp_ledger ', 'FROM xp_ledger IGNORE INDEX (%s) ' % idxname)
            entry['ignored'] = measure(sec, qi, note='IGNORE INDEX %s：模拟没有该索引时的行为' % idxname)
            entry['explain_ignored'] = explain(sec, qi)
        report['cases'].append(entry)
        print()
        print('## ' + title)
        print('   EXPLAIN(实际)      : %s' % json.dumps(entry['explain'], ensure_ascii=False))
        if 'explain_ignored' in entry:
            print('   EXPLAIN(忽略索引)  : %s' % json.dumps(entry['explain_ignored'], ensure_ascii=False))
        for k in ('as_is', 'ignored'):
            if k not in entry:
                continue
            m = entry[k]
            if not m.get('ok'):
                print('   %-8s 失败：%s' % (k, m['error'].splitlines()[0]))
                continue
            print('   %-8s %-46s 中位 %s ms（%s~%s）· 每次逻辑页读 %s · 每次扫过行 %s'
                  % (k, m['note'], m['ms_med'], m['ms_min'], m['ms_max'], m['pages_per_query'], m['rows_per_query']))
    json.dump(report, open(outpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print()
    print('JSON 落盘：' + outpath)
    return 0


if __name__ == '__main__':
    sys.exit(main())