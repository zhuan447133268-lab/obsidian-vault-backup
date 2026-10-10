# -*- coding: utf-8 -*-
# Claude 复跑补拍：真 Chromium 无头 390x844 截 S9 五屏（等价 Zcode 09 步产物）
import json, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
TOK = json.loads((HERE / "demo-tokens.json").read_text(encoding="utf-8"))
WEB = "http://127.0.0.1:5174"


def arm(page, token, uid):
    page.add_init_script(
        "localStorage.setItem('cet46_token', %s);"
        "localStorage.setItem('cet46_target_confirmed', JSON.stringify({[%s]:'1'}));"
        % (json.dumps(token), json.dumps(str(uid)))
    )


def shoot(page, name):
    page.screenshot(path=str(HERE / name))
    print("shot", name)


with sync_playwright() as p:
    b = p.chromium.launch()
    errors = []

    # S9A（uid=307）：me 顶部 / 商城区块 / 宠物区 / 明细
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    arm(pg, TOK["S9A"], 307)
    pg.goto(WEB + "/s/me", wait_until="networkidle")
    pg.wait_for_timeout(600)
    shoot(pg, "s9-browser-01-me-top.png")
    pg.get_by_text("福利兑换").first.scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    shoot(pg, "s9-browser-02-shop.png")
    pg.get_by_text("奶酪").first.scroll_into_view_if_needed()
    pg.wait_for_timeout(400)
    shoot(pg, "s9-browser-03-pet.png")
    pg.goto(WEB + "/s/ledger", wait_until="networkidle")
    pg.wait_for_timeout(600)
    shoot(pg, "s9-browser-05-ledger.png")
    pg.close()

    # S9B（uid=308）：复盘页
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    arm(pg, TOK["S9B"], 308)
    pg.goto(WEB + "/s/review", wait_until="networkidle")
    pg.wait_for_timeout(600)
    shoot(pg, "s9-browser-04-review.png")
    pg.close()

    b.close()
    print("console_errors:", len(errors))
    for e in errors[:5]:
        print("ERR:", e[:200])
