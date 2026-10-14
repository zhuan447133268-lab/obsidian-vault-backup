"""S11 验收公用件：HTTP（urllib，避开原生 curl 的 GBK 转码坑）、DB 查询、断言计数。

与 S10.5 的 s105_lib.py 同构（同一套 Harness / req / sql 口径），随本轮交卷放进
仓库 evidence/S11-2026-10-14-zcode/（开工说明第五点：evidence 必须交付到本机仓库）。

BASE 可用环境变量 S11_BASE 覆盖：验收脚本要拿同一个大屏接口去问第二台实例
（8081，LIVE_REFRESH_SECONDS=3）来证明「刷新间隔可配置」。
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("S11_BASE", "http://127.0.0.1:8080/api")
DB = ["mysql", "--protocol=tcp", "-h", "127.0.0.1", "-P", "3307", "-uroot", "cet46",
      "--default-character-set=utf8mb4", "-N", "-B"]

NEWPWD = "S11Accept@2026"


class Fail(Exception):
    pass


class Harness:
    """断言计数器：与 S8/S9/S10/S10.5 验收同构，最后输出 `<总数> <失败数>` 供 99-summary.txt。"""

    def __init__(self, tag):
        self.tag = tag
        self.total = 0
        self.failed = 0
        self.msgs = []

    def check(self, ok, desc, detail=""):
        self.total += 1
        if ok:
            print("  [OK]   %s" % desc)
        else:
            self.failed += 1
            line = "  [FAIL] %s %s" % (desc, detail)
            print(line)
            self.msgs.append(line)
        return ok

    def eq(self, got, want, desc):
        return self.check(got == want, desc, "实际=%r 期望=%r" % (got, want))

    def section(self, name):
        print("\n== %s ==" % name)

    def result(self):
        print("\n[%s] 断言 %d 条 / 失败 %d" % (self.tag, self.total, self.failed))
        return self.total, self.failed


def req(method, path, token=None, body=None, raw=False, timeout=20, base=None):
    """一次 HTTP 调用。返回 (status, payload)；raw=True 时 payload 是 bytes。"""
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request((base or BASE) + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            buf = resp.read()
            if raw:
                return resp.status, buf
            return resp.status, json.loads(buf.decode("utf-8"))
    except urllib.error.HTTPError as e:
        buf = e.read()
        if raw:
            return e.code, buf
        try:
            return e.code, json.loads(buf.decode("utf-8"))
        except Exception:
            return e.code, {"code": -1, "message": buf.decode("utf-8", "replace"), "data": None}


def probe_many(method, path, token=None, times=10, base=None):
    """同一发被拒请求连打 N 次，返回 [(status, code)]，断连记 (0, None)。

    来由见 S8：Go 中间件 Abort 前不 drain 请求体会让服务端发 RST，把回执带走；
    这类探针不能 1 发定生死，要连发并同时看 HTTP 码 / 业务码 / 断连数。
    """
    out = []
    for _ in range(times):
        try:
            st, p = req(method, path, token=token, base=base)
            out.append((st, code_of(p)))
        except Exception:  # noqa: BLE001 断连/超时都算一次异常样本，不让它崩掉整步
            out.append((0, None))
    return out


def code_of(payload):
    if isinstance(payload, dict):
        return payload.get("code")
    return None


def data_of(payload):
    if isinstance(payload, dict):
        return payload.get("data")
    return None


def multipart(path, token, filepath, field="file", extra=None, base=None):
    """multipart/form-data 上传（导入名单 / 题库）。extra 是附加表单字段。"""
    boundary = "----S11Boundary7f3a9c"
    with open(filepath, "rb") as f:
        content = f.read()
    fname = os.path.basename(filepath)
    parts = []
    for k, v in (extra or {}).items():
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, k, v)).encode("utf-8"))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                  "Content-Type: application/octet-stream\r\n\r\n"
                  % (boundary, field, fname)).encode("utf-8"))
    parts.append(content)
    parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    body = b"".join(parts)
    headers = {"Content-Type": "multipart/form-data; boundary=" + boundary,
               "Content-Length": str(len(body))}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request((base or BASE) + path, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        buf = e.read()
        try:
            return e.code, json.loads(buf.decode("utf-8"))
        except Exception:
            return e.code, {"code": -1, "message": buf.decode("utf-8", "replace"), "data": None}


def sql(query):
    """跑一条 SQL，返回行列表（每行是字段列表，全部 str）。"""
    out = subprocess.run(DB + ["-e", query], capture_output=True)
    if out.returncode != 0:
        raise Fail("SQL 失败: %s\n%s" % (query, out.stderr.decode("utf-8", "replace")))
    # $(mysql) 多行输出带 \r：不剥掉行尾会让每个字段都自带回车（S5 起的老坑）
    text = out.stdout.decode("utf-8", "replace").replace("\r", "")
    rows = []
    for line in text.split("\n"):
        if line.strip() == "":
            continue
        rows.append(line.split("\t"))
    return rows


def sql1(query, default=None):
    rows = sql(query)
    if not rows or not rows[0]:
        return default
    return rows[0][0]


def sql_int(query, default=0):
    v = sql1(query)
    if v is None or v == "NULL":
        return default
    return int(v)


def login(username, password, must_change=False):
    """登录 +（需要时）改密到统一口令，返回 token。

    先试统一口令：脚本要能反复跑，第二次跑时账号早就改过密了。
    """
    st, p = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
    if st == 200 and code_of(p) == 0:
        return data_of(p)["token"]
    st, p = req("POST", "/auth/login", body={"username": username, "password": password})
    if st != 200 or code_of(p) != 0:
        raise Fail("登录失败 %s: %s" % (username, p))
    token = data_of(p)["token"]
    if must_change and data_of(p)["user"].get("mustChangePwd"):
        st2, p2 = req("POST", "/auth/chpwd", token=token,
                      body={"oldPassword": password, "newPassword": NEWPWD})
        if st2 != 200 or code_of(p2) != 0:
            raise Fail("首登改密失败 %s: %s" % (username, p2))
        st3, p3 = req("POST", "/auth/login", body={"username": username, "password": NEWPWD})
        if st3 != 200 or code_of(p3) != 0:
            raise Fail("改密后重新登录失败 %s: %s" % (username, p3))
        return data_of(p3)["token"]
    return token


def say(msg):
    print(msg)
    sys.stdout.flush()