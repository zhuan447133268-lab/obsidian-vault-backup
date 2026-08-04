---
description: 个人创作工作台首页，上方情绪入口，下方工作入口
tags:
  - dashboard
  - desk
  - homepage
---

# 早上好，小可爱

> _把高频动作放在离自己最近的地方。_

---

## 🌅 情绪入口

今天打开 Obsidian，先给自己一个愿意靠近的理由。
![[jimeng-2026-06-10-8161-微信图片_20260610093702_357_51保留小男孩的面部特征和发型A....png]]


---

## 🚀 今天从这里开始

| 入口                                                | 用途               |
| ------------------------------------------------- | ---------------- |
| [[工作台/选题库\|选题库]]                                  | 看看最近有什么选题在推进     |
| [[Dashboards/剪藏内容管理仪表盘\|剪藏仪表盘]]                   | 处理 inbox 里的待整理内容 |
| [[WeeklyReports/周报_2026-W24\|本周周报]]               | 写复盘、看这周进度        |
| [[Projects/烟台AI培训项目\|烟台AI培训项目]]                   | 当前重点项目           |
| [[Excalidraw/Drawing 2026-07-14 14.52.57\|最近一张图]] | 继续改图 / 画新图       |

---

## ✍️ 最近在推进

```dataview
TABLE WITHOUT ID
  file.link AS "笔记",
  status AS "状态",
  source AS "来源",
  date AS "日期"
FROM #topic OR #writing OR #idea
WHERE status != "done" AND status != "archived"
SORT file.mtime DESC
LIMIT 8
```

> 如果这里为空，说明你还没有用 `status` 字段。先去 [[工作台/选题库\|选题库]] 建几个选题。

---

## 🎨 最近的画布 / 图

```dataview
TABLE WITHOUT ID
  file.link AS "文件",
  file.mtime AS "修改时间"
FROM "Excalidraw"
SORT file.mtime DESC
LIMIT 5
```

---

## ⏳ 本周人生脚本

```dataview
TABLE WITHOUT ID
  file.link AS "日期",
  work AS "工作",
  writing AS "写作",
  family AS "家庭",
  sleep AS "睡眠"
FROM #journal/daily
WHERE date >= date(today) - dur(7 days)
SORT date DESC
LIMIT 7
```

> 还没开始记录？先记三天，再回头可视化。参考 [[工作台/人生脚本]]。

---

## 🤖 AI 协作入口

- 打开 [[工作台/选题库\|选题库]]，让 AI 帮你拆选题
- 打开任意一篇文章，让 AI 改稿、调结构、起标题
- 放进一篇对标文章，让 AI 拆标题 / 开头 / 结构 / 情绪

> 右侧固定你的 AI 侧边栏（Claude / ChatGPT / Copilot），不要让 AI 和 Obsidian 之间来回复制。

---

## 🛠️ 维护说明

- 每两周回来看一次：哪个入口几乎没点过？删掉或下沉。
- 哪个动作总是要找很久？放到首页。
- [[工作台/我的布局设计\|我的布局设计]] 里有你的 5 个原始答案，改了布局记得同步这里。
