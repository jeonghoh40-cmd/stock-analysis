"""
Streamlit 대시보드 v2 — AI 주식 스크리닝 (stock_performance.db 기반)
────────────────────────────────────────────────────────────────────
실행:  streamlit run dashboard.py
접속:  http://localhost:8501

탭 구성:
  📋 오늘의 추천   — v4 최신 매수/매도 (KOSPI·KOSDAQ·US)
  📊 성능 분석     — 기간별 승률·점수구간·최근 HIT/MISS
  🗂️ 히스토리     — 날짜 × 시장 × 신호 조합 조회
  🎯 ARK 추천      — ARK Big Ideas 2026
  ⚠️ Citrini       — 2028 부정적 종목
"""

import os
import sys
import datetime
import sqlite3

import streamlit as st
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

PERF_DB = os.path.join(BASE_DIR, "stock_performance.db")

# ── ARK / Citrini 는 기존 db_manager 유지 ───────────────────────
from db_manager import (
    init_db,
    get_latest_ark_recommended,
    get_ark_performance_summary,
    get_latest_citrini_risky,
    get_citrini_performance_summary,
    get_citrini_by_sector,
)

# ── 페이지 설정 ─────────────────────────────────────────────────
st.set_page_config(
    page_title="AI 주식 스크리닝 v2",
    page_icon="📊",
    layout="wide",
)
init_db()


# ═══════════════════════════════════════════════════════════════
# DB 헬퍼
# ═══════════════════════════════════════════════════════════════

def _perf_conn():
    return sqlite3.connect(PERF_DB)


def _get_latest_date() -> str:
    try:
        conn = _perf_conn()
        cur = conn.cursor()
        cur.execute("SELECT MAX(date) FROM daily_recommendations")
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else ""
    except Exception:
        return ""


def _get_all_dates() -> list:
    try:
        conn = _perf_conn()
        df = pd.read_sql(
            "SELECT DISTINCT date FROM daily_recommendations ORDER BY date DESC",
            conn,
        )
        conn.close()
        return df["date"].tolist()
    except Exception:
        return []


def _get_recommendations(date: str, market: str = "ALL",
                         rec_type: str = "BUY") -> pd.DataFrame:
    try:
        conn = _perf_conn()
        q = """
            SELECT market, recommendation_type as type, rank,
                   name, ticker, score, price, rsi,
                   macd_hist, ma5, ma20, ma60, investor_tags
            FROM daily_recommendations
            WHERE date = ? AND recommendation_type = ?
        """
        params = [date, rec_type]
        if market != "ALL":
            q += " AND market = ?"
            params.append(market)
        q += " ORDER BY market, rank"
        df = pd.read_sql(q, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _get_win_rates() -> dict:
    """기간별 승률 (이상값 ±30% 제외)"""
    OUTLIER = {1: 20, 3: 25, 5: 30, 10: 40, 20: 60}
    result = {}
    try:
        conn = _perf_conn()
        for day in [1, 3, 5, 10, 20]:
            lim = OUTLIER[day]
            row = pd.read_sql(f"""
                SELECT
                  COUNT(*) as cnt,
                  ROUND(SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as buy_wr,
                  ROUND(AVG(p.return_pct),2) as avg_ret
                FROM daily_recommendations r
                JOIN price_tracking p ON r.id=p.recommendation_id AND p.day_after={day}
                WHERE r.recommendation_type='BUY' AND ABS(p.return_pct)<{lim}
            """, conn).iloc[0]
            row_sell = pd.read_sql(f"""
                SELECT
                  COUNT(*) as cnt,
                  ROUND(SUM(CASE WHEN p.return_pct < 0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as sell_wr
                FROM daily_recommendations r
                JOIN price_tracking p ON r.id=p.recommendation_id AND p.day_after={day}
                WHERE r.recommendation_type='SELL' AND ABS(p.return_pct)<{lim}
            """, conn).iloc[0]
            if row["cnt"] > 0:
                result[day] = {
                    "buy_cnt":  int(row["cnt"]),
                    "buy_wr":   float(row["buy_wr"] or 0),
                    "avg_ret":  float(row["avg_ret"] or 0),
                    "sell_cnt": int(row_sell["cnt"]),
                    "sell_wr":  float(row_sell["sell_wr"] or 0),
                }
        conn.close()
    except Exception:
        pass
    return result


def _get_score_win_rate() -> pd.DataFrame:
    """점수 구간별 매수 승률 (5일, ±30% 이내)"""
    try:
        conn = _perf_conn()
        df = pd.read_sql("""
            SELECT
              CASE WHEN r.score >= 60 THEN '60점+'
                   WHEN r.score >= 40 THEN '40~60점'
                   WHEN r.score >= 20 THEN '20~40점'
                   ELSE '20점 미만' END as 점수구간,
              COUNT(*) as 건수,
              ROUND(AVG(p.return_pct),2) as 평균수익률,
              ROUND(SUM(CASE WHEN p.return_pct>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as 승률
            FROM daily_recommendations r
            JOIN price_tracking p ON r.id=p.recommendation_id AND p.day_after=5
            WHERE r.recommendation_type='BUY' AND ABS(p.return_pct)<30
            GROUP BY 점수구간
            ORDER BY 승률 DESC
        """, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _get_market_win_rate() -> pd.DataFrame:
    """시장별 매수 승률 (5일, ±30% 이내)"""
    try:
        conn = _perf_conn()
        df = pd.read_sql("""
            SELECT r.market as 시장,
              COUNT(*) as 건수,
              ROUND(AVG(p.return_pct),2) as 평균수익률,
              ROUND(SUM(CASE WHEN p.return_pct>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as 승률
            FROM daily_recommendations r
            JOIN price_tracking p ON r.id=p.recommendation_id AND p.day_after=5
            WHERE r.recommendation_type='BUY' AND ABS(p.return_pct)<30
            GROUP BY r.market ORDER BY 승률 DESC
        """, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _get_recent_results(limit: int = 30) -> pd.DataFrame:
    """최근 HIT/MISS 결과 (5일 후, ±30% 이내)"""
    try:
        conn = _perf_conn()
        df = pd.read_sql(f"""
            SELECT r.date, r.market, r.ticker, r.name,
                   r.recommendation_type as 신호, r.rank as 순위,
                   r.score as 점수,
                   r.price as 진입가, p.close_price as 청산가,
                   p.return_pct as 수익률
            FROM daily_recommendations r
            JOIN price_tracking p ON r.id=p.recommendation_id AND p.day_after=5
            WHERE r.date >= date('now', '-30 days')
              AND ABS(p.return_pct) < 30
            ORDER BY r.date DESC, r.recommendation_type, r.rank
            LIMIT {limit}
        """, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def _read_market_regime() -> dict:
    """report_v4.txt 에서 시장 레짐 정보 파싱"""
    regime = {"fear_greed": None, "regime": None, "vix": None, "kospi_chg": None}
    try:
        report_path = os.path.join(BASE_DIR, "report_v4.txt")
        if not os.path.exists(report_path):
            return regime
        with open(report_path, encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[:15]:
            if "Fear&Greed:" in line:
                import re
                m = re.search(r"Fear&Greed:\s*(\d+)", line)
                if m:
                    regime["fear_greed"] = int(m.group(1))
            if "시장레짐:" in line:
                m = re.search(r"시장레짐:\s*(\S+)", line)
                if m:
                    regime["regime"] = m.group(1)
            if "VIX" in line:
                m = re.search(r"VIX\s+([\d.]+)", line)
                if m:
                    regime["vix"] = float(m.group(1))
            if "KOSPI" in line and ("+" in line or "-" in line):
                m = re.search(r"KOSPI\s*([+-][\d.]+)%", line)
                if m:
                    regime["kospi_chg"] = float(m.group(1))
    except Exception:
        pass
    return regime


# ═══════════════════════════════════════════════════════════════
# 스타일 헬퍼
# ═══════════════════════════════════════════════════════════════

def _style_score(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #2ecc40; font-weight: bold;"
        if v < 0:
            return "color: #ff4136; font-weight: bold;"
    except Exception:
        pass
    return ""


def _style_return(val):
    try:
        v = float(str(val).replace("%", ""))
        if v >= 5:
            return "background-color: #186a3b; color: white; font-weight: bold;"
        if v > 0:
            return "background-color: #e6ffe6; color: #186a3b; font-weight: bold;"
        if v <= -5:
            return "background-color: #922b21; color: white; font-weight: bold;"
        if v < 0:
            return "background-color: #ffe6e6; color: #922b21; font-weight: bold;"
    except Exception:
        pass
    return ""


def _style_winrate(val):
    try:
        v = float(str(val).replace("%", ""))
        if v >= 60:
            return "background-color: #e6ffe6; color: #186a3b; font-weight: bold;"
        if v >= 50:
            return "background-color: #fff9e6; color: #7d6608;"
        if v < 40:
            return "background-color: #ffe6e6; color: #922b21;"
    except Exception:
        pass
    return ""


def _fmt_price(v):
    try:
        f = float(v)
        return f"{f:,.2f}" if f < 1000 else f"{f:,.0f}"
    except Exception:
        return str(v) if v else "-"


def _fmt_pct(v):
    try:
        f = float(v)
        return f"{f:+.2f}%"
    except Exception:
        return "-"


SIGNAL_LABEL = {"BUY": "🔵 매수", "SELL": "🟠 매도"}
MARKET_LABEL = {"KOSPI": "🇰🇷 코스피", "KOSDAQ": "🇰🇷 코스닥", "US": "🇺🇸 미국"}


def _rec_to_display(df: pd.DataFrame) -> pd.DataFrame:
    """추천 DataFrame → 표시용"""
    if df.empty:
        return df
    rename = {
        "market": "시장", "rank": "순위", "name": "종목명",
        "ticker": "티커", "price": "현재가", "score": "점수",
        "rsi": "RSI", "macd_hist": "MACD히스트",
        "ma5": "MA5", "ma20": "MA20", "ma60": "MA60",
        "investor_tags": "투자자태그",
    }
    out = df.rename(columns=rename)
    if "현재가" in out.columns:
        out["현재가"] = out["현재가"].apply(_fmt_price)
    if "시장" in out.columns:
        out["시장"] = out["시장"].map(MARKET_LABEL).fillna(out["시장"])
    for c in ["점수", "RSI", "MACD히스트", "MA5", "MA20"]:
        if c in out.columns:
            out[c] = out[c].apply(lambda x: f"{float(x):.0f}" if x is not None and x != "" else "-")
    show = [c for c in ["시장", "순위", "종목명", "티커", "현재가", "점수",
                         "RSI", "MACD히스트", "MA5", "MA20", "투자자태그"]
            if c in out.columns]
    return out[show]


# ═══════════════════════════════════════════════════════════════
# 헤더 — 시장 레짐 카드
# ═══════════════════════════════════════════════════════════════
st.title("📊 AI 주식 스크리닝 대시보드 v2")

latest_date = _get_latest_date()
regime = _read_market_regime()

col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
with col_h1:
    st.metric("📅 최신 분석일", latest_date or "-")
with col_h2:
    fg = regime.get("fear_greed")
    fg_label = "극공포" if fg and fg < 20 else ("공포" if fg and fg < 40 else
               "중립" if fg and fg < 60 else ("탐욕" if fg and fg < 80 else "극탐욕"))
    st.metric("😨 Fear & Greed", f"{fg}/100 [{fg_label}]" if fg else "-")
with col_h3:
    vix = regime.get("vix")
    st.metric("📉 VIX", f"{vix}" if vix else "-",
              delta="위험" if vix and vix > 20 else "안정",
              delta_color="inverse" if vix and vix > 20 else "normal")
with col_h4:
    kospi = regime.get("kospi_chg")
    st.metric("🇰🇷 KOSPI 5일", f"{kospi:+.1f}%" if kospi else "-",
              delta=f"{kospi:+.1f}%" if kospi else None,
              delta_color="normal")
with col_h5:
    r = regime.get("regime") or "-"
    color = "🔴🔴" if "극도약세" in r else ("🔴" if "약세" in r else
            "🟢🟢" if "극도강세" in r else ("🟢" if "강세" in r else "⚪"))
    st.metric("📊 시장레짐", f"{color} {r}")

st.divider()


# ═══════════════════════════════════════════════════════════════
# 탭
# ═══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 오늘의 추천",
    "📊 성능 분석",
    "🗂️ 히스토리",
    "🎯 ARK 추천",
    "⚠️ Citrini 2028",
])


# ───────────────────────────────────────────────────────────────
# TAB 1 : 오늘의 추천
# ───────────────────────────────────────────────────────────────
with tab1:
    if not latest_date:
        st.info("분석 데이터가 없습니다. stock_advisor_v4.py를 먼저 실행하세요.")
    else:
        st.caption(f"기준일: {latest_date}  |  DB: {PERF_DB}")

        # 시장 필터
        market_sel = st.radio(
            "시장 선택", ["전체", "KOSPI", "KOSDAQ", "US"],
            horizontal=True, key="tab1_market"
        )
        mkt = "ALL" if market_sel == "전체" else market_sel

        c_buy, c_sell = st.columns(2)

        with c_buy:
            st.subheader("🔵 매수 추천")
            buy_df = _get_recommendations(latest_date, mkt, "BUY")
            if buy_df.empty:
                st.info("매수 추천 데이터 없음")
            else:
                disp = _rec_to_display(buy_df)
                styled = disp.style.applymap(_style_score, subset=["점수"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
                st.caption(f"총 {len(buy_df)}개 종목 (최소 점수 40점 이상)")

        with c_sell:
            st.subheader("🟠 매도 추천")
            sell_df = _get_recommendations(latest_date, mkt, "SELL")
            if sell_df.empty:
                st.info("매도 추천 데이터 없음")
            else:
                disp = _rec_to_display(sell_df)
                styled = disp.style.applymap(_style_score, subset=["점수"])
                st.dataframe(styled, use_container_width=True, hide_index=True)
                st.caption(f"총 {len(sell_df)}개 종목")


# ───────────────────────────────────────────────────────────────
# TAB 2 : 성능 분석
# ───────────────────────────────────────────────────────────────
with tab2:
    st.subheader("📈 기간별 매수 / 매도 승률")
    st.caption("이상값(±30% 초과) 제외 기준")

    win_data = _get_win_rates()

    if not win_data:
        st.info("성능 데이터가 부족합니다. 분석을 며칠 더 실행하세요.")
    else:
        # KPI 테이블
        rows = []
        for day in sorted(win_data.keys()):
            d = win_data[day]
            rows.append({
                "기간": f"{day}일 후",
                "매수 건수": d["buy_cnt"],
                "매수 승률": f"{d['buy_wr']:.1f}%",
                "평균 수익률": f"{d['avg_ret']:+.2f}%",
                "매도 건수": d["sell_cnt"],
                "매도 승률": f"{d['sell_wr']:.1f}%",
            })
        wr_df = pd.DataFrame(rows)

        # 5일 기준 강조 메트릭
        p5 = win_data.get(5, {})
        p10 = win_data.get(10, {})
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("5일 매수 승률", f"{p5.get('buy_wr', 0):.1f}%",
                      help="이상값 제외 기준")
        with c2:
            st.metric("5일 매수 평균수익", f"{p5.get('avg_ret', 0):+.2f}%")
        with c3:
            st.metric("5일 매도 승률", f"{p5.get('sell_wr', 0):.1f}%")
        with c4:
            st.metric("10일 매수 승률", f"{p10.get('buy_wr', 0):.1f}%",
                      help="데이터 충분 시 가장 신뢰도 높은 지표")

        st.dataframe(
            wr_df.style.applymap(_style_winrate, subset=["매수 승률", "매도 승률"])
                       .applymap(_style_return, subset=["평균 수익률"]),
            use_container_width=True, hide_index=True
        )

    st.divider()

    # 점수 구간별 승률
    col_s, col_m = st.columns(2)
    with col_s:
        st.subheader("🎯 점수 구간별 승률 (5일)")
        score_df = _get_score_win_rate()
        if score_df.empty:
            st.info("데이터 부족")
        else:
            styled_s = score_df.style.applymap(_style_winrate, subset=["승률"]) \
                                     .applymap(_style_return, subset=["평균수익률"])
            st.dataframe(styled_s, use_container_width=True, hide_index=True)
            st.caption("👉 40점 이상 구간에서 승률이 높음 → 매수 최소 점수 40점 적용 중")

    with col_m:
        st.subheader("🌏 시장별 승률 (5일)")
        mkt_df = _get_market_win_rate()
        if mkt_df.empty:
            st.info("데이터 부족")
        else:
            styled_m = mkt_df.style.applymap(_style_winrate, subset=["승률"]) \
                                    .applymap(_style_return, subset=["평균수익률"])
            st.dataframe(styled_m, use_container_width=True, hide_index=True)

    st.divider()

    # 최근 HIT / MISS 결과
    st.subheader("📋 최근 HIT / MISS (5일 후, ±30% 이내)")
    recent_df = _get_recent_results(40)
    if recent_df.empty:
        st.info("검증 데이터가 없습니다. 추천 후 5거래일이 지나면 자동 집계됩니다.")
    else:
        # HIT 여부 컬럼 추가
        def hit_label(row):
            if row["신호"] == "BUY":
                return "✅ HIT" if row["수익률"] > 0 else "❌ MISS"
            else:
                return "✅ HIT" if row["수익률"] < 0 else "❌ MISS"

        recent_df["결과"] = recent_df.apply(hit_label, axis=1)
        recent_df["수익률"] = recent_df["수익률"].apply(_fmt_pct)
        recent_df["진입가"] = recent_df["진입가"].apply(_fmt_price)
        recent_df["청산가"] = recent_df["청산가"].apply(_fmt_price)
        recent_df["시장"] = recent_df["market"].map(MARKET_LABEL).fillna(recent_df["market"])
        if "점수" in recent_df.columns:
            recent_df["점수"] = recent_df["점수"].apply(lambda x: f"{float(x):.0f}" if x is not None and x != "" else "-")

        show = ["date", "시장", "신호", "순위", "name", "ticker",
                "점수", "진입가", "청산가", "수익률", "결과"]
        show = [c for c in show if c in recent_df.columns]
        rename_r = {"date": "날짜", "name": "종목명", "ticker": "티커"}
        disp_r = recent_df[show].rename(columns=rename_r)

        # 결과별 필터
        result_filter = st.radio(
            "결과 필터", ["전체", "HIT만", "MISS만"], horizontal=True, key="tab2_filter"
        )
        if result_filter == "HIT만":
            disp_r = disp_r[disp_r["결과"].str.contains("HIT")]
        elif result_filter == "MISS만":
            disp_r = disp_r[disp_r["결과"].str.contains("MISS")]

        hit_cnt  = (recent_df["결과"].str.contains("HIT")).sum()
        miss_cnt = (recent_df["결과"].str.contains("MISS")).sum()
        total    = hit_cnt + miss_cnt
        st.caption(f"HIT {hit_cnt}건 / MISS {miss_cnt}건 / 승률 {hit_cnt/total*100:.1f}%" if total else "")

        styled_r = disp_r.style.applymap(_style_return, subset=["수익률"])
        st.dataframe(styled_r, use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────
# TAB 3 : 히스토리
# ───────────────────────────────────────────────────────────────
with tab3:
    all_dates = _get_all_dates()
    if not all_dates:
        st.info("저장된 히스토리가 없습니다.")
    else:
        col_d, col_mkt, col_sig = st.columns(3)
        with col_d:
            sel_date = st.selectbox("📅 날짜", all_dates, key="tab3_date")
        with col_mkt:
            sel_mkt = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ", "US"], key="tab3_mkt")
        with col_sig:
            sel_sig = st.radio("신호", ["매수", "매도"], horizontal=True, key="tab3_sig")

        mkt3 = "ALL" if sel_mkt == "전체" else sel_mkt
        sig3 = "BUY" if sel_sig == "매수" else "SELL"

        hist_df = _get_recommendations(sel_date, mkt3, sig3)
        if hist_df.empty:
            st.info(f"{sel_date} {sel_mkt} {sel_sig} 데이터가 없습니다.")
        else:
            disp3 = _rec_to_display(hist_df)
            styled3 = disp3.style.applymap(_style_score, subset=["점수"])
            st.dataframe(styled3, use_container_width=True, hide_index=True)
            st.caption(f"총 {len(hist_df)}개 종목 · {sel_date} · {sel_mkt} · {sel_sig}")

        with st.expander("📅 전체 보유 날짜 목록"):
            for d in all_dates:
                st.text(f"  {d}")


# ───────────────────────────────────────────────────────────────
# TAB 4 : ARK 추천 종목
# ───────────────────────────────────────────────────────────────
with tab4:
    st.header("🎯 ARK Invest Big Ideas 2026")
    st.caption("ARK Big Ideas 2026 보고서 기반 13대 메가테마 유망 종목")
    st.divider()

    ark_perf = get_ark_performance_summary(days_back=30)
    if ark_perf:
        c1, c2, c3, c4 = st.columns(4)
        avg = ark_perf.get("평균 20 일수익률", 0)
        with c1:
            st.metric("종목수", f"{ark_perf.get('종목수', 0)}개")
        with c2:
            st.metric("평균 20일 수익률", f"{avg:+.2f}%",
                      delta=f"{avg:+.2f}%", delta_color="normal")
        with c3:
            st.metric("최고 수익률", f"{ark_perf.get('최고수익률', 0):+.2f}%")
        with c4:
            st.metric("최저 수익률", f"{ark_perf.get('최저수익률', 0):+.2f}%")
    st.divider()

    ark_rows = get_latest_ark_recommended(limit=60)
    if ark_rows:
        ark_df = pd.DataFrame(ark_rows)
        rename_ark = {
            "ticker": "티커", "name": "종목명", "market": "시장",
            "theme_key": "테마", "price": "현재가",
            "change_1d": "1일등락", "change_5d": "5일등락",
            "change_20d": "20일등락", "rsi": "RSI",
            "priority": "우선순위", "reason": "추천사유",
        }
        ark_df = ark_df.rename(columns=rename_ark)
        for c in ["1일등락", "5일등락", "20일등락"]:
            if c in ark_df.columns:
                ark_df[c] = ark_df[c].apply(lambda x: f"{x:+.2f}%" if x else "-")
        ark_df["현재가"] = ark_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
        ark_df["RSI"] = ark_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")
        pri_map = {"CORE": "🔴 CORE", "HIGH": "🟡 HIGH", "MEDIUM": "⚪ MEDIUM"}
        ark_df["우선순위"] = ark_df["우선순위"].map(pri_map).fillna(ark_df["우선순위"])

        show_cols = ["티커", "종목명", "시장", "우선순위", "테마",
                     "현재가", "1일등락", "5일등락", "20일등락", "RSI", "추천사유"]
        show_cols = [c for c in show_cols if c in ark_df.columns]

        def _ark_ret(val):
            try:
                v = float(str(val).replace("%", ""))
                if v > 0:
                    return "background-color:#e6ffe6;color:#186a3b;font-weight:bold;"
                if v < 0:
                    return "background-color:#ffe6e6;color:#922b21;font-weight:bold;"
            except Exception:
                pass
            return ""

        styled_ark = ark_df[show_cols].style.applymap(_ark_ret, subset=["20일등락"])
        st.dataframe(styled_ark, use_container_width=True, hide_index=True)
    else:
        st.info("ARK 데이터 없음. ark_recommended_stocks.py 먼저 실행하세요.")


# ───────────────────────────────────────────────────────────────
# TAB 5 : Citrini 2028 부정적 종목
# ───────────────────────────────────────────────────────────────
with tab5:
    st.header("⚠️ Citrini 2028 글로벌 지능위기 — 부정적 종목")
    st.caption("AI 대량실업·소비붕괴 시나리오에서 피해 예상 종목 추적")
    st.divider()

    citrini_perf = get_citrini_performance_summary(days_back=30)
    if citrini_perf:
        c1, c2, c3, c4 = st.columns(4)
        avg_c = citrini_perf.get("평균 20 일수익률", 0)
        with c1:
            st.metric("종목수", f"{citrini_perf.get('종목수', 0)}개")
        with c2:
            st.metric("평균 20일 수익률", f"{avg_c:+.2f}%",
                      delta=f"{avg_c:+.2f}%",
                      delta_color="normal" if avg_c < 0 else "inverse")
        with c3:
            h = citrini_perf.get("HIGH 위험평균")
            st.metric("HIGH 위험 평균", f"{h:+.2f}%" if h else "N/A")
        with c4:
            st.metric("최저 수익률", f"{citrini_perf.get('최저수익률', 0):+.2f}%")
    st.divider()

    citrini_rows = get_latest_citrini_risky(limit=60)
    if citrini_rows:
        risk_filter = st.radio(
            "위험등급", ["ALL", "HIGH", "MEDIUM", "LOW"], horizontal=True
        )
        rows_f = [r for r in citrini_rows if risk_filter == "ALL"
                  or r.get("risk_level") == risk_filter]

        cit_df = pd.DataFrame(rows_f)
        if not cit_df.empty:
            rename_cit = {
                "ticker": "티커", "name": "종목명", "market": "시장",
                "sector": "섹터", "risk_level": "위험등급",
                "price": "현재가", "change_1d": "1일등락",
                "change_20d": "20일등락", "rsi": "RSI", "reason": "위험사유",
            }
            cit_df = cit_df.rename(columns=rename_cit)
            cit_df["현재가"] = cit_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
            cit_df["1일등락"] = cit_df["1일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            cit_df["20일등락"] = cit_df["20일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            cit_df["RSI"] = cit_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")
            risk_map = {"HIGH": "🔴 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "⚪ LOW"}
            cit_df["위험등급"] = cit_df["위험등급"].map(risk_map).fillna(cit_df["위험등급"])

            def _cit_ret(val):
                try:
                    v = float(str(val).replace("%", ""))
                    if v < -15:
                        return "background-color:#ff4444;color:white;font-weight:bold;"
                    if v < -5:
                        return "background-color:#ffe6e6;color:#922b21;font-weight:bold;"
                    if v < 0:
                        return "background-color:#fff3e6;color:#ba4a00;"
                    return "background-color:#e6ffe6;color:#186a3b;"
                except Exception:
                    return ""

            show_cit = ["티커", "종목명", "시장", "위험등급", "섹터",
                        "현재가", "20일등락", "RSI", "위험사유"]
            show_cit = [c for c in show_cit if c in cit_df.columns]
            styled_cit = cit_df[show_cit].style.applymap(_cit_ret, subset=["20일등락"])
            st.dataframe(styled_cit, use_container_width=True, hide_index=True)
        else:
            st.info(f"{risk_filter} 위험등급 데이터 없음")
    else:
        st.info("Citrini 데이터 없음. citrini_risky_stocks.py 먼저 실행하세요.")
