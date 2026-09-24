# -*- coding: utf-8 -*-
"""解析 Obsidian Vault 的 wikilink 关系，输出知识星系图数据 JSON。"""
import os, re, json, sys

VAULT = r"D:/Users/dfjq/Documents/Obsidian Vault"
OUT = r"D:/培训temp/knowledge_graph.json"

SKIP_DIRS = {".obsidian", ".git", ".obsidian-mcp-trash", "node_modules", ".claudian"}

wiki_re = re.compile(r"\[\[([^\]]+)\]\]")
tag_re = re.compile(r"(?:^|\s)#([A-Za-z0-9_\u4e00-\u9fff/\-]+)")

def collect_files(root):
    files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.lower().endswith(".md"):
                files.append(os.path.join(dp, f))
    return files

def rel(p):
    return os.path.relpath(p, VAULT)

def group_of(p):
    parts = p.split(os.sep)
    top = parts[0] if parts else "(root)"
    # Projects 巨文件夹拆到二级子项目上色，星系更有意义
    if top == "Projects" and len(parts) > 1:
        return parts[1]
    return top

def parse_md(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        text = ""
    # frontmatter 跳过
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end+4:]
    links = []
    for m in wiki_re.finditer(text):
        inner = m.group(1)
        target = inner.split("|")[0].split("#")[0].strip()
        if target:
            links.append(target)
    tags = []
    for m in tag_re.finditer(text):
        t = m.group(1)
        # 排除看起来像标题的（已被 [ 包裹的不含 #，这里再排除纯数字锚点）
        if not t.startswith(("http",)):
            tags.append(t)
    # 标题 + 摘要
    title = None
    summary = None
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if title is None:
                title = s.lstrip("#").strip()
            continue
        if summary is None:
            summary = s
            break
    return links, tags, title, summary

def main():
    files = collect_files(VAULT)
    # 名称 -> 相对路径（大小写不敏感）
    name_map = {}
    nodes = []
    for p in files:
        base = os.path.splitext(os.path.basename(p))[0]
        key = base.lower()
        if key not in name_map:
            name_map[key] = rel(p)
        links, tags, title, summary = parse_md(p)
        nodes.append({
            "id": rel(p),
            "name": base,
            "title": title or base,
            "group": group_of(rel(p)),
            "tags": tags,
            "summary": (summary or "")[:160],
            "out": links,
        })
    id_by_name = {os.path.splitext(os.path.basename(n["id"]))[0].lower(): n["id"] for n in nodes}

    edges = []
    dangling = 0
    adj = {n["id"]: set() for n in nodes}
    ghost_ids = set()
    for n in nodes:
        seen = set()
        for t in n["out"]:
            tid = id_by_name.get(t.lower())
            if tid is None:
                # 幽灵节点：计划写但未创建的笔记
                gid = "ghost::" + t
                if gid not in ghost_ids:
                    ghost_ids.add(gid)
                    adj[gid] = set()
                    nodes.append({
                        "id": gid,
                        "name": t,
                        "title": t,
                        "group": "（待写笔记）",
                        "tags": [],
                        "summary": "（此笔记尚未创建，是某篇笔记中引用但缺失的目标）",
                        "out": [],
                        "ghost": True,
                    })
                tid = gid
                dangling += 1
            if tid == n["id"] or tid in seen:
                continue
            seen.add(tid)
            adj[n["id"]].add(tid)
    for a, ts in adj.items():
        for b in ts:
            edges.append({"s": a, "t": b})

    # 度（被链接数 in-degree，hub 更大）
    indeg = {n["id"]: 0 for n in nodes}
    for e in edges:
        indeg[e["t"]] += 1
    for n in nodes:
        n["in"] = indeg[n["id"]]
        n["out_count"] = len(adj.get(n["id"], set()))

    data = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "notes": len(nodes),
            "edges": len(edges),
            "dangling": dangling,
        }
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    print("notes=%d edges=%d dangling=%d" % (len(nodes), len(edges), dangling))
    # 打印 top 文件夹分布
    from collections import Counter
    c = Counter(n["group"] for n in nodes)
    for k, v in c.most_common():
        print("  %-22s %d" % (k, v))
    # top hubs
    hubs = sorted(nodes, key=lambda x: x["in"], reverse=True)[:12]
    print("--- top hubs (被链接最多) ---")
    for h in hubs:
        print("  [%d] %s  (%s)" % (h["in"], h["title"], h["group"]))

if __name__ == "__main__":
    main()
