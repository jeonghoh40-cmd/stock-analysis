"use client"

import { cn } from "@/lib/utils"
import type { ICOpinionResponse } from "@/lib/types"

const stanceColor: Record<string, string> = {
  FOR: "bg-green-500",
  AGAINST: "bg-red-500",
  CONDITIONAL: "bg-yellow-400",
  NEUTRAL: "bg-gray-400",
}

export function ICOpinions({ icOpinions }: { icOpinions: ICOpinionResponse | null }) {
  if (!icOpinions) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">투심위 의견</h2>
        <p className="text-sm text-zinc-400">투심위 텍스트 미입력</p>
      </div>
    )
  }

  const total = Object.values(icOpinions.stance_distribution).reduce((a, b) => a + b, 0)

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">투심위 의견</h2>
      {total > 0 && (
        <div className="mb-4">
          <div className="mb-2 flex gap-3 text-xs text-zinc-500">
            {Object.entries(icOpinions.stance_distribution).map(([stance, count]) => (
              <span key={stance} className="flex items-center gap-1">
                <span className={cn("inline-block h-2.5 w-2.5 rounded-full", stanceColor[stance] ?? "bg-gray-300")} />
                {stance} ({count})
              </span>
            ))}
          </div>
          <div className="flex h-3 overflow-hidden rounded-full">
            {Object.entries(icOpinions.stance_distribution).map(([stance, count]) => (
              <div key={stance} className={cn(stanceColor[stance] ?? "bg-gray-300")} style={{ width: `${(count / total) * 100}%` }} />
            ))}
          </div>
        </div>
      )}
      {icOpinions.consensus && (
        <div className="mb-4">
          <p className="mb-1 text-xs font-medium text-zinc-500">합의</p>
          <p className="text-sm text-zinc-700 dark:text-zinc-300">{icOpinions.consensus}</p>
        </div>
      )}
      {icOpinions.key_concerns.length > 0 && (
        <div className="mb-4">
          <p className="mb-1 text-xs font-medium text-zinc-500">주요 우려사항</p>
          <ul className="space-y-1">
            {icOpinions.key_concerns.map((c, i) => (
              <li key={i} className="text-sm text-zinc-600 dark:text-zinc-400">
                <span className="font-medium">[{c.category}]</span> {c.concern}
                {c.frequency > 1 && <span className="ml-1 text-xs text-zinc-400">(x{c.frequency})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {icOpinions.risk_flags.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-zinc-500">리스크 플래그</p>
          <div className="flex flex-wrap gap-1.5">
            {icOpinions.risk_flags.map((flag, i) => (
              <span key={i} className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">
                {flag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
