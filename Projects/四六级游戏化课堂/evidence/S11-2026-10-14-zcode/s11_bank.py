"""生成 S11 验收用的题库 xlsx（一个单元、三个关卡、每关两题）。

为什么这么小：S11 验收要的手算是「人在纸上能算出来」的规模——10 条 attempt、
6 道题，指标逐桶逐行都能对。单元落在教学带（week_no=9 < 100），不碰 S10.5 的卷私有带。

关卡类型只认导入器白名单（vocab/grammar/reading/review/boss），「听力」体现在**题型**上
（S10.5 的 s105_bank.py 同口径）。
"""
import sys

import openpyxl

HEAD = ['班级', '单元序号', '单元名称', '关卡序号', '关卡名称', '关卡类型', '限时(分钟)', '是否Boss',
        '备考目标', '题型', '题干', '选项', '正确答案', '考点', '解析', '知识点', '难度', '启用']

# (关卡序号, 关卡名, 关卡类型, 题型, 知识点, 题数)
LEVELS = [
    (1, '词汇一', 'vocab', 'vocab', '词义辨析', 2),
    (2, '词汇二', 'vocab', 'vocab', '词义搭配', 2),
    (3, '听力一', 'vocab', 'listening', '短对话场景', 2),
]
WEEK = 9
UNIT = 'S11验收单元'


def rows_for(cls):
    out = []
    for seq, name, ltype, qtype, tag, n in LEVELS:
        for i in range(1, n + 1):
            stem = '%s 第 %d 题：选出最恰当的一项。' % (tag, i)
            out.append([cls, WEEK, UNIT, seq, name, ltype, 8, '否', '4', qtype, stem,
                        '%s-A|%s-B|%s-C|%s-D' % (qtype, qtype, qtype, qtype), 'A',
                        '考点：%s #%d' % (tag, i),
                        '解析：本题考的是「%s」（S11 验收自建题库）。' % tag, tag, 1, '是'])
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