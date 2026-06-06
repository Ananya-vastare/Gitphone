import axios, { AxiosError } from 'axios';
import { getBackendUrl, getConfig } from './config';

export interface RegisterPayload {
  telegram_id: string;
  github_token: string;
  default_repo: string;
  branch: string;
}

export interface SyncFilePayload {
  telegram_id: string;
  filepath: string;
  diff: string | null;
  full_content: string | null;
  base_sha: string;
  is_binary: boolean;
  file_size: number;
  active_repo?: string;    // Auto-detected from .git/config
  active_branch?: string;  // Auto-detected from .git/HEAD
  change_type?: 'create' | 'modify' | 'delete';  // Type of change
}

export interface RegisterResponse {
  ok: boolean;
  message: string;
  telegram_id?: string;
  api_key?: string;      // Returned once at registration
  error?: string;
}

export interface SyncFileResponse {
  ok: boolean;
  staged_id?: string;
  message: string;
  error?: string;
}

export interface VersionResponse {
  schema_version: number;
  migration_sql: string | null;
  docs_url: string;
}

function baseUrl(): string {
  return getBackendUrl().replace(/\/$/, '');
}

/** Headers required for authenticated endpoints */
function authHeaders(): Record<string, string> {
  const cfg = getConfig();
  if (!cfg?.apiKey) return {};
  return {
    'X-Telegram-Id': cfg.telegramId,
    'X-Api-Key': cfg.apiKey,
  };
}

// ── Public endpoints (no auth) ───────────────────────────────────────────────

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  const response = await axios.post<RegisterResponse>(`${baseUrl()}/register`, payload, {
    timeout: 15000,
    // No auth headers — this is the endpoint that creates the key
  });
  return response.data;
}

export async function getVersion(): Promise<VersionResponse> {
  const response = await axios.get<VersionResponse>(`${baseUrl()}/version`, {
    timeout: 5000,
  });
  return response.data;
}

export async function healthCheck(): Promise<boolean> {
  try {
    await axios.get(`${baseUrl()}/health`, { timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

// ── Authenticated endpoints (require X-Telegram-Id + X-Api-Key) ─────────────

export async function syncFile(payload: SyncFilePayload): Promise<SyncFileResponse> {
  const response = await axios.post<SyncFileResponse>(`${baseUrl()}/sync-file`, payload, {
    timeout: 10000,
    headers: authHeaders(),
  });
  return response.data;
}


/**
 * Extract a human-readable error message from an axios error.
 */
export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail?.message) return detail.message;
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return 'Unknown error';
}
