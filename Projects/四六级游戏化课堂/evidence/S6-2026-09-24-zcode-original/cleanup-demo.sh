#!/usr/bin/env bash
# 清掉 S6 演示学生 S6V6A/B/C 与他们的全部闯关/账本数据（run-acceptance.sh 故意不清，
# 因为验收④的账本对账证据就落在库里）。清完再跑 run-acceptance.sh 会从零重建这三个号。
# 用法：bash cleanup-demo.sh
set -uo pipefail
SRV=/d/claude-work/cet46-game/server
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' "$SRV/.env" | tr -d '\r' | cut -d= -f2-)"
# 带上默认库 cet46：多表 DELETE ... JOIN 在没选库时 MySQL 会直接报 1046 No database selected
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)
"${MYSQL[@]}" -e "
DELETE aa FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S6V6%';
DELETE l  FROM cet46.xp_ledger l  JOIN cet46.users u ON u.id=l.user_id WHERE u.username LIKE 'S6V6%';
DELETE w  FROM cet46.wrong_book w JOIN cet46.users u ON u.id=w.user_id WHERE u.username LIKE 'S6V6%';
DELETE d  FROM cet46.diagnoses  d JOIN cet46.users u ON u.id=d.user_id WHERE u.username LIKE 'S6V6%';
DELETE a  FROM cet46.attempts   a JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S6V6%';
DELETE    FROM cet46.users WHERE username LIKE 'S6V6%';"
echo "剩余 S6V6% 账号：$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM cet46.users WHERE username LIKE 'S6V6%';")"
echo "剩余 S6V6% 闯关：$("${MYSQL[@]}" -e "SELECT COUNT(*) FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S6V6%';")"