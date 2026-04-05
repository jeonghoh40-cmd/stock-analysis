"use client"

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts"
import type { DimensionScores } from "@/lib/types"

const dimensionLabels: Record<keyof DimensionScores, string> = {
  founder_quality: "경영진 역량",
  market_opportunity: "시장 기회",
  competitive_position: "경쟁 우위",
  unit_economics: "유닛이코노믹스",
  financial_health: "재무 건전성",
  exit_potential: "엑싯 잠재력",
}

export function DimensionChart({ dimensions }: { dimensions: DimensionScores }) {
  const data = Object.entries(dimensionLabels).map(([key, label]) => ({
    dimension: label,
    score: dimensions[key as keyof DimensionScores],
  }))

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">6차원 분석</h2>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
            <PolarGrid stroke="#e4e4e7" />
            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: "#71717a" }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10, fill: "#a1a1aa" }} />
            <Radar name="점수" dataKey="score" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.25} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
