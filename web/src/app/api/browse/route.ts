import { NextRequest } from "next/server"
import fs from "fs/promises"
import path from "path"
import os from "os"

type EntryInfo = {
  name: string
  path: string
  isDir: boolean
  size: number
  modified: string
}

// 탐색 가능한 루트 경로 목록 (Windows/Linux 대응)
async function getRoots(): Promise<EntryInfo[]> {
  const roots: EntryInfo[] = []

  if (process.platform === "win32") {
    for (const letter of "CDEFGHIJKLMNOPQRSTUVWXYZ") {
      const drive = `${letter}:\\`
      try {
        await fs.access(drive)
        roots.push({
          name: `${letter}: 드라이브`,
          path: drive,
          isDir: true,
          size: 0,
          modified: "",
        })
      } catch {
        // skip
      }
    }
  } else {
    roots.push({ name: "/", path: "/", isDir: true, size: 0, modified: "" })
    for (const dir of ["/data", "/mnt"]) {
      try {
        await fs.access(dir)
        roots.push({ name: dir, path: dir, isDir: true, size: 0, modified: "" })
      } catch {
        // skip
      }
    }
  }

  const home = os.homedir()
  roots.push({ name: "홈 폴더", path: home, isDir: true, size: 0, modified: "" })

  return roots
}

// 파일 탐색 기능 활성화 여부 (환경변수로 명시적 허용 필요)
const BROWSE_ENABLED = process.env.ENABLE_FILE_BROWSE === "true"

// 로컬(서버PC) 접속인지 확인 — 외부 접속자는 서버 파일시스템 탐색 차단
// 주의: x-forwarded-for/x-real-ip 헤더는 클라이언트가 위조할 수 있으므로
// 반드시 ENABLE_FILE_BROWSE 환경변수와 함께 사용해야 함
function isLocalRequest(request: NextRequest): boolean {
  // 환경변수로 기능이 명시적으로 활성화되지 않으면 차단
  if (!BROWSE_ENABLED) return false

  const forwarded = request.headers.get("x-forwarded-for")
  const realIp = request.headers.get("x-real-ip")
  const ip = forwarded?.split(",")[0]?.trim() || realIp || ""

  const localIps = ["127.0.0.1", "::1", "localhost", "0.0.0.0"]
  if (localIps.includes(ip) || ip === "") return true

  // 사내 네트워크 대역 (192.168.x.x, 10.x.x.x, 172.16~31.x.x)
  if (ip.startsWith("192.168.") || ip.startsWith("10.")) return true
  if (ip.startsWith("172.")) {
    const second = parseInt(ip.split(".")[1] || "0", 10)
    if (second >= 16 && second <= 31) return true
  }

  return false
}

export async function POST(request: NextRequest) {
  if (!isLocalRequest(request)) {
    return Response.json(
      { error: "서버 파일 탐색은 사내 네트워크에서만 가능합니다. 파일 업로드를 이용해주세요." },
      { status: 403 }
    )
  }

  const { dirPath } = await request.json()

  if (!dirPath) {
    const roots = await getRoots()
    return Response.json({ entries: roots, currentPath: "", parentPath: null })
  }

  try {
    const resolvedPath = path.resolve(dirPath)

    // 먼저 경로 접근 가능 여부 확인
    await fs.access(resolvedPath)

    const names = await fs.readdir(resolvedPath)
    const entries: EntryInfo[] = []

    for (const name of names) {
      // 숨김 파일/시스템 폴더 제외
      if (name.startsWith(".") || name.startsWith("$") || name.startsWith("~")) continue
      if (["node_modules", "__pycache__", ".git", "System Volume Information"].includes(name)) continue

      const fullPath = path.join(resolvedPath, name)
      try {
        const stat = await fs.stat(fullPath)
        entries.push({
          name,
          path: fullPath,
          isDir: stat.isDirectory(),
          size: stat.isDirectory() ? 0 : stat.size,
          modified: stat.mtime.toISOString(),
        })
      } catch {
        // stat 실패해도 폴더일 가능성이 있으므로 기본값으로 추가
        entries.push({
          name,
          path: fullPath,
          isDir: true,
          size: 0,
          modified: "",
        })
      }
    }

    // 폴더 먼저, 이름순 정렬
    entries.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })

    const parentPath = path.dirname(resolvedPath)

    return Response.json({
      entries,
      currentPath: resolvedPath,
      parentPath: parentPath !== resolvedPath ? parentPath : null,
    })
  } catch (err: unknown) {
    const e = err as NodeJS.ErrnoException
    let message = `경로를 열 수 없습니다: ${dirPath}`
    if (e.code === "ENOENT") {
      message = `경로가 존재하지 않습니다: ${dirPath}`
    } else if (e.code === "EACCES" || e.code === "EPERM") {
      message = `접근 권한이 없습니다: ${dirPath}`
    } else if (e.code === "ENOTDIR") {
      message = `폴더가 아닙니다: ${dirPath}`
    }
    return Response.json(
      { error: `${message} [${e.code || "UNKNOWN"}]`, entries: [], currentPath: dirPath, parentPath: null },
      { status: 400 }
    )
  }
}
