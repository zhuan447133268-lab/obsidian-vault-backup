"""生成 S10 验收用的题库 xlsx（自己写，带知识点，才能让「薄弱知识点 TOP」有真数据）。

结构（每个班一份，内容相同）：
  单元 1「起跑线」
    第 1 关 · 高频词      vocab   5 题   知识点=词义辨析
    第 2 关 · 语法陷阱    grammar 5 题   知识点=虚拟语气
    第 3 关 · 长文速读    reading 5 题   知识点=长难句拆解
    第 4 关 · 单元 Boss   boss    3 题   知识点=固定搭配（锁定，需前三关通关）
正确答案全部是 A（与原型题库同口径），选项是 4 个英文词的 `|` 分隔串。
"""
import sys

import openpyxl

HEAD = ['班级', '单元序号', '单元名称', '关卡序号', '关卡名称', '关卡类型', '限时(分钟)', '是否Boss',
        '备考目标', '题型', '题干', '选项', '正确答案', '考点', '解析', '知识点', '难度', '启用']

LEVELS = [
    (1, '第 1 关 · 高频词', 'vocab', 'vocab', '词义辨析', 5),
    (2, '第 2 关 · 语法陷阱', 'grammar', 'grammar', '虚拟语气', 5),
    (3, '第 3 关 · 长文速读', 'reading', 'reading', '长难句拆解', 5),
    # Boss 是「关卡类型」，题型仍要走白名单（translation）——两者不是一回事。
    (4, '第 4 关 · 单元 Boss', 'boss', 'translation', '固定搭配', 3),
]


def rows_for(cls):
    out = []
    for seq, name, ltype, qtype, tag, n in LEVELS:
        for i in range(1, n + 1):
            stem = "%s 第 %d 题：选出最恰当的一项。" % (tag, i)
            options = "%s-A|%s-B|%s-C|%s-D" % (qtype, qtype, qtype, qtype)
            out.append([cls, 1, '起跑线', seq, name, ltype, 8, '是' if ltype == 'boss' else '否',
                        '4', qtype, stem, options, 'A',
                        '考点：%s #%d' % (tag, i), '解析：本题考的是「%s」（S10 验收自建题库）。' % tag,
                        tag, 1, '是'])
    return out


def main(path, cls):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '题库'
    ws.append(HEAD)
    for r in rows_for(cls):
        ws.append(r)
    wb.save(path)
    print("写出 %s（班级=%s，%d 题）" % (path, cls, len(rows_for(cls))))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])