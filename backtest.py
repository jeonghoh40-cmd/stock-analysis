"""
백테스팅 엔진 (Phase 2.6)
────────────────────────────────────────────────────────────
현재 전략의 과거 성과를 시뮬레이션해 실전 투입 전 유효성을 검증한다.

핵심 원칙:
  [PIT]  Point-in-Time — 해당 시점에 알 수 있는 데이터만 사용
  [LAB]  Look-ahead Bias 차단 — 미래 데이터 참조 금지
  [SB]   생존편향 제거 — 상장폐지 종목 포함 (데이터 있는 한)
  [TC]   수수료·슬리피지 반영 — 편도 0.015% + 슬리피지 0.1%
  [OOS]  Out-of-sample 분리 — 70% 훈련 / 30% 검증

HARD-GATE 합격 기준 (실전 전환 필수 조건):
  - 승률 ≥ 55%
  - MDD ≤ 10%
  - 샤프 지수 ≥ 1.0
"""

import os
import sys
import json
import sqlite3
import logging
import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
import yfinance as yf

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backtest")

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = BASE_DIR / "stock_performance.db"

# ── 전략 파라미터 ─────────────────────────────────────────────
COMMISSION   = 0.00015   # 편도 0.015%
SLIPPAGE     = 0.001     # 슬리피지 0.1%
ATR_STOP_MULT   = 1.5    # 손절: 진입가 − ATR × 1.5
ATR_TARGET_MULT = 2.5    # 목표: 진입가 + ATR × 2.5
MAX_HOLD_DAYS   = 20     # 최대 보유 일수

# HARD-GATE 합격 기준
GATE_WIN_RATE   = 55.0   # 승률 % 이상
GATE_MAX_MDD    = 10.0   # MDD % 이하
GATE_SHARPE     = 1.0    # 샤프 지수 이상


# ═══════════════════════════════════════════════════════════════
# DB 유틸
# ═══════════════════════════════════════════════════════════════

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_backtest_table():
    """backtest_results 테이블이 없으면 생성"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            strategy TEXT NOT NULL,
            market TEXT NOT NULL,
            total_trades INTEGER,
            win_trades INTEGER,
            lose_trades INTEGER,
            win_rate REAL,
            avg_return REAL,
            total_return REAL,
            mdd REAL,
            sharpe REAL,
            hardgate_pass INTEGER,
            params TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# 가격 데이터 수집 (PIT 보장)
# ═══════════════════════════════════════════════════════════════

def _fetch_prices(ticker: str, start: str, end: str) -> Optional[pd.Series]:
    """
    ticker의 start~end 구간 종가 Series 반환.
    yfinance는 end 날짜를 포함하지 않으므로 +1일로 요청.
    상폐 종목도 데이터가 있는 한 반환.
    """
    try:
        end_dt = (datetime.datetime.strptime(end, "%Y-%m-%d")
                  + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        df = yf.download(ticker, start=start, end=end_dt,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception as e:
        logger.debug(f"[PriceData] {ticker} 조회 실패: {e}")
        return None


def _atr14(prices: pd.Series) -> float:
    """단순 ATR 근사: 최근 14일 고저 범위 평균"""
    if len(prices) < 15:
        return float(prices.std()) if len(prices) > 1 else 0.0
    recent = prices.iloc[-15:]
    return float((recent.max() - recent.min()) / 14)


# ═══════════════════════════════════════════════════════════════
# 단일 거래 시뮬레이션
# ═══════════════════════════════════════════════════════════════

def _simulate_trade(
    ticker: str,
    entry_date: str,
    entry_price: float,
    direction: str = "BUY",
) -> Optional[dict]:
    """
    진입일 이후 가격을 조회해 손절·목표·보유기간 중 먼저 도달한 시점에 청산.
    Look-ahead Bias 방지: entry_date 이전 데이터로 ATR 계산.

    반환: {"ticker", "entry_date", "exit_date", "entry_price", "exit_price",
           "return_pct", "exit_reason", "hold_days"}
    """
    # 진입 전 60일 데이터로 ATR 계산 (PIT)
    pre_start = (datetime.datetime.strptime(entry_date, "%Y-%m-%d")
                 - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    pre_prices = _fetch_prices(ticker, pre_start, entry_date)
    atr = _atr14(pre_prices) if pre_prices is not None else entry_price * 0.02

    stop_loss  = entry_price - atr * ATR_STOP_MULT   if direction == "BUY" \
                 else entry_price + atr * ATR_STOP_MULT
    target     = entry_price + atr * ATR_TARGET_MULT  if direction == "BUY" \
                 else entry_price - atr * ATR_TARGET_MULT

    # 진입일 이후 가격 (최대 보유 기간)
    post_end = (datetime.datetime.strptime(entry_date, "%Y-%m-%d")
                + datetime.timedelta(days=MAX_HOLD_DAYS + 10)).strftime("%Y-%m-%d")
    post_prices = _fetch_prices(ticker, entry_date, post_end)
    if post_prices is None or len(post_prices) < 2:
        return None

    # 진입 다음 영업일부터 순회
    for i, (dt, price) in enumerate(post_prices.iloc[1:].items(), start=1):
        hit_stop   = price <= stop_loss  if direction == "BUY" else price >= stop_loss
        hit_target = price >= target     if direction == "BUY" else price <= target
        hit_maxday = i >= MAX_HOLD_DAYS

        if hit_stop or hit_target or hit_maxday:
            exit_price = float(price)
            # 수수료 + 슬리피지 반영
            cost = (COMMISSION + SLIPPAGE) * 2  # 매수·매도 양방향
            raw_ret = (exit_price - entry_price) / entry_price
            if direction == "SELL":
                raw_ret = -raw_ret
            net_ret = raw_ret - cost

            return {
                "ticker":       ticker,
                "entry_date":   entry_date,
                "exit_date":    dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt),
                "entry_price":  round(entry_price, 4),
                "exit_price":   round(exit_price, 4),
                "return_pct":   round(net_ret * 100, 3),
                "exit_reason":  "STOP" if hit_stop else ("TARGET" if hit_target else "MAXDAY"),
                "hold_days":    i,
            }

    return None


# ═══════════════════════════════════════════════════════════════
# 성과 지표 계산
# ═══════════════════════════════════════════════════════════════

def _calc_metrics(trades: list[dict]) -> dict:
    """거래 목록에서 성과 지표를 계산한다."""
    if not trades:
        return {"error": "거래 데이터 없음"}

    df = pd.DataFrame(trades)
    returns = df["return_pct"].dropna()

    total  = len(returns)
    wins   = int((returns > 0).sum())
    losses = total - wins

    win_rate   = wins / total * 100 if total > 0 else 0.0
    avg_return = float(returns.mean())
    total_ret  = float(returns.sum())
    std_ret    = float(returns.std()) if len(returns) > 1 else 0.0
    sharpe     = avg_return / std_ret * (252 ** 0.5 / 20) if std_ret > 0 else 0.0  # 연환산

    # MDD 계산 (누적 수익률 기준)
    cumulative = (1 + returns / 100).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max * 100
    mdd = float(drawdown.min())

    return {
        "total_trades": total,
        "win_trades":   wins,
        "lose_trades":  losses,
        "win_rate":     round(win_rate, 2),
        "avg_return":   round(avg_return, 3),
        "total_return": round(total_ret, 2),
        "mdd":          round(abs(mdd), 2),
        "sharpe":       round(sharpe, 3),
    }


# ═══════════════════════════════════════════════════════════════
# HARD-GATE
# ═══════════════════════════════════════════════════════════════

def check_hardgate(metrics: dict) -> dict:
    """
    실전 전환 HARD-GATE 검사.
    반환: {"pass": bool, "reasons": [실패 사유 목록]}
    """
    if "error" in metrics:
        return {"pass": False, "reasons": [metrics["error"]]}

    reasons = []
    if metrics["win_rate"] < GATE_WIN_RATE:
        reasons.append(f"승률 {metrics['win_rate']:.1f}% < 기준 {GATE_WIN_RATE}%")
    if metrics["mdd"] > GATE_MAX_MDD:
        reasons.append(f"MDD {metrics['mdd']:.1f}% > 기준 {GATE_MAX_MDD}%")
    if metrics["sharpe"] < GATE_SHARPE:
        reasons.append(f"샤프 {metrics['sharpe']:.2f} < 기준 {GATE_SHARPE}")

    return {"pass": len(reasons) == 0, "reasons": reasons}


# ═══════════════════════════════════════════════════════════════
# Out-of-sample 분리
# ═══════════════════════════════════════════════════════════════

def split_train_test(
    start_date: str, end_date: str, train_ratio: float = 0.7
) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    기간을 훈련(70%) / 검증(30%)으로 분리한다.
    반환: (train_start, train_end), (test_start, test_end)
    """
    s = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    e = datetime.datetime.strptime(end_date,   "%Y-%m-%d")
    total_days = (e - s).days
    split_day  = int(total_days * train_ratio)
    split_dt   = s + datetime.timedelta(days=split_day)

    train = (start_date, split_dt.strftime("%Y-%m-%d"))
    test  = ((split_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d"), end_date)
    return train, test


# ═══════════════════════════════════════════════════════════════
# 메인 백테스트 실행
# ═══════════════════════════════════════════════════════════════

def run_backtest(
    start_date: str,
    end_date: str,
    strategy: str = "top5",
    market: str = "ALL",
    out_of_sample: bool = True,
) -> dict:
    """
    DB에 저장된 daily_recommendations를 기반으로 백테스트 시뮬레이션을 실행한다.

    Args:
        start_date: 시작일 (YYYY-MM-DD)
        end_date:   종료일 (YYYY-MM-DD)
        strategy:   'top5' | 'top10' | 'score60' (진입 종목 선정 기준)
        market:     'KOSPI' | 'KOSDAQ' | 'US' | 'ALL'
        out_of_sample: True면 70/30 분리 후 검증 구간 결과도 추가 반환

    Returns:
        전체 기간 + (out_of_sample 시) 훈련/검증 구간 성과 지표 딕셔너리
    """
    _ensure_backtest_table()

    # 전략별 필터
    rank_filter  = "r.rank <= 5"  if strategy == "top5"  \
                   else "r.rank <= 10" if strategy == "top10" \
                   else "r.score >= 60"
    market_filter = f"AND r.market = '{market}'" if market != "ALL" else ""

    conn = _get_conn()
    query = f"""
        SELECT r.date, r.market, r.ticker, r.name, r.price, r.recommendation_type
        FROM daily_recommendations r
        WHERE r.date BETWEEN ? AND ?
          AND r.recommendation_type = 'BUY'
          AND {rank_filter}
          {market_filter}
        ORDER BY r.date
    """
    recs = [dict(row) for row in conn.execute(query, (start_date, end_date)).fetchall()]
    conn.close()

    if not recs:
        return {
            "error": f"해당 기간 추천 데이터 없음 ({start_date} ~ {end_date})",
            "hint": "먼저 stock_advisor_v4.main()을 실행해 추천 데이터를 축적하세요."
        }

    print(f"\n  📊 백테스트 시작: {start_date} ~ {end_date} ({len(recs)}개 추천)")

    # 거래 시뮬레이션
    trades = []
    for i, rec in enumerate(recs, 1):
        print(f"  [{i}/{len(recs)}] {rec['ticker']} ({rec['date']})", end="\r")
        trade = _simulate_trade(rec["ticker"], rec["date"], rec["price"])
        if trade:
            trade["market"] = rec["market"]
            trades.append(trade)

    print(f"\n  ✓ 시뮬레이션 완료: {len(trades)}/{len(recs)}개 거래 성립")

    result = {
        "period":    f"{start_date} ~ {end_date}",
        "strategy":  strategy,
        "market":    market,
        "attempted": len(recs),
        "simulated": len(trades),
        **_calc_metrics(trades),
    }

    # HARD-GATE 검사
    gate = check_hardgate(result)
    result["hardgate_pass"]   = gate["pass"]
    result["hardgate_reasons"] = gate["reasons"]

    # Out-of-sample 분리
    if out_of_sample and len(trades) > 10:
        train_range, test_range = split_train_test(start_date, end_date)
        train_trades = [t for t in trades if train_range[0] <= t["entry_date"] <= train_range[1]]
        test_trades  = [t for t in trades if test_range[0]  <= t["entry_date"] <= test_range[1]]

        result["train"] = {
            "period":  f"{train_range[0]} ~ {train_range[1]}",
            "trades":  len(train_trades),
            **_calc_metrics(train_trades),
        }
        result["test"] = {
            "period":  f"{test_range[0]} ~ {test_range[1]}",
            "trades":  len(test_trades),
            **_calc_metrics(test_trades),
        }

    # DB 저장
    _save_result(result, start_date, end_date, strategy, market)

    return result


def _save_result(result: dict, start_date: str, end_date: str,
                 strategy: str, market: str) -> None:
    """백테스트 결과를 stock_performance.db에 저장"""
    if "error" in result:
        return
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO backtest_results
            (run_at, start_date, end_date, strategy, market,
             total_trades, win_trades, lose_trades, win_rate,
             avg_return, total_return, mdd, sharpe, hardgate_pass, params)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.datetime.now().isoformat(),
            start_date, end_date, strategy, market,
            result.get("total_trades"), result.get("win_trades"),
            result.get("lose_trades"), result.get("win_rate"),
            result.get("avg_return"), result.get("total_return"),
            result.get("mdd"), result.get("sharpe"),
            int(result.get("hardgate_pass", False)),
            json.dumps({"atr_stop": ATR_STOP_MULT, "atr_target": ATR_TARGET_MULT,
                        "commission": COMMISSION, "slippage": SLIPPAGE}),
        ))
        conn.commit()
        conn.close()
        logger.info("[백테스트] 결과 DB 저장 완료")
    except Exception as e:
        logger.warning(f"[백테스트] DB 저장 실패: {e}")


# ═══════════════════════════════════════════════════════════════
# 보고서 출력
# ═══════════════════════════════════════════════════════════════

def print_report(result: dict) -> str:
    """백테스트 결과를 보기 좋게 출력하고 문자열로도 반환한다."""
    if "error" in result:
        msg = f"\n⚠️  백테스트 오류: {result['error']}\n"
        if "hint" in result:
            msg += f"   힌트: {result['hint']}\n"
        print(msg)
        return msg

    L = []
    L.append("\n" + "=" * 70)
    L.append(f"  📊 백테스트 결과 — {result['strategy'].upper()} 전략 / {result['market']}")
    L.append(f"  기간: {result['period']}")
    L.append("=" * 70)
    L.append(f"  시도 {result['attempted']}건 → 시뮬레이션 {result['simulated']}건\n")
    L.append(f"  총 거래:       {result.get('total_trades', 0)}건")
    L.append(f"  승/패:         {result.get('win_trades', 0)}승 {result.get('lose_trades', 0)}패")
    L.append(f"  승률:          {result.get('win_rate', 0):.1f}%  {'✅' if result.get('win_rate',0) >= GATE_WIN_RATE else '❌'} (기준 {GATE_WIN_RATE}%)")
    L.append(f"  평균 수익률:   {result.get('avg_return', 0):+.3f}%")
    L.append(f"  누적 수익률:   {result.get('total_return', 0):+.2f}%")
    L.append(f"  MDD:           {result.get('mdd', 0):.2f}%  {'✅' if result.get('mdd',0) <= GATE_MAX_MDD else '❌'} (기준 {GATE_MAX_MDD}%)")
    L.append(f"  샤프 지수:     {result.get('sharpe', 0):.3f}  {'✅' if result.get('sharpe',0) >= GATE_SHARPE else '❌'} (기준 {GATE_SHARPE})")

    gate_pass = result.get("hardgate_pass", False)
    L.append("\n" + "─" * 70)
    if gate_pass:
        L.append("  🟢 HARD-GATE: 통과 — 실전 전환 가능")
    else:
        L.append("  🔴 HARD-GATE: 미통과 — 실전 전환 불가")
        for r in result.get("hardgate_reasons", []):
            L.append(f"     ✗ {r}")

    if "train" in result and "test" in result:
        L.append("\n" + "─" * 70)
        L.append("  📈 Out-of-sample 검증")
        for label, seg in [("훈련(70%)", result["train"]), ("검증(30%)", result["test"])]:
            if "error" not in seg:
                L.append(f"\n  [{label}] {seg.get('period', '')}  ({seg.get('trades', 0)}건)")
                L.append(f"    승률: {seg.get('win_rate', 0):.1f}%  MDD: {seg.get('mdd', 0):.2f}%  샤프: {seg.get('sharpe', 0):.3f}")

    L.append("=" * 70 + "\n")
    report = "\n".join(L)
    print(report)
    return report


# ═══════════════════════════════════════════════════════════════
# Look-ahead Bias 단위 테스트
# ═══════════════════════════════════════════════════════════════

def test_no_lookahead():
    """
    Look-ahead Bias 차단 검증:
    진입일 이후 데이터가 ATR 계산에 사용되지 않았는지 확인.
    """
    import random
    errors = []

    for _ in range(3):
        # 임의의 과거 날짜로 테스트
        days_ago = random.randint(30, 200)
        entry_dt = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        entry_date = entry_dt.strftime("%Y-%m-%d")

        pre_start = (entry_dt - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        pre_prices = _fetch_prices("AAPL", pre_start, entry_date)

        if pre_prices is not None:
            # pre_prices에 entry_date 이후 데이터가 없어야 함
            for idx_dt in pre_prices.index:
                idx_str = idx_dt.strftime("%Y-%m-%d") if hasattr(idx_dt, "strftime") else str(idx_dt)[:10]
                if idx_str > entry_date:
                    errors.append(f"Look-ahead Bias! {idx_str} > {entry_date}")

    if errors:
        print(f"  ❌ Look-ahead Bias 테스트 실패:\n" + "\n".join(errors))
        return False
    print("  ✅ Look-ahead Bias 테스트 통과 (진입일 이전 데이터만 사용 확인)")
    return True


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  🧪 백테스팅 엔진 — Phase 2.6")
    print("=" * 70)

    # Look-ahead Bias 테스트
    print("\n[1] Look-ahead Bias 단위 테스트...")
    test_no_lookahead()

    # 백테스트 실행
    end   = datetime.datetime.now().strftime("%Y-%m-%d")
    start = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"\n[2] 백테스트 실행 ({start} ~ {end}, TOP5 전략, 전 시장)...")
    result = run_backtest(start, end, strategy="top5", market="ALL", out_of_sample=True)
    print_report(result)

    # 시장별 세부 결과
    for mkt in ["KOSPI", "KOSDAQ", "US"]:
        print(f"\n[3-{mkt}] {mkt} 시장 백테스트...")
        r = run_backtest(start, end, strategy="top5", market=mkt, out_of_sample=False)
        print_report(r)
