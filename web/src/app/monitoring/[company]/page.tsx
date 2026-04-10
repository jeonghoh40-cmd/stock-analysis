"use client"

import { use } from "react"
import { Card } from "@/components/ui/card"

export default function CompanyMonitoringPage({
  params,
}: {
  params: Promise<{ company: string }>
}) {
  const { company } = use(params)
  const companyName = decodeURIComponent(company)

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        {companyName} 모니터링
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        기업별 상세 KPI 및 모니터링 데이터
      </p>

      <Card className="py-12 text-center">
        <p className="text-zinc-500">
          기업별 상세 모니터링 기능은 백엔드 API 연결 후 활성화됩니다.
        </p>
      </Card>
    </div>
  )
}
