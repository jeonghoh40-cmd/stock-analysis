"""한국 ETF 구성종목 포함 AI 심층분석"""
import sys, json, datetime, smtplib
sys.path.insert(0, r'C:\Users\geunho\stock analysis')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import anthropic, yfinance as yf
from dotenv import dotenv_values
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser

cfg = dotenv_values(r'C:\Users\geunho\stock analysis\.env')
def _get(k, d=''): return __import__('os').environ.get(k) or cfg.get(k) or d

# ── ETF 구성종목 및 비중 ──────────────────────────────────────────
ETF_HOLDINGS = {
    'KODEX 코스닥150': {
        'desc': '코스닥150 지수 추종 | 코스닥 대형·중형주 150개 | AUM 약 1.2조원',
        'top10': [('에코프로비엠',4.8),('알테오젠',4.2),('HLB',3.9),('셀트리온헬스케어',3.5),
                  ('크래프톤',3.2),('에코프로',3.1),('카카오게임즈',2.8),('펄어비스',2.5),
                  ('리가켐바이오',2.3),('클래시스',2.1)],
        'sector': {'바이오/헬스케어':35,'IT/게임':28,'소재/화학':18,'기타':19},
        'total_stocks': 150, 'expense_ratio': 0.09
    },
    'TIGER 코스닥150': {
        'desc': '코스닥150 지수 추종 | 미래에셋운용 | AUM 약 0.8조원',
        'top10': [('에코프로비엠',4.9),('알테오젠',4.1),('HLB',3.8),('셀트리온헬스케어',3.4),
                  ('크래프톤',3.3),('에코프로',3.0),('카카오게임즈',2.7),('펄어비스',2.4),
                  ('리가켐바이오',2.2),('클래시스',2.0)],
        'sector': {'바이오/헬스케어':35,'IT/게임':28,'소재/화학':18,'기타':19},
        'total_stocks': 150, 'expense_ratio': 0.07
    },
    'KODEX 바이오': {
        'desc': 'KRX 헬스케어 지수 추종 | 제약·바이오·의료기기 | AUM 약 0.4조원',
        'top10': [('삼성바이오로직스',25.3),('셀트리온',18.7),('유한양행',7.2),('한미약품',5.1),
                  ('종근당',4.3),('대웅제약',3.8),('HLB',3.5),('알테오젠',3.2),
                  ('동아ST',2.9),('제넥신',2.4)],
        'sector': {'바이오/CMO':55,'제약':32,'의료기기':13},
        'total_stocks': 45, 'expense_ratio': 0.45
    },
    'KODEX 2차전지': {
        'desc': 'FnGuide 2차전지산업 지수 추종 | 배터리 셀+소재+장비 | AUM 약 2.1조원',
        'top10': [('LG에너지솔루션',19.2),('삼성SDI',15.8),('포스코퓨처엠',10.3),
                  ('에코프로비엠',9.7),('에코프로',7.5),('LG화학',6.2),
                  ('SK이노베이션',5.8),('엘앤에프',4.1),('천보',3.2),('나노신소재',2.8)],
        'sector': {'셀/팩':44,'양극재':28,'음극재/전해질':15,'장비':13},
        'total_stocks': 35, 'expense_ratio': 0.45
    },
    'TIGER 2차전지': {
        'desc': 'iSelect 2차전지 지수 추종 | 미래에셋운용 | AUM 약 1.4조원',
        'top10': [('LG에너지솔루션',20.1),('삼성SDI',16.2),('포스코퓨처엠',10.5),
                  ('에코프로비엠',9.3),('에코프로',7.1),('LG화학',5.9),
                  ('SK이노베이션',5.4),('엘앤에프',3.9),('천보',3.1),('솔루스첨단소재',2.6)],
        'sector': {'셀/팩':45,'양극재':27,'음극재/전해질':15,'장비':13},
        'total_stocks': 30, 'expense_ratio': 0.40
    },
    'KODEX 반도체': {
        'desc': 'KRX반도체 지수 추종 | 반도체 소자·장비·소재 | AUM 약 1.8조원',
        'top10': [('삼성전자',37.5),('SK하이닉스',25.8),('한미반도체',6.2),
                  ('HPSP',4.1),('리노공업',3.7),('원익IPS',2.9),
                  ('이오테크닉스',2.4),('DB하이텍',2.1),('유진테크',1.8),('테크윙',1.6)],
        'sector': {'메모리반도체':63,'반도체장비':24,'반도체소재':13},
        'total_stocks': 30, 'expense_ratio': 0.45
    },
    'TIGER 반도체': {
        'desc': 'KRX반도체 지수 추종 | 삼성자산운용 | AUM 약 0.9조원',
        'top10': [('삼성전자',38.2),('SK하이닉스',26.1),('한미반도체',5.9),
                  ('HPSP',4.0),('리노공업',3.5),('원익IPS',2.8),
                  ('이오테크닉스',2.3),('DB하이텍',2.0),('유진테크',1.7),('테크윙',1.5)],
        'sector': {'메모리반도체':64,'반도체장비':23,'반도체소재':13},
        'total_stocks': 30, 'expense_ratio': 0.45
    },
    'KODEX 200': {
        'desc': 'KOSPI200 지수 추종 | 한국 대표 지수 ETF | AUM 약 12조원 (국내 최대)',
        'top10': [('삼성전자',27.8),('SK하이닉스',8.9),('LG에너지솔루션',4.1),
                  ('삼성바이오로직스',3.7),('현대차',3.2),('기아',2.8),
                  ('셀트리온',2.1),('POSCO홀딩스',1.9),('KB금융',1.7),('신한지주',1.5)],
        'sector': {'IT/반도체':42,'자동차':7,'금융':12,'바이오':8,'소재/에너지':12,'기타':19},
        'total_stocks': 200, 'expense_ratio': 0.15
    },
    'TIGER 200': {
        'desc': 'KOSPI200 지수 추종 | 미래에셋자산운용 | AUM 약 4.2조원',
        'top10': [('삼성전자',27.6),('SK하이닉스',8.8),('LG에너지솔루션',4.0),
                  ('삼성바이오로직스',3.6),('현대차',3.1),('기아',2.7),
                  ('셀트리온',2.0),('POSCO홀딩스',1.8),('KB금융',1.6),('신한지주',1.4)],
        'sector': {'IT/반도체':41,'자동차':7,'금융':12,'바이오':8,'소재/에너지':12,'기타':20},
        'total_stocks': 200, 'expense_ratio': 0.07
    },
    'KODEX 레버리지': {
        'desc': 'KOSPI200 일간수익률 2배 추종 | 단기 트레이딩 전용 | AUM 약 3.5조원',
        'top10': [('KOSPI200 선물',100.0)],
        'sector': {'파생상품':100},
        'total_stocks': 1, 'expense_ratio': 0.64
    },
    'KODEX 자동차': {
        'desc': 'FnGuide 자동차 지수 추종 | 완성차+부품+타이어 | AUM 약 0.3조원',
        'top10': [('현대차',25.8),('기아',22.3),('현대모비스',15.1),
                  ('한국타이어',7.2),('HL만도',5.8),('현대위아',4.3),
                  ('금호타이어',3.9),('현대글로비스',3.5),('에스엘',2.8),('성우하이텍',2.1)],
        'sector': {'완성차':48,'자동차부품':39,'타이어':13},
        'total_stocks': 20, 'expense_ratio': 0.45
    },
    'KODEX 은행': {
        'desc': 'KRX Banks 지수 추종 | 4대 금융지주+은행 | AUM 약 0.6조원',
        'top10': [('KB금융',25.3),('신한지주',22.8),('하나금융지주',18.7),
                  ('우리금융지주',14.2),('기업은행',9.1),('BNK금융',4.2),
                  ('DGB금융',3.1),('JB금융',2.6)],
        'sector': {'시중은행/금융지주':100},
        'total_stocks': 8, 'expense_ratio': 0.45
    },
    'KODEX 고배당': {
        'desc': 'FnGuide 고배당플러스 지수 추종 | 배당수익률 상위 | AUM 약 0.5조원',
        'top10': [('KT&G',8.2),('맥쿼리인프라',7.9),('한국전력',6.8),
                  ('SK텔레콤',6.2),('KT',5.8),('금호석유',4.9),
                  ('현대글로비스',4.3),('삼성화재',4.1),('하나금융지주',3.7),('GS건설',3.1)],
        'sector': {'통신':17,'에너지':15,'금융':25,'인프라':15,'소재':13,'기타':15},
        'total_stocks': 30, 'expense_ratio': 0.30
    },
    'TIGER 고배당': {
        'desc': 'FnGuide 배당성장&가치주 지수 추종 | 미래에셋 | AUM 약 0.4조원',
        'top10': [('삼성전자',9.8),('KB금융',7.2),('신한지주',6.8),
                  ('하나금융지주',6.1),('SK텔레콤',5.9),('KT',5.3),
                  ('현대차',4.8),('삼성화재',4.5),('LG전자',3.9),('기아',3.6)],
        'sector': {'금융':30,'IT/통신':18,'자동차':12,'에너지/소재':15,'기타':25},
        'total_stocks': 30, 'expense_ratio': 0.29
    },
    'TIGER 금융': {
        'desc': 'KRX금융 지수 추종 | 은행+증권+보험 통합 | AUM 약 0.2조원',
        'top10': [('KB금융',18.2),('신한지주',16.7),('삼성생명',12.3),
                  ('하나금융지주',11.8),('삼성화재',9.2),('메리츠금융',7.1),
                  ('우리금융',6.8),('미래에셋증권',4.2),('한화생명',3.5),('키움증권',2.9)],
        'sector': {'은행/지주':65,'보험':22,'증권':13},
        'total_stocks': 25, 'expense_ratio': 0.45
    },
    'TIGER 헬스케어': {
        'desc': 'KRX Healthcare 지수 추종 | 제약+의료기기 | AUM 약 0.3조원',
        'top10': [('삼성바이오로직스',22.1),('셀트리온',16.4),('유한양행',6.8),
                  ('한미약품',5.3),('GC녹십자',4.2),('종근당',3.9),
                  ('보령제약',3.1),('제일약품',2.8),('동국제약',2.5),('HLB',2.3)],
        'sector': {'바이오/CMO':45,'제약':38,'의료기기':17},
        'total_stocks': 40, 'expense_ratio': 0.45
    },
    'KODEX 미국S&P500': {
        'desc': 'S&P500 지수 추종 | 국내상장 미국ETF | AUM 약 3.8조원',
        'top10': [('NVIDIA',7.1),('Apple',6.8),('Microsoft',6.3),
                  ('Amazon',4.2),('Meta',3.8),('Alphabet A',3.1),
                  ('Berkshire',2.4),('Eli Lilly',2.1),('Broadcom',2.0),('JPMorgan',1.9)],
        'sector': {'IT/반도체':32,'커뮤니케이션':9,'금융':13,'헬스케어':12,'소비재':11,'기타':23},
        'total_stocks': 500, 'expense_ratio': 0.05
    },
    'TIGER 미국나스닥100': {
        'desc': 'NASDAQ-100 지수 추종 | 미국 빅테크 집중 | AUM 약 5.1조원',
        'top10': [('NVIDIA',8.9),('Apple',8.4),('Microsoft',7.8),
                  ('Amazon',5.3),('Meta',4.6),('Alphabet A+C',4.2),
                  ('Broadcom',3.8),('Tesla',3.1),('Costco',2.8),('Netflix',2.4)],
        'sector': {'IT/반도체':52,'커뮤니케이션':16,'소비재':13,'의료':5,'기타':14},
        'total_stocks': 100, 'expense_ratio': 0.07
    },
    'KODEX 인버스': {
        'desc': 'KOSPI200 일간수익률 -1배 | 하락장 헤지용 | AUM 약 1.9조원',
        'top10': [('KOSPI200 인버스선물',100.0)],
        'sector': {'파생상품':100},
        'total_stocks': 1, 'expense_ratio': 0.64
    },
}

# ── 데이터 로드 & 분류 ────────────────────────────────────────────
with open('etf_screen.json', encoding='utf-8') as f:
    etf_data = json.load(f)

# 인버스/레버리지 제외한 매수 후보
EXCLUDE = ['KODEX 인버스', 'KODEX 레버리지']
buy_candidates = [r for r in etf_data if r['name'] not in EXCLUDE]
buy_top   = buy_candidates[:10]   # 점수 상위
avoid_etf = [r for r in etf_data if r['name'] in EXCLUDE or r['score'] <= -10][:4]

# ── 거시경제 수집 ──────────────────────────────────────────────────
macro = {}
for name, tk in {'USD/KRW':'KRW=X','WTI유가':'CL=F','금':'GC=F','VIX':'^VIX',
                  'KOSPI':'^KS11','KOSDAQ':'^KQ11','S&P500':'^GSPC','나스닥':'^IXIC'}.items():
    try:
        h = yf.Ticker(tk).history(period='5d')
        if not h.empty:
            cur=h['Close'].iloc[-1]; prev=h['Close'].iloc[-2] if len(h)>1 else cur
            macro[name] = {'현재':round(cur,2), '등락':round((cur-prev)/prev*100,2)}
    except: pass

news = []
for rss in ['https://www.yonhapnewstv.co.kr/category/news/economy/feed/',
            'https://rss.donga.com/economy.xml']:
    try:
        feed = feedparser.parse(rss)
        if feed.entries: news = [e.title for e in feed.entries[:8]]; break
    except: continue

# ── 프롬프트 ──────────────────────────────────────────────────────
macro_txt = '\n'.join(f'  {k}: {v["현재"]} ({v["등락"]:+.2f}%)' for k,v in macro.items())
news_txt  = '\n'.join(f'  - {h}' for h in news) if news else '  (없음)'

def etf_block(etfs):
    lines = []
    for r in etfs:
        h = ETF_HOLDINGS.get(r['name'], {})
        desc = h.get('desc','정보없음')
        top5 = ' / '.join(f"{n}({w}%)" for n,w in h.get('top10',[])[:5])
        sec  = ' | '.join(f"{k}:{v}%" for k,v in list(h.get('sector',{}).items())[:4])
        er   = h.get('expense_ratio','N/A')
        lines.append(
            f"  [{r['name']}] ({r['ticker']}) 점수:{r['score']:+d} | {r['price']:,.0f}원 ({r['chg']:+.2f}%)\n"
            f"    RSI:{r['rsi']} | MACD:{r['macd_hist']:+.2f} | BB:{r['bb_pct']}% | 모멘텀5일:{r['mom5']:+.2f}% | 모멘텀20일:{r['mom20']:+.2f}% | 거래량:{r['vol_ratio']}x\n"
            f"    MA5:{r['ma5']:,.0f} MA20:{r['ma20']:,.0f} MA60:{r['ma60']:,.0f}\n"
            f"    📋 {desc} | 운용보수:{er}%\n"
            f"    🏆 상위5종목: {top5}\n"
            f"    📊 섹터배분: {sec}"
        )
    return '\n\n'.join(lines)

prompt = f"""당신은 한국 ETF 전문 애널리스트입니다.
오늘 {datetime.datetime.now().strftime('%Y년 %m월 %d일')} 기준으로
기술적 분석 + ETF 구성종목·섹터 분석을 결합한 투자 의견을 작성하세요.

■ 거시경제 현황
{macro_txt}

■ 오늘의 주요 뉴스
{news_txt}

■ ETF 매수 후보 (기술적 점수 순)
{etf_block(buy_top)}

■ 주의·회피 ETF
{etf_block(avoid_etf)}

─────────────────────────────────────────────────────────
【작성 지침】

## PART 1. 매수 추천 ETF TOP 5

각 ETF별 아래 형식 정확히 준수:

[순위. ETF명(티커)] 투자의견: ★★★(강력매수) / ★★(매수) / ★(약한매수)

📦 ETF 구성 분석:
   · 추종 지수 및 핵심 테마 1줄 요약
   · 상위 3개 구성종목 현재 주가 흐름 및 비중 의미
   · 섹터 쏠림 리스크 또는 분산 효과

✅ 매수 논리 (2개 이상, 수치 명시):
   · RSI, MACD, BB%, 모멘텀 수치 기반
   · 거시경제(환율·금리·VIX) 연관성
   · 구성종목 당일 강세 여부

💰 매수 전략 (3단계):
   · 1차: 현재가 기준 (비중 40%)
   · 2차: -3% 하락 시 (비중 30%)
   · 3차: -6% 하락 시 (비중 30%)

🎯 목표가 (3단계, 정확한 원화):
   · 1차 +8% = X,XXX원
   · 2차 +15% = X,XXX원
   · 3차 +25% = X,XXX원

🛑 손절가: -5% = X,XXX원

⚠️ 리스크: ETF 구성 집중도·정책·환율 리스크 1~2줄

---

## PART 2. 주의/회피 ETF (2개, 각 3줄)

## PART 3. ETF 포트폴리오 종합 전략 (10줄 이상)
   · 현재 시장 국면별 최적 ETF 조합 (공격형/균형형/방어형)
   · 섹터 로테이션 방향 (현재 강세→약세 예상 섹터)
   · 레버리지/인버스 활용 조건
   · 오늘의 최선호 ETF 1개 선정 + 이유 3가지
   · 향후 2~4주 ETF 전략 시나리오

─────────────────────────────────────────────────────────
⚠️ 본 분석은 참고용이며 투자 책임은 본인에게 있습니다."""

print('Claude AI ETF 심층 분석 중...')
client = anthropic.Anthropic(api_key=_get('ANTHROPIC_API_KEY'))
resp = client.messages.create(
    model='claude-sonnet-4-6',
    max_tokens=10000,
    messages=[{'role':'user','content':prompt}]
)
analysis = resp.content[0].text
print('분석 완료')

# ── 리포트 ────────────────────────────────────────────────────────
now = datetime.datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
L = []
L.append('='*72)
L.append(f'  📊 한국 ETF AI 스크리닝 리포트  |  {now}')
L.append(f'  분석 ETF: {len(etf_data)}개  |  매수후보: {len(buy_top)}개')
L.append('='*72)

L.append('\n■ 전체 ETF 스코어보드')
L.append(f"{'순위':<4} {'ETF명':<22} {'현재가':>9} {'등락':>7} {'점수':>5} {'RSI':>6} {'BB%':>6} {'모멘텀5일':>9} {'모멘텀20일':>10}")
L.append('-'*82)
for i,r in enumerate(etf_data,1):
    flag = '★' if i<=5 and r['name'] not in EXCLUDE else ('⚠' if r['score']<=-10 else ' ')
    L.append(f"{flag}{i:<3} {r['name']:<22} {r['price']:>8,.0f}원 {r['chg']:>+6.2f}% {r['score']:>+4d}점 {r['rsi']:>6.1f} {r['bb_pct']:>5.1f}% {r['mom5']:>+8.2f}% {r['mom20']:>+9.2f}%")

L.append('\n' + '='*72)
L.append('  ✅ 매수 추천 ETF 상세 (구성종목 포함)')
L.append('='*72)
for i, r in enumerate(buy_top[:7], 1):
    h = ETF_HOLDINGS.get(r['name'], {})
    ic = '▲' if r['chg'] >= 0 else '▼'
    L.append(f"\n  [{i}위] {r['name']} ({r['ticker']})")
    L.append(f"  {'─'*60}")
    L.append(f"  점수:{r['score']:+d}점 | {r['price']:,.0f}원 {ic}{abs(r['chg']):.2f}% | RSI:{r['rsi']} | MACD:{r['macd_hist']:+.2f} | BB:{r['bb_pct']}% | 모멘텀:{r['mom5']:+.2f}%")
    L.append(f"  MA5:{r['ma5']:,.0f} / MA20:{r['ma20']:,.0f} / MA60:{r['ma60']:,.0f} | 거래량:{r['vol_ratio']}x")
    L.append(f"  📋 {h.get('desc','')}")
    if h.get('top10'):
        L.append(f"  🏆 상위10 구성종목:")
        for j, (name, wt) in enumerate(h['top10'], 1):
            bar = '█' * int(wt/2)
            L.append(f"     {j:2d}. {name:<18} {wt:5.1f}%  {bar}")
    if h.get('sector'):
        L.append(f"  📊 섹터배분: " + ' | '.join(f"{k} {v}%" for k,v in h['sector'].items()))
    if h.get('expense_ratio'):
        L.append(f"  💸 운용보수: {h['expense_ratio']}% / 년")

L.append('\n' + '='*72)
L.append('  🤖 Claude AI 심층 ETF 분석')
L.append('='*72)
L.append(analysis)
L.append('\n' + '='*72)
L.append('  ⚠️  기술적 분석 참고용 / 투자 손익 책임은 본인에게 있습니다.')
L.append('='*72)
report = '\n'.join(L)

with open('report.txt', 'w', encoding='utf-8') as f:
    f.write(report)
print('report.txt 저장 완료')

# ── 이메일 발송 ────────────────────────────────────────────────────
msg = MIMEMultipart('alternative')
msg['Subject'] = f'📊 한국 ETF AI 분석 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")} | ETF 매수 TOP5'
msg['From'] = _get('EMAIL_FROM', _get('EMAIL_USER'))
msg['To']   = _get('EMAIL_TO', 'geunho@stic.co.kr')
msg.attach(MIMEText(report, 'plain', 'utf-8'))
with smtplib.SMTP(_get('SMTP_SERVER','smtp.office365.com'), int(_get('SMTP_PORT','587'))) as srv:
    srv.ehlo(); srv.starttls(); srv.ehlo()
    srv.login(_get('EMAIL_USER'), _get('EMAIL_PASS'))
    srv.sendmail(msg['From'], msg['To'], msg.as_string())
print(f'이메일 발송 완료: {msg["To"]}')
