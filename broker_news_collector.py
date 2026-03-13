"""
broker_news_collector.py — 증권사 추천 종목 수집 모듈

오늘 증권사(한국투자증권 KIS) 추천 종목을 수집하여 반환한다.
캐시(cache/broker_picks_YYYYMMDD.json)가 있으면 재사용하고,
없으면 KIS API 시도 후 실패 시 빈 리스트를 반환한다.

plan.md §증권사 리서치·추천 데이터 참조.
"""

import sys
import os
import json
import logging
import requests
from datetime import date
from typing import Any

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

_logger = logging.getLogger('broker_news_collector')
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(message)s'))
    _logger.addHandler(_handler)

# ── KIS API 엔드포인트 ─────────────────────────────────────────────────────
_KIS_PROD_BASE = 'https://openapi.koreainvestment.com:9443'
_KIS_VTS_BASE = 'https://openapivts.koreainvestment.com:29443'


def _get_env() -> dict[str, str]:
    """프로젝트 루트 .env 로드."""
    env_path = os.path.join(BASE_DIR, '.env')
    return dotenv_values(env_path)


def _get_base_url(kis_env: str) -> str:
    return _KIS_VTS_BASE if kis_env == 'vts' else _KIS_PROD_BASE


def _fetch_access_token(base_url: str, app_key: str, secret_key: str) -> str | None:
    """KIS access token 발급. 실패 시 None 반환."""
    url = f'{base_url}/oauth2/tokenP'
    payload = {
        'grant_type': 'client_credentials',
        'appkey': app_key,
        'appsecret': secret_key,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        token = data.get('access_token')
        if not token:
            _logger.warning('[broker] KIS 토큰 응답에 access_token 없음: %s', data)
        return token
    except Exception as e:
        _logger.warning('[broker] KIS 토큰 발급 실패: %s', e)
        return None


def _fetch_kis_research_picks(
    base_url: str,
    app_key: str,
    token: str,
) -> list[dict[str, Any]]:
    """
    KIS API로 리서치 추천 종목 조회.
    엔드포인트: /uapi/domestic-stock/v1/ranking/analyst-report
    실패 시 빈 리스트 반환.
    """
    url = f'{base_url}/uapi/domestic-stock/v1/ranking/analyst-report'
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {token}',
        'appkey': app_key,
        'tr_id': 'HHKDB669108C0',
        'custtype': 'P',
    }
    params = {
        'FID_COND_MRKT_DIV_CODE': 'J',
        'FID_INPUT_ISCD': '0000',
        'FID_RANK_SORT_CLS_CODE': '0',
        'FID_INPUT_CNT_1': '20',
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        output = data.get('output', [])
        if not isinstance(output, list):
            _logger.info('[broker] KIS 리서치 응답 output 형식 이상: %s', type(output))
            return []

        picks = []
        for item in output:
            ticker_raw = item.get('mksc_shrn_iscd', '').strip()
            name = item.get('hts_kor_isnm', '').strip()
            reason = item.get('mbcr_name', '') or item.get('anlr_opnn', '')

            if not ticker_raw:
                continue

            # KRX 종목 코드에 .KS 접미사 추가
            ticker = f'{ticker_raw}.KS' if not ticker_raw.endswith(('.KS', '.KQ')) else ticker_raw

            picks.append({
                'ticker': ticker,
                'name': name,
                'source': 'KIS',
                'reason': str(reason)[:200],
            })

        _logger.info('[broker] KIS 추천 종목 %d개 수집', len(picks))
        return picks

    except Exception as e:
        _logger.warning('[broker] KIS 리서치 조회 실패: %s', e)
        return []


def _load_cache(today_str: str) -> list[dict[str, Any]] | None:
    """캐시 파일 로드. 없거나 파싱 실패 시 None."""
    cache_path = os.path.join(CACHE_DIR, f'broker_picks_{today_str}.json')
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _logger.info('[broker] 캐시 로드: %s (%d건)', cache_path, len(data))
        return data
    except Exception as e:
        _logger.warning('[broker] 캐시 로드 실패 (%s): %s', cache_path, e)
        return None


def _save_cache(today_str: str, picks: list[dict[str, Any]]) -> None:
    """수집 결과를 캐시 파일에 저장. 실패해도 예외 전파 안 함."""
    cache_path = os.path.join(CACHE_DIR, f'broker_picks_{today_str}.json')
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(picks, f, ensure_ascii=False, indent=2)
        _logger.info('[broker] 캐시 저장: %s', cache_path)
    except Exception as e:
        _logger.warning('[broker] 캐시 저장 실패: %s', e)


def get_broker_picks() -> list[dict[str, Any]]:
    """
    오늘 증권사 추천 종목 반환.

    캐시(cache/broker_picks_YYYYMMDD.json) 있으면 재사용.
    없으면 KIS API 시도 → 실패 시 빈 리스트 반환.

    Returns
    -------
    list[dict]
        [{"ticker": "005930.KS", "name": "삼성전자", "source": "KIS", "reason": "..."}]
    """
    today_str = date.today().strftime('%Y%m%d')

    # 1. 캐시 확인
    cached = _load_cache(today_str)
    if cached is not None:
        return cached

    # 2. KIS API 시도
    picks: list[dict[str, Any]] = []
    try:
        env = _get_env()
        app_key = env.get('KIS_APP_KEY', '').strip()
        secret_key = env.get('KIS_SECRET_KEY', '').strip()
        kis_env = env.get('KIS_ENV', 'vts').strip()

        if not app_key or not secret_key:
            _logger.info('[broker] KIS_APP_KEY 또는 KIS_SECRET_KEY 미설정 — KIS API 건너뜀')
        else:
            base_url = _get_base_url(kis_env)
            token = _fetch_access_token(base_url, app_key, secret_key)
            if token:
                picks = _fetch_kis_research_picks(base_url, app_key, token)

    except Exception as e:
        _logger.warning('[broker] get_broker_picks 예외 (빈 리스트 반환): %s', e)
        picks = []

    # 3. 캐시 저장 (빈 리스트라도 저장해 재시도 방지)
    _save_cache(today_str, picks)
    return picks
