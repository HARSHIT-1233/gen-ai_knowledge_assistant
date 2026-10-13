"use client";

import { useState } from "react";
import type { ConversationSummary } from "@/lib/api";

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRefresh: () => void;
  creating?: boolean;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function Sidebar({
  conversations,
  activeId,
  loading,
  error,
  onSelect,
  onNew,
  onDelete,
  onRefresh,
  creating = false,
}: Props) {
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  function confirmDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (pendingDelete === id) {
      setPendingDelete(null);
      onDelete(id);
    } else {
      setPendingDelete(id);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="p-3 border-b border-slate-700 flex items-center gap-2">
        <button
          onClick={onNew}
          disabled={creating}
          className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-3 py-2 text-sm font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400"
        >
          <span aria-hidden>＋</span>
          {creating ? "Creating…" : "New chat"}
        </button>
        <button
          onClick={onRefresh}
          aria-label="Refresh conversations"
          title="Refresh"
          className="h-9 w-9 flex items-center justify-center rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400"
        >
          ↻
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1">
        {loading && (
          <div className="space-y-2 p-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-12 rounded-lg bg-slate-800 animate-pulse"
              />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="p-3 text-xs text-red-300 bg-red-900/30 border border-red-800 rounded-lg">
            {error}
          </div>
        )}

        {!loading && !error && conversations.length === 0 && (
          <p className="p-3 text-sm text-slate-500 text-center">
            No conversations yet. Start a new chat.
          </p>
        )}

        {!loading &&
          conversations.map((c) => {
            const active = c.id === activeId;
            return (
              <div
                key={c.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelect(c.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(c.id);
                  }
                }}
                aria-current={active}
                className={`group w-full text-left rounded-lg px-3 py-2 cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-violet-400 ${
                  active
                    ? "bg-slate-700 border border-slate-600"
                    : "hover:bg-slate-800 border border-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-slate-100 truncate">
                    {c.title}
                  </span>
                  <button
                    onClick={(e) => confirmDelete(e, c.id)}
                    aria-label={
                      pendingDelete === c.id
                        ? "Confirm delete conversation"
                        : "Delete conversation"
                    }
                    title={
                      pendingDelete === c.id
                        ? "Click again to confirm"
                        : "Delete"
                    }
                    className={`text-xs shrink-0 rounded px-1 transition-colors ${
                      pendingDelete === c.id
                        ? "text-red-300 font-semibold"
                        : "text-slate-500 opacity-0 group-hover:opacity-100 hover:text-red-400"
                    }`}
                  >
                    {pendingDelete === c.id ? "confirm?" : "✕"}
                  </button>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {c.message_count} msg · {relativeTime(c.updated_at)}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
