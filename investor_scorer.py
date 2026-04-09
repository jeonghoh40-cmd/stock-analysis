"""
투자자 스코어링 모듈
────────────────────────────────────────────────────────────────
데이터 소스:
  ① Pelosi 의원   : House Stock Watcher API (라이브) + 정적 fallback
  ② ARK Invest    : arkfunds.io API (라이브) + 정적 fallback
  ③ 국내 유명투자자: 박세익·존리·이채원·김민국·강방천 (정적 큐레이션)

캐시: investor_live_cache.json (24시간 유효)
"""

import os
import sys
import json
import datetime

import requests

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_CACHE_F   = os.path.join(BASE_DIR, "investor_live_cache.json")
_CACHE_TTL = 24   # hours

# 정적 데이터 할인 계수 — 라이브 데이터 실패 시 정적 포트폴리오 영향력 감소
_STATIC_DISCOUNT = 0.5           # Pelosi/ARK 정적 시 50% 할인
_KOREAN_STATIC_DISCOUNT = 0.6    # 한국 투자자 60% (100% 정적이므로)

# ─── 캐시 I/O ──────────────────────────────────────────────────
def _load_live_cache() -> dict:
    try:
        if os.path.exists(_CACHE_F):
            with open(_CACHE_F, encoding="utf-8") as f:
                d = json.load(f)
            saved = datetime.datetime.fromisoformat(d.get("saved_at", "2000-01-01T00:00:00"))
            if (datetime.datetime.now() - saved).total_seconds() < _CACHE_TTL * 3600:
                return d
    except Exception:
        pass
    return {}

def _save_live_cache(data: dict):
    data["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(_CACHE_F, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── 라이브 API 수집 ───────────────────────────────────────────
def _fetch_live_pelosi() -> set:
    url = ("https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
           "/data/all_transactions.json")
    resp = requests.get(url, timeout=25)
    resp.raise_for_status()
    tickers: set = set()
    for t in resp.json():
        if "Pelosi" not in t.get("representative", ""):
            continue
        if t.get("type", "").lower() not in ("purchase", "buy", "exchange"):
            continue
        tk = t.get("ticker", "").strip().upper()
        if tk and 1 <= len(tk) <= 5 and tk.isalpha():
            tickers.add(tk)
    return tickers

def _fetch_live_ark() -> dict:
    funds, combined = ["ARKK", "ARKW", "ARKG", "ARKF", "ARKQ"], {}
    for fund in funds:
        try:
            resp = requests.get(
                f"https://arkfunds.io/api/v2/fund/holdings?symbol={fund}", timeout=15)
            for h in resp.json().get("holdings", []):
                tk = h.get("ticker", "").upper().strip()
                w  = float(h.get("weight", 0))
                if tk:
                    combined[tk] = round(combined.get(tk, 0.0) + w, 4)
        except Exception:
            pass
    return combined

def refresh_live_data() -> dict:
    """라이브 API 강제 갱신 (수동 호출 가능)"""
    result: dict = {}
    try:
        pelosi = list(_fetch_live_pelosi())
        result["pelosi_live"] = pelosi
        print(f"  [investor] Pelosi 라이브 픽 {len(pelosi)}개")
    except Exception as e:
        print(f"  [investor] Pelosi API 실패 (정적 데이터 사용): {e}")
    try:
        ark = _fetch_live_ark()
        result["ark_live"] = ark
        print(f"  [investor] ARK 라이브 {len(ark)}개")
    except Exception as e:
        print(f"  [investor] ARK API 실패 (정적 데이터 사용): {e}")
    _save_live_cache(result)
    return result

# ──────────────────────────────────────────────
# Nancy Pelosi 주요 보유 종목 (2024-2025 기준)
# ──────────────────────────────────────────────
PELOSI_PORTFOLIO = {
    'NVDA': {'weight': 15, 'note': 'AI 칩 대장주'},
    'MSFT': {'weight': 12, 'note': '클라우드/AI'},
    'GOOGL': {'weight': 10, 'note': '빅테크'},
    'AMZN': {'weight': 10, 'note': '이커머스'},
    'META': {'weight': 8, 'note': '소셜미디어'},
    'AAPL': {'weight': 8, 'note': '빅테크'},
    'AMD': {'weight': 7, 'note': '반도체'},
    'CRM': {'weight': 5, 'note': '클라우드'},
    'NFLX': {'weight': 5, 'note': '스트리밍'},
    'TSLA': {'weight': 3, 'note': '일부 보유'},
    'AVGO': {'weight': 5, 'note': '반도체'},
    'ORCL': {'weight': 4, 'note': '클라우드'},
    'NOW': {'weight': 3, 'note': 'SaaS'},
    'UBER': {'weight': 3, 'note': '모빌리티'},
    'COIN': {'weight': 2, 'note': '코인베이스'},
}

# ──────────────────────────────────────────────
# ARK Invest (Cathie Wood) 주요 보유 종목
# ──────────────────────────────────────────────
ARK_TOP_HOLDINGS = {
    'TSLA': {'weight': 15, 'note': '혁신형 전기차'},
    'COIN': {'weight': 10, 'note': '코인베이스'},
    'ROKU': {'weight': 8, 'note': '스트리밍'},
    'ZM': {'weight': 7, 'note': '화상회의'},
    'SHOP': {'weight': 7, 'note': '이커머스'},
    'SQ': {'weight': 6, 'note': '핀테크'},
    'PATH': {'weight': 5, 'note': 'AI'},
    'TWLO': {'weight': 5, 'note': '클라우드'},
    'DKNG': {'weight': 4, 'note': '스포츠베팅'},
    'RBLX': {'weight': 4, 'note': '메타버스'},
    'CRSP': {'weight': 4, 'note': '유전자편집'},
    'BEAM': {'weight': 3, 'note': '유전자치료'},
    'PACB': {'weight': 3, 'note': '유전체분석'},
    'TDOC': {'weight': 3, 'note': '원격의료'},
    'EXAS': {'weight': 3, 'note': '암진단'},
    'NVDA': {'weight': 5, 'note': 'AI 칩'},
    'GOOGL': {'weight': 4, 'note': '빅테크'},
    'AMZN': {'weight': 4, 'note': '클라우드'},
}

# ──────────────────────────────────────────────
# 한국 유명 투자자 포트폴리오
# ──────────────────────────────────────────────

# 1️⃣ 박세익 전무 (체슬리투자자문) - 반도체·2 차전지 사이클
PARK_SEOIK_PORTFOLIO = {
    '005930': {'weight': 15, 'note': '삼성전자 - 반도체 사이클'},
    '000660': {'weight': 12, 'note': 'SK 하이닉스 - HBM 대장주'},
    '373220': {'weight': 10, 'note': 'LG 에너지솔루션 - 2 차전지'},
    '051910': {'weight': 8, 'note': 'LG 화학 - 배터리 소재'},
    '006400': {'weight': 7, 'note': '삼성 SDI - 2 차전지'},
    '042700': {'weight': 6, 'note': '한미반도체 - HBM 장비'},
    '003670': {'weight': 5, 'note': '포스코퓨처엠 - 양극재'},
    '247540': {'weight': 5, 'note': '에코프로비엠 - 양극재'},
    '086520': {'weight': 4, 'note': '에코프로 - 2 차전지 소재'},
}

# 2️⃣ 존리 (전 메리츠자산운용) - 장기 가치투자
JOHN_LEE_PORTFOLIO = {
    '005930': {'weight': 12, 'note': '삼성전자 - 장기보유'},
    '035420': {'weight': 10, 'note': 'NAVER - 플랫폼'},
    '035720': {'weight': 8, 'note': '카카오 - 플랫폼'},
    '051910': {'weight': 7, 'note': 'LG 화학 - 화학'},
    '105560': {'weight': 6, 'note': 'KB 금융 - 금융주'},
    '055550': {'weight': 5, 'note': '신한지주 - 금융주'},
    '086790': {'weight': 5, 'note': '하나금융지주 - 금융주'},
    '005380': {'weight': 5, 'note': '현대차 - 자동차'},
    '000270': {'weight': 4, 'note': '기아 - 자동차'},
}

# 3️⃣ 이채원 의장 (라이프자산운용) - 저 PBR·지주사
LEE_CHAEWON_PORTFOLIO = {
    '005930': {'weight': 10, 'note': '삼성전자 - 저 PBR'},
    '000270': {'weight': 8, 'note': '기아 - 저 PBR'},
    '005380': {'weight': 8, 'note': '현대차 - 저 PBR'},
    '097950': {'weight': 7, 'note': 'CJ 제일제당 - 지주사'},
    '000720': {'weight': 6, 'note': '현대건설 - 저 PBR'},
    '034730': {'weight': 6, 'note': 'SK - 지주사'},
    '078930': {'weight': 5, 'note': 'GS - 지주사'},
    '009540': {'weight': 5, 'note': '한국조선해양 - 저 PBR'},
    '015760': {'weight': 4, 'note': '한국전력 - 저 PBR'},
    '032830': {'weight': 4, 'note': '삼성생명 - 금융지주'},
}

# 4️⃣ 김민국 대표 (VIP 자산운용) - 행동주의·밸류업
KIM_MINGUK_PORTFOLIO = {
    '000720': {'weight': 10, 'note': '현대건설 - 밸류업'},
    '009540': {'weight': 8, 'note': '한국조선해양 - 밸류업'},
    '015760': {'weight': 7, 'note': '한국전력 - 공기업'},
    '034730': {'weight': 6, 'note': 'SK - 지배구조'},
    '078930': {'weight': 6, 'note': 'GS - 지배구조'},
    '000720': {'weight': 5, 'note': '현대건설 - 자사주 소각'},
    '004170': {'weight': 5, 'note': '삼양홀딩스 - 지주사'},
    '000080': {'weight': 4, 'note': '미래에셋증권 - 금융주'},
}

# 5️⃣ 강방천 회장 (에셋플러스) - 장기 성장주·소비재
KANG_BANGCHEON_PORTFOLIO = {
    '005930': {'weight': 10, 'note': '삼성전자 - 장기성장'},
    '035420': {'weight': 8, 'note': 'NAVER - 플랫폼'},
    '035720': {'weight': 7, 'note': '카카오 - 플랫폼'},
    '090430': {'weight': 6, 'note': '아모레퍼시픽 - 소비재'},
    '051900': {'weight': 6, 'note': 'LG 생활건강 - 소비재'},
    '097950': {'weight': 5, 'note': 'CJ 제일제당 - 식품'},
    '271560': {'weight': 4, 'note': '오리온 - 식품'},
    '003490': {'weight': 4, 'note': '대한항공 - 항공'},
    '036570': {'weight': 4, 'note': '엔씨소프트 - 게임'},
}

# ──────────────────────────────────────────────
# Damodaran 밸류에이션 기준
# ──────────────────────────────────────────────
DAMODARAN_METRICS = {
    'risk_free_rate': 4.50,      # 무위험 금리 (10 년물 국채)
    'equity_risk_premium': 4.80, # 시장 리스크 프리미엄
    'expected_market_return': 9.30,  # 기대 수익률
}

# ──────────────────────────────────────────────
# Howard Marks 사이클 단계
# ──────────────────────────────────────────────
MARKS_CYCLE_STAGES = {
    'early_recovery': {'stage': 1, 'description': '초기 회복기', 'strategy': '공격적 매수'},
    'mid_expansion': {'stage': 2, 'description': '중기 확장기', 'strategy': '중립'},
    'late_expansion': {'stage': 3, 'description': '후기 확장기', 'strategy': '방어적'},
    'recession': {'stage': 4, 'description': '경기침체기', 'strategy': '현금 보유'},
}

# ──────────────────────────────────────────────
# Tom Lee S&P 전망 (2025)
# ──────────────────────────────────────────────
TOM_LEE_OUTLOOK = {
    'sp500_target': 6500,
    'outlook': 'Bullish',
    'key_drivers': ['AI 투자 확대', '금리 인하 기대', '기업 이익 성장'],
}


def get_investor_score(ticker: str) -> dict:
    """
    종목의 투자자 스코어를 계산합니다.
    - 미국 주식: Pelosi(라이브 우선), ARK(라이브 우선)
    - 한국 주식: 박세익·존리·이채원·김민국·강방천 (정적 큐레이션)

    Args:
        ticker: 종목 티커 (예: 'NVDA', '005930', '005930.KS')
    """
    # 한국 종목 suffix 제거
    clean = ticker.upper().replace(".KS", "").replace(".KQ", "")

    # 라이브 캐시 로드 (없으면 갱신 시도, 실패 시 정적 사용)
    live = _load_live_cache()

    # ── Pelosi ──────────────────────────────────────────────────
    pelosi_score   = 0
    investor_notes = []

    live_pelosi = live.get("pelosi_live", [])
    if live_pelosi:
        is_pelosi = clean in live_pelosi
    else:
        is_pelosi = clean in PELOSI_PORTFOLIO

    pelosi_source = 'live' if live_pelosi else 'static'
    if is_pelosi:
        if live_pelosi:
            pelosi_score = 15           # 라이브 API: 의회 공시 실제 매수 = 최고 점수
        else:
            w = PELOSI_PORTFOLIO.get(clean, {}).get("weight", 0)
            # weight 기반 점수: weight 10+ → 15, 5~9 → 10, 1~4 → 5
            raw = 15 if w >= 10 else (10 if w >= 5 else 5)
            pelosi_score = int(raw * _STATIC_DISCOUNT)
        investor_notes.append(
            f"Pelosi 매수: {PELOSI_PORTFOLIO.get(clean, {}).get('note', clean)}"
        )

    # ── ARK ─────────────────────────────────────────────────────
    live_ark = live.get("ark_live", {})
    if live_ark:
        is_ark  = clean in live_ark
        ark_w   = live_ark.get(clean, 0.0)
    else:
        is_ark  = clean in ARK_TOP_HOLDINGS
        ark_w   = ARK_TOP_HOLDINGS.get(clean, {}).get("weight", 0) / 100.0  # 정규화

    ark_source = 'live' if live_ark else 'static'
    if   ark_w >= 1.0: ark_score = 15
    elif ark_w >= 0.5: ark_score = 10
    elif is_ark:       ark_score = 5
    else:              ark_score = 0
    if not live_ark and ark_score > 0:
        ark_score = int(ark_score * _STATIC_DISCOUNT)

    if is_ark:
        investor_notes.append(
            f"ARK {ark_w:.1f}%: {ARK_TOP_HOLDINGS.get(clean, {}).get('note', clean)}"
        )

    # ── 국내 유명 투자자 ─────────────────────────────────────────
    korean_investors = [
        ('박세익', PARK_SEOIK_PORTFOLIO),
        ('존리',   JOHN_LEE_PORTFOLIO),
        ('이채원', LEE_CHAEWON_PORTFOLIO),
        ('김민국', KIM_MINGUK_PORTFOLIO),
        ('강방천', KANG_BANGCHEON_PORTFOLIO),
    ]
    korean_score = 0
    for inv_name, portfolio in korean_investors:
        if clean in portfolio:
            w = portfolio[clean].get("weight", 0)
            korean_score += min(5, w // 5 + 1)
            investor_notes.append(f"{inv_name}: {portfolio[clean]['note']}")
    korean_score = int(min(25, korean_score) * _KOREAN_STATIC_DISCOUNT)

    return {
        'is_pelosi_pick':        is_pelosi,
        'pelosi_score':          pelosi_score,
        'pelosi_source':         pelosi_source,
        'is_ark_pick':           is_ark,
        'ark_score':             ark_score,
        'ark_source':            ark_source,
        'ark_weight':            round(ark_w, 4),
        'korean_investor_score': korean_score,
        'is_korean_investor_pick': korean_score > 0,
        'total_score':           pelosi_score + ark_score + korean_score,
        'investor_notes':        investor_notes,
    }


def get_pelosi_top_picks() -> list:
    """Pelosi 주요 보유 종목 리스트 반환"""
    return sorted(PELOSI_PORTFOLIO.items(), key=lambda x: x[1]['weight'], reverse=True)[:10]


def get_ark_top_picks() -> list:
    """ARK 주요 보유 종목 리스트 반환"""
    return sorted(ARK_TOP_HOLDINGS.items(), key=lambda x: x[1]['weight'], reverse=True)[:10]


def get_korean_investor_picks(investor_name: str = 'all') -> dict:
    """
    한국 투자자 보유 종목 반환
    
    Args:
        investor_name: '박세익', '존리', '이채원', '김민국', '강방천', 'all'
    """
    investors = {
        '박세익': PARK_SEOIK_PORTFOLIO,
        '존리': JOHN_LEE_PORTFOLIO,
        '이채원': LEE_CHAEWON_PORTFOLIO,
        '김민국': KIM_MINGUK_PORTFOLIO,
        '강방천': KANG_BANGCHEON_PORTFOLIO,
    }
    
    if investor_name == 'all':
        return investors
    return {investor_name: investors.get(investor_name, {})}


def print_investor_summary():
    """투자자 포트폴리오 요약 출력"""
    print("\n" + "="*60)
    print("  유명 투자자 포트폴리오 요약")
    print("="*60)
    
    print("\n🇺🇸 미국 투자자")
    print("\n📌 Nancy Pelosi TOP 5:")
    for i, (ticker, info) in enumerate(get_pelosi_top_picks()[:5], 1):
        print(f"  {i}. {ticker} ({info['note']}) - 비중: {info['weight']}")
    
    print("\n📌 ARK Invest (Cathie Wood) TOP 5:")
    for i, (ticker, info) in enumerate(get_ark_top_picks()[:5], 1):
        print(f"  {i}. {ticker} ({info['note']}) - 비중: {info['weight']}")
    
    print("\n🇰🇷 한국 투자자")
    korean_investors = get_korean_investor_picks('all')
    
    for name, portfolio in korean_investors.items():
        print(f"\n📌 {name} TOP 5:")
        top5 = sorted(portfolio.items(), key=lambda x: x[1]['weight'], reverse=True)[:5]
        for i, (ticker, info) in enumerate(top5, 1):
            print(f"  {i}. {ticker} ({info['note']}) - 비중: {info['weight']}")
    
    print(f"\n📌 Damodaran 기준 금리: {DAMODARAN_METRICS['risk_free_rate']}%")
    print(f"📌 Tom Lee S&P 전망: {TOM_LEE_OUTLOOK['sp500_target']} ({TOM_LEE_OUTLOOK['outlook']})")
    print("="*60 + "\n")


if __name__ == '__main__':
    print_investor_summary()
    
    # 테스트 - 미국 주식
    print("\n=== 미국 주식 스코어 ===")
    us_tickers = ['NVDA', 'AAPL', 'MSFT', 'TSLA', 'GOOGL']
    for ticker in us_tickers:
        score = get_investor_score(ticker)
        print(f"{ticker}: Pelosi={score['pelosi_score']}, ARK={score['ark_score']}, "
              f"한국={score['korean_investor_score']}, Total={score['total_score']}")
        if score['investor_notes']:
            for note in score['investor_notes']:
                print(f"  - {note}")
    
    # 테스트 - 한국 주식
    print("\n=== 한국 주식 스코어 ===")
    kr_tickers = ['005930', '000660', '035420', '035720', '005380']
    for ticker in kr_tickers:
        score = get_investor_score(ticker)
        print(f"{ticker}: Pelosi={score['pelosi_score']}, ARK={score['ark_score']}, "
              f"한국={score['korean_investor_score']}, Total={score['total_score']}")
        if score['investor_notes']:
            for note in score['investor_notes']:
                print(f"  - {note}")
