# -*- coding: utf-8 -*-
"""验收④ 1440px 走查截图的机械校验（图由浏览器子代理产出，本脚本只判真伪）。

为什么要机械校验：截图是最容易被"看起来做了"糊弄的产物——
  · 宽度不是 1440 → 不是验收口径的桌面宽度；
  · 高度只有一屏 → 内层滚动容器把整页截成同一帧（S8 踩过：4 张图 hash 相同）；
  · 图与图两两相同 → 实际只截了一张，剩下是复制；
  · 全白/全黑 → 页面根本没渲染出来（接口 500、白屏）。
这几条都能在不看图的前提下判死，所以放在脚本里，而不是靠"我看着没问题"。

用法：python s10_shots.py   → 打印每张图的尺寸/hash，最后写 99-shots.txt（断言数 失败数）。
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

W = 1440
# 每张图的最小高度。
#
# 视口是 1440x900，所以"整页截图"的下限就是 900（内容不足一屏时，整页就等于一屏）。
# 曾经把看板（02/03/05）也卡在 1520，是照搬"长页面"的想当然——实测看板在 1440 宽下
# 内容高只有 818 / 703 / 818（左栏 380px 两列布局，一屏放得下），页内没有任何内层
# 滚动容器（.wrap 770==770 overflow visible、.stu-wrap 355==355 六行全见），
# 900 高的图与"按内容高重截"逐像素相同 → 900 就是它的整页。
#
# "截图会随内容变高"这条机制另外用正向对照证明：07 审计 1196、08 校级 1099，
# 都比视口高——说明截图不是简单裁一屏，内容长了它真会长。
#
# 隐患备忘：.stu-wrap 是内层滚动容器（max-height 430px）。如果拿大班（如 52 人的
# 校级名单班）截看板，必须先 style.maxHeight='none'; style.overflow='visible'，
# 否则明细只截到滚动窗口内的几行，而 outerHeight 看起来"完整"——S8 踩过同款。
SHOTS = [
    ("01-login.png", "教师端登录页", 900),
    ("02-dashboard.png", "班级看板（数据卡/趋势/薄弱点/明细，内容高 818）", 900),
    ("03-class-switch.png", "切到第二个班后的看板（内容高 703）", 900),
    ("04-adjust-dialog.png", "调关弹窗（含「教师放行」样本）", 900),
    ("05-rank-off.png", "公开排行榜开关关闭态（内容高 818）", 900),
    ("06-export.png", "导出平时成绩表（下载提示）", 900),
    ("07-audit.png", "审计日志查询页（三类动作，长页面正向对照）", 901),
    ("08-school.png", "校级汇总视图（admin，长页面正向对照）", 901),
    # 09/10 是走查撞出的两处缺陷修完后的回归现场（同目录，同一次走查的续拍）：
    # 09 = 全新 context（localStorage 0 个 key）冷启动进看板，验证不再整页报错；
    # 10 = 审计页中文化后（分页「共 40 条」、占位「请选择」，正文无 Select/Total）。
    ("09-cold-start.png", "冷启动回归：全新浏览器进看板（无预设 localStorage）", 900),
    ("10-audit-zh.png", "审计页中文化回归（分页/占位符中文）", 901),
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
    """返回 (w, h, sha1, ink)：ink 是"非纯背景像素占比"，用来判白屏。"""
    with io.open(path, "rb") as f:
        raw = f.read()
    sha = hashlib.sha1(raw).hexdigest()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    small = im.resize((min(w, 240), min(h, 480)))
    px = list(small.getdata())
    # 取出现最多的颜色当背景，其余算"有内容"。
    from collections import Counter
    bg, bg_n = Counter(px).most_common(1)[0]
    ink = 1.0 - bg_n / float(len(px))
    return w, h, sha, ink, bg


print("== 验收④ 1440px 走查截图校验（%d 张）==" % len(SHOTS))
hashes = {}
for name, label, min_h in SHOTS:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        check(False, "%s 存在" % label, "缺 %s" % name)
        continue
    w, h, sha, ink, bg = stats(path)
    check(w == W, "%s：宽度 1440px" % label, "实际 %dx%d" % (w, h))
    check(h >= min_h, "%s：整页高 ≥%d（视口 900，内容不足一屏时整页=一屏）" % (label, min_h),
          "实际 %dx%d" % (w, h))
    check(ink >= 0.01, "%s：有实际渲染内容（非白屏/黑屏）" % label,
          "内容像素占比 %.4f，主色 %s" % (ink, bg))
    hashes[name] = sha
    print("         %s %dx%d ink=%.4f sha1=%s" % (name, w, h, ink, sha[:12]))

# 两两不同：同一帧复制出来的图在这里现形。
names = [n for n in hashes]
dups = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        if hashes[names[i]] == hashes[names[j]]:
            dups.append("%s == %s" % (names[i], names[j]))
check(not dups, "%d 张截图两两不同（不是同一帧复制）" % len(hashes), "; ".join(dups))

with io.open(os.path.join(HERE, "99-shots.txt"), "w", encoding="utf-8") as f:
    f.write("%d %d\n" % (total, failed))
print("\n[S10-SHOTS] 断言 %d 条 / 失败 %d" % (total, failed))
for m in msgs:
    print(m)
sys.exit(1 if failed else 0)