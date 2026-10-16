# -*- coding: utf-8 -*-
"""看板两条重查询的索引候选试装：先量基线，再建候选索引量一遍，最后同秒 IGNORE INDEX 反证。

要证的是两件事：
  ① xp_ledger(user_id, created_at, delta) 能把「本周 XP 求和」从回表变成覆盖索引；
  ② attempt_answers(attempt_id, created_at, question_id, is_correct) 能把薄弱知识点的 JOIN
     从「查 7 条再逐条回表」变成索引内取数。
试装是可逆的（DROP INDEX 即可），先确认优化器真会用，再决定要不要写进模型。
"""
import io
import json
import subprocess
import time

S = json.load(io.open(r'D:\cet46-pilot\sql\pilot_secrets.json', encoding='utf-8'))


def q(sql):
    p = subprocess.run([S['mysql_bin'], '--default-character-set=utf8mb4',
                        '-u' + S['db_user'], '-p' + S['db_password'],
                        '-h127.0.0.1', '-P3306', '-N', '-B', '-e', sql, S['db_name']],
                       capture_output=True)
    return p.stdout.decode('utf-8', 'replace').strip(), p.stderr.decode('utf-8', 'replace').strip()


def status():
    out, _ = q("SHOW GLOBAL STATUS WHERE Variable_name IN "
               "('Innodb_rows_read','Innodb_buffer_pool_read_requests')")
    return {k: int(v) for k, v in (l.split('\t') for l in out.splitlines())}


ids_out, _ = q("SELECT id FROM users WHERE class_id = 1 AND role = 'student' ORDER BY username")
IN = '(' + ','.join(x for x in ids_out.splitlines() if x.strip()) + ')'

WEEK_XP = ("SELECT user_id AS user_id, COALESCE(SUM(delta),0) AS sum FROM xp_ledger "
           "WHERE user_id IN %s AND created_at >= '2026-10-12 00:00:00' "
           "AND created_at < '2026-10-15 18:30:00' GROUP BY user_id" % IN)
WEAK = ("SELECT COALESCE(NULLIF(questions.knowledge_tag,''),'未分类') AS tag, "
        "attempts.user_id AS user_id, COUNT(*) AS total, "
        "SUM(CASE WHEN attempt_answers.is_correct THEN 0 ELSE 1 END) AS wrong "
        "FROM attempt_answers "
        "JOIN questions ON questions.id = attempt_answers.question_id "
        "JOIN attempts ON attempts.id = attempt_answers.attempt_id "
        "WHERE attempts.user_id IN %s AND attempt_answers.created_at >= '2026-10-12 00:00:00' "
        "AND attempts.unit_id IN (SELECT id FROM units WHERE class_id = 1) "
        "GROUP BY tag, attempts.user_id" % IN)


def measure(label, sql, times=3):
    rows = pages = 0
    best = None
    for _ in range(times):
        c0 = status()
        t0 = time.time() * 1000.0
        out, _ = q(sql)
        ms = time.time() * 1000.0 - t0
        c1 = status()
        rows = c1['Innodb_rows_read'] - c0['Innodb_rows_read']
        pages = c1['Innodb_buffer_pool_read_requests'] - c0['Innodb_buffer_pool_read_requests']
        best = ms if best is None else min(best, ms)
    ex, _ = q('EXPLAIN ' + sql)
    plan = []
    for l in ex.splitlines():
        c = l.split('\t')
        if len(c) >= 12:
            plan.append('%s/%s/%s/rows=%s/%s' % (c[3], c[4], c[6], c[9], c[11]))
    print('%-30s 扫过行 %-8d 逻辑页读 %-8d 最快 %7.1f ms' % (label, rows, pages, best))
    print('      plan: %s' % ' | '.join(plan[:4]))


print('== 阶段一：基线（现有 6 个 xp_ledger 索引 / 4 个 attempt_answers 索引）==')
measure('本周 XP 求和', WEEK_XP)
measure('薄弱知识点 JOIN', WEAK)

print()
print('== 阶段二：试装候选索引 ==')
print(q("CREATE INDEX idx_xp_ledger_user_created_delta ON xp_ledger(user_id, created_at, delta)")[1].strip() or '  xp_ledger 索引已建')
print(q("CREATE INDEX idx_attempt_answers_attempt_created ON attempt_answers(attempt_id, created_at, question_id, is_correct)")[1].strip() or '  attempt_answers 索引已建')
measure('本周 XP 求和', WEEK_XP)
measure('薄弱知识点 JOIN', WEAK)

print()
print('== 阶段三：同秒反证（IGNORE INDEX 强制走老路）==')
measure('本周 XP 求和（忽略新索引）',
        WEEK_XP.replace('FROM xp_ledger', 'FROM xp_ledger IGNORE INDEX (idx_xp_ledger_user_created_delta)'))
measure('薄弱知识点（忽略新索引）',
        WEAK.replace('FROM attempt_answers',
                     'FROM attempt_answers IGNORE INDEX (idx_attempt_answers_attempt_created)'))

print()
out, _ = q("SHOW INDEX FROM xp_ledger")
print('xp_ledger 现有索引：' + ', '.join(sorted(set(l.split('\t')[2] for l in out.splitlines() if l.strip()))))
out, _ = q("SHOW INDEX FROM attempt_answers")
print('attempt_answers 现有索引：' + ', '.join(sorted(set(l.split('\t')[2] for l in out.splitlines() if l.strip()))))
print()
print('注：两个索引已试装在试点库上，未写进模型；确认有效后再决定是否落模型 + 是否删掉被覆盖的旧索引。')