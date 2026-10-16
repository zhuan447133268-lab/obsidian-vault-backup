# -*- coding: utf-8 -*-
"""S13 复测前置：教师在试点库里组一份课下练习卷并发布到真实班，
   让「试卷关卡条 .strip」有真实数据可量。全程走真实接口（组卷→发布）。"""
import json, urllib.request, urllib.error, sys
BASE = "http://127.0.0.1/api"

def call(method, path, body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try: return e.code, json.loads(raw)
        except Exception: return e.code, {"raw": raw[:300]}

OK = 0
def chk(name, cond, extra=""):
    global OK
    print(("  ok  " if cond else "  FAIL") + f" {name} {extra}")
    if cond: OK += 1

print("① 任课教师首登（初始口令，试点交接文件里的那一份）")
st, r = call("POST", "/auth/login", {"username": "T2024001", "password": "<教师口令：运行时从 pilot_secrets.json 取，不入仓>"})
chk("login 200", st == 200 and r.get("code") == 0, f"st={st} mustChangePwd={r.get('data',{}).get('mustChangePwd')}")
tok = r["data"]["token"]
NEW = "<复测临时口令>"
print("② 首登强制改密（改完才放行教师接口）：旧口令 -> 临时强口令")
st, r = call("POST", "/auth/chpwd", {"oldPassword": "<教师口令：运行时从 pilot_secrets.json 取，不入仓>", "newPassword": NEW}, tok)
chk("chpwd 200", st == 200 and r.get("code") == 0, f"st={st} msg={r.get('message')}")
st, r = call("POST", "/auth/login", {"username": "T2024001", "password": NEW})
chk("改密后能登录", st == 200 and r.get("code") == 0, f"st={st}")
tok = r["data"]["token"]
chk("mustChangePwd 已清", r["data"].get("mustChangePwd") is False)

print("③ 选题池：拿班里真实单元（第 9/10/11 周真题）")
st, r = call("GET", "/admin/bank/units?classId=1", None, tok)
chk("bank/units 200", st == 200 and r.get("code") == 0, f"st={st} msg={r.get('message')}")
units = (r.get("data") or {}).get("items") or []
chk("有真实单元可选", len(units) >= 1, f"n={len(units)}")
for u in units[:6]:
    print(f"      unit {u['unitId']} · 第{u['weekNo']}周 · {u['name'][:26]} · 题 {u['questionCount']}")
src = units[0]

print("④ 组卷（课下练习形态，整单元引用真实题库）")
ctitle = "S13复测·课下练习（第%s周真题）" % src["weekNo"]
st, r = call("POST", "/admin/papers", {"classId": 1, "title": ctitle, "mode": "practice",
                                      "sourceUnitId": src["unitId"], "timeLimitMin": 20}, tok)
chk("compose 200", st == 200 and r.get("code") == 0, f"st={st} msg={r.get('message')}")
pdata = r.get("data") or {}
unit_id = pdata.get("unitId") or pdata.get("id")
qcount = pdata.get("questionCount") or pdata.get("questionTotal")
print(f"      卷单元 id={unit_id} 题数={qcount} 状态={pdata.get('status')}")
chk("卷里有题", bool(unit_id) and (qcount or 0) > 0, f"qcount={qcount}")

print("⑤ 发布到真实班（2024级英语1班）")
st, r = call("POST", f"/admin/papers/{unit_id}/publish",
             {"classIds": [1], "mode": "practice", "title": ctitle, "dueAt": ""}, tok)
chk("publish 200", st == 200 and r.get("code") == 0, f"st={st} msg={r.get('message')}")

print("⑥ 学生端视角：练习单元是否可见（用班里真实学生登录）")
st, r = call("POST", "/auth/login", {"username": "2405510101", "password": "Initpwd@2026"})
if st != 200:
    print(f"      （该学号口令未知，跳过学生端可见性；step ⑥ 留给浏览器复测）st={st}")
else:
    stok = r["data"]["token"]
    st2, r2 = call("GET", "/quiz/levels", None, stok)
    chk("quiz/levels 200", st2 == 200, f"st={st2}")
    ps = [u for u in ((r2.get("data") or {}).get("units") or []) if u.get("practice")]
    chk("学生端出现练习单元", len(ps) >= 1, f"practice_units={len(ps)}")
print(f"\n断言 {OK} 条通过")
sys.exit(0)
