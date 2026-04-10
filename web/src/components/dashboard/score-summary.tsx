"use client"

import { cn } from "@/lib/utils"
import type { ScoreResponse } from "@/lib/types"

const verdictConfig: Record<string, { label: string; color: string }> = {
  STRONG_BUY: { label: "적극 투자", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
  BUY: { label: "투자 권고", color: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400" },
  NEUTRAL: { label: "중립", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400" },
  WATCH: { label: "관망", color: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400" },
  PASS: { label: "패스", color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400" },
}

export function ScoreSummary({ scoring }: { scoring: ScoreResponse }) {
  const verdict = verdictConfig[scoring.verdict] ?? {
    label: scoring.verdict,
    color: "bg-gray-100 text-gray-800",
  }

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">종합 점수</h2>
      <div className="flex items-end gap-3">
        <span className="text-5xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          {scoring.overall_score.toFixed(1)}
        </span>
        <span className="mb-1 text-lg text-zinc-400">/ 100</span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", verdict.color)}>
          {verdict.label}
        </span>
        <span className={cn(
          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
          scoring.hard_gate_pass
            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
        )}>
          Hard Gate {scoring.hard_gate_pass ? "ALL PASS" : "FAIL"}
        </span>
      </div>
      <div className="mt-4 space-y-1 text-sm text-zinc-600 dark:text-zinc-400">
        <p>추정 필드 수: {scoring.estimated_field_count}개</p>
        <p>평균 신뢰도: {(scoring.avg_confidence * 100).toFixed(0)}%</p>
      </div>
      {scoring.rationale && (
        <p className="mt-4 text-sm leading-relaxed text-zinc-500">{scoring.rationale}</p>
      )}
    </div>
  )
}
