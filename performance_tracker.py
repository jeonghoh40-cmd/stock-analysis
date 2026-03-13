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
        'us': 'US'
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
            
            cursor.execute('''
                INSERT INTO daily_recommendations 
                (date, market, ticker, name, recommendation_type, rank, score, 
                 price, rsi, macd_hist, ma5, ma20, ma60, investor_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, market, rec['ticker'], rec['name'], rec_type, rank,
                rec['score'], rec['price'], rec.get('rsi'), rec.get('macd_hist'),
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
    """
    if target_date is None:
        target_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 아직 추적되지 않은 추천 종목 조회
    cursor.execute('''
        SELECT DISTINCT id, ticker, date, price
        FROM daily_recommendations
        WHERE id NOT IN (SELECT DISTINCT recommendation_id FROM price_tracking)
    ''')
    
    recommendations = cursor.fetchall()
    
    import yfinance as yf
    
    for rec_id, ticker, rec_date, initial_price in recommendations:
        try:
            # 추천일 이후 가격 데이터 조회
            df = yf.download(ticker, start=rec_date, progress=False)
            
            if df.empty or len(df) < 2:
                continue
            
            # yfinance 1.x: 단일 ticker도 Close가 DataFrame으로 반환될 수 있음
            close_col = df['Close']
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]

            # 일별 수익률 계산 (최대 20 일)
            for day_after in [1, 3, 5, 10, 20]:
                if len(df) <= day_after:
                    continue

                close_price = float(close_col.iloc[day_after])
                return_pct = ((close_price - initial_price) / initial_price) * 100
                
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
    
    # 매수 추천 성과 분석
    query = '''
        SELECT 
            r.market,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
            MAX(p.return_pct) as max_return,
            MIN(p.return_pct) as min_return
        FROM daily_recommendations r
        LEFT JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'BUY'
        GROUP BY r.market
    '''
    
    buy_performance = pd.read_sql_query(query, conn, params=[start_date])
    
    # 매도 추천 성과 분석
    query = '''
        SELECT 
            r.market,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM daily_recommendations r
        LEFT JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'SELL'
        GROUP BY r.market
    '''
    
    sell_performance = pd.read_sql_query(query, conn, params=[start_date])
    
    # 투자자별 성과 분석
    query = '''
        SELECT 
            r.investor_tags,
            COUNT(*) as total_count,
            AVG(p.return_pct) as avg_return,
            SUM(CASE WHEN p.return_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
        FROM daily_recommendations r
        LEFT JOIN price_tracking p ON r.id = p.recommendation_id AND p.day_after = 5
        WHERE r.date >= ? AND r.recommendation_type = 'BUY' AND r.investor_tags != '해당없음'
        GROUP BY r.investor_tags
        ORDER BY avg_return DESC
    '''
    
    investor_performance = pd.read_sql_query(query, conn, params=[start_date])
    
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
