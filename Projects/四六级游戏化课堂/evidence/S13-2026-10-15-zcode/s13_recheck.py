# 【归档副本说明】复测用的临时口令字面量已置为占位符 <复测临时口令：运行时注入，原文不入仓>；
# 运行原文（含临时口令）只留在本机运行目录，不随 evidence 入仓。
r"""S13 移动视口二次复测（A/F/B/D/E）v3 —— Playwright + 系统 Edge，真手机级模拟。

跑法（临时目录内，不进仓库/工作区）：
    cd C:\Users\dfjq\AppData\Local\Temp && PYTHONUTF8=1 python s13_recheck.py

v3 相对 v2 的改动（都是复跑踩出来的）：
  * 短屏（700 / 664）改在「练习卷」上量 A：计分关 3 颗爱心，点错 3 次关卡直接失败并弹结算浮层，
    会把后续点击全拦住；练习卷答错不结束，可以反复量。
  * 计分关只量 2 空就退出（不再尝试打通），避免把爱心耗光影响后续。
  * 面板顶边改用面板自身的真实 rect（过渡结束后），不再用 zone.bottom 反推。
产物：evidence\S13-2026-10-15-zcode\walkthrough-recheck-final\
    *.png 截图 + recheck-final-measurements.json（原始数字）+ recheck-final-run.log（运行日志）

复跑坑（三轮踩到，写进来防复跑者重复踩）：
  1) 首进必选目标弹层由「设备本地标记」决定，新上下文必弹并拦截点击 —— 要先点当前目标关掉；
  2) 视口高度必须「一开始就是目标高度」：先用 844 建上下文再 set_viewport_size(700)，
     100vh 仍是 844，页面会多出 144px 并自动滚起来 —— 短屏必须新开上下文；
  3) 计分关只有 3 颗爱心，连点同一个选项 3 次就结算 —— 要跑满 10 空请用练习卷（答错不结束）；
  4) 中途退出的计分关是 in_progress、可被下次进关「续用」，已错的题数会带到下一轮，
     所以每轮量完要么打完、要么清掉 attempt 行再进。
"""
import csv
import json
import os
import sys
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1"
OUT = r"C:\Users\dfjq\Documents\Obsidian Vault\Projects\四六级游戏化课堂\evidence\S13-2026-10-15-zcode\walkthrough-recheck-final"
TOKEN_FILE = r"C:\Users\dfjq\AppData\Local\Temp\s13_recheck_token.txt"
ROSTER = r"D:\cet46-pilot\data\学生初始口令-分发后删除.csv"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
M = {"meta": {}, "shots": {}, "A": {}, "F": {}, "B": {}, "D": {}, "E": {}, "errors": []}
LOG = []


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    LOG.append(line)
    print(line, flush=True)


def rec(path, value):
    cur = M
    keys = path.split(".")
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def shot(pg, name):
    p = os.path.join(OUT, name)
    pg.screenshot(path=p)
    M["shots"][name] = os.path.getsize(p)
    log("截图 %s (%d 字节)" % (name, os.path.getsize(p)))


BOX = """(sel) => Array.from(document.querySelectorAll(sel)).map((e, i) => {
  const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  return { i: i, w: +r.width.toFixed(1), h: +r.height.toFixed(1),
           top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1),
           left: +r.left.toFixed(1), right: +r.right.toFixed(1),
           minH: cs.minHeight, minW: cs.minWidth, maxH: cs.maxHeight,
           cls: String(e.className || ''),
           text: (e.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 44) };
})"""

BANK = """() => Array.from(document.querySelectorAll('.wordbank .opt')).map((e) => ({
  label: (e.querySelector('.key') ? e.querySelector('.key').innerText : '').trim(),
  text:  (e.querySelector('.wtext') ? e.querySelector('.wtext').innerText : '').trim(),
  cls: String(e.className || '')
}))"""

QTYPE = """() => {
  const q = document.querySelector('.qtype');
  const fb = document.querySelector('.feedback.show');
  const ans = fb ? fb.querySelector('.ans') : null;
  const right = document.querySelector('.opt.right .key');
  return {
    qtype: q ? q.innerText.replace(/\\s+/g,' ').trim() : null,
    panelAnsLetter: ans ? ans.innerText.replace(/\\s+/g,' ').trim() : null,
    rightKeyLetter: right ? right.innerText.replace(/\\s+/g,' ').trim() : null,
    hasSubmitBtn: !!document.querySelector('.submitbtn'),
    slotCount: document.querySelectorAll('.slots .slot').length,
    bankTitle: (document.querySelector('.banktitle') || {}).innerText || null,
    headText: (document.querySelector('.quizscreen .head') || {}).innerText || null
  };
}"""

AREVEAL = """() => {
  const panel = document.querySelector('.feedback.show');
  const zone = document.querySelector('.answerpanel .optzone');
  if (!zone) return { error: 'no optzone' };
  const panelH = panel ? panel.offsetHeight : 0;
  const pr = panel ? panel.getBoundingClientRect() : null;
  const zr = zone.getBoundingClientRect();
  const panelRectTop = pr ? pr.top : null;
  const panelTop = Math.min(panelRectTop === null ? innerHeight : panelRectTop, innerHeight);
  const clipTop = zr.top;
  const clipBottom = Math.min(zr.bottom, panelTop);
  const right = zone.querySelector('.opt.right');
  const wrong = zone.querySelector('.opt.wrong');
  const pick = zone.querySelector('.opt.picked');
  const picked = wrong || pick || right;
  function info(e) {
    if (!e) return null;
    const r = e.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const hit = (cy >= 0 && cy <= innerHeight - 1) ? document.elementFromPoint(cx, cy) : null;
    const visiblePx = Math.max(0, Math.min(r.bottom, clipBottom) - Math.max(r.top, clipTop));
    return {
      text: e.innerText.replace(/\\s+/g, ' ').trim().slice(0, 30),
      top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1), h: +r.height.toFixed(1),
      overlapWithPanel: +Math.max(0, r.bottom - panelTop).toFixed(1),
      abovePanel: r.bottom <= panelTop + 0.5,
      fullyVisible: visiblePx >= r.height - 0.5,
      visiblePx: +visiblePx.toFixed(1),
      visibleFraction: +(visiblePx / r.height).toFixed(2),
      hitIsThisOption: hit ? (hit === e || (hit.closest && hit.closest('.opt') === e)) : null,
      hitDesc: hit ? (String(hit.className || '') || hit.tagName) : null
    };
  }
  return {
    viewportH: innerHeight, viewportW: innerWidth,
    scrollY: +window.scrollY.toFixed(1), docH: document.documentElement.scrollHeight,
    panelH: panelH,
    panelRectTop: panelRectTop === null ? null : +panelRectTop.toFixed(1),
    panelMaxH: panel ? getComputedStyle(panel).maxHeight : null,
    panelText: panel ? panel.innerText.replace(/\\s+/g, ' ').trim().slice(0, 140) : null,
    bandAbovePanel: +(panelTop - clipTop).toFixed(1),
    qcard: (() => { const q = document.querySelector('.qcard'); if (!q) return null;
      const r = q.getBoundingClientRect();
      return { top: +r.top.toFixed(1), bottom: +r.bottom.toFixed(1), h: +r.height.toFixed(1),
               maxH: getComputedStyle(q).maxHeight, scrollTop: +q.scrollTop.toFixed(1) }; })(),
    zone: { top: +clipTop.toFixed(1), bottom: +zr.bottom.toFixed(1), h: +zr.height.toFixed(1),
            scrollTop: +zone.scrollTop.toFixed(1), scrollHeight: zone.scrollHeight,
            clientHeight: zone.clientHeight,
            inlinePadBottom: zone.style.paddingBottom || '' },
    rightOpt: info(right),
    pickedOpt: info(picked)
  };
}"""

RESET = """() => {
  const zone = document.querySelector('.answerpanel .optzone');
  if (!zone) return { error: 'no optzone' };
  return {
    feedbackShown: !!document.querySelector('.feedback.show'),
    qcardMaxH: (() => { const q = document.querySelector('.qcard');
      return q ? getComputedStyle(q).maxHeight : null; })(),
    inlinePadBottom: zone.style.paddingBottom || '',
    scrollTop: +zone.scrollTop.toFixed(1),
    inlinePadIsCleared: (zone.style.paddingBottom || '') === '',
    scrollTopIsZero: zone.scrollTop === 0
  };
}"""

FKEYS = {
    "map_go": ".node.current .card .go",
    "strip": ".strip",
    "quit": ".quit",
    "me_entry": ".entry",
    "me_review_go": ".review .go",
    "me_back": ".back",
    "accbtn": ".accbtn",
    "rank_switch": ".switch",
    "team_mini": ".member .mini",
    "team_pick": ".pick-btn",
}


def measure_f(pg, key, note=""):
    sel = FKEYS[key]
    try:
        boxes = pg.evaluate(BOX, sel)
    except Exception as e:
        boxes = ["ERR:" + str(e)[:80]]
    rec("F." + key, {"selector": sel, "note": note, "boxes": boxes})
    if isinstance(boxes, list) and boxes and isinstance(boxes[0], dict):
        hs = [b["h"] for b in boxes]
        ws = [b["w"] for b in boxes]
        log("F.%-12s %-30s -> %d 个，高 %s / 宽 %s（最小边 %.1f）"
            % (key, sel, len(boxes), hs, ws, min(min(hs), min(ws))))
    return boxes


def dismiss_picker(pg, where=""):
    if pg.locator(".tgt-overlay").count() == 0:
        return False
    M["D"].setdefault("target_picker_shown_on", []).append(where or "-")
    pg.locator(".tgt-card.c4").click()
    pg.wait_for_selector(".tgt-overlay", state="detached", timeout=10000)
    pg.wait_for_timeout(900)
    log("首进必选目标弹层：已选四级关闭（%s）" % (where or "-"))
    return True


def open_map(pg):
    pg.goto(BASE + "/s/", wait_until="domcontentloaded")
    pg.wait_for_selector(".node.current .card .go", timeout=20000)
    pg.wait_for_timeout(400)
    dismiss_picker(pg, "地图首屏")
    pg.wait_for_timeout(400)


def enter_by(pg, locator):
    open_map(pg)
    locator.click()
    pg.wait_for_selector(".pvcard .act", timeout=15000)
    pg.locator(".pvcard .act").click()
    pg.wait_for_selector(".opt", timeout=20000)
    pg.wait_for_timeout(500)


def enter_graded_cloze(pg):
    unit = pg.locator(".unit").filter(has_text="UNIT 11")
    node = unit.locator(".node.current")
    if node.count() != 1:
        raise RuntimeError("UNIT 11 可进关卡数=%d（期望 1）" % node.count())
    enter_by(pg, unit.locator(".node.current .card .go"))


def enter_practice_cloze(pg):
    enter_by(pg, pg.locator(".strip").filter(has_text="选词填空"))


def answer_current(pg):
    meta = pg.evaluate(QTYPE)
    if meta["hasSubmitBtn"]:
        opts = pg.locator(".opt")
        total = opts.count()
        for k in range(meta["slotCount"]):
            opts.nth(k % total).click()
            pg.wait_for_timeout(150)
        pg.locator(".submitbtn").click()
    else:
        pg.locator(".opt").nth(0).click()
    pg.wait_for_selector(".feedback.show", timeout=10000)
    pg.wait_for_timeout(650)


def advance(pg):
    pg.locator(".fbbtn").click()
    pg.wait_for_function("() => !document.querySelector('.feedback.show')", timeout=8000)
    pg.wait_for_timeout(300)
    return pg.evaluate(RESET)


def measure_a(pg, tag, png=None):
    a = pg.evaluate(AREVEAL)
    rec("A." + tag, a)
    log("A@%s 视口高=%s scrollY=%s docH=%s 面板高=%s 真实顶=%s maxH=%s 可视带=%s 题卡maxH=%s"
        % (tag, a["viewportH"], a["scrollY"], a["docH"], a["panelH"],
           a["panelRectTop"], a["panelMaxH"], a["bandAbovePanel"],
           (a["qcard"] or {}).get("maxH")))
    for nm, o in (("正确项", a["rightOpt"]), ("自己选的项", a["pickedOpt"])):
        if o:
            log("   %s「%s」：%s~%s（高 %s）露出 %s px（%.0f%%）整行可见=%s 重叠=%s 命中=%s/%s"
                % (nm, o["text"], o["top"], o["bottom"], o["h"], o["visiblePx"],
                   o["visibleFraction"] * 100, o["fullyVisible"], o["overlapWithPanel"],
                   o["hitIsThisOption"], o["hitDesc"]))
    if png:
        shot(pg, png)
    return a


def sweep_blanks(pg, count, tag):
    rows = []
    for i in range(1, count + 1):
        bank = pg.evaluate(BANK)
        before = pg.evaluate(QTYPE)
        answer_current(pg)
        after = pg.evaluate(QTYPE)
        rows.append({"blank": i, "slotCount": before["slotCount"], "bank": bank,
                     "qtype": before["qtype"], "panelAnsLetter": after["panelAnsLetter"],
                     "rightKeyLetter": after["rightKeyLetter"]})
        if i < count:
            rows[-1]["reset"] = advance(pg)
    rec("B." + tag, rows)
    banks = [r["bank"] for r in rows]
    first = [x["label"] + x["text"] for x in banks[0]]
    same_all = all([x["label"] + x["text"] for x in s] == first for s in banks)
    letter_ok = all((r["panelAnsLetter"] or "") == (r["rightKeyLetter"] or "") for r in rows)
    rec("B.%s_summary" % tag, {"blanks": len(rows), "bank_identical": same_all,
                               "letter_match_all": letter_ok})
    log("B sweep@%s：%d 空，词表逐空同序=%s，面板字母==界面字母=%s（%s）"
        % (tag, len(rows), same_all, letter_ok,
           ", ".join("空%s:%s" % (r["blank"], r["panelAnsLetter"]) for r in rows)))
    return rows


def new_ctx(browser, w, h, token):
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=3,
                             is_mobile=True, has_touch=True, user_agent=UA)
    ctx.add_init_script("try{localStorage.setItem('cet46_token', %s);}catch(e){}"
                        % json.dumps(token))
    pg = ctx.new_page()
    pg.on("console", lambda m: M["errors"].append("console:%s:%s" % (m.type, m.text[:120]))
          if m.type == "error" else None)
    return ctx, pg


def run_tall(browser, token):
    ctx, pg = new_ctx(browser, 390, 844, token)
    try:
        open_map(pg)
        me = pg.evaluate("() => fetch('/api/auth/me',{headers:{Authorization:'Bearer '+localStorage.getItem('cet46_token')}}).then(r=>r.json())")
        rec("meta.student", me.get("data"))
        log("[390x844] 登录态：%s（%s）lv=%s 目标=%s，视口 %s"
            % (me["data"]["realName"], me["data"]["username"], me["data"]["lv"],
               me["data"]["target"], pg.viewport_size))

        shot(pg, "01-map-top-390x844.png")
        pg.locator(".strip").nth(0).scroll_into_view_if_needed()
        pg.wait_for_timeout(500)
        shot(pg, "02-map-practice-strip-390x844.png")
        measure_f(pg, "map_go", "地图「开始冲关」")
        measure_f(pg, "strip", "练习卷关卡条（整条可点）")
        M["F.strip_children"] = pg.evaluate(BOX, ".strip > *")
        pg.locator(".unit").filter(has_text="UNIT 11").first.scroll_into_view_if_needed()
        pg.wait_for_timeout(500)
        shot(pg, "03-map-unit11-390x844.png")
        rec("D.unit_titles", pg.evaluate(
            "() => Array.from(document.querySelectorAll('.unit')).map(u => "
            "(u.querySelector('.maptitle')||{}).innerText.replace(/\\s+/g,' ').trim().slice(0,52) "
            "+ ' || ' + Array.from(u.querySelectorAll('.node h4')).map(h=>h.innerText.replace(/\\s+/g,' ').trim()).join(' | '))"))

        # ---- 计分关（UNIT 11 选词填空）：量 1~2 空即退，避免耗光爱心 ----
        enter_graded_cloze(pg)
        rec("D.graded_first_qtype", pg.evaluate(QTYPE))
        shot(pg, "04-quiz-cloze-blank1-390x844.png")
        measure_f(pg, "quit", "关卡右上退出")
        bank1 = pg.evaluate(BANK)
        rec("B.graded_bank1", bank1)
        answer_current(pg)
        measure_a(pg, "graded-390x844-blank1", "05-A-feedback-390x844.png")
        r = advance(pg)
        rec("A.reset_after_next", r)
        log("复位检查：pad=%s scrollTop=%s 题卡maxH=%s（清空=%s / 归零=%s）"
            % (r["inlinePadBottom"], r["scrollTop"], r["qcardMaxH"],
               r["inlinePadIsCleared"], r["scrollTopIsZero"]))
        bank2 = pg.evaluate(BANK)
        rec("B.graded_bank2", bank2)
        same = [b["label"] + b["text"] for b in bank1] == [b["label"] + b["text"] for b in bank2]
        rec("B.graded_bank1_eq_bank2", same)
        log("计分关词表：第 1 空 %d 词，与第 2 空同序=%s" % (len(bank1), same))
        answer_current(pg)
        rec("B.graded_letters_blank2", pg.evaluate(QTYPE))
        measure_a(pg, "graded-390x844-blank2")
        pg.locator(".quit").click()
        pg.wait_for_timeout(800)
        st = pg.evaluate("() => ({url: location.pathname, dlg: !!document.querySelector('.van-dialog')})")
        rec("A.quit_state", st)
        if st["dlg"]:
            pg.locator(".van-dialog__confirm, .van-dialog .van-button--primary").first.click()
            pg.wait_for_timeout(800)
        rec("A.quit_landing", pg.evaluate("() => location.pathname"))
        log("退出关卡落点=%s（对话框=%s）" % (pg.evaluate("() => location.pathname"), st["dlg"]))

        # ---- 练习卷选词填空：跑满 10 空（练习卷答错不结束） ----
        enter_practice_cloze(pg)
        rec("D.practice_first_qtype", pg.evaluate(QTYPE))
        shot(pg, "07-practice-cloze-blank1-390x844.png")
        sweep_blanks(pg, 10, "practice_cloze_10blanks")
        shot(pg, "08-practice-cloze-after-10-390x844.png")
        pg.locator(".quit").click()
        pg.wait_for_timeout(900)
        if pg.locator(".van-dialog").count():
            pg.locator(".van-dialog__confirm, .van-dialog .van-button--primary").first.click()
            pg.wait_for_timeout(800)

        # ---- 我的页 + 其他页触达件 ----
        pg.goto(BASE + "/s/me", wait_until="domcontentloaded")
        pg.wait_for_selector(".accbtn", timeout=15000)
        pg.locator(".accbtn").nth(0).scroll_into_view_if_needed()
        pg.wait_for_timeout(600)
        shot(pg, "10-me-account-card-390x844.png")
        measure_f(pg, "accbtn", "我的页账户入口两颗")
        measure_f(pg, "me_entry", "明细入口")
        measure_f(pg, "me_review_go", "复盘入口")
        measure_f(pg, "me_back", "返回按钮")
        pg.evaluate("() => window.scrollTo(0,0)")
        pg.wait_for_timeout(300)
        shot(pg, "11-me-top-390x844.png")
        for path, key, png, note in [
            ("/s/rank", "rank_switch", "12-rank-390x844.png", "排行榜切换"),
            ("/s/team", "team_pick", "13-team-390x844.png", "小队加入/创建"),
            ("/s/team", "team_mini", None, "小队成员卡按钮"),
            ("/s/review", "me_back", "14-review-390x844.png", "复盘页返回"),
            ("/s/ledger", "me_back", "15-ledger-390x844.png", "明细页返回"),
        ]:
            try:
                pg.goto(BASE + path, wait_until="domcontentloaded")
                pg.wait_for_timeout(1300)
                measure_f(pg, key, note + " @" + path)
                if png:
                    shot(pg, png)
            except Exception as e:
                log("页面 %s 测量失败：%s" % (path, str(e)[:110]))
    except Exception:
        M["errors"].append("390x844:" + traceback.format_exc()[-600:])
        log("[390x844] 流程异常：\n%s" % traceback.format_exc())
    finally:
        ctx.close()


def run_short(browser, token, w, h):
    tag = "%dx%d" % (w, h)
    ctx, pg = new_ctx(browser, w, h, token)
    try:
        enter_practice_cloze(pg)
        shot(pg, "09-practice-cloze-blank1-%s.png" % tag)
        answer_current(pg)
        measure_a(pg, "practice-%s-blank1" % tag, "09b-A-feedback-practice-%s.png" % tag)
        r = advance(pg)
        rec("A.reset_after_next_practice_%s" % tag, r)
        log("[%s] 复位检查：pad=%s scrollTop=%s 题卡maxH=%s（清空=%s / 归零=%s）"
            % (tag, r["inlinePadBottom"], r["scrollTop"], r["qcardMaxH"],
               r["inlinePadIsCleared"], r["scrollTopIsZero"]))
        closed = pg.evaluate(AREVEAL)["qcard"]
        rec("A.qcard_closed_%s" % tag, closed)
        log("[%s] 面板收起后题卡 maxH=%s 高=%s" % (tag, closed["maxH"], closed["h"]))
        answer_current(pg)
        measure_a(pg, "practice-%s-blank2" % tag)
        pg.locator(".quit").click()
        pg.wait_for_timeout(900)
        if pg.locator(".van-dialog").count():
            pg.locator(".van-dialog__confirm, .van-dialog .van-button--primary").first.click()
            pg.wait_for_timeout(800)
    except Exception:
        M["errors"].append(tag + ":" + traceback.format_exc()[-600:])
        log("[%s] 流程异常：\n%s" % (tag, traceback.format_exc()))
    finally:
        ctx.close()


def run_e(browser, rows):
    try:
        ctx2 = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                                  is_mobile=True, has_touch=True, user_agent=UA)
        p2 = ctx2.new_page()
        p2.goto(BASE + "/s/login", wait_until="domcontentloaded")
        shot(p2, "20-E-login-390x844.png")
        target = None
        for row in rows:
            sid = (row.get("学号") or "").strip()
            pw = (row.get("初始密码") or "").strip()
            if not sid or sid == "2405510103":
                continue
            body = p2.evaluate(
                """(a) => fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({username:a.u,password:a.p})}).then(r=>r.json())""",
                {"u": sid, "p": pw})
            if body.get("code") == 0 and body["data"].get("user", {}).get("mustChangePwd"):
                target = {"sid": sid, "pw": pw, "name": body["data"]["user"]["realName"]}
                break
        rec("E.init_state_student", {"sid": target["sid"], "name": target["name"]} if target else None)
        log("E 用初始态学生：%s（%s）" % ((target or {}).get("name"), (target or {}).get("sid")))
        if not target:
            return
        p2.goto(BASE + "/s/login", wait_until="domcontentloaded")
        p2.locator("input[placeholder='请输入学号']").fill(target["sid"])
        p2.locator("input[placeholder='初始密码由老师发给你']").fill(target["pw"])
        p2.get_by_text("登 录", exact=True).click()
        p2.wait_for_timeout(1600)
        rec("E.login_landing", p2.evaluate("() => location.pathname"))
        rec("E.must_change_gate_title", p2.evaluate("() => (document.querySelector('.brand h1')||{}).innerText || null"))
        log("首登落点 path=%s 门标题=%s" % (p2.evaluate("() => location.pathname"),
                                        p2.evaluate("() => (document.querySelector('.brand h1')||{}).innerText || null")))
        shot(p2, "21-E-forced-chpwd-390x844.png")
        rec("E.blocked_before_chpwd", p2.evaluate(
            "() => fetch('/api/quiz/levels',{headers:{Authorization:'Bearer '+(localStorage.getItem('cet46_token')||'')}}).then(r=>r.json()).then(j=>({code:j.code,message:j.message}))"))
        log("改密前业务接口：%s" % M["E"]["blocked_before_chpwd"])
        p2.locator("input[placeholder='老师发的初始密码']").fill(target["pw"])
        p2.locator("input[placeholder='至少 6 位']").fill("<复测临时口令：运行时注入，原文不入仓>")
        p2.locator("input[placeholder='再输一遍新密码']").fill("<复测临时口令：运行时注入，原文不入仓>")
        p2.get_by_text("确认修改", exact=False).first.click()
        p2.wait_for_timeout(2200)
        rec("E.after_chpwd_path", p2.evaluate("() => location.pathname"))
        log("改密后 path=%s（旧令牌按设计即刻作废，需重登）" % p2.evaluate("() => location.pathname"))
        shot(p2, "22-E-after-chpwd-390x844.png")
        p2.locator("input[placeholder='请输入学号']").fill(target["sid"])
        p2.locator("input[placeholder='初始密码由老师发给你']").fill("<复测临时口令：运行时注入，原文不入仓>")
        p2.get_by_text("登 录", exact=True).click()
        p2.wait_for_timeout(2000)
        rec("E.relogin_landing", p2.evaluate("() => location.pathname"))
        log("新口令重登落点 path=%s" % p2.evaluate("() => location.pathname"))
        dismiss_picker(p2, "E 重登后")
        shot(p2, "23-E-relogin-map-390x844.png")
        p2.goto(BASE + "/s/me", wait_until="domcontentloaded")
        p2.wait_for_selector(".accbtn", timeout=20000)
        p2.locator(".accbtn").nth(0).scroll_into_view_if_needed()
        p2.wait_for_timeout(600)
        shot(p2, "24-E-me-account-card-390x844.png")
        rec("E.account_buttons", p2.evaluate(BOX, ".accbtn"))
        log("账户卡两颗按钮：%s" % [(b["w"], b["h"], b["text"]) for b in p2.evaluate(BOX, ".accbtn")])
        p2.get_by_text("修改密码", exact=False).first.click()
        p2.wait_for_timeout(1500)
        rec("E.voluntary_chpwd_path", p2.evaluate("() => location.pathname"))
        rec("E.voluntary_chpwd_title", p2.evaluate("() => (document.querySelector('.brand h1')||{}).innerText || null"))
        log("主动改密入口：path=%s 标题=%s" % (p2.evaluate("() => location.pathname"),
                                          p2.evaluate("() => (document.querySelector('.brand h1')||{}).innerText || null")))
        shot(p2, "25-E-voluntary-chpwd-390x844.png")
        p2.go_back()
        p2.wait_for_timeout(1500)
        p2.get_by_text("退出登录", exact=False).first.click()
        p2.wait_for_timeout(1500)
        dlg = p2.evaluate("() => document.querySelector('.van-dialog') ? document.querySelector('.van-dialog').innerText.replace(/\\s+/g,' ').trim().slice(0,80) : null")
        rec("E.logout_dialog", dlg)
        log("退出确认弹层：%s" % dlg)
        if dlg:
            p2.locator(".van-dialog__confirm, .van-dialog .van-button--primary").first.click()
            p2.wait_for_timeout(1500)
        rec("E.logout_landing", p2.evaluate("() => location.pathname"))
        rec("E.token_after_logout", p2.evaluate("() => localStorage.getItem('cet46_token')"))
        log("退出后 path=%s token=%s" % (p2.evaluate("() => location.pathname"),
                                      p2.evaluate("() => localStorage.getItem('cet46_token')")))
        shot(p2, "26-E-after-logout-390x844.png")
        p2.locator("input[placeholder='请输入学号']").fill(target["sid"])
        p2.locator("input[placeholder='初始密码由老师发给你']").fill("<复测临时口令：运行时注入，原文不入仓>")
        p2.get_by_text("登 录", exact=True).click()
        p2.wait_for_timeout(2000)
        rec("E.login_again_landing", p2.evaluate("() => location.pathname"))
        log("退出后再登落点 path=%s" % p2.evaluate("() => location.pathname"))
        dismiss_picker(p2, "E 再登后")
        shot(p2, "27-E-login-again-map-390x844.png")
        ctx2.close()
    except Exception:
        M["errors"].append("E:" + traceback.format_exc()[-600:])
        log("E 流程异常：\n" + traceback.format_exc())


def main():
    os.makedirs(OUT, exist_ok=True)
    token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    rows = list(csv.DictReader(open(ROSTER, encoding="utf-8-sig")))
    log("名单 CSV 行数=%d" % len(rows))
    M["meta"] = {
        "when": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": "Playwright + 系统 Edge（channel=msedge, headless）",
        "emulation": "390x844 / 390x700 / 390x664 各自新建上下文；DPR 3、isMobile、hasTouch、iPhone UA",
        "base": BASE,
        "roster_rows": len(rows),
        "token_source": "已登录会话的 localStorage；E 用名单 CSV 里的初始口令（脚本不打印口令）",
        "web_bundle": "本次复测用的是修复后重新构建并部署的 web 包（QuizView 短屏让位 + revealAnswer 基准修正）",
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        run_tall(browser, token)
        run_short(browser, token, 390, 700)
        run_short(browser, token, 390, 664)
        run_e(browser, rows)
        browser.close()

    with open(os.path.join(OUT, "recheck-final-measurements.json"), "w", encoding="utf-8") as f:
        json.dump(M, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "recheck-final-run.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    log("完成：measurements.json + run.log 已落盘；错误 %d 条" % len(M["errors"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())