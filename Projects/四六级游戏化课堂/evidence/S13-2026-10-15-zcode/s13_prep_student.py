# -*- coding: utf-8 -*-
"""S13 复测前置②：真实班学生登录 → 首登强制改密 → 学生端是否已挂上刚发布的课下练习卷。
（脚本可重入：口令已改过时自动跳过改密段，只做「练习卷可见」的复核。）"""
import json, urllib.request, urllib.error
BASE="http://127.0.0.1/api"
def call(m,p,b=None,t=None):
    d=json.dumps(b,ensure_ascii=False).encode() if b is not None else None
    r=urllib.request.Request(BASE+p,data=d,method=m)
    r.add_header("Content-Type","application/json; charset=utf-8")
    if t: r.add_header("Authorization","Bearer "+t)
    try:
        with urllib.request.urlopen(r,timeout=20) as x: return x.status, json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try: return e.code, json.loads(raw)
        except Exception: return e.code,{"raw":raw[:200]}
OK=0
def chk(n,c,e=""):
    global OK
    print(("  ok  " if c else "  FAIL")+f" {n} {e}")
    if c: OK+=1
U,PW,INIT="2405510103","<复测临时口令>","<学生初始口令>"
print(f"① 学生登录（真实班 2024级英语1班 · 学号 {U}）")
st,r=call("POST","/auth/login",{"username":U,"password":INIT})
if st==200 and r.get("code")==0:
    tok=r["data"]["token"]
    chk("初始口令登录成功",True,f"mustChangePwd={r['data'].get('mustChangePwd')}")
    st,r2=call("GET","/quiz/levels",None,tok)
    chk("未改密时被闸门拦住（40302）",r2.get("code")==40302,f"code={r2.get('code')}")
    print("② 首登强制改密 → 临时口令（复测用，复测结束后整库复位回初始态）")
    st,r=call("POST","/auth/chpwd",{"oldPassword":INIT,"newPassword":PW},tok)
    chk("chpwd 200",st==200 and r.get("code")==0,f"st={st} msg={r.get('message')}")
else:
    chk("初始口令登录（已被前次复测改密，属预期）",False,f"msg={r.get('message')}")
    print("② 用复测临时口令登录")
st,r=call("POST","/auth/login",{"username":U,"password":PW})
chk("改密后能登录",st==200 and r.get("code")==0,f"st={st} msg={r.get('message')}")
if not (st==200 and r.get("code")==0): raise SystemExit("登录失败，后续不可测")
tok=r["data"]["token"]
chk("mustChangePwd 已清",r["data"].get("mustChangePwd") is False)
print("③ 学生端单元列表：教师刚发布的课下练习卷是否已挂上")
st,r=call("GET","/quiz/levels",None,tok)
chk("quiz/levels 200",st==200 and r.get("code")==0,f"st={st} {r.get('message')}")
units=(r.get("data") or {}).get("units") or []
for u in units:
    print(f"      unit {u.get('unitId')} · 第{u.get('weekNo')}周 · practice={bool(u.get('practice'))} · 关 {u.get('levelCount')} · 题 {u.get('questionCount')} · {str(u.get('name'))[:28]}")
ps=[u for u in units if u.get("practice")]
chk("出现练习卷单元（.strip 的数据来源）",len(ps)>=1,f"n={len(ps)}")
if ps:
    p0=ps[0]
    chk("练习卷有关卡",(p0.get("levelCount") or 0)>=1,f"levelCount={p0.get('levelCount')}")
    chk("练习卷有题",(p0.get("questionCount") or 0)>0,f"questionCount={p0.get('questionCount')}")
    chk("走 practice 形态",p0.get("paperMode")=="practice",f"paperMode={p0.get('paperMode')}")
    chk("未设到期",not p0.get("dueAt"),f"dueAt={p0.get('dueAt')!r}")
print(f"\n断言 {OK} 条通过")
