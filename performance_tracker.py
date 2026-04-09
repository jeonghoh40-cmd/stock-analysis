"""
성능 추적 및 학습 모듈
- 매일의 추천 결과를 SQLite 데이터베이스에 저장
- 추천 정확도 추적 (수익률, 승률, 평균 수익 등)
- 백테스팅 기능
- 정확도 기반 투자자 가중치 자동 조정
- 성능 리포트 생성
"""

import os
import sys
import json
import sqlite3
import datetime
import pandas as pd
from typing import Optional, Dict, List
from dotenv import dotenv_values

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── .env 로드 ─────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_cfg = dotenv_values(_env_path)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'stock_performance.db')


# ═══════════════════════════════════════════════════════════════
# 데이터베이스 관리
# ═══════════════════════════════════════════════════════════════

def init_database():
    """
    성능 추적용 SQLite 데이터베이스 초기화
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 일일 추천 기록 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            market TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            rank INTEGER NOT NULL,
            score REAL NOT NULL,
            price REAL NOT NULL,
            rsi REAL,
            macd_hist REAL,
            ma5 REAL,
            ma20 REAL,
            ma60 REAL,
            investor_tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 같은 날 같은 티커+타입 중복 저장 방지 (rank 무관)
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_recommendation
        ON daily_recommendations(date, ticker, recommendation_type)
    ''')
    
    # 2. 일별 가격 변동 테이블 (추천 후 성과 추적)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            day_after INTEGER NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            return_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recommendation_id) REFERENCES daily_recommendations(id)
        )
    ''')
    
    # 3. 투자자별 성능 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investor_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            recommendation_date TEXT NOT NULL,
            initial_price REAL NOT NULL,
            current_price REAL,
            return_pct REAL,
            is_profitable INTEGER,
            tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 4. 일일 종합 성능 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_recommendations INTEGER,
            buy_count INTEGER,
            sell_count INTEGER,
            avg_buy_score REAL,
            avg_sell_score REAL,
            kospi_return REAL,
            kosdaq_return REAL,
            sp500_return REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 5. 모델 설정 테이블 (가중치 등)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value REAL NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 기본 가중치 초기화
    default_weights = {
        'pelosi_base_weight': 10.0,
        'ark_base_weight': 8.0,
        'korean_investor_base_weight': 5.0,
        'technical_score_ratio': 0.7,
        'investor_score_ratio': 0.3,
    }
    
    for key, value in default_weights.items():
        cursor.execute('''
            INSERT OR IGNORE INTO model_config (config_key, config_value)
            VALUES (?, ?)
        ''', (key, value))
    
    conn.commit()
    conn.close()
    print(f"  ✓ 데이터베이스 초기화 완료: {DB_PATH}")


def get_db_connection():
    """
    데이터베이스 연결 반환
    """
    if not os.path.exists(DB_PATH):
        init_database()
    return sqlite3.connect(DB_PATH)


# ═══════════════════════════════════════════════════════════════
# 추천 결과 저장
# ═══════════════════════════════════════════════════════════════

def save_daily_recommendations(date: str, recommendations: Dict[str, List[dict]]):
    """
    일일 추천 결과를 데이터베이스에 저장
    
    Args:
        date: 날짜 (YYYY-MM-DD)
        recommendations: {
            'kospi_buy': [...],
            'kospi_sell': [...],
            'kosdaq_buy': [...],
            'kosdaq_sell': [...],
            'us_buy': [...],
            'us_sell': [...]
        }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    market_map = {
        'kospi': 'KOSPI',
        'kosdaq': 'KOSDAQ',
        'us': 'US',
        'ipo': 'IPO',
    }
    
    for key, recs in recommendations.items():
        parts = key.split('_')
        if len(parts) != 2:
            continue

        market_key, rec_type = parts
        market = market_map.get(market_key, market_key.upper())
        rec_type = rec_type.upper()  # BUY or SELL

        for rank, rec in enumerate(recs, 1):
            # 투자자 태그 문자열 변환
            investor_tags = rec.get('investor_tags', '해당없음')
            if isinstance(investor_tags, list):
                investor_tags = ','.join(investor_tags)

            # entry price 유효성 검증: 0 이하이거나 비정상적으로 낮은 값 방어
            entry_price = rec.get('price')
            if not entry_price or entry_price <= 0:
                print(f"  ⚠️ {rec['ticker']} entry price 오류({entry_price}), 저장 건너뜀")
                continue

            cursor.execute('''
                INSERT OR IGNORE INTO daily_recommendations
                (date, market, ticker, name, recommendation_type, rank, score,
                 price, rsi, macd_hist, ma5, ma20, ma60, investor_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, market, rec['ticker'], rec['name'], rec_type, rank,
                rec['score'], entry_price, rec.get('rsi'), rec.get('macd_hist'),
                rec.get('ma5'), rec.get('ma20'), rec.get('ma60'), investor_tags
            ))
    
    conn.commit()
    conn.close()
    print(f"  ✓ {date} 추천 데이터 저장 완료 ({sum(len(v) for v in recommendations.values())}개)")


# ═══════════════════════════════════════════════════════════════
# 가격 추적 및 수익률 계산
# ═══════════════════════════════════════════════════════════════

def update_price_tracking(target_date: str = None):
    """
    저장된 추천 종목들의 가격 추적 업데이트
    추천일로부터 1 일, 3 일, 5 일, 10 일, 20 일 후 수익률 계산

    수정: (recommendation_id, day_after) 조합별로 개별 체크하여
    일부 day_after만 누락된 경우에도 채울 수 있도록 개선
    """
    if target_date is None:
        target_date = datetime.datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 모든 추천 종목 조회 (미래 추천일은 제외)
    cursor.execute('''
        SELECT DISTINCT id, ticker, date, price
        FROM daily_recommendations
        WHERE date <= ?
        ORDER BY date
    ''', (target_date,))

    recommendations = cursor.fetchall()

    import yfinance as yf

    DAY_AFTERS = [1, 3, 5, 10, 20]

    for rec_id, ticker, rec_date, initial_price in recommendations:
        # 이 추천에 대해 아직 없는 day_after 목록만 추출
        cursor.execute('''
            SELECT day_after FROM price_tracking
            WHERE recommendation_id = ?
        ''', (rec_id,))
        existing_days = {row[0] for row in cursor.fetchall()}

        # 각 day_after 별로 대상일이 오늘 이전인지 확인 후 누락분만 선별
        missing_days = []
        for day_after in DAY_AFTERS:
            if day_after in existing_days:
                continue
            # 거래일 기준이 아닌 단순 캘린더 기준으로 필터 (실제 거래일은 df 길이로 판단)
            # 추천일 + day_after 캘린더 일수가 오늘 이전이면 처리 대상
            try:
                rec_dt = datetime.datetime.strptime(rec_date, '%Y-%m-%d')
                expected_dt = rec_dt + datetime.timedelta(days=day_after)
                if expected_dt.strftime('%Y-%m-%d') < target_date:
                    missing_days.append(day_after)
            except ValueError:
                missing_days.append(day_after)

        if not missing_days:
            continue

        try:
            # 추천일 이후 가격 데이터 조회 (auto_adjust=True 기본값: 배당·분할 조정 종가)
            df = yf.Ticker(ticker).history(start=rec_date, auto_adjust=True, timeout=10)

            if df.empty or len(df) < 2:
                continue

            close_col = df['Close']

            # 누락된 day_after 만 INSERT
            # NOTE: day_after는 거래일 인덱스 (캘린더일 아님).
            # yfinance DataFrame은 거래일만 포함하므로 iloc[5] = 5거래일 후.
            for day_after in missing_days:
                if len(df) <= day_after:
                    continue

                close_price = float(close_col.iloc[day_after])
                if initial_price and initial_price > 0:
                    return_pct = ((close_price - initial_price) / initial_price) * 100
                else:
                    return_pct = 0.0

                cursor.execute('''
                    INSERT INTO price_tracking
                    (recommendation_id, ticker, date, day_after, close_price, return_pct)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (rec_id, ticker, rec_date, day_after, close_price, return_pct))

        except Exception as e:
            print(f"  ⚠️ {ticker} 가격 추적 실패: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"  ✓ 가격 추적 업데이트 완료")


# ═══════════════════════════════════════════════════════════════
# 추천 검증 (과거 추천 실적 집계)
# ═══════════════════════════════════════════════════════════════

def verify_past_recommendations() -> dict:
    """
    추천일 기준 1/3/5/10/20일 후 성과를 집계해 반환.
    충분한 데이터가 있는 기간(day_after)만 포함.

    반환 구조:
    {
        "by_period": {
            5: {
                "buy_count": int, "buy_win_rate": float, "buy_avg_return": float,
                "sell_count": int, "sell_win_rate": float, "sell_avg_return": float,
                "by_market": {"KOSPI": {...}, "KOSDAQ": {...}, "US": {...}}
            },
            ...  # 데이터 있는 day_after만
        },
        "recent_results": [  # 최근 20거래일 내 추천의 5일 성과
            {
                "date": str, "market": str, "ticker": str, "name": str,
                "type": "BUY"/"SELL", "rank": int,
                "entry_price": float, "exit_price": float,
                "return_pct": float, "result": "HIT"/"MISS"
            }, ...
        ],
        "summary": {
            "best_day_after": int,
            "overall_buy_win_rate": float,
            "overall_sell_win_rate": float,
            "total_verified": int,
        }
    }
    """
    try:
        conn = get_db_connection()

        # ── 기간별 집계 ────────────────────────────────────────────
        # 이상값 필터 기준: 기간별 최대 허용 수익률
        # 과거 장중 스냅샷 오류로 기록된 비정상 수익률 제거
        _OUTLIER = {1: 20, 3: 25, 5: 30, 10: 40, 20: 60}

        by_period = {}
        for day_after in [1, 3, 5, 10, 20]:
            limit = _OUTLIER[day_after]
            # 전체 매수 집계 (이상값 제외)
            query_buy = '''
                SELECT
                    COUNT(*) as cnt,
                    SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(p.return_pct) as avg_ret
                FROM daily_recommendations r
                INNER JOIN price_tracking p
                    ON r.id = p.recommendation_id AND p.day_after = ?
                WHERE r.recommendation_type = 'BUY'
                  AND ABS(p.return_pct) < ?
            '''
            cur = conn.cursor()
            cur.execute(query_buy, (day_after, limit))
            row = cur.fetchone()
            buy_count = row[0] or 0
            buy_wins  = row[1] or 0
            buy_avg   = row[2] or 0.0

            # 전체 매도 집계 (음수 수익률이 HIT, 이상값 제외)
            query_sell = '''
                SELECT
                    COUNT(*) as cnt,
                    SUM(CASE WHEN p.return_pct < 0 THEN 1 ELSE 0 END) as wins,
                    AVG(p.return_pct) as avg_ret
                FROM daily_recommendations r
                INNER JOIN price_tracking p
                    ON r.id = p.recommendation_id AND p.day_after = ?
                WHERE r.recommendation_type = 'SELL'
                  AND ABS(p.return_pct) < ?
            '''
            cur.execute(query_sell, (day_after, limit))
            row = cur.fetchone()
            sell_count = row[0] or 0
            sell_wins  = row[1] or 0
            sell_avg   = row[2] or 0.0

            total_count = buy_count + sell_count
            if total_count == 0:
                continue

            buy_win_rate  = (buy_wins / buy_count * 100)   if buy_count  > 0 else 0.0
            sell_win_rate = (sell_wins / sell_count * 100) if sell_count > 0 else 0.0

            # 시장별 집계 (이상값 제외)
            by_market = {}
            for market in ('KOSPI', 'KOSDAQ', 'US'):
                cur.execute('''
                    SELECT
                        COUNT(*) as cnt,
                        SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) as wins,
                        AVG(p.return_pct) as avg_ret
                    FROM daily_recommendations r
                    INNER JOIN price_tracking p
                        ON r.id = p.recommendation_id AND p.day_after = ?
                    WHERE r.recommendation_type = 'BUY' AND r.market = ?
                      AND ABS(p.return_pct) < ?
                ''', (day_after, market, limit))
                mrow = cur.fetchone()
                mcnt = mrow[0] or 0
                if mcnt > 0:
                    by_market[market] = {
                        "buy_count":    mcnt,
                        "buy_win_rate": round((mrow[1] or 0) / mcnt * 100, 1),
                        "buy_avg_return": round(mrow[2] or 0.0, 2),
                    }

            by_period[day_after] = {
                "buy_count":      buy_count,
                "buy_win_rate":   round(buy_win_rate, 1),
                "buy_avg_return": round(buy_avg, 2),
                "sell_count":     sell_count,
                "sell_win_rate":  round(sell_win_rate, 1),
                "sell_avg_return": round(sell_avg, 2),
                "by_market":      by_market,
            }

        # ── 최근 20거래일 내 추천의 5일 성과 ──────────────────────
        recent_results = []
        cur.execute('''
            SELECT
                r.date, r.market, r.ticker, r.name,
                r.recommendation_type, r.rank, r.price,
                p.close_price, p.return_pct
            FROM daily_recommendations r
            INNER JOIN price_tracking p
                ON r.id = p.recommendation_id AND p.day_after = 5
            WHERE r.date >= date('now', '-30 days')
              AND ABS(p.return_pct) < 30
            ORDER BY r.date DESC, r.recommendation_type, r.rank
            LIMIT 50
        ''')
        for row in cur.fetchall():
            date_, market, ticker, name, rtype, rank, entry, exit_, ret = row
            if ret is None:
                continue
            # BUY면 수익(양수)=HIT, SELL이면 손실(음수)=HIT
            if rtype == 'BUY':
                result = 'HIT' if ret > 0 else 'MISS'
            else:
                result = 'HIT' if ret < 0 else 'MISS'
            recent_results.append({
                "date":        date_,
                "market":      market,
                "ticker":      ticker,
                "name":        name,
                "type":        rtype,
                "rank":        rank,
                "entry_price": entry,
                "exit_price":  exit_,
                "return_pct":  round(ret, 2),
                "result":      result,
            })

        conn.close()

        # ── 요약 ───────────────────────────────────────────────────
        total_verified = sum(
            v["buy_count"] + v["sell_count"] for v in by_period.values()
        )

        # 가장 승률 높은 day_after (매수 기준)
        best_day_after = 5
        best_rate = -1.0
        for d, v in by_period.items():
            if v["buy_count"] >= 3 and v["buy_win_rate"] > best_rate:
                best_rate = v["buy_win_rate"]
                best_day_after = d

        # 전체 매수/매도 승률 (5일 기준)
        p5 = by_period.get(5, {})
        overall_buy_win_rate  = p5.get("buy_win_rate",  0.0)
        overall_sell_win_rate = p5.get("sell_win_rate", 0.0)

        return {
            "by_period":     by_period,
            "recent_results": recent_results,
            "summary": {
                "best_day_after":       best_day_after,
                "overall_buy_win_rate": overall_buy_win_rate,
                "overall_sell_win_rate": overall_sell_win_rate,
                "total_verified":       total_verified,
            },
        }

    except Exception as e:
        print(f"  ⚠️ verify_past_recommendations 실패: {e}")
        return {"by_period": {}, "recent_results": [], "summary": {
            "best_day_after": 5,
            "overall_buy_win_rate": 0.0,
            "overall_sell_win_rate": 0.0,
            "total_verified": 0,
        }}


def format_verification_section() -> str:
    """
    verify_past_recommendations() 결과를 텍스트 리포트 섹션으로 포맷.
    검증 가능한 데이터가 없으면 빈 문자열 반환.
    """
    data = verify_past_recommendations()
    by_period = data.get("by_period", {})
    recent    = data.get("recent_results", [])
    summary   = data.get("summary", {})

    if not by_period and not recent:
        return ""

    L = []
    L.append("=" * 80)
    L.append("  📊 추천 검증 리포트 (과거 추천 실적)")
    L.append("=" * 80)

    # ── 기간별 검증 결과 ───────────────────────────────────────
    if by_period:
        L.append("")
        L.append("  ── 기간별 검증 결과 ──────────────────────────────────────────────────────────")
        for day_after in sorted(by_period.keys()):
            v = by_period[day_after]
            buy_part  = ""
            sell_part = ""
            if v["buy_count"] > 0:
                buy_part = (f"매수 승률: {v['buy_win_rate']:.1f}% "
                            f"({v['buy_count']}건) 평균수익 {v['buy_avg_return']:+.1f}%")
            if v["sell_count"] > 0:
                sell_part = (f"매도 승률: {v['sell_win_rate']:.1f}% "
                             f"({v['sell_count']}건)")
            parts = [p for p in [buy_part, sell_part] if p]
            if parts:
                label = f"[{day_after:>2d}일 후 기준]"
                L.append(f"  {label}  " + " | ".join(parts))

    # ── 최근 추천 실적 (5일 후) ────────────────────────────────
    if recent:
        L.append("")
        L.append("  ── 최근 추천 실적 (5일 후) ──────────────────────────────────────────────────")
        for r in recent:
            icon   = "✅ HIT " if r["result"] == "HIT" else "❌ MISS"
            ticker = r["ticker"].replace(".KS", "").replace(".KQ", "")
            entry  = r["entry_price"]
            exit_  = r["exit_price"]
            ret    = r["return_pct"]
            sign   = "+" if ret >= 0 else ""
            # 가격 포맷: 큰 숫자(한국주)는 정수, 소수점 필요한 것은 2자리
            def fmt_price(p):
                if p is None:
                    return "N/A"
                return f"{p:,.0f}" if p >= 1000 else f"{p:,.2f}"
            L.append(
                f"  {icon}  {r['date']} [{r['market']:6s}] "
                f"{r['name'][:10]:10s}({ticker:8s}) "
                f"{r['type']} #{r['rank']}  "
                f"{sign}{ret:.1f}%  "
                f"({fmt_price(entry)}→{fmt_price(exit_)})"
            )

    # ── 종합 요약 ──────────────────────────────────────────────
    if summary.get("total_verified", 0) > 0:
        L.append("")
        L.append(f"  총 검증 건수: {summary['total_verified']}건 | "
                 f"최우수 기간: {summary['best_day_after']}일 후 | "
                 f"5일 매수 승률: {summary['overall_buy_win_rate']:.1f}% | "
                 f"5일 매도 승률: {summary['overall_sell_win_rate']:.1f}%")

        # 벤치마크 대비 초과 수익(alpha) — 5일 기준
        try:
            import yfinance as yf
            bench = {"KOSPI": "^KS11", "S&P500": "^GSPC"}
            avg_ret = by_period.get(5, {}).get("buy_avg_return", 0)
            alpha_parts = []
            for name, sym in bench.items():
                h = yf.Ticker(sym).history(period="10d", timeout=10)
                if len(h) >= 6:
                    bm_ret = (float(h["Close"].iloc[-1]) / float(h["Close"].iloc[-6]) - 1) * 100
                    alpha = avg_ret - bm_ret
                    alpha_parts.append(f"vs {name} {alpha:+.1f}%")
            if alpha_parts:
                L.append(f"  벤치마크 대비 Alpha (5일): {' | '.join(alpha_parts)}")
        except Exception:
            pass

    L.append("=" * 80)
    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════
# 성능 분석
# ═══════════════════════════════════════════════════════════════

def analyze_performance(period_days: int = 30) -> dict:
    """
    최근 성능 분석
    
    Args:
        period_days: 분석 기간 (일)
    
    Returns:
        성능 분석 결과 딕셔너리
    """
    conn = get_db_connection()
    
    # 분석 시작일
    start_date = (datetime.datetime.now() - datetime.timedelta(days=period_days)).strftime('%Y-%m-%d')
    
    # 이상값 필터 기준 (±30% 초과 수익률은 데이터 오류로 간주)
    _OUTLIER_LIMIT = 30

    # 매수 추천 성과 분석 (이상값 제외)
    query = '''
        SELECT
            r.market,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
            MAX(p.return_pct) as max_return,
            MIN(p.return_pct) as min_return
        FROM daily_recommendations r
        INNER JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'BUY'
          AND ABS(p.return_pct) < ?
        GROUP BY r.market
    '''

    buy_performance = pd.read_sql_query(query, conn, params=[start_date, _OUTLIER_LIMIT])

    # 매도 추천 성과 분석 (이상값 제외)
    query = '''
        SELECT
            r.market,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM daily_recommendations r
        INNER JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'SELL'
          AND ABS(p.return_pct) < ?
        GROUP BY r.market
    '''

    sell_performance = pd.read_sql_query(query, conn, params=[start_date, _OUTLIER_LIMIT])

    # 투자자별 성과 분석 (이상값 제외)
    query = '''
        SELECT
            r.investor_tags,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM daily_recommendations r
        INNER JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'BUY'
          AND r.investor_tags != '해당없음'
          AND ABS(p.return_pct) < ?
        GROUP BY r.investor_tags
        ORDER BY avg_return DESC
    '''

    investor_performance = pd.read_sql_query(query, conn, params=[start_date, _OUTLIER_LIMIT])
    
    conn.close()
    
    return {
        'buy_performance': buy_performance.to_dict('records'),
        'sell_performance': sell_performance.to_dict('records'),
        'investor_performance': investor_performance.to_dict('records'),
        'period_days': period_days,
        'analysis_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    }


# ═══════════════════════════════════════════════════════════════
# 자동 가중치 조정
# ═══════════════════════════════════════════════════════════════

def auto_adjust_weights():
    """
    성과 기반 자동 가중치 조정
    - 승률이 높은 투자자는 가중치 증가
    - 승률이 낮은 투자자는 가중치 감소
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 투자자별 최근 60 일 승률 조회
    query = '''
        SELECT 
            r.investor_tags,
            COUNT(*) as total_count,
            SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
            AVG(p.return_pct) as avg_return
        FROM daily_recommendations r
        LEFT JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.recommendation_type = 'BUY' 
        AND r.investor_tags != '해당없음'
        AND r.date >= date('now', '-60 days')
        GROUP BY r.investor_tags
        HAVING COUNT(*) >= 3
    '''
    
    cursor.execute(query)
    investor_stats = cursor.fetchall()
    
    # 가중치 조정
    adjustments = []
    for investor_tags, total_count, win_rate, avg_return in investor_stats:
        # 기본 가중치 조회
        cursor.execute('SELECT config_value FROM model_config WHERE config_key = ?', 
                      ('korean_investor_base_weight',))
        base_weight = cursor.fetchone()[0]
        
        # 승률 기반 조정 (50% 기준 ±50%)
        if win_rate >= 60:
            new_weight = base_weight * 1.5
        elif win_rate >= 50:
            new_weight = base_weight * 1.2
        elif win_rate >= 40:
            new_weight = base_weight * 0.8
        else:
            new_weight = base_weight * 0.5
        
        adjustments.append({
            'investor': investor_tags,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'old_weight': base_weight,
            'new_weight': new_weight
        })
    
    conn.close()
    
    return {
        'adjustments': adjustments,
        'adjusted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    }


# ═══════════════════════════════════════════════════════════════
# 백테스팅
# ═══════════════════════════════════════════════════════════════

def run_backtest(start_date: str, end_date: str, strategy: str = 'top5') -> dict:
    """
    백테스팅 실행
    
    Args:
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        strategy: 전략 ('top5', 'top10', 'high_score')
    
    Returns:
        백테스팅 결과
    """
    conn = get_db_connection()
    
    # 전략별 필터
    if strategy == 'top5':
        rank_filter = 'r.rank <= 5'
    elif strategy == 'top10':
        rank_filter = 'r.rank <= 10'
    else:
        rank_filter = 'r.score >= 50'
    
    query = f'''
        SELECT 
            r.date,
            r.ticker,
            r.name,
            r.price as buy_price,
            p.close_price as sell_price,
            p.return_pct,
            p.day_after
        FROM daily_recommendations r
        LEFT JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date BETWEEN ? AND ?
        AND r.recommendation_type = 'BUY'
        AND {rank_filter}
        ORDER BY r.date
    '''
    
    results = pd.read_sql_query(query, conn, params=[start_date, end_date])
    conn.close()
    
    if results.empty:
        return {'error': '백테스팅 데이터가 없습니다.'}
    
    # 성과 지표 계산
    total_trades = len(results)
    winning_trades = len(results[results['return_pct'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_return = results['return_pct'].mean()
    total_return = results['return_pct'].sum()
    max_return = results['return_pct'].max()
    min_return = results['return_pct'].min()
    sharpe_ratio = (avg_return / results['return_pct'].std()) if results['return_pct'].std() > 0 else 0
    
    return {
        'period': f'{start_date} ~ {end_date}',
        'strategy': strategy,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': total_trades - winning_trades,
        'win_rate': round(win_rate, 2),
        'avg_return': round(avg_return, 2),
        'total_return': round(total_return, 2),
        'max_return': round(max_return, 2),
        'min_return': round(min_return, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'trades': results.to_dict('records')
    }


# ═══════════════════════════════════════════════════════════════
# 성능 리포트 생성
# ═══════════════════════════════════════════════════════════════

def generate_performance_report(period_days: int = 30) -> str:
    """
    성능 분석 리포트 생성
    
    Args:
        period_days: 분석 기간
    
    Returns:
        리포트 텍스트
    """
    # 성능 분석
    performance = analyze_performance(period_days)
    
    # 백테스팅 (최근 30 일)
    end_date = datetime.datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.datetime.now() - datetime.timedelta(days=period_days)).strftime('%Y-%m-%d')
    backtest = run_backtest(start_date, end_date, 'top5')
    
    # 가중치 조정
    weight_adj = auto_adjust_weights()
    
    # 리포트 생성
    L = []
    L.append("=" * 80)
    L.append(f"  📈 AI 주식 스크리닝 성능 분석 리포트")
    L.append(f"  분석 기간: {period_days}일 ({start_date} ~ {end_date})")
    L.append(f"  생성일: {performance['analysis_date']}")
    L.append("=" * 80)
    
    # 매수 추천 성과
    L.append("\n" + "─" * 80)
    L.append("  🇰🇷 매수 추천 성과 (5 일 후 기준)")
    L.append("─" * 80)
    
    for perf in performance['buy_performance']:
        L.append(f"\n  [{perf['market']}]")
        L.append(f"    총 추천: {perf['total_count']:.0f}회")
        L.append(f"    평균 수익률: {perf['avg_return']:+.2f}%")
        L.append(f"    승률: {perf['win_rate']:.1f}%")
        L.append(f"    최대 수익: {perf['max_return']:+.2f}%")
        L.append(f"    최소 수익: {perf['min_return']:+.2f}%")
    
    # 투자자별 성과
    L.append("\n" + "─" * 80)
    L.append("  👥 투자자별 성과 (승률 상위)")
    L.append("─" * 80)
    
    for perf in performance['investor_performance'][:5]:
        L.append(f"\n  [{perf['investor_tags']}]")
        L.append(f"    추천 횟수: {perf['total_count']:.0f}회")
        L.append(f"    평균 수익률: {perf['avg_return']:+.2f}%")
        L.append(f"    승률: {perf['win_rate']:.1f}%")
    
    # 백테스팅 결과
    L.append("\n" + "─" * 80)
    L.append("  🧪 백테스팅 결과 (TOP5 전략)")
    L.append("─" * 80)
    
    if 'error' not in backtest:
        L.append(f"\n  총 거래: {backtest['total_trades']}회")
        L.append(f"  승패: {backtest['winning_trades']}승 {backtest['losing_trades']}패")
        L.append(f"  승률: {backtest['win_rate']:.1f}%")
        L.append(f"  평균 수익률: {backtest['avg_return']:+.2f}%")
        L.append(f"  누적 수익률: {backtest['total_return']:+.2f}%")
        L.append(f"  샤프 지수: {backtest['sharpe_ratio']:.2f}")
    
    # 가중치 조정
    L.append("\n" + "─" * 80)
    L.append("  ⚙️  자동 가중치 조정")
    L.append("─" * 80)
    
    for adj in weight_adj['adjustments'][:5]:
        L.append(f"\n  [{adj['investor']}]")
        L.append(f"    승률: {adj['win_rate']:.1f}%")
        L.append(f"    평균 수익: {adj['avg_return']:+.2f}%")
        L.append(f"    가중치: {adj['old_weight']:.1f} → {adj['new_weight']:.1f}")
    
    L.append("\n" + "=" * 80)
    L.append("  ⚠️  과거 성과가 미래 수익을 보장하지 않습니다.")
    L.append("=" * 80 + "\n")
    
    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  성능 추적 및 학습 모듈")
    print("=" * 60)
    
    # 데이터베이스 초기화
    init_database()
    
    # 성능 분석
    print("\n📊 최근 30 일 성능 분석 중...")
    performance = analyze_performance(30)
    
    if performance['buy_performance']:
        print(f"  매수 추천 평균 승률: {performance['buy_performance'][0].get('win_rate', 0):.1f}%")
    else:
        print("  분석할 데이터가 없습니다. 먼저 추천을 저장하세요.")
    
    # 백테스팅
    print("\n🧪 백테스팅 실행 중...")
    end_date = datetime.datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    backtest = run_backtest(start_date, end_date, 'top5')
    
    if 'error' not in backtest:
        print(f"  승률: {backtest['win_rate']:.1f}%")
        print(f"  누적 수익률: {backtest['total_return']:+.2f}%")
    else:
        print(f"  {backtest['error']}")
    
    # 성능 리포트
    print("\n📄 성능 리포트 생성 중...")
    report = generate_performance_report(30)
    
    # 리포트 저장
    report_path = os.path.join(BASE_DIR, 'performance_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"  ✓ 리포트 저장: {report_path}")
    
    print("\n" + "=" * 60)
    print("  성능 추적 모듈이 준비되었습니다!")
    print("=" * 60 + "\n")
