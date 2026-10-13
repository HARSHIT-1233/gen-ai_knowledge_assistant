"use client";

import { useRef, useState } from "react";
import type { DocumentSummary } from "@/lib/api";

interface Props {
  documents: DocumentSummary[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onUpload: (
    file: File,
    onProgress: (pct: number) => void
  ) => Promise<void>;
  onIndex: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

const MAX_BYTES = 10 * 1024 * 1024;

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function statusFor(doc: DocumentSummary): {
  label: string;
  className: string;
} {
  if (doc.chunk_count === 0) {
    return { label: "No text", className: "text-slate-400" };
  }
  if (doc.indexed_chunk_count === 0) {
    return { label: "Not indexed", className: "text-amber-400" };
  }
  if (doc.indexed_chunk_count >= doc.chunk_count) {
    return { label: "Indexed", className: "text-emerald-400" };
  }
  return {
    label: `Partial (${doc.indexed_chunk_count}/${doc.chunk_count})`,
    className: "text-amber-400",
  };
}

export default function KnowledgeLibrary({
  documents,
  loading,
  error,
  onRefresh,
  onUpload,
  onIndex,
  onDelete,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [opError, setOpError] = useState<string | null>(null);

  const uploading = progress !== null;

  function pickFile(file: File | null) {
    setOpError(null);
    if (!file) {
      setSelected(null);
      return;
    }
    const ok = /\.(pdf|txt)$/i.test(file.name);
    if (!ok) {
      setOpError("Only PDF and TXT files are supported.");
      setSelected(null);
      return;
    }
    if (file.size > MAX_BYTES) {
      setOpError("File exceeds the 10 MiB size limit.");
      setSelected(null);
      return;
    }
    setSelected(file);
  }

  async function handleUpload() {
    if (!selected || uploading) return;
    setOpError(null);
    setProgress(0);
    try {
      await onUpload(selected, setProgress);
      setSelected(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setOpError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setProgress(null);
    }
  }

  async function handleIndex(id: string) {
    if (busyId) return;
    setOpError(null);
    setBusyId(id);
    try {
      await onIndex(id);
    } catch (e) {
      setOpError(e instanceof Error ? e.message : "Indexing failed.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(id: string) {
    if (pendingDelete !== id) {
      setPendingDelete(id);
      return;
    }
    setOpError(null);
    setPendingDelete(null);
    setBusyId(id);
    try {
      await onDelete(id);
    } catch (e) {
      setOpError(e instanceof Error ? e.message : "Delete failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="p-3 border-b border-slate-700 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">
          Knowledge Library
        </h2>
        <button
          onClick={onRefresh}
          aria-label="Refresh documents"
          title="Refresh"
          className="h-8 w-8 flex items-center justify-center rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400"
        >
          ↻
        </button>
      </div>

      {/* Upload */}
      <div className="p-3 border-b border-slate-700 space-y-2">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          disabled={uploading}
          aria-label="Choose a PDF or TXT file"
          className="block w-full text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-700 file:px-3 file:py-1.5 file:text-slate-100 file:text-xs hover:file:bg-slate-600"
        />
        <button
          onClick={handleUpload}
          disabled={!selected || uploading}
          className="w-full rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed px-3 py-2 text-sm font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400"
        >
          {uploading ? `Uploading… ${progress}%` : "Upload document"}
        </button>
        {uploading && (
          <div className="h-1.5 w-full rounded-full bg-slate-700 overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
        {loading && (
          <div className="space-y-2">
            {[0, 1].map((i) => (
              <div
                key={i}
                className="h-16 rounded-lg bg-slate-800 animate-pulse"
              />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="p-3 text-xs text-red-300 bg-red-900/30 border border-red-800 rounded-lg">
            {error}
          </div>
        )}

        {!loading && !error && documents.length === 0 && (
          <p className="text-sm text-slate-500 text-center py-6">
            No documents yet. Upload a PDF or TXT file to get started.
          </p>
        )}

        {!loading &&
          documents.map((doc) => {
            const status = statusFor(doc);
            const busy = busyId === doc.document_id;
            return (
              <div
                key={doc.document_id}
                className="bg-slate-800/70 border border-slate-700 rounded-lg p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <p
                    className="text-sm font-medium text-slate-100 truncate"
                    title={doc.filename}
                  >
                    {doc.filename}
                  </p>
                  <span className={`text-[11px] shrink-0 ${status.className}`}>
                    {status.label}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  {formatCount(doc.character_count)} chars ·{" "}
                  {doc.chunk_count} chunks
                  {doc.page_count ? ` · ${doc.page_count} pages` : ""}
                </div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleIndex(doc.document_id)}
                    disabled={busy}
                    className="flex-1 rounded-md border border-slate-600 text-slate-200 hover:bg-slate-700 disabled:opacity-40 px-2 py-1 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400"
                  >
                    {busy
                      ? "Working…"
                      : doc.indexed_chunk_count > 0
                        ? "Re-index"
                        : "Index"}
                  </button>
                  <button
                    onClick={() => handleDelete(doc.document_id)}
                    disabled={busy}
                    className={`rounded-md border px-2 py-1 text-xs transition-colors disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-red-400 ${
                      pendingDelete === doc.document_id
                        ? "border-red-500 bg-red-600 text-white"
                        : "border-slate-600 text-slate-300 hover:bg-red-900/40 hover:text-red-200"
                    }`}
                  >
                    {pendingDelete === doc.document_id
                      ? "Confirm"
                      : "Delete"}
                  </button>
                </div>
              </div>
            );
          })}
      </div>

      {opError && (
        <div className="p-3 border-t border-slate-700">
          <div className="text-xs text-red-300 bg-red-900/30 border border-red-800 rounded-lg px-3 py-2">
            {opError}
          </div>
        </div>
      )}
    </div>
  );
}
