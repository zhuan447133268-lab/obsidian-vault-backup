"""生成 S10.5 验收用的题库 xlsx。

结构（每个班一份，内容相同）——两份分套都造，因为组卷有两条硬规则要验：
  · 「同一份卷只能用一个分套的题」→ 需要一份六级题来撞这条；
  · 「发布前对齐分套」→ 需要一份纯六级卷发到四级班，撞「班里没人备考这个分套」。

单元 1「起跑线」（四级，week 1）——组卷的主力题源，题型铺开覆盖 5 种，验「按题型自动分关」：
  关 1 · 听力预热   listening 2 题  知识点=短对话场景
  关 2 · 高频词     vocab     3 题  知识点=词义辨析
  关 3 · 语法陷阱   grammar   2 题  知识点=虚拟语气
  关 4 · 长文速读   reading   2 题  知识点=长难句拆解
  关 5 · 单元 Boss  boss/translation 2 题 知识点=固定搭配

单元 2「六级加练」（六级，week 2）：
  关 1 · 六级词汇   vocab     2 题  知识点=六级词义辨析

正确答案全是 A（与原型题库同口径），选项是 4 个英文词的 `|` 分隔串。
"""
import sys

import openpyxl

HEAD = ['班级', '单元序号', '单元名称', '关卡序号', '关卡名称', '关卡类型', '限时(分钟)', '是否Boss',
        '备考目标', '题型', '题干', '选项', '正确答案', '考点', '解析', '知识点', '难度', '启用']

# (单元序号, 单元名, 关卡序号, 关卡名, 关卡类型, 题型, 备考目标, 知识点, 题数)
LEVELS = [
    # 关卡类型只认 vocab/grammar/reading/review/boss（导入器白名单），题型才认 listening——
    # 这一关的"听力"体现在**题型**上（组卷按题型分关），关卡类型借用 vocab。
    (1, '起跑线', 1, '第 1 关 · 听力预热', 'vocab', 'listening', '4', '短对话场景', 2),
    (1, '起跑线', 2, '第 2 关 · 高频词', 'vocab', 'vocab', '4', '词义辨析', 3),
    (1, '起跑线', 3, '第 3 关 · 语法陷阱', 'grammar', 'grammar', '4', '虚拟语气', 2),
    (1, '起跑线', 4, '第 4 关 · 长文速读', 'reading', 'reading', '4', '长难句拆解', 2),
    (1, '起跑线', 5, '第 5 关 · 单元 Boss', 'boss', 'translation', '4', '固定搭配', 2),
    (2, '六级加练', 1, '第 1 关 · 六级词汇', 'vocab', 'vocab', '6', '六级词义辨析', 2),
]


def rows_for(cls):
    out = []
    for week, uname, seq, name, ltype, qtype, band, tag, n in LEVELS:
        for i in range(1, n + 1):
            stem = "%s 第 %d 题：选出最恰当的一项。" % (tag, i)
            options = "%s-A|%s-B|%s-C|%s-D" % (qtype, qtype, qtype, qtype)
            out.append([cls, week, uname, seq, name, ltype, 8, '是' if ltype == 'boss' else '否',
                        band, qtype, stem, options, 'A',
                        '考点：%s #%d' % (tag, i), '解析：本题考的是「%s」（S10.5 验收自建题库）。' % tag,
                        tag, 1, '是'])
    return out


def main(path, cls):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '题库'
    ws.append(HEAD)
    rows = rows_for(cls)
    for r in rows:
        ws.append(r)
    wb.save(path)
    print("写出 %s（班级=%s，%d 题）" % (path, cls, len(rows)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])