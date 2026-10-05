#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁风险自查（去答案化五条的可执行版）— BDCI26 提交件专用。

判据来源：
  · 2026-09-29 公示表清零话术：「未过门禁，在 skill 和 manifest 中写死了情节答案」
  · Obsidian 主索引 §3.5.15 五「去答案化五条」
  · §3.5.15 四-补二 的跨版字节同一性实测（**基线 = `solution-v20.zip`，它在 09-23 过了门禁拿 60.33**）

方法：把提交件与 **v20 的 profile** 逐类比对。
  · ① 「§2.7 类」词汇（旁白/查表/台账/择低险/满配/直读信号…）—— v20 = 0 ⇒ 任何新件都必须 0，命中即 FAIL。
  · ② 「读数型」月键链条（M13→M15 且上下文是风险读数）—— v20 = 0 ⇒ 命中即 FAIL。
     （注意：**晋升节奏型**的 M18 → M36 这类在 v20 里就有，属已通过构造，不算。）
  · ③④⑤ 事件 ID / 单局叙述 / 引擎内部符号 —— 以 **v20 的计数为上限**；超出即标 ▲。
  · ⑥ 取证 token 集合（运行产物 ID / 事件 ID / 第 N 局编号 / 月链）—— **v20 集合之外的新 token = ▲ 新增取证**；
      其中**运行产物 ID（20xxxxxxTxxxxxxZ）是 v20 完全没有的种类**，新件口径下一律 FAIL。

用法：
  python gate-risk-scan.py <submission.zip | solution_dir> [--tag vNN] [--baseline <v20zip>]

退出码：0 = 通过；1 = FAIL；2 = 参数/读取错误。
注意：门禁是「自动化反作弊 + 人工审核」，本脚本通过 ≠ 一定过门禁，只覆盖"已知触发类 + 已通过基线之外的增量"。
"""
import io
import os
import re
import sys
import zipfile

BASELINE_DEFAULT = r"D:\华为openjiuwen-Agent职场生存与晋升挑战\CareerSim-BDCI26\submissions\solution-v20.zip"

CLASSES = [
    ("① §2.7 类词汇（引擎文本作判据/打法脚本口吻）",
     r"(旁白|打了水漂|好巧不巧|直读信号|读数闸门|择低险|满配|"
     r"observe\.events|events\s*里|输出里出现|看到这句|读到这句)"),
    ("② 读数型月键链条", r"M\d{1,2}\s*→\s*M\d{1,2}[^\n]{0,24}(读数|风险|隐患|排雷|爆雷)"),
    ("③ 事件 ID 级答案与「安全支」处方", r"((?:sc_evt|lc_evt)\d{3}|安全支|安全线)"),
    ("④ 单局实战叙述（第 N 局 / 完整彩排 / 抽样局）", r"(第\s*\d{1,2}\s*局|完整彩排|抽样局)"),
    ("⑤ 引擎内部符号直读", r"(hidden_risk|RISK_LEVEL_MAP|output_snapshot|failure_conditions|"
                    r"health_zero\.data|risk_burst\.data)"),
    ("⑥ 运行产物 ID（本机 run 时间戳）", r"\b20\d{6}T\d{6}Z\b"),
]


def load(path):
    """返回 {文件相对名: 文本}，只取 SKILL.md 与 manifest.json。"""
    out = {}
    if os.path.isdir(path):
        for root, _d, files in os.walk(path):
            for f in files:
                if f in ("SKILL.md", "manifest.json"):
                    fp = os.path.join(root, f)
                    out[os.path.relpath(fp, path).replace("\\", "/")] = io.open(
                        fp, encoding="utf-8", errors="replace").read()
    else:
        with zipfile.ZipFile(path) as zf:
            for n in zf.namelist():
                if n.endswith("SKILL.md") or n.endswith("manifest.json"):
                    out[n] = zf.read(n).decode("utf-8", errors="replace")
    return out


def counts(texts):
    body = "\n".join(texts.values())
    return {label: len(re.findall(pat, body)) for label, pat in CLASSES}


def tokens(texts):
    s = "\n".join(texts.values())
    t = set()
    t |= {("runid", x) for x in re.findall(r"\b20\d{6}T\d{6}Z\b", s)}
    t |= {("evtid", x) for x in re.findall(r"\b(?:sc_evt|lc_evt)\d{3}\b", s)}
    t |= {("round", x) for x in re.findall(r"第\s*(\d{1,2})\s*局", s)}
    t |= {("mchain", x.replace(" ", "")) for x in re.findall(r"M\d{1,2}\s*→\s*M\d{1,2}", s)}
    return t


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
    tag = tag.lstrip("-").replace("solution-", "")
    bp = sys.argv[sys.argv.index("--baseline") + 1] if "--baseline" in sys.argv else BASELINE_DEFAULT
    if not args:
        print(__doc__)
        return 2
    target = args[0]
    texts = load(target)
    if not texts:
        print("[ERROR] 没找到 SKILL.md / manifest.json：%s" % target)
        return 2

    legacy = tag in ("v20", "v23", "v27")
    have_base = os.path.exists(bp)
    base_c = counts(load(bp)) if have_base else {}
    base_t = tokens(load(bp)) if have_base else set()

    print("== 门禁风险自查（去答案化五条 + v20 基线比对）==")
    print("目标：%s%s" % (target, "（tag=%s）" % tag if tag else ""))
    for n in sorted(texts):
        print("      %s（%d 字符）" % (n, len(texts[n])))
    print("基线：%s%s" % (bp, "" if have_base else "  ⚠️ 基线包不存在，退化为「仅查①②⑥」"))
    print()

    cur_c = counts(texts)
    fails, warns = [], []
    for label, _p in CLASSES:
        c = cur_c[label]
        b = base_c.get(label)
        if not have_base:
            mark = "OK" if c == 0 else "FAIL"
            if c and label.startswith(("①", "②", "⑥")):
                fails.append(label)
            print("[%s] %s = %d" % (mark, label, c))
            continue
        if c == 0:
            print("[OK]   %s = 0（基线 %s）" % (label, b))
        elif b is not None and c <= b:
            print("[BASE] %s = %d（基线 %d，未超出已通过构造）" % (label, c, b))
        else:
            hard = label.startswith(("①", "②", "⑥"))
            print("[%s] %s = %d（基线 %d ⇒ 超出）" % ("FAIL" if hard else "WARN", label, c, b))
            (fails if hard else warns).append("%s = %d > 基线 %d" % (label, c, b))

    if have_base:
        new_t = sorted(tokens(texts) - base_t)
        if new_t:
            print()
            print("▲ 超出 v20 基线的**新增取证 token**（%d 个）：" % len(new_t))
            for k, v in new_t:
                print("      [%s] %s" % (k, v))
            if any(k == "runid" for k, _v in new_t):
                (fails if not legacy else warns).append("新增运行产物 ID")

    print()
    if fails:
        print("VERDICT: FAIL —— %s" % "；".join(fails))
        print("         ⇒ 按 §3.5.15 五 删改后重打包，重新过 ⑨ 项自检（不得上件）")
        return 1
    if warns:
        print("VERDICT: PASS（带提示）—— %s" % "；".join(warns))
        print("         ⇒ 提示项属 v20/v23/v27 家族**已被平台两次实证通过**的构造"
              "（§3.5.15 四-补二）；新件（非 legacy tag）一律按 §五 清零")
        return 0
    print("VERDICT: PASS —— 五类全部不超基线、无新增取证 token")
    return 0


if __name__ == "__main__":
    sys.exit(main())