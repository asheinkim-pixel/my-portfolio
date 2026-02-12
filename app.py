"""
📊 포트폴리오 실시간 시세 서버
- 네이버 금융 스크래핑 프록시
- PWA 프론트엔드 서빙
- Render 무료 배포 지원
"""

from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ─── 종목 코드 (로컬 폴백용) ───
STOCK_CODES = {
    '삼성전자': '005930', '삼성전자우': '005935',
    'SK하이닉스': '000660', 'LG에너지솔루션': '373220',
    '삼성바이오로직스': '207940', '현대차': '005380', '기아': '000270',
    'NAVER': '035420', '네이버': '035420', '카카오': '035720',
    'KB금융': '105560', '신한지주': '055550', '삼성물산': '028260',
    'POSCO홀딩스': '005490', '포스코홀딩스': '005490',
    'LG화학': '051910', '삼성SDI': '006400',
    '현대모비스': '012330', 'LG전자': '066570',
    'SK이노베이션': '096770', '셀트리온': '068270',
    '삼성생명': '032830', 'SK텔레콤': '017670',
    'KT&G': '033780', 'LG생활건강': '051900',
    '한국전력': '015760', '삼성화재': '000810',
    'HD현대중공업': '329180', '기업은행': '024110',
    '우리금융지주': '316140', '하나금융지주': '086790',
    'SK': '034730', 'LG': '003550',
    '한화에어로스페이스': '012450', '한국항공우주': '047810',
    '현대로템': '064350', '두산에너빌리티': '034020',
    '에코프로비엠': '247540', '알테오젠': '196170',
    'HLB': '028300', '에코프로': '086520',
    '크래프톤': '259960', '펄어비스': '263750',
    '리노공업': '058470', 'SK바이오팜': '326030',
    'SK스퀘어': '402340', '삼성전기': '009150',
    '고려아연': '010130', '포스코퓨처엠': '003670',
    'LS일렉트릭': '010120', '효성중공업': '298040',
    'KT': '030200', '한화': '000880',
    # ETF
    'KODEX 200': '069500', 'KODEX 레버리지': '122630',
    'KODEX 인버스': '114800', 'TIGER 200': '102110',
    'TIGER 미국S&P500': '360750', 'TIGER 미국나스닥100': '133690',
    'KODEX 미국S&P500': '379800',
}

# ─── 캐시 ───
price_cache = {}
search_cache = {}
PRICE_CACHE_TTL = 15      # 15초
SEARCH_CACHE_TTL = 300    # 5분
MAX_CACHE_SIZE = 500


def cleanup_cache(cache, max_size):
    """캐시 크기 제한"""
    if len(cache) > max_size:
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k][0])
        for k in sorted_keys[:len(cache) - max_size // 2]:
            del cache[k]


def extract_naver_stock_name(soup):
    """네이버 종목 상세페이지에서 종목명을 최대한 안정적으로 추출"""
    # 1) 기존 선택자
    el = soup.select_one('.wrap_company h2 a')
    if el and el.text.strip():
        return el.text.strip()
    el = soup.select_one('.h_company h2')
    if el and el.text.strip():
        return el.text.strip()

    # 2) OG 메타 태그 (페이지 구조가 바뀌어도 비교적 안정적)
    meta = soup.select_one('meta[property="og:title"]')
    if meta and meta.get('content'):
        title = meta['content'].strip()
        # 예: "현대차2우B : 네이버 금융"
        if ':' in title:
            title = title.split(':', 1)[0].strip()
        if title:
            return title

    # 3) <title> 태그 fallback
    if soup.title and soup.title.text:
        t = soup.title.text.strip()
        if ':' in t:
            t = t.split(':', 1)[0].strip()
        if t:
            return t

    return None



def search_stock_naver(query):
    """네이버 금융 종목 검색"""
    try:
        cache_key = f"s_{query}"
        if cache_key in search_cache:
            ts, result = search_cache[cache_key]
            if time.time() - ts < SEARCH_CACHE_TTL:
                return result

        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
        }


        # 6자리 코드(숫자/문자 포함) 직접 조회: 검색 페이지 파싱이 깨져도 추가 가능하게
        if len(query) == 6 and query.isalnum():
            try:
                url = f'https://finance.naver.com/item/main.naver?code={query}'
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200 and resp.text:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    name = extract_naver_stock_name(soup)

                    # 이름을 못 뽑아도 최소한 코드로는 등록 가능하게
                    if not name:
                        name = query.upper()

                    result = [{'name': name, 'code': query.upper()}]
                    search_cache[cache_key] = (time.time(), result)
                    return result
            except Exception:
                pass


        # 네이버 검색 페이지
        url = 'https://finance.naver.com/search/searchList.naver'
        resp = requests.get(url, params={'query': query}, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        seen = set()
        for item in soup.select('.tbl_search tbody tr')[:15]:
            try:
                a = item.select_one('td a.tltle')
                if not a:
                    continue
                name = a.text.strip()
                link = a.get('href', '')
                if 'code=' in link:
                    code = link.split('code=')[1].split('&')[0]
                    if len(code) == 6 and code.upper() not in seen:
                        seen.add(code.upper())
                        results.append({'name': name, 'code': code.upper()})
            except Exception:
                continue

        # 로컬 폴백
        if not results:
            for name, code in STOCK_CODES.items():
                if query.lower() in name.lower():
                    results.append({'name': name, 'code': code})

        search_cache[cache_key] = (time.time(), results)
        cleanup_cache(search_cache, MAX_CACHE_SIZE)
        return results

    except Exception as e:
        print(f"Search error: {e}")
        return []


def get_stock_price(code):
    """네이버 금융 시세 조회"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        url = f'https://finance.naver.com/item/main.naver?code={code}'
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 현재가
        price = None
        el = soup.select_one('.no_today .blind')
        if el:
            price = int(el.text.replace(',', '').strip())
        if not price:
            el = soup.select_one('.rate_info .blind')
            if el:
                price = int(el.text.replace(',', '').strip())
        if not price:
            return None

        # 등락
        change = 0
        change_rate = 0.0
        try:
            exday = soup.select_one('.no_exday')
            if exday:
                blind = exday.select_one('.blind')
                if blind:
                    val = int(blind.text.replace(',', '').strip())
                    text = exday.text
                    change = val if '상승' in text else -val if '하락' in text else 0

                blinds = exday.select('.blind')
                if len(blinds) >= 2:
                    r = blinds[1].text.replace('%', '').replace('+', '').replace('-', '').strip()
                    if r:
                        change_rate = float(r)
                        if '하락' in text:
                            change_rate = -change_rate
        except Exception:
            pass

        return {
            'price': price,
            'change': change,
            'changeRate': round(change_rate, 2)
        }

    except Exception as e:
        print(f"Price error for {code}: {e}")
        return None


# ─── API 엔드포인트 ───

@app.route('/')
def index():
    """PWA 메인 페이지"""
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
    results = search_stock_naver(q)
    return jsonify(results[:10])


@app.route('/api/stock/<code>')
def api_stock(code):
    # 캐시
    cache_key = code
    if cache_key in price_cache:
        ts, data = price_cache[cache_key]
        if time.time() - ts < PRICE_CACHE_TTL:
            return jsonify(data)

    data = get_stock_price(code)
    if data:
        result = {
            'success': True,
            'code': code,
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
    """여러 종목 일괄 조회 (모바일 최적화)"""
    codes = request.json.get('codes', [])
    results = []
    for code in codes[:20]:  # 최대 20개
        cache_key = code
        if cache_key in price_cache:
            ts, data = price_cache[cache_key]
            if time.time() - ts < PRICE_CACHE_TTL:
                results.append(data)
                continue

        data = get_stock_price(code)
        if data:
            result = {
                'success': True,
                'code': code,
                'price': data['price'],
                'priceStr': f"{data['price']:,}",
                'change': data['change'],
                'changeRate': data['changeRate']
            }
            price_cache[cache_key] = (time.time(), result)
            results.append(result)
            time.sleep(0.3)  # 네이버 차단 방지

    cleanup_cache(price_cache, MAX_CACHE_SIZE)
    return jsonify({'success': True, 'results': results})


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f"🚀 서버 시작: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
