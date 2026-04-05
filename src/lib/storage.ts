import { AnalysisHistory, CompanyCodes, FullAnalysisResponse } from "./types"

const STORAGE_KEY = "vc_analysis_history"
const CRYPTO_KEY_NAME = "vc_crypto_key"

// ---------------------------------------------------------------------------
// AES-GCM 암호화 (Web Crypto API)
// ---------------------------------------------------------------------------

async function getOrCreateKey(): Promise<CryptoKey> {
  const stored = sessionStorage.getItem(CRYPTO_KEY_NAME)
  if (stored) {
    const raw = Uint8Array.from(atob(stored), (c) => c.charCodeAt(0))
    return crypto.subtle.importKey("raw", raw, "AES-GCM", true, [
      "encrypt",
      "decrypt",
    ])
  }
  const key = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
  )
  const exported = await crypto.subtle.exportKey("raw", key)
  sessionStorage.setItem(
    CRYPTO_KEY_NAME,
    btoa(String.fromCharCode(...new Uint8Array(exported)))
  )
  return key
}

async function encrypt(plaintext: string): Promise<string> {
  const key = await getOrCreateKey()
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encoded = new TextEncoder().encode(plaintext)
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    encoded
  )
  const combined = new Uint8Array(iv.length + new Uint8Array(ciphertext).length)
  combined.set(iv)
  combined.set(new Uint8Array(ciphertext), iv.length)
  return btoa(String.fromCharCode(...combined))
}

async function decrypt(encoded: string): Promise<string> {
  const key = await getOrCreateKey()
  const combined = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0))
  const iv = combined.slice(0, 12)
  const ciphertext = combined.slice(12)
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    ciphertext
  )
  return new TextDecoder().decode(decrypted)
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function generateId(): string {
  return `${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

export async function saveAnalysis(
  id: string,
  company_name: string,
  codes: CompanyCodes,
  result: FullAnalysisResponse
): Promise<void> {
  const history = await getAllAnalyses()
  const entry: AnalysisHistory = {
    id,
    timestamp: new Date().toISOString(),
    company_name,
    codes,
    result,
  }
  history.unshift(entry)
  if (history.length > 50) history.pop()
  const encrypted = await encrypt(JSON.stringify(history))
  localStorage.setItem(STORAGE_KEY, encrypted)
}

export async function getAllAnalyses(): Promise<AnalysisHistory[]> {
  if (typeof window === "undefined") return []
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return []
  try {
    const decrypted = await decrypt(raw)
    return JSON.parse(decrypted) as AnalysisHistory[]
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return []
  }
}

export async function getAnalysis(id: string): Promise<AnalysisHistory | null> {
  const history = await getAllAnalyses()
  return history.find((h) => h.id === id) || null
}

export async function deleteAnalysis(id: string): Promise<void> {
  const history = (await getAllAnalyses()).filter((h) => h.id !== id)
  const encrypted = await encrypt(JSON.stringify(history))
  localStorage.setItem(STORAGE_KEY, encrypted)
}

export function clearAllAnalyses(): void {
  localStorage.removeItem(STORAGE_KEY)
  sessionStorage.removeItem(CRYPTO_KEY_NAME)
}
