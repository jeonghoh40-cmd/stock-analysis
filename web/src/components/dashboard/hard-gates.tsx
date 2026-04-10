"use client"

import { cn } from "@/lib/utils"
import type { HardGateResult } from "@/lib/types"

export function HardGates({ gates }: { gates: HardGateResult[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">Hard Gates</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-zinc-500 dark:border-zinc-700">
              <th className="pb-2 pr-4 font-medium">게이트</th>
              <th className="pb-2 pr-4 font-medium">항목</th>
              <th className="pb-2 pr-4 font-medium">값</th>
              <th className="pb-2 font-medium">결과</th>
            </tr>
          </thead>
          <tbody>
            {gates.map((g) => (
              <tr key={g.gate} className={cn("border-b last:border-b-0 dark:border-zinc-800", !g.passed && "bg-red-50 dark:bg-red-950/20")}>
                <td className="py-2 pr-4 font-mono text-xs text-zinc-600 dark:text-zinc-400">{g.gate}</td>
                <td className="py-2 pr-4 text-zinc-700 dark:text-zinc-300">{g.name}</td>
                <td className="py-2 pr-4 text-zinc-700 dark:text-zinc-300">{g.value}</td>
                <td className="py-2">
                  <span className={cn(
                    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                    g.passed ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                  )}>
                    {g.passed ? "PASS" : "FAIL"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
