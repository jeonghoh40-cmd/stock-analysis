"""
Streamlit 대시보드 — AI 주식 스크리닝 히스토리 뷰어
────────────────────────────────────────────────────
실행:  streamlit run dashboard.py
접속:  http://localhost:8501

탭 구성:
  📋 오늘의 추천  — 가장 최근 매수/매도 TOP10
  📈 백테스팅     — 최근 N일 수익률 분석
  🗂️  히스토리    — 날짜별 과거 추천 조회
"""

import os
import sys
import datetime

import streamlit as st
import pandas as pd

# ── 경로 설정 (dashboard.py가 있는 폴더 기준) ──────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from db_manager import (
    get_latest_results,
    get_history_dates,
    get_results_by_date,
    run_backtest,
    get_performance_summary,
    init_db,
    get_latest_ark_recommended,
    get_ark_history_dates,
    get_ark_performance_summary,
    get_latest_citrini_risky,
    get_citrini_performance_summary,
    get_citrini_by_risk_level,
    get_citrini_by_sector,
)

# ── 페이지 기본 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="AI 주식 스크리닝",
    page_icon="📊",
    layout="wide",
)

init_db()   # 테이블 미존재 시 자동 생성


# ═══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════
def _style_score(val):
    """점수 컬럼 색상: 양수=초록, 음수=빨강"""
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
    """수익률 컬럼 색상"""
    try:
        v = float(str(val).replace("%", ""))
        if v > 0:
            return "background-color: #e6ffe6; color: #186a3b; font-weight: bold;"
        if v < 0:
            return "background-color: #ffe6e6; color: #922b21; font-weight: bold;"
    except Exception:
        pass
    return ""


def _fmt_price(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return str(v) if v else "-"


def _fmt_pct(v):
    try:
        f = float(v)
        sign = "+" if f >= 0 else ""
        return f"{sign}{f:.2f}%"
    except Exception:
        return str(v) if v else "-"


def _results_to_df(rows: list) -> pd.DataFrame:
    """DB row 리스트 → 표시용 DataFrame"""
    if not rows:
        return pd.DataFrame()

    cols_map = {
        "rank":         "순위",
        "group_name":   "그룹",
        "name":         "종목명",
        "ticker":       "티커",
        "price":        "현재가",
        "score":        "점수",
        "dart_bonus":   "DART보너스",
        "rsi":          "RSI",
        "macd_hist":    "MACD히스트",
        "bb_pct":       "BB위치(%)",
        "vol_ratio":    "거래량비",
        "mom5":         "5일모멘텀",
        "ma5":          "MA5",
        "ma20":         "MA20",
        "ma60":         "MA60",
        "atr":          "ATR14",
        "stop_loss":    "손절가",
        "target_price": "목표가",
    }

    df = pd.DataFrame(rows)
    rename = {k: v for k, v in cols_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    # 숫자 포맷
    for c in ["현재가", "손절가", "목표가", "MA5", "MA20", "MA60", "ATR14"]:
        if c in df.columns:
            df[c] = df[c].apply(_fmt_price)

    for c in ["5일모멘텀"]:
        if c in df.columns:
            df[c] = df[c].apply(_fmt_pct)

    # 표시 컬럼만 추출 (항상 유지할 핵심 컬럼)
    show = [c for c in
            ["순위", "그룹", "종목명", "티커", "현재가", "점수", "DART보너스",
             "RSI", "BB위치(%)", "거래량비", "5일모멘텀",
             "손절가", "목표가"]
            if c in df.columns]
    return df[show]


# ═══════════════════════════════════════════════════════════════
# 헤더
# ═══════════════════════════════════════════════════════════════
st.title("📊 AI 주식 스크리닝 대시보드")
st.caption(f"DB: {os.path.join(BASE_DIR, 'stock_history.db')}  "
           f"| 최종 갱신: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.divider()


# ═══════════════════════════════════════════════════════════════
# 탭 구성
# ═══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 오늘의 추천",
    "📈 백테스팅 성과",
    "🗂️ 히스토리 조회",
    "🎯 ARK 추천 종목",
    "⚠️ Citrini 2028 부정적 종목",
])


# ───────────────────────────────────────────────────────────────
# TAB 1 : 오늘의 추천
# ───────────────────────────────────────────────────────────────
with tab1:
    st.subheader("✅ 매수 추천 TOP 10")
    buy_rows = get_latest_results(signal="buy", limit=10)
    if buy_rows:
        buy_df = _results_to_df(buy_rows)
        # 점수 컬럼 스타일
        styled_buy = buy_df.style.applymap(_style_score, subset=["점수"])
        st.dataframe(styled_buy, use_container_width=True, hide_index=True)
    else:
        st.info("매수 추천 데이터가 없습니다. stock_advisor.py를 먼저 실행하세요.")

    st.divider()

    st.subheader("❌ 매도 추천 TOP 10")
    sell_rows = get_latest_results(signal="sell", limit=10)
    if sell_rows:
        sell_df = _results_to_df(sell_rows)
        styled_sell = sell_df.style.applymap(_style_score, subset=["점수"])
        st.dataframe(styled_sell, use_container_width=True, hide_index=True)
    else:
        st.info("매도 추천 데이터가 없습니다.")

    # 오늘의 날짜 표시
    if buy_rows:
        run_date = buy_rows[0].get("date", "")
        st.caption(f"📅 데이터 기준일: {run_date[:4]}-{run_date[4:6]}-{run_date[6:]}")


# ───────────────────────────────────────────────────────────────
# TAB 2 : 백테스팅 성과
# ───────────────────────────────────────────────────────────────
with tab2:
    days_opt = st.radio(
        "조회 기간",
        options=[7, 14, 30, 60],
        index=2,
        horizontal=True,
        format_func=lambda x: f"{x}일",
    )

    perf = get_performance_summary(days_opt)

    if not perf:
        st.warning("백테스팅 데이터가 없습니다. "
                   "stock_advisor.py를 며칠 실행한 뒤 다시 확인하세요.")
    else:
        # 핵심 KPI 카드
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📦 분석 종목수", f"{perf['종목수']}개")
        with col2:
            st.metric("🏆 승률", f"{perf['승률(%)']:.1f}%")
        with col3:
            avg = perf["평균수익률"]
            st.metric("📊 평균수익률",
                      f"{avg:+.2f}%",
                      delta=f"{avg:+.2f}%",
                      delta_color="normal")
        with col4:
            st.metric("📈 최대수익률", f"{perf['최대수익률']:+.2f}%")
        with col5:
            st.metric("📉 최대손실률", f"{perf['최대손실률']:+.2f}%")

        col6, col7, col8 = st.columns(3)
        with col6:
            st.metric("✅ 수익 종목", f"{perf['양수종목']}개")
        with col7:
            st.metric("❌ 손실 종목", f"{perf['음수종목']}개")
        with col8:
            sl = perf.get("손절도달", 0)
            tg = perf.get("목표도달", 0)
            st.metric("🎯 손절/목표 도달", f"손절:{sl}  목표:{tg}")

        st.divider()

        # 상세 백테스팅 결과 테이블
        st.subheader("📋 종목별 수익률 상세")
        bt_rows = run_backtest(days_opt)
        if bt_rows:
            bt_df = pd.DataFrame(bt_rows)

            # 컬럼 이름 한글화
            rename_bt = {
                "entry_date":    "진입일",
                "rank":          "순위",
                "name":          "종목명",
                "ticker":        "티커",
                "entry_price":   "진입가",
                "current_price": "현재가",
                "return_pct":    "수익률(%)",
                "hit_stop":      "손절도달",
                "hit_target":    "목표도달",
            }
            bt_df = bt_df.rename(columns=rename_bt)

            # 수익률 포맷
            bt_df["수익률(%)"] = bt_df["수익률(%)"].apply(
                lambda x: f"{x:+.2f}%" if x is not None else "-"
            )
            bt_df["손절도달"] = bt_df["손절도달"].apply(
                lambda x: "🔴" if x else ("⚪" if x is False else "-")
            )
            bt_df["목표도달"] = bt_df["목표도달"].apply(
                lambda x: "🟢" if x else ("⚪" if x is False else "-")
            )

            show_cols = ["진입일", "순위", "종목명", "티커",
                         "진입가", "현재가", "수익률(%)", "손절도달", "목표도달"]
            bt_df = bt_df[[c for c in show_cols if c in bt_df.columns]]

            styled_bt = bt_df.style.applymap(_style_return, subset=["수익률(%)"])
            st.dataframe(styled_bt, use_container_width=True, hide_index=True)


# ───────────────────────────────────────────────────────────────
# TAB 3 : 히스토리 조회
# ───────────────────────────────────────────────────────────────
with tab3:
    dates = get_history_dates()

    if not dates:
        st.info("저장된 히스토리가 없습니다. stock_advisor.py를 먼저 실행하세요.")
    else:
        # 날짜 선택기
        date_labels = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates]
        selected_label = st.selectbox(
            "📅 조회할 날짜를 선택하세요",
            options=date_labels,
        )
        selected_date = dates[date_labels.index(selected_label)]

        sig_opt = st.radio("신호 유형", ["매수", "매도"], horizontal=True)
        signal  = "buy" if sig_opt == "매수" else "sell"

        hist_rows = get_results_by_date(selected_date, signal)
        if hist_rows:
            hist_df = _results_to_df(hist_rows)
            styled_hist = hist_df.style.applymap(_style_score, subset=["점수"])
            st.dataframe(styled_hist, use_container_width=True, hide_index=True)
            st.caption(f"총 {len(hist_rows)}개 종목 · {selected_label} · {sig_opt} 추천")
        else:
            st.info(f"{selected_label} {sig_opt} 데이터가 없습니다.")

        # 날짜별 수집 현황
        with st.expander("📅 전체 저장 날짜 목록"):
            for d in dates:
                st.text(f"  {d[:4]}-{d[4:6]}-{d[6:]}")


# ───────────────────────────────────────────────────────────────
# TAB 4 : ARK 추천 종목
# ───────────────────────────────────────────────────────────────
with tab4:
    st.header("🎯 ARK Invest Big Ideas 2026 — 추천 종목")
    st.caption("""
    ARK Invest 의 'Big Ideas 2026' 보고서에서 선정한 유망 기업들을 추적합니다.
    13 대 메가테마 (AI 인프라, 로보틱스, 바이오텍, 에너지 등) 에 따라 분류되며,
    기존 스크리닝 추천 종목과 별도로 관리됩니다.
    """)
    st.divider()

    # ARK 성과 요약
    ark_perf = get_ark_performance_summary(days_back=30)

    if ark_perf:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📦 분석 종목수", f"{ark_perf.get('종목수', 0)}개")
        with col2:
            avg = ark_perf.get('평균 20 일수익률', 0)
            st.metric("📊 평균 20 일수익률",
                      f"{avg:+.2f}%",
                      delta=f"{avg:+.2f}%",
                      delta_color="normal")
        with col3:
            st.metric("📈 최고수익률", f"{ark_perf.get('최고수익률', 0):+.2f}%")
        with col4:
            st.metric("📉 최저수익률", f"{ark_perf.get('최저수익률', 0):+.2f}%")
    else:
        st.info("ARK 추천 종목 데이터가 없습니다. ark_recommended_stocks.py 를 먼저 실행하세요.")

    st.divider()

    # 최신 ARK 추천 종목 목록
    st.subheader("📋 최신 ARK 추천 종목 목록")

    ark_rows = get_latest_ark_recommended(limit=50)

    if ark_rows:
        # 데이터프레임 변환
        ark_df = pd.DataFrame(ark_rows)

        # 컬럼 이름 한글화
        rename_ark = {
            "ticker":       "티커",
            "name":         "종목명",
            "market":       "시장",
            "theme_key":    "테마",
            "price":        "현재가",
            "change_1d":    "1 일등락",
            "change_5d":    "5 일등락",
            "change_20d":   "20 일등락",
            "rsi":          "RSI",
            "priority":     "우선순위",
            "reason":       "추천사유",
        }
        ark_df = ark_df.rename(columns=rename_ark)

        # 포맷팅
        ark_df["현재가"] = ark_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
        ark_df["1 일등락"] = ark_df["1 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
        ark_df["5 일등락"] = ark_df["5 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
        ark_df["20 일등락"] = ark_df["20 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
        ark_df["RSI"] = ark_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")

        # 우선순위 아이콘
        def priority_icon(p):
            if p == "CORE": return "🔴 CORE"
            if p == "HIGH": return "🟡 HIGH"
            if p == "MEDIUM": return "⚪ MEDIUM"
            return p

        ark_df["우선순위"] = ark_df["우선순위"].apply(priority_icon)

        # 20 일등락 색상
        def style_return(val):
            try:
                v = float(str(val).replace("%", ""))
                if v > 0:
                    return "background-color: #e6ffe6; color: #186a3b; font-weight: bold;"
                if v < 0:
                    return "background-color: #ffe6e6; color: #922b21; font-weight: bold;"
            except Exception:
                pass
            return ""

        # 표시 컬럼
        show_cols = ["티커", "종목명", "시장", "우선순위", "테마",
                     "현재가", "1 일등락", "5 일등락", "20 일등락", "RSI", "추천사유"]
        show_cols = [c for c in show_cols if c in ark_df.columns]

        styled_ark = ark_df.style.apply(style_return, subset=["20 일등락"])
        st.dataframe(styled_ark, use_container_width=True, hide_index=True)

        # 데이터 기준일
        if ark_rows:
            run_date = ark_rows[0].get("date", "")
            st.caption(f"📅 데이터 기준일: {run_date[:4]}-{run_date[4:6]}-{run_date[6:]}")

    else:
        st.info("ARK 추천 종목 데이터가 없습니다. ark_recommended_stocks.py 를 먼저 실행하세요.")

    st.divider()

    # ARK 테마별 필터
    st.subheader("🔍 테마별 필터")

    theme_options = {
        "1_대가속": "1. 대가속 (5 개 플랫폼 수렴)",
        "2_AI 인프라": "2. AI 인프라",
        "3_AI_Consumer_OS": "3. AI Consumer OS",
        "4_AI_생산성": "4. AI 생산성",
        "5_비트코인": "5. 비트코인",
        "6_토큰화자산": "6. 토큰화 자산",
        "7_DeFi": "7. DeFi",
        "8_멀티오믹스": "8. 멀티오믹스",
        "9_재사용로켓": "9. 재사용 로켓",
        "10_로보틱스": "10. 로보틱스",
        "11_분산에너지": "11. 분산 에너지",
        "12_자율주행": "12. 자율주행",
        "13_자율물류": "13. 자율 물류",
    }

    selected_theme = st.selectbox(
        "테마를 선택하세요",
        options=list(theme_options.keys()),
        format_func=lambda x: theme_options[x],
    )

    if st.button("테마별 종목 조회"):
        from db_manager import get_ark_by_theme
        theme_rows = get_ark_by_theme(selected_theme)

        if theme_rows:
            theme_df = pd.DataFrame(theme_rows)
            theme_df = theme_df.rename(columns=rename_ark)

            # 포맷팅
            theme_df["현재가"] = theme_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
            theme_df["20 일등락"] = theme_df["20 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            theme_df["RSI"] = theme_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")
            theme_df["우선순위"] = theme_df["우선순위"].apply(priority_icon)

            show_cols = ["티커", "종목명", "시장", "우선순위",
                         "현재가", "20 일등락", "RSI", "추천사유"]
            show_cols = [c for c in show_cols if c in theme_df.columns]

            styled_theme = theme_df.style.apply(style_return, subset=["20 일등락"])
            st.dataframe(styled_theme, use_container_width=True, hide_index=True)
            st.caption(f"총 {len(theme_rows)}개 종목 · {theme_options[selected_theme]}")
        else:
            st.info(f"{theme_options[selected_theme]} 테마의 데이터가 없습니다.")

    st.divider()

    # ARK 정보
    with st.expander("📚 ARK Big Ideas 2026 정보"):
        st.markdown("""
        ### ARK Invest Big Ideas 2026
        ARK Invest 는 2026 년 1 월 연례 보고서 'Big Ideas 2026'을 통해
        13 대 메가테마를 발표했습니다.

        **주요 테마:**
        - 1. 대가속 (The Great Acceleration) — 5 개 플랫폼 수렴
        - 2. AI 인프라 — 데이터센터·반도체·전력
        - 3. AI Consumer OS — AI 가 검색·쇼핑·의사결정 대체
        - 4. AI 생산성 — 기업 소프트웨어 AI 전환
        - 8. 멀티오믹스 — AI × Biology 신약개발
        - 10. 로보틱스 — 범용 물리 AI
        - 11. 분산 에너지 — 전력이 AI 의 병목

        **출처:** [ark-invest.com/big-ideas-2026](https://ark-invest.com/big-ideas-2026)

        **참고:** 이 데이터는 투자 참고용이며, 최종 투자 결정은 본인의 책임입니다.
        """)


# ───────────────────────────────────────────────────────────────
# TAB 5 : Citrini 2028 부정적 종목
# ───────────────────────────────────────────────────────────────
with tab5:
    st.header("⚠️ Citrini 2028 글로벌 지능위기 — 부정적 종목")
    st.caption("""
    Citrini Research 의 '2028 Global Intelligence Crisis' 보고서는 
    AI 에 의한 대량실업과 소비 붕괴 시나리오를 경고합니다.
    이 탭에서는 위기 피해가 예상되는 기업들을 추적합니다.
    """)
    st.divider()

    # 시나리오 개요
    st.subheader("📜 Citrini 2028 위기 시나리오")
    st.markdown("""
    **주요 내용:**
    - AI 가 화이트칼라 대량 실업 유발
    - 소비 붕괴 → 디플레이션 악순환
    - S&P 500: 8000 → 3500 붕괴 (2028 년 6 월)
    - 실업률 최고 10.2% 도달
    """)

    st.divider()

    # Citrini 성과 요약
    citrini_perf = get_citrini_performance_summary(days_back=30)

    if citrini_perf:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📦 분석 종목수", f"{citrini_perf.get('종목수', 0)}개")
        with col2:
            avg = citrini_perf.get('평균 20 일수익률', 0)
            st.metric("📊 평균 20 일수익률",
                      f"{avg:+.2f}%",
                      delta=f"{avg:+.2f}%",
                      delta_color="normal" if avg < 0 else "inverse")
        with col3:
            st.metric("🔴 HIGH 위험평균", 
                      f"{citrini_perf.get('HIGH 위험평균', 0):+.2f}%" if citrini_perf.get('HIGH 위험평균') else "N/A")
        with col4:
            st.metric("📉 최저수익률", f"{citrini_perf.get('최저수익률', 0):+.2f}%")
    else:
        st.info("Citrini 부정적 종목 데이터가 없습니다. citrini_risky_stocks.py 를 먼저 실행하세요.")

    st.divider()

    # 최신 부정적 종목 목록
    st.subheader("📋 부정적 종목 목록 (위험등급별)")

    citrini_rows = get_latest_citrini_risky(limit=50)

    if citrini_rows:
        # 위험등급 필터
        risk_filter = st.radio(
            "위험등급 필터",
            options=["ALL", "HIGH", "MEDIUM", "LOW"],
            horizontal=True
        )

        if risk_filter != "ALL":
            filtered_rows = [r for r in citrini_rows if r.get("risk_level") == risk_filter]
        else:
            filtered_rows = citrini_rows

        # 데이터프레임 변환
        citrini_df = pd.DataFrame(filtered_rows)

        if not citrini_df.empty:
            # 컬럼 이름 한글화
            rename_citrini = {
                "ticker":       "티커",
                "name":         "종목명",
                "market":       "시장",
                "sector":       "섹터",
                "risk_level":   "위험등급",
                "price":        "현재가",
                "change_1d":    "1 일등락",
                "change_20d":   "20 일등락",
                "rsi":          "RSI",
                "reason":       "위험사유",
            }
            citrini_df = citrini_df.rename(columns=rename_citrini)

            # 포맷팅
            citrini_df["현재가"] = citrini_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
            citrini_df["1 일등락"] = citrini_df["1 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            citrini_df["20 일등락"] = citrini_df["20 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            citrini_df["RSI"] = citrini_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")

            # 위험등급 아이콘
            def risk_icon(p):
                if p == "HIGH": return "🔴 HIGH"
                if p == "MEDIUM": return "🟡 MEDIUM"
                if p == "LOW": return "⚪ LOW"
                return p

            citrini_df["위험등급"] = citrini_df["위험등급"].apply(risk_icon)

            # 20 일등락 색상 (음수일 때 더 강조)
            def style_risk_return(val):
                try:
                    v = float(str(val).replace("%", ""))
                    if v < -15:
                        return "background-color: #ff4444; color: white; font-weight: bold;"
                    if v < -5:
                        return "background-color: #ffe6e6; color: #922b21; font-weight: bold;"
                    if v < 0:
                        return "background-color: #fff3e6; color: #ba4a00;"
                    return "background-color: #e6ffe6; color: #186a3b;"
                except Exception:
                    return ""

            # 표시 컬럼
            show_cols = ["티커", "종목명", "시장", "위험등급", "섹터",
                         "현재가", "20 일등락", "RSI", "위험사유"]
            show_cols = [c for c in show_cols if c in citrini_df.columns]

            styled_citrini = citrini_df.style.apply(style_risk_return, subset=["20 일등락"])
            st.dataframe(styled_citrini, use_container_width=True, hide_index=True)

            # 데이터 기준일
            if citrini_rows:
                run_date = citrini_rows[0].get("date", "")
                st.caption(f"📅 데이터 기준일: {run_date[:4]}-{run_date[4:6]}-{run_date[6:]}")
        else:
            st.info(f"{risk_filter} 위험등급의 데이터가 없습니다.")

    else:
        st.info("Citrini 부정적 종목 데이터가 없습니다.")

    st.divider()

    # 섹터별 필터
    st.subheader("🔍 섹터별 필터")

    sector_options = {
        "IT 아웃소싱": "인도 IT 서비스, BPO 계약",
        "전통 SaaS": "CRM, ERP, HR 소프트웨어",
        "배달·결제": "소비 지출 의존",
        "부동산": "고가 주택시장",
        "플랫폼": "검색, 광고, 모빌리티",
        "IT 서비스": "레거시 IT 서비스",
        "하드웨어": "PC, 서버",
        "엔터테인먼트": "음악, 연예기획",
    }

    selected_sector = st.selectbox(
        "섹터를 선택하세요",
        options=list(sector_options.keys()),
    )

    if st.button("섹터별 종목 조회"):
        sector_rows = get_citrini_by_sector(selected_sector)

        if sector_rows:
            sector_df = pd.DataFrame(sector_rows)
            sector_df = sector_df.rename(columns=rename_citrini)

            # 포맷팅
            sector_df["현재가"] = sector_df["현재가"].apply(lambda x: f"{x:,.0f}" if x else "-")
            sector_df["20 일등락"] = sector_df["20 일등락"].apply(lambda x: f"{x:+.2f}%" if x else "-")
            sector_df["RSI"] = sector_df["RSI"].apply(lambda x: f"{x:.1f}" if x else "-")
            sector_df["위험등급"] = sector_df["위험등급"].apply(risk_icon)

            show_cols = ["티커", "종목명", "시장", "위험등급",
                         "현재가", "20 일등락", "RSI", "위험사유"]
            show_cols = [c for c in show_cols if c in sector_df.columns]

            styled_sector = sector_df.style.apply(style_risk_return, subset=["20 일등락"])
            st.dataframe(styled_sector, use_container_width=True, hide_index=True)
            st.caption(f"총 {len(sector_rows)}개 종목 · {selected_sector} ({sector_options[selected_sector]})")
        else:
            st.info(f"{selected_sector} 섹터의 데이터가 없습니다.")

    st.divider()

    # 위기 선행 지표
    st.subheader("📊 위기 선행 지표")
    st.markdown("""
    **Citrini 위기 지표 모니터링:**
    
    | 지표 | 설명 |
    |------|------|
    | IGV | 소프트웨어 ETF (SaaS 멀티플 압축 선행지표) |
    | XHB | 주택건설 ETF (주택시장 버블 지표) |
    | ^VIX | 공포지수 (50+ = 위기 급박) |
    | ^TNX | 미 10 년채 수익률 (급락 = 디플레이션 신호) |
    | DXY | 달러인덱스 (급등 = 위험회피 자금 이동) |
    | XRT | 소매 ETF (소비 붕괴 조기 지표) |
    
    **주의:** 이 데이터는 Citrini Research 의 시나리오 기반 경고이며, 
    실제 위기 발생 여부는 다릅니다. 투자 참고용으로만 활용하세요.
    """)

    st.divider()

    # Citrini 정보
    with st.expander("📚 Citrini 2028 보고서 정보"):
        st.markdown("""
        ### Citrini Research "2028 Global Intelligence Crisis"
        
        Citrini Research 는 2026 년 2 월 '2028 글로벌 지능위기' 시나리오 보고서를 발표했습니다.
        
        **주요 경고:**
        - AI 에 의한 화이트칼라 대량 실업
        - 소비 붕괴와 디플레이션 악순환
        - S&P 500 의 8000 → 3500 붕괴 (2028 년 6 월)
        - 실업률 10.2% 도달
        
        **피해 예상 업종:**
        - 인도 IT 아웃소싱 (Wipro, Infosys, Accenture 등)
        - 전통 SaaS (Salesforce, Oracle, SAP 등)
        - 배달·결제 서비스 (DoorDash, American Express 등)
        - 고가 부동산 (Zillow, Redfin 등)
        - 화이트칼라 고용 의존 업종
        
        **출처:** Citrini Research "2028 Global Intelligence Crisis" (2026-02-22)
        
        **참고:** 이 데이터는 투자 참고용이며, 최종 투자 결정은 본인의 책임입니다.
        """)
