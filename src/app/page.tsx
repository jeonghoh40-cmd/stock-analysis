"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Card, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getAllAnalyses } from "@/lib/storage"
import type { AnalysisHistory } from "@/lib/types"

function verdictVariant(verdict: string) {
  if (verdict.includes("STRONG_BUY") || verdict.includes("BUY"))
    return "success" as const
  if (verdict.includes("NEUTRAL")) return "warning" as const
  if (verdict.includes("WATCH") || verdict.includes("PASS"))
    return "error" as const
  return "default" as const
}

export default function HomePage() {
  const [analyses, setAnalyses] = useState<AnalysisHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAllAnalyses().then((data) => {
      setAnalyses(data)
      setLoading(false)
    })
  }, [])

  const avgScore =
    analyses.length > 0
      ? Math.round(
          analyses.reduce((sum, a) => sum + a.result.scoring.overall_score, 0) /
            analyses.length
        )
      : 0

  const recentAnalyses = analyses.slice(0, 6)

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            대시보드
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            VC 투자 검토 고도화 시스템
          </p>
        </div>
        <Link href="/analysis/new">
          <Button>새 분석 시작</Button>
        </Link>
      </div>

      {/* 통계 카드 */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardTitle>총 분석 수</CardTitle>
          <p className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {loading ? "-" : analyses.length}
          </p>
        </Card>
        <Card>
          <CardTitle>평균 점수</CardTitle>
          <p className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {loading ? "-" : avgScore}
            <span className="text-lg text-zinc-400"> / 100</span>
          </p>
        </Card>
        <Card>
          <CardTitle>최근 분석</CardTitle>
          <p className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {loading
              ? "-"
              : analyses.length > 0
                ? new Date(analyses[0].timestamp).toLocaleDateString("ko-KR")
                : "없음"}
          </p>
        </Card>
      </div>

      {/* 최근 분석 결과 */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          최근 분석 결과
        </h2>
        {analyses.length > 0 && (
          <Link
            href="/history"
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            전체 보기
          </Link>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-zinc-400">로딩 중...</p>
      ) : recentAnalyses.length === 0 ? (
        <Card className="flex flex-col items-center py-12">
          <p className="mb-4 text-zinc-500">아직 분석 이력이 없습니다.</p>
          <Link href="/analysis/new">
            <Button>첫 번째 분석 시작하기</Button>
          </Link>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {recentAnalyses.map((a) => (
            <Link key={a.id} href={`/analysis/${a.id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {a.company_name}
                    </h3>
                    <p className="mt-1 text-xs text-zinc-400">
                      {new Date(a.timestamp).toLocaleString("ko-KR")}
                    </p>
                  </div>
                  <Badge variant={verdictVariant(a.result.scoring.verdict)}>
                    {a.result.scoring.verdict}
                  </Badge>
                </div>
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                      {a.result.scoring.overall_score}
                      <span className="text-sm text-zinc-400"> 점</span>
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {a.codes.sector.slice(0, 2).map((s) => (
                      <Badge key={s} variant="info">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
