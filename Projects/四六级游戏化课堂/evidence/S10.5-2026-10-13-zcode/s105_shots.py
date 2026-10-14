# -*- coding: utf-8 -*-
"""S10.5 走查截图的机械校验（图由浏览器子代理实拍，本脚本只判真伪）。

为什么要机械校验：截图是最容易被"看起来做了"糊弄的产物——
  · 宽度不是验收口径（教师 1440 / 学生 390）→ 不是要求的那个界面宽度；
  · 高度只有一屏 → 内层滚动容器把整页截成同一帧（S8 踩过：4 张图 hash 相同）；
  · 图与图两两相同 → 实际只截了一张，剩下是复制；
  · 全白/全黑 → 页面根本没渲染出来（接口 500、白屏、跳登录）。
这几条都能在不看图的前提下判死，所以放在脚本里，而不是靠"我看着没问题"。

两条宽度口径：教师端 PC 是 1440x900，学生端 H5 是 390x844（手机竖屏）。
高度下限按**实测**写（同一次走查的第一轮结果），不是想当然：
内容不足一屏时整页就等于一屏，所以教师端 900、学生端 844 是天然下限；
长页面（工作台 1117、公共题库 1335、地图 2120/1840）比一屏高，正是"整页截的是内容全高"
的正向对照——如果哪天这些长页面缩回一屏高，就是内层滚动容器又把它裁了。

用法：python s105_shots.py   → 打印每张图的尺寸/hash，最后写 99-shots.txt（断言数 失败数）。
"""
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow：python -m pip install pillow")
    sys.exit(2)

TEACHER_W, TEACHER_MIN_H = 1440, 900
STUDENT_W, STUDENT_MIN_H = 390, 844

# (文件名, 说明, 期望宽度, 高度下限)
#
# 带 ★ 的是修完走查撞出的三处问题后补拍的回归现场（12 草稿回显 6 题 / 13 旧链接提示语 /
# 14 双栏角标），与其它图放在同一次走查里对比着看。
SHOTS = [
    ("01-login.png", "教师端登录页", TEACHER_W, TEACHER_MIN_H),
    ("02-paper-workbench.png", "组卷工作台（已组卷列表 + 我的题库选题池）", TEACHER_W, 1100),
    ("03-paper-public-bank.png", "教研室公共题库 tab（分享后可见 + 出题教师真名）", TEACHER_W, 1300),
    ("04-paper-compose.png", "组卷：勾题 + 按题型自动分关预览", TEACHER_W, 1100),
    ("05-paper-publish.png", "发布弹窗（目标班 / 到期时间 / 分享开关）", TEACHER_W, 1100),
    ("06-paper-published.png", "发布成功：状态=已发布、落点班级、到期时间", TEACHER_W, 1100),
    ("07-student-map.png", "学生地图页「本周练习」区块（练习卷入口在教学链之上）", STUDENT_W, 2000),
    ("08-student-quiz.png", "学生答题页（练习口径：只记逐题分 / 限时倒计时）", STUDENT_W, STUDENT_MIN_H),
    ("09-student-result.png", "学生结算页（「练习完成！」无三星、无满分加成）", STUDENT_W, STUDENT_MIN_H),
    ("10-student-entry-gone.png", "关闭后学生地图：该练习入口消失", STUDENT_W, 1700),
    ("11-paper-closed.png", "教师端关闭后：状态=已关闭、落点标注（已关闭）", TEACHER_W, 1100),
    ("12-draft-edit-fixed.png", "★ 草稿「编辑」回显 6 题（原缺陷：读回 0 题）+ 落点标注（未发布）", TEACHER_W, 1100),
    ("13-stale-link-closed.png", "★ 旧链接进已结束的练习卷：提示「本次练习已结束」", STUDENT_W, STUDENT_MIN_H),
    ("14-badge-fixed.png", "★ 双栏角标都不为 0（原瑕疵：非激活栏恒显 0）——停在「我的题库」栏", TEACHER_W, 1100),
    ("14b-badge-public-tab.png", "★ 同上，切到「公共题库」栏：非激活的「我的题库」角标同样非 0", TEACHER_W, 1300),
]

total = failed = 0
msgs = []


def check(ok, desc, detail=""):
    global total, failed
    total += 1
    if ok:
        print("  [OK]   %s" % desc)
    else:
        failed += 1
        line = "  [FAIL] %s %s" % (desc, detail)
        print(line)
        msgs.append(line)


def stats(path):
    """返回 (w, h, sha1, ink, bg)：ink 是"非纯背景像素占比"，用来判白屏/黑屏。"""
    with io.open(path, "rb") as f:
        raw = f.read()
    sha = hashlib.sha1(raw).hexdigest()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    small = im.resize((min(w, 240), min(h, 480)))
    px = list(small.getdata())
    from collections import Counter
    bg, bg_n = Counter(px).most_common(1)[0]
    ink = 1.0 - bg_n / float(len(px))
    return w, h, sha, ink, bg


print("== S10.5 走查截图校验（%d 张：教师 1440 / 学生 390）==" % len(SHOTS))
hashes = {}
for name, label, want_w, min_h in SHOTS:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        check(False, "%s 存在" % label, "缺 %s" % name)
        continue
    w, h, sha, ink, bg = stats(path)
    check(w == want_w, "%s：宽度 %dpx" % (label, want_w), "实际 %dx%d" % (w, h))
    check(h >= min_h, "%s：整页高 ≥%d（不足一屏时整页=一屏）" % (label, min_h),
          "实际 %dx%d" % (w, h))
    check(ink >= 0.01, "%s：有实际渲染内容（非白屏/黑屏）" % label,
          "内容像素占比 %.4f，主色 %s" % (ink, bg))
    hashes[name] = sha
    print("         %s %dx%d ink=%.4f sha1=%s" % (name, w, h, ink, sha[:12]))

# 两两不同：同一帧复制出来的图在这里现形。
names = list(hashes)
dups = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        if hashes[names[i]] == hashes[names[j]]:
            dups.append("%s == %s" % (names[i], names[j]))
check(not dups, "%d 张截图两两不同（不是同一帧复制）" % len(hashes), "; ".join(dups))

with io.open(os.path.join(HERE, "99-shots.txt"), "w", encoding="utf-8") as f:
    f.write("%d %d\n" % (total, failed))
print("\n[S10.5-SHOTS] 断言 %d 条 / 失败 %d" % (total, failed))
for m in msgs:
    print(m)
sys.exit(1 if failed else 0)