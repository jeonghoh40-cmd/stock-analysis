// 폼 선택지 상수 — config/tag_schema.json에서 가져옴 (단일 소스)
// Python 스크립트(scripts/run_analysis.py)와 값을 공유하므로 직접 수정하지 말 것.

import schema from "../../config/tag_schema.json"

type Option = { value: string; label: string }

function options(key: keyof typeof schema): readonly Option[] {
  const node = schema[key] as { options?: Option[] } | undefined
  return (node?.options ?? []) as readonly Option[]
}

export const SECTORS = options("sector")
export const ERAS = options("era")
export const STAGES = options("stage")
export const FOUNDER_GRADES = options("founder_grade")
export const MARKET_GRADES = options("market_grade")
export const MARKET_POSITIONS = options("market_position")
export const GLOBAL_EXPANSIONS = options("global_expansion")
export const VC_LIQUIDITIES = options("vc_liquidity")
export const TECH_LISTINGS = options("tech_listing")
export const URGENCY_GRADES = options("urgency_grade")
export const AI_UTILIZATION = options("ai_utilization")
export const NETWORK_EFFECTS = options("network_effect")
