"use client"

import { cn } from "@/lib/utils"
import type { BenchmarkResponse } from "@/lib/types"

const positionColor: Record<string, string> = {
  "\uc0c1\uc704": "bg-green-100 text-green-800",
  "\ud3c9\uade0": "bg-yellow-100 text-yellow-800",
  "\ud558\uc704": "bg-red-100 text-red-800",
  ABOVE: "bg-green-100 text-green-800",
  AVERAGE: "bg-yellow-100 text-yellow-800",
  BELOW: "bg-red-100 text-red-800",
}

export function BenchmarkPanel({ benchmark }: { benchmark: BenchmarkResponse | null }) {
  if (!benchmark) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">벤치마크 비교</h2>
        <p className="text-sm text-zinc-400">벤치마크 데이터 없음</p>
      </div>
    )
  }

  const posColor = positionColor[benchmark.relative_position] ?? "bg-gray-100 text-gray-800"

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">벤치마크 비교</h2>
        <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", posColor)}>
          {benchmark.relative_position}
        </span>
      </div>
      {benchmark.sector_benchmarks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-zinc-500 dark:border-zinc-700">
                <th className="pb-2 pr-3 font-medium">섹터</th>
                <th className="pb-2 pr-3 font-medium">기업수</th>
                <th className="pb-2 pr-3 font-medium">성공률</th>
                <th className="pb-2 font-medium">평균 멀티플</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.sector_benchmarks.map((s) => (
                <tr key={s.segment} className="border-b last:border-b-0 dark:border-zinc-800">
                  <td className="py-2 pr-3 text-zinc-700 dark:text-zinc-300">{s.segment}</td>
                  <td className="py-2 pr-3 text-zinc-700 dark:text-zinc-300">{s.total_count}</td>
                  <td className="py-2 pr-3 text-zinc-700 dark:text-zinc-300">{(s.success_rate * 100).toFixed(0)}%</td>
                  <td className="py-2 text-zinc-700 dark:text-zinc-300">{s.avg_multiple.toFixed(1)}x</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {benchmark.key_insights.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-zinc-500">인사이트</p>
          <ul className="space-y-1">
            {benchmark.key_insights.map((insight, i) => (
              <li key={i} className="text-sm text-zinc-600 dark:text-zinc-400 before:mr-1 before:content-['\u2022']">{insight}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
