"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import FileUploadZone from "@/components/analysis/file-upload-zone"
import AnalysisForm from "@/components/analysis/analysis-form"
import { Button } from "@/components/ui/button"
import { analyzeCompany } from "@/lib/api"
import { saveAnalysis, generateId } from "@/lib/storage"
import type { CompanyCodes, ExtractedFile } from "@/lib/types"
import { cn } from "@/lib/utils"

const STEPS = [
  { id: 1, label: "자료 업로드" },
  { id: 2, label: "정보 입력" },
  { id: 3, label: "분석 실행" },
]

export default function NewAnalysisPage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [extractedText, setExtractedText] = useState("")
  const [extractedFiles, setExtractedFiles] = useState<ExtractedFile[]>([])
  const [codes, setCodes] = useState<CompanyCodes | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function handleExtracted(combinedText: string, files: ExtractedFile[]) {
    setExtractedText(combinedText)
    setExtractedFiles(files)
  }

  function handleFormSubmit(formCodes: CompanyCodes) {
    setCodes(formCodes)
    setStep(3)
  }

  async function handleRunAnalysis() {
    if (!codes) return
    setLoading(true)
    setError(null)

    try {
      const result = await analyzeCompany(codes)
      const id = generateId()
      await saveAnalysis(id, codes.company_name, codes, result)
      router.push(`/analysis/${id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "분석 중 오류가 발생했습니다.")
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        새 투자 분석
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        자료를 업로드하고 기업 정보를 입력하여 종합 투자 분석을 수행합니다.
      </p>

      {/* 스텝 표시 */}
      <div className="mb-8 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2">
            <button
              onClick={() => s.id < step && setStep(s.id)}
              disabled={s.id > step}
              className={cn(
                "flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                step === s.id
                  ? "bg-blue-600 text-white"
                  : s.id < step
                    ? "bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400"
                    : "bg-zinc-100 text-zinc-400 dark:bg-zinc-800"
              )}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/20 text-xs">
                {s.id < step ? "\u2713" : s.id}
              </span>
              {s.label}
            </button>
            {i < STEPS.length - 1 && (
              <div className={cn(
                "h-px w-8",
                s.id < step ? "bg-blue-300" : "bg-zinc-200 dark:bg-zinc-700"
              )} />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: 파일 업로드 */}
      {step === 1 && (
        <div className="space-y-6">
          <FileUploadZone onExtracted={handleExtracted} />
          <div className="flex justify-between">
            <Button
              variant="ghost"
              onClick={() => {
                setExtractedText("")
                setStep(2)
              }}
            >
              건너뛰기
            </Button>
            <Button
              onClick={() => setStep(2)}
              disabled={extractedFiles.length === 0}
            >
              다음 단계
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: 정보 입력 폼 */}
      {step === 2 && (
        <AnalysisForm
          initialIrContext={extractedText}
          onSubmit={handleFormSubmit}
        />
      )}

      {/* Step 3: 확인 + 실행 */}
      {step === 3 && codes && (
        <div className="space-y-6">
          <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-4 text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              분석 요약
            </h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="text-zinc-500">기업명</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">{codes.company_name}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">산업군</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">{codes.sector.join(", ")}</dd>
              </div>
              {codes.stage && (
                <div>
                  <dt className="text-zinc-500">투자 단계</dt>
                  <dd className="font-medium text-zinc-900 dark:text-zinc-100">{codes.stage}</dd>
                </div>
              )}
              {codes.founder_grade && (
                <div>
                  <dt className="text-zinc-500">창업자 등급</dt>
                  <dd className="font-medium text-zinc-900 dark:text-zinc-100">{codes.founder_grade}</dd>
                </div>
              )}
              {codes.market_grade && (
                <div>
                  <dt className="text-zinc-500">시장 등급</dt>
                  <dd className="font-medium text-zinc-900 dark:text-zinc-100">{codes.market_grade}</dd>
                </div>
              )}
              {codes.ir_context && (
                <div className="col-span-2">
                  <dt className="text-zinc-500">투심위 텍스트</dt>
                  <dd className="mt-1 max-h-32 overflow-y-auto rounded bg-zinc-50 p-2 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                    {codes.ir_context.slice(0, 500)}
                    {codes.ir_context.length > 500 && "..."}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
              {error}
            </div>
          )}

          <div className="flex justify-between">
            <Button variant="secondary" onClick={() => setStep(2)}>
              이전 단계
            </Button>
            <Button onClick={handleRunAnalysis} disabled={loading}>
              {loading ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  분석 중...
                </>
              ) : (
                "분석 시작"
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
