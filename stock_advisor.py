"""
주식 분석 어드바이저 시스템 (DART + 해외지표 통합판)

분석 레이어:
  1. 거시경제  — KOSPI·S&P500·나스닥·VIX·환율·유가·금
  2. 뉴스 감성 — RSS/NewsAPI → Claude 감성 분석
  3. 기술적지표 — MA5/20/60 · RSI · MACD · 볼린저밴드 · 피봇지지/저항
  4. DART 재무 — 연간재무 · 분기실적 추세 · 중요공시
  5. 해외 섹터 — 섹터별 연관 해외주식·ETF (NVDA/TSM/SOXX/TSLA/LMT 등)

⚠️  이 시스템은 투자 참고용입니다. 최종 투자 결정은 반드시 본인이 직접 판단하세요.
"""

import os
import sys
import json
import time
import datetime
from typing import Optional
from dotenv import dotenv_values

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import anthropic
import yfinance as yf
import pandas as pd
import requests
import feedparser

from dart_collector import collect_dart_data as _dart_collect

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_cfg = dotenv_values(_env_path)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _cfg.get(key) or default


# ──────────────────────────────────────────────────────────
# 종목코드 → 연관 해외 지표 매핑
# ──────────────────────────────────────────────────────────
_OVERSEAS_MAP = {
    "005930": {  # 삼성전자
        "tickers": ["NVDA", "TSM", "SOXX", "AMAT", "^SOX"],
        "memo":    "엔비디아·TSMC·SOXX는 메모리/파운드리 수요의 선행지표",
    },
    "000660": {  # SK하이닉스
        "tickers": ["NVDA", "TSM", "SOXX", "AMAT"],
        "memo":    "HBM 최대 고객사 엔비디아 실적이 직결 지표",
    },
    "042700": {  # 한미반도체
        "tickers": ["NVDA", "TSM", "SOXX"],
        "memo":    "HBM 패키징 장비 수혜 — 엔비디아·TSMC 수주와 연동",
    },
    "373220": {  # LG에너지솔루션
        "tickers": ["TSLA", "LIT", "BYDDF", "CHKP"],
        "memo":    "테슬라 판매량·리튬 ETF(LIT)가 배터리 수요 대리지표",
    },
    "006400": {  # 삼성SDI
        "tickers": ["TSLA", "LIT", "STLA"],
        "memo":    "전기차 배터리 고객사(스텔란티스·BMW) 수요 연동",
    },
    "051910": {  # LG화학
        "tickers": ["LIT", "HG=F", "TSLA"],
        "memo":    "리튬·구리 선물 가격이 배터리 소재 원가 영향",
    },
    "035420": {  # NAVER
        "tickers": ["META", "GOOGL", "MSFT"],
        "memo":    "글로벌 AI·광고 플랫폼 흐름이 밸류에이션 리레이팅 기준",
    },
    "035720": {  # 카카오
        "tickers": ["META", "SNAP", "GOOGL"],
        "memo":    "SNS·광고 플랫폼 글로벌 동향이 밸류에이션 참고",
    },
    "005380": {  # 현대차
        "tickers": ["TSLA", "GM", "F", "STLA"],
        "memo":    "글로벌 완성차 경쟁사 주가·전기차 수요 선행지표",
    },
    "000270": {  # 기아
        "tickers": ["TSLA", "GM", "F"],
        "memo":    "현대차 동일 섹터 — 미국 자동차 시장 수급 연동",
    },
    "207940": {  # 삼성바이오로직스
        "tickers": ["XBI", "IBB", "PFE", "MRK"],
        "memo":    "글로벌 바이오테크 ETF(XBI·IBB)가 CDMO 밸류에이션 기준",
    },
    "068270": {  # 셀트리온
        "tickers": ["XBI", "IBB", "AMGN"],
        "memo":    "바이오시밀러 경쟁사 암젠 동향·글로벌 바이오 지수",
    },
    "105560": {  # KB금융
        "tickers": ["^TNX", "XLF", "JPM"],
        "memo":    "미국 10년물 금리(^TNX)·글로벌 금융주 ETF(XLF) 연동",
    },
    "055550": {  # 신한지주
        "tickers": ["^TNX", "XLF", "C"],
        "memo":    "금리 방향이 NIM에 직결 — 미국 금리 추이 핵심",
    },
    "012450": {  # 한화에어로스페이스
        "tickers": ["LMT", "NOC", "RTX", "BA"],
        "memo":    "미국 방산주(록히드·레이시온)가 글로벌 방위비 지출 선행지표",
    },
    "329180": {  # HD현대중공업
        "tickers": ["LNG", "HG=F", "EURN"],
        "memo":    "LNG 선물·구리 선물이 조선 수주가격·원자재비 영향",
    },
}


class StockAdvisorSystem:
    """
    거시경제 + 뉴스 + 기술적지표 + DART 재무/공시 + 해외 섹터 지표를 종합해
    Claude에게 종목별 매수/매도 의견을 요청하는 시스템.
    """

    def __init__(self, target_stocks: Optional[list] = None):
        self.anthropic_client = anthropic.Anthropic(api_key=_get("ANTHROPIC_API_KEY"))
        self.fred_api_key = _get("FRED_API_KEY")
        self.news_api_key = _get("NEWS_API_KEY")
        self.dart_api_key = _get("DART_API_KEY")

        env_stocks = _get("TARGET_STOCKS", "005930,000660,035420").split(",")
        self.target_stocks = target_stocks or [s.strip() + ".KS" for s in env_stocks]

        self.collected_data: dict = {}

    # ──────────────────────────────────────────────
    # 1. 거시경제 데이터
    # ──────────────────────────────────────────────
    def collect_macro_data(self) -> dict:
        print("📊 거시경제 데이터 수집 중...")
        macro = {}
        for name, ticker in {
            "USD/KRW":      "KRW=X",
            "WTI유가":      "CL=F",
            "금(Gold)":     "GC=F",
            "VIX(공포지수)":"^VIX",
            "KOSPI":        "^KS11",
            "S&P500":       "^GSPC",
            "나스닥":        "^IXIC",
        }.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                if not hist.empty:
                    cur  = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2] if len(hist) > 1 else cur
                    macro[name] = {
                        "현재가":      round(cur, 2),
                        "전일대비(%)": round((cur - prev) / prev * 100, 2),
                    }
            except Exception as e:
                macro[name] = {"오류": str(e)}

        if self.fred_api_key and self.fred_api_key != "your_fred_api_key_here":
            for name, sid in {"미국기준금리": "FEDFUNDS",
                               "미국10년국채": "DGS10",
                               "미국2년국채":  "DGS2"}.items():
                try:
                    url = (f"https://api.stlouisfed.org/fred/series/observations"
                           f"?series_id={sid}&api_key={self.fred_api_key}"
                           f"&file_type=json&limit=2&sort_order=desc")
                    obs = requests.get(url, timeout=10).json().get("observations", [])
                    if obs:
                        macro[name] = {"현재값": obs[0]["value"], "날짜": obs[0]["date"]}
                except Exception as e:
                    macro[name] = {"오류": str(e)}

        self.collected_data["macro"] = macro
        print(f"  ✓ {len(macro)}개 거시지표 수집 완료")
        return macro

    # ──────────────────────────────────────────────
    # 2. 뉴스 감성 분석
    # ──────────────────────────────────────────────
    def analyze_news_sentiment(self) -> dict:
        print("📰 뉴스 감성 분석 중...")
        headlines = []

        if self.news_api_key and self.news_api_key != "your_newsapi_key_here":
            try:
                url = (f"https://newsapi.org/v2/everything?q=코스피+주식+경제"
                       f"&language=ko&sortBy=publishedAt&pageSize=10"
                       f"&apiKey={self.news_api_key}")
                headlines = [f"[{a['source']['name']}] {a['title']}"
                             for a in requests.get(url, timeout=10).json().get("articles", [])[:10]]
            except Exception:
                pass

        if not headlines:
            for rss in ["https://finance.naver.com/news/news_list.naver?mode=RSS",
                        "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"]:
                try:
                    feed = feedparser.parse(rss)
                    if feed.entries:
                        headlines = [e.title for e in feed.entries[:10]]
                        break
                except Exception:
                    continue

        if not headlines:
            result = {"헤드라인": [], "Claude분석": "뉴스 수집 실패"}
            self.collected_data["news_sentiment"] = result
            return result

        try:
            resp = self.anthropic_client.messages.create(
                model="claude-sonnet-4-6", max_tokens=400,
                messages=[{"role": "user", "content":
                    f"다음 뉴스 헤드라인의 주식시장 감성을 분석하세요:\n"
                    + "\n".join(f"- {h}" for h in headlines)
                    + "\n\n형식: 1.전체감성(매우긍정/긍정/중립/부정/매우부정) "
                      "2.긍정요인(1-2줄) 3.부정요인(1-2줄) 4.종합한줄요약"}])
            analysis = resp.content[0].text
        except Exception as e:
            analysis = f"Claude 분석 실패: {e}"

        result = {"헤드라인": headlines, "Claude분석": analysis}
        self.collected_data["news_sentiment"] = result
        print(f"  ✓ {len(headlines)}개 뉴스 분석 완료")
        return result

    # ──────────────────────────────────────────────
    # 3. 기술적 지표 + 피봇 지지/저항선
    # ──────────────────────────────────────────────
    def check_market_liquidity(self) -> dict:
        print("💹 기술적 지표 + 지지/저항선 분석 중...")
        liquidity = {}

        for ticker in self.target_stocks:
            try:
                stock = yf.Ticker(ticker)
                hist   = stock.history(period="120d")
                hist1y = stock.history(period="252d")
                if hist.empty:
                    liquidity[ticker] = {"오류": "데이터 없음"}
                    continue

                close  = hist["Close"]
                volume = hist["Volume"]

                # 이동평균
                ma5  = close.rolling(5).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma60 = close.rolling(60).mean().iloc[-1]

                # RSI(14)
                d     = close.diff()
                gain  = d.clip(lower=0).rolling(14).mean()
                loss  = (-d.clip(upper=0)).rolling(14).mean()
                rsi   = (100 - 100 / (1 + gain / loss)).iloc[-1]

                # MACD(12,26,9)
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd  = ema12 - ema26
                sig   = macd.ewm(span=9, adjust=False).mean()
                macd_val, sig_val = macd.iloc[-1], sig.iloc[-1]

                # 볼린저밴드(20, 2σ)
                bb_mid   = close.rolling(20).mean()
                bb_std   = close.rolling(20).std()
                bb_upper = (bb_mid + 2 * bb_std).iloc[-1]
                bb_lower = (bb_mid - 2 * bb_std).iloc[-1]
                cur      = close.iloc[-1]
                bb_pct   = (cur - bb_lower) / (bb_upper - bb_lower) * 100 \
                           if (bb_upper - bb_lower) > 0 else 50.0

                # 거래량
                avg_vol   = volume.rolling(20).mean().iloc[-1]
                vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1.0

                # 52주
                high52 = hist1y["High"].max() if not hist1y.empty else cur
                low52  = hist1y["Low"].min()  if not hist1y.empty else cur

                # 피봇 포인트 (전일 H·L·C 기준)
                pH, pL, pC = hist["High"].iloc[-2], hist["Low"].iloc[-2], close.iloc[-2]
                pivot = (pH + pL + pC) / 3
                r1, r2 = 2 * pivot - pL, pivot + (pH - pL)
                s1, s2 = 2 * pivot - pH, pivot - (pH - pL)

                # 최근 20일 스윙 고점/저점
                rec = hist.tail(20)
                sw_hi = [rec["High"].iloc[i] for i in range(1, len(rec)-1)
                         if rec["High"].iloc[i] > rec["High"].iloc[i-1]
                         and rec["High"].iloc[i] > rec["High"].iloc[i+1]]
                sw_lo = [rec["Low"].iloc[i]  for i in range(1, len(rec)-1)
                         if rec["Low"].iloc[i]  < rec["Low"].iloc[i-1]
                         and rec["Low"].iloc[i]  < rec["Low"].iloc[i+1]]

                near_res = round(min(sw_hi), 0) if sw_hi else round(r1, 0)
                near_sup = round(max(sw_lo), 0) if sw_lo else round(s1, 0)

                # 밸류에이션
                info      = stock.info
                name      = info.get("longName") or info.get("shortName") or ticker
                per       = info.get("trailingPE")
                pbr       = info.get("priceToBook")
                div_yield = info.get("dividendYield")

                prev_p     = close.iloc[-2]
                change_pct = (cur - prev_p) / prev_p * 100

                def _bb_sig(p):
                    if p > 100: return "상단돌파(과매수경고)"
                    if p < 0:   return "하단돌파(과매도반등)"
                    if p > 80:  return "상단근접"
                    if p < 20:  return "하단근접"
                    return "중립"

                liquidity[ticker] = {
                    "종목명":              name,
                    "현재가":              round(cur, 0),
                    "전일대비(%)":         round(change_pct, 2),
                    "MA5":                 round(ma5, 0),
                    "MA20":                round(ma20, 0),
                    "MA60":                round(ma60, 0),
                    "골든크로스":          bool(ma5 > ma20),
                    "MA정배열":            bool(ma5 > ma20 > ma60),
                    "RSI(14)":             round(rsi, 1),
                    "RSI신호":             "과매수" if rsi >= 70 else ("과매도" if rsi <= 30 else "중립"),
                    "MACD선":              round(macd_val, 1),
                    "시그널선":            round(sig_val, 1),
                    "MACD히스토그램":      round(macd_val - sig_val, 1),
                    "MACD>시그널":         bool(macd_val > sig_val),
                    "BB위치(%)":           round(bb_pct, 1),
                    "BB상단":              round(bb_upper, 0),
                    "BB하단":              round(bb_lower, 0),
                    "BB신호":              _bb_sig(bb_pct),
                    "거래량비율(vs20일)":  round(vol_ratio, 2),
                    "52주최고":            round(high52, 0),
                    "52주최저":            round(low52, 0),
                    "52주고점대비(%)":     round((cur - high52) / high52 * 100, 1),
                    # 피봇
                    "근접저항선":          near_res,
                    "근접지지선":          near_sup,
                    "피봇R2":              round(r2, 0),
                    "피봇R1":              round(r1, 0),
                    "피봇":                round(pivot, 0),
                    "피봇S1":              round(s1, 0),
                    "피봇S2":              round(s2, 0),
                    # 밸류에이션
                    "PER":                 round(per, 1) if per else None,
                    "PBR":                 round(pbr, 2) if pbr else None,
                    "배당수익률(%)":       round(div_yield * 100, 2) if div_yield else None,
                }
            except Exception as e:
                liquidity[ticker] = {"오류": str(e)}

        self.collected_data["liquidity"] = liquidity
        print(f"  ✓ {len(self.target_stocks)}개 종목 기술적 지표 완료")
        return liquidity

    # ──────────────────────────────────────────────
    # 4. DART 재무/공시
    # ──────────────────────────────────────────────
    def collect_dart_data(self) -> dict:
        if not self.dart_api_key or self.dart_api_key in ("", "your_dart_api_key_here"):
            print("⚠️  DART_API_KEY 없음 → 재무/공시 분석 생략")
            self.collected_data["dart"] = {}
            return {}

        print("📑 DART 재무/공시 데이터 수집 중...")
        codes = [t.replace(".KS", "").replace(".KQ", "") for t in self.target_stocks]
        dart_data = _dart_collect(codes, self.dart_api_key)
        self.collected_data["dart"] = dart_data
        print(f"  ✓ {len(dart_data)}개 종목 DART 수집 완료")
        return dart_data

    # ──────────────────────────────────────────────
    # 5. 해외 섹터 지표 (신규)
    # ──────────────────────────────────────────────
    def collect_overseas_data(self) -> dict:
        """
        섹터별 연관 해외 주식·ETF·선물 데이터 수집 (yfinance).

        수집 지표:
          반도체  : NVDA · TSM · ASML · SOXX · AMAT
          배터리  : TSLA · LIT · STLA
          자동차  : GM · F
          바이오  : XBI · IBB · AMGN · PFE
          AI/인터넷: META · GOOGL · MSFT
          방산    : LMT · NOC · RTX · BA
          원자재  : HG=F(구리) · LNG=F(LNG)
          거시    : DX=F(달러인덱스) · ^TNX(미10년채)
        """
        print("🌍 해외 섹터 지표 수집 중...")

        # (yfinance 티커, 표시명) 리스트
        OVERSEAS = [
            # 반도체
            ("NVDA",   "엔비디아"),
            ("TSM",    "TSMC(ADR)"),
            ("ASML",   "ASML홀딩"),
            ("SOXX",   "반도체ETF(SOXX)"),
            ("AMAT",   "어플라이드머티리얼"),
            # 배터리/EV
            ("TSLA",   "테슬라"),
            ("LIT",    "리튬ETF(LIT)"),
            ("STLA",   "스텔란티스"),
            # 자동차
            ("GM",     "GM"),
            ("F",      "포드"),
            # 바이오
            ("XBI",    "바이오테크ETF(XBI)"),
            ("IBB",    "바이오ETF(IBB)"),
            ("AMGN",   "암젠"),
            ("PFE",    "화이자"),
            # AI/인터넷
            ("META",   "메타"),
            ("GOOGL",  "알파벳(구글)"),
            ("MSFT",   "마이크로소프트"),
            # 방산
            ("LMT",    "록히드마틴"),
            ("NOC",    "노스롭그러먼"),
            ("RTX",    "레이시온"),
            ("BA",     "보잉"),
            # 원자재/LNG
            ("HG=F",   "구리선물"),
            ("LNG",    "Cheniere(LNG기업)"),
            # 거시
            ("DX=F",   "달러인덱스"),
            ("^TNX",   "미국10년채수익률"),
        ]

        raw = {}   # ticker → dict
        for ticker, label in OVERSEAS:
            try:
                hist   = yf.Ticker(ticker).history(period="30d")
                hist1y = yf.Ticker(ticker).history(period="252d")
                if hist.empty:
                    raw[ticker] = {"표시명": label, "오류": "데이터 없음"}
                    continue

                cur    = hist["Close"].iloc[-1]
                prev   = hist["Close"].iloc[-2] if len(hist) > 1 else cur
                w1_ago = hist["Close"].iloc[-6]  if len(hist) >= 6  else hist["Close"].iloc[0]
                m1_ago = hist["Close"].iloc[-22] if len(hist) >= 22 else hist["Close"].iloc[0]
                high52 = hist1y["High"].max() if not hist1y.empty else cur
                low52  = hist1y["Low"].min()  if not hist1y.empty else cur

                raw[ticker] = {
                    "표시명":          label,
                    "현재가":          round(cur, 2),
                    "전일대비(%)":     round((cur - prev)   / prev   * 100, 2),
                    "1주대비(%)":      round((cur - w1_ago) / w1_ago * 100, 2),
                    "1개월대비(%)":    round((cur - m1_ago) / m1_ago * 100, 2),
                    "52주고점대비(%)": round((cur - high52) / high52 * 100, 1),
                    "52주저점대비(%)": round((cur - low52)  / low52  * 100, 1),
                }
            except Exception as e:
                raw[ticker] = {"표시명": label, "오류": str(e)}

        # 섹터별 그룹화
        SECTOR_GROUPS = {
            "반도체/AI인프라":  ["NVDA", "TSM", "ASML", "SOXX", "AMAT"],
            "배터리/전기차":    ["TSLA", "LIT", "STLA"],
            "자동차":           ["GM", "F"],
            "바이오/제약":      ["XBI", "IBB", "AMGN", "PFE"],
            "AI/인터넷플랫폼":  ["META", "GOOGL", "MSFT"],
            "방산/항공":        ["LMT", "NOC", "RTX", "BA"],
            "원자재/에너지":    ["HG=F", "LNG"],
            "거시(금리/달러)":  ["DX=F", "^TNX"],
        }

        sectors: dict = {}
        for sector, tickers in SECTOR_GROUPS.items():
            sectors[sector] = {t: raw[t] for t in tickers if t in raw and "오류" not in raw[t]}

        result = {"원본": raw, "섹터별": sectors}
        self.collected_data["overseas"] = result

        ok_cnt = sum(1 for v in raw.values() if "오류" not in v)
        print(f"  ✓ 해외 지표 {ok_cnt}/{len(OVERSEAS)}개 수집 완료")
        return result

    # ──────────────────────────────────────────────
    # 6. Claude 종합 분석 (모든 레이어 통합)
    # ──────────────────────────────────────────────
    def ask_claude_for_advice(self, all_data: Optional[dict] = None) -> dict:
        print("\n🤖 Claude에게 투자 의견 요청 중 (전 레이어 통합)...")

        data = all_data or self.collected_data
        if not data:
            return {"오류": "분석 데이터 없음"}

        # ── 거시 요약 ──
        macro = data.get("macro", {})
        macro_lines = []
        for k, v in macro.items():
            if "오류" in v:
                continue
            cur = v.get("현재가") or v.get("현재값", "?")
            chg = v.get("전일대비(%)", "")
            chg_str = f"  ({chg:+.2f}%)" if isinstance(chg, (int, float)) else ""
            macro_lines.append(f"  {k}: {cur}{chg_str}")
        macro_block = "\n".join(macro_lines)

        # ── 뉴스 감성 ──
        news_block = data.get("news_sentiment", {}).get("Claude분석", "뉴스 데이터 없음")

        # ── 해외 섹터 블록 ──
        overseas = data.get("overseas", {})
        raw_ov   = overseas.get("원본", {})
        sectors  = overseas.get("섹터별", {})

        overseas_block = ""
        for sector, items in sectors.items():
            if not items:
                continue
            overseas_block += f"\n  [{sector}]\n"
            for ticker, v in items.items():
                overseas_block += (
                    f"    {v['표시명']:22s} "
                    f"전일{v.get('전일대비(%)','?'):+.1f}%  "
                    f"1주{v.get('1주대비(%)','?'):+.1f}%  "
                    f"1개월{v.get('1개월대비(%)','?'):+.1f}%  "
                    f"52주고점대비{v.get('52주고점대비(%)','?'):+.1f}%\n"
                )

        # ── 종목별 블록 생성 ──
        liquidity = data.get("liquidity", {})
        dart      = data.get("dart", {})

        stocks_block = ""
        for ticker, liq in liquidity.items():
            if "오류" in liq:
                continue
            code = ticker.replace(".KS", "").replace(".KQ", "")
            name = liq.get("종목명", ticker)

            # 기술적 지표 블록
            tech = (
                f"  현재가: {liq['현재가']:,.0f}원  전일대비: {liq['전일대비(%)']:+.2f}%\n"
                f"  [이동평균]  MA5={liq['MA5']:,.0f}  MA20={liq['MA20']:,.0f}  MA60={liq['MA60']:,.0f}\n"
                f"              정배열={liq['MA정배열']}  골든크로스={liq['골든크로스']}\n"
                f"  [RSI/MACD]  RSI={liq['RSI(14)']}({liq['RSI신호']})  "
                f"MACD={liq['MACD선']}  시그널={liq['시그널선']}  히스토={liq['MACD히스토그램']}  MACD>시그널={liq['MACD>시그널']}\n"
                f"  [볼린저밴드] 위치={liq['BB위치(%)']}%({liq['BB신호']})  상단={liq['BB상단']:,.0f}  하단={liq['BB하단']:,.0f}\n"
                f"  [지지/저항]  근접저항={liq['근접저항선']:,.0f}  근접지지={liq['근접지지선']:,.0f}\n"
                f"              피봇R2={liq['피봇R2']:,.0f}  R1={liq['피봇R1']:,.0f}  "
                f"P={liq['피봇']:,.0f}  S1={liq['피봇S1']:,.0f}  S2={liq['피봇S2']:,.0f}\n"
                f"  [거래량]    20일평균대비={liq['거래량비율(vs20일)']}배\n"
                f"  [52주]      고점대비={liq['52주고점대비(%)']}%  "
                f"최고={liq['52주최고']:,.0f}  최저={liq['52주최저']:,.0f}\n"
                f"  [밸류에이션] PER={liq.get('PER','N/A')}  "
                f"PBR={liq.get('PBR','N/A')}  배당={liq.get('배당수익률(%)', 'N/A')}%"
            )

            # DART 재무 블록
            dart_part = ""
            if code in dart:
                d   = dart[code]
                fin = d.get("재무제표", {})
                qtr = d.get("분기실적", [])
                imp = d.get("중요공시", [])
                if "오류" not in fin and fin:
                    dart_part += (
                        f"\n  [DART 연간재무 - {fin.get('기준연도')}년]\n"
                        f"    매출={fin.get('매출액_억',0):,.0f}억  "
                        f"영업이익={fin.get('영업이익_억',0):,.0f}억  "
                        f"순이익={fin.get('당기순이익_억',0):,.0f}억\n"
                        f"    영업이익률={fin.get('영업이익률(%)','?')}%  "
                        f"부채비율={fin.get('부채비율(%)','?')}%"
                    )
                if qtr:
                    dart_part += "\n  [분기실적 추세]"
                    for q in qtr[:4]:
                        dart_part += (
                            f"\n    {q['연도']} {q['보고서'][:5]}: "
                            f"매출 {q['매출액(억)']:,.0f}억  "
                            f"영업이익 {q['영업이익(억)']:,.0f}억  "
                            f"이익률 {q['영업이익률(%)']}%"
                        )
                if imp:
                    dart_part += "\n  [중요공시 ★]"
                    for it in imp[:3]:
                        dart_part += f"\n    {it['접수일']}  {it['제목']}"

            # 종목별 연관 해외 지표 블록
            ov_map  = _OVERSEAS_MAP.get(code, {})
            ov_tickers = ov_map.get("tickers", [])
            ov_memo    = ov_map.get("memo", "")
            ov_part = ""
            if ov_tickers:
                ov_part += f"\n  [연관 해외지표 — {ov_memo}]"
                for ot in ov_tickers:
                    if ot in raw_ov and "오류" not in raw_ov[ot]:
                        v = raw_ov[ot]
                        ov_part += (
                            f"\n    {v['표시명']:22s} "
                            f"전일{v.get('전일대비(%)','?'):+.1f}%  "
                            f"1주{v.get('1주대비(%)','?'):+.1f}%  "
                            f"1개월{v.get('1개월대비(%)','?'):+.1f}%  "
                            f"52주고점대비{v.get('52주고점대비(%)','?'):+.1f}%"
                        )

            stocks_block += (
                f"\n{'═'*65}\n"
                f"[{name} / {code}]\n"
                f"{tech}"
                f"{dart_part}"
                f"{ov_part}\n"
            )

        # ── 최종 프롬프트 ──
        prompt = f"""당신은 한국 주식시장 전문 분석가입니다.
아래 5개 레이어의 데이터를 종합해 종목별 투자 의견을 제시하세요.

레이어①: 거시경제 지표
{macro_block}

레이어②: 시장 뉴스 감성
{news_block}

레이어③: 해외 섹터별 지표 (글로벌 모멘텀 파악)
{overseas_block}

레이어④⑤: 종목별 기술적 지표 + DART 재무/공시 + 연관 해외지표
{stocks_block}

─────────────────────────────────────
【분석 지침】
각 종목에 대해 다음 형식으로 작성하세요.

[종목명 / 코드]
- 투자의견: 매수 / 관망 / 매도
- 신뢰도: 높음 / 중간 / 낮음
- 핵심 근거 (반드시 아래 3가지를 근거로 명시):
  · 해외지표: 연관 해외주식·ETF 동향이 국내 종목에 미치는 영향
  · 기술적: RSI·MACD·볼린저밴드·이동평균·지지/저항선 종합
  · 재무적: DART 영업이익률 추세·부채비율·PER 밸류에이션
- 리스크: (1-2줄)
- 매수 전략: (신규 진입 가격대 또는 전략)
- 적정 비중: X%

【종합 판단】
- 현재 시장 국면 (1줄):
- 섹터별 선호 순위 (표):
- 핵심 투자 전략 (3줄):
- 추천 포트폴리오 배분표 (매수 종목 위주):

⚠️ 본 분석은 참고용이며 최종 투자 결정은 투자자 본인 책임입니다."""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            advice_text = response.content[0].text
        except Exception as e:
            advice_text = f"Claude API 오류: {e}"

        advice = {
            "분석시각":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Claude의견": advice_text,
        }
        self.collected_data["advice"] = advice
        print("  ✓ Claude 분석 완료")
        return advice

    # ──────────────────────────────────────────────
    # 7. 주문 실행 (사용자 최종 승인 필수)
    # ──────────────────────────────────────────────
    def execute_trade(self, decision: dict) -> dict:
        ticker      = decision.get("ticker", "")
        action      = decision.get("action", "")
        quantity    = decision.get("quantity", 0)
        order_type  = decision.get("order_type", "market")
        limit_price = decision.get("limit_price")

        action_kr    = "매수" if action == "buy" else "매도"
        order_type_kr = "시장가" if order_type == "market" else f"지정가({limit_price:,}원)"

        print("\n" + "=" * 50)
        print("⚠️  주문 실행 최종 확인")
        print("=" * 50)
        print(f"  종목코드 : {ticker}")
        print(f"  주문유형 : {action_kr}")
        print(f"  수량     : {quantity:,}주")
        print(f"  주문방식 : {order_type_kr}")
        print("=" * 50)
        confirm = input("정말 주문을 실행하시겠습니까? (yes 입력 시 실행): ").strip().lower()

        if confirm != "yes":
            return {"상태": "취소", "사유": "사용자 취소"}

        app_key    = _get("KIS_APP_KEY")
        app_secret = _get("KIS_APP_SECRET")
        account_no = _get("KIS_ACCOUNT_NO")

        if not all([app_key, app_secret, account_no]):
            return {
                "상태": "시뮬레이션",
                "메시지": f"[모의] {ticker} {action_kr} {quantity}주 {order_type_kr}",
            }

        try:
            return self._kis_place_order(
                app_key, app_secret, account_no,
                ticker, action, quantity, order_type, limit_price
            )
        except Exception as e:
            return {"상태": "오류", "사유": str(e)}

    def _kis_place_order(self, app_key, app_secret, account_no,
                         ticker, action, quantity, order_type, limit_price):
        token_resp = requests.post(
            "https://openapi.koreainvestment.com:9443/oauth2/tokenP",
            json={"grant_type": "client_credentials",
                  "appkey": app_key, "appsecret": app_secret},
            timeout=10,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appkey": app_key, "appsecret": app_secret,
            "tr_id": "TTTC0802U" if action == "buy" else "TTTC0801U",
        }
        body = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:] if len(account_no) > 8 else "01",
            "PDNO": ticker,
            "ORD_DVSN": "01" if order_type == "market" else "00",
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(limit_price or 0),
        }
        resp = requests.post(
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/trading/order-cash",
            headers=headers, json=body, timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("rt_cd") == "0":
            return {"상태": "성공", "주문번호": result.get("output", {}).get("ODNO")}
        return {"상태": "실패", "사유": result.get("msg1")}

    # ──────────────────────────────────────────────
    # 전체 분석 실행
    # ──────────────────────────────────────────────
    def run_full_analysis(self) -> dict:
        """
        5개 레이어 순차 실행:
          거시경제 → 뉴스 → 기술적지표(피봇포함) → DART → 해외섹터 → Claude 종합
        """
        print("\n" + "=" * 65)
        print("🚀 주식 어드바이저 (해외지표 통합판) 시작")
        print(f"   분석 종목: {', '.join(self.target_stocks)}")
        print(f"   실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 65 + "\n")

        self.collect_macro_data()          # 레이어①
        self.analyze_news_sentiment()      # 레이어②
        self.check_market_liquidity()      # 레이어③ (기술적 + 피봇)
        self.collect_dart_data()           # 레이어④ (DART 재무/공시)
        self.collect_overseas_data()       # 레이어⑤ (해외 섹터)
        advice = self.ask_claude_for_advice()  # Claude 종합 분석

        print("\n" + "=" * 65)
        print("📋 Claude 투자 의견 (5-레이어 통합 분석)")
        print("=" * 65)
        print(advice.get("Claude의견", "분석 결과 없음"))
        print("=" * 65)
        print("⚠️  본 분석은 참고용입니다. 투자 결정은 본인 책임입니다.")

        return self.collected_data


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    advisor = StockAdvisorSystem()   # .env의 TARGET_STOCKS (16개 전 종목)
    result  = advisor.run_full_analysis()

    output_path = f"analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 분석 결과 저장: {output_path}")
