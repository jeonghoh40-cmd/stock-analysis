"use client"

import { useState } from "react"
import { SelectField } from "@/components/ui/select-field"
import {
  SECTORS,
  ERAS,
  STAGES,
  FOUNDER_GRADES,
  MARKET_GRADES,
  MARKET_POSITIONS,
  GLOBAL_EXPANSIONS,
  VC_LIQUIDITIES,
  TECH_LISTINGS,
  URGENCY_GRADES,
  AI_UTILIZATION,
  NETWORK_EFFECTS,
} from "@/lib/constants"
import type { CompanyCodes } from "@/lib/types"

interface AnalysisFormProps {
  initialIrContext?: string
  onSubmit: (codes: CompanyCodes) => void
  loading?: boolean
  error?: string | null
}

export default function AnalysisForm({
  initialIrContext = "",
  onSubmit,
  loading = false,
  error,
}: AnalysisFormProps) {
  const [companyName, setCompanyName] = useState("")
  const [selectedSectors, setSelectedSectors] = useState<string[]>([])
  const [era, setEra] = useState("")
  const [stage, setStage] = useState("")
  const [founderGrade, setFounderGrade] = useState("")
  const [marketGrade, setMarketGrade] = useState("")
  const [marketPosition, setMarketPosition] = useState("")
  const [globalExpansion, setGlobalExpansion] = useState("")
  const [vcLiquidity, setVcLiquidity] = useState("")
  const [techListing, setTechListing] = useState("")
  const [urgencyGrade, setUrgencyGrade] = useState("")
  const [irContext, setIrContext] = useState(initialIrContext)
  const [showExtra, setShowExtra] = useState(false)
  const [aiUtilization, setAiUtilization] = useState("")
  const [dataMoat, setDataMoat] = useState(false)
  const [networkEffect, setNetworkEffect] = useState("")
  const [esgScore, setEsgScore] = useState(0.5)
  const [formError, setFormError] = useState<string | null>(null)

  function handleSectorToggle(value: string) {
    setSelectedSectors((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)

    if (!companyName.trim()) {
      setFormError("기업명을 입력해 주세요.")
      return
    }
    if (selectedSectors.length === 0) {
      setFormError("산업군을 하나 이상 선택해 주세요.")
      return
    }

    const dynamicEvaluations: CompanyCodes["dynamic_evaluations"] = []
    if (aiUtilization) {
      dynamicEvaluations.push({ criterion_id: "ai_utilization", value: aiUtilization, note: "" })
    }
    if (dataMoat) {
      dynamicEvaluations.push({ criterion_id: "data_moat", value: "yes", note: "" })
    }
    if (networkEffect) {
      dynamicEvaluations.push({ criterion_id: "network_effect", value: networkEffect, note: "" })
    }
    if (esgScore !== 0.5) {
      dynamicEvaluations.push({ criterion_id: "esg_fit", value: esgScore, note: "" })
    }

    onSubmit({
      company_name: companyName.trim(),
      sector: selectedSectors,
      era,
      stage,
      founder_grade: founderGrade,
      market_grade: marketGrade,
      market_position: marketPosition,
      global_expansion: globalExpansion,
      vc_liquidity: vcLiquidity,
      tech_listing: techListing,
      urgency_grade: urgencyGrade,
      ir_context: irContext,
      dynamic_evaluations: dynamicEvaluations,
    })
  }

  const displayError = formError || error

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {displayError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {displayError}
        </div>
      )}

      {/* 기업 정보 */}
      <section className="space-y-4 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
          기업 정보
        </h2>
        <div>
          <label htmlFor="company-name" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            기업명 <span className="text-red-500">*</span>
          </label>
          <input
            id="company-name"
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="예: 스타트업 A"
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>
      </section>

      {/* 분류 코드 */}
      <section className="space-y-6 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
          분류 코드
        </h2>

        <div>
          <span className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            산업군 <span className="text-red-500">*</span>
          </span>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {SECTORS.map((s) => (
              <label
                key={s.value}
                className="flex cursor-pointer items-center gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm transition-colors select-none hover:bg-zinc-50 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50 dark:border-zinc-700 dark:hover:bg-zinc-800 dark:has-[:checked]:border-blue-600 dark:has-[:checked]:bg-blue-950"
              >
                <input
                  type="checkbox"
                  checked={selectedSectors.includes(s.value)}
                  onChange={() => handleSectorToggle(s.value)}
                  className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                />
                {s.label}
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <SelectField label="투자 시대" value={era} onChange={setEra} options={ERAS} />
          <SelectField label="투자 단계" value={stage} onChange={setStage} options={STAGES} />
          <SelectField label="창업자 등급" value={founderGrade} onChange={setFounderGrade} options={FOUNDER_GRADES} />
          <SelectField label="시장 등급" value={marketGrade} onChange={setMarketGrade} options={MARKET_GRADES} />
          <SelectField label="시장 포지션" value={marketPosition} onChange={setMarketPosition} options={MARKET_POSITIONS} />
          <SelectField label="글로벌 확장" value={globalExpansion} onChange={setGlobalExpansion} options={GLOBAL_EXPANSIONS} />
          <SelectField label="VC 유동성" value={vcLiquidity} onChange={setVcLiquidity} options={VC_LIQUIDITIES} />
          <SelectField label="기술특례" value={techListing} onChange={setTechListing} options={TECH_LISTINGS} />
          <SelectField label="재무 긴급도" value={urgencyGrade} onChange={setUrgencyGrade} options={URGENCY_GRADES} />
        </div>
      </section>

      {/* 투심위 텍스트 */}
      <section className="space-y-4 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            투심위 텍스트
          </h2>
          <span className="text-sm text-zinc-400">(선택)</span>
          {initialIrContext && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
              자동 추출 텍스트
            </span>
          )}
        </div>
        <textarea
          value={irContext}
          onChange={(e) => setIrContext(e.target.value)}
          placeholder="투심위 보고서 또는 IR 자료 텍스트를 붙여넣기 하세요..."
          rows={6}
          className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
      </section>

      {/* 추가 평가기준 */}
      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <button
          type="button"
          onClick={() => setShowExtra(!showExtra)}
          className="flex w-full items-center justify-between px-6 py-4 text-left"
        >
          <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
            추가 평가기준 <span className="text-sm font-normal text-zinc-400">(선택)</span>
          </h2>
          <svg
            className={`h-5 w-5 text-zinc-400 transition-transform ${showExtra ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showExtra && (
          <div className="space-y-4 border-t border-zinc-200 px-6 pb-6 pt-4 dark:border-zinc-800">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <SelectField label="AI 활용도" value={aiUtilization} onChange={setAiUtilization} options={AI_UTILIZATION} />
              <SelectField label="네트워크 효과" value={networkEffect} onChange={setNetworkEffect} options={NETWORK_EFFECTS} />
            </div>
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={dataMoat}
                onChange={(e) => setDataMoat(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                데이터 해자 보유
              </span>
            </label>
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                ESG 적합성: <span className="font-mono text-blue-600 dark:text-blue-400">{esgScore.toFixed(2)}</span>
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={esgScore}
                onChange={(e) => setEsgScore(parseFloat(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-zinc-200 accent-blue-600 dark:bg-zinc-700"
              />
              <div className="mt-1 flex justify-between text-xs text-zinc-400">
                <span>0 (낮음)</span>
                <span>1 (높음)</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 제출 */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading && (
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {loading ? "분석 중..." : "분석 시작"}
        </button>
      </div>
    </form>
  )
}
