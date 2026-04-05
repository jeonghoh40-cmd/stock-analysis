// ScoreResponse
export interface HardGateResult {
  gate: string
  name: string
  value: string
  passed: boolean
  note: string
}

export interface DimensionScores {
  founder_quality: number
  market_opportunity: number
  competitive_position: number
  unit_economics: number
  financial_health: number
  exit_potential: number
}

export interface RedFlagItem {
  flag: string
  name: string
  triggered: boolean
  detail: string
}

export interface ConfidenceItem {
  field: string
  label: string
  value: string
  source: string
  confidence: number
  reasoning: string
}

export interface DynamicCriterionResultItem {
  criterion_id: string
  name: string
  value: string | number
  score: number
  max_score: number
  is_hard_gate_fail: boolean
  note: string
}

export interface ScoreResponse {
  company_name: string
  overall_score: number
  verdict: string
  hard_gate_pass: boolean
  hard_gates: HardGateResult[]
  dimensions: DimensionScores
  red_flags: RedFlagItem[]
  rationale: string
  confidence_items: ConfidenceItem[]
  estimated_field_count: number
  avg_confidence: number
  dynamic_score: number
  dynamic_max: number
  dynamic_results: DynamicCriterionResultItem[]
  dynamic_hard_gate_fails: string[]
}

// SimilarResponse
export interface SimilarCaseItem {
  name: string
  similarity: number
  outcome: string
  multiple: number
  sector: string[]
}

export interface SimilarResponse {
  company_name: string
  similar_cases: SimilarCaseItem[]
  success_rate: number
  avg_multiple: number
}

// RedTeamResponse
export interface CounterArgumentItem {
  title: string
  severity: string
  argument: string
  evidence: string[]
  related_red_flag: string
}

export interface RedTeamResponse {
  company_name: string
  overall_risk_level: string
  counter_arguments: CounterArgumentItem[]
  recommendation: string
}

// ICOpinionResponse
export interface ICOpinionResponse {
  company_name: string
  total_opinions: number
  stance_distribution: Record<string, number>
  key_concerns: Array<{ category: string; concern: string; frequency: number }>
  key_strengths: Array<{ category: string; strength: string; frequency: number }>
  consensus: string
  risk_flags: string[]
}

// BenchmarkResponse
export interface BenchmarkStatItem {
  category: string
  segment: string
  total_count: number
  success_count: number
  failure_count: number
  success_rate: number
  avg_multiple: number
  median_multiple: number
  notable_cases: string[]
}

export interface BenchmarkResponse {
  company_name: string
  sector_benchmarks: BenchmarkStatItem[]
  stage_benchmark: BenchmarkStatItem | null
  founder_benchmark: BenchmarkStatItem | null
  era_benchmark: BenchmarkStatItem | null
  liquidity_benchmark: BenchmarkStatItem | null
  global_benchmark: BenchmarkStatItem | null
  position_benchmark: BenchmarkStatItem | null
  overall_peer_success_rate: number
  overall_peer_avg_multiple: number
  relative_position: string
  key_insights: string[]
}

// FullAnalysisResponse
export interface FullAnalysisResponse {
  company_name: string
  scoring: ScoreResponse
  similar: SimilarResponse
  redteam: RedTeamResponse
  ic_opinions: ICOpinionResponse | null
  benchmark: BenchmarkResponse | null
  report_markdown: string
  ic_meeting_markdown?: string
}

// Input form types
export interface CompanyCodes {
  company_name: string
  sector: string[]
  era: string
  stage: string
  founder_grade: string
  market_grade: string
  market_position: string
  global_expansion: string
  vc_liquidity: string
  tech_listing: string
  urgency_grade: string
  ir_context: string
  dynamic_evaluations: Array<{
    criterion_id: string
    value: string | number
    note: string
  }>
}

// Analysis history
export interface AnalysisHistory {
  id: string
  timestamp: string
  company_name: string
  codes: CompanyCodes
  result: FullAnalysisResponse
}

// File upload
export interface ExtractedFile {
  filename: string
  file_type: string
  char_count: number
  extracted_text: string
  status: "success" | "error"
  error?: string
}

export interface UploadExtractResponse {
  files: ExtractedFile[]
  combined_text: string
}
