"""
📊 포트폴리오 실시간 시세 서버 v2
- 네이버 JSON API 사용 (HTML 스크래핑 제거)
- 3단계 폴백: polling API → m.stock API → api.stock
- Render 무료 배포 지원
"""

from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import requests
import json
import time
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ─── 캐시 ───
price_cache = {}
search_cache = {}
PRICE_CACHE_TTL = 15
SEARCH_CACHE_TTL = 300
MAX_CACHE_SIZE = 500

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Referer': 'https://m.stock.naver.com/',
    'Accept': 'application/json, text/plain, */*',
}


def cleanup_cache(cache, max_size):
    if len(cache) > max_size:
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k][0])
        for k in sorted_keys[:len(cache) - max_size // 2]:
            del cache[k]


# ═══════════════════════════════════════
# 종목 검색 (다단계 폴백)
# ═══════════════════════════════════════

def search_stock(query):
    """종목 검색 - 네이버 자동완성 JSON API"""
    try:
        cache_key = f"s_{query}"
        if cache_key in search_cache:
            ts, result = search_cache[cache_key]
            if time.time() - ts < SEARCH_CACHE_TTL:
                return result

        results = []

        # ① 네이버 증권 자동완성 API (가장 안정적)
        try:
            url = 'https://ac.stock.naver.com/ac'
            params = {'q': query, 'target': 'stock'}
            r = requests.get(url, params=params, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()
                items = data.get('items', [])
                for item in items[:10]:
                    code = item.get('code', '')
                    name = item.get('name', '')
                    if code and name:
                        results.append({'name': name, 'code': code})
                if results:
                    print(f"[Search OK - ac.stock] '{query}' → {len(results)} results")
        except Exception as e:
            print(f"[Search ① ac.stock] failed: {e}")

        # ② m.stock.naver.com 검색 API
        if not results:
            try:
                url = f'https://m.stock.naver.com/api/search/all'
                params = {'query': query}
                r = requests.get(url, params=params, headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    # 응답 구조가 여러 형태일 수 있음
                    stock_list = (
                        data.get('stocks', []) or
                        data.get('result', {}).get('stocks', []) or
                        data.get('result', {}).get('d', []) or
                        []
                    )
                    for item in stock_list[:10]:
                        code = item.get('code', item.get('itemCode', item.get('cd', '')))
                        name = item.get('name', item.get('stockName', item.get('nm', '')))
                        if code and name:
                            results.append({'name': name, 'code': code})
                    if results:
                        print(f"[Search OK - m.stock] '{query}' → {len(results)} results")
            except Exception as e:
                print(f"[Search ② m.stock] failed: {e}")

        # ③ 6자리 종목코드 직접 입력인 경우 → 바로 시세 조회
        if not results and len(query) == 6 and query.isalnum():
            price_data = get_stock_price(query)
            if price_data and price_data.get('name'):
                results.append({'name': price_data['name'], 'code': query.upper()})
                print(f"[Search OK - direct code] '{query}' → {price_data['name']}")

        search_cache[cache_key] = (time.time(), results)
        cleanup_cache(search_cache, MAX_CACHE_SIZE)
        return results

    except Exception as e:
        print(f"Search error: {e}")
        return []


# ═══════════════════════════════════════
# 주가 조회 (다단계 폴백)
# ═══════════════════════════════════════

def parse_polling_response(text, code):
    """polling API 응답 파싱 (JSON-like but not strict JSON)"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            cleaned = text.replace("null", "None").replace("true", "True").replace("false", "False")
            data = eval(cleaned)
        except Exception:
            return None

    try:
        areas = data.get('result', {}).get('areas', [])
        if not areas:
            return None
        datas = areas[0].get('datas', [])
        if not datas:
            return None

        d = datas[0]
        price = int(d.get('nv', 0))
        if price <= 0:
            return None

        change = int(d.get('cv', 0))
        change_rate = float(d.get('cr', 0))
        name = d.get('nm', '')

        # sv: 부호 (1=상승, 2=하락, 3=보합, 4=상한, 5=하한)
        sign = str(d.get('sv', '3'))
        if sign in ('2', '5'):
            change = -abs(change)
            change_rate = -abs(change_rate)
        elif sign in ('1', '4'):
            change = abs(change)
            change_rate = abs(change_rate)

        return {
            'name': name,
            'price': price,
            'change': change,
            'changeRate': round(change_rate, 2)
        }
    except Exception:
        return None


def parse_mstock_response(data):
    """m.stock / api.stock 응답 파싱 - 부호 포함"""
    try:
        # 현재가
        price_str = str(
            data.get('closePrice', '') or
            data.get('now', '') or
            data.get('currentPrice', '') or
            '0'
        )
        price = int(price_str.replace(',', '').replace('+', '').replace('-', '').strip())
        if price <= 0:
            return None

        # 전일대비 (부호 포함 가능)
        change_str = str(
            data.get('compareToPreviousClosePrice', '') or
            data.get('change', '') or
            '0'
        )
        change_clean = change_str.replace(',', '').strip()
        change = int(change_clean) if change_clean else 0

        # 등락률 (부호 포함 가능)
        rate_str = str(
            data.get('fluctuationsRatio', '') or
            data.get('changeRate', '') or
            '0'
        )
        rate_clean = rate_str.replace(',', '').replace('%', '').strip()
        change_rate = float(rate_clean) if rate_clean else 0.0

        # 부호 보정: compareToPreviousPrice에 부호 없을 때
        # → sign 필드 또는 비교 텍스트로 판단
        sign_code = data.get('compareToPreviousPrice', {})
        if isinstance(sign_code, dict):
            sign_code = sign_code.get('code', '')

        sign_text = str(
            data.get('stockExchangeType', {}).get('nameEng', '') if isinstance(data.get('stockExchangeType'), dict) else
            data.get('compareToPreviousPrice', '') if isinstance(data.get('compareToPreviousPrice'), str) else
            ''
        )

        # FALL / DOWN = 하락
        if str(sign_code) in ('2', '5', 'FALL', 'LOWER_LIMIT'):
            change = -abs(change)
            change_rate = -abs(change_rate)
        elif str(sign_code) in ('1', '4', 'RISE', 'UPPER_LIMIT'):
            change = abs(change)
            change_rate = abs(change_rate)
        # 부호가 이미 포함된 경우 (음수 문자열) → 그대로 사용

        name = (
            data.get('stockName', '') or
            data.get('itemName', '') or
            data.get('stockNameEng', '') or
            ''
        )

        return {
            'name': name,
            'price': price,
            'change': change,
            'changeRate': round(change_rate, 2)
        }
    except Exception as e:
        print(f"[parse_mstock] error: {e}")
        return None


def get_stock_price(code):
    """실시간 주가 조회 - m.stock 우선 (가장 정확)"""
    code = code.upper()

    # ① m.stock.naver.com API (가장 정확, 당일 등락률 신뢰)
    try:
        url = f'https://m.stock.naver.com/api/stock/{code}/basic'
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            result = parse_mstock_response(r.json())
            if result:
                print(f"[Price OK - m.stock] {code}: {result['price']:,}원 ({result['changeRate']:+}%)")
                return result
    except Exception as e:
        print(f"[Price ① m.stock] {code} failed: {e}")

    # ② api.stock.naver.com
    try:
        url = f'https://api.stock.naver.com/stock/{code}/basic'
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            result = parse_mstock_response(r.json())
            if result:
                print(f"[Price OK - api.stock] {code}: {result['price']:,}원 ({result['changeRate']:+}%)")
                return result
    except Exception as e:
        print(f"[Price ② api.stock] {code} failed: {e}")

    # ③ polling.finance.naver.com (폴백 - 캐시 지연 가능성)
    try:
        url = f'https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}'
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            result = parse_polling_response(r.text, code)
            if result:
                print(f"[Price OK - polling] {code}: {result['price']:,}원 ({result['changeRate']:+}%)")
                return result
    except Exception as e:
        print(f"[Price ③ polling] {code} failed: {e}")

    print(f"[Price FAIL] {code}: all methods failed")
    return None


# ═══════════════════════════════════════
# Flask 라우트
# ═══════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    results = search_stock(q)
    return jsonify(results[:10])


@app.route('/api/stock/<code>')
def api_stock(code):
    cache_key = code.upper()
    if cache_key in price_cache:
        ts, data = price_cache[cache_key]
        if time.time() - ts < PRICE_CACHE_TTL:
            return jsonify(data)

    data = get_stock_price(code)
    if data:
        result = {
            'success': True,
            'code': code.upper(),
            'name': data.get('name', ''),
            'price': data['price'],
            'priceStr': f"{data['price']:,}",
            'change': data['change'],
            'changeRate': data['changeRate']
        }
        price_cache[cache_key] = (time.time(), result)
        cleanup_cache(price_cache, MAX_CACHE_SIZE)
        return jsonify(result)
    return jsonify({'success': False, 'message': '조회 실패'}), 404


@app.route('/api/batch', methods=['POST'])
def api_batch():
    """여러 종목 일괄 조회"""
    codes = request.json.get('codes', [])
    results = []
    for code in codes[:20]:
        cache_key = code.upper()
        if cache_key in price_cache:
            ts, data = price_cache[cache_key]
            if time.time() - ts < PRICE_CACHE_TTL:
                results.append(data)
                continue

        data = get_stock_price(code)
        if data:
            result = {
                'success': True,
                'code': code.upper(),
                'name': data.get('name', ''),
                'price': data['price'],
                'priceStr': f"{data['price']:,}",
                'change': data['change'],
                'changeRate': data['changeRate']
            }
            price_cache[cache_key] = (time.time(), result)
            results.append(result)
            time.sleep(0.2)

    cleanup_cache(price_cache, MAX_CACHE_SIZE)
    return jsonify({'success': True, 'results': results})


@app.route('/api/debug/<code>')
def api_debug(code):
    """디버그: 각 API별 응답 + 파싱 결과 확인"""
    debug = {}

    # m.stock (최우선)
    try:
        url = f'https://m.stock.naver.com/api/stock/{code}/basic'
        r = requests.get(url, headers=HEADERS, timeout=5)
        raw = r.json() if r.status_code == 200 else {}
        parsed = parse_mstock_response(raw) if raw else None
        # 핵심 필드만 추출
        key_fields = {k: raw.get(k) for k in [
            'stockName', 'closePrice', 'compareToPreviousClosePrice',
            'fluctuationsRatio', 'compareToPreviousPrice', 'risefall'
        ] if k in raw}
        debug['m_stock'] = {
            'status': r.status_code,
            'key_fields': key_fields,
            'parsed': parsed
        }
    except Exception as e:
        debug['m_stock'] = {'error': str(e)}

    # api.stock
    try:
        url = f'https://api.stock.naver.com/stock/{code}/basic'
        r = requests.get(url, headers=HEADERS, timeout=5)
        raw = r.json() if r.status_code == 200 else {}
        parsed = parse_mstock_response(raw) if raw else None
        key_fields = {k: raw.get(k) for k in [
            'stockName', 'closePrice', 'compareToPreviousClosePrice',
            'fluctuationsRatio', 'compareToPreviousPrice', 'risefall'
        ] if k in raw}
        debug['api_stock'] = {
            'status': r.status_code,
            'key_fields': key_fields,
            'parsed': parsed
        }
    except Exception as e:
        debug['api_stock'] = {'error': str(e)}

    # polling
    try:
        url = f'https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}'
        r = requests.get(url, headers=HEADERS, timeout=5)
        parsed = parse_polling_response(r.text, code) if r.status_code == 200 else None
        debug['polling'] = {
            'status': r.status_code,
            'body_preview': r.text[:300] if r.status_code == 200 else '',
            'parsed': parsed
        }
    except Exception as e:
        debug['polling'] = {'error': str(e)}

    return jsonify(debug)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': 'v2-json-api'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f"🚀 서버 v2 시작: http://localhost:{port}")
    print(f"   디버그: /api/debug/005930")
    app.run(host='0.0.0.0', port=port, debug=debug)
