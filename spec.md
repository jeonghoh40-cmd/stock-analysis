# AI 주식 스크리닝 v4 — Technical Spec

> 스코어링 알고리즘, 임계값, API 명세, 파일 구조를 기술합니다.

---

## 1. 점수 체계

### 1-1. 기술적 점수 (−100 ~ +100)

`score_technical()` — `stock_advisor_v4.py:247`

| 지표 | 범위 | 매수 조건 → 점수 | 매도 조건 → 점수 |
|------|------|-----------------|-----------------|
| **RSI(14)** | ±35 | <20 → +35 / <30 → +20 / <40 → +8 | >80 → −35 / >70 → −20 / >60 → −8 |
| **Stochastic K** | ±10 | <20 → +10 / <30 → +5 | >80 → −10 / >70 → −5 |
| **MACD Histogram** | ±15 | >0 → +15 | ≤0 → −15 |
| **이동평균 정배열** | ±15 | 가격>MA20>MA60 → +15 / 가격>MA20 → +7 | 가격<MA20<MA60 → −15 / 가격<MA20 → −7 |
| **MA5 vs MA20** | ±8 | MA5>MA20 → +8 | MA5≤MA20 → −8 |
| **5일 모멘텀** | ±8 | >5% → +8 / >2% → +4 | <−5% → −8 / <−2% → −4 |
| **ADX 보정** | ±4 | ADX>25 + 상승DI → 최대 +4 증폭 | ADX>25 + 하락DI → 최대 −4 | ADX<15 → 전체 신호 ×0.8 감쇠 |
| **OBV Trend** | ±5 | >0.05 → +5 | <−0.05 → −5 |
| **52주 위치** | ±5 | >85% → +5 / <15% → +3 / >70% → +2 | <30% → −2 |

### 1-2. 펀더멘털 점수 (−30 ~ +30)

`score_fundamental()` — `stock_advisor_v4.py:309`

| 지표 | 범위 | 기준값 → 점수 |
|------|------|--------------|
| **P/E** | ±12 | <10 → +12 / <15 → +8 / <20 → +4 / <30 → 0 / <50 → −8 / ≥50 → −12 |
| **P/B** | ±8 | <0.8 → +8 / <1.5 → +4 / <3.0 → 0 / <5.0 → −4 / ≥5.0 → −8 |
| **ROE** | ±6 | >25% → +6 / >15% → +4 / >10% → +2 / <0% → −6 |
| **순이익률** | ±4 | >20% → +4 / >10% → +2 / <0% → −4 |

### 1-3. 투자자 가중치 보정

`score_with_investor_weight()` — `stock_advisor_v4.py:349`

| 조건 | 가산점 |
|------|--------|
| Pelosi 매수 종목 | +pelosi_score |
| ARK 편입 종목 | +ark_score |
| 국내 유명 투자자 종목 | +korean_investor_score |
| Pelosi + ARK 동시 해당 | +5 (추가 보너스) |

### 1-4. 종합 점수

```
종합 점수 = clamp(기술적 점수 + 투자자 가중치, −100, +100)
           → 펀더멘털 점수는 STEP 2에서 별도 반영 (정렬 기준에 포함)
```

---

## 2. ATR 기반 손절가

```
손절가 = 현재가 − (2.0 × ATR14)
ATR% = ATR / 현재가 × 100
```

---

## 3. 스크리닝 통과 기준

`screen_one()` — `stock_advisor_v4.py:369`

```
필수 조건:
  - yfinance 데이터 존재
  - 최소 65일 이상 거래 이력
  - data_cleaner.clean() 통과 (이상가격 필터)

통과 후 score 기준으로 정렬:
  - 매수 TOP: 상위 N개 (양수 우선)
  - 매도 TOP: 하위 N개 (음수 우선, 역순)
```

---

## 4. 데이터 소스 명세

### 4-1. 가격 데이터

| 항목 | 라이브러리 | 파라미터 |
|------|-----------|---------|
| 스크리닝용 OHLCV | `yf.download()` | period=12mo, interval=1d, timeout=10 |
| 거시지표 | `yf.Ticker().history()` | period=5d, timeout=10 |
| 섹터 ETF | `yf.Ticker().history()` | period=20d, timeout=10 |
| 해외 스냅샷 | `yf.Ticker().history()` | period=10d, timeout=10 |
| 펀더멘털 | `yf.Ticker().fast_info` | 실시간 |

### 4-2. 외부 API

| 항목 | URL | 응답 |
|------|-----|------|
| Fear & Greed | `https://api.alternative.me/fng/?limit=3` | JSON (value, value_classification) |
| 연합뉴스 RSS | `https://www.yonhapnewstv.co.kr/category/news/economy/feed/` | RSS XML |
| 동아경제 RSS | `https://rss.donga.com/economy.xml` | RSS XML |
| BusinessInsider | `https://feeds.feedburner.com/businessinsider` | RSS XML |
| 증권사 리서치 | KIS OpenAPI (404 오류 중) | JSON |

### 4-3. Fear & Greed 해석 기준

| 지수 범위 | 레이블 | 전략 시사점 |
|----------|--------|------------|
| 0 ~ 24 | Extreme Fear | 극도공포 → 역발상 매수 기회 |
| 25 ~ 49 | Fear | 공포 → 관망 |
| 50 ~ 74 | Greed | 탐욕 → 신중 |
| 75 ~ 100 | Extreme Greed | 극도탐욕 → 매도 고려 |

---

## 5. Claude 프롬프트 명세

**모델**: `claude-sonnet-4-6`
**max_tokens**: 5,000
**temperature**: 0

### 입력 구조

```
[날짜] 주식 애널리스트 투자 의견 작성

[외부 변수] (external_events.json)
거시: USD/KRW:N | WTI:N | VIX:N | ...
심리: Fear&Greed N/100 [레이블]
섹터5일: XLK:+N% | XLE:+N% | ...
해외: NVDA:N(+N%) | TSMC:N(+N%) | ...
뉴스: 헤드라인 10건

유명투자자 관심종목:
Pelosi: NVDA(보유) / AAPL(보유) / ...
ARK: TSLA(편입) / COIN(편입) / ...

국내테마 상위종목:
[반도체] 종목A(+72) / 종목B(+68) / ...

[KR매수] 종목1: 가격, RSI, ATR, ADX, PE, ROE, ...  ← 확대 후보 TOP10
[KQ매수] ...  ← 확대 후보 TOP6
[US매수] ...  ← 확대 후보 TOP10
[KR매도] ...
[KQ매도] ...
[US매도] ...

출력 형식 (JSON 먼저, 상세 분석 이후):
```json
{"top_buy":[...],"top_sell":[...],"market":"...","risk":"...","fg_signal":"매수|관망|매도"}
```
━━━ 🌐 시장 총평 ━━━
시장판단 / 강세섹터 / 핵심전략 / 주요리스크

━━━ 🟢 KR 매수 추천 ━━━
① 종목명 (티커) ★등급
📌 매수논리 : 기술적 + 펀더멘털 핵심 근거 1~2줄
🏢 비즈니스 : 실적개선·매출성장·마진확대·신사업·섹터 모멘텀 등 비즈니스 상황 1줄
💰 분할매수 / 🎯 목표가 / 🛑 손절가
📊 펀더멘털 : P/E·ROE·EPS성장률·이익률 등 핵심 지표 1줄

━━━ 🔴 KR 매도 추천 ━━━
① 종목명 (티커) ▼
📌 매도논리 : 기술적 + 펀더멘털 핵심 근거 1~2줄
🔍 리스크요인 : 밸류에이션·실적악화·재무구조·테마 소멸·업황 둔화 1줄
📉 매도전략 / 🎯 하락목표

... (KQ·US 매수/매도 동일 구조)
```

### 토큰 초과 시 축소 정책

```
프롬프트 > 28,000자 → 각 블록에서 종목 1개씩 순차 제거
최소 1개는 유지
```

---

## 6. 유니버스 관리

### 파일 구조

```
universe.py
├── UNIVERSE (정적 dict)
│   ├── 🇰🇷 국내           (54개 — KOSPI 대형주 anchor)
│   ├── 🛡️ 코스닥 방산·보안  (11개)
│   ├── 🇰🇷 국내 ETF        (10개 — KODEX·TIGER 섹터 ETF)   ← 신규
│   ├── 🇰🇷 코스닥 테마      (18개 — 반도체장비·2차전지·바이오·우주) ← 신규
│   ├── 🇰🇷 코스피 테마      (12개 — 에너지·방산·전력기기)    ← 신규
│   ├── 🇺🇸 미국            (60개 — 빅테크 anchor)
│   └── 🇨🇳 중국ETF         ( 6개 — KRX 상장)
│
├── DELIST_BLACKLIST (set) — 영구 제외 티커 (universe.py에 정의)
│
├── get_kospi200()    — FinanceDataReader 시총 상위 200 (24h 캐시)
├── get_kosdaq150()   — FinanceDataReader 시총 상위 150 (24h 캐시)
├── get_sp500_top20() — yfinance 시총 상위 20 (6h 캐시)
├── get_recent_ipos() — universe_ipo_watchlist.json (180일)
└── get_kr_pools()    — KOSPI200 + 🇰🇷 국내 ETF + 🇰🇷 코스피 테마 병합
                        KOSDAQ150 + 🇰🇷 코스닥 테마 병합
                        DELIST_BLACKLIST 제외 후 반환

stock_advisor_v4.py
└── US_POOL (dict, 83개)
    ├── 빅테크·AI (AAPL·NVDA·MSFT·GOOGL 등)
    ├── AI 인프라·반도체 (ARM·MRVL·SMCI·VRT·ASML·ANET)
    ├── 금융 (V·MA·JPM·GS·BRK-B·BAC·WFC·SCHW·BLK)
    ├── 헬스케어 (JNJ·LLY·UNH·PFE·NVO)
    ├── 에너지 (XOM·CVX·COP·OXY·DVN·FANG·VLO·PSX·HAL)
    ├── 방산 (LMT·RTX·NOC·GD·BA·LHX)
    ├── 원전·전력 (CEG·VST·CCJ·NRG·NEE)
    ├── 소비재·산업재 (WMT·COST·CAT·DIS)
    ├── 미국 섹터 ETF (XLE·XLK·XLF·XLV·XLI·XLP·XLU·XLB)
    └── 테마 ETF (SMH·ITA·GLD·USO·QQQ·ARKK)
```

### 블랙리스트 현황 (universe.py DELIST_BLACKLIST)

| 티커 | 사유 |
|------|------|
| 068670.KS | 상장폐지 |
| 426260.KQ | 상장폐지 |
| 457400.KS | yfinance 데이터 없음 (TIGER K방산 ETF) |

---

## 7. 캐시 파일 명세

| 파일 | 유효 기간 | 형식 | 비고 |
|------|----------|------|------|
| `cache/screening_YYYYMMDD.json` | 당일 / 3일 초과 자동 삭제 | JSON | KOSPI·KOSDAQ·US 결과 전체 |
| `cache/broker_picks_YYYYMMDD.json` | 당일 | JSON | 증권사 추천 종목 |
| `cache/{md5hash}.json` | 당일 / 7일 초과 자동 삭제 | JSON | Claude 분석 결과 (32자리 MD5 이름) |
| `cache/{ticker}_fund.json` | 7일 | JSON | 종목별 펀더멘털 |

---

## 8. 성능 추적 DB 스키마

**파일**: `stock_performance.db` (SQLite)

```sql
-- 일별 추천 기록
CREATE TABLE recommendations (
    date        TEXT,
    market      TEXT,   -- KOSPI·KOSDAQ·US
    action      TEXT,   -- buy·sell
    ticker      TEXT,
    name        TEXT,
    price       REAL,
    score       INTEGER
);

-- 가격 추적 (추천 후 수익률 계산용)
CREATE TABLE price_tracking (
    ticker      TEXT,
    date        TEXT,
    price       REAL
);
```

---

## 9. 환경 변수 (.env)

| 변수 | 필수 | 용도 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API 인증 |
| `EMAIL_USER` | ✅ | Gmail 발신 계정 |
| `EMAIL_PASS` | ✅ | Gmail 앱 비밀번호 |
| `EMAIL_TO` | ✅ | 수신 주소 |
| `EMAIL_FROM` | ✅ | 발신 주소 |
| `SMTP_SERVER` | ✅ | 기본값: smtp.gmail.com |
| `SMTP_PORT` | ✅ | 기본값: 587 |
| `TELEGRAM_BOT_TOKEN` | ❌ | 텔레그램 알림 (미사용 시 생략) |
| `TELEGRAM_CHAT_ID` | ❌ | 텔레그램 채팅 ID |
| `DART_API_KEY` | ❌ | 공시 데이터 수집 |
| `KIS_APP_KEY` | ❌ | 한국투자증권 리서치 (현재 404) |

---

## 10. 병렬 처리 설정

| 단계 | 방식 | 동시 실행 수 |
|------|------|------------|
| STEP 1 KOSPI  | ThreadPoolExecutor | 8 |
| STEP 1 KOSDAQ | ThreadPoolExecutor | 6 |
| STEP 1 US     | ThreadPoolExecutor | 8 |
| STEP 2 펀더멘털 | ThreadPoolExecutor | 내부 설정 |
| STEP 3 보조 수집 | threading.Thread | 6 (동시) |

yfinance 동시 접속 제한: `Semaphore(8)` (`_YF_SEM`)

---

## 11. 주요 상수

```python
# stock_advisor_v4.py
RECOMMEND_COUNT    = {"KOSPI": 5, "KOSDAQ": 3, "US": 5}
SELL_COUNT         = {"KOSPI": 3, "KOSDAQ": 2, "US": 3}
_MAX_PROMPT_CHARS  = 28_000   # Claude 프롬프트 상한
_FUND_CACHE_DAYS   = 7        # 펀더멘털 캐시 유효일
_last_claude_structured: dict = {}  # 최근 Claude JSON 구조화 결과 (전역)

# universe.py
_KR_INDEX_CACHE_TTL_SEC = 24 * 3600   # KOSPI/KOSDAQ 지수 24시간 캐시
_SP500_CACHE_TTL_SEC    =  6 * 3600   # S&P500 Top20 6시간 캐시
_LIQUIDITY_THRESHOLD    = 0.3         # 유동성 급감 판정 (20일 평균 대비 30%)
_LIQUIDITY_LOOKBACK     = 3           # 최근 3일 평균으로 비교
```

## 12. 주요 함수 (신규)

| 함수 | 파일 | 설명 |
|------|------|------|
| `collect_investor_summary()` | `stock_advisor_v4.py` | 유명 투자자 포트폴리오 TOP5 요약 반환 |
| `get_theme_picks(all_results, top_n=3)` | `stock_advisor_v4.py` | 스크리닝 결과에서 국내 테마별 상위 종목 추출 |
| `_extract_claude_json(text)` | `stock_advisor_v4.py` | Claude 응답에서 JSON 블록 추출 (JSON 뒤 텍스트 우선) |
| `_claude_ordered(pool, claude_tickers, n)` | `stock_advisor_v4.py` | Claude 추천 순서 우선 + 부족분 점수 순 채우기 |
| `collect_kr_etf_picks(top_n=5)` | `stock_advisor_v4.py` | 국내 ETF 12개 모멘텀 분석 → 상위 5개 반환 |

---

## 13. 매수 근거·리스크 자동 생성 규칙

`_auto_analysis()` — `stock_advisor_v4.py`

### 매수 근거 (두 줄 분리 출력)

**기술적 근거** (`✅ 기술적 근거`) — 최대 3개

| 조건 | 메시지 |
|------|--------|
| RSI < 30 | "RSI N 과매도 — 기술적 반등 신호" |
| RSI < 40 | "RSI N 약과매도 — 저가 매수 구간" |
| MACD > 0 | "MACD 히스토그램 양전환 — 상승 모멘텀 확인" |
| 가격 > MA20 > MA60 | "이동평균 정배열 — 강한 상승 추세" |
| ADX > 25 + DI양전 | "ADX N 강한 추세 — 방향성 확립" |
| 52주 위치 < 20% | "52주 저점 근처 — 반등 기대" |
| 52주 위치 > 80% | "52주 고점 구간 — 상승 모멘텀 지속" |
| Stoch < 20 | "스토캐스틱 N 과매도 — 반등 가능" |
| 거래량 > 1.5x | "거래량 Nx 급증 — 수급 유입 신호" |
| 5일 모멘텀 > 3% | "5일 모멘텀 +N% — 단기 상승 흐름" |

**펀더멘털 근거** (`📈 펀더멘털`) — 최대 3개, 데이터 있을 때만 출력

| 조건 | 메시지 |
|------|--------|
| EPS 성장 > 20% | "EPS 성장 +N% — 실적 개선 가속" |
| EPS 성장 > 10% | "EPS 성장 +N% — 이익 성장 확인" |
| ROE > 25% | "ROE N% — 탁월한 자본 효율" |
| ROE > 15% | "ROE N% — 고수익성 비즈니스" |
| 순이익률 > 20% | "순이익률 N% — 고마진 구조" |
| 순이익률 > 10% | "순이익률 N% — 견조한 수익성" |
| P/E < 15 | "P/E N — 저평가 가치 매력" |
| P/B < 1.0 | "P/B N — 자산 대비 저평가" |

### 리스크 (두 줄 분리 출력)

**기술적 리스크** (`⚠️ 기술적 리스크`) — 최대 3개

| 조건 | 메시지 |
|------|--------|
| RSI > 60 | "RSI N — 추가 과열 시 조정 가능" |
| ADX < 20 | "ADX N 횡보 — 추세 신뢰도 낮음" |
| 5일 모멘텀 < -2% | "5일 모멘텀 N% — 단기 하락 압력" |
| 가격 < MA20 | "MA20 하회 — 지지선 붕괴 주의" |
| BB > 85% | "BB N% — 상단 근접, 단기 과열" |
| Stoch > 75 | "스토캐스틱 N — 단기 과매수" |
| 거래량 < 0.5x | "거래량 Nx 위축 — 상승 동력 부족" |
| 52주 위치 > 90% | "52주 신고가 N% — 차익 실현 압력" |

**펀더멘털 리스크** (`🔍 펀더멘털 리스크`) — 최대 3개, 데이터 있을 때만 출력

| 조건 | 메시지 |
|------|--------|
| P/E > 50 | "P/E N — 밸류에이션 과부담" |
| P/E > 30 | "P/E N — 고평가, 실적 미달 시 급락 위험" |
| EPS 성장 < -10% | "EPS -N% 역성장 — 실적 악화 추세" |
| EPS 성장 < 0% | "EPS 감소 N% — 이익 모멘텀 약화" |
| ROE < 0% | "ROE 음수 — 적자 기업 구조" |
| ROE < 5% | "ROE N% — 낮은 자본 효율" |
| 순이익률 < 0% | "순이익률 N% — 수익성 적자" |
| 부채비율 > 200% | "부채비율 N% — 재무 레버리지 부담" |
| P/B > 5 | "P/B N — 자산 대비 고평가" |

---

## 14. 국내 유망 ETF TOP 5

`collect_kr_etf_picks()` — STEP 3 병렬 수집

**모멘텀 점수** = 5일 수익률 × 2 + 20일 수익률 × 1

**ETF 유니버스** (`_KR_ETF_LIST`, 12개):

| 티커 | 이름 |
|------|------|
| 069500.KS | KODEX 200 |
| 091160.KS | KODEX 반도체 |
| 305720.KS | KODEX 2차전지 |
| 091180.KS | KODEX 자동차 |
| 244580.KS | KODEX 바이오 |
| 133690.KS | TIGER 미국나스닥100 |
| 379800.KS | KODEX 미국S&P500 |
| 232080.KS | TIGER 코스닥150 |
| 329200.KS | TIGER K-방산 |
| 278540.KS | KODEX 글로벌AI |
| 364980.KS | TIGER 글로벌리튬&2차전지 |
| 381170.KS | TIGER 글로벌반도체 |

**리포트 출력 형식**:
```
📦 국내 유망 ETF TOP 5
N위  ETF명 (티커)
     현재가: N  전일: ▲N%  5일: ▲N%  20일: ▲N%
     주요 구성: 종목1 / 종목2 / 종목3 / 종목4 / 종목5
```
