"""
SQLite 히스토리 DB 관리 + 백테스팅
────────────────────────────────────────────────────────────────
DB 파일 : stock_history.db
테이블  : screening_results  — 매일 매수/매도 추천 종목 저장
          macro_snapshots    — 거시지표 스냅샷 저장

사용법:
  from db_manager import save_screening, run_backtest, get_performance_summary
"""

import os
import sqlite3
import datetime
from typing import Optional

import yfinance as yf

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_history.db")


# ═══════════════════════════════════════════════════════════════
# 연결 및 초기화
# ═══════════════════════════════════════════════════════════════
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블/인덱스가 없으면 생성 (멱등 연산)"""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS screening_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT    NOT NULL,      -- YYYYMMDD
            run_at       TEXT    NOT NULL,      -- ISO 타임스탬프
            signal       TEXT    NOT NULL,      -- 'buy' | 'sell'
            rank         INTEGER NOT NULL,      -- 순위 (1~10)
            group_name   TEXT,                  -- 국내 / 미국 / 중국
            name         TEXT,
            ticker       TEXT,
            price        REAL,                  -- 당일 종가
            score        INTEGER,               -- 기술적 종합 점수
            dart_bonus   INTEGER DEFAULT 0,     -- DART 재무 보정점수
            rsi          REAL,
            macd_hist    REAL,
            bb_pct       REAL,
            vol_ratio    REAL,
            mom5         REAL,
            ma5          REAL,
            ma20         REAL,
            ma60         REAL,
            atr          REAL,                  -- 14일 ATR
            stop_loss    REAL,                  -- 손절가 (price - 2*ATR)
            target_price REAL                   -- 목표가 (price + 3*ATR)
        );

        CREATE TABLE IF NOT EXISTS macro_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL,
            run_at     TEXT    NOT NULL,
            indicator  TEXT    NOT NULL,
            value      REAL,
            change_pct REAL
        );

        CREATE INDEX IF NOT EXISTS idx_results_date   ON screening_results(date);
        CREATE INDEX IF NOT EXISTS idx_results_ticker ON screening_results(ticker);
        CREATE INDEX IF NOT EXISTS idx_results_signal ON screening_results(signal);
        CREATE INDEX IF NOT EXISTS idx_macro_date     ON macro_snapshots(date);

        CREATE TABLE IF NOT EXISTS ark_recommended (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT    NOT NULL,      -- YYYYMMDD
            run_at       TEXT    NOT NULL,      -- ISO 타임스탬프
            ticker       TEXT    NOT NULL,
            name         TEXT,
            market       TEXT,                  -- KOSPI/KOSDAQ/US
            theme        TEXT,                  -- ARK 테마명
            theme_key    TEXT,                  -- 테마 키 (1_대가속 등)
            price        REAL,                  -- 현재가
            change_1d    REAL,                  -- 1 일 등락률
            change_5d    REAL,                  -- 5 일 등락률
            change_20d   REAL,                  -- 20 일 등락률
            rsi          REAL,
            ma5          REAL,
            ma20         REAL,
            ma60         REAL,
            market_cap   INTEGER,               -- 시가총액
            pe           REAL,                  -- PER
            pb           REAL,                  -- PBR
            priority     TEXT,                  -- CORE/HIGH/MEDIUM
            reason       TEXT                   -- 추천 사유
        );

        CREATE INDEX IF NOT EXISTS idx_ark_date       ON ark_recommended(date);
        CREATE INDEX IF NOT EXISTS idx_ark_ticker     ON ark_recommended(ticker);
        CREATE INDEX IF NOT EXISTS idx_ark_theme      ON ark_recommended(theme_key);

        CREATE TABLE IF NOT EXISTS citrini_risky (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT    NOT NULL,      -- YYYYMMDD
            run_at       TEXT    NOT NULL,      -- ISO 타임스탬프
            ticker       TEXT    NOT NULL,
            name         TEXT,
            market       TEXT,                  -- US/KOSPI/KOSDAQ/India
            sector       TEXT,                  -- IT 아웃소싱/전통 SaaS/배달·결제/부동산 등
            risk_level   TEXT,                  -- HIGH/MEDIUM/LOW
            price        REAL,                  -- 현재가
            change_1d    REAL,                  -- 1 일 등락률
            change_5d    REAL,                  -- 5 일 등락률
            change_20d   REAL,                  -- 20 일 등락률
            rsi          REAL,
            ma5          REAL,
            ma20         REAL,
            ma60         REAL,
            market_cap   INTEGER,               -- 시가총액
            pe           REAL,                  -- PER
            pb           REAL,                  -- PBR
            reason       TEXT,                  -- 위험 사유
            exposure     TEXT                   -- 노출 요인
        );

        CREATE INDEX IF NOT EXISTS idx_citrini_date       ON citrini_risky(date);
        CREATE INDEX IF NOT EXISTS idx_citrini_ticker     ON citrini_risky(ticker);
        CREATE INDEX IF NOT EXISTS idx_citrini_risk       ON citrini_risky(risk_level);
        CREATE INDEX IF NOT EXISTS idx_citrini_sector     ON citrini_risky(sector);
        """)


# ═══════════════════════════════════════════════════════════════
# 저장
# ═══════════════════════════════════════════════════════════════
def save_screening(buy_top: list, sell_top: list, macro: dict):
    """
    스크리닝 결과를 DB에 저장한다.
    같은 날 중복 실행 시 기존 데이터를 유지하고 새 run_at으로 추가 저장.
    """
    init_db()
    now    = datetime.datetime.now()
    date   = now.strftime("%Y%m%d")
    run_at = now.isoformat(timespec="seconds")

    def _row(signal: str, rank: int, r: dict) -> tuple:
        return (
            date, run_at, signal, rank,
            r.get("group"), r.get("name"), r.get("ticker"),
            r.get("price"), r.get("score"), r.get("dart_bonus", 0),
            r.get("rsi"), r.get("macd_hist"), r.get("bb_pct"),
            r.get("vol_ratio"), r.get("mom5"),
            r.get("ma5"), r.get("ma20"), r.get("ma60"),
            r.get("atr"), r.get("stop_loss"), r.get("target_price"),
        )

    rows = (
        [_row("buy",  i + 1, r) for i, r in enumerate(buy_top)]
        + [_row("sell", i + 1, r) for i, r in enumerate(sell_top)]
    )

    macro_rows = [
        (date, run_at, k, v.get("현재"), v.get("등락(%)"))
        for k, v in macro.items()
    ]

    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO screening_results
            (date, run_at, signal, rank,
             group_name, name, ticker, price, score, dart_bonus,
             rsi, macd_hist, bb_pct, vol_ratio, mom5,
             ma5, ma20, ma60, atr, stop_loss, target_price)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)

        if macro_rows:
            conn.executemany("""
                INSERT INTO macro_snapshots
                (date, run_at, indicator, value, change_pct)
                VALUES (?,?,?,?,?)
            """, macro_rows)

    print(f"  [DB] {len(rows)}건 저장 완료 ({date})")


# ═══════════════════════════════════════════════════════════════
# 백테스팅
# ═══════════════════════════════════════════════════════════════
def run_backtest(days_back: int = 30) -> list:
    """
    N일 전부터 오늘까지의 매수 추천 종목 수익률을 계산한다.
    각 추천 종목의 진입가(추천 당일 종가) vs 현재가 비교.

    반환: [{entry_date, signal, rank, name, ticker,
            entry_price, current_price, return_pct,
            hit_stop, hit_target}]
    """
    init_db()
    cutoff = (
        datetime.date.today() - datetime.timedelta(days=days_back)
    ).strftime("%Y%m%d")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT date, signal, rank, name, ticker,
                   price AS entry_price, stop_loss, target_price, score
            FROM   screening_results
            WHERE  date >= ? AND signal = 'buy'
            GROUP  BY date, ticker           -- 같은 날 중복 run 제거 (최초 1건만)
            ORDER  BY date DESC
        """, (cutoff,)).fetchall()

    if not rows:
        return []

    # 현재가 일괄 조회 (중복 제거)
    tickers = list({r["ticker"] for r in rows})
    current_prices: dict = {}
    for tk in tickers:
        try:
            h = yf.Ticker(tk).history(period="3d")
            if not h.empty:
                current_prices[tk] = float(h["Close"].iloc[-1])
        except Exception:
            pass

    results = []
    for r in rows:
        cur = current_prices.get(r["ticker"])
        if cur is None:
            continue
        ep  = r["entry_price"]
        if not ep:
            continue

        ret        = round((cur - ep) / ep * 100, 2)
        hit_stop   = (cur < r["stop_loss"])    if r["stop_loss"]    else None
        hit_target = (cur > r["target_price"]) if r["target_price"] else None

        results.append({
            "entry_date":    r["date"],
            "signal":        r["signal"],
            "rank":          r["rank"],
            "name":          r["name"],
            "ticker":        r["ticker"],
            "entry_price":   round(ep, 2),
            "current_price": round(cur, 2),
            "return_pct":    ret,
            "hit_stop":      hit_stop,
            "hit_target":    hit_target,
        })

    return sorted(results, key=lambda x: x["return_pct"], reverse=True)


def get_performance_summary(days_back: int = 30) -> dict:
    """
    백테스팅 종합 성과 지표를 반환한다.

    반환: {종목수, 승률(%), 평균수익률, 최대수익률, 최대손실률,
           양수종목, 음수종목, 손절도달, 목표도달}
    """
    results = run_backtest(days_back)
    if not results:
        return {}

    rets = [r["return_pct"] for r in results if r["return_pct"] is not None]
    if not rets:
        return {}

    wins       = sum(1 for x in rets if x > 0)
    losses     = sum(1 for x in rets if x < 0)
    hit_stop   = sum(1 for r in results if r.get("hit_stop"))
    hit_target = sum(1 for r in results if r.get("hit_target"))

    return {
        "조회기간(일)": days_back,
        "종목수":       len(rets),
        "승률(%)":      round(wins / len(rets) * 100, 1),
        "평균수익률":   round(sum(rets) / len(rets), 2),
        "최대수익률":   round(max(rets), 2),
        "최대손실률":   round(min(rets), 2),
        "양수종목":     wins,
        "음수종목":     losses,
        "손절도달":     hit_stop,
        "목표도달":     hit_target,
    }


def get_latest_results(signal: str = "buy", limit: int = 10) -> list:
    """DB에서 가장 최근 추천 결과를 가져온다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT *
            FROM   screening_results
            WHERE  signal = ?
              AND  date = (SELECT MAX(date) FROM screening_results)
            ORDER  BY rank
            LIMIT  ?
        """, (signal, limit)).fetchall()
    return [dict(r) for r in rows]


def get_history_dates() -> list:
    """DB에 저장된 날짜 목록을 반환한다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM screening_results ORDER BY date DESC"
        ).fetchall()
    return [r["date"] for r in rows]


def get_results_by_date(date: str, signal: str = "buy") -> list:
    """특정 날짜의 추천 결과를 가져온다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM screening_results
            WHERE date = ? AND signal = ?
            ORDER BY rank
        """, (date, signal)).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# ARK 추천 종목 관리
# ═══════════════════════════════════════════════════════════════
def save_ark_recommended(ark_data: list):
    """
    ARK 추천 종목 데이터를 DB 에 저장한다.
    ark_data: [{ticker, name, market, themes, reasons, price, change_1d, ...}]
    """
    init_db()
    now = datetime.datetime.now()
    date = now.strftime("%Y%m%d")
    run_at = now.isoformat(timespec="seconds")

    rows = []
    for item in ark_data:
        themes = item.get("themes", [])
        reasons = item.get("reasons", [])
        for theme in themes:
            reason = reasons[themes.index(theme)] if theme.index(theme) < len(reasons) else ""
            rows.append((
                date, run_at,
                item.get("ticker"),
                item.get("name"),
                item.get("market"),
                theme,
                item.get("priority", "MEDIUM"),
                item.get("price"),
                item.get("change_1d"),
                item.get("change_5d"),
                item.get("change_20d"),
                item.get("rsi"),
                item.get("ma5"),
                item.get("ma20"),
                item.get("ma60"),
                item.get("market_cap"),
                item.get("pe"),
                item.get("pb"),
                reason,
            ))

    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO ark_recommended
            (date, run_at, ticker, name, market, theme_key, priority,
             price, change_1d, change_5d, change_20d,
             rsi, ma5, ma20, ma60, market_cap, pe, pb, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)

    print(f"  [DB] ARK 추천 종목 {len(rows)}건 저장 완료 ({date})")


def get_latest_ark_recommended(limit: int = 50) -> list:
    """DB 에서 가장 최근 ARK 추천 종목을 가져온다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT *
            FROM   ark_recommended
            WHERE  date = (SELECT MAX(date) FROM ark_recommended)
            ORDER  BY change_20d DESC
            LIMIT  ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_ark_history_dates() -> list:
    """ARK 추천 종목이 저장된 날짜 목록을 반환한다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM ark_recommended ORDER BY date DESC"
        ).fetchall()
    return [r["date"] for r in rows]


def get_ark_by_theme(theme_key: str, date: str = None) -> list:
    """특정 테마의 ARK 추천 종목을 가져온다."""
    init_db()
    if date is None:
        date = get_ark_history_dates()[0] if get_ark_history_dates() else None

    if not date:
        return []

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM ark_recommended
            WHERE date = ? AND theme_key = ?
            ORDER BY change_20d DESC
        """, (date, theme_key)).fetchall()
    return [dict(r) for r in rows]


def get_ark_performance_summary(days_back: int = 30) -> dict:
    """
    ARK 추천 종목의 최근 성과를 요약한다.
    """
    init_db()
    cutoff = (
        datetime.date.today() - datetime.timedelta(days=days_back)
    ).strftime("%Y%m%d")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker, name, theme_key, price, change_20d
            FROM   ark_recommended
            WHERE  date >= ?
            ORDER  BY date DESC
        """, (cutoff,)).fetchall()

    if not rows:
        return {}

    changes = [r["change_20d"] for r in rows if r["change_20d"] is not None]
    if not changes:
        return {}

    return {
        "종목수": len(changes),
        "평균 20 일수익률": round(sum(changes) / len(changes), 2),
        "최고수익률": round(max(changes), 2),
        "최저수익률": round(min(changes), 2),
        "양수비율": round(sum(1 for c in changes if c > 0) / len(changes) * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════
# Citrini 2028 부정적 종목 관리
# ═══════════════════════════════════════════════════════════════
def save_citrini_risky(citrini_data: list):
    """
    Citrini 2028 부정적 종목 데이터를 DB 에 저장한다.
    citrini_data: [{ticker, name, market, sector, risk_level, reason, price, ...}]
    """
    init_db()
    now = datetime.datetime.now()
    date = now.strftime("%Y%m%d")
    run_at = now.isoformat(timespec="seconds")

    rows = []
    for item in citrini_data:
        rows.append((
            date, run_at,
            item.get("ticker"),
            item.get("name"),
            item.get("market"),
            item.get("sector"),
            item.get("risk_level"),
            item.get("price"),
            item.get("change_1d"),
            item.get("change_5d"),
            item.get("change_20d"),
            item.get("rsi"),
            item.get("ma5"),
            item.get("ma20"),
            item.get("ma60"),
            item.get("market_cap"),
            item.get("pe"),
            item.get("pb"),
            item.get("reason"),
            item.get("exposure"),
        ))

    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO citrini_risky
            (date, run_at, ticker, name, market, sector, risk_level,
             price, change_1d, change_5d, change_20d,
             rsi, ma5, ma20, ma60, market_cap, pe, pb, reason, exposure)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)

    print(f"  [DB] Citrini 부정적 종목 {len(rows)}건 저장 완료 ({date})")


def get_latest_citrini_risky(limit: int = 50) -> list:
    """DB 에서 가장 최근 Citrini 부정적 종목을 가져온다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT *
            FROM   citrini_risky
            WHERE  date = (SELECT MAX(date) FROM citrini_risky)
            ORDER  BY 
                CASE risk_level 
                    WHEN 'HIGH' THEN 1 
                    WHEN 'MEDIUM' THEN 2 
                    WHEN 'LOW' THEN 3 
                END,
                change_20d ASC
            LIMIT  ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_citrini_history_dates() -> list:
    """Citrini 부정적 종목가 저장된 날짜 목록을 반환한다."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM citrini_risky ORDER BY date DESC"
        ).fetchall()
    return [r["date"] for r in rows]


def get_citrini_by_risk_level(risk_level: str, date: str = None) -> list:
    """특정 위험등급의 부정적 종목을 가져온다."""
    init_db()
    if date is None:
        date = get_citrini_history_dates()[0] if get_citrini_history_dates() else None

    if not date:
        return []

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM citrini_risky
            WHERE date = ? AND risk_level = ?
            ORDER BY change_20d ASC
        """, (date, risk_level)).fetchall()
    return [dict(r) for r in rows]


def get_citrini_by_sector(sector: str, date: str = None) -> list:
    """특정 섹터의 부정적 종목을 가져온다."""
    init_db()
    if date is None:
        date = get_citrini_history_dates()[0] if get_citrini_history_dates() else None

    if not date:
        return []

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM citrini_risky
            WHERE date = ? AND sector = ?
            ORDER BY change_20d ASC
        """, (date, sector)).fetchall()
    return [dict(r) for r in rows]


def get_citrini_performance_summary(days_back: int = 30) -> dict:
    """
    Citrini 부정적 종목의 최근 성과를 요약한다.
    """
    init_db()
    cutoff = (
        datetime.date.today() - datetime.timedelta(days=days_back)
    ).strftime("%Y%m%d")

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ticker, name, sector, risk_level, price, change_20d
            FROM   citrini_risky
            WHERE  date >= ?
            ORDER  BY date DESC
        """, (cutoff,)).fetchall()

    if not rows:
        return {}

    changes = [r["change_20d"] for r in rows if r["change_20d"] is not None]
    if not changes:
        return {}

    # 위험등급별 분석
    by_risk = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for r in rows:
        risk = r["risk_level"]
        if risk in by_risk and r["change_20d"] is not None:
            by_risk[risk].append(r["change_20d"])

    return {
        "종목수": len(changes),
        "평균 20 일수익률": round(sum(changes) / len(changes), 2),
        "최고수익률": round(max(changes), 2),
        "최저수익률": round(min(changes), 2),
        "양수비율": round(sum(1 for c in changes if c > 0) / len(changes) * 100, 1),
        "HIGH 위험평균": round(sum(by_risk["HIGH"]) / len(by_risk["HIGH"]), 2) if by_risk["HIGH"] else None,
        "MEDIUM 위험평균": round(sum(by_risk["MEDIUM"]) / len(by_risk["MEDIUM"]), 2) if by_risk["MEDIUM"] else None,
        "LOW 위험평균": round(sum(by_risk["LOW"]) / len(by_risk["LOW"]), 2) if by_risk["LOW"] else None,
    }


# ═══════════════════════════════════════════════════════════════
# CLI 실행 (직접 실행 시 백테스팅 결과 출력)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print(f"\n{'='*60}")
    print(f"  백테스팅 결과 ({days}일)")
    print(f"{'='*60}")

    perf = get_performance_summary(days)
    if not perf:
        print("  저장된 데이터 없음 (stock_advisor.py를 먼저 실행하세요)")
    else:
        for k, v in perf.items():
            label = f"  {k:12s}"
            if isinstance(v, float):
                print(f"{label}: {v:+.2f}" if "률" in k else f"{label}: {v:.1f}")
            else:
                print(f"{label}: {v}")

        print(f"\n{'─'*60}")
        print(f"  {'날짜':8s}  {'순위':4s}  {'종목명':14s}  {'진입가':>10}  {'현재가':>10}  {'수익률':>8}  {'비고':6s}")
        print(f"{'─'*60}")
        for r in run_backtest(days):
            flag = ""
            if r.get("hit_stop"):    flag = "🔴손절"
            elif r.get("hit_target"): flag = "🟢목표"
            ret  = r["return_pct"]
            sign = "+" if ret >= 0 else ""
            print(f"  {r['entry_date']:8s}  {r['rank']:4d}  {r['name']:14s}  "
                  f"{r['entry_price']:>10,.0f}  {r['current_price']:>10,.0f}  "
                  f"{sign}{ret:>7.2f}%  {flag}")
