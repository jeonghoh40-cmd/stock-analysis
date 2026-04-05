// 폼 선택지 상수 (config/tag_schema.json 기반)

export const SECTORS = [
  { value: "SW", label: "SW/SaaS" },
  { value: "DEEPTECH", label: "딥테크" },
  { value: "BIO", label: "바이오" },
  { value: "HEALTHCARE", label: "헬스케어" },
  { value: "COMMERCE", label: "커머스" },
  { value: "FOOD", label: "푸드테크" },
  { value: "PLATFORM", label: "플랫폼" },
  { value: "LOGISTICS", label: "물류" },
  { value: "O2O", label: "O2O" },
  { value: "CONTENT", label: "콘텐츠" },
  { value: "AI", label: "AI" },
  { value: "FINTECH", label: "핀테크" },
  { value: "ENERGY", label: "에너지" },
  { value: "MANUFACTURING", label: "제조" },
  { value: "GLOBAL", label: "글로벌" },
  { value: "ENTERTAINMENT", label: "엔터테인먼트" },
  { value: "SECURITY", label: "보안" },
  { value: "MOBILITY", label: "모빌리티" },
  { value: "AGRITECH", label: "애그테크" },
  { value: "PROPTECH", label: "프롭테크" },
  { value: "EDTECH", label: "에듀테크" },
  { value: "GAMING", label: "게이밍" },
  { value: "HARDWARE", label: "하드웨어" },
] as const

export const ERAS = [
  { value: "ERA_08", label: "2008~2012 (금융위기 이후 회복기)" },
  { value: "ERA_15", label: "2013~2019 (안정 성장기)" },
  { value: "ERA_COVID", label: "2020~2021 (코로나 특수)" },
  { value: "ERA_RATE_HIKE", label: "2022~2023 (금리 인상기)" },
  { value: "ERA_AI", label: "2024~현재 (AI 투자 붐)" },
] as const

export const STAGES = [
  { value: "Seed/Pre-A", label: "Seed / Pre-A" },
  { value: "Series-A", label: "Series A" },
  { value: "Series-B", label: "Series B" },
  { value: "Series-C+", label: "Series C+" },
  { value: "Pre-IPO", label: "Pre-IPO" },
  { value: "Growth", label: "Growth" },
] as const

export const FOUNDER_GRADES = [
  { value: "FOUNDER_S", label: "S (연쇄창업 성공 + 도메인 전문가)" },
  { value: "FOUNDER_A", label: "A (강한 도메인 전문성)" },
  { value: "FOUNDER_B", label: "B (잠재력 있으나 미검증)" },
  { value: "FOUNDER_C", label: "C (역량 부족)" },
] as const

export const MARKET_GRADES = [
  { value: "MARKET_S", label: "S (글로벌 초대형 + 고성장)" },
  { value: "MARKET_A", label: "A (대형 + 구조적 성장)" },
  { value: "MARKET_B", label: "B (중형 또는 성장성 제한)" },
  { value: "MARKET_C", label: "C (소형/정체)" },
] as const

export const MARKET_POSITIONS = [
  { value: "POS_1ST", label: "1위" },
  { value: "POS_TOP3", label: "Top 3" },
  { value: "POS_NICHE", label: "니치 리더" },
  { value: "POS_FOLLOWER", label: "팔로워" },
] as const

export const GLOBAL_EXPANSIONS = [
  { value: "GLOBAL_PROVEN", label: "해외 매출 검증 완료" },
  { value: "GLOBAL_READY", label: "해외 법인/파트너 구축 완료" },
  { value: "GLOBAL_POTENTIAL", label: "글로벌 확장 가능성 (미실행)" },
  { value: "GLOBAL_DOMESTIC", label: "국내 전용" },
  { value: "GLOBAL_NONE", label: "해당 없음" },
] as const

export const VC_LIQUIDITIES = [
  { value: "LIQUIDITY_EXCESS", label: "과잉 유동성 (저금리)" },
  { value: "LIQUIDITY_NORMAL", label: "정상적 VC 시장" },
  { value: "LIQUIDITY_TIGHT", label: "유동성 경색 (긴축)" },
] as const

export const TECH_LISTINGS = [
  { value: "TECH_ELIGIBLE", label: "기술특례 적격" },
  { value: "TECH_NA", label: "해당 없음" },
] as const

export const URGENCY_GRADES = [
  { value: "URGENT_HIGH", label: "높음 (긴급)" },
  { value: "URGENT_MEDIUM", label: "보통" },
  { value: "URGENT_LOW", label: "낮음 (여유)" },
] as const

export const AI_UTILIZATION = [
  { value: "CORE_AI", label: "핵심 AI (AI가 핵심 제품)" },
  { value: "ENHANCED", label: "AI 활용 (AI로 제품 강화)" },
  { value: "WRAPPER", label: "래퍼 (API 래핑 수준)" },
  { value: "NONE", label: "미활용" },
] as const

export const NETWORK_EFFECTS = [
  { value: "STRONG", label: "강함" },
  { value: "MODERATE", label: "보통" },
  { value: "WEAK", label: "약함" },
  { value: "NONE", label: "없음" },
] as const
