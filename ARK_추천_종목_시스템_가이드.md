# ARK Invest Big Ideas 2026 — 추천 종목 시스템 구축 완료

## 📋 개요

ARK Invest 의 2026 년 2 월 투자보고서 (Big Ideas 2026) 를 기반으로 향후 유망한 기업들을 DB 에 기록하고, 주기적인 관찰 보고서를 생성하는 시스템이 구축되었습니다.

## 🎯 주요 기능

### 1. ARK 추천 종목 관리 (`ark_recommended_stocks.py`)

**13 대 메가테마별 핵심 종목 수록:**

| 테마 | 설명 | 우선순위 |
|------|------|----------|
| 1. 대가속 | 5 개 플랫폼 (AI·로보틱스·에너지·블록체인·멀티오믹스) 수렴 | CORE |
| 2. AI 인프라 | 데이터센터·반도체·전력 | CORE |
| 3. AI Consumer OS | AI 가 검색·쇼핑·의사결정 대체 | HIGH |
| 4. AI 생산성 | 기업 소프트웨어 AI 전환 | HIGH |
| 5. 비트코인 | 디지털 금·제도권 편입 | MEDIUM |
| 6. 토큰화자산 | 실물자산의 블록체인 온체인화 | MEDIUM |
| 7. DeFi | 탈중앙화 금융 | MEDIUM |
| 8. 멀티오믹스 | AI × Biology 신약개발 | HIGH |
| 9. 재사용로켓 | 우주 접근 비용 감소 | MEDIUM |
| 10. 로보틱스 | 범용 물리 AI | HIGH |
| 11. 분산에너지 | 전력이 AI 의 병목 | CORE |
| 12. 자율주행 | 로보택시 경제학 | HIGH |
| 13. 자율물류 | 라스트마일 자동화 | MEDIUM |

**수집 데이터:**
- 현재가, 1 일/5 일/20 일 등락률
- RSI, MA5/20/60 이동평균
- 시가총액, PER, PBR
- 테마별 추천 사유

### 2. 데이터베이스 확장 (`db_manager.py`)

**새로운 테이블: `ark_recommended`**
```sql
CREATE TABLE ark_recommended (
    id           INTEGER PRIMARY KEY,
    date         TEXT NOT NULL,      -- YYYYMMDD
    run_at       TEXT NOT NULL,      -- ISO 타임스탬프
    ticker       TEXT NOT NULL,
    name         TEXT,
    market       TEXT,               -- KOSPI/KOSDAQ/US
    theme        TEXT,               -- ARK 테마명
    theme_key    TEXT,               -- 테마 키
    price        REAL,               -- 현재가
    change_1d    REAL,               -- 1 일 등락률
    change_5d    REAL,               -- 5 일 등락률
    change_20d   REAL,               -- 20 일 등락률
    rsi          REAL,
    ma5          REAL,
    ma20         REAL,
    ma60         REAL,
    market_cap   INTEGER,
    pe           REAL,
    pb           REAL,
    priority     TEXT,               -- CORE/HIGH/MEDIUM
    reason       TEXT                -- 추천 사유
);
```

**주요 함수:**
- `save_ark_recommended()` — ARK 종목 DB 저장
- `get_latest_ark_recommended()` — 최신 ARK 추천 조회
- `get_ark_by_theme()` — 테마별 종목 조회
- `get_ark_performance_summary()` — 성과 요약

### 3. 주기적 관찰 보고서 (`ark_observation_scheduler.py`)

**실행 모드:**
```bash
# 단일 실행 (즉시)
python ark_observation_scheduler.py --once

# 매일 자동 실행 (장 마감 후 오후 6 시)
python ark_observation_scheduler.py --daily

# 매주 자동 실행 (금요일 오후 6 시)
python ark_observation_scheduler.py --weekly
```

**보고서 유형:**
- **일일 보고서**: 당일 데이터 기반 관찰报告
- **주간 종합 보고서**: 금일 데이터 + 히스토리 비교 + 주간 성과 요약

**저장 위치:**
- `ark_reports/` 디렉토리에 자동 저장
- JSON + TXT 형식

### 4. 대시보드 통합 (`dashboard.py`)

**새로운 탭: "🎯 ARK 추천 종목"**

제공 기능:
- ARK 성과 요약 (분석 종목수, 평균 20 일수익률, 최고/최저수익률, 양수비율)
- 최신 ARK 추천 종목 목록 (50 개)
- 테마별 필터 조회
- ARK Big Ideas 2026 정보

**실행:**
```bash
streamlit run dashboard.py
```

## 📊 생성된 파일

| 파일명 | 설명 |
|--------|------|
| `ark_recommended_stocks.py` | ARK 추천 종목 데이터 수집 및 보고서 생성 |
| `ark_observation_scheduler.py` | 주기적 관찰 보고서 스케줄러 |
| `ark_report_YYYYMMDD_HHMM.json` | ARK 보고서 (JSON) |
| `ark_report_YYYYMMDD_HHMM.txt` | ARK 보고서 (TXT) |
| `ark_reports/` | 보고서 저장 디렉토리 |

## 🚀 사용 방법

### 1.单次 실행 (즉시 분석)

```bash
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" ark_recommended_stocks.py
```

### 2. 대시보드에서 확인

```bash
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m streamlit run dashboard.py
```

### 3. 주기적 관찰 (스케줄러)

```bash
# 매일 자동 실행
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" ark_observation_scheduler.py --daily

# 매주 금요일 자동 실행
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" ark_observation_scheduler.py --weekly
```

## 📈 관찰 보고서 항목

### 일일 보고서 포함 내용:
1. **시장별 종목 현황** (KOSPI/KOSDAQ/US)
2. **20 일 수익률 기준 정렬**
3. **테마별 모멘텀 분석**
4. **종합 의견 및 투자 판단**

### 주간 보고서 추가 항목:
1. **주간 성과 요약**
2. **상위/하위 성과 종목 TOP 10/BOTTOM 5**
3. **테마별 주간 성과**
4. **투자 권고** (시장 상황별)

## 🔍 기존 시스템과 차별점

| 항목 | 기존 스크리닝 | ARK 추천 종목 |
|------|--------------|--------------|
| **목적** | 단기 기술적 분석 | 장기 메가테마 기반 |
| **카테고리** | 매수/매도 | CORE/HIGH/MEDIUM 우선순위 |
| **저장 테이블** | `screening_results` | `ark_recommended` |
| **보고서** | 일일 추천 | 일일/주간 관찰 |
| **대시보드** | 1~3 탭 | 4 번째 탭 |

## ⚠️ 투자 참고사항

- ARK 추천 종목은 **장기 성장 테마** 기반이나 **변동성이 매우 큽니다**
- **분할 매수·손절 관리 필수**
- 이 데이터는 **투자 참고용**이며, 최종 투자 결정은 본인의 책임입니다
- 출처: [ark-invest.com/big-ideas-2026](https://ark-invest.com/big-ideas-2026)

## 📚 데이터 출처

1. **ARK Invest Big Ideas 2026** (2026-01-21 발표)
   - 13 대 Big Ideas 테마
   - 5 개 플랫폼 수렴 시나리오
   
2. **주가 데이터**: Yahoo Finance

3. **Citrini Research "2028 Global Intelligence Crisis"** (참고)
   - AI 위기 시나리오 모니터링
   - 수혜주/피해주 분석

## ✅ 체크리스트

- [x] ARK 13 대 테마별 핵심 종목 정리
- [x] DB 테이블 확장 (`ark_recommended`)
- [x] 데이터 수집 및 저장 모듈 구현
- [x] 주기적 관찰 보고서 생성
- [x] 대시보드 통합 (4 번째 탭)
- [x] 시스템 테스트 완료

## 📞 문의

시스템 관련 문의는 README.md 의 연락처를 참조하세요.

---

**최종 업데이트:** 2026-03-05  
**버전:** 1.0
