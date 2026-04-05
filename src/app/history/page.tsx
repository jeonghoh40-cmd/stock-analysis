"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getAllAnalyses, deleteAnalysis, clearAllAnalyses } from "@/lib/storage"
import type { AnalysisHistory } from "@/lib/types"

function verdictVariant(verdict: string) {
  if (verdict.includes("STRONG_BUY") || verdict.includes("BUY")) return "success" as const
  if (verdict.includes("NEUTRAL")) return "warning" as const
  if (verdict.includes("WATCH") || verdict.includes("PASS")) return "error" as const
  return "default" as const
}

export default function HistoryPage() {
  const [analyses, setAnalyses] = useState<AnalysisHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [compareMode, setCompareMode] = useState(false)

  useEffect(() => {
    getAllAnalyses().then((data) => {
      setAnalyses(data)
      setLoading(false)
    })
  }, [])

  const filtered = analyses.filter(
    (a) =>
      a.company_name.toLowerCase().includes(search.toLowerCase()) ||
      a.codes.sector.some((s) => s.toLowerCase().includes(search.toLowerCase()))
  )

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < 2) {
        next.add(id)
      }
      return next
    })
  }

  async function handleDelete(id: string) {
    await deleteAnalysis(id)
    setAnalyses((prev) => prev.filter((a) => a.id !== id))
  }

  function handleClearAll() {
    if (confirm("모든 분석 이력을 삭제하시겠습니까?")) {
      clearAllAnalyses()
      setAnalyses([])
    }
  }

  const selectedItems = analyses.filter((a) => selected.has(a.id))

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">분석 이력</h1>
          <p className="mt-1 text-sm text-zinc-500">{analyses.length}건의 분석 결과</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={compareMode ? "primary" : "secondary"}
            onClick={() => {
              setCompareMode(!compareMode)
              setSelected(new Set())
            }}
          >
            {compareMode ? "비교 취소" : "비교하기"}
          </Button>
          {analyses.length > 0 && (
            <Button variant="ghost" onClick={handleClearAll}>
              전체 삭제
            </Button>
          )}
        </div>
      </div>

      {/* 검색 */}
      <div className="mb-6">
        <input
          type="text"
          placeholder="기업명 또는 산업군으로 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
      </div>

      {/* 비교 모드 선택 바 */}
      {compareMode && selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 rounded-lg bg-blue-50 px-4 py-3 dark:bg-blue-950/30">
          <span className="text-sm text-blue-700 dark:text-blue-400">
            {selected.size}/2 선택됨
          </span>
          {selected.size === 2 && (
            <Link
              href={`/history?compare=${Array.from(selected).join(",")}`}
              className="text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              비교 보기
            </Link>
          )}
        </div>
      )}

      {/* 비교 뷰 */}
      {compareMode && selectedItems.length === 2 && (
        <div className="mb-8 grid grid-cols-2 gap-6">
          {selectedItems.map((a) => (
            <Card key={a.id}>
              <h3 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {a.company_name}
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">종합 점수</span>
                  <span className="font-bold">{a.result.scoring.overall_score}점</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">판정</span>
                  <Badge variant={verdictVariant(a.result.scoring.verdict)}>
                    {a.result.scoring.verdict}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Hard Gate</span>
                  <Badge variant={a.result.scoring.hard_gate_pass ? "success" : "error"}>
                    {a.result.scoring.hard_gate_pass ? "ALL PASS" : "FAIL"}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">유사 성공률</span>
                  <span>{(a.result.similar.success_rate * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">평균 멀티플</span>
                  <span>{a.result.similar.avg_multiple.toFixed(1)}x</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* 이력 목록 */}
      {loading ? (
        <p className="text-sm text-zinc-400">로딩 중...</p>
      ) : filtered.length === 0 ? (
        <Card className="py-12 text-center">
          <p className="text-zinc-500">
            {search ? "검색 결과가 없습니다." : "분석 이력이 없습니다."}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((a) => (
            <div key={a.id} className="relative">
              {compareMode && (
                <button
                  onClick={() => toggleSelect(a.id)}
                  className={`absolute -left-2 -top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 text-xs ${
                    selected.has(a.id)
                      ? "border-blue-500 bg-blue-500 text-white"
                      : "border-zinc-300 bg-white dark:border-zinc-600 dark:bg-zinc-800"
                  }`}
                >
                  {selected.has(a.id) && "\u2713"}
                </button>
              )}
              <Link href={`/analysis/${a.id}`}>
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
                  <div className="mt-3 flex items-end justify-between">
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                      {a.result.scoring.overall_score}
                      <span className="text-sm text-zinc-400"> 점</span>
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {a.codes.sector.slice(0, 2).map((s) => (
                        <Badge key={s} variant="info">{s}</Badge>
                      ))}
                    </div>
                  </div>
                </Card>
              </Link>
              {!compareMode && (
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    handleDelete(a.id)
                  }}
                  className="absolute right-2 top-2 rounded p-1 text-zinc-300 hover:text-red-500"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
