# -*- coding: utf-8 -*-
"""教师看板 500ms / 60 万逻辑页读到底花在哪条 SQL —— 逐条量，不猜。

看板（/api/admin/dashboard）在一次请求里跑 17 条 SQL（MySQL Questions 增量实测 17）。
这里把代码里能对上的候选查询逐条单独跑，各量三件事：
  扫过行 Innodb_rows_read / 逻辑页读 Innodb_buffer_pool_read_requests / 服务端耗时
逻辑页读是「回表、全表扫」最硬的证据（不受并发噪声影响）。

用法：python s13_dashboard_queries.py
"""
import io
import json
import subprocess
import time

S = json.load(io.open(r'D:\cet46-pilot\sql\pilot_secrets.json', encoding='utf-8'))
DB = S['db_name']


def q(sql):
    p = subprocess.run([S['mysql_bin'], '--default-character-set=utf8mb4',
                        '-u' + S['db_user'], '-p' + S['db_password'],
                        '-h127.0.0.1', '-P3306', '-N', '-B', '-e', sql, DB],
                       capture_output=True)
    return p.stdout.decode('utf-8', 'replace').strip(), p.stderr.decode('utf-8', 'replace').strip()


def status():
    out, _ = q("SHOW GLOBAL STATUS WHERE Variable_name IN "
               "('Innodb_rows_read','Innodb_buffer_pool_read_requests')")
    d = {}
    for line in out.splitlines():
        k, v = line.split('\t')
        d[k] = int(v)
    return d


def measure(label, sql, explain=None):
    if explain:
        ex, _ = q('EXPLAIN ' + explain)
    else:
        ex, _ = q('EXPLAIN ' + sql)
    c0 = status()
    t0 = time.time() * 1000.0
    out, err = q(sql)
    ms = time.time() * 1000.0 - t0
    c1 = status()
    rows = c1['Innodb_rows_read'] - c0['Innodb_rows_read']
    pages = c1['Innodb_buffer_pool_read_requests'] - c0['Innodb_buffer_pool_read_requests']
    nlines = len([l for l in out.splitlines() if l.strip()])
    print('%-34s 返回 %-6d 扫过行 %-9d 逻辑页读 %-9d 耗时 %8.1f ms' % (label, nlines, rows, pages, ms))
    for l in ex.splitlines()[:4]:
        cols = l.split('\t')
        if len(cols) >= 12:
            print('      EXPLAIN: table=%s type=%s key=%s rows=%s Extra=%s'
                  % (cols[3], cols[4], cols[6], cols[9], cols[11]))
    if err and 'Warning' not in err:
        print('      ERR: %s' % err.strip())
    print()
    return rows, pages, ms


ids_out, _ = q("SELECT id FROM users WHERE class_id = 1 AND role = 'student' ORDER BY username")
IDS = [x for x in ids_out.splitlines() if x.strip()]
IN = '(' + ','.join(IDS) + ')'
print('班级 1 学生 %d 人 · 本周一 = 2026-10-12 · 上周一 = 2026-10-05\n' % len(IDS))
print('%-34s %s' % ('查询', '结果') + '\n' + '-' * 104)

T = []
T.append(measure('① classStudents(名单)',
                 "SELECT * FROM users WHERE class_id = 1 AND role = 'student' ORDER BY username ASC"))
T.append(measure('② studentCounts(各班人数)',
                 "SELECT class_id AS class_id, COUNT(*) AS n FROM users WHERE class_id IN (1) "
                 "AND role = 'student' GROUP BY class_id"))
T.append(measure('③ clearPoints(本周通关事件)',
                 "SELECT user_id AS user_id, level_id AS level_id, finished_at AS finished_at "
                 "FROM attempts WHERE user_id IN %s AND status = 'finished' AND finished_at IS NOT NULL" % IN))
T.append(measure('④ xpSumsBetween(本周 XP)',
                 "SELECT user_id AS user_id, COALESCE(SUM(delta),0) AS sum FROM xp_ledger "
                 "WHERE user_id IN %s AND created_at >= '2026-10-12 00:00:00' "
                 "AND created_at < '2026-10-15 18:20:00' GROUP BY user_id" % IN))
T.append(measure('⑤ xpSumsBetween(上周 XP)',
                 "SELECT user_id AS user_id, COALESCE(SUM(delta),0) AS sum FROM xp_ledger "
                 "WHERE user_id IN %s AND created_at >= '2026-10-05 00:00:00' "
                 "AND created_at < '2026-10-12 00:00:00' GROUP BY user_id" % IN))
T.append(measure('⑥ attendCount 再跑一次本周 XP',
                 "SELECT user_id AS user_id, COALESCE(SUM(delta),0) AS sum FROM xp_ledger "
                 "WHERE user_id IN %s AND created_at >= '2026-10-12 00:00:00' "
                 "AND created_at < '2026-10-15 18:20:00' GROUP BY user_id" % IN))
T.append(measure('⑦ weakPoints(薄弱知识点 JOIN)',
                 "SELECT COALESCE(NULLIF(questions.knowledge_tag,''),'未分类') AS tag, "
                 "attempts.user_id AS user_id, COUNT(*) AS total, "
                 "SUM(CASE WHEN attempt_answers.is_correct THEN 0 ELSE 1 END) AS wrong "
                 "FROM attempt_answers "
                 "JOIN questions ON questions.id = attempt_answers.question_id "
                 "JOIN attempts ON attempts.id = attempt_answers.attempt_id "
                 "WHERE attempts.user_id IN %s AND attempt_answers.created_at >= '2026-10-12 00:00:00' "
                 "AND attempts.unit_id IN (SELECT id FROM units WHERE class_id = 1) "
                 "GROUP BY tag, attempts.user_id" % IN))

print('-' * 104)
tr = sum(x[0] for x in T)
tp = sum(x[1] for x in T)
tm = sum(x[2] for x in T)
print('七条合计：扫过行 %d · 逻辑页读 %d · 耗时 %.1f ms' % (tr, tp, tm))
print('整只请求（含 17 条 SQL + Go 侧纯函数计算）：扫过行 209441 · 逻辑页读 603113 · 约 550 ms')
print('差值里剩下的：本探针没复刻的 SQL（题库计数等）+ Go 侧按周分桶/预警/建议文案的计算。')