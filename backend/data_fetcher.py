"""
A股市场数据获取模块 - 使用腾讯财经免费API (qt.gtimg.cn) 为主
"""
import subprocess
import json
import time
import random
from datetime import datetime

# ========== 通用 ==========

def _curl(url, timeout=15, max_retries=3, encoding='gbk'):
    """通过curl获取数据（避免Python requests的代理问题）"""
    headers = [
        '-s', '--max-time', str(timeout),
        '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    ]
    for attempt in range(max_retries):
        try:
            cmd = ['curl'] + headers + [url]
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
            if result.returncode == 0 and len(result.stdout) > 10:
                return result.stdout.decode(encoding, errors='replace')
            time.sleep(1 + random.random())
        except:
            time.sleep(1 + random.random())
    return ''

def _curl_em(url, params=None, timeout=20, max_retries=3):
    """通过curl获取East Money API数据（带重试，处理间歇性不可达）"""
    if params:
        import urllib.parse
        qs = urllib.parse.urlencode(params)
        full_url = f"{url}?{qs}"
    else:
        full_url = url
    
    headers = [
        '-s', '--max-time', str(timeout),
        '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        '-H', 'Referer: https://quote.eastmoney.com/',
        '-H', 'Accept: application/json',
    ]
    for attempt in range(max_retries):
        try:
            cmd = ['curl'] + headers + [full_url]
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
            if result.returncode == 0 and len(result.stdout) > 10:
                data = json.loads(result.stdout.decode('utf-8', errors='replace'))
                if data.get('rc') == 0:
                    return data
            time.sleep(2 + random.random() * 2)
        except:
            time.sleep(2 + random.random() * 2)
    return {'rc': -1, 'data': None}

def _parse_tencent_stock(line):
    """解析腾讯行情单行数据"""
    try:
        if not line or '~' not in line:
            return None
        
        # v_sh000001="field1~field2~..."
        if '="' in line:
            line = line.split('="', 1)[1].rstrip('";\n\r ')
        
        fields = line.split('~')
        
        # 成交额处理：优先从[35]提取（格式: price/volume/amount）
        amount = 0
        if len(fields) > 35 and fields[35]:
            parts = fields[35].split('/')
            if len(parts) >= 3:
                amount = _f(parts[2])  # 元
        if amount == 0 and len(fields) > 37:
            amount = _f(fields[37]) * 10000  # 万元转元
        
        return {
            'market': fields[0],
            'name': fields[1],
            'code': fields[2],
            'price': _f(fields[3]),
            'prev_close': _f(fields[4]),
            'open': _f(fields[5]),
            'volume': int(fields[6]) if fields[6].isdigit() else 0,
            'amount': amount,
            'high': _f(fields[33]) if len(fields) > 33 else 0,
            'low': _f(fields[34]) if len(fields) > 34 else 0,
            'change': _f(fields[31]) if len(fields) > 31 else 0,
            'change_pct': _f(fields[32]) if len(fields) > 32 else 0,
            'time': fields[30] if len(fields) > 30 else '',
        }
    except:
        return None


def _f(v):
    try: return float(v) if v not in (None, '', '-') else 0
    except: return 0


def _pct_class(v):
    if v > 0: return 'up'
    if v < 0: return 'down'
    return 'flat'


def _fmt_amount(val):
    try:
        v = float(val)
        if v >= 1e8: return f'{v/1e8:.2f}亿'
        if v >= 1e4: return f'{v/1e4:.2f}万'
        return str(int(v))
    except: return '—'


def _fmt_vol(val):
    try:
        v = float(val)
        if v >= 1e8: return f'{v/1e8:.2f}亿手'
        if v >= 1e4: return f'{v/1e4:.2f}万手'
        return str(int(v))
    except: return '—'


# ========== 指数 ==========

def get_market_indices():
    """获取主要指数行情"""
    codes = 'sh000001,sz399001,sz399006,sh000688,sh000300,sh000016,sh000905,sh000852'
    raw = _curl(f'https://qt.gtimg.cn/q={codes}')
    records = []
    for line in raw.strip().split('\n'):
        p = _parse_tencent_stock(line)
        if p:
            records.append({
                'name': p['name'],
                'code': p['code'],
                'price': p['price'],
                'change_pct': p['change_pct'],
                'change_amount': p['change'],
                'volume': _fmt_vol(p['volume']),
                'amount': _fmt_amount(p['amount']),
                'open': p['open'],
                'high': p['high'],
                'low': p['low'],
                'prev_close': p['prev_close'],
            })
    return records


# ========== 情绪 ==========

def get_market_sentiment():
    """市场情绪 - 通过指数 + 批量股票采样估算"""
    try:
        indices = get_market_indices()

        # 获取A股涨跌分布: 通过批量查询涨跌幅排名靠前/靠后的股票
        # 腾讯不支持直接排序查询，改用随机采样
        # 取沪深300成分股 + 创业板50 + 科创50 的涨跌情况作为样本
        sample_codes = [
            # 沪深300 top
            'sz000858', 'sh600519', 'sz300750', 'sz000333', 'sz002415',
            'sz000002', 'sz000001', 'sz002594', 'sz300059', 'sz002475',
            'sh601318', 'sh600036', 'sh600900', 'sh601166', 'sh600276',
            'sh601857', 'sh601012', 'sh600887', 'sh600585', 'sh601888',
            'sh600690', 'sh601398', 'sh601939', 'sh601288', 'sh601988',
            'sz002714', 'sz002304', 'sz000568', 'sz000651', 'sz002032',
            'sz300124', 'sz002230', 'sz300274', 'sz002371', 'sz300661',
            # 创业板
            'sz300760', 'sz300015', 'sz300122', 'sz300347', 'sz300413',
            'sz300433', 'sz300450', 'sz300496', 'sz300502', 'sz300601',
            # 科创板
            'sh688981', 'sh688036', 'sh688012', 'sh688008', 'sh688126',
            'sh688185', 'sh688169', 'sh688256', 'sh688390', 'sh688599',
        ]

        raw = _curl(f'https://qt.gtimg.cn/q={",".join(sample_codes)}')
        stocks = []
        for line in raw.strip().split('\n'):
            p = _parse_tencent_stock(line)
            if p and p['code'] and p['price'] > 0:
                stocks.append(p)

        up_count = sum(1 for s in stocks if s['change_pct'] > 0)
        down_count = sum(1 for s in stocks if s['change_pct'] < 0)
        total = len(stocks)

        # 涨停/跌停
        limit_up = sum(1 for s in stocks if s['change_pct'] >= 9.8)
        limit_down = sum(1 for s in stocks if s['change_pct'] <= -9.8)

        up_ratio = up_count / total if total > 0 else 0.5
        sentiment_temp = round(up_ratio * 100)

        # 估算全市场(约5300只)
        est_up = round(5300 * up_ratio)
        est_down = 5300 - est_up

        ratio = round(up_count / down_count, 2) if down_count > 0 else '—'

        # 成交额（从指数获取）
        total_amount = '—'
        for idx in indices:
            if idx['name'] == '上证指数':
                total_amount = idx['amount']
                break

        return {
            'sentiment_temperature': sentiment_temp,
            'total_stocks': 5300,
            'up_count': est_up,
            'down_count': est_down,
            'flat_count': 5300 - est_up - est_down,
            'limit_up': limit_up,
            'limit_down': limit_down,
            'advance_decline_ratio': ratio,
            'total_amount': total_amount,
            'indices': indices,
            'updated_at': datetime.now().strftime('%H:%M:%S'),
        }
    except Exception as e:
        return {'error': f'获取市场情绪失败: {str(e)}'}


# ========== 行业板块（从腾讯） ==========

def get_sector_data():
    """获取行业板块行情（East Money API）"""
    try:
        data = _curl_em('https://82.push2.eastmoney.com/api/qt/clist/get', {
            'pn': 1, 'pz': 200, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:90+t:2',
            'fields': 'f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18,f20,f21,f104,f105,f136'
        })
        if not data.get('data', {}).get('diff'):
            return [{'name': '数据加载中...', 'change_pct': 0}]
        records = []
        for item in data['data']['diff']:
            records.append({
                'name': item.get('f14', ''),
                'code': item.get('f12', ''),
                'price': _f(item.get('f2')),
                'change_pct': _f(item.get('f3')),
                'change_amount': _f(item.get('f4')),
                'volume': _fmt_vol(item.get('f5', 0)),
                'amount': _fmt_amount(item.get('f6', 0)),
                'up_count': int(item.get('f104', 0)),
                'down_count': int(item.get('f105', 0)),
                'lead_stock': item.get('f136', ''),
            })
        records.sort(key=lambda x: x['change_pct'], reverse=True)
        return records
    except Exception as e:
        return {'error': f'获取行业板块数据失败: {str(e)}'}


def get_concept_sector_data():
    """获取概念板块行情"""
    try:
        data = _curl_em('https://82.push2.eastmoney.com/api/qt/clist/get', {
            'pn': 1, 'pz': 500, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:90+t:3',
            'fields': 'f2,f3,f4,f5,f6,f12,f14,f20,f21,f104,f105'
        })
        if not data.get('data', {}).get('diff'):
            return [{'name': '数据加载中...', 'change_pct': 0}]
        records = []
        for item in data['data']['diff']:
            records.append({
                'name': item.get('f14', ''),
                'change_pct': _f(item.get('f3')),
                'amount': _fmt_amount(item.get('f6', 0)),
                'up_count': int(item.get('f104', 0)),
                'down_count': int(item.get('f105', 0)),
            })
        records.sort(key=lambda x: x['change_pct'], reverse=True)
        return records
    except Exception as e:
        return {'error': f'获取概念板块数据失败: {str(e)}'}


# ========== 行情热股 ==========

def get_hot_stocks(top_n=30):
    """获取热门个股（East Money API，按成交额排序）"""
    try:
        data = _curl_em('https://82.push2.eastmoney.com/api/qt/clist/get', {
            'pn': 1, 'pz': top_n, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f6',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
            'fields': 'f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f20,f21,f23,f62,f115,f128,f140,f152'
        })
        if not data.get('data', {}).get('diff'):
            return [{'name': '暂无数据', 'code': '', 'price': 0, 'change_pct': 0}]
        records = []
        for item in data['data']['diff']:
            records.append({
                'code': item.get('f12', ''),
                'name': item.get('f14', ''),
                'price': _f(item.get('f2')),
                'change_pct': _f(item.get('f3')),
                'change_amount': _f(item.get('f4')),
                'volume': _fmt_vol(item.get('f5', 0)),
                'amount': _fmt_amount(item.get('f6', 0)),
                'turnover': _f(item.get('f8')),
                'pe': _f(item.get('f9')),
                'total_mv': _fmt_amount(item.get('f20', 0)),
            })
        return records
    except Exception as e:
        return {'error': f'获取热门个股失败: {str(e)}'}


# ========== 搜索 ==========

def search_stocks(keyword):
    """搜索个股 - 通过腾讯批量查询匹配"""
    # 只搜索常见股票列表
    try:
        common = [
            'sz000858', 'sh600519', 'sz300750', 'sz000333', 'sz002415',
            'sz000002', 'sz000001', 'sz002594', 'sz300059', 'sz002475',
            'sh601318', 'sh600036', 'sh600900', 'sh601166', 'sh600276',
            'sz002714', 'sz002304', 'sz000568', 'sz000651', 'sz300124',
        ]
        # 动态生成一些代码
        all_codes = list(common)
        for prefix in ['sh600', 'sh601', 'sh603', 'sh688', 'sz000', 'sz002', 'sz300']:
            for i in range(0, 100, 5):
                code = f'{prefix}{(1+i):03d}'
                if code not in all_codes:
                    all_codes.append(code)

        raw = _curl(f'https://qt.gtimg.cn/q={",".join(all_codes[:120])}')
        records = []
        for line in raw.strip().split('\n'):
            p = _parse_tencent_stock(line)
            if p and p['code'] and p['name'] and keyword in p['name']:
                records.append({
                    'code': p['code'],
                    'name': p['name'],
                    'price': p['price'],
                    'change_pct': p['change_pct'],
                })
        return records[:20]
    except Exception as e:
        return {'error': f'搜索失败: {str(e)}'}


# ========== 指数历史（East Money K线API，已验证可用） ==========

def get_index_history(days=60):
    """获取大盘指数历史数据"""
    try:
        result = {}
        for name, em_id in [
            ('上证指数', '1.000001'),
            ('深证成指', '0.399001'),
            ('创业板指', '0.399006'),
        ]:
            raw = _curl(
                f'https://push2his.eastmoney.com/api/qt/stock/kline/get'
                f'?secid={em_id}'
                f'&ut=fa5fd1943c7b386f172d6893dbfd32bb'
                f'&fields1=f1,f2,f3,f4,f5,f6'
                f'&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
                f'&klt=101&fqt=1&end=20500101&lmt={days}',
                encoding='utf-8'
            )
            data = json.loads(raw)
            klines = data.get('data', {}).get('klines', [])
            dates, closes, opens, highs, lows, volumes = [], [], [], [], [], []
            for line in klines:
                parts = line.split(',')
                dates.append(parts[0])
                closes.append(float(parts[2]))
                opens.append(float(parts[1]))
                highs.append(float(parts[3]))
                lows.append(float(parts[4]))
                volumes.append(float(parts[5]))
            result[name] = {
                'dates': dates, 'close': closes,
                'open': opens, 'high': highs, 'low': lows,
                'volume': volumes,
            }
        return result
    except Exception as e:
        return {'error': f'获取指数历史数据失败: {str(e)}'}
