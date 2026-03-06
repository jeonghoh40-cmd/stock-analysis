# Citrini 2028 글로벌 지능위기 — 부정적 종목 추적 시스템

## 📋 개요

Citrini Research 의 "2028 Global Intelligence Crisis" 보고서를 기반으로 AI 에 의한 대량실업 위기에 노출된 기업들을 추적하고 경고하는 시스템이 구축되었습니다.

## ⚠️ Citrini 2028 위기 시나리오

### 보고서 개요
- **발표일**: 2026-02-22
- **저자**: James van Geelen & Alap Shah (Citrini Research)
- **시나리오**: AI 가 화이트칼라 대량 실업 유발 → 소비 붕괴 → 디플레이션 악순환

### 주요 예측
| 지표 | 예측치 |
|------|--------|
| S&P 500 정점 | 8000 (AI 낙관 랠리) |
| S&P 500 붕괴 | 3500 (2028 년 6 월) |
| 실업률 최고 | 10.2% |
| 붕괴 시기 | 2028 년 6 월 |

---

## 🎯 부정적 종목 분류

### 위험등급별 분류

#### 🔴 HIGH 위험 (9 개 종목)
인도 IT 아웃소싱 및 소비 취약 업종

| 티커 | 종목명 | 섹터 | 20 일등락 (평균) |
|------|--------|------|------------------|
| WIT | Wipro | IT 아웃소싱 | -14.1% |
| INFY | Infosys | IT 아웃소싱 | -17.3% |
| ACN | Accenture | IT 아웃소싱 | -12.9% |
| CTSH | Cognizant | IT 아웃소싱 | -12.2% |
| TCS.NS | Tata Consultancy | IT 아웃소싱 | -14.4% |
| HCLTECH.NS | HCL Technologies | IT 아웃소싱 | -17.1% |
| DASH | DoorDash | 배달·결제 | -12.0% |
| Z | Zillow | 부동산 | -22.3% |
| OPEN | Opendoor | 부동산 | -4.9% |

#### 🟡 MEDIUM 위험 (12 개 종목)
전통 SaaS 및 플랫폼 기업

| 티커 | 종목명 | 섹터 | 위험 사유 |
|------|--------|------|-----------|
| CRM | Salesforce | 전통 SaaS | AI 네이티브 CRM 으로 전환 위험 |
| ORCL | Oracle | 전통 SaaS | 레거시 ERP 대체 위험 |
| SAP | SAP | 전통 SaaS | 레거시 시스템 대체 위험 |
| ADBE | Adobe | 전통 SaaS | 생성형 AI 에 의한 자동화 |
| NOW | ServiceNow | 전통 SaaS | AI 워크플로우 자동화 |
| WDAY | Workday | 전통 SaaS | HR AI 자동화 |
| AXP | American Express | 배달·결제 | 화이트칼라 소비 감소 |
| PYPL | PayPal | 배달·결제 | 소비 감소·경쟁 심화 |
| SQ | Block | 배달·결제 | 중소기업 결제 감소 |
| UBER | Uber | 배달·결제 | 소비 위축·자율주행 위협 |
| 035420.KS | NAVER | 플랫폼 | AI 검색·광고 수익 감소 |
| 035720.KS | 카카오 | 플랫폼 | AI 비서 대체·모빌리티 위협 |

#### ⚪ LOW 위험 (3 개 종목)
하드웨어 및 엔터테인먼트

| 티커 | 종목명 | 섹터 | 위험 사유 |
|------|--------|------|-----------|
| IBM | IBM | IT 서비스 | 레거시 IT 서비스 AI 대체 |
| HPQ | HP Inc | 하드웨어 | PC 수요 감소 (재택근무 종료) |
| DELL | Dell | 하드웨어 | 엔터프라이즈 PC 수요 감소 |

---

## 📊 생성된 파일

| 파일명 | 설명 |
|--------|------|
| `citrini_risky_stocks.py` | Citrini 부정적 종목 데이터 수집 및 보고서 생성 |
| `citrini_report_YYYYMMDD_HHMM.json` | Citrini 보고서 (JSON) |
| `citrini_report_YYYYMMDD_HHMM.txt` | Citrini 보고서 (TXT) |
| `db_manager.py` (수정) | Citrini DB 저장/조회 함수 추가 |
| `dashboard.py` (수정) | Citrini 부정적 종목 탭 추가 |

---

## 🚀 사용 방법

### 1.单次 실행 (즉시 분석)

```bash
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" citrini_risky_stocks.py
```

### 2. 대시보드에서 확인

```bash
"C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe" -m streamlit run dashboard.py
```

대시보드의 **5 번째 탭 "⚠️ Citrini 2028 부정적 종목"**에서 확인 가능합니다.

---

## 📈 DB 테이블 구조

### `citrini_risky` 테이블

```sql
CREATE TABLE citrini_risky (
    id           INTEGER PRIMARY KEY,
    date         TEXT NOT NULL,      -- YYYYMMDD
    run_at       TEXT NOT NULL,      -- ISO 타임스탬프
    ticker       TEXT NOT NULL,
    name         TEXT,
    market       TEXT,               -- US/KOSPI/KOSDAQ/India
    sector       TEXT,               -- IT 아웃소싱/전통 SaaS 등
    risk_level   TEXT,               -- HIGH/MEDIUM/LOW
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
    reason       TEXT,               -- 위험 사유
    exposure     TEXT                -- 노출 요인
);
```

---

## 🔍 대시보드 기능

### TAB 5: Citrini 2028 부정적 종목

#### 주요 기능:
1. **성과 요약**
   - 분석 종목수, 평균 20 일수익률, HIGH 위험평균, 최저수익률

2. **부정적 종목 목록**
   - 위험등급별 필터 (ALL/HIGH/MEDIUM/LOW)
   - 20 일등락 정렬 (오름차순 - 최악의 성과부터)
   - 색상 강조 (-15% 미만: 빨강, -5% 미만: 주황)

3. **섹터별 필터**
   - IT 아웃소싱, 전통 SaaS, 배달·결제, 부동산, 플랫폼 등
   - 섹터별 위험 종목 조회

4. **위기 선행 지표**
   - IGV, XHB, ^VIX, ^TNX, DXY, XRT, XLY, KRE

---

## 📊 섹터별 위험 종목

| 섹터 | 종목수 | 주요 종목 |
|------|--------|-----------|
| IT 아웃소싱 | 6 | Wipro, Infosys, Accenture, Cognizant, TCS, HCL |
| 전통 SaaS | 6 | Salesforce, Oracle, SAP, Adobe, ServiceNow, Workday |
| 배달·결제 | 4 | DoorDash, Amex, PayPal, Uber |
| 부동산 | 2 | Zillow, Opendoor |
| 플랫폼 | 2 | NAVER, 카카오 |
| IT 서비스 | 1 | IBM |
| 하드웨어 | 2 | HP, Dell |
| 엔터테인먼트 | 1 | JYP Ent |

---

## ⚠️ 투자 경고

### Citrini 시나리오의 의미

이 데이터는 **시나리오 기반 경고**이며, 실제 위기 발생 여부는 다릅니다.

**투자 권고:**
- 🔴 **HIGH 위험**: 즉시 축소 또는 헤지 고려
- 🟡 **MEDIUM 위험**: 모니터링 및 점진적 축소
- ⚪ **LOW 위험**: 장기적 위험 인식 유지

### 위기 선행 지표 모니터링

| 지표 | 현재 | 경고 수준 | 의미 |
|------|------|-----------|------|
| IGV | - | -15% 이하 | SaaS 멀티플 압축 |
| ^VIX | - | 50+ | 위기 급박 |
| ^TNX | - | 급락 | 디플레이션 신호 |
| DXY | - | 급등 | 위험회피 자금 이동 |

---

## 📚 출처 및 참고

### 주요 출처:
1. **Citrini Research** "2028 Global Intelligence Crisis" (2026-02-22)
   - 저자: James van Geelen & Alap Shah
   - 시나리오 보고서 (예측이 아닌 경고)

2. **ARK Invest** "Big Ideas 2026" (2026-01-21)
   - 대조적 시나리오: AI 낙관론
   - 수혜주 vs 피해주 대비 분석

### 참고 사항:
- 이 시스템은 **투자 참고용**입니다
- 최종 투자 결정은 **본인의 책임**입니다
- 실제 위기 발생 여부는 시나리오와 다를 수 있습니다
- 지속적인 모니터링과 업데이트가 필요합니다

---

## ✅ 시스템 체크리스트

- [x] Citrini 2028 보고서 기반 부정적 종목 추출
- [x] DB 테이블 (`citrini_risky`) 생성
- [x] 데이터 수집 모듈 (`citrini_risky_stocks.py`) 구현
- [x] 위험등급별 분류 (HIGH/MEDIUM/LOW)
- [x] 섹터별 분류 (8 개 섹터)
- [x] 경고 보고서 생성 기능
- [x] 대시보드 통합 (5 번째 탭)
- [x] 위기 선행 지표 모니터링
- [x] 시스템 테스트 완료

---

**최종 업데이트:** 2026-03-05  
**버전:** 1.0  
**시스템:** Citrini 2028 부정적 종목 추적
