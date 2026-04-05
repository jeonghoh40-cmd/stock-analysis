"use client"

import { useState } from "react"
import { Card, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SelectField } from "@/components/ui/select-field"
import { Spinner } from "@/components/ui/spinner"
import { searchSimilarCases } from "@/lib/api"
import {
  SECTORS,
  STAGES,
  FOUNDER_GRADES,
  MARKET_GRADES,
  MARKET_POSITIONS,
} from "@/lib/constants"
import type { CompanyCodes, SimilarResponse } from "@/lib/types"

export default function SimilarPage() {
  const [selectedSectors, setSelectedSectors] = useState<string[]>([])
  const [stage, setStage] = useState("")
  const [founderGrade, setFounderGrade] = useState("")
  const [marketGrade, setMarketGrade] = useState("")
  const [marketPosition, setMarketPosition] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SimilarResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  function handleSectorToggle(value: string) {
    setSelectedSectors((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]
    )
  }

  async function handleSearch() {
    if (selectedSectors.length === 0) {
      setError("산업군을 하나 이상 선택해 주세요.")
      return
    }
    setError(null)
    setLoading(true)

    const codes: CompanyCodes = {
      company_name: "검색",
      sector: selectedSectors,
      era: "",
      stage,
      founder_grade: founderGrade,
      market_grade: marketGrade,
      market_position: marketPosition,
      global_expansion: "",
      vc_liquidity: "",
      tech_listing: "",
      urgency_grade: "",
      ir_context: "",
      dynamic_evaluations: [],
    }

    try {
      const res = await searchSimilarCases(codes)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색 중 오류가 발생했습니다.")
    } finally {
      setLoading(false)
    }
  }

  function outcomeVariant(outcome: string) {
    if (outcome.includes("우수성공") || outcome.includes("성공")) return "success" as const
    if (outcome.includes("실패")) return "error" as const
    return "warning" as const
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        유사 케이스 검색
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        과거 182건 투자 데이터에서 유사한 기업을 찾습니다.
      </p>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* 검색 조건 */}
        <div className="lg:col-span-1">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              검색 조건
            </h2>
            <div className="space-y-4">
              <div>
                <span className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  산업군 <span className="text-red-500">*</span>
                </span>
                <div className="grid grid-cols-2 gap-1.5">
                  {SECTORS.slice(0, 12).map((s) => (
                    <label
                      key={s.value}
                      className="flex cursor-pointer items-center gap-1.5 rounded border border-zinc-200 px-2 py-1.5 text-xs transition-colors select-none hover:bg-zinc-50 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50 dark:border-zinc-700"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSectors.includes(s.value)}
                        onChange={() => handleSectorToggle(s.value)}
                        className="h-3.5 w-3.5 rounded border-zinc-300 text-blue-600"
                      />
                      {s.label}
                    </label>
                  ))}
                </div>
              </div>
              <SelectField label="투자 단계" value={stage} onChange={setStage} options={STAGES} />
              <SelectField label="창업자 등급" value={founderGrade} onChange={setFounderGrade} options={FOUNDER_GRADES} />
              <SelectField label="시장 등급" value={marketGrade} onChange={setMarketGrade} options={MARKET_GRADES} />
              <SelectField label="시장 포지션" value={marketPosition} onChange={setMarketPosition} options={MARKET_POSITIONS} />

              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}

              <Button onClick={handleSearch} disabled={loading} className="w-full">
                {loading ? <Spinner className="h-4 w-4" /> : "검색"}
              </Button>
            </div>
          </Card>
        </div>

        {/* 검색 결과 */}
        <div className="lg:col-span-2">
          {result ? (
            <div className="space-y-4">
              <div className="flex gap-4">
                <Card className="flex-1">
                  <CardTitle>유사 케이스 성공률</CardTitle>
                  <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    {(result.success_rate * 100).toFixed(0)}%
                  </p>
                </Card>
                <Card className="flex-1">
                  <CardTitle>평균 멀티플</CardTitle>
                  <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    {result.avg_multiple.toFixed(1)}x
                  </p>
                </Card>
              </div>

              {result.similar_cases.map((c, i) => (
                <Card key={i}>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{c.name}</h3>
                      <div className="mt-1 flex gap-1">
                        {c.sector.map((s) => (
                          <Badge key={s} variant="info">{s}</Badge>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge variant={outcomeVariant(c.outcome)}>{c.outcome}</Badge>
                      <p className="mt-1 text-sm text-zinc-500">{c.multiple.toFixed(1)}x</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-500">유사도</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${c.similarity * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                        {(c.similarity * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="flex flex-col items-center py-16">
              <svg className="mb-4 h-12 w-12 text-zinc-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-zinc-500">검색 조건을 입력하고 검색 버튼을 눌러주세요.</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
