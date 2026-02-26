"""
지정학/거시경제 데이터 수집기 (미·중 중심)
미국·중국 경제지표 + 원자재/해운 운임 + 무역 통계를 수집한다.

⚠️  이 모듈는 주식 어드바이저 시스템의 일부로, 
    한국 기업에 미치는 미·중 영향을 분석하는 데 사용됩니다.
"""

import os
import sys
import json
import datetime
import time
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import yfinance as yf
import pandas as pd
from dotenv import dotenv_values

# .env 로드
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_cfg = dotenv_values(_env_path)


def _get_env(key: str, default: str = "") -> str:
    """환경변수 → .env 파일 순으로 값을 가져온다."""
    return os.environ.get(key) or _cfg.get(key) or default


# ──────────────────────────────────────────────
# 1. 미국 경제지표 (FRED API 확장)
# ──────────────────────────────────────────────

def collect_us_economic_indicators(api_key: str = None) -> dict:
    """
    FRED API 를 사용해 미국 주요 경제지표를 수집한다.
    API 키가 없으면 yfinance 대체 데이터로 수집.

    수집 항목:
    - 금리: 연방기금금리, 국채 10 년/2 년/3 개월, 장단기 금리차
    - 물가: CPI, 핵심 CPI, PCE, 핵심 PCE
    - 고용: 실업률, 비농업 고용인구, 시간당 임금
    - 경기: GDP, 소비자신뢰, 제조업 PMI, 서비스업 PMI
    - 통화: M2, 달러인덱스 (DXY)
    """
    key = api_key or _get_env("FRED_API_KEY")
    result = {}

    # FRED API 키가 없으면 yfinance 로 대체 수집
    if not key or key == "your_fred_api_key_here":
        print("  ⚠️  FRED_API_KEY 없음 → yfinance 대체 데이터 수집")
        return collect_us_economic_indicators_yfinance()
    
    print("  🇺🇸 미국 경제지표 수집 중 (FRED API)...")
    
    # FRED 시리즈 ID 매핑
    series_map = {
        # ── 금리 ──
        "연방기금금리": "FEDFUNDS",
        "국채_10 년": "DGS10",
        "국채_2 년": "DGS2",
        "국채_3 개월": "DGS3MO",
        "금리스프레드 (10Y-3M)": "T10Y3M",  # 장단기 금리차 (역전 시 경기침체 신호)
        
        # ── 물가 ──
        "CPI(전체)": "CPIAUCSL",
        "CPI(핵심)": "CPILFESL",  # 식품·에너지 제외
        "PCE(전체)": "PCEPI",
        "PCE(핵심)": "PCEPILFE",
        
        # ── 고용 ──
        "실업률": "UNRATE",
        "비농업고용": "PAYEMS",
        "시간당임금": "CES0500000003",
        
        # ── 경기 ──
        "GDP(전분기대비%)": "A191RL1Q225SBEA",
        "소비자신뢰": "UMCSENT",
        "제조업 PMI": "MANEMP",
        "서비스업 PMI": "NONMANEMP",
        
        # ── 통화 ──
        "M2통화량": "M2SL",
    }
    
    for name, series_id in series_map.items():
        try:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={key}"
                f"&file_type=json&limit=2&sort_order=desc"
            )
            resp = requests.get(url, timeout=15)
            obs = resp.json().get("observations", [])
            
            if obs:
                current = obs[0]["value"]
                prev = obs[1]["value"] if len(obs) > 1 else current
                date = obs[0]["date"]
                
                # 전월/전분기 대비 변화
                try:
                    change = float(current) - float(prev)
                    change_pct = (float(current) / float(prev) - 1) * 100 if float(prev) else 0
                except:
                    change = 0
                    change_pct = 0
                
                result[name] = {
                    "현재값": current,
                    "날짜": date,
                    "전월대비": round(change, 3),
                    "전월대비 (%)": round(change_pct, 2),
                }
        except Exception as e:
            result[name] = {"오류": str(e)}
        
        time.sleep(0.1)  # API rate limit
    
    # 달러인덱스 (yfinance)
    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d")
        if not dxy.empty:
            cur = dxy["Close"].iloc[-1]
            prev = dxy["Close"].iloc[-2] if len(dxy) > 1 else cur
            result["달러인덱스 (DXY)"] = {
                "현재값": round(cur, 2),
                "전일대비 (%)": round((cur - prev) / prev * 100, 2),
            }
    except:
        result["달러인덱스 (DXY)"] = {"오류": "데이터 없음"}
    
    print(f"  ✓ {len(result)}개 미국 경제지표 수집 완료")
    return result


def collect_us_economic_indicators_yfinance() -> dict:
    """
    FRED API 키가 없을 때 yfinance 로 대체 데이터를 수집한다.
    
    수집 항목:
    - 국채 금리 (10 년, 2 년)
    - 달러인덱스
    - VIX (공포지수)
    - S&P500, 나스닥
    """
    result = {}
    
    # 미국 국채 금리 (티커로 대체)
    treasury_bonds = {
        "국채_10 년": "^TNX",  # 10 년물 금리 (0.1 배)
        "국채_2 년": "^UST",   # 2 년물 금리
    }
    
    for name, ticker in treasury_bonds.items():
        try:
            data = yf.Ticker(ticker).history(period="5d")
            if not data.empty:
                cur = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2] if len(data) > 1 else cur
                
                # ^TNX 는 0.1 배所以需要 조정
                if name == "국채_10 년":
                    cur = cur / 10
                    prev = prev / 10
                
                result[name] = {
                    "현재값": round(cur, 3),
                    "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                    "데이터소스": "yfinance",
                }
        except Exception as e:
            result[name] = {"오류": str(e), "데이터소스": "yfinance"}
    
    # 달러인덱스
    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d")
        if not dxy.empty:
            cur = dxy["Close"].iloc[-1]
            prev = dxy["Close"].iloc[-2] if len(dxy) > 1 else cur
            result["달러인덱스"] = {
                "현재값": round(cur, 2),
                "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                "데이터소스": "yfinance",
            }
    except:
        result["달러인덱스"] = {"오류": "데이터 없음", "데이터소스": "yfinance"}
    
    # VIX (공포지수)
    try:
        vix = yf.Ticker("^VIX").history(period="5d")
        if not vix.empty:
            cur = vix["Close"].iloc[-1]
            prev = vix["Close"].iloc[-2] if len(vix) > 1 else cur
            result["VIX_공포지수"] = {
                "현재값": round(cur, 2),
                "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                "해석": "20 이상이면 시장 불안",
                "데이터소스": "yfinance",
            }
    except:
        result["VIX_공포지수"] = {"오류": "데이터 없음", "데이터소스": "yfinance"}
    
    # S&P500, 나스닥
    us_indices = {
        "S&P500": "^GSPC",
        "나스닥": "^IXIC",
        "다우존스": "^DJI",
    }
    
    for name, ticker in us_indices.items():
        try:
            idx = yf.Ticker(ticker).history(period="5d")
            if not idx.empty:
                cur = idx["Close"].iloc[-1]
                prev = idx["Close"].iloc[-2] if len(idx) > 1 else cur
                result[f"미국증시_{name}"] = {
                    "현재값": round(cur, 2),
                    "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                    "데이터소스": "yfinance",
                }
        except:
            result[f"미국증시_{name}"] = {"오류": "데이터 없음", "데이터소스": "yfinance"}
    
    print(f"  ✓ {len(result)}개 미국 경제지표 (yfinance 대체) 수집 완료")
    return result


# ──────────────────────────────────────────────
# 2. 중국 경제지표
# ──────────────────────────────────────────────

def collect_china_economic_indicators() -> dict:
    """
    중국 주요 경제지표를 수집한다.
    
    수집 항목:
    - GDP 성장률
    - 제조업/비제조업 PMI
    - 산업생산
    - 소매판매
    - 고정자산투자
    - 수출/수입
    - CPI/PPI
    - 위안화 환율
    """
    print("  🇨🇳 중국 경제지표 수집 중...")
    result = {}
    
    # 중국 지표는 공식 API 가 제한적이므로 yfinance + 웹기반 데이터 활용
    # 일부 지표는 대용 데이터 (프록시) 사용
    
    # ── 위안화 환율 (USD/CNY) ──
    try:
        cny = yf.Ticker("CNY=X").history(period="5d")
        if not cny.empty:
            cur = cny["Close"].iloc[-1]
            prev = cny["Close"].iloc[-2] if len(cny) > 1 else cur
            result["위안화환율 (USD/CNY)"] = {
                "현재값": round(cur, 4),
                "전일대비 (%)": round((cur - prev) / prev * 100, 2),
            }
    except:
        result["위안화환율 (USD/CNY)"] = {"오류": "데이터 없음"}
    
    # ── 중국 주식시장 (상해/심천) ──
    china_indices = {
        "상해종합": "000001.SS",
        "심천성분": "399001.SZ",
        "항생 (항셍)": "^HSI",
        "항생테크": "^HSTECH",
    }
    
    for name, ticker in china_indices.items():
        try:
            idx = yf.Ticker(ticker).history(period="5d")
            if not idx.empty:
                cur = idx["Close"].iloc[-1]
                prev = idx["Close"].iloc[-2] if len(idx) > 1 else cur
                result[f"중국증시_{name}"] = {
                    "현재값": round(cur, 2),
                    "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                }
        except:
            result[f"중국증시_{name}"] = {"오류": "데이터 없음"}
    
    # ── 원자재 (중국 수요 민감) ──
    china_commodities = {
        "구리": "HG=F",
        "철광석": "62%FF.CMX",
        "원유 (브렌트)": "BZ=F",
    }
    
    for name, ticker in china_commodities.items():
        try:
            comm = yf.Ticker(ticker).history(period="5d")
            if not comm.empty:
                cur = comm["Close"].iloc[-1]
                prev = comm["Close"].iloc[-2] if len(comm) > 1 else cur
                result[f"원자재_{name}"] = {
                    "현재값": round(cur, 2),
                    "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                }
        except:
            result[f"원자재_{name}"] = {"오류": "데이터 없음"}
    
    # ── PMI (웹 스크래핑 대체: 뉴스 RSS) ──
    # 실제 PMI 는 뉴스에서 파싱하거나 수동 입력
    # 여기서는 최근 뉴스 기반 감성 점수로 대체
    try:
        news_result = _fetch_china_pmi_from_news()
        if news_result:
            result["중국_PMI_뉴스감성"] = news_result
    except:
        pass
    
    print(f"  ✓ {len(result)}개 중국 경제지표 수집 완료")
    return result


def _fetch_china_pmi_from_news() -> dict:
    """
    중국 PMI 관련 뉴스를 검색해 감성 분석용 데이터를 반환한다.
    """
    # 뉴스 API 가 없으면 기본값 반환
    news_api_key = _get_env("NEWS_API_KEY")
    
    if news_api_key and news_api_key != "your_newsapi_key_here":
        try:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q=China+PMI+manufacturing&language=en"
                f"&sortBy=publishedAt&pageSize=5"
                f"&apiKey={news_api_key}"
            )
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])
            
            if articles:
                headlines = [a["title"] for a in articles[:5]]
                return {
                    "최신뉴스": headlines,
                    "수집일": datetime.date.today().isoformat(),
                }
        except:
            pass
    
    # 뉴스 API 없으면 수동 입력용 템플릿
    return {
        "안내": "중국 PMI 는 수동으로 업데이트하거나 뉴스 API 키를 설정하세요.",
        "참고": "공식 발표: 중국 국가통계국 (http://www.stats.gov.cn)",
    }


# ──────────────────────────────────────────────
# 3. 원자재 가격 (한국 기업 민감도 높은 품목)
# ──────────────────────────────────────────────

def collect_commodity_prices() -> dict:
    """
    한국 기업에 영향력 있는 원자재 가격을 수집한다.
    
    수집 항목:
    - 에너지: WTI, 브렌트, 천연가스
    - 금속: 구리, 알루미늄, 니켈, 아연
    - 배터리: 리튬, 코발트 (뉴스 기반)
    - 희토류: 희토류 지수 (뉴스 기반)
    - 농산물: 대두, 옥수수, 밀
    """
    print("  🛢️ 원자재 가격 수집 중...")
    result = {}
    
    commodities = {
        # ── 에너지 ──
        "WTI 원유": "CL=F",
        "브렌트유": "BZ=F",
        "천연가스": "NG=F",
        
        # ── 금속 ──
        "구리": "HG=F",
        "알루미늄": "ALI=F",
        "니켈": "NI=F",
        "아연": "ZS=F",
        "금": "GC=F",
        "은": "SI=F",
        
        # ── 농산물 ──
        "대두": "ZS=F",
        "옥수수": "ZC=F",
        "밀": "ZW=F",
    }
    
    for name, ticker in commodities.items():
        try:
            data = yf.Ticker(ticker).history(period="30d")
            if not data.empty:
                cur = data["Close"].iloc[-1]
                prev = data["Close"].iloc[-2] if len(data) > 1 else cur
                high_30d = data["High"].max()
                low_30d = data["Low"].min()
                
                result[name] = {
                    "현재가": round(cur, 2),
                    "전일대비 (%)": round((cur - prev) / prev * 100, 2),
                    "30 일고점": round(high_30d, 2),
                    "30 일저점": round(low_30d, 2),
                    "고점대비 (%)": round((cur - high_30d) / high_30d * 100, 1),
                }
        except Exception as e:
            result[name] = {"오류": str(e)}
        
        time.sleep(0.1)
    
    # ── 리튬/코발트/희토류 (뉴스 기반 감성) ──
    battery_materials = _collect_battery_materials_news()
    if battery_materials:
        result["배터리원료_뉴스"] = battery_materials
    
    print(f"  ✓ {len(result)}개 원자재 데이터 수집 완료")
    return result


def _collect_battery_materials_news() -> dict:
    """
    리튬, 코발트, 희토류 관련 뉴스를 수집한다.
    가격 변동이 한국 배터리 기업에 미치는 영향 분석용.
    """
    news_api_key = _get_env("NEWS_API_KEY")
    result = {}
    
    keywords = ["lithium price", "cobalt price", "rare earth price"]
    
    for keyword in keywords:
        if news_api_key and news_api_key != "your_newsapi_key_here":
            try:
                url = (
                    f"https://newsapi.org/v2/everything"
                    f"?q={keyword}&language=en&sortBy=publishedAt&pageSize=3"
                    f"&apiKey={news_api_key}"
                )
                resp = requests.get(url, timeout=10)
                articles = resp.json().get("articles", [])
                
                if articles:
                    result[keyword] = [a["title"] for a in articles[:3]]
            except:
                pass
        time.sleep(0.2)
    
    if not result:
        return {
            "안내": "뉴스 API 키가 없으면 배터리 원료 데이터를 수집할 수 없습니다.",
        }
    
    return result


# ──────────────────────────────────────────────
# 4. 해운 운임 (수출입 기업 영향도)
# ──────────────────────────────────────────────

def collect_shipping_freight_rates() -> dict:
    """
    해운 운임 지수를 수집한다.
    
    수집 항목:
    - Baltic Dry Index (벌크선)
    - Shanghai Container Freight Index
    - 한국항만물류협회 운임지수
    """
    print("  🚢 해운 운임 수집 중...")
    result = {}
    
    # ── Baltic Dry Index (웹기반) ──
    # 공식 API 는 유료이므로 뉴스/웹 스크래핑 대체
    bdi = _fetch_baltic_dry_index()
    if bdi:
        result["Baltic_Dry_Index"] = bdi
    
    # ── 상해 컨테이너 운임지수 (SCFI) ──
    scfi = _fetch_shanghai_container_index()
    if scfi:
        result["SCFI_상해컨테이너"] = scfi
    
    # ── 한미/한중 운임 (뉴스 기반) ──
    kr_shipping = _fetch_korea_shipping_news()
    if kr_shipping:
        result["한국해운_뉴스"] = kr_shipping
    
    print(f"  ✓ {len(result)}개 해운 운임 데이터 수집 완료")
    return result


def _fetch_baltic_dry_index() -> dict:
    """
    Baltic Dry Index 를 수집한다.
    공식 API 는 없으므로 yfinance 대체 티커 사용.
    """
    # BDI 는 yfinance 에서 직접 지원하지 않음 → 뉴스 기반
    news_api_key = _get_env("NEWS_API_KEY")
    
    if news_api_key and news_api_key != "your_newsapi_key_here":
        try:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q=Baltic+Dry+Index&language=en&sortBy=publishedAt&pageSize=5"
                f"&apiKey={news_api_key}"
            )
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])
            
            if articles:
                return {
                    "최신뉴스": [a["title"] for a in articles[:5]],
                    "수집일": datetime.date.today().isoformat(),
                }
        except:
            pass
    
    return {
        "안내": "Baltic Dry Index 는 뉴스 API 키 설정 시 최신 뉴스를 제공합니다.",
        "참고": "공식 발표: https://www.balticexchange.com",
    }


def _fetch_shanghai_container_index() -> dict:
    """
    Shanghai Container Freight Index (SCFI) 관련 뉴스.
    """
    news_api_key = _get_env("NEWS_API_KEY")
    
    if news_api_key and news_api_key != "your_newsapi_key_here":
        try:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q=Shanghai+Container+Freight+Index+SCFI&language=en"
                f"&sortBy=publishedAt&pageSize=3"
                f"&apiKey={news_api_key}"
            )
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])
            
            if articles:
                return {
                    "최신뉴스": [a["title"] for a in articles[:3]],
                    "수집일": datetime.date.today().isoformat(),
                }
        except:
            pass
    
    return {
        "안내": "SCFI 는 뉴스 API 키 설정 시 최신 뉴스를 제공합니다.",
    }


def _fetch_korea_shipping_news() -> dict:
    """
    한국 해운/물류 관련 뉴스 (한미/한중 항로).
    """
    news_api_key = _get_env("NEWS_API_KEY")
    
    if news_api_key and news_api_key != "your_newsapi_key_here":
        try:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q=Korea+shipping+freight+export&language=en"
                f"&sortBy=publishedAt&pageSize=3"
                f"&apiKey={news_api_key}"
            )
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])
            
            if articles:
                return {
                    "최신뉴스": [a["title"] for a in articles[:3]],
                    "수집일": datetime.date.today().isoformat(),
                }
        except:
            pass
    
    return {}


# ──────────────────────────────────────────────
# 5. 미·중 무역/관세 데이터
# ──────────────────────────────────────────────

def collect_us_china_trade_data() -> dict:
    """
    미·중 무역 분쟁 관련 데이터를 수집한다.
    
    수집 항목:
    - 미국 관세 부과 현황
    - 중국 보복 관세
    - 수출통제/제재 목록
    - 무역수지
    """
    print("  📊 미·중 무역 데이터 수집 중...")
    result = {}
    
    # ── 무역수지 (FRED) ──
    fred_key = _get_env("FRED_API_KEY")
    
    if fred_key and fred_key != "your_fred_api_key_here":
        trade_series = {
            "미국무역수지": "TRADEFBAL",
            "미국대중국수지": "XCHNAUSM052N",
        }
        
        for name, series_id in trade_series.items():
            try:
                url = (
                    f"https://api.stlouisfed.org/fred/series/observations"
                    f"?series_id={series_id}&api_key={fred_key}"
                    f"&file_type=json&limit=2&sort_order=desc"
                )
                resp = requests.get(url, timeout=15)
                obs = resp.json().get("observations", [])
                
                if obs:
                    result[name] = {
                        "현재값": obs[0]["value"],
                        "날짜": obs[0]["date"],
                    }
            except:
                pass
    
    # ── 관세/제재 뉴스 ──
    news_api_key = _get_env("NEWS_API_KEY")
    
    if news_api_key and news_api_key != "your_newsapi_key_here":
        tariff_news = _fetch_tariff_news(news_api_key)
        if tariff_news:
            result["관세_무역뉴스"] = tariff_news
    
    print(f"  ✓ {len(result)}개 미·중 무역 데이터 수집 완료")
    return result


def _fetch_tariff_news(api_key: str) -> dict:
    """
    관세 및 무역 분쟁 관련 뉴스를 수집한다.
    """
    keywords = [
        "US China tariff trade war",
        "China export control sanction",
        "US semiconductor restriction China",
    ]
    
    result = {}
    
    for kw in keywords:
        try:
            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={kw}&language=en&sortBy=publishedAt&pageSize=3"
                f"&apiKey={api_key}"
            )
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])
            
            if articles:
                result[kw] = [a["title"] for a in articles[:3]]
        except:
            pass
        time.sleep(0.2)
    
    return result


# ──────────────────────────────────────────────
# 6. 종합 수집 함수
# ──────────────────────────────────────────────

def collect_all_geopolitical_data() -> dict:
    """
    모든 지정학/거시경제 데이터를 수집한다.
    """
    print("\n" + "=" * 60)
    print("  🌍 지정학/거시경제 데이터 수집 시작")
    print("=" * 60)
    
    data = {}
    
    # 1. 미국 경제지표
    data["us_economy"] = collect_us_economic_indicators()
    
    # 2. 중국 경제지표
    data["china_economy"] = collect_china_economic_indicators()
    
    # 3. 원자재 가격
    data["commodities"] = collect_commodity_prices()
    
    # 4. 해운 운임
    data["shipping"] = collect_shipping_freight_rates()
    
    # 5. 미·중 무역
    data["us_china_trade"] = collect_us_china_trade_data()
    
    print("\n" + "=" * 60)
    print("  ✓ 지정학/거시경제 데이터 수집 완료")
    print("=" * 60)
    
    return data


# ──────────────────────────────────────────────
# 7. 섹터별 미·중 의존도 매핑
# ──────────────────────────────────────────────

SECTOR_EXPOSURE_MAP = {
    """
    각 섹터별 미·중 의존도 (수출비중, 공급망 리스크) 를 매핑한다.
    점수: 0 (영향없음) ~ 5 (매우높음)
    """
    # 반도체
    "005930": {"name": "삼성전자", "sector": "반도체", "US_exposure": 4, "CN_exposure": 3},
    "000660": {"name": "SK 하이닉스", "sector": "반도체", "US_exposure": 5, "CN_exposure": 4},
    "042700": {"name": "한미반도체", "sector": "반도체장비", "US_exposure": 5, "CN_exposure": 2},
    
    # 2 차전지
    "373220": {"name": "LG 에너지솔루션", "sector": "배터리", "US_exposure": 5, "CN_exposure": 2},
    "006400": {"name": "삼성 SDI", "sector": "배터리", "US_exposure": 4, "CN_exposure": 3},
    "051910": {"name": "LG 화학", "sector": "화학/배터리", "US_exposure": 4, "CN_exposure": 3},
    
    # 인터넷/AI
    "035420": {"name": "NAVER", "sector": "플랫폼", "US_exposure": 2, "CN_exposure": 2},
    "035720": {"name": "카카오", "sector": "플랫폼", "US_exposure": 1, "CN_exposure": 1},
    
    # 자동차
    "005380": {"name": "현대차", "sector": "자동차", "US_exposure": 4, "CN_exposure": 2},
    "000270": {"name": "기아", "sector": "자동차", "US_exposure": 4, "CN_exposure": 2},
    
    # 바이오
    "207940": {"name": "삼성바이오로직스", "sector": "바이오", "US_exposure": 5, "CN_exposure": 1},
    "068270": {"name": "셀트리온", "sector": "바이오", "US_exposure": 4, "CN_exposure": 2},
    
    # 금융
    "105560": {"name": "KB 금융", "sector": "금융", "US_exposure": 2, "CN_exposure": 2},
    "055550": {"name": "신한지주", "sector": "금융", "US_exposure": 2, "CN_exposure": 3},
    
    # 방산/기계
    "012450": {"name": "한화에어로스페이스", "sector": "방산", "US_exposure": 3, "CN_exposure": 1},
    "329180": {"name": "HD 현대중공업", "sector": "造船", "US_exposure": 3, "CN_exposure": 2},
}


def get_sector_exposure_analysis(geopolitical_data: dict) -> dict:
    """
    수집된 지정학 데이터를 바탕으로 섹터별 영향도를 분석한다.
    """
    analysis = {}
    
    us_econ = geopolitical_data.get("us_economy", {})
    china_econ = geopolitical_data.get("china_economy", {})
    commodities = geopolitical_data.get("commodities", {})
    
    # 미국 금리/달러 강세 → 수출기업 압박
    us_rate = us_econ.get("연방기금금리", {}).get("현재값", 0)
    dxy = us_econ.get("달러인덱스 (DXY)", {}).get("현재값", 0)
    
    # 중국 경기 둔화 → 중국 의존도 높은 기업 리스크
    china_pmi_news = china_econ.get("중국_PMI_뉴스감성", {})
    
    # 원자재 가격 → 원가 압박
    oil_price = commodities.get("WTI 원유", {}).get("현재가", 0)
    copper_price = commodities.get("구리", {}).get("현재가", 0)
    
    for code, info in SECTOR_EXPOSURE_MAP.items():
        risk_factors = []
        
        # 미국 금리 리스크
        if float(us_rate) > 4.0:
            if info["US_exposure"] >= 4:
                risk_factors.append(f"고금리 장기화로 {info['sector']} 수출 압박")
        
        # 중국 경기 리스크
        if info["CN_exposure"] >= 3:
            risk_factors.append(f"중국 경기둔화 민감도 높음 (의존도:{info['CN_exposure']}/5)")
        
        # 원자재 리스크
        if oil_price and float(oil_price) > 80:
            risk_factors.append(f"고유가 ({oil_price}달러) 로 원가 부담")
        
        if copper_price and float(copper_price) > 4.5:
            risk_factors.append(f"구리가격 상승 ({copper_price}달러) 으로 생산비 증가")
        
        analysis[code] = {
            "종목명": info["name"],
            "섹터": info["sector"],
            "미국노출": info["US_exposure"],
            "중국노출": info["CN_exposure"],
            "리스크요인": risk_factors,
        }
    
    return analysis


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # 전체 데이터 수집
    geo_data = collect_all_geopolitical_data()
    
    # 섹터별 영향도 분석
    exposure = get_sector_exposure_analysis(geo_data)
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("  📈 섹터별 미·중 영향도 분석")
    print("=" * 80)
    
    for code, info in exposure.items():
        print(f"\n  [{code}] {info['종목명']} ({info['섹터']})")
        print(f"    미국 노출: {'★' * info['미국노출']}{'☆' * (5-info['미국노출'])}")
        print(f"    중국 노출: {'★' * info['중국노출']}{'☆' * (5-info['중국노출'])}")
        
        if info["리스크요인"]:
            print("    리스크 요인:")
            for risk in info["리스크요인"]:
                print(f"      - {risk}")
    
    # JSON 저장
    output_path = f"geopolitical_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geo_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 데이터 저장 완료: {output_path}")
