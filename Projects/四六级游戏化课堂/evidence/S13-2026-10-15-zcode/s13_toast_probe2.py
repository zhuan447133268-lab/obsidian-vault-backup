# -*- coding: utf-8 -*-
"""探针2：把页面上所有 .van-toast / .van-popup 逐个列出（盒子、文本、pointer-events），
判断那个「命中点被挡」到底是真的可见浮层，还是残留的空节点。"""
import io, json
from playwright.sync_api import sync_playwright
TOKEN = io.open(r"C:\Users\dfjq\AppData\Local\Temp\s13_recheck_token.txt", encoding="utf-8").read().strip()
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
PROBE = """() => {
  const dump = (sel) => Array.from(document.querySelectorAll(sel)).map((e) => {
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return { cls: String(e.className).slice(0, 70), text: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0,40),
             box: [+r.left.toFixed(0), +r.top.toFixed(0), +r.width.toFixed(0), +r.height.toFixed(0)],
             pe: cs.pointerEvents, opacity: cs.opacity, display: cs.display, visibility: cs.visibility };
  });
  const right = document.querySelector('.opt.right');
  const rr = right ? right.getBoundingClientRect() : null;
  return { toasts: dump('.van-toast'), popups: dump('.van-popup').slice(0,6), overlays: dump('.van-overlay'),
           rightOptBox: rr ? [+rr.top.toFixed(0), +rr.bottom.toFixed(0)] : null,
           hitAtRightCenter: (() => { if (!rr) return null;
             const e = document.elementFromPoint(rr.left+rr.width/2, rr.top+rr.height/2);
             return e ? (String(e.className).slice(0,60) || e.tagName) : null; })() };
}"""
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width":390,"height":664}, device_scale_factor=3, is_mobile=True,
                        has_touch=True, user_agent=UA)
    ctx.add_init_script("try{localStorage.setItem('cet46_token', %s);}catch(e){}" % json.dumps(TOKEN))
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1/s/", wait_until="domcontentloaded")
    pg.wait_for_selector(".node.current .card .go", timeout=20000); pg.wait_for_timeout(400)
    if pg.locator(".tgt-overlay").count():
        pg.locator(".tgt-card.c4").click(); pg.wait_for_selector(".tgt-overlay", state="detached"); pg.wait_for_timeout(800)
    pg.locator(".strip").filter(has_text="选词填空").click()
    pg.wait_for_selector(".pvcard .act", timeout=15000); pg.locator(".pvcard .act").click()
    pg.wait_for_selector(".opt", timeout=20000); pg.wait_for_timeout(500)
    print("答题前：", json.dumps(pg.evaluate(PROBE), ensure_ascii=False)[:500], flush=True)
    pg.locator(".opt").nth(0).click()
    pg.wait_for_selector(".feedback.show", timeout=10000)
    for t in (800, 3000, 6000):
        pg.wait_for_timeout(t)
        print("答后 +%dms：" % t, json.dumps(pg.evaluate(PROBE), ensure_ascii=False)[:700], flush=True)
    ctx.close(); b.close()
