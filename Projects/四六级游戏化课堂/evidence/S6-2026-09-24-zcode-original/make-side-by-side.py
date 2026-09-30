# 并排图：把 S6 学生端答题页的真机截图与原型 quiz.html 截图拼成一张（验收③「与原型比对」）。
# 用法：python make-side-by-side.py   （在本目录执行；PYTHONUTF8=1 避免中文路径/文字问题）
#
# 左=真机（390×844 视口，e2e-quiz.py 在真实环境跑的实录），右=原型 quiz.html（390×844 手机框）。
# 两侧都在 shots/ 下，成对的状态一一对应：题目 / 答对反馈 / 答错反馈 / 通关结算 / 爱心扣完 / Boss 成绩单。
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
S = lambda n: os.path.join('shots', n)
PAIRS = [
    ("cmp-390-question.png", S("shot-chain-L25-question.png"), S("proto-question.png"),
     "S6 学生端答题（真数据 · 四级 L25 高频词）", "原型 quiz.html 第 1 关"),
    ("cmp-390-feedback-ok.png", S("shot-chain-L25-feedback-ok.png"), S("proto-feedback-ok.png"),
     "S6 答对反馈（💡解析 + 连击）", "原型 答对反馈"),
    ("cmp-390-feedback-no.png", S("shot-failmixed-L25-feedback-no.png"), S("proto-feedback-no.png"),
     "S6 答错反馈（正确答案 + 💡解析，爱心 -1）", "原型 答错反馈"),
    ("cmp-390-settlement.png", S("shot-chain-L25-settlement-clear.png"), S("proto-settlement-clear.png"),
     "S6 通关结算（星级 + 逐题回顾 + XP 明细）", "原型 通关结算"),
    ("cmp-390-fail.png", S("shot-failmixed-L25-settlement-fail.png"), S("proto-settlement-fail.png"),
     "S6 爱心扣完（本次得分已作废）", "原型 爱心扣完"),
    ("cmp-390-boss.png", S("shot-chain-L30-settlement-boss.png"), S("proto-settlement-boss.png"),
     "S6 Boss 710 分制成绩单（真数据）", "原型 单元 Boss 成绩单"),
]
GAP = 24
BAR = 44


def font(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(out, left, right, title_l, title_r):
    a = Image.open(os.path.join(HERE, left)).convert("RGB")
    b = Image.open(os.path.join(HERE, right)).convert("RGB")
    h = max(a.height, b.height) + BAR
    w = a.width + b.width + GAP * 3
    canvas = Image.new("RGB", (w, h), (18, 16, 38))
    canvas.paste(a, (GAP, BAR))
    canvas.paste(b, (GAP * 2 + a.width, BAR))
    draw = ImageDraw.Draw(canvas)
    f = font(18)
    draw.text((GAP + 4, 13), title_l, fill=(255, 255, 255), font=f)
    draw.text((GAP * 2 + a.width + 4, 13), title_r, fill=(255, 215, 110), font=f)
    canvas.save(os.path.join(HERE, out))
    print("{}: {} | {} -> {}".format(out, a.size, b.size, canvas.size))


for row in PAIRS:
    compose(*row)
    print('  左=' + row[1] + '  右=' + row[2])