# 📊 AI 주식 스크리닝 어드바이저

Claude AI 를 활용해 **매일 오전 7 시 전**,
국내·미국·중국 ~150 개 대형주를 자동 스크리닝하여
**매수 추천 TOP 10 / 매도 추천 TOP 10** 을 선별하고
이메일 + 카카오톡으로 알림을 발송합니다.

## 🌟 주요 기능 (2026 업데이트)

### ✅ 유명 투자자 포트폴리오 자동 추적

#### 🇺🇸 미국 투자자
- **Nancy Pelosi** (前하원의장) - 빅테크 중심 포트폴리오
- **Cathie Wood** (ARK Invest) - 혁신주·성장주
- **Aswath Damodaran** (NYU 교수) - 밸류에이션 데이터
- **Howard Marks** (Oaktree) - 시장 사이클 메모
- **Tom Lee** (Fundstrat) - S&P 전망

#### 🇰🇷 한국 투자자
- **박세익** (체슬리투자자문) - 반도체·2 차전지 사이클
- **존리** (메리츠자산운용) - 장기 가치투자
- **이채원** (라이프자산운용) - 저 PBR·지주사
- **김민국** (VIP 자산운용) - 행동주의·밸류업
- **강방천** (에셋플러스) - 장기 성장주·소비재

### ✅ 투자자 스코어링 시스템
- Pelosi/ARK 보유 종목 → 가중치 +5~15 점
- 한국 투자자 보유 종목 → 가중치 +5~25 점
- 다수 투자자 동시 보유 → 추가 보너스 점수

---

## 분석 흐름

```
① 전종목 병렬 스크리닝 (~150 개, 12 스레드)
        ↓
② 기술적 점수 계산 (RSI·MACD·이동평균·모멘텀·BB)
        ↓
③ 유명 투자자 포트폴리오 가중치 적용
        ↓
④ 매수 TOP10 / 매도 TOP10 자동 선별
        ↓
⑤ 거시경제 + 뉴스 + 해외섹터 데이터 수집
        ↓
⑥ Claude AI 심층 분석 → 목표가·손절가·투자전략 제시
        ↓
⑦ report.txt 저장 + 이메일 + 카카오톡 발송
```

---

## 설치 방법

```bash
# 1. 코드 받기
git clone https://github.com/jeonghoh40-cmd/stock-advisor.git
cd stock-advisor

# 2. API 키 설정
copy .env.example .env        # Windows
# cp .env.example .env        # Mac/Linux
# .env 파일 열어서 키 입력

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 실행
py stock_advisor.py           # Windows
# python3 stock_advisor.py    # Mac/Linux
```

---

## .env 주요 설정

| 키 | 필수 여부 | 용도 | 발급처 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **필수** | Claude AI 분석 | [console.anthropic.com](https://console.anthropic.com) |
| `EMAIL_USER` / `EMAIL_PASS` | **필수** | 이메일 발송 | Gmail 앱 비밀번호 |
| `EMAIL_TO` | **필수** | 수신 이메일 | — |
| `KAKAO_TOKEN` | 선택 | 카카오톡 알림 | [developers.kakao.com](https://developers.kakao.com) |
| `DART_API_KEY` | 선택 | 국내 재무/공시 | [opendart.fss.or.kr](https://opendart.fss.or.kr) (무료) |
| `FRED_API_KEY` | 선택 | 미국 금리 데이터 | [fred.stlouisfed.org](https://fred.stlouisfed.org) (무료) |
| `KIS_APP_KEY` 등 | 선택 | 실제 주문 | 한국투자증권 Open API |

---

## 매일 자동 실행 설정 (06:30 → 07:00 전 완료)

```bash
bash setup_schedule.sh
```

> Mac: 터미널 앱에 **전체 디스크 접근 권한** 필요
> (시스템 설정 → 개인정보 보호 → 전체 디스크 접근 권한 → 터미널 추가)

---

## 스크리닝 유니버스

| 시장 | 종목 수 | 주요 종목 |
|---|---|---|
| 🇰🇷 국내 KOSPI/KOSDAQ | 50 개 | 삼성전자·SK 하이닉스·NAVER·현대차 등 |
| 🇺🇸 미국 NASDAQ/NYSE | 60 개 | NVIDIA·Apple·Microsoft·Tesla 등 |
| 🇨🇳 중국 (미국 ADR) | 40 개 | 알리바바·바이두·핀둬둬 등 |

---

## 기술적 점수 기준 (–100 ~ +100 점)

| 지표 | 가중치 | 매수 신호 | 매도 신호 |
|---|---|---|---|
| RSI(14) | ±40 점 | 30 이하 과매도 | 70 이상 과매수 |
| MACD 히스토그램 | ±20 점 | 양수 (상승 모멘텀) | 음수 (하락 모멘텀) |
| 이동평균 정배열 | ±20 점 | 가격>MA20>MA60 | 가격<MA20<MA60 |
| MA5 vs MA20 | ±10 점 | 골든크로스 | 데드크로스 |
| 5 일 모멘텀 | ±10 점 | +5% 이상 | –5% 이하 |

---

## 📁 주요 파일

| 파일 | 용도 |
|------|------|
| `stock_advisor.py` | 메인 주식 분석 스크립트 |
| `investor_scorer.py` | 투자자 포트폴리오 스코어링 |
| `investor_tracker.py` | 유명 투자자 데이터 수집 |
| `dart_collector.py` | DART 재무제표 수집 |
| `data_collector.py` | 주가 데이터 수집 |
| `geopolitical_collector.py` | 지정학/거시경제 데이터 |
| `run_all.bat` | 전체 스크립트 일괄 실행 |
| `DART_가이드.md` | DART 활용 가이드 |

---

## 🚀 빠른 실행

```bash
# 전체 시스템 실행 (권장)
run_all.bat

# 개별 실행
py investor_scorer.py      # 투자자 스코어 확인
py investor_tracker.py     # 투자자 데이터 수집
py stock_advisor.py        # 주식 분석
```

---

## ⚠️ 주의사항

- 본 시스템은 **투자 참고용**입니다
- Claude AI 분석은 과거 데이터 기반이며 미래 수익을 보장하지 않습니다
- 실제 주문은 사용자가 직접 확인·실행해야 합니다
- 유명 투자자 포트폴리오는 공개 자료 기반이며 지연될 수 있습니다

---

## 📚 참고 자료

- [DART 기반 한국 투자자 포트폴리오 확인 가이드](DART_가이드.md)
- [설정 가이드](설정_가이드.txt)
- [완성 체크리스트](완성_체크리스트.txt)
