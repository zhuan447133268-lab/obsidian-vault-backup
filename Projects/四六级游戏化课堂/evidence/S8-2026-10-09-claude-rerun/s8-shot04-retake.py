# -*- coding: utf-8 -*-
"""重拍 04：重开后的公开榜滚到低名次区，证明重开有真实数据（帧自然不同）。"""
import io, json, sys, time, urllib.request
from playwright.sync_api import sync_playwright

HERE = sys.argv[1]
API = "http://127.0.0.1:8080"; WEB = "http://127.0.0.1:5174"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
urls404 = []

def login(u, p):
    req = urllib.request.Request(API + "/api/auth/login",
        data=json.dumps({"username": u, "password": p}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

stu = login("S8F", "S8demo2026")
tea = login("T0001", "Teacher@456")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    page = b.new_page(viewport={"width": 390, "height": 844})
    page.on("response", lambda r: urls404.append(r.url) if r.status == 404 else None)
    page.goto(WEB + "/s/", wait_until="networkidle")
    page.evaluate("t => localStorage.setItem('cet46_token', t)", stu["data"]["token"])
    page.goto(WEB + "/s/rank", wait_until="networkidle")
    time.sleep(1.5)
    m = page.locator("text=选择备考目标")
    if m.count() and m.first.is_visible():
        page.locator("button:has-text('四级')").first.click(); time.sleep(1.2)
    page.wait_for_selector(".board", timeout=15000)
    # 直接确认当前公开（此前脚本已拨回），滚到榜尾再拍重开帧
    rows = page.locator(".board .row, .board > div")
    n = rows.count()
    if n:
        rows.nth(n - 1).evaluate("el => el.scrollIntoView({block:'end'})")
    time.sleep(0.8)
    page.screenshot(path=HERE + "/s8-browser-04-after-open.png")
    b.close()
print("404 urls:", urls404 or "none")
