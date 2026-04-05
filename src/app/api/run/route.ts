import { NextRequest } from "next/server"
import path from "path"

export async function POST(request: NextRequest) {
  const { company, irDir, outputDir, options } = await request.json()

  if (!company || !irDir || !outputDir) {
    return Response.json(
      { error: "company, irDir, outputDir 모두 필수입니다." },
      { status: 400 }
    )
  }

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
        shell: true,
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
