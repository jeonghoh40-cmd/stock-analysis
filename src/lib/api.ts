import type {
  CompanyCodes,
  FullAnalysisResponse,
  SimilarResponse,
  UploadExtractResponse,
} from "./types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const API_KEY = process.env.NEXT_PUBLIC_VC_API_KEY || ""

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" }
  if (API_KEY) h["X-API-Key"] = API_KEY
  return h
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {}
  if (API_KEY) h["X-API-Key"] = API_KEY
  return h
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: headers(),
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

export async function analyzeCompany(
  codes: CompanyCodes
): Promise<FullAnalysisResponse> {
  return post("/api/v1/analysis/full", codes)
}

export async function searchSimilarCases(
  codes: CompanyCodes
): Promise<SimilarResponse> {
  return post("/api/v1/analysis/similar", codes)
}

// ---------------------------------------------------------------------------
// File Upload
// ---------------------------------------------------------------------------

export function uploadAndExtract(
  files: File[],
  onProgress?: (percent: number) => void
): Promise<UploadExtractResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    files.forEach((f) => formData.append("files", f))

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${API_BASE}/api/v1/upload/extract`)

    if (API_KEY) {
      xhr.setRequestHeader("X-API-Key", API_KEY)
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`))
      }
    }

    xhr.onerror = () => reject(new Error("Upload failed: network error"))
    xhr.send(formData)
  })
}

// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

export async function getPortfolio(): Promise<unknown> {
  return get("/api/v1/monitoring/portfolio")
}

export async function getAlerts(): Promise<unknown> {
  return get("/api/v1/monitoring/alerts")
}

export async function getCompanyDetail(company: string): Promise<unknown> {
  return get(`/api/v1/monitoring/${encodeURIComponent(company)}/detail`)
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export async function healthCheck(): Promise<boolean> {
  try {
    await get("/")
    return true
  } catch {
    return false
  }
}
