import { NextRequest } from "next/server"
import fs from "fs/promises"
import path from "path"

const OUTPUT_ROOT = path.resolve(process.cwd(), "outputs")

import { accessSync } from "fs"

function findAnalyzerReportsDir(): string | null {
  for (const name of ["vc_investment_analyzer", "vc-investment-analyzer"]) {
    const dir = path.resolve(process.cwd(), "..", name, "reports")
    try {
      accessSync(dir)
      return dir
    } catch {
      // skip
    }
  }
  return null
}

const ANALYZER_REPORTS = findAnalyzerReportsDir()

// 다운로드 허용 경로 검증
function isAllowedPath(filePath: string): boolean {
  const resolved = path.resolve(filePath)
  if (resolved.startsWith(OUTPUT_ROOT)) return true
  if (ANALYZER_REPORTS && resolved.startsWith(ANALYZER_REPORTS)) return true
  return false
}

// GET: 단일 파일 다운로드
export async function GET(request: NextRequest) {
  const filePath = request.nextUrl.searchParams.get("path")

  if (!filePath) {
    return Response.json({ error: "path 파라미터가 필요합니다." }, { status: 400 })
  }

  if (!isAllowedPath(filePath)) {
    return Response.json({ error: "허용되지 않은 경로입니다." }, { status: 403 })
  }

  try {
    const buffer = await fs.readFile(filePath)
    const fileName = path.basename(filePath)

    return new Response(buffer, {
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
      },
    })
  } catch {
    return Response.json({ error: "파일을 찾을 수 없습니다." }, { status: 404 })
  }
}

// POST: 기업명으로 생성된 보고서 목록 조회
export async function POST(request: NextRequest) {
  const { company, reportType, directory } = await request.json()

  // 기존 호환: directory가 직접 전달된 경우
  const searchDirs: string[] = []

  if (directory && isAllowedPath(directory)) {
    searchDirs.push(directory)
  }

  if (company) {
    // outputs/{company} 에서 검색
    searchDirs.push(path.join(OUTPUT_ROOT, company))

    // analyzer reports에서도 검색
    if (ANALYZER_REPORTS) {
      searchDirs.push(ANALYZER_REPORTS)
      searchDirs.push(path.join(ANALYZER_REPORTS, "ic_reports"))
    }
  }

  const allFiles: { name: string; path: string; size: number; modified: Date }[] = []
  const seen = new Set<string>()

  for (const dir of searchDirs) {
    try {
      const entries = await fs.readdir(dir)
      const docxFiles = entries.filter((f) => {
        if (!f.endsWith(".docx") || f.startsWith("~")) return false
        if (company && !f.startsWith(company)) return false
        if (reportType === "ic" && !f.includes("투심위")) return false
        if (reportType === "investment" && !f.includes("투자검토")) return false
        return true
      })

      for (const name of docxFiles) {
        if (seen.has(name)) continue
        seen.add(name)
        const fullPath = path.join(dir, name)
        try {
          const stat = await fs.stat(fullPath)
          allFiles.push({ name, path: fullPath, size: stat.size, modified: stat.mtime })
        } catch {
          // skip
        }
      }
    } catch {
      // dir doesn't exist, skip
    }
  }

  // 최신 순 정렬, 최대 5개
  allFiles.sort((a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime())
  return Response.json({ files: allFiles.slice(0, 5) })
}
