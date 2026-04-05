"use client"

import { cn } from "@/lib/utils"
import type { SimilarResponse } from "@/lib/types"

export function SimilarCases({ similar }: { similar: SimilarResponse }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">유사 케이스</h2>
      <div className="mb-4 flex gap-6">
        <div>
          <p className="text-xs text-zinc-400">유사 기업군 성공률</p>
          <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{(similar.success_rate * 100).toFixed(0)}%</p>
        </div>
        <div>
          <p className="text-xs text-zinc-400">평균 멀티플</p>
          <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{similar.avg_multiple.toFixed(1)}x</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-zinc-500 dark:border-zinc-700">
              <th className="pb-2 pr-3 font-medium">#</th>
              <th className="pb-2 pr-3 font-medium">기업명</th>
              <th className="pb-2 pr-3 font-medium">유사도</th>
              <th className="pb-2 pr-3 font-medium">결과</th>
              <th className="pb-2 font-medium">멀티플</th>
            </tr>
          </thead>
          <tbody>
            {similar.similar_cases.map((c, i) => (
              <tr key={c.name} className="border-b last:border-b-0 dark:border-zinc-800">
                <td className="py-2 pr-3 text-zinc-400">{i + 1}</td>
                <td className="py-2 pr-3 text-zinc-700 dark:text-zinc-300">{c.name}</td>
                <td className="py-2 pr-3 text-zinc-700 dark:text-zinc-300">{(c.similarity * 100).toFixed(0)}%</td>
                <td className="py-2 pr-3">
                  <span className={cn(
                    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                    c.outcome.includes("성공") || c.outcome === "SUCCESS"
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-800"
                  )}>
                    {c.outcome}
                  </span>
                </td>
                <td className="py-2 text-zinc-700 dark:text-zinc-300">{c.multiple.toFixed(1)}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
