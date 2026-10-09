# -*- coding: utf-8 -*-
"""S8 Claude 复验截图：真 Chrome 390x844，公开榜/我的明细/关闭态/重开四帧。"""
import io, json, sys, time, urllib.request
from playwright.sync_api import sync_playwright

HERE = sys.argv[1] if len(sys.argv) > 1 else "."
API = "http://127.0.0.1:8080"
WEB = "http://127.0.0.1:5174"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def toggle(tea_tok, public):
    cid = class12_id()
    req = urllib.request.Request(API + "/api/admin/rank-toggle",
        data=json.dumps({"classId": cid, "public": public}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tea_tok})
    urllib.request.urlopen(req).read()

def class12_id():
    import pymysql
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE name='S8联赛验收班'")
            return int(cur.fetchone()[0])
    finally:
        conn.close()

def db_conn():
    import pymysql, os
    pwd = ""
    with io.open(r"D:\claude-work\cet46-game\server\.env", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_PASSWORD="):
                pwd = line.strip().split("=", 1)[1]
    return pymysql.connect(host="127.0.0.1", port=3307, user="cet46", password=pwd, database="cet46")

def login(username, pwd):
    req = urllib.request.Request(API + "/api/auth/login",
        data=json.dumps({"username": username, "password": pwd}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

stu = login("S8F", "S8demo2026")
if stu.get("mustChangePwd"):
    sys.exit("S8F 仍在未改密状态")
tea = login("T0001", "Teacher@456")

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(WEB + "/s/", wait_until="networkidle")
    page.evaluate("t => localStorage.setItem('cet46_token', t)", stu["data"]["token"])
    page.goto(WEB + "/s/rank", wait_until="networkidle")
    time.sleep(1.5)

    # 首进目标弹层（若出现）：点「四级」
    modal = page.locator("text=选择备考目标")
    if modal.count() and modal.first.is_visible():
        page.locator("button:has-text('四级')").first.click()
        time.sleep(1.2)

    page.wait_for_selector(".board", timeout=15000)
    time.sleep(1.0)
    page.screenshot(path=HERE + "/s8-browser-01-rank-public.png")

    # 我的明细：滚到 mine-card
    card = page.locator(".mine-card")
    if card.count():
        card.first.evaluate("el => el.scrollIntoView({block:'start'})")
        time.sleep(0.8)
    page.screenshot(path=HERE + "/s8-browser-02-mine-detail.png")

    # 教师关榜 → 10s 轮询自动反映
    toggle(tea["data"]["token"], False)
    page.wait_for_selector(".hidden-card", timeout=20000)
    time.sleep(0.8)
    page.screenshot(path=HERE + "/s8-browser-03-rank-closed.png")

    # 重开
    toggle(tea["data"]["token"], True)
    page.wait_for_selector(".board", timeout=20000)
    time.sleep(0.8)
    page.screenshot(path=HERE + "/s8-browser-04-after-open.png")

    browser.close()

print("console errors:", [e for e in errors if "favicon" not in e] or "none")
