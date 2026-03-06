import sys
sys.path.insert(0, r'C:\Users\geunho\stock analysis')
sys.path.insert(0, r'C:\Users\geunho\stock analysis\Lib\site-packages')
try:
    import yfinance
    print("yfinance OK:", yfinance.__version__)
except Exception as e:
    print("yfinance FAIL:", e)
try:
    import anthropic
    print("anthropic OK:", anthropic.__version__)
except Exception as e:
    print("anthropic FAIL:", e)
try:
    import feedparser
    print("feedparser OK:", feedparser.__version__)
except Exception as e:
    print("feedparser FAIL:", e)
try:
    import dotenv
    print("dotenv OK")
except Exception as e:
    print("dotenv FAIL:", e)
print("All done")
