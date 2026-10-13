// Central API client — all fetch calls go through here.
// The base URL is read from NEXT_PUBLIC_API_BASE_URL (falling back to
// NEXT_PUBLIC_API_URL) so it can be pointed at any backend deployment.

const RAW_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const BASE = RAW_BASE.replace(/\/+$/, "");
const API = `${BASE}/api/v1`;

// ── Types ──────────────────────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}

export interface KnowledgeSource {
  source_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  score: number;
  text: string;
}

export interface ConversationReply {
  conversation_id: string;
  answer: string;
  model: string;
  messages: ConversationMessage[];
  sources: KnowledgeSource[];
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  content_type: string;
  created_at: string;
  page_count: number | null;
  character_count: number;
  chunk_count: number;
  indexed_chunk_count: number;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  page_count: number | null;
  character_count: number;
  chunk_count: number;
  preview: string;
}

export interface IndexDocumentResponse {
  document_id: string;
  filename: string;
  indexed_chunks: number;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

// ── Helpers ────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  } catch {
    // response was not JSON
  }
  return `Request failed (HTTP ${res.status}).`;
}

async function request<T>(
  url: string,
  init?: RequestInit,
  timeoutMs = 60_000
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("The request timed out. Is the backend running?");
    }
    throw new ApiError(
      "Cannot reach the backend. Make sure it is running on " + BASE + "."
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    throw new ApiError(await parseError(res), res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ── Health ─────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>(`${BASE}/health`, undefined, 10_000);
}

// ── Conversations ──────────────────────────────────────────────────

export async function listConversations(): Promise<ConversationSummary[]> {
  const data = await request<ConversationListResponse>(
    `${API}/conversations`
  );
  return data.conversations;
}

export async function createConversation(
  title = "New conversation"
): Promise<ConversationSummary> {
  return request<ConversationSummary>(`${API}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function getConversation(
  id: string
): Promise<ConversationDetail> {
  return request<ConversationDetail>(`${API}/conversations/${id}`);
}

export async function sendMessage(
  conversationId: string,
  content: string,
  useKnowledge: boolean
): Promise<ConversationReply> {
  return request<ConversationReply>(
    `${API}/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, use_knowledge: useKnowledge }),
    },
    180_000 // local LLM responses can be slow on low-end hardware
  );
}

export async function deleteConversation(id: string): Promise<void> {
  return request<void>(`${API}/conversations/${id}`, { method: "DELETE" });
}

// ── Documents ──────────────────────────────────────────────────────

export async function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>(`${API}/documents`);
}

export async function uploadDocument(
  file: File,
  onProgress?: (pct: number) => void
): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/documents/upload`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status === 201) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new ApiError("The server returned an invalid response."));
        }
        return;
      }
      let detail = `Upload failed (HTTP ${xhr.status}).`;
      try {
        const body = JSON.parse(xhr.responseText);
        const d = body?.detail;
        if (typeof d === "string") detail = d;
        else if (Array.isArray(d) && d[0]?.msg) detail = d[0].msg;
      } catch {
        // not JSON
      }
      reject(new ApiError(detail, xhr.status));
    };

    xhr.onerror = () =>
      reject(new ApiError("Network error during upload."));
    xhr.ontimeout = () => reject(new ApiError("Upload timed out."));
    xhr.timeout = 120_000;

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

export async function indexDocument(
  documentId: string
): Promise<IndexDocumentResponse> {
  return request<IndexDocumentResponse>(
    `${API}/knowledge/index/${documentId}`,
    { method: "POST" },
    600_000 // embedding all chunks can take a while
  );
}

export async function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`${API}/documents/${documentId}`, {
    method: "DELETE",
  });
}
