r"""复验：把「接着上次答」提示条改到靠上之后，390x664 短屏上提示条不再压住刚揭示的正确项。
并把这一帧（含提示条在场）替换成 canonical 读数。
"""
import io, json, os
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\dfjq\Documents\Obsidian Vault\Projects\四六级游戏化课堂\evidence\S13-2026-10-15-zcode\walkthrough-recheck-final"
TOKEN = io.open(r"C:\Users\dfjq\AppData\Local\Temp\s13_recheck_token.txt", encoding="utf-8").read().strip()
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

PROBE = """() => {
  const t = document.querySelector('.van-toast');
  const tr = t ? t.getBoundingClientRect() : null;
  const panel = document.querySelector('.feedback.show');
  const zone = document.querySelector('.answerpanel .optzone');
  const pr = panel ? panel.getBoundingClientRect() : null;
  const zr = zone.getBoundingClientRect();
  const panelTop = Math.min(pr ? pr.top : innerHeight, innerHeight);
  function info(e) {
    if (!e) return null;
    const r = e.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const hit = (cy >= 0 && cy <= innerHeight - 1) ? document.elementFromPoint(cx, cy) : null;
    const vis = Math.max(0, Math.min(r.bottom, panelTop) - Math.max(r.top, zr.top));
    return { text: e.innerText.replace(/\\s+/g,' ').trim().slice(0,30),
             top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1), h: +r.height.toFixed(1),
             visiblePx: +vis.toFixed(1), fullyVisible: vis >= r.height - 0.5,
             hitIsThisOption: hit ? (hit === e || (hit.closest && hit.closest('.opt') === e)) : null,
             hitDesc: hit ? (String(hit.className || '') || hit.tagName) : null };
  }
  return { viewportH: innerHeight, viewportW: innerWidth,
           panelH: panel ? panel.offsetHeight : 0,
           panelRectTop: pr ? +pr.top.toFixed(1) : null,
           panelMaxH: panel ? getComputedStyle(panel).maxHeight : null,
           bandAbovePanel: +(panelTop - zr.top).toFixed(1),
           qcardMaxH: (() => { const q = document.querySelector('.qcard');
             return q ? getComputedStyle(q).maxHeight : null; })(),
           toast: t ? { text: (t.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40),
                        top: +tr.top.toFixed(1), bottom: +tr.bottom.toFixed(1),
                        display: getComputedStyle(t).display } : null,
           panelText: panel ? panel.innerText.replace(/\\s+/g,' ').trim().slice(0,140) : null,
           rightOpt: info(zone.querySelector('.opt.right')),
           pickedOpt: info(zone.querySelector('.opt.wrong') || zone.querySelector('.opt.picked')) };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 664}, device_scale_factor=3,
                        is_mobile=True, has_touch=True, user_agent=UA)
    ctx.add_init_script("try{localStorage.setItem('cet46_token', %s);}catch(e){}" % json.dumps(TOKEN))
    pg = ctx.new_page()
    pg.goto("http://127.0.0.1/s/", wait_until="domcontentloaded")
    pg.wait_for_selector(".node.current .card .go", timeout=20000)
    pg.wait_for_timeout(400)
    if pg.locator(".tgt-overlay").count():
        pg.locator(".tgt-card.c4").click()
        pg.wait_for_selector(".tgt-overlay", state="detached", timeout=10000)
        pg.wait_for_timeout(800)
    pg.locator(".strip").filter(has_text="选词填空").click()
    pg.wait_for_selector(".pvcard .act", timeout=15000)
    pg.locator(".pvcard .act").click()
    pg.wait_for_selector(".opt", timeout=20000)
    pg.wait_for_timeout(600)
    enter = pg.evaluate(PROBE)
    print("进关时提示条：", json.dumps(enter["toast"], ensure_ascii=False))
    pg.locator(".opt").nth(0).click()
    pg.wait_for_selector(".feedback.show", timeout=10000)
    pg.wait_for_timeout(500)
    while_toast = pg.evaluate(PROBE)
    print("答题后（提示条仍在场）：", json.dumps({k: while_toast[k] for k in
          ("panelH", "panelRectTop", "bandAbovePanel", "toast", "rightOpt")}, ensure_ascii=False))
    png = os.path.join(OUT, "09b-A-feedback-practice-390x664.png")
    pg.screenshot(path=png)
    ctx.close(); b.close()

M = json.load(io.open(os.path.join(OUT, "recheck-final-measurements.json"), encoding="utf-8"))
prev = M["A"].get("practice-390x664-blank1")
M["A"]["practice-390x664-blank1_before_toastfix"] = prev
M["A"]["practice-390x664-blank1"] = while_toast
M["meta"]["toast_fix"] = ("「接着上次答」提示条由默认居中改为靠上，复测：提示条在场时正确项仍整行可见且命中自身；"
                          "修复前同帧读数留在 A.practice-390x664-blank1_before_toastfix")
io.open(os.path.join(OUT, "recheck-final-measurements.json"), "w", encoding="utf-8").write(
    json.dumps(M, ensure_ascii=False, indent=2))
with io.open(os.path.join(OUT, "recheck-final-run.log"), "a", encoding="utf-8") as f:
    f.write("[复验] 390x664：「接着上次答」提示条改靠上后，提示条在场时正确项 %s~%s 露出 %s px，"
            "命中自身=%s（修复前该点被提示条挡住）；截图已替换\n"
            % (while_toast["rightOpt"]["top"], while_toast["rightOpt"]["bottom"],
               while_toast["rightOpt"]["visiblePx"], while_toast["rightOpt"]["hitIsThisOption"]))
print("已并回 json+log；截图 %d 字节" % os.path.getsize(png))