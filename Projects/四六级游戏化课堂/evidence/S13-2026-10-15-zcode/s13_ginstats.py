# -*- coding: utf-8 -*-
"""把 gin 访问日志（[GIN] 行）按端点汇总成延迟分布 —— 服务端口径，与 locust 客户端口径互为印证。

为什么要服务端口径：locust 是客户端，绿色线程+单进程，40 并发时它自己也会占 CPU；
「慢」到底是服务端慢还是压测机慢，只有服务端自己记的时间能分清。gin.Logger() 写在
router.go 里，逐请求带耗时，正好是这份底账。

用法：python s13_ginstats.py <gin日志路径> [端点过滤子串...]
"""
import re
import sys

LINE = re.compile(r'\[GIN\].*?\|\s*(\d{3})\s*\|\s*([0-9.a-zµu]+)\s*\|\s*\S+\s*\|\s*([A-Z]+)\s+"([^"]+)"')


def parse_dur(s):
    """Go 的 time.Duration.String()：1h2m3.4s / 1.2ms / 456µs / 78ns / 0s。"""
    s = s.replace('µ', 'u')
    if s in ('0s', '0'):
        return 0.0
    total = 0.0
    # 单位必须从长到短排：写 (h|m|s|ms|us|ns) 的话 "17.0063ms" 会先被 'm' 吃掉，
    # 17 毫秒被读成 17 分钟——这个坑踩过一次，报表直接离谱一个数量级。
    for val, unit in re.findall(r'([0-9.]+)(ns|us|ms|h|m|s)', s):
        v = float(val)
        total += {'h': 3600.0, 'm': 60.0, 's': 1.0, 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9}[unit] * v
    return total * 1000.0  # ms


def pct(sorted_ms, p):
    if not sorted_ms:
        return None
    k = (len(sorted_ms) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_ms) - 1)
    return sorted_ms[lo] + (sorted_ms[hi] - sorted_ms[lo]) * (k - lo)


def main():
    path = sys.argv[1]
    filters = sys.argv[2:]
    groups = {}
    total = 0
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if '[GIN]' not in line:
                continue
            m = LINE.search(line)
            if not m:
                continue
            status, dur, method, full = m.group(1), m.group(2), m.group(3), m.group(4)
            p = full.split('?')[0]
            if filters and not any(fl in full for fl in filters):
                continue
            key = '%s %s' % (method, p)
            g = groups.setdefault(key, {'ms': [], 'ng': 0})
            try:
                g['ms'].append(parse_dur(dur))
            except Exception:
                continue
            if status[0] in '45':
                g['ng'] += 1
            total += 1
    rows = sorted(groups.items(), key=lambda kv: -len(kv[1]['ms']))
    print('%-34s %7s %7s %8s %8s %8s %8s %9s' % ('端点', '样本', '5xx/4xx', 'p50', 'p90', 'p95', 'p99', 'max'))
    print('-' * 100)
    for key, g in rows:
        ms = sorted(g['ms'])
        print('%-34s %7d %7d %8.1f %8.1f %8.1f %8.1f %9.1f'
              % (key, len(ms), g['ng'], pct(ms, 50), pct(ms, 90), pct(ms, 95), pct(ms, 99), ms[-1]))
    print('-' * 100)
    print('合计 GIN 行：%d' % total)


if __name__ == '__main__':
    main()