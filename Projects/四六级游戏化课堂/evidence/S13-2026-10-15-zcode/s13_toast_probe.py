# -*- coding: utf-8 -*-
"""探针：那个挡在选项上的 van-toast 到底是什么、多大、多久消失。"""
import io, json, time
from playwright.sync_api import sync_playwright
TOKEN = io.open(r"C:\Users\dfjq\AppData\Local\Temp\s13_recheck_token.txt", encoding="utf-8").read().strip()
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
PROBE = """() => {
  const t = document.querySelector('.van-toast');
  if (!t) return { toast: null };
  const r = t.getBoundingClientRect(); const cs = getComputedStyle(t);
  const right = document.querySelector('.opt.right');
  const rr = right ? right.getBoundingClientRect() : null;
  return { toast: t.innerText.replace(/\s+/g,' ').trim().slice(0,60),
           box: { top:+r.top.toFixed(1), bottom:+r.bottom.toFixed(1), h:+r.height.toFixed(1) },
           pos: cs.position, z: cs.zIndex, opacity: cs.opacity, transition: cs.transition.slice(0,40),
           rightOptBox: rr ? { top:+rr.top.toFixed(1), bottom:+rr.bottom.toFixed(1) } : null,
           toastCoversRightCenter: (rr && t.contains(document.elementFromPoint(rr.left+rr.width/2, rr.top+rr.height/2))) };
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
    pg.locator(".opt").nth(0).click()
    pg.wait_for_selector(".feedback.show", timeout=10000)
    for i in range(10):
        pg.wait_for_timeout(2000)
        d = pg.evaluate(PROBE)
        print(i*2+2, "秒：", json.dumps(d, ensure_ascii=False)[:260], flush=True)
        if d.get("toast") is None:
            break
    ctx.close(); b.close()
