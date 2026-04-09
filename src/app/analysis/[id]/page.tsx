"use client"

import { use, useEffect, useState } from "react"
import Link from "next/link"
import { getAnalysis } from "@/lib/storage"
import { Tabs } from "@/components/ui/tabs"
import { Spinner } from "@/components/ui/spinner"
import { Badge } from "@/components/ui/badge"
import { ScoreSummary } from "@/components/dashboard/score-summary"
import { DimensionChart } from "@/components/dashboard/dimension-chart"
import { HardGates } from "@/components/dashboard/hard-gates"
import { RedFlags } from "@/components/dashboard/red-flags"
import { SimilarCases } from "@/components/dashboard/similar-cases"
import { RedteamPanel } from "@/components/dashboard/redteam-panel"
import { BenchmarkPanel } from "@/components/dashboard/benchmark-panel"
import { ICOpinions } from "@/components/dashboard/ic-opinions"
import { ConfidencePanel } from "@/components/dashboard/confidence-panel"
import { ReportViewer } from "@/components/reports/report-viewer"
import { ReportDownload } from "@/components/reports/report-download"
import type { AnalysisHistory } from "@/lib/types"

const TABS = [
  { id: "dashboard", label: "분석 결과" },
  { id: "investment-review", label: "투자검토보고서" },
  { id: "ic-meeting", label: "투심위보고서" },
]

export default function AnalysisDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const [analysis, setAnalysis] = useState<AnalysisHistory | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAnalysis(id).then((data) => {
      setAnalysis(data)
      setLoading(false)
    })
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="py-20 text-center">
        <p className="text-zinc-500">분석 결과를 찾을 수 없습니다.</p>
        <Link href="/history" className="mt-4 inline-block text-sm text-blue-600 hover:text-blue-700">
          이력으로 돌아가기
        </Link>
      </div>
    )
  }

  const { result } = analysis

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {analysis.company_name}
            </h1>
            <Badge variant="info">{result.scoring.verdict}</Badge>
          </div>
          <p className="mt-1 text-sm text-zinc-500">
            {new Date(analysis.timestamp).toLocaleString("ko-KR")} |{" "}
            {analysis.codes.sector.join(", ")}
          </p>
        </div>
        <Link href="/history" className="text-sm text-zinc-500 hover:text-zinc-700">
          목록으로
        </Link>
      </div>

      {/* 탭 */}
      <Tabs tabs={TABS}>
        {(activeTab) => {
          if (activeTab === "dashboard") {
            return (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <ScoreSummary scoring={result.scoring} />
                <DimensionChart dimensions={result.scoring.dimensions} />
                <HardGates gates={result.scoring.hard_gates} />
                <RedFlags flags={result.scoring.red_flags} />
                <SimilarCases similar={result.similar} />
                <RedteamPanel redteam={result.redteam} />
                <BenchmarkPanel benchmark={result.benchmark} />
                <ICOpinions icOpinions={result.ic_opinions} />
                <div className="lg:col-span-2">
                  <ConfidencePanel
                    items={result.scoring.confidence_items}
                    estimatedFieldCount={result.scoring.estimated_field_count}
                    avgConfidence={result.scoring.avg_confidence}
                  />
                </div>
              </div>
            )
          }

          if (activeTab === "investment-review") {
            return (
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
                    투자검토보고서
                  </h2>
                  <ReportDownload
                    markdown={result.report_markdown}
                    companyName={analysis.company_name}
                    reportType="투자검토보고서"
                  />
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
                  <ReportViewer markdown={result.report_markdown} />
                </div>
              </div>
            )
          }

          if (activeTab === "ic-meeting") {
            const icMarkdown = result.ic_meeting_markdown || ""
            return (
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">
                    투심위보고서
                  </h2>
                  <ReportDownload
                    markdown={icMarkdown}
                    companyName={analysis.company_name}
                    reportType="투심위보고서"
                  />
                </div>
                <div className="rounded-lg border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
                  {icMarkdown ? (
                    <ReportViewer markdown={icMarkdown} />
                  ) : (
                    <div className="py-12 text-center text-sm text-zinc-400">
                      투심위보고서는 백엔드에서 IC 보고서 생성 기능이 활성화되면 표시됩니다.
                    </div>
                  )}
                </div>
              </div>
            )
          }

          return null
        }}
      </Tabs>
    </div>
  )
}
