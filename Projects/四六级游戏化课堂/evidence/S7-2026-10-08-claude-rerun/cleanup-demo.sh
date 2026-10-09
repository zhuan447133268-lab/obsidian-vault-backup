#!/usr/bin/env bash
# 清掉 S7 验收的演示数据（S7A/S7B/S7C/S7D 的队/成员/提醒/成绩）。
# 演示数据默认**故意留着**（验收①②③的证据落在库里）；要恢复干净底账再跑这个。
#   用法：bash cleanup-demo.sh            # 只清数据，保留账号
#         bash cleanup-demo.sh --users    # 连演示账号一起删
set -uo pipefail
export MYSQL_PWD="$(grep -m1 '^DB_PASSWORD=' /d/claude-work/cet46-game/server/.env | tr -d '\r' | cut -d= -f2-)"
MYSQL=(mysql -h127.0.0.1 -P3307 -ucet46 -N -B --default-character-set=utf8mb4 cet46)

"${MYSQL[@]}" -e "
  DELETE r FROM cet46.reminders r JOIN cet46.users u ON u.id=r.from_user WHERE u.username LIKE 'S7%';
  DELETE r FROM cet46.reminders r JOIN cet46.users u ON u.id=r.to_user WHERE u.username LIKE 'S7%';
  DELETE tm FROM cet46.team_members tm JOIN cet46.users u ON u.id=tm.user_id WHERE u.username LIKE 'S7%';
  DELETE t FROM cet46.teams t JOIN cet46.users u ON u.id=t.leader_id WHERE u.username LIKE 'S7%';
  DELETE aa FROM cet46.attempt_answers aa JOIN cet46.attempts a ON a.id=aa.attempt_id JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S7%';
  DELETE l FROM cet46.xp_ledger l JOIN cet46.users u ON u.id=l.user_id WHERE u.username LIKE 'S7%';
  DELETE w FROM cet46.wrong_book w JOIN cet46.users u ON u.id=w.user_id WHERE u.username LIKE 'S7%';
  DELETE d FROM cet46.diagnoses d JOIN cet46.users u ON u.id=d.user_id WHERE u.username LIKE 'S7%';
  DELETE a FROM cet46.attempts a JOIN cet46.users u ON u.id=a.user_id WHERE u.username LIKE 'S7%';
"
echo "S7 演示数据已清（队/成员/提醒/成绩）"

if [ "${1:-}" = "--users" ]; then
  "${MYSQL[@]}" -e "DELETE FROM cet46.users WHERE username LIKE 'S7%';"
  echo "S7 演示账号已删"
fi

echo "剩下的 S7 用户行："
"${MYSQL[@]}" -e "SELECT username, class_id FROM cet46.users WHERE username LIKE 'S7%' ORDER BY username;"