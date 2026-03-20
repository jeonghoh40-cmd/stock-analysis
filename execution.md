# 🚀 실행 가이드 (execution.md)

> AI 주식 스크리닝 어드바이저 v4 — 설치부터 자동 실행까지

---

<!--
## Claude Code 자동 업데이트 규칙

이 파일은 Claude Code가 작업 중 스스로 업데이트한다. 아래 규칙을 따른다.

### 업데이트 시점
- 작업을 완료했을 때 → [섹션 A] 완료된 작업에 추가
- 아직 남은 작업이 생겼을 때 → [섹션 B] 남은 작업에 추가 또는 체크
- 에러를 만나고 해결했을 때 → [섹션 C] 에러 로그에 추가

### 포맷 규칙
- 날짜는 항상 YYYY-MM-DD 형식 (bash: `date +%Y-%m-%d`)
- 완료 항목: `- [x] YYYY-MM-DD | 작업내용 | 수정파일`
- 남은 항목: `- [ ] 작업내용 | 관련 Phase`
- 에러 항목: 아래 템플릿 사용

### 에러 로그 템플릿
```
### ❌→✅ 에러명 (YYYY-MM-DD)
- **발생 위치**: 파일명:함수명
- **에러 메시지**: `오류 내용`
- **원인**: 한 줄 설명
- **해결**: 적용한 해결책
- **재발 방지**: 앞으로 주의할 점
```
-->

---

## [섹션 A] 완료된 작업

> Claude Code가 작업 완료 시 이 섹션에 추가한다.

<!-- 포맷: - [x] YYYY-MM-DD | 작업내용 | 수정된 파일 -->

- [x] 2026-03-13 | `plan.md` 프로젝트 로드맵 초안 작성 | `plan.md`
- [x] 2026-03-13 | `plan.md`에 구현목표·수정파일·라이브러리·사이드이펙트·실행프로세스 추가 | `plan.md`
- [x] 2026-03-13 | `plan.md`에 키움증권·KIS API 활용 계획 추가 | `plan.md`
- [x] 2026-03-13 | `plan.md` Phase 5-1 유니버스 확장 1순위로 승격 및 상세화 | `plan.md`
- [x] 2026-03-13 | `.env.example` 실제 API 키 → 플레이스홀더로 교체 | `.env.example`
- [x] 2026-03-13 | `execution.md` 실행 가이드 초안 작성 | `execution.md`
- [x] 2026-03-13 | `execution.md` 자동 업데이트 구조로 개편 | `execution.md`
- [x] 2026-03-13 | 사전 준비 확인 (Python 3.13.11, 패키지 8종, .env 7개 키) | —
- [x] 2026-03-13 | `stock_advisor_v4.main()` 실행 완료 (62개 종목, 2분 19초, 이메일 발송) | —
- [x] 2026-03-13 | `plan.md` 목표·Data Source·종목선정 알고리즘·매매전략·Risk Management 보강 | `plan.md`
- [x] 2026-03-13 | `plan.md` Phase 2.5(Data Sanity Check)·2.6(백테스팅) 신규 추가 | `plan.md`
- [x] 2026-03-13 | `plan.md` 중국 ADR → KRX 상장 중국ETF 6종으로 교체 | `plan.md`
- [x] 2026-03-13 | `plan.md` 운용 모드 추천 ONLY 명시 및 ETF 전용 필터 엔진 설계 | `plan.md`
- [x] 2026-03-13 | `plan.md` 증권사 추천(키움·KIS) Pool 편입 설계 | `plan.md`
- [x] 2026-03-13 | `plan.md` 백테스트 Point-in-Time + Delisted 포함 원칙 추가 | `plan.md`
- [x] 2026-03-13 | `universe.py` 전면 재작성 — 중국ADR 제거, 중국ETF·KOSPI200·KOSDAQ150·SP500Top20·IPO·SELL_POOL 추가 | `universe.py`
- [x] 2026-03-13 | `universe_ipo_watchlist.json` 신규 생성 (IPO 종목 관리 파일) | `universe_ipo_watchlist.json`
- [x] 2026-03-13 | `stock_advisor_v4.py` KOSPI_POOL·KOSDAQ_POOL 하드코딩 제거 → `get_kr_pools()` 통합 | `stock_advisor_v4.py`
- [x] 2026-03-13 | `.mcp.json` 생성 — GitHub MCP 서버 연동 (GITHUB_TOKEN 환경변수 참조) | `.mcp.json`
- [x] 2026-03-13 | `.gitignore` 예외 추가 (`universe_ipo_watchlist.json`, `.mcp.json`) | `.gitignore`
- [x] 2026-03-13 | `execution.md` 섹션 B 중복 항목 제거 (`### 즉시 (버그 수정)` 섹션 중복 삭제) | `execution.md`
- [x] 2026-03-13 | 가격 추적 Series 오류 수정 — `h["Close"].squeeze().iloc[-1]` + 명시적 `float()` 변환 | `stock_advisor_v4.py`
- [x] 2026-03-13 | 카카오톡 한글 인코딩 오류 — 텔레그램(`send_telegram`)으로 교체 완료 (N/A) | `stock_advisor_v4.py`
- [x] 2026-03-13 | pykrx → FinanceDataReader 교체 — KOSPI200(시총 상위 200개)·KOSDAQ150(시총 상위 150개) 동적 조회 정상화 | `universe.py`
- [x] 2026-03-13 | `data_cleaner.py` 신규 — 거래량0 제거·결측 보간·이상치탐지·제외로그 | `data_cleaner.py`
- [x] 2026-03-13 | `stock_advisor_v4.py` `screen_one()` 직후 `data_cleaner.clean()` 삽입 | `stock_advisor_v4.py`
- [x] 2026-03-13 | `broker_news_collector.py` 신규 — KIS API 시도 + 캐시 관리 | `broker_news_collector.py`
- [x] 2026-03-13 | `run_screening()` broker_picks 유니버스 병합 로직 추가 | `stock_advisor_v4.py`
- [x] 2026-03-13 | `etf_filter.py` 신규 — AUM·거래대금·상장기간 필터 | `etf_filter.py`
- [x] 2026-03-13 | `backtest.py` 신규 — PIT·LAB차단·수수료슬리피지·OOS분리·HARD-GATE·DB저장 | `backtest.py`
- [x] 2026-03-13 | Phase 3-1: yfinance `timeout=10` 추가 — `yf.download` + `history()` 4곳 hang 방지 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 3-2: 캐시 자동 만료 — `_clean_old_screening_caches(3일)` + `clear_old_cache(7일)` main() 시작 시 실행 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 3-3: 토큰 예산 제한 — `_MAX_PROMPT_CHARS=28000` 초과 시 종목 수 자동 축소 로직 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 3-2: 펀더멘털 주간 캐시 — `_FUND_CACHE` + `fundamentals.json` 7일 유효, `enrich_with_fundamentals()` 캐시 통계 출력 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 3-3: Claude 응답 JSON 구조화 — `_extract_claude_json()` + `_save_claude_structured()`, `claude_structured_YYYYMMDD.json` 저장 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 4-3: HTML 이메일 템플릿 — `build_html_report()` + `_html_stock_table()` + CSS, `send_email()` HTML+Text 대체 발송 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 4-2: 성과 추적 자동화 — `generate_performance_report(30)` → `performance_report.txt` + HTML 이메일 포함 | `stock_advisor_v4.py`
- [x] 2026-03-13 | Phase 5-1: IPO 자동 편입 — `fetch_kr_new_listings()` + `update_ipo_watchlist()` + CLI `python universe_utils.py ipo` | `universe_utils.py`
- [x] 2026-03-13 | Phase 5-1: S&P500 후보 풀 확장 — 30개 → 58개 (섹터별 분류: AI·금융·헬스·소비재·에너지·통신·산업재) | `universe.py`
- [x] 2026-03-13 | Phase 5-1: 테마별 실행 옵션 — `--theme [all|ai|defense|bio|energy|finance|kr|us]` CLI 인수, `_THEMES` + `run_screening` 오버라이드 | `stock_advisor_v4.py`
- [x] 2026-03-19 | `score_technical()`에 MACD+ADX 복합 추세 점수 블록 추가 (0~+10) — ADX>25·+DI>-DI·MACD골든크로스 삼중 확인 | `stock_advisor_v4.py`
- [x] 2026-03-19 | `screen_one()` 결과 dict에 `macd_adx_score` 필드 추가 (0~10, 리포트 투명도 향상) | `stock_advisor_v4.py`
- [x] 2026-03-19 | `plan.md` 종목 선정 필터 원칙 섹션 신규 추가 — 기술적(MACD골든크로스+ADX>25) / 기본적(EBITDA성장률>10%+비지배지분>0) 필터 철학 명시 | `plan.md`
- [x] 2026-03-19 | `plan.md` 통합 스코어 구성 테이블에 MACD+ADX 복합 점수 및 EBITDA·비지배지분 항목 반영 | `plan.md`
- [x] 2026-03-19 | `plan.md` 3단계 투자 프레임워크 섹션 신규 추가 — Step1(Quality: ROE>15%·이자보상배율>3·비지배지분>0) / Step2(Valuation: DCF 30%저평가·역발상 지표) / Step3(Timing: 주봉MACD전환+ADX>25) | `plan.md`
- [x] 2026-03-19 | `workflow.md` 3단계 프레임워크를 STEP별 상세에 반영 (STEP 2 Valuation, STEP 3 Timing) | `workflow.md`

---

## [섹션 B] 남은 작업

> Claude Code가 작업 시작·발견 시 추가하고, 완료 시 `[섹션 A]`로 이동한다.

<!-- 포맷: - [ ] 작업내용 | 관련 Phase | 우선순위 -->

### 즉시 — 버그 수정

### Phase 2.5 — 데이터 정제 + 증권사 추천 수집 ✅

### Phase 2.6 — 백테스팅 엔진 ✅
- [ ] 누적 수익률 차트 이미지 출력 (matplotlib) | Phase 2.6 | 🟢

### Phase 3 — 성능 최적화 ✅
- [x] yfinance 타임아웃 설정으로 hang 방지 | Phase 3-1 | 🔴
- [x] 캐시 자동 만료 정책 (7일 이상 된 파일 삭제) | Phase 3-2 | 🔴
- [x] 펀더멘털 데이터 별도 캐시 (주 1회 갱신) | Phase 3-2 | 🟡
- [x] Claude 응답 JSON 구조화 (파싱 안정화) | Phase 3-3 | 🟡
- [x] 입력 토큰 예산 제한 로직 (최대 8,000 토큰) | Phase 3-3 | 🟡

### Phase 4 — 대시보드 & 리포트
- [x] HTML 이메일 템플릿 | Phase 4-3 | 🟡
- [x] 성과 추적 자동화 (추천 후 N일 수익률) | Phase 4-2 | 🟡
- [ ] Streamlit 대시보드 (`dashboard.py` 완성) | Phase 4-1 | 🟢
- [ ] 종목 차트 이미지 첨부 (matplotlib) | Phase 4-3 | 🟢

### Phase 5-1 — 유니버스 확장 ✅
- [x] `universe_ipo_watchlist.json` 신규 IPO 종목 주기적 업데이트 | Phase 5-1 | 🟡
- [x] `get_sp500_top20()` 후보 풀 주기적 검토·확장 | Phase 5-1 | 🟡
- [x] 테마별 선택 실행 옵션 (`--theme ai` 등) | Phase 5-1 | 🟡

### Phase 5-3 — 자동매매 연동 (백테스트 통과 후)
- [ ] `broker_kis.py` 작성 (KIS REST API 래퍼) | Phase 5-3 | 🟡
- [ ] `broker_kiwoom.py` 작성 (OpenAPI+ COM 래퍼) | Phase 5-3 | 🟡
- [ ] Kelly Criterion 포지션 계산 | Phase 5-3 | 🟢
- [ ] 가상계좌 30일 시뮬레이션 (승률 55%+, MDD 10% 이하) | Phase 5-3 | 🟢

---

## [섹션 C] 에러 로그

> Claude Code가 에러 발생·해결 시 이 섹션에 추가한다.

<!-- 새 에러는 맨 위에 추가 (최신순) -->

### ✅ 가격 추적 Series 오류 (2026-03-13) — 해결
- **발생 위치**: `stock_advisor_v4.py` macro 수집 함수 (557~558번 줄)
- **에러 메시지**: `float() argument must be a string or a real number, not 'Series'`
- **원인**: yfinance 1.2.0에서 `ticker.history()`가 단일 값 대신 `Series`를 반환하는 API 변경
- **영향**: 거시 지표 수집 실패 가능 (분석·이메일 발송 자체는 정상)
- **해결**: `h["Close"].squeeze().iloc[-1]` + 명시적 `float()` 변환으로 수정 완료
- **재발 방지**: yfinance 업그레이드 시 가격 추출 코드 호환성 사전 확인

---

### ✅ 카카오톡 한글 인코딩 오류 (2026-03-13) — 해결 (N/A)
- **발생 위치**: `stock_advisor_v4.py` 카카오톡 발송 함수
- **에러 메시지**: `'latin-1' codec can't encode characters in position 7-9: ordinal not in range(256)`
- **원인**: HTTP 요청 헤더가 `latin-1`로 인코딩되어 한글 처리 불가
- **영향**: 카카오톡 알림 미발송
- **해결**: 카카오 발송 함수 자체를 **텔레그램(`send_telegram`)으로 교체** — `json=` 파라미터 사용으로 UTF-8 인코딩 자동 처리
- **재발 방지**: 알림 채널 변경 시 UTF-8 인코딩 지원 여부 사전 확인

---

### ⚠️ Pelosi API 403 / ARK 라이브 0개 (2026-03-13) — 정보
- **발생 위치**: `investor_scorer.py:refresh_live_data()`
- **에러 메시지**: `403 Client Error: Forbidden` / `ARK 라이브 0개`
- **원인**: 외부 데이터 소스 접근 제한 (S3 버킷 정책 변경 추정)
- **영향**: 정적 캐시 데이터로 대체 실행 — 분석 결과 영향 미미
- **해결**: 정적 데이터 fallback으로 자동 처리됨 (현재 허용 범위)
- **재발 방지**: 대체 소스(SEC EDGAR, ARK 공식 CSV) 연동 검토 필요

---

---

## 1. 사전 준비

### Python 경로 확인

이 프로젝트는 pgAdmin 번들 Python을 사용한다.

```batch
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" --version
```

> 다른 Python을 사용할 경우 `run_daily.bat`의 `PYTHON` 변수를 해당 경로로 수정

### 패키지 설치

```batch
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m pip install -r requirements.txt
```

**KOSPI200·KOSDAQ150 동적 조회 활성화 (즉시 권장):**

```batch
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m pip install pykrx
```

> pykrx 미설치 시 정적 anchor 종목(약 60개)으로 fallback 동작. 설치 후 자동으로 KOSPI200+KOSDAQ150(350개) 전환.

신규 기능(Phase 4 이후) 사용 시 추가 설치:

```batch
pip install streamlit matplotlib plotly finance-datareader pywin32
```

### .env 설정

```batch
copy .env.example .env
```

`.env` 파일을 메모장으로 열어 아래 항목을 채운다:

| 항목 | 필수 | 값 |
|------|------|----|
| `ANTHROPIC_API_KEY` | ✅ | console.anthropic.com에서 발급 |
| `EMAIL_USER` / `EMAIL_PASS` | ✅ | Microsoft 365 또는 Gmail 앱 비밀번호 |
| `KAKAO_TOKEN` | 선택 | 카카오 개발자 콘솔 |
| `DART_API_KEY` | 선택 | opendart.fss.or.kr (무료) |
| `KIWOOM_APP_KEY` / `KIWOOM_SECRET_KEY` | 선택 | 키움증권 OpenAPI+ |
| `KIS_APP_KEY` / `KIS_SECRET_KEY` | 선택 | 한국투자증권 apiportal |
| `GITHUB_TOKEN` | 선택 | github.com/settings/tokens (MCP 서버용) |

> ⚠️ `.env`는 절대 git에 커밋하지 않는다. `.env.example`에는 플레이스홀더만 입력한다.
> ⚠️ `.mcp.json`은 `${GITHUB_TOKEN}` 환경변수 참조 방식 사용 — 토큰 직접 입력 금지.

---

## 2. 실행 방법

### 2-1. 전체 분석 실행 (수동)

> **현재 운용 모드: 추천 ONLY** — 실제 주문 없음. 리포트만 생성·발송.

```batch
run_all_v4.bat
```

실행 순서:
1. `universe.py:get_kr_pools()` — KOSPI200·KOSDAQ150 동적 로드 (pykrx, 24h 캐시)
2. `investor_scorer.py` — Pelosi·ARK·국내 투자자 캐시 갱신
3. `investor_scorer.refresh_live_data()` — ARK/Pelosi 라이브 갱신
4. `data_cleaner.clean()` *(Phase 2.5 구현 후 활성화)* — 결측치·이상치·상폐 탐지
5. `stock_advisor_v4.main()` — 기술 + 펀더멘털 + 수급 + 증권사추천 종합 분석
6. 리포트 생성 + 이메일·카카오톡 발송

완료 후 생성되는 파일:
- `report_v4.txt` — 분석 결과 전문 (추천 ONLY)
- `cache/screening_YYYYMMDD.json` — 당일 스크리닝 캐시
- `cache/broker_picks_YYYYMMDD.json` — 증권사 추천 Pool *(Phase 2.5 이후)*
- `logs/excluded_YYYYMMDD.log` — 데이터 정제 제외 종목 *(Phase 2.5 이후)*

### 2-2. 개별 스크립트 실행

```batch
REM Python 경로 변수 (매번 입력 대신 이렇게 설정)
set PY="C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe"

REM 투자자 스코어 갱신
%PY% investor_scorer.py

REM ARK PDF 분석
%PY% analyze_ark_pdf.py

REM 지정학 데이터 수집
%PY% geopolitical_collector.py

REM ETF 분석
%PY% etf_analysis.py

REM 이메일 발송 테스트
%PY% test_email.py
```

### 2-3. 브로커 API 연결 테스트

```batch
REM 한국투자증권 — 토큰 발급 테스트 (vts 가상거래 환경)
%PY% -c "
import os; from dotenv import dotenv_values
cfg = dotenv_values('.env')
print('KIS_ENV:', cfg.get('KIS_ENV'))
print('APP_KEY 앞 8자:', cfg.get('KIS_APP_KEY','')[:8])
"

REM 키움증권 — 환경변수 로드 확인
%PY% -c "
from dotenv import dotenv_values
cfg = dotenv_values('.env')
print('KIWOOM_ENV:', cfg.get('KIWOOM_ENV'))
print('APP_KEY 앞 8자:', cfg.get('KIWOOM_APP_KEY','')[:8])
"
```

> 실제 주문 전 반드시 `KIS_ENV=vts` (가상) / `KIWOOM_ENV=dev` (모의) 확인

---

## 3. 자동 실행 스케줄러 등록

### 등록 (최초 1회)

PowerShell을 **관리자 권한**으로 열고 실행:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "C:\Users\geunho\stock analysis\setup_scheduler_v4.ps1"
```

등록 후 설정 내용:
- 실행 시간: **월~금 오전 06:30**
- 실행 파일: `run_daily.bat`
- 작업 이름: `AI_Stock_Screener`
- 로그 위치: `logs\daily_YYYYMMDD.log`

### 등록 확인

```powershell
Get-ScheduledTask -TaskName "AI_Stock_Screener" | Select-Object TaskName, State
```

### 수동 즉시 실행 (스케줄러 통해)

```powershell
Start-ScheduledTask -TaskName "AI_Stock_Screener"
```

### 스케줄러 삭제

```powershell
Unregister-ScheduledTask -TaskName "AI_Stock_Screener" -Confirm:$false
```

---

## 4. 로그 모니터링

### 오늘 로그 실시간 확인

```powershell
$today = Get-Date -Format "yyyyMMdd"
Get-Content "C:\Users\geunho\stock analysis\logs\daily_$today.log" -Wait
```

### 마지막 10줄 확인

```powershell
$today = Get-Date -Format "yyyyMMdd"
Get-Content "C:\Users\geunho\stock analysis\logs\daily_$today.log" -Tail 10
```

### 오류 줄만 필터

```powershell
$today = Get-Date -Format "yyyyMMdd"
Select-String "ERROR|WARNING" "C:\Users\geunho\stock analysis\logs\daily_$today.log"
```

---

## 5. 실행 결과 확인

| 확인 항목 | 위치 | 정상 상태 |
|----------|------|----------|
| 분석 리포트 | `report_v4.txt` | 매수 TOP10 포함, 추천 ONLY 모드 |
| 당일 캐시 | `cache/screening_YYYYMMDD.json` | 오늘 날짜 파일 존재 |
| 이메일 | geunho@stic.co.kr 수신함 | 오전 7시 전 도착 |
| 로그 | `logs/daily_YYYYMMDD.log` | 마지막 줄에 "전체 완료" |
| KOSPI/KOSDAQ 유니버스 | 로그 내 `[KOSPI200]` `[KOSDAQ150]` | pykrx 설치 후 200·150개 |
| 제외 종목 로그 | `logs/excluded_YYYYMMDD.log` | Phase 2.5 이후 생성 |
| 증권사 추천 캐시 | `cache/broker_picks_YYYYMMDD.json` | Phase 2.5 이후 생성 |

---

## 6. 트러블슈팅

### Python 실행 오류

```batch
REM import 오류 → 패키지 재설치
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m pip install --upgrade -r requirements.txt
```

### yfinance hang (응답 없음)

```batch
REM 캐시 초기화 후 재실행
del /q "C:\Users\geunho\stock analysis\cache\screening_*.json"
run_all_v4.bat
```

### 이메일 발송 실패

```batch
REM 이메일 설정만 단독 테스트
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" test_email.py
```

Gmail 앱 비밀번호 재발급: myaccount.google.com → 보안 → 앱 비밀번호

### 스케줄러가 실행되지 않을 때

```powershell
# 작업 상태 확인
Get-ScheduledTaskInfo -TaskName "AI_Stock_Screener" | Select LastRunTime, LastTaskResult, NextRunTime

# LastTaskResult: 0 = 성공, 그 외 = 오류 코드
# 재등록
& "C:\Users\geunho\stock analysis\setup_scheduler_v4.ps1"
```

### Claude API 오류 (토큰 초과 · 429)

`stock_advisor_v4.py` 실행 중 Claude API 오류 발생 시:
- 토큰 초과 → 프롬프트 압축 로직 확인 (Phase 3-3 완료 후 개선 예정)
- 429 Rate Limit → 약 60초 대기 후 재실행

### 한국투자증권 KIS 토큰 만료

```batch
REM 액세스 토큰은 24시간 유효 — 수동 재발급 (broker_kis.py 완성 전 임시)
%PY% -c "
import requests, json
from dotenv import dotenv_values
cfg = dotenv_values('.env')
url = 'https://openapivts.koreainvestment.com:29443/oauth2/tokenP'  # vts
body = {'grant_type':'client_credentials','appkey':cfg['KIS_APP_KEY'],'appsecret':cfg['KIS_SECRET_KEY']}
r = requests.post(url, json=body)
print(r.json().get('access_token','')[:40], '...')
"
```

---

## 7. 실행 환경 전체 구조

```
매일 06:30 Windows 작업 스케줄러
        ↓
run_daily.bat
  ├─ [Step 1]  investor_scorer.py       (~2분)  투자자 캐시 갱신
  ├─ [Step 1b] refresh_live_data()      (~1분)  ARK/Pelosi 라이브 갱신
  ├─ [Step 2]  yfinance 수집 + data_cleaner.clean()  (~5분)  데이터 수집 및 정제
  │              └─ logs\excluded_YYYYMMDD.log  ← 제외 종목 기록
  └─ [Step 3]  stock_advisor_v4.main()  (~10분) 전체 분석 + 리포트 + 발송
        ↓
logs\daily_YYYYMMDD.log        ← 실행 로그
report_v4.txt                  ← 분석 결과
cache\screening_YYYYMMDD.json  ← 당일 캐시
        ↓
[Dry Run 모드] logs\dryrun_YYYYMMDD.log  ← 신호 검증 (실전 전환 전)
        ↓
이메일(geunho@stic.co.kr) + 카카오톡 발송
        ↓
오전 07:00 전 완료 ✅
```

---

## 8. Dry Run — 1주일 가상 매매 테스트

> 실제 주문 없이 매매 신호만 발생시켜 로직이 의도대로 작동하는지 검증한다.
> **이 단계를 통과하지 않으면 자동매매(Phase 5-3) 실전 전환 불가.**

### Dry Run 실행 방법

```batch
REM --dry-run 플래그로 주문 없이 신호만 출력 (Phase 5-3 구현 후 활성화)
%PY% stock_advisor_v4.py --dry-run

REM 결과는 logs\dryrun_YYYYMMDD.log 에 저장됨
```

### 7일간 검증 체크리스트

> 매일 실행 후 아래 항목을 직접 확인하고 체크한다.

| 일차 | 날짜 | 신호 발생 | 로직 정상 | 이상 신호 | 확인자 |
|------|------|----------|----------|----------|--------|
| Day 1 | | [ ] | [ ] | — | |
| Day 2 | | [ ] | [ ] | — | |
| Day 3 | | [ ] | [ ] | — | |
| Day 4 | | [ ] | [ ] | — | |
| Day 5 | | [ ] | [ ] | — | |
| Day 6 | | [ ] | [ ] | — | |
| Day 7 | | [ ] | [ ] | — | |

### 신호 검증 기준

| 검증 항목 | 확인 방법 | 합격 기준 |
|----------|----------|----------|
| 매수 신호 종목이 통합 스코어 60점 이상인가 | `dryrun_*.log` 스코어 확인 | 100% 충족 |
| 손절가·목표가가 ATR 기반으로 계산됐는가 | 리포트 내 값 확인 | 100% 충족 |
| Citrini 리스크 종목이 추천에 포함됐는가 | 리스트 대조 | 0건 |
| 동일 종목이 중복 추천됐는가 | 종목 코드 중복 확인 | 0건 |
| 유니버스 외 종목이 포함됐는가 | `universe.py` 대조 | 0건 |
| 데이터 수집 실패 종목이 분석에 포함됐는가 | `excluded_*.log` 대조 | 0건 |

### Dry Run 종료 조건 (모두 충족 시 실전 진행 가능)

- [ ] 7일 연속 오류 없이 실행 완료
- [ ] 이상 신호 (Citrini 포함, 중복 추천 등) 0건
- [ ] 매일 TOP 10 신호가 의도한 스코어 순서대로 정렬됨
- [ ] `dryrun_*.log` 7개 파일 존재 확인

---

## 9. 브로커 API 실전 전환 체크리스트

> 현재 모드: **추천 ONLY** (`KIS_ENV=vts`, `KIWOOM_ENV=dev`)
> 아래 단계를 순서대로 완료해야 실전 전환 가능. 순서 건너뜀 금지.

### Step 1 — 백테스트 통과 (Phase 2.6)
- [ ] `backtest.py` 완성 및 과거 2년 이상 데이터 검증
- [ ] 승률 ≥ 55% 확인 (`stock_performance.db` 집계)
- [ ] MDD ≤ 10% 확인
- [ ] 샤프 지수 ≥ 1.0 확인
- [ ] Look-ahead Bias 단위 테스트 통과

### Step 2 — Dry Run 통과 (7일)
- [ ] `--dry-run` 모드 7일 연속 이상 신호 0건
- [ ] `dryrun_*.log` 7개 파일 존재 확인

### Step 3 — 브로커 연동
- [ ] `broker_kis.py` 작성 완료 (plan.md Phase 5-3 참고)
- [ ] `broker_kiwoom.py` 작성 완료
- [ ] 가상계좌 30일 시뮬레이션 완료 (승률 55%+, MDD 10% 이하)

### Step 4 — 실전 전환
- [ ] `.env`에서 `KIS_ENV=prod` / `KIWOOM_ENV=prod` 변경
- [ ] 최초 실전 주문: 1주 단위 소액 테스트 (계좌의 1%)
- [ ] 주문 로그 `stock_performance.db` 저장 확인
- [ ] 2주 검증 후 포지션 한도 단계적 확대 (1% → 3% → 5%)
 

---

## 10. 시스템 건강도 모니터링 (Phase 6)

### 건강도 점수 확인

```batch
REM 건강도 점수 출력 (Phase 6 구현 후)
%PY% -c "from health_monitor import HealthMonitor; print(HealthMonitor().get_score())"
```

### 건강도 등급별 대응

| 등급 | 점수 | 대응 |
|------|------|------|
| 🟢 우수 | 80~100 | 정상 운영 |
| 🟡 주의 | 60~79 | 로그 확인, 일부 기능 점검 |
| 🔴 위험 | 40~59 | 즉시 점검, API 키 확인 |
| ⚫ 심각 | 0~39 | 비상 연락, 시스템 복구 |

---

## 11. 고급 트러블슈팅

### Claude API 토큰 초과

```
증상: `400 Bad Request` 또는 `context_length_exceeded`
해결:
  1. `stock_advisor_v4.py` 에서 `_MAX_PROMPT_CHARS` 확인 (기본 28,000)
  2. `--theme` 옵션으로 종목 수 축소 (예: `--theme ai`)
  3. Claude 캐시 삭제 후 재실행: `del /q "cache\*.json"`
```

### yfinance 503 에러 (Rate Limit)

```
증상: `HTTPError: 503 Service Unavailable`
해결:
  1. Semaphore 값 확인 (기본 8)
  2. `time.sleep(1)` inserted between requests
  3. 캐시 활용: 동일 날짜 재실행 시 캐시 히트
  4. 60 초 대기 후 재시도
```

### DB 잠금 오류

```
증상: `sqlite3.OperationalError: database is locked`
해결:
  1. 다른 프로세스에서 DB 사용 중인지 확인
  2. `stock_performance.db-shm`, `-wal` 파일 삭제
  3. SQLite WAL 모드 확인: `PRAGMA journal_mode;`
```

### 스트리mlit 대시보드 실행 오류

```
증상: `Port 8501 already in use`
해결:
  1. 사용 중인 포트 확인: `netstat -ano | findstr :8501`
  2. 프로세스 종료: `taskkill /PID <PID> /F`
  3. 또는 다른 포트 사용: `streamlit run dashboard.py --server.port 8502`
```

### 텔레그램 알림 미수신

```
증상: 텔레그램 알림이 오지 않음
해결:
  1. `TELEGRAM_BOT_TOKEN` 유효성 확인
  2. `TELEGRAM_CHAT_ID` 확인 (BotFather 에서 확인)
  3. 테스트 발송: `%PY% test_telegram.py`
  4. 봇 차단 여부 확인: 봇과 대화 시작
```

---

## 12. 성능 최적화 팁

### 수집 시간 단축

```batch
REM 테마별 선택 실행 (전체 대신)
%PY% stock_advisor_v4.py --theme ai      # AI·반도체만
%PY% stock_advisor_v4.py --theme defense # 방산·우주만

REM 병렬 처리 수 조정 (기본 8)
set YF_SEMAPHORE=12
%PY% stock_advisor_v4.py
```

### 메모리 사용량 감소

```batch
REM 캐시 삭제 후 실행
del /q "cache\*.json"
%PY% stock_advisor_v4.py

REM 프로파일링 모드 (오버헤드 있음)
%PY% stock_advisor_v4.py --profile
```

---

## 13. 백업·복구 가이드

### 일일 백업 스크립트

```batch
@echo off
set BACKUP_DIR=C:\Users\geunho\stock analysis\backups
set DATE=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%
mkdir "%BACKUP_DIR%\%DATE%" 2>nul
xcopy /Y /I cache "%BACKUP_DIR%\%DATE%\cache"
xcopy /Y /I logs "%BACKUP_DIR%\%DATE%\logs"
copy /Y stock_performance.db "%BACKUP_DIR%\%DATE%\"
echo Backup completed: %DATE%
```

### DB 복구

```batch
REM 백업 DB 로 복원
copy /Y "backups\20260319\stock_performance.db" .
```

### 캐시 복구

```batch
REM 특정 날짜 캐시 복원
xcopy /Y "backups\20260319\cache\*" cache\
```

---

## 14. 로그 분석 유틸리티

### 일일 로그 요약

```batch
REM 오늘 로그에서 오류만 추출
findstr "ERROR" "logs\daily_%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%.log"

REM 실행 시간 추출
findstr "elapsed" "logs\daily_*.log" | tail -1
```

### 건강도 로그 분석

```powershell
# 건강도 점수 추이 (Phase 6 구현 후)
Get-Content "logs\health_*.log" | Select-String "score" | Out-File health_trend.txt
```

### 에러 통계

```powershell
# 일별 에러 건수
Get-ChildItem "logs\*.log" | ForEach-Object {
    $errors = Select-String "ERROR" $_.FullName
    [PSCustomObject]@{
        Date = $_.LastWriteTime.Date
        Errors = $errors.Count
    }
} | Export-Csv error_stats.csv
```

---

## 15. 실전 주문 최종 체크리스트

> 실전 주문 활성화 전 **반드시** 모든 항목을 확인하세요.

### 사전 점검 (매일 장전)

- [ ] 건강도 점수 80 이상
- [ ] 어제 에러 로그에서 `ERROR` 0 건
- [ ] `.env` 에서 `KIS_ENV=vts` (가상) 또는 `prod` (실전) 확인
- [ ] 계좌 잔고 충분 확인
- [ ] 장중 시간 확인 (09:00~15:30)

### 주문 후 점검

- [ ] 주문 로그 `stock_performance.db` 저장 확인
- [ ] 체결 내역 조회 (KIS 앱 또는 HTS)
- [ ] 잔고 업데이트 확인
- [ ] 손절가·목표가 설정 확인

### 비상 연락망

| 역할 | 연락처 | 비고 |
|------|--------|------|
| 시스템 관리자 | geunho@stic.co.kr | 이메일 |
| 긴급 연락 (문자) | 010-XXXX-XXXX | SMS 알림 |
| 증권사 고객센터 | 1588-XXXX | 주문 장애 시 |

---

## 16. 용어 정리

| 용어 | 설명 |
|------|------|
| **유니버스** | 스크리닝 대상 종목 집합 |
| **스코어링** | 종목별 통합 점수 계산 (100 점 만점) |
| **ATR** | Average True Range, 변동성 기반 손절가 계산 |
| **Citrini** | 리스크 종목 필터링 리스트 |
| **Dry Run** | 실제 주문 없이 신호만 발생시키는 테스트 |
| **HARD-GATE** | 실전 전환 필수 조건 (승률 55%+, MDD 10% 이하) |
| **PIT** | Point-in-Time, 백테스트 시 미래 데이터 참조 차단 |
| **LAB** | Look-ahead Bias, 미래 데이터 오류 참조 |
| **건강도** | 시스템 정상 운영 점수 (100 점 만점) |
| **2FA** | 2 단계 인증, 실전 주문 보안 |
