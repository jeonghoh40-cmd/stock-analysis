# 주식 어드바이저 시스템

Claude API를 활용한 거시경제 + 뉴스 + 수급 종합 분석 도구

## 시스템 구조

```
collect_macro_data()       거시지표 수집 (금리/환율/VIX/KOSPI 등)
        ↓
analyze_news_sentiment()   뉴스 헤드라인 수집 → Claude 감성 분석
        ↓
check_market_liquidity()   종목별 기술적 지표 (MA, RSI, 거래량)
        ↓
ask_claude_for_advice()    전체 데이터 → Claude 매수/매도 판단
        ↓
execute_trade()            사용자 최종 확인 → KIS API 주문 실행
```

## 설치

```bash
cd "stock analysis"
pip install -r requirements.txt
```

## 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 필수 API 키

| 키 | 용도 | 발급처 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 분석 엔진 | [console.anthropic.com](https://console.anthropic.com) |

### 선택 API 키 (없어도 동작)

| 키 | 용도 | 발급처 |
|---|---|---|
| `FRED_API_KEY` | 미국 금리 데이터 | [fred.stlouisfed.org](https://fred.stlouisfed.org) - 무료 |
| `NEWS_API_KEY` | 뉴스 수집 | [newsapi.org](https://newsapi.org) - 무료 플랜 |
| `KIS_APP_KEY` 등 | 실제 주문 | 한국투자증권 계좌 필요 |

## 실행

```bash
python stock_advisor.py
```

## 분석 대상 종목 변경

`.env` 파일에서:
```
TARGET_STOCKS=005930,000660,035420
```

또는 코드에서 직접 지정:
```python
advisor = StockAdvisorSystem(target_stocks=["005930.KS", "373220.KS"])
# LG에너지솔루션 추가 예시
```

## ⚠️ 주의사항

- 이 시스템은 **투자 참고용**입니다
- Claude의 분석은 과거 데이터 기반이며 미래를 보장하지 않습니다
- 실제 주문은 `execute_trade()` 호출 시 **터미널에서 "yes" 입력**해야만 실행됩니다
- KIS API 실주문은 [한국투자증권 Open API](https://apiportal.koreainvestment.com) 신청 후 사용 가능합니다
