r"""S13 短屏竖向预算实测：只量，不改。375x667 / 390x664 / 390x700 / 390x844
产出 evidence\...\walkthrough-recheck-final\short-screen-budget.json
"""
import io, json, os, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1"
OUT = r"C:\Users\dfjq\Documents\Obsidian Vault\Projects\四六级游戏化课堂\evidence\S13-2026-10-15-zcode\walkthrough-recheck-final"
TOKEN_FILE = r"C:\Users\dfjq\AppData\Local\Temp\s13_recheck_token.txt"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

STACK = """() => {
  const pick = (sel) => { const e = document.querySelector(sel); if (!e) return null;
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return { top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1), h: +r.height.toFixed(1),
             maxH: cs.maxHeight, clientH: e.clientHeight, scrollH: e.scrollHeight }; };
  return { innerH: innerHeight, innerW: innerWidth, scrollY: window.scrollY,
           docH: document.documentElement.scrollHeight,
           quizscreen: pick('.quizscreen'), answerpanel: pick('.answerpanel'),
           qcard: pick('.qcard'), qtext: pick('.qtext'), optzone: pick('.optzone'),
           wordbank: pick('.wordbank'), feedback: pick('.feedback.show'),
           bankOpts: document.querySelectorAll('.optzone .opt').length,
           visibleOpts: Array.from(document.querySelectorAll('.optzone .opt')).map((e,i)=>{
             const r = e.getBoundingClientRect();
             const panel = document.querySelector('.feedback.show');
             const pt = panel ? panel.getBoundingClientRect().top : innerHeight;
             const clipB = Math.min(innerHeight, pt);
             const clipT = Math.max(0, document.querySelector('.optzone').getBoundingClientRect().top);
             return { i: i, top: +r.top.toFixed(0), bottom: +r.bottom.toFixed(0),
                      vis: +Math.max(0, Math.min(r.bottom, clipB) - Math.max(r.top, clipT)).toFixed(0) };
           }) };
}"""


def run(rows):
    token = io.open(TOKEN_FILE, encoding="utf-8").read().strip()
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        for w, h in rows:
            tag = "%dx%d" % (w, h)
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=3,
                                is_mobile=True, has_touch=True, user_agent=UA)
            ctx.add_init_script("try{localStorage.setItem('cet46_token', %s);}catch(e){}"
                                % json.dumps(token))
            pg = ctx.new_page()
            pg.goto(BASE + "/s/", wait_until="domcontentloaded")
            pg.wait_for_selector(".node.current .card .go", timeout=20000)
            pg.wait_for_timeout(400)
            if pg.locator(".tgt-overlay").count():
                pg.locator(".tgt-card.c4").click()
                pg.wait_for_selector(".tgt-overlay", state="detached", timeout=10000)
                pg.wait_for_timeout(700)
            unit = pg.locator(".unit").filter(has_text="UNIT 11")
            unit.locator(".node.current .card .go").click()
            pg.wait_for_selector(".pvcard .act", timeout=15000)
            res[tag + ".before"] = pg.evaluate(STACK)
            pg.locator(".pvcard .act").click()
            pg.wait_for_selector(".opt", timeout=20000)
            pg.wait_for_timeout(600)
            res[tag + ".quiz_nofeedback"] = pg.evaluate(STACK)
            pg.locator(".opt").nth(0).click()
            pg.wait_for_selector(".feedback.show", timeout=10000)
            pg.wait_for_timeout(900)
            res[tag + ".feedback_open"] = pg.evaluate(STACK)
            print(tag, json.dumps(res[tag + ".feedback_open"], ensure_ascii=False)[:400], flush=True)
            ctx.close()
        b.close()
    io.open(os.path.join(OUT, "short-screen-budget.json"), "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run([(375, 667), (390, 664), (390, 700), (390, 844)]))