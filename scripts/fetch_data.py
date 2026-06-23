#!/usr/bin/env python3
"""
数据获取脚本 - 在 GitHub Actions 中定时运行，生成静态 JSON 数据
"""
import json, time, random, math, os, sys
from urllib.request import Request, urlopen
from urllib.parse import urlencode

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _fetch(url, params=None, timeout=20, headers=None):
    """通用 HTTP GET 请求"""
    if params:
        url = f"{url}?{urlencode(params)}"
    req = Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Referer", "https://quote.eastmoney.com/")
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.read()
    except Exception as e:
        print(f"  fetch error: {e}")
        return None


def _fetch_json(url, params=None):
    raw = _fetch(url, params)
    if raw:
        try:
            return json.loads(raw.decode("utf-8"))
        except:
            pass
    return {"rc": -1, "data": None}


def _em_get(params, timeout=20):
    """East Money API 请求（带重试）"""
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    for attempt in range(3):
        data = _fetch_json(url, params)
        if data and data.get("rc") == 0:
            return data
        print(f"  EM retry {attempt+1}...")
        time.sleep(2 + random.random() * 2)
    return None


def _sf(v, default=0):
    try: return float(v) if v not in (None, "", "-") else default
    except: return default


def _fa(val):
    try:
        v = float(val)
        if v >= 1e8: return f"{v/1e8:.2f}亿"
        if v >= 1e4: return f"{v/1e4:.2f}万"
        return str(int(v))
    except: return "—"


def _parse_tencent(line):
    """解析腾讯行情行"""
    try:
        if not line or "~" not in line:
            return None
        if '="' in line:
            line = line.split('="', 1)[1].rstrip('";\n\r ')
        fields = line.split("~")
        amount = 0
        if len(fields) > 35 and fields[35]:
            parts = fields[35].split("/")
            if len(parts) >= 3:
                amount = _sf(parts[2])
        if amount == 0 and len(fields) > 37:
            amount = _sf(fields[37]) * 10000
        return {
            "name": fields[1], "code": fields[2],
            "price": _sf(fields[3]), "change_pct": _sf(fields[32]) if len(fields) > 32 else 0,
            "change": _sf(fields[31]) if len(fields) > 31 else 0,
            "amount": amount,
            "open": _sf(fields[5]), "high": _sf(fields[33]) if len(fields) > 33 else 0,
            "low": _sf(fields[34]) if len(fields) > 34 else 0,
            "prev_close": _sf(fields[4]),
        }
    except:
        return None


def fetch_indices():
    """主要指数"""
    print("Fetching indices...")
    raw = _fetch("https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000300,sh000016,sh000905,sh000852")
    if not raw:
        return None
    records = []
    for line in raw.decode("gbk", errors="replace").strip().split("\n"):
        p = _parse_tencent(line)
        if p:
            records.append({
                "name": p["name"], "code": p["code"],
                "price": p["price"], "change_pct": round(p["change_pct"], 2),
                "change_amount": round(p["change"], 2),
                "amount": _fa(p["amount"]),
                "open": p["open"], "high": p["high"], "low": p["low"],
            })
    print(f"  -> {len(records)} indices")
    return records


def fetch_sentiment(indices):
    """市场情绪"""
    print("Fetching sentiment...")
    # 用 East Money 采样
    params = {
        "pn": 1, "pz": 100, "po": 0, "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f12",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f2,f3,f4,f5,f6,f12,f14",
    }
    total_stocks = 5300
    up_count, down_count, limit_up, limit_down = 0, 0, 0, 0
    total_amount = 0
    sampled = 0

    # 取首页
    data = _em_get(params)
    if not data or not data.get("data", {}).get("diff"):
        print("  -> East Money unavailable, using estimate")
        # 用腾讯数据做粗略估计
        result = {
            "sentiment_temperature": 50,
            "total_stocks": total_stocks,
            "up_count": round(total_stocks * 0.45),
            "down_count": round(total_stocks * 0.45),
            "flat_count": round(total_stocks * 0.1),
            "limit_up": 0, "limit_down": 0,
            "advance_decline_ratio": "—",
            "total_amount": "—",
            "indices": indices or [],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return result
    
    total_stocks = data["data"].get("total", 5300)
    all_items = list(data["data"]["diff"])
    # 再取几页
    per_page = len(all_items)
    total_pages = max(1, math.ceil(total_stocks / per_page))
    for page in [2, 3, total_pages - 2, total_pages - 1, total_pages]:
        if page > 1 and page <= total_pages:
            p = dict(params, pn=page)
            d = _em_get(p)
            if d and d.get("data", {}).get("diff"):
                all_items.extend(d["data"]["diff"])
            time.sleep(0.5)

    up_count = sum(1 for r in all_items if _sf(r.get("f3")) > 0)
    down_count = sum(1 for r in all_items if _sf(r.get("f3")) < 0)
    sampled = len(all_items)
    limit_up = sum(1 for r in all_items if _sf(r.get("f3")) >= 9.8)
    limit_down = sum(1 for r in all_items if _sf(r.get("f3")) <= -9.8)
    total_amount = sum(_sf(r.get("f6", 0)) for r in all_items)

    up_ratio = up_count / sampled if sampled > 0 else 0.5
    ratio = round(up_count / down_count, 2) if down_count > 0 else "—"

    # 成交额取上证
    total_amount_str = "—"
    for idx in (indices or []):
        if "上证" in idx.get("name", ""):
            total_amount_str = idx.get("amount", "—")
            break

    result = {
        "sentiment_temperature": round(up_ratio * 100),
        "total_stocks": total_stocks,
        "up_count": round(total_stocks * up_ratio),
        "down_count": total_stocks - round(total_stocks * up_ratio),
        "flat_count": 0,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "advance_decline_ratio": ratio,
        "total_amount": total_amount_str,
        "indices": indices or [],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(f"  -> 温度 {result['sentiment_temperature']}° | 涨{result['up_count']}/跌{result['down_count']}")
    return result


def fetch_sectors():
    """行业板块"""
    print("Fetching sectors...")
    data = _em_get({
        "pn": 1, "pz": 200, "po": 1, "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f5,f6,f12,f14,f104,f105,f136",
    })
    if not data.get("data", {}).get("diff"):
        return []
    records = []
    for item in data["data"]["diff"]:
        records.append({
            "name": item.get("f14", ""),
            "code": item.get("f12", ""),
            "change_pct": round(_sf(item.get("f3")), 2),
            "amount": _fa(item.get("f6", 0)),
            "up_count": int(item.get("f104", 0)),
            "down_count": int(item.get("f105", 0)),
            "lead_stock": item.get("f136", ""),
        })
    records.sort(key=lambda x: x["change_pct"], reverse=True)
    print(f"  -> {len(records)} sectors")
    return records


def fetch_hot_stocks():
    """热门个股"""
    print("Fetching hot stocks...")
    data = _em_get({
        "pn": 1, "pz": 50, "po": 1, "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f6",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f2,f3,f4,f5,f6,f8,f9,f12,f14,f20",
    })
    if not data.get("data", {}).get("diff"):
        return []
    records = []
    for item in data["data"]["diff"]:
        records.append({
            "code": item.get("f12", ""),
            "name": item.get("f14", ""),
            "price": round(_sf(item.get("f2")), 2),
            "change_pct": round(_sf(item.get("f3")), 2),
            "change_amount": round(_sf(item.get("f4")), 2),
            "amount": _fa(item.get("f6", 0)),
            "turnover": round(_sf(item.get("f8")), 2),
        })
    print(f"  -> {len(records)} hot stocks")
    return records


def fetch_index_history():
    """K线历史"""
    print("Fetching index history...")
    result = {}
    for name, em_id in [
        ("上证指数", "1.000001"),
        ("深证成指", "0.399001"),
        ("创业板指", "0.399006"),
    ]:
        raw = _fetch(
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={em_id}"
            f"&ut=fa5fd1943c7b386f172d6893dbfd32bb"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&end=20500101&lmt=60"
        )
        if not raw:
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
            klines = data.get("data", {}).get("klines", [])
            dates, closes, opens, highs, lows = [], [], [], [], []
            for line in klines:
                parts = line.split(",")
                dates.append(parts[0])
                closes.append(float(parts[2]))
                opens.append(float(parts[1]))
                highs.append(float(parts[3]))
                lows.append(float(parts[4]))
            result[name] = {"dates": dates, "close": closes, "open": opens, "high": highs, "low": lows}
        except:
            continue
    print(f"  -> {len(result)} indices history")
    return result


def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  saved {filename} ({os.path.getsize(path)} bytes)")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    indices = fetch_indices()
    if indices:
        save_json("indices.json", indices)
    
    sentiment = fetch_sentiment(indices)
    if sentiment:
        save_json("sentiment.json", sentiment)
    
    sectors = fetch_sectors()
    if sectors:
        save_json("sectors.json", sectors)
    
    hot = fetch_hot_stocks()
    if hot:
        save_json("hot_stocks.json", hot)
    
    history = fetch_index_history()
    if history:
        save_json("index_history.json", history)
    
    # 更新时间戳
    save_json("last_update.json", {"updated_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    print("\n✅ All data updated!")


if __name__ == "__main__":
    main()
