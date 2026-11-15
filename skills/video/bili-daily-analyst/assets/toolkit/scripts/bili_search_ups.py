# B站搜索 API helpers；搜索只能发现候选，不能证明覆盖完整。
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
REFERER = "https://www.bilibili.com/"
MIXIN = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
         33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 56, 30, 22, 7, 44,
         0, 11, 51, 6, 40, 54, 55, 20, 25, 24, 36, 17, 21, 26, 34, 16, 1, 57,
         52, 4, 59]
BEIJING = datetime.timezone(datetime.timedelta(hours=8))


def http_json(url, cookies=""):
    headers = {
        "User-Agent": UA,
        "Referer": REFERER,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if cookies:
        headers["Cookie"] = cookies
    req = urllib.request.Request(url, headers=headers)
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    return json.loads(raw)


def get_buvid():
    """访问首页拿 buvid3/buvid4 cookie（搜索接口风控需要设备指纹）"""
    req = urllib.request.Request("https://www.bilibili.com/", headers={
        "User-Agent": UA, "Referer": REFERER})
    resp = urllib.request.urlopen(req, timeout=20)
    set_cookies = resp.headers.get_all("Set-Cookie") or []
    pairs = {}
    for sc in set_cookies:
        first = sc.split(";", 1)[0]
        if "=" in first:
            k, v = first.split("=", 1)
            pairs[k.strip()] = v.strip()
    need = {k: pairs[k] for k in ("buvid3", "buvid4", "b_nut") if k in pairs}
    return "; ".join(f"{k}={v}" for k, v in need.items())


def wbi_keys(cookies):
    nav = http_json("https://api.bilibili.com/x/web-interface/nav", cookies)
    data = nav.get("data") or {}
    img = data.get("wbi_img") or {}
    img_url, sub_url = img.get("img_url", ""), img.get("sub_url", "")
    if not img_url or not sub_url:
        raise RuntimeError(f"nav 未返回 wbi_img（code={nav.get('code')} msg={nav.get('message')}）")
    orig = (img_url.rsplit("/", 1)[-1].split(".")[0]
            + sub_url.rsplit("/", 1)[-1].split(".")[0])
    return "".join(orig[i] for i in MIXIN if i < len(orig))[:32]


def sign(params, mixin_key):
    params = {k: str(v) for k, v in params.items()}
    params["wts"] = str(int(time.time()))
    params = {k: params[k].translate(str.maketrans("", "", "!'()*"))
              for k in sorted(params)}
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return urllib.parse.urlencode(params)


def search_type(kw, stype, mixin, cookies, order="", page=1):
    params = {
        "search_type": stype,
        "keyword": kw,
        "page": page,
        "platform": "pc",
        "web_location": "1550101",
    }
    if order:
        params["order"] = order
    url = ("https://api.bilibili.com/x/web-interface/wbi/search/type?"
           + sign(params, mixin))
    return http_json(url, cookies)

