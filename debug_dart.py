import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import dotenv_values
import requests, zipfile, io, xml.etree.ElementTree as ET

cfg = dotenv_values('.env')
key = cfg.get('DART_API_KEY','')

resp = requests.get(f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}', timeout=30)
with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
    xml_data = zf.read('CORPCODE.xml')
root = ET.fromstring(xml_data)
corp_code = ''
for item in root.findall('list'):
    if item.findtext('stock_code','').strip() == '005930':
        corp_code = item.findtext('corp_code','').strip()
        break

params = {'crtfc_key': key, 'corp_code': corp_code,
          'bsns_year': '2024', 'reprt_code': '11011', 'fs_div': 'CFS'}
r = requests.get('https://opendart.fss.or.kr/api/fnlttSinglAcnt.json', params=params, timeout=15)
items = r.json().get('list', [])

print('=== 전체 account_nm 목록 (sj_div별) ===')
for item in items:
    print(f"  sj_div={item['sj_div']:3s} | {item['account_nm']:30s} | {item['thstrm_amount']}")
