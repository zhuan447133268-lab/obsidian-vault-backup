"""生成 S12 验收用的题库 xlsx：一个单元 / 三个关卡 / 每关两题。

三个关卡各有用途：
  L1「词汇一」——摆**上一个赛季窗口内**的首刷（赛季结算用的名单从这里算）；
  L2「词汇二」——摆**本周窗口内**的首刷（周榜/名次线用的名单从这里算）；
  L3「词汇三」——S12 主验收班的学生真打（取卷→全对交卷），走真实链路拿 XP 去兑券。

关卡类型只认导入器白名单（vocab/grammar/reading/review/boss）；单元落在教学带
（week_no=9 < 100），不碰 S10.5 的卷私有带（≥100）。
"""
import sys

import openpyxl

HEAD = ['班级', '单元序号', '单元名称', '关卡序号', '关卡名称', '关卡类型', '限时(分钟)', '是否Boss',
        '备考目标', '题型', '题干', '选项', '正确答案', '考点', '解析', '知识点', '难度', '启用']

LEVELS = [
    (1, '词汇一', 'vocab', 'vocab', '词义辨析', 2),
    (2, '词汇二', 'vocab', 'vocab', '词义搭配', 2),
    (3, '词汇三', 'vocab', 'vocab', '熟词僻义', 2),
]
WEEK = 9
UNIT = 'S12验收单元'


def rows_for(cls):
    out = []
    for seq, name, ltype, qtype, tag, n in LEVELS:
        for i in range(1, n + 1):
            stem = '%s 第 %d 题：选出最恰当的一项。' % (tag, i)
            out.append([cls, WEEK, UNIT, seq, name, ltype, 8, '否', '4', qtype, stem,
                        '%s-A|%s-B|%s-C|%s-D' % (qtype, qtype, qtype, qtype), 'A',
                        '考点：%s #%d' % (tag, i),
                        '解析：本题考的是「%s」（S12 验收自建题库）。' % tag, tag, 1, '是'])
    return out


def main(path, cls):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '题库'
    ws.append(HEAD)
    for r in rows_for(cls):
        ws.append(r)
    wb.save(path)
    print("写出 %s（班级=%s，%d 题）" % (path, cls, len(LEVELS) * 2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])