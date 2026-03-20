# AI 주식 스크리닝 v4 — Workflow

> 전체 실행 흐름과 데이터 이동 경로를 기술합니다.

---

## 전체 흐름도

```
[실행 트리거]
     │
     ▼
[STEP 0] 캐시 정리
     │
     ▼
[STEP 1] 기술적 스크리닝 ──── yfinance (12 개월 일봉, 실시간) + MACD+ADX 복합 점수
     │        │
     │        ├─ KOSPI  ~222 개 → ThreadPoolExecutor(8)
     │        ├─ KOSDAQ ~168 개 → ThreadPoolExecutor(6)
     │        └─ US       83 개 → ThreadPoolExecutor(8)
     │
     ▼
[STEP 2] 펀더멘털 보강 ─────── yfinance fast_info (7 일 캐시)
     │        └─ 시장별 상위 10 개 대상 (P/E·P/B·ROE·순이익률)
     │
     ▼
[STEP 2-b] 종목 POOL 확대 ──── IPO + 중국 ETF 자동 편입
     │        ├─ IPO(최근 6 개월 상장) 최대 20 개 → "IPO" 풀 별도 저장
     │        └─ 중국 ETF(10 개) → 모멘텀 상위 5 개 선별
     │
     ▼
[STEP 3] 보조 데이터 수집 ───── 병렬 7 개 Thread (항상 실시간, 2 회 재시도)
     │        ├─ 거시지표  : yfinance (USD/KRW·WTI·VIX·US10Y 등 11 개)
     │        ├─ Fear&Greed: alternative.me API
     │        ├─ 섹터 ETF  : yfinance (XLK·XLE·SOXX 등 15 개)
     │        ├─ 해외 스냅샷: yfinance (NVDA·TSMC·LMT 등 9 개)
     │        ├─ 뉴스       : RSS (연합뉴스·동아·BusinessInsider)
     │        ├─ 국내 ETF  : yfinance (KODEX·TIGER 12 개 → 모멘텀 상위 5 개 선별)
     │        └─ 중국 ETF  : yfinance (TIGER·KODEX 9 개 → 모멘텀 상위 5 개 선별) ← 신규
     │
     ▼
[STEP 4] 외부 변수 + 투자자 포트폴리오 + 테마 선별
     │        ├─ external_events.json (지정학·정책 이벤트)
     │        ├─ 유명 투자자 포트폴리오 수집 → 스코어 +5 가산 후 풀 재정렬
     │        │   (Pelosi, ARK, 박세익, 존리, 이채원, 김민국, 강방천)
     │        └─ 국내 테마별 상위 종목 추출 (반도체·2 차전지·바이오 등)
     │
     ▼
[STEP 5] Claude 심층 분석 ──── Anthropic API (claude-sonnet-4-6)
     │        ├─ 입력: 확대 후보 (KOSPI 10 / KOSDAQ 6 / US 10 / IPO 8)
     │        │         + 거시·뉴스·섹터·외부변수·투자자·테마
     │        └─ JSON 출력 (top_buy / top_sell 순위) → 최종 선별 기준
     │
     ▼
[STEP 6] 최종 선별 (Claude JSON 순위 우선)
     │        ├─ Claude top_buy 순서 → 매수 KOSPI 5 / KOSDAQ 3 / US 5 / IPO 5
     │        └─ Claude top_sell 순서 → 매도 KOSPI 3 / KOSDAQ 2 / US 3
     │            (Claude 미추천 슬롯은 점수 순으로 채움)
     │
     ▼
[STEP 7] 리포트 저장
     │        ├─ report_v4.txt  (이메일 본문)
     │        └─ report_v4.html (보관용)
     │
     ▼
[STEP 8] 성능 추적
     │        ├─ stock_performance.db 추천 이력 저장
     │        └─ performance_report.txt (30 일 성과)
     │
     ▼
[STEP 9] 알림 발송
          ├─ 이메일 (HTML + plain text) → geunho@stic.co.kr
          └─ 텔레그램 (현재 미설정)
```

---

## STEP 별 상세

### STEP 0 — 캐시 정리

| 대상 | 조건 | 동작 |
|------|------|------|
| Claude 분석 캐시 | 7 일 초과 | 자동 삭제 |
| 스크리닝 캐시 | 3 일 초과 | 자동 삭제 |

---

### STEP 1 — 기술적 스크리닝

**데이터 소스**: `yf.download(ticker, period="12mo", interval="1d")`
**조건**: 최소 65 일 이상 데이터 필요 (지표 계산 최소 요건)
**병렬도**: KOSPI 8 / KOSDAQ 6 / US 8 스레드
**캐시**: 당일 `cache/screening_YYYYMMDD.json` 존재 시 재사용

**계산 지표 (종목별)**

| 지표 | 함수 | 용도 |
|------|------|------|
| RSI(14) | `_rsi()` | 과매수/과매도 |
| MACD Histogram | `_macd()` | 추세 전환 |
| MA5·MA20·MA60 | `_mas()` | 이동평균 정배열 |
| 5 일 모멘텀 | `_mom()` | 단기 방향성 |
| Bollinger Band | `_bb()` | 밴드 위치 |
| ATR(14) | `_atr()` | 손절가 산출 |
| Stochastic(14,3) | `_stochastic()` | RSI 교차 확인 |
| ADX(14) + DI | `_adx()` | 추세 강도 |
| OBV Trend | `_obv_trend()` | 거래량 추세 |
| 52 주 위치 | `_week52_pos()` | 신고가/저점 |
| 거래량 비율 | vol_cur/vol_avg | 거래량 급증 |
| **MACD+ADX 복합 (0~10)** | `score_technical()` 내 블록 | **진입 시점 삼중 확인** |

> MACD+ADX 복합 점수 세부: ADX>25 → +2, +DI>-DI → +3, MACD hist>0 → +5. 3 조건 모두 충족 시 +10 점이 기술적 총점에 가산된다.
> 결과 dict 의 `macd_adx_score` 필드 (0~10) 로 리포트에 노출된다.

**Step 3 — Entry Timing** (3 단계 프레임워크의 최종 타이밍 확인)

| 조건 | 기준 | 의미 |
|------|------|------|
| 주봉 (Weekly) MACD | 하락 멈춤 + 횡보 또는 골든크로스 기미 | 하락 추세 종료 → 중기 전환 시작 신호 |
| 일봉 ADX | > 25 + +DI > -DI | 상승 방향 추세 진입 확인 |

> **핵심 로직**: Step 2(저평가 확인) **AND** 주봉 MACD 전환 기미 **AND** ADX > 25 상승 방향
> → 세 조건 동시 충족 시 분할 매수 1 차 (50%) 시작, 주봉 MACD 골든크로스 완성 시 2 차 (50%) 추가.
> 주봉 기준 적용 이유: 일봉 노이즈 제거, 수주~수개월 단위 추세 전환 포착.

**유니버스 구성**

```
KOSPI  = FinanceDataReader 시총 상위 200 개
       + 국내 ETF 10 개 (KODEX 반도체·2 차전지 등)          ← universe.py 🇰🇷 국내 ETF
       + 코스피 테마 12 개 (S-Oil·현대로템·LS 일렉트릭 등)  ← universe.py 🇰🇷 코스피 테마
       + 증권사 추천 (당일 캐시)

KOSDAQ = FinanceDataReader 시총 상위 150 개
       + 코스닥 테마 18 개 (리노공업·HLB·알테오젠 등)      ← universe.py 🇰🇷 코스닥 테마
       + 증권사 추천 (당일 캐시)

US     = 정적 83 개 (빅테크·AI 인프라·AI 반도체·금융·헬스케어
                    에너지·방산·원전전력·소비재·섹터 ETF·테마 ETF)
       + 증권사 추천 (당일 캐시)

블랙리스트 (영구 제외, universe.py DELIST_BLACKLIST):
       068670.KS / 426260.KQ / 457400.KS
```

---

### STEP 2 — 펀더멘털 보강

**대상**: 시장별 기술적 점수 상위 10 개
**캐시**: 7 일 (종목별, `cache/{ticker}_fund.json`)
**수집 항목**: P/E · P/B · ROE · 순이익률 · EPS 성장률

**기본적 퀄리티 필터 — 3 단계 프레임워크 Step 1 + Step 2**

**Step 1 — Quality Filter** (우량 종목 스크리닝)

| 필터 | 기준 | 역할 |
|------|------|------|
| ROE | > 15% | 자기자본 수익성 — 돈을 잘 버는 기업인가 |
| 이자보상배율 (EBITDA/이자비용) | > 3 배 | 재무 건전성 — 빚을 감당할 수 있는가 |
| 비지배지분 (Minority Interest) | > 0 | 실질 연결 자회사 존재 — 자본잠식 리스크 제거 |
| EBITDA 성장률 | > 10% (YoY) | 본업 현금창출력 성장 중인가 |

**Step 2 — Valuation** (내재가치 및 저점 판별)

| 필터 | 기준 | 역할 |
|------|------|------|
| DCF 저평가 | 시가총액 ≤ DCF 내재가치 × 70% | 1 년 뒤 기대 FCF 기반 내재가치 대비 30%+ 저평가 |
| 역발상 지표 | 업종 평균 PER 미만 + FCF 우상향 | 시장이 외면하지만 현금은 늘고 있는 종목 |

> **원칙**: 기술적 지표는 진입 시점을 결정하고, 기본적 지표는 종목의 퀄리티를 결정한다.
> Step 1 전체 통과 + Step 2 하나 이상 충족 종목만 STEP 3(Entry Timing) 으로 진행.
> 데이터 미수집 (yfinance `info` 부재) 시 0 점 처리 (감점 없음) — 기존 원칙 유지.

---

### STEP 2-b — 종목 POOL 확대 (IPO + 중국 ETF)

**정책**: STEP 2 펀더멘털 보강 완료 후, 자동 편입

| 확대 POOL | 수집 방법 | 편입 수 | 가산점 |
|----------|----------|--------|--------|
| **IPO (최근 6 개월)** | `universe_utils.get_recent_ipos(days=180)` | 최대 20 개 | +10 점 |
| **중국 ETF** | `etf_recommender.CHINA_ETF_POOL` | 10 개 → 5 개 선별 | — |

**IPO 편입 로직**:
1. `universe_ipo_watchlist.json` 에서 최근 180 일 이내 상장 종목 조회
2. 당일 스크리닝 제외 종목 (`exclude_ipo`) 제외
3. 남은 종목 (최대 20 개) 을 기술적 스크리닝 태스크에 추가
4. 스크리닝 결과 `"IPO"` 풀에 별도 저장
5. IPO 종목은 데이터 부족 보완을 위해 +10 점 가산점 부여
6. 매수 추천 시 IPO 전용 슬롯 (최대 5 개) 할당

**중국 ETF 편입 로직**:
1. `etf_recommender.CHINA_ETF_POOL` 에서 10 개 ETF 추출
2. 각 ETF 의 1 일·5 일·20 일 수익률 계산
3. 모멘텀 점수 (5 일×2 + 20 일×1) 로 상위 5 개 선별
4. `"중국 ETF"` 섹션으로 리포트 별도 표기
5. 국내 ETF 와 병렬 수집 (threading)

---

### STEP 3 — 보조 데이터 수집 (항상 실시간)

**정책**: 캐시 없음 (항상 실시간), 매 실행 시 신규 수집, 실패 시 2 회 재시도
**실패 감지**: 빈 데이터 반환 시 `⚠️` 경고 출력

| 수집 항목 | 소스 | 주요 데이터 |
|----------|------|------------|
| 거시지표 | yfinance | USD/KRW·WTI·Gold·VIX·KOSPI·KOSDAQ·S&P500·나스닥·미 10 년채·달러인덱스 |
| Fear & Greed | alternative.me | 0~100 지수, 전일 비교 |
| 섹터 ETF | yfinance | XLK·XLF·XLE·XLV·XLI·XLY·XLP·SOXX·ARKK·GLD·USO·UUP + KR ETF |
| 해외 스냅샷 | yfinance | NVDA·TSM·ASML·TSLA·META·MSFT·LMT·미 10 년채·달러인덱스 |
| 뉴스 | RSS | 연합뉴스 TV·동아경제·BusinessInsider (최대 10 건) |
| 국내 ETF | yfinance | KODEX·TIGER 12 개 → 1D·5D·20D 수익률 계산 → 모멘텀 상위 5 개 |
| **중국 ETF** | yfinance | **TIGER·KODEX 9 개 → 1D·5D·20D 수익률 계산 → 모멘텀 상위 5 개** |

---

### STEP 4 — 외부 변수 + 투자자 포트폴리오 + 테마

**외부변수**: `external_events.json` → Claude 프롬프트에 반영

**유명 투자자 포트폴리오**: 관심 종목과 매칭되는 스크리닝 결과에 +5 가산 후 재정렬

| 투자자 | 유형 |
|--------|------|
| 낸시 펠로시 (Pelosi) | 미국 의원 포트폴리오 |
| ARK Invest | Cathie Wood ETF 편입 종목 |
| 박세익 | 국내 투자자 |
| 존리 | 국내 투자자 |
| 이채원 | 국내 투자자 |
| 김민국 | 국내 투자자 |
| 강방천 | 국내 투자자 |

**국내 테마 추출**: 반도체·2 차전지·바이오 등 테마별 스크리닝 상위 종목 추출 → 리포트 포함

---

### STEP 5 — Claude 심층 분석

**모델**: `claude-sonnet-4-6`
**max_tokens**: 5,000
**temperature**: 0 (결정론적)
**프롬프트 상한**: 28,000 자 (초과 시 종목 수 자동 축소)
**캐시**: 당일 동일 입력 시 재사용 (해시 기반)
**입력 후보 범위**: 시장별 확대 후보 TOP (KOSPI 10 / KOSDAQ 6 / US 10 / IPO 8)

**출력 포맷 (JSON 우선)**:
```json
{"top_buy":[{"ticker":"...","name":"...","score":N},...],
 "top_sell":[...],
 "market":"시장 총평",
 "risk":"주요 리스크",
 "fg_signal":"매수|관망|매도"}
```
(JSON 이후 상세 텍스트 분석)
🌐 시장 총평 / 🟢 KR·KQ·US 매수 추천 / 🔴 KR·KQ·US 매도 추천

---

### STEP 6 — 최종 선별 (Claude JSON 순위 우선)

**매수 추천 수**: `RECOMMEND_COUNT = {KOSPI:5, KOSDAQ:3, US:5, IPO:5}`
**매도 추천 수**: `SELL_COUNT = {KOSPI:3, KOSDAQ:2, US:3}`

**선별 우선순위**:
1. Claude `top_buy` JSON 순서대로 해당 시장 풀에서 매칭
2. Claude 미추천 슬롯 → 기술+펀더멘털+투자자 가중 점수 내림차순으로 채움

---

### STEP 7~9 — 저장 및 발송

| 출력 | 경로 | 형식 |
|------|------|------|
| 이메일 본문 | `report_v4.txt` | plain text |
| HTML 보관 | `report_v4.html` | HTML |
| 성과 리포트 | `performance_report.txt` | plain text |
| 추천 이력 DB | `stock_performance.db` | SQLite |
| 이메일 발송 | geunho@stic.co.kr | SMTP (Gmail) |

**리포트 추가 섹션**:
- `🌟 유명 투자자 포트폴리오 TOP5` — 투자자별 관심 종목 + 비중
- `🏷️ 국내 테마별 스크리닝 상위 종목` — 테마별 점수·RSI·손절가
- `📦 국내 유망 ETF TOP 5` — 모멘텀 상위 ETF, 전일·5 일·20 일 수익률, 주요 구성종목 5 개
- `🇨🇳 중국 ETF 추천 TOP 5` — 모멘텀 상위 중국 ETF, 전일·5 일·20 일 수익률, 주요 구성종목
- `🆕 신규상장 (IPO) 주목 TOP` — 최근 6 개월 상장 종목, 점수·RSI·손절가

**매수 근거 구조 (종목별)**:
```
✅ 기술적 근거: [RSI·MACD·MA·ADX·52 주위치·스토캐스틱·거래량·모멘텀·MACD+ADX 복합 중 상위 3 개]
   └─ macd_adx_score: 0~10 점 (ADX>25+ 방향+MACD 골든크로스 삼중 확인)
📈 펀더멘털: [EPS 성장·ROE·순이익률·P/E·P/B·EBITDA 성장률·비지배지분 조건 충족 시 최대 3 개]
```

**리스크 구조 (종목별)**:
```
⚠️ 기술적 리스크: [RSI 과열·ADX 횡보·MA 하회·BB 상단·스토캐스틱과매수·거래량위축·52 주신고가 중 상위 3 개]
🔍 펀더멘털 리스크: [P/E 고평가·EPS 역성장·ROE 음수·순이익률적자·부채비율·P/B 고평가 조건 충족 시 최대 3 개]
```

**Claude 매수 분석 항목**:
```
📌 매수논리 : 기술적 + 펀더멘털 핵심 근거
🏢 비즈니스 : 실적개선·매출성장·마진확대·신사업·섹터 모멘텀 등 비즈니스 상황
💰 분할매수 / 🎯 목표가 / 🛑 손절가
📊 펀더멘털 : P/E·ROE·EPS 성장률·이익률 등 핵심 지표
```

**Claude 매도 분석 항목**:
```
📌 매도논리 : 기술적 + 펀더멘털 핵심 근거
🔍 리스크요인 : 밸류에이션·실적악화·재무구조·테마 소멸·업황 둔화
📉 매도전략 / 🎯 하락목표
```

---

## 캐시 정책 요약

| 캐시 | 유효기간 | 위치 |
|------|---------|------|
| 스크리닝 결과 | 당일 한정 | `cache/screening_YYYYMMDD.json` |
| 펀더멘털 | 7 일 | `cache/` 종목별 JSON |
| Claude 분석 | 당일 한정 | `cache/{hash}.json` |
| 증권사 추천 | 당일 한정 | `cache/broker_picks_YYYYMMDD.json` |
| 거시·섹터·뉴스 | **없음 (항상 실시간)** | — |
| 국내 ETF | **없음 (항상 실시간)** | — |
| 중국 ETF | **없음 (항상 실시간)** | — |

---

## 종목 선정 필터 요약 — 3 단계 투자 프레임워크

> **워런 버핏식 가치투자 + 기술적 타이밍 복합 체계.**
> 기술적 지표는 진입 시점을 결정하고, 기본적 지표는 종목의 퀄리티를 결정한다.

### Step 1 — Quality Filter (우량 종목 스크리닝)

| 구분 | 필터 | 기준 | 적용 단계 |
|------|------|------|----------|
| 수익성 | ROE | > 15% | STEP 2 펀더멘털 |
| 재무건전성 | 이자보상배율 (EBITDA/이자비용) | > 3 배 | STEP 2 펀더멘털 |
| 자회사 리스크 | 비지배지분 | > 0 | STEP 2 펀더멘털 |
| 성장성 | EBITDA 성장률 | > 10% (YoY) | STEP 2 펀더멘털 |

### Step 2 — Valuation (내재가치 저점 판별)

| 구분 | 필터 | 기준 | 적용 단계 |
|------|------|------|----------|
| DCF | 시가총액 vs 내재가치 | ≤ DCF 가치 × 70% (30%+ 저평가) | STEP 2 펀더멘털 |
| 역발상 | 업종 PER 하회 + FCF 우상향 | 시장 외면 + 현금흐름 개선 | STEP 2 펀더멘털 |

### Step 3 — Entry Timing (기술적 타이밍)

| 구분 | 필터 | 기준 | 적용 단계 |
|------|------|------|----------|
| 추세 전환 | 주봉 MACD | 하락 멈춤 + 횡보/골든크로스 기미 | STEP 1 주봉 계산 |
| 추세 강도 | ADX (일봉) | > 25 + +DI > -DI | STEP 1 스크리닝 |
| 복합 점수 | MACD+ADX 복합 | 0~10 점 (3 조건 가산) | STEP 1 score_technical() |

```
[Step 1 전체 통과] AND [Step 2 하나 이상] AND [Step 3 전체] → ✅ 분할 매수 시작
```

---

## 실행 트리거별 차이

| 트리거 | 스크리닝 | 보조데이터 (STEP3) | 국내 ETF | 중국 ETF | IPO | Claude(STEP5) |
|--------|---------|-----------------|---------|---------|-----|--------------|
| 첫 실행 (당일) | yfinance 전수 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | API 호출 |
| 재실행 (당일) | 캐시 재사용 | 실시간 수집 | 실시간 수집 | 실시간 수집 | 캐시 재사용 | 캐시 재사용 |
| 다음날 실행 | yfinance 전수 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | API 호출 |
| 캐시 삭제 후 | yfinance 전수 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | 실시간 수집 | API 호출 |

> 투자자 포트폴리오 (STEP4) · 국내 ETF · 중국 ETF 는 항상 실시간 수집 (캐시 없음)
