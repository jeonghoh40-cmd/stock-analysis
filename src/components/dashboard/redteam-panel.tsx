"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import type { RedTeamResponse, CounterArgumentItem } from "@/lib/types"

const riskColor: Record<string, string> = {
  HIGH: "bg-red-100 text-red-800",
  MEDIUM: "bg-orange-100 text-orange-800",
  LOW: "bg-green-100 text-green-800",
}

function CounterArgument({ item }: { item: CounterArgumentItem }) {
  const [open, setOpen] = useState(false)
  const severityColor = item.severity === "HIGH"
    ? "bg-red-100 text-red-800"
    : item.severity === "MEDIUM"
      ? "bg-orange-100 text-orange-800"
      : "bg-green-100 text-green-800"

  return (
    <div className="rounded-md border border-zinc-200 dark:border-zinc-700">
      <button type="button" className="flex w-full items-center justify-between px-4 py-3 text-left text-sm" onClick={() => setOpen(!open)}>
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{item.title}</span>
        <div className="flex items-center gap-2">
          <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", severityColor)}>
            {item.severity}
          </span>
          <span className="text-zinc-400">{open ? "\u25B2" : "\u25BC"}</span>
        </div>
      </button>
      {open && (
        <div className="border-t border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{item.argument}</p>
          {item.evidence.length > 0 && (
            <ul className="mt-2 space-y-1">
              {item.evidence.map((e, i) => (
                <li key={i} className="text-xs text-zinc-500 before:mr-1 before:content-['\u2022']">{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export function RedteamPanel({ redteam }: { redteam: RedTeamResponse }) {
  const color = riskColor[redteam.overall_risk_level] ?? "bg-gray-100 text-gray-800"

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">레드팀 반론</h2>
        <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", color)}>
          리스크 {redteam.overall_risk_level}
        </span>
      </div>
      <div className="space-y-2">
        {redteam.counter_arguments.map((ca) => (
          <CounterArgument key={ca.title} item={ca} />
        ))}
      </div>
      {redteam.recommendation && (
        <p className="mt-4 text-sm leading-relaxed text-zinc-500">{redteam.recommendation}</p>
      )}
    </div>
  )
}
