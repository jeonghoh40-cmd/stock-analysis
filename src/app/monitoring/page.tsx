"use client"

import { useEffect, useState } from "react"
import { Card, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import { getPortfolio, getAlerts } from "@/lib/api"

interface PortfolioCompany {
  name: string
  investment_date: string
  score: number
  score_delta: number
  status: string
  alert_count: number
}

interface Alert {
  company: string
  severity: string
  message: string
  timestamp: string
}

export default function MonitoringPage() {
  const [companies, setCompanies] = useState<PortfolioCompany[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [portfolio, alertData] = await Promise.all([
          getPortfolio(),
          getAlerts(),
        ])
        setCompanies(portfolio as PortfolioCompany[])
        setAlerts(alertData as Alert[])
      } catch {
        setError("모니터링 데이터를 불러올 수 없습니다. 백엔드 서버를 확인해 주세요.")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  function severityVariant(severity: string) {
    switch (severity.toUpperCase()) {
      case "CRITICAL": return "error" as const
      case "WARNING": return "warning" as const
      default: return "info" as const
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        포트폴리오 모니터링
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        투자 기업 현황 및 알림을 확인합니다.
      </p>

      {error ? (
        <Card className="py-12 text-center">
          <p className="text-zinc-500">{error}</p>
          <p className="mt-2 text-xs text-zinc-400">
            백엔드 서버에 모니터링 API가 구현되면 데이터가 표시됩니다.
          </p>
        </Card>
      ) : (
        <>
          {/* 알림 요약 */}
          <div className="mb-6 flex gap-3">
            {["CRITICAL", "WARNING", "INFO"].map((sev) => {
              const count = alerts.filter((a) => a.severity.toUpperCase() === sev).length
              return (
                <Badge key={sev} variant={severityVariant(sev)}>
                  {sev}: {count}
                </Badge>
              )
            })}
          </div>

          {/* 포트폴리오 테이블 */}
          <Card className="mb-8 overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800/50">
                    <th className="px-4 py-3 text-left font-medium text-zinc-500">기업명</th>
                    <th className="px-4 py-3 text-left font-medium text-zinc-500">투자일</th>
                    <th className="px-4 py-3 text-right font-medium text-zinc-500">현재 점수</th>
                    <th className="px-4 py-3 text-right font-medium text-zinc-500">변동</th>
                    <th className="px-4 py-3 text-center font-medium text-zinc-500">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {companies.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-zinc-400">
                        포트폴리오 데이터가 없습니다.
                      </td>
                    </tr>
                  ) : (
                    companies.map((c, i) => (
                      <tr
                        key={i}
                        className="border-b border-zinc-100 last:border-0 dark:border-zinc-800"
                      >
                        <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-100">
                          {c.name}
                        </td>
                        <td className="px-4 py-3 text-zinc-500">{c.investment_date}</td>
                        <td className="px-4 py-3 text-right font-medium">{c.score}</td>
                        <td className={`px-4 py-3 text-right font-medium ${c.score_delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {c.score_delta >= 0 ? "+" : ""}{c.score_delta}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Badge variant={c.status === "정상" || c.status === "양호" ? "success" : "warning"}>
                            {c.status}
                          </Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* 최근 알림 */}
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            최근 알림
          </h2>
          {alerts.length === 0 ? (
            <Card className="py-8 text-center">
              <p className="text-zinc-400">활성 알림이 없습니다.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {alerts.map((a, i) => (
                <Card key={i} className="flex items-start gap-3 py-4">
                  <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
                  <div className="flex-1">
                    <p className="text-sm text-zinc-900 dark:text-zinc-100">
                      <span className="font-medium">{a.company}</span> — {a.message}
                    </p>
                    <p className="mt-0.5 text-xs text-zinc-400">{a.timestamp}</p>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
