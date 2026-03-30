"""
토큰 캐싱 모듈
- 동일한 데이터에 대한 재분석 방지
- 해시 기반 캐시 키 생성
- JSON 캐시 파일 관리
"""

import os
import sys
import json
import hashlib
import datetime
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, 'cache')


def ensure_cache_dir():
    """캐시 디렉토리 생성"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def generate_cache_key(data: dict) -> str:
    """
    데이터의 해시값을 캐시 키로 생성
    
    Args:
        data: 캐싱할 데이터 딕셔너리
    
    Returns:
        MD5 해시 문자열
    """
    # 데이터를 정렬된 JSON 문자열로 변환
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    
    # MD5 해시 생성
    cache_key = hashlib.md5(json_str.encode('utf-8')).hexdigest()
    
    return cache_key


def get_cached_analysis(data: dict, cache_hours: int = 24) -> Optional[dict]:
    """
    캐시된 분석 결과 조회
    
    Args:
        data: 분석 데이터 (캐시 키 생성용)
        cache_hours: 캐시 유효기간 (시간, 기본 24 시간)
    
    Returns:
        캐시된 분석 결과 또는 None
    """
    ensure_cache_dir()
    
    cache_key = generate_cache_key(data)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 캐시 유효기간 확인
        cached_at = datetime.datetime.fromisoformat(cache_data['cached_at'])
        now = datetime.datetime.now()
        age_hours = (now - cached_at).total_seconds() / 3600
        
        if age_hours > cache_hours:
            # 캐시 만료
            os.remove(cache_file)
            return None
        
        return cache_data['result']
    
    except Exception as e:
        print(f"  ⚠️ 캐시 읽기 오류: {e}")
        return None


def save_analysis_cache(data: dict, result: str) -> bool:
    """
    분석 결과를 캐시에 저장
    
    Args:
        data: 분석 데이터 (캐시 키 생성용)
        result: 분석 결과 (Claude 응답)
    
    Returns:
        성공 여부
    """
    ensure_cache_dir()
    
    cache_key = generate_cache_key(data)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    try:
        cache_data = {
            'cached_at': datetime.datetime.now().isoformat(),
            'data_summary': {
                'kospi_buy_count': len(data.get('kospi_buy', [])),
                'kosdaq_buy_count': len(data.get('kosdaq_buy', [])),
                'us_buy_count': len(data.get('us_buy', [])),
            },
            'result': result
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        return True
    
    except Exception as e:
        print(f"  ⚠️ 캐시 쓰기 오류: {e}")
        return False


def clear_old_cache(max_age_days: int = 7) -> int:
    """
    오래된 Claude 분석 캐시 파일 삭제.

    Claude 캐시 파일은 32자리 MD5 hex 이름을 사용한다.
    screening_*, fundamentals.json, broker_picks_*, claude_structured_* 등
    다른 캐시 파일은 건드리지 않는다.

    Args:
        max_age_days: 최대 보관 기간 (일)

    Returns:
        삭제된 파일 수
    """
    import re
    ensure_cache_dir()

    # Claude 분석 캐시 파일만 대상: 32자리 16진수 이름
    _MD5_PATTERN = re.compile(r'^[0-9a-f]{32}\.json$')

    deleted_count = 0
    now = datetime.datetime.now()

    for filename in os.listdir(CACHE_DIR):
        if not _MD5_PATTERN.match(filename):
            continue  # screening/fundamentals 등 다른 캐시는 무시

        cache_file = os.path.join(CACHE_DIR, filename)

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            cached_at = datetime.datetime.fromisoformat(cache_data['cached_at'])
            age_days = (now - cached_at).total_seconds() / 86400

            if age_days > max_age_days:
                os.remove(cache_file)
                deleted_count += 1

        except Exception:
            # 파싱 오류 시에만 삭제 (형식 이상 파일)
            try:
                os.remove(cache_file)
                deleted_count += 1
            except Exception:
                pass

    return deleted_count


def get_cache_stats() -> dict:
    """
    캐시 통계 정보 반환
    
    Returns:
        캐시 통계 딕셔너리
    """
    ensure_cache_dir()
    
    total_files = 0
    total_size = 0
    oldest_file = None
    newest_file = None
    
    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith('.json'):
            continue
        
        cache_file = os.path.join(CACHE_DIR, filename)
        total_files += 1
        total_size += os.path.getsize(cache_file)
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cached_at = datetime.datetime.fromisoformat(cache_data['cached_at'])
            
            if oldest_file is None or cached_at < oldest_file:
                oldest_file = cached_at
            if newest_file is None or cached_at > newest_file:
                newest_file = cached_at
        
        except:
            pass
    
    return {
        'total_files': total_files,
        'total_size_kb': round(total_size / 1024, 2),
        'oldest_cache': oldest_file.isoformat() if oldest_file else '없음',
        'newest_cache': newest_file.isoformat() if newest_file else '없음',
        'cache_dir': CACHE_DIR
    }


# ═══════════════════════════════════════════════════════════════
# 메인 실행 (테스트용)
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  토큰 캐싱 모듈 테스트")
    print("=" * 60)
    
    # 캐시 통계
    stats = get_cache_stats()
    print(f"\n📊 캐시 통계:")
    print(f"  총 파일: {stats['total_files']}개")
    print(f"  총 크기: {stats['total_size_kb']} KB")
    print(f"  가장 오래된 캐시: {stats['oldest_cache']}")
    print(f"  가장 최신 캐시: {stats['newest_cache']}")
    print(f"  캐시 디렉토리: {stats['cache_dir']}")
    
    # 오래된 캐시 정리
    deleted = clear_old_cache(7)
    if deleted > 0:
        print(f"\n🧹 7 일 이상된 캐시 {deleted}개 삭제 완료")
    
    # 테스트 데이터
    test_data = {
        'kospi_buy': [{'name': '삼성전자', 'score': 50}],
        'test_date': datetime.datetime.now().isoformat()
    }
    
    # 캐시 저장 테스트
    test_result = "테스트 분석 결과입니다."
    if save_analysis_cache(test_data, test_result):
        print("\n✅ 캐시 저장 테스트 성공")
    
    # 캐시 조회 테스트
    cached = get_cached_analysis(test_data)
    if cached:
        print(f"✅ 캐시 조회 테스트 성공: {cached[:20]}...")
    else:
        print("⚠️ 캐시 조회 테스트 실패")
    
    print("\n" + "=" * 60 + "\n")
