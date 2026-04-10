"use client"

import { cn } from "@/lib/utils"
import type { ConfidenceItem } from "@/lib/types"

export function ConfidencePanel({
  items,
  estimatedFieldCount,
  avgConfidence,
}: {
  items: ConfidenceItem[]
  estimatedFieldCount: number
  avgConfidence: number
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">데이터 신뢰도</h2>
      <div className="mb-4 flex gap-6">
        <div>
          <p className="text-xs text-zinc-400">추정 필드 수</p>
          <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{estimatedFieldCount}개</p>
        </div>
        <div>
          <p className="text-xs text-zinc-400">평균 신뢰도</p>
          <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{(avgConfidence * 100).toFixed(0)}%</p>
        </div>
      </div>
      {items.length > 0 && (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.field}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-700 dark:text-zinc-300">{item.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">{item.value}</span>
                  <span className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                    item.source === "확인" || item.source === "CONFIRMED"
                      ? "bg-green-100 text-green-800"
                      : "bg-yellow-100 text-yellow-800"
                  )}>
                    {item.source}
                  </span>
                </div>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    item.confidence >= 0.8 ? "bg-green-500" : item.confidence >= 0.5 ? "bg-yellow-500" : "bg-red-500"
                  )}
                  style={{ width: `${item.confidence * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
