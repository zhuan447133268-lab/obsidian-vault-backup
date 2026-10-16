-- cet46 建库建号（MySQL 8，utf8mb4）。
-- 用法（先把下面两处 __CT46_STRONG_PWD__ 换成同一个随机强口令再执行）：
--   mysql -u root -p --execute="source deploy/sql/000_mysql_init.sql"
-- docker compose 起库时由 MYSQL_DATABASE/MYSQL_USER 环境变量自动完成同等初始化，
-- 本文件用于公司现成 MySQL 手工初始化场景。
-- 同时授 @'localhost'（本机直连）与 @'%'（容器/远程）两种来源。
--
-- 【上线铁律】占位串 __CT46_STRONG_PWD__ 必须替换成 64 位随机强口令后才可执行；
-- 本文件里出现任何"看起来像口令"的示例值都只是占位，禁止照抄上线（部署文档 §4.5）。
-- 生成一条（PowerShell，无需管理员权限）：
--   -join ((48..57 + 65..90 + 97..122 + 33 + 35 + 36 + 37 + 42 + 43 + 45 + 61 + 63) | Get-Random -Count 64 | % {[char]$_})
-- 生成后同时把同一个口令写进 server\.env 的 DB_PASSWORD（该文件不进 git）。
-- 注意：MySQL 的 CREATE USER 不接受变量作口令，所以占位串只能就地替换。

CREATE DATABASE IF NOT EXISTS `cet46`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'cet46'@'localhost' IDENTIFIED BY '__CT46_STRONG_PWD__';
ALTER USER 'cet46'@'localhost' IDENTIFIED BY '__CT46_STRONG_PWD__';
GRANT ALL PRIVILEGES ON `cet46`.* TO 'cet46'@'localhost';

CREATE USER IF NOT EXISTS 'cet46'@'%' IDENTIFIED BY '__CT46_STRONG_PWD__';
ALTER USER 'cet46'@'%' IDENTIFIED BY '__CT46_STRONG_PWD__';
GRANT ALL PRIVILEGES ON `cet46`.* TO 'cet46'@'%';

FLUSH PRIVILEGES;