"""
지정학 리스크 엔진 (Geopolitical Risk Engine)
─────────────────────────────────────────────
전쟁·지정학 이벤트에 따른 섹터별 차등 점수 보정 및
급락 후 V자 반등(crash recovery) 시그널 감지.

통합 지점: stock_advisor_v4.py  ③-b → ③-c(GRI) → ③-d(recovery)
"""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 1. 섹터 분류 테이블
# ═══════════════════════════════════════════════════════════════

SECTOR_TAGS: dict[str, str] = {
    # ── 방산 (KR) ─────────────────────────────────────────────
    "012450.KS": "defense",  # 한화에어로스페이스
    "079550.KS": "defense",  # LIG넥스원
    "047810.KS": "defense",  # 한국항공우주
    "064350.KS": "defense",  # 현대로템
    "103140.KS": "defense",  # 풍산
    "272210.KS": "defense",  # 한화시스템
    "034020.KS": "defense",  # 두산에너빌리티
    "329180.KS": "defense",  # HD현대중공업
    "214430.KQ": "defense",  # 아이쓰리시스템
    "274090.KQ": "defense",  # 켄코아에어로스페이스
    "065150.KQ": "defense",  # 빅텍
    "013810.KQ": "defense",  # 스페코
    "010820.KQ": "defense",  # 퍼스텍
    "099440.KQ": "defense",  # 쎄트렉아이
    "462350.KQ": "defense",  # 이노스페이스
    "083650.KQ": "defense",  # 비에이치아이
    # ── 방산 (US) ─────────────────────────────────────────────
    "LMT": "defense",  "RTX": "defense",  "NOC": "defense",
    "GD":  "defense",  "BA":  "defense",  "HII": "defense",
    "LDOS": "defense", "LHX": "defense",
    # ── 에너지·정유 ───────────────────────────────────────────
    "XOM": "energy",  "CVX": "energy",  "COP": "energy",
    "OXY": "energy",  "DVN": "energy",  "FANG": "energy",
    "VLO": "energy",  "PSX": "energy",  "HAL": "energy",
    "SLB": "energy",  "EOG": "energy",  "BP":  "energy",
    "096770.KS": "energy",  # SK이노베이션
    "010950.KS": "energy",  # S-Oil
    "267260.KS": "energy",  # HD현대일렉트릭
    "010120.KS": "energy",  # LS일렉트릭
    "298040.KS": "energy",  # 효성중공업
    "015760.KS": "energy",  # 한국전력
    "NEE": "energy",
    # ── 금·안전자산 ───────────────────────────────────────────
    "GLD": "gold",  "IAU": "gold",  "SLV": "gold",
    "NEM": "gold",  "GOLD": "gold",  "AEM": "gold",
    # ── 테크 ──────────────────────────────────────────────────
    "AAPL": "tech",  "NVDA": "tech",  "MSFT": "tech",
    "GOOGL": "tech", "AMZN": "tech",  "META": "tech",
    "TSLA": "tech",  "AVGO": "tech",  "AMD":  "tech",
    "TSM": "tech",   "NFLX": "tech",  "CRM":  "tech",
    "ORCL": "tech",  "ADBE": "tech",  "QCOM": "tech",
    "INTC": "tech",  "MU":   "tech",  "AMAT": "tech",
    "LRCX": "tech",  "KLAC": "tech",  "PANW": "tech",
    "CRWD": "tech",  "SNOW": "tech",  "PLTR": "tech",
    "DDOG": "tech",  "NOW":  "tech",  "WDAY": "tech",
    "005930.KS": "tech",  # 삼성전자
    "000660.KS": "tech",  # SK하이닉스
    "035420.KS": "tech",  # NAVER
    "035720.KS": "tech",  # 카카오
    "009150.KS": "tech",  # 삼성전기
    "011070.KS": "tech",  # LG이노텍
    "042700.KS": "tech",  # 한미반도체
    # ── 소비재 ────────────────────────────────────────────────
    "WMT": "consumer",  "COST": "consumer",  "NKE": "consumer",
    "SBUX": "consumer", "DIS":  "consumer",  "MCD": "consumer",
    "090430.KS": "consumer",  # 아모레퍼시픽
    "051900.KS": "consumer",  # LG생활건강
    "097950.KS": "consumer",  # CJ제일제당
    "271560.KS": "consumer",  # 오리온
    # ── 항공·운송 ─────────────────────────────────────────────
    "003490.KS": "transport",  # 대한항공
    "086280.KS": "transport",  # 현대글로비스
    "011200.KS": "transport",  # HMM
    "UBER": "transport",  "ABNB": "transport",  "BKNG": "transport",
    # ── 금융 ──────────────────────────────────────────────────
    "JPM": "finance",  "GS": "finance",  "MS": "finance",
    "105560.KS": "finance",  # KB금융
    "055550.KS": "finance",  # 신한지주
    "086790.KS": "finance",  # 하나금융지주
    "032830.KS": "finance",  # 삼성생명
    "000810.KS": "finance",  # 삼성화재
    # ── 바이오 ────────────────────────────────────────────────
    "LLY": "bio",  "UNH": "bio",  "JNJ": "bio",  "PFE": "bio",
    "MRNA": "bio", "NVO": "bio",
    "207940.KS": "bio",  # 삼성바이오로직스
    "068270.KS": "bio",  # 셀트리온
}

# ═══════════════════════════════════════════════════════════════
# 2. 섹터별 보정 매트릭스
# ═══════════════════════════════════════════════════════════════

SECTOR_ADJUSTMENT_MATRIX: dict[str, dict[str, int]] = {
    "high_escalation": {
        "defense": +12, "energy": +8, "gold": +10,
        "tech": -6, "consumer": -8, "transport": -10,
        "finance": -3, "bio": -2, "default": -5,
    },
    "moderate_escalation": {
        "defense": +6, "energy": +4, "gold": +5,
        "tech": -3, "consumer": -4, "transport": -5,
        "finance": -1, "bio": -1, "default": -2,
    },
    "de_escalation": {
        "defense": -5, "energy": -3, "gold": -4,
        "tech": +5, "consumer": +6, "transport": +4,
        "finance": +3, "bio": +2, "default": +3,
    },
    "neutral": {
        "defense": 0, "energy": 0, "gold": 0,
        "tech": 0, "consumer": 0, "transport": 0,
        "finance": 0, "bio": 0, "default": 0,
    },
}

# ═══════════════════════════════════════════════════════════════
# 3. 전쟁 수혜주 워치리스트
# ═══════════════════════════════════════════════════════════════

WAR_BENEFICIARY_LIST: list[dict] = [
    # 방산
    {"name": "한화에어로스페이스", "ticker": "012450.KS", "sector": "defense",
     "reason": "방산 대장주, K-방산 수출 확대 수혜"},
    {"name": "LIG넥스원", "ticker": "079550.KS", "sector": "defense",
     "reason": "미사일·유도무기 전문, 전쟁 시 수주 급증"},
    {"name": "한국항공우주", "ticker": "047810.KS", "sector": "defense",
     "reason": "KF-21 전투기, 수출 계약 확대"},
    {"name": "현대로템", "ticker": "064350.KS", "sector": "defense",
     "reason": "K2 전차, 폴란드 등 수출 호조"},
    {"name": "풍산", "ticker": "103140.KS", "sector": "defense",
     "reason": "탄약 제조, 전쟁 시 직접 수혜"},
    {"name": "Lockheed Martin", "ticker": "LMT", "sector": "defense",
     "reason": "미국 방산 1위, F-35·미사일 체계"},
    {"name": "RTX (Raytheon)", "ticker": "RTX", "sector": "defense",
     "reason": "패트리어트 미사일, 중동 분쟁 직접 수혜"},
    {"name": "Northrop Grumman", "ticker": "NOC", "sector": "defense",
     "reason": "B-21 스텔스 폭격기, 장거리 무기체계"},
    # 에너지
    {"name": "Exxon Mobil", "ticker": "XOM", "sector": "energy",
     "reason": "유가 상승 시 수익 직접 증가"},
    {"name": "Chevron", "ticker": "CVX", "sector": "energy",
     "reason": "통합 에너지, 유가 수혜"},
    {"name": "SK이노베이션", "ticker": "096770.KS", "sector": "energy",
     "reason": "정유·배터리, 유가 상승 수혜"},
    # 금·안전자산
    {"name": "GLD (금ETF)", "ticker": "GLD", "sector": "gold",
     "reason": "전쟁 시 안전자산 수요 급증"},
    {"name": "Newmont", "ticker": "NEM", "sector": "gold",
     "reason": "세계 최대 금광기업, 금가 상승 수혜"},
]


# ═══════════════════════════════════════════════════════════════
# 4. 핵심 함수
# ═══════════════════════════════════════════════════════════════

def classify_stock_sector(ticker: str, name: str = "") -> str:
    """종목의 지정학 민감도 섹터를 분류한다."""
    if ticker in SECTOR_TAGS:
        return SECTOR_TAGS[ticker]
    base = ticker.split(".")[0].upper()
    if base in SECTOR_TAGS:
        return SECTOR_TAGS[base]
    # 이름 기반 fallback
    name_lower = name.lower() if name else ""
    if any(kw in name_lower for kw in ["방산", "defense", "군", "미사일", "전투"]):
        return "defense"
    if any(kw in name_lower for kw in ["에너지", "석유", "정유", "oil", "energy"]):
        return "energy"
    if any(kw in name_lower for kw in ["금", "gold", "귀금속"]):
        return "gold"
    if any(kw in name_lower for kw in ["항공", "운송", "airline", "transport"]):
        return "transport"
    return "default"


def compute_geopolitical_risk_index(
    macro: dict,
    sector_flows: dict,
) -> dict:
    """
    지정학 리스크 인덱스(GRI) 산출 (0~100).

    5개 컴포넌트:
      1) 유가 변동성 (WTI 5일 절대 변동)
      2) 금 급등 (안전자산 수요)
      3) VIX 급등 패턴
      4) 방산 ETF 상대강도 (ITA vs SPY)
      5) 달러 강세 (DXY)
    """
    components = {}
    score = 0

    # ── 1) 유가 변동성 (0~25) ────────────────────────────────
    wti = macro.get("WTI유가", {})
    wti_chg = abs(wti.get("등락(%)", 0))
    if wti_chg > 8:
        oil_score = 25
    elif wti_chg > 5:
        oil_score = 15
    elif wti_chg > 3:
        oil_score = 8
    else:
        oil_score = 0
    components["oil_volatility"] = {"change_pct": wti_chg, "score": oil_score}
    score += oil_score

    # ── 2) 금 급등 (0~20) ─────────────────────────────────────
    gold = macro.get("금(Gold)", {})
    gold_chg = gold.get("등락(%)", 0)
    if gold_chg > 3:
        gold_score = 20
    elif gold_chg > 1.5:
        gold_score = 10
    elif gold_chg > 0.5:
        gold_score = 4
    else:
        gold_score = 0
    components["gold_surge"] = {"change_pct": gold_chg, "score": gold_score}
    score += gold_score

    # ── 3) VIX 급등 패턴 (0~30) ──────────────────────────────
    vix_cur = macro.get("VIX", {}).get("현재", 20)
    vix_chg = macro.get("VIX", {}).get("등락(%)", 0)
    if vix_cur > 35:
        vix_score = 25
    elif vix_cur > 30:
        vix_score = 18
    elif vix_cur > 25:
        vix_score = 10
    elif vix_cur > 20:
        vix_score = 4
    else:
        vix_score = 0
    # 급등 보너스: 5일 내 30%+ 급등
    if vix_chg > 30:
        vix_score = min(vix_score + 5, 30)
    components["vix_spike"] = {"current": vix_cur, "change_pct": vix_chg, "score": vix_score}
    score += vix_score

    # ── 4) 방산 ETF 상대강도 (0~15) ──────────────────────────
    defense_rs = 0
    try:
        ita = yf.Ticker("ITA").history(period="10d")
        spy = yf.Ticker("SPY").history(period="10d")
        if len(ita) >= 6 and len(spy) >= 6:
            # 5거래일 수익률: iloc[-6] → iloc[-1] (6개 데이터포인트 = 5일 변화)
            ita_ret = (ita["Close"].iloc[-1] / ita["Close"].iloc[-6] - 1) * 100
            spy_ret = (spy["Close"].iloc[-1] / spy["Close"].iloc[-6] - 1) * 100
        elif len(ita) >= 2 and len(spy) >= 2:
            ita_ret = (ita["Close"].iloc[-1] / ita["Close"].iloc[0] - 1) * 100
            spy_ret = (spy["Close"].iloc[-1] / spy["Close"].iloc[0] - 1) * 100
            defense_rs = ita_ret - spy_ret
    except Exception as e:
        logger.warning(f"[GRI] ITA/SPY 조회 실패: {e}")
    if defense_rs > 3:
        def_score = 15
    elif defense_rs > 1.5:
        def_score = 8
    elif defense_rs > 0:
        def_score = 3
    else:
        def_score = 0
    components["defense_relative_strength"] = {"ita_vs_spy_pct": round(defense_rs, 2), "score": def_score}
    score += def_score

    # ── 5) 달러 강세 (0~15) ──────────────────────────────────
    dxy = macro.get("달러인덱스", {})
    dxy_chg = abs(dxy.get("등락(%)", 0))
    if dxy_chg > 2:
        dxy_score = 15
    elif dxy_chg > 1:
        dxy_score = 8
    elif dxy_chg > 0.5:
        dxy_score = 3
    else:
        dxy_score = 0
    components["usd_strength"] = {"change_pct": dxy_chg, "score": dxy_score}
    score += dxy_score

    # ── 레벨 판정 ─────────────────────────────────────────────
    if score >= 60:
        level = "high_escalation"
    elif score >= 35:
        level = "moderate_escalation"
    elif score < 15:
        level = "de_escalation"
    else:
        level = "neutral"

    sector_adj = SECTOR_ADJUSTMENT_MATRIX[level]

    return {
        "gri_score": score,
        "gri_level": level,
        "gri_label": {
            "high_escalation": "고위험 (전쟁 격화)",
            "moderate_escalation": "경계 (긴장 고조)",
            "de_escalation": "완화 (긴장 해소)",
            "neutral": "중립",
        }[level],
        "components": components,
        "sector_adjustments": sector_adj,
    }


def compute_crash_recovery_signal(
    macro: dict,
    fear_greed: dict,
) -> dict:
    """
    급락 후 V자 반등 시그널 감지.

    4개 시그널:
      1) VIX 평균회귀 — 10일 피크 대비 15%+ 하락
      2) 공포 지속 소진 — F&G < 20 연속 후 반등
      3) 과매도 폭 반전 — S&P500 10일 내 -5% 후 저점 대비 +2% 회복
      4) 거래량 항복 — 대량 매도 후 저거래량 회복
    """
    signals_fired = []

    # VIX 30일 + S&P500 30일 히스토리
    try:
        vix_hist = yf.Ticker("^VIX").history(period="1mo")
        spx_hist = yf.Ticker("^GSPC").history(period="1mo")
    except Exception as e:
        logger.warning(f"[Recovery] VIX/SPX 히스토리 조회 실패: {e}")
        return {"recovery_active": False, "recovery_strength": 0,
                "signals_fired": [], "recovery_adjustment": 0}

    # ── 1) VIX 평균회귀 ──────────────────────────────────────
    if len(vix_hist) >= 10:
        recent_vix = vix_hist["Close"].iloc[-10:]
        vix_peak = recent_vix.max()
        vix_now = recent_vix.iloc[-1]
        if vix_peak > 25 and vix_now < vix_peak * 0.85:
            signals_fired.append("vix_mean_reversion")
            logger.info(f"[Recovery] VIX 평균회귀: 피크 {vix_peak:.1f} → 현재 {vix_now:.1f}")

    # ── 2) 공포 지속 소진 ────────────────────────────────────
    fg_val = fear_greed.get("지수", 50) if fear_greed else 50
    fg_prev = fear_greed.get("전일", fg_val) if fear_greed else fg_val
    fg_prev_week = fear_greed.get("지난주", fg_val) if fear_greed else fg_val
    # 전일·지난주 모두 < 20 이었고 현재 반등 중이면
    if fg_prev < 20 and fg_prev_week < 25 and fg_val > fg_prev:
        signals_fired.append("fear_exhaustion")
        logger.info(f"[Recovery] 공포 소진: 전일={fg_prev}, 지난주={fg_prev_week}, 현재={fg_val}")

    # ── 3) 과매도 폭 반전 ────────────────────────────────────
    if len(spx_hist) >= 10:
        spx_close = spx_hist["Close"].iloc[-10:]
        spx_high = spx_close.max()
        spx_low = spx_close.min()
        spx_now = spx_close.iloc[-1]
        drawdown = (spx_low / spx_high - 1) * 100
        recovery_from_low = (spx_now / spx_low - 1) * 100
        if drawdown < -5 and recovery_from_low > 2:
            signals_fired.append("oversold_breadth_reversal")
            logger.info(f"[Recovery] 과매도 반전: 낙폭 {drawdown:.1f}%, 저점 대비 반등 {recovery_from_low:.1f}%")

    # ── 4) 거래량 항복 ───────────────────────────────────────
    if len(spx_hist) >= 5:
        vol = spx_hist["Volume"].iloc[-5:]
        close = spx_hist["Close"].iloc[-5:]
        avg_vol = spx_hist["Volume"].iloc[:-5].mean() if len(spx_hist) > 5 else vol.mean()
        if avg_vol > 0:
            for i in range(len(vol) - 1):
                day_ret = (close.iloc[i + 1] / close.iloc[i] - 1) * 100 if close.iloc[i] > 0 else 0
                # 대량 매도일: 평균 2배 거래량 + 2% 이상 하락
                if vol.iloc[i] > avg_vol * 2 and day_ret < -2:
                    # 다음 날 거래량 감소 + 반등
                    if i + 1 < len(vol) - 1:
                        next_ret = (close.iloc[i + 2] / close.iloc[i + 1] - 1) * 100 if close.iloc[i + 1] > 0 else 0
                        if vol.iloc[i + 1] < vol.iloc[i] and next_ret > 0:
                            if "volume_capitulation" not in signals_fired:
                                signals_fired.append("volume_capitulation")
                                logger.info("[Recovery] 거래량 항복 감지")

    strength = len(signals_fired)
    recovery_adj = min(strength * 2, 8)

    return {
        "recovery_active": strength >= 2,
        "recovery_strength": strength,
        "signals_fired": signals_fired,
        "recovery_adjustment": recovery_adj if strength >= 2 else 0,
    }


def apply_sector_differential_adjustment(
    all_results: dict,
    gri: dict,
    recovery: dict,
    base_adj: int,
) -> None:
    """
    기존 균일 보정(base_adj)에 섹터별 차등 보정 + 리커버리 보너스를 적용.
    각 종목의 score를 in-place 수정한다.
    """
    sector_adj_map = gri.get("sector_adjustments", {})
    recovery_bonus = recovery.get("recovery_adjustment", 0)
    counts: dict[str, int] = {}

    for market in all_results:
        for r in all_results[market]:
            sector = classify_stock_sector(r["ticker"], r.get("name", ""))
            sector_delta = sector_adj_map.get(sector, sector_adj_map.get("default", 0))
            total_adj = base_adj + sector_delta + recovery_bonus
            r["score"] = r["score"] + total_adj
            r["_geo_sector"] = sector
            r["_geo_adj"] = sector_delta
            r["_recovery_adj"] = recovery_bonus
            counts[sector] = counts.get(sector, 0) + 1
        all_results[market].sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"[GRI] 섹터별 차등 보정 완료: {counts}")


def get_war_beneficiary_watchlist(gri: dict) -> list[dict]:
    """GRI >= 35일 때 전쟁 수혜주 워치리스트 반환."""
    if gri.get("gri_score", 0) < 35:
        return []
    return WAR_BENEFICIARY_LIST


def format_gri_summary(gri: dict, recovery: dict) -> str:
    """리포트용 GRI + 리커버리 요약 텍스트 생성."""
    lines = []
    lines.append(f"  지정학 리스크(GRI): {gri['gri_score']}/100 [{gri['gri_label']}]")

    comps = gri.get("components", {})
    details = []
    if comps.get("oil_volatility", {}).get("score", 0) > 0:
        c = comps["oil_volatility"]
        details.append(f"유가변동 {c['change_pct']:.1f}%({c['score']}점)")
    if comps.get("gold_surge", {}).get("score", 0) > 0:
        c = comps["gold_surge"]
        details.append(f"금급등 {c['change_pct']:+.1f}%({c['score']}점)")
    if comps.get("vix_spike", {}).get("score", 0) > 0:
        c = comps["vix_spike"]
        details.append(f"VIX {c['current']:.0f}({c['score']}점)")
    if comps.get("defense_relative_strength", {}).get("score", 0) > 0:
        c = comps["defense_relative_strength"]
        details.append(f"방산RS {c['ita_vs_spy_pct']:+.1f}%({c['score']}점)")
    if comps.get("usd_strength", {}).get("score", 0) > 0:
        c = comps["usd_strength"]
        details.append(f"달러 {c['change_pct']:.1f}%({c['score']}점)")
    if details:
        lines.append(f"    구성: {' | '.join(details)}")

    # 섹터별 보정
    adj = gri.get("sector_adjustments", {})
    adj_parts = [f"{k}:{v:+d}" for k, v in adj.items() if k != "default" and v != 0]
    if adj_parts:
        lines.append(f"    섹터보정: {' / '.join(adj_parts)}")

    if recovery.get("recovery_active"):
        sig = ", ".join(recovery["signals_fired"])
        lines.append(f"  급락반등 시그널: {sig} → 전종목 +{recovery['recovery_adjustment']}점")
    elif recovery.get("signals_fired"):
        sig = ", ".join(recovery["signals_fired"])
        lines.append(f"  반등 징후(약): {sig} (2개 미만, 보너스 미적용)")

    return "\n".join(lines)


def format_gri_for_claude(gri: dict, recovery: dict, war_watchlist: list) -> str:
    """Claude 프롬프트에 추가할 GRI 컨텍스트 텍스트."""
    parts = [f"GRI:{gri['gri_score']}/100({gri['gri_label']})"]

    adj = gri.get("sector_adjustments", {})
    adj_parts = [f"{k}:{v:+d}" for k, v in adj.items() if k != "default" and v != 0]
    if adj_parts:
        parts.append(f"섹터보정({'/'.join(adj_parts)})")

    if recovery.get("recovery_active"):
        parts.append(f"반등시그널:{','.join(recovery['signals_fired'])}→+{recovery['recovery_adjustment']}")

    if war_watchlist:
        tickers = [w["ticker"] for w in war_watchlist[:5]]
        parts.append(f"전쟁수혜주:{'/'.join(tickers)}")

    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 5. 단독 실행 (테스트)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("=" * 60)
    print("  Geopolitical Risk Engine - 단독 테스트")
    print("=" * 60)

    # 간이 macro 데이터 수집
    tickers = {
        "WTI유가": "CL=F", "금(Gold)": "GC=F", "VIX": "^VIX",
        "달러인덱스": "DX=F", "S&P500": "^GSPC",
    }
    macro = {}
    for label, sym in tickers.items():
        try:
            hist = yf.Ticker(sym).history(period="10d")
            if len(hist) >= 2:
                cur = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[0]
                chg = (cur / prev - 1) * 100
                macro[label] = {"현재": round(cur, 2), "등락(%)": round(chg, 2)}
            else:
                macro[label] = {"현재": 0, "등락(%)": 0}
        except Exception:
            macro[label] = {"현재": 0, "등락(%)": 0}

    print("\n[수집된 거시 데이터]")
    for k, v in macro.items():
        print(f"  {k}: {v['현재']} ({v['등락(%)']:+.1f}%)")

    # GRI 계산
    gri = compute_geopolitical_risk_index(macro, {})
    print(f"\n[GRI] 점수: {gri['gri_score']}/100  레벨: {gri['gri_label']}")
    for comp_name, comp_data in gri["components"].items():
        print(f"  {comp_name}: {comp_data}")
    print(f"  섹터보정: {gri['sector_adjustments']}")

    # 리커버리 시그널
    fg = {"지수": 15, "전일": 18, "지난주": 22}
    recovery = compute_crash_recovery_signal(macro, fg)
    print(f"\n[Recovery] active={recovery['recovery_active']}, "
          f"strength={recovery['recovery_strength']}, "
          f"signals={recovery['signals_fired']}")

    # 요약 출력
    print(f"\n{format_gri_summary(gri, recovery)}")

    # 전쟁 수혜주
    watchlist = get_war_beneficiary_watchlist(gri)
    if watchlist:
        print(f"\n[전쟁 수혜주 워치리스트] ({len(watchlist)}개)")
        for w in watchlist:
            print(f"  {w['name']} ({w['ticker']}) — {w['reason']}")
