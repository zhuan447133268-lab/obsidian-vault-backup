#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁自查 v2（标准版）—— BDCI26 提交件专用。替换 v1（gate-risk-scan.py）。

为什么有 v2（v1 的方法错误，必须记住）
--------------------------------------
v1 的判据是「与 `solution-v20.zip` 逐类比对，v20 的计数即上限」。
它的隐含前提是「v20 过了门禁 ⇒ v20 的内容安全」。
2026-10-03 该前提被证伪：`v27c` 与 `v20` 的 SKILL.md 只有 3 处句子级差异、
整包 26 个文件里 24 个字节相同，v20 拿 60.33（无备注），v27c 却被判
「未过门禁，在 skill 中写死了情节答案」。
⇒ **拿一个「曾经通过」的样本当安全基线是自证循环**：v1 只能发现相对 v20 的
   *增量*，永远发现不了 v20 与 v27c 共有的那份核心内容 —— 而那正是触发面。

v2 的判据（来自平台判语本身，不是来自任何样本）
----------------------------------------------
来源 = 四天 36 条 0.00 行的备注原文（evidence-zero-rows-4days-2026-10-01.txt）
＋ 员工手册的信息边界（手册明示下列内容为「隐藏信息，只能靠自然语言推断」：
   晋升所需分数、谈话结果、绩效计算指数、潜在隐患、随机事件触发概率）。
＋ 官方 README 的目录结构要求。

对每一类，**标准是 0 命中**，不与任何历史包比较：

  L1 事件编号与事件级答案      ----- 事件 ID、安全支/安全线/最优支/标准答案
  L2 台账/查表/映射表          ----- 把事件后果预先写成查表、对照表、速查
  L3 模拟器内部符号            ----- hidden_risk / *.data / RISK_LEVEL_MAP / 源码、反解
  L4 数据挖掘统计              ----- dev 全集/数据集/dev 满局 + 命中数/百分比
  L5 单局复盘叙述              ----- 第 N 局 / 完整彩排 / 抽样局 / 实测 X 局
  L6 运行产物 ID               ----- 20xxxxxxTxxxxxxZ
  L7 隐藏阈值数字              ----- 逐级晋升阈值数字表、上限×1.2、绩效公式系数
  L8 逐选项数值抄录            ----- 选项文本同现英文属性增量（Skill+2/Output−2 等）
  L9 包结构                    ----- 缺 manifest.json / 缺 skills/*/SKILL.md / mode 非 agent

用法：
  python gate-risk-scan-v2.py <submission.zip | solution_dir> [--ws <solution_dir>]

退出码：0 = 全绿；1 = 有命中；2 = 参数/读取错误。
注意：本工具是**必要条件**检查，不是门禁的替代品；它只覆盖已归约的判语类别。
"""

import hashlib
import io
import os
import re
import sys
import zipfile

# ---------------------------------------------------------------- 判据

RULES = [
    ("L1 事件编号与事件级答案",
     r"((?:sc_evt|lc_evt|evt)[_\-]?\d{2,4}|安全支|安全线|最优支|标准答案|正确答案)"),
    ("L2 台账/查表/映射表",
     r"(台账|查表|速查表|对照表|映射表|预先写成|事先知道|背下这张表)"),
    ("L3 模拟器内部符号与解码自述",
     r"(hidden_risk|RISK_LEVEL_MAP|output_snapshot|failure_conditions|"
     r"health_zero\.data|risk_burst\.data|salary_conditions|half_year_performance_bonus|"
     r"[\w/]+\.data\b|源码级|源码复核|源码反解|数据集反解|反解|解码规则)"),
    ("L4 数据挖掘统计",
     r"(dev\s*(全量|全集|满局|数据集)|全库\s*\d|数据集\s*\d|命中\s*\d+\s*(个|/)|"
     r"\d+\s*/\s*\d+\s*(为负|带健康|扣减))"),
    ("L5 单局复盘叙述",
     r"(第\s*\d{1,2}\s*局|完整彩排|抽样局|实测\s*\d+\s*局|局里|那一局)"),
    ("L6 运行产物 ID",
     r"\b20\d{6}T\d{6}Z\b"),
    ("L7 隐藏阈值数字",
     r"(门槛\s*[=＝]?\s*\d|阈值\s*\d|上限\s*[=＝]?\s*(门槛\s*)?×?\s*1\.2|门槛×1\.2|"
     r"职级调整|L5\s*−\s*4|绩效\s*=\s*round|3\.5\s*×\s*perf)"),
    ("L8 逐选项数值抄录",
     r"((?:Skill|Network|Output|Health|Dignity|Wealth)\s*[+＋−-]\s*\d[^。\n]{0,40}"
     r"(?:[+＋−-]\s*\d)?)"),
]

STRUCT = [
    ("L9a manifest.json 存在", None),
    ("L9b skills/*/SKILL.md 存在", None),
    ("L9c mode == agent", None),
]


def load_zip(path):
    out = {}
    with zipfile.ZipFile(path) as zf:
        for n in zf.namelist():
            if n.endswith("/"):
                continue
            out[n] = zf.read(n).decode("utf-8", "replace")
    return out


def load_dir(path):
    out = {}
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            fp = os.path.join(dp, f)
            rel = os.path.relpath(fp, path).replace("\\", "/")
            out[rel] = io.open(fp, encoding="utf-8", errors="replace").read()
    return out


def scan(texts):
    hits = []
    for name in sorted(texts):
        body = texts[name]
        for label, pat in RULES:
            for m in re.finditer(pat, body):
                line = body.count("\n", 0, m.start()) + 1
                hits.append((label, name, line, m.group(0)[:60]))
    return hits


def structure_checks(texts):
    res = []
    keys = [k for k in texts if k.endswith("manifest.json")]
    res.append(("L9a manifest.json 存在", bool(keys), ",".join(keys) or "缺失"))
    sk = [k for k in texts if k.endswith("/SKILL.md") or k.endswith("SKILL.md")]
    res.append(("L9b skills/*/SKILL.md 存在", bool(sk), ",".join(sk) or "缺失"))
    mode_ok, mode_val = False, "?"
    for k in keys:
        txt = texts[k]
        m = re.search(r'"mode"\s*:\s*"([^"]*)"', txt)
        if m:
            mode_val = m.group(1)
            mode_ok = mode_val == "agent"
    res.append(("L9c mode == agent", mode_ok, mode_val))
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ws = sys.argv[sys.argv.index("--ws") + 1] if "--ws" in sys.argv else ""
    if not args:
        print(__doc__)
        return 2
    target = args[0]
    if not os.path.exists(target):
        print("[ERROR] 找不到目标：%s" % target)
        return 2
    texts = load_zip(target) if target.lower().endswith(".zip") else load_dir(target)

    print("== 门禁自查 v2（标准版：按判语类别扫**全包**，标准 = 0 命中）==")
    print("目标：%s" % target)
    print("文件数：%d（全包扫描，不只看 SKILL.md/manifest.json）" % len(texts))
    for n in sorted(texts):
        print("      %-52s %7d 字符" % (n, len(texts[n])))
    print()

    hits = scan(texts)
    by = {}
    for label, name, line, tok in hits:
        by.setdefault(label, []).append((name, line, tok))

    allgreen = True
    for label, _pat in RULES:
        got = by.get(label, [])
        if not got:
            print("  OK    %s" % label)
            continue
        allgreen = False
        print("  FAIL  %s  (%d 处)" % (label, len(got)))
        for name, line, tok in got[:6]:
            print("          %s:%d  %r" % (name, line, tok))
        if len(got) > 6:
            print("          ...（其余 %d 处省略）" % (len(got) - 6))
    print()
    for label, ok, det in structure_checks(texts):
        print(("  OK    " if ok else "  FAIL  ") + label + "  | " + det)
        if not ok:
            allgreen = False

    if ws:
        print()
        print("== zip ↔ 工作区逐字节一致性 ==")
        if os.path.isdir(ws):
            wsx = load_dir(ws)
            ok = bad = 0
            for n in sorted(texts):
                rel = n[len("solution/"):] if n.startswith("solution/") else n
                if rel in wsx:
                    if wsx[rel] == texts[n]:
                        ok += 1
                    else:
                        print("  DIFF  %s" % rel)
                        bad += 1
                else:
                    print("  工作区缺 %s" % rel)
                    bad += 1
            for n in sorted(wsx):
                if not any(k.endswith(n) for k in texts):
                    print("  包内缺（工作区多出） %s" % n)
                    bad += 1
            print("  逐字节一致：%d/%d" % (ok, ok + bad))
            if bad:
                allgreen = False
        else:
            print("  [WARN] 工作区目录不存在：%s" % ws)

    print()
    if allgreen:
        print("VERDICT: ALL GREEN（L1–L9 全 0）")
        print("  说明：这只是必要条件；真实门禁是自动化反作弊 + 人工/模型复核。")
        return 0
    print("VERDICT: FAIL（见上方 FAIL 项）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())