"""
ARK Big Ideas 2026 PDF 분석기
- PDF 에서 테마별 핵심 종목 추출
- 딕셔너리 자동 생성
"""

import pdfplumber
import json
import re
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PDF_PATH = 'Ark/ARKInvest BigIdeas2026.pdf'
OUTPUT_PATH = 'Ark/ark_extracted_content.txt'

def extract_pdf_content():
    """PDF 전체 내용을 추출한다."""
    print("PDF 내용 추출 중...")
    
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"총 {len(pdf.pages)}페이지")
        
        all_text = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                all_text.append(f"=== 페이지 {i+1} ===\n{text}")
                if (i + 1) % 10 == 0:
                    print(f"  {i+1}/{len(pdf.pages)} 페이지 처리 중...")
    
    # 저장
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_text))
    
    print(f"추출 완료: {OUTPUT_PATH}")
    return '\n'.join(all_text)


def find_stock_mentions(text):
    """텍스트에서 언급된 종목들을 찾는다."""
    # 미국 티커 패턴 (대문자 2-5 자)
    us_tickers = re.findall(r'\b[A-Z]{2,5}\b', text)
    
    # 주요 티커 필터링
    major_tickers = [
        'NVDA', 'TSLA', 'MSFT', 'META', 'AMZN', 'GOOGL', 'GOOG', 'AAPL',
        'AMD', 'AVGO', 'TSM', 'AMAT', 'LRCX', 'KLAC', 'SMCI', 'VRTX',
        'COIN', 'MSTR', 'HOOD', 'ARKB', 'BLK', 'GS',
        'ILMN', 'CRSP', 'TXG', 'TEM', 'RXRX', 'IONS', 'EXAS',
        'RKLB', 'ASTS', 'LUNR', 'ASTR',
        'ABB', 'ISRG', 'PATH', 'AI', 'NOW', 'CRM', 'WDAY', 'PLTR',
        'ENPH', 'NEE', 'CEG', 'VST', 'GEV', 'SMR', 'AES',
        'UBER', 'MBLY', 'ZM', 'LYFT',
        'UPS', 'FDX', 'AMZN',
        'NFLX', 'DIS', 'SPOT',
        'SQ', 'PYPL', 'V', 'MA',
        'SHOP', 'SE', 'MELI',
        'DDOG', 'NET', 'ESTC', 'MDB',
        'SNOW', 'DBX', 'BOX',
        'CRWD', 'PANW', 'ZS', 'FTNT',
        'ZG', 'RDFN', 'OPEN',
        'TDOC', 'VEEV', 'DOCU',
        'TWLO', 'SEND', 'PATH'
    ]
    
    found = [t for t in us_tickers if t in major_tickers]
    
    # 빈도수 계산
    from collections import Counter
    ticker_freq = Counter(found)
    
    return ticker_freq


def extract_theme_sections(text):
    """테마별 섹션을 추출한다."""
    themes = {
        'The Great Acceleration': [],
        'AI Infrastructure': [],
        'AI Consumer Operating System': [],
        'AI Productivity': [],
        'Bitcoin': [],
        'Tokenized Assets': [],
        'Decentralized Finance': [],
        'Multiomics': [],
        'Reusable Rockets': [],
        'Robotics': [],
        'Distributed Energy': [],
        'Autonomous Vehicles': [],
        'Autonomous Logistics': []
    }
    
    current_theme = None
    current_content = []
    
    for line in text.split('\n'):
        # 테마 제목 확인
        for theme in themes.keys():
            if theme.lower() in line.lower() and len(line) < 100:
                if current_theme:
                    themes[current_theme] = current_content
                current_theme = theme
                current_content = [line]
                break
        else:
            if current_theme:
                current_content.append(line)
    
    if current_theme:
        themes[current_theme] = current_content
    
    return themes


if __name__ == "__main__":
    print("=" * 60)
    print("ARK Big Ideas 2026 PDF 분석기")
    print("=" * 60)
    
    # 1. PDF 내용 추출
    full_text = extract_pdf_content()
    
    # 2. 종목 언급 추출
    print("\n종목 언급 빈도 분석 중...")
    ticker_freq = find_stock_mentions(full_text)
    
    print("\n📊 상위 언급 종목:")
    for ticker, count in ticker_freq.most_common(20):
        print(f"  {ticker}: {count}회")
    
    # 3. 테마별 섹션 추출
    print("\n테마별 섹션 추출 중...")
    themes = extract_theme_sections(full_text)
    
    print("\n📑 테마별 페이지 수:")
    for theme, content in themes.items():
        if content:
            print(f"  {theme}: {len(content)}줄")
    
    print("\n✅ 분석 완료!")
    print(f"   - 전체 텍스트: {OUTPUT_PATH}")
