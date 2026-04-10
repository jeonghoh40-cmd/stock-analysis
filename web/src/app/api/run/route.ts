import { NextRequest } from "next/server"
import path from "path"
import fs from "fs/promises"

// 보고서 출력 기본 경로 (서버 내부)
const OUTPUT_ROOT = path.resolve(process.cwd(), "outputs")

// 안전한 문자열 검증: 영문, 한글, 숫자, 공백, 하이픈, 언더스코어, 점만 허용
const SAFE_NAME_RE = /^[\w\s\uAC00-\uD7A3._-]+$/
const VALID_REPORT_TYPES = ["investment", "ic", "both"]

export async function POST(request: NextRequest) {
  const { company, irDir, reportType, options } = await request.json()

  if (!company || !irDir) {
    return Response.json(
      { error: "company, irDir는 필수입니다." },
      { status: 400 }
    )
  }

  // 입력값 검증: 명령 인젝션 방지
  if (typeof company !== "string" || !SAFE_NAME_RE.test(company)) {
    return Response.json(
      { error: "기업명에 허용되지 않는 문자가 포함되어 있습니다." },
      { status: 400 }
    )
  }

  if (typeof irDir !== "string" || irDir.includes("..")) {
    return Response.json(
      { error: "잘못된 경로입니다." },
      { status: 400 }
    )
  }

  if (reportType && !VALID_REPORT_TYPES.includes(reportType)) {
    return Response.json(
      { error: "잘못된 보고서 유형입니다." },
      { status: 400 }
    )
  }

  // 기업별 출력 디렉토리 (서버 내부, 사용자에게 노출 안 됨)
  const outputDir = path.join(OUTPUT_ROOT, company)
  await fs.mkdir(outputDir, { recursive: true })

  const scriptPath = path.resolve(process.cwd(), "scripts", "run_analysis.py")
  const pythonBin = process.env.PYTHON_BIN || "python"

  const args = [
    scriptPath,
    "--company",
    company,
    "--ir-dir",
    irDir,
    "--output-dir",
    outputDir,
  ]

  if (reportType) args.push("--report-type", reportType)
  if (options?.noWeb) args.push("--no-web")
  if (options?.noApi) args.push("--no-api")

  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      const { spawn } = await import("child_process")

      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "info", message: `실행 시작: ${company}` })}\n\n`
        )
      )

      const proc = spawn(pythonBin, args, {
        cwd: process.cwd(),
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      })

      proc.stdout.on("data", (data: Buffer) => {
        const text = data.toString("utf-8")
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "stdout", message: text })}\n\n`
          )
        )
      })

      proc.stderr.on("data", (data: Buffer) => {
        const text = data.toString("utf-8")
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "stderr", message: text })}\n\n`
          )
        )
      })

      proc.on("close", (code: number | null) => {
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({
              type: "done",
              message: code === 0 ? "완료" : `종료 코드: ${code}`,
              exitCode: code,
            })}\n\n`
          )
        )
        controller.close()
      })

      proc.on("error", (err: Error) => {
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "error", message: err.message })}\n\n`
          )
        )
        controller.close()
      })
    },
  })

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  })
}
