"use client";

import { useState, useRef, useEffect } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ConversationMessage, KnowledgeSource } from "@/lib/api";

interface Props {
  messages: ConversationMessage[];
  sources: KnowledgeSource[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  useKnowledge: boolean;
  onToggleKnowledge: (v: boolean) => void;
  onSend: (content: string) => void;
  disabled?: boolean;
}

const markdownComponents: Components = {
  pre: ({ children }) => (
    <pre className="bg-slate-950 border border-slate-700 rounded-lg p-3 overflow-x-auto my-2 text-xs leading-relaxed">
      {children}
    </pre>
  ),
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return <code className="font-mono">{children}</code>;
    }
    return (
      <code className="bg-slate-700/70 rounded px-1 py-0.5 text-xs font-mono">
        {children}
      </code>
    );
  },
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => (
    <ul className="list-disc list-outside ml-4 mb-2 space-y-1">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside ml-4 mb-2 space-y-1">
      {children}
    </ol>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-violet-400 underline hover:text-violet-300"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-slate-600 pl-3 my-2 text-slate-400 italic">
      {children}
    </blockquote>
  ),
};

export default function ChatPanel({
  messages,
  sources,
  isLoading,
  error,
  onRetry,
  useKnowledge,
  onToggleKnowledge,
  onSend,
  disabled = false,
}: Props) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = draft.trim();
    if (!trimmed || isLoading || disabled) return;
    setDraft("");
    onSend(trimmed);
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center text-slate-500">
            <span className="text-5xl mb-4" aria-hidden>
              🧠
            </span>
            <p className="text-lg font-semibold text-slate-300">
              Start a conversation
            </p>
            <p className="text-sm mt-1 max-w-sm">
              Ask anything for general chat, or toggle{" "}
              <span className="text-violet-400 font-medium">
                Knowledge Mode
              </span>{" "}
              to ground answers in your uploaded documents.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-violet-600 text-white rounded-br-sm"
                  : "bg-slate-800 text-slate-100 rounded-bl-sm border border-slate-700"
              }`}
            >
              {m.role === "user" ? (
                <span className="whitespace-pre-wrap break-words">
                  {m.content}
                </span>
              ) : (
                <div className="break-words">
                  <Markdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                  >
                    {m.content}
                  </Markdown>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div
              className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2"
              aria-label="Assistant is thinking"
            >
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div
              role="alert"
              className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-sm text-red-200 flex items-center gap-3"
            >
              <span>⚠ {error}</span>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="underline text-red-100 hover:text-white transition-colors"
                >
                  Retry
                </button>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Sources strip */}
      {sources.length > 0 && (
        <div className="border-t border-slate-700 px-4 py-3 bg-slate-900/60 max-h-44 overflow-y-auto">
          <p className="text-xs text-slate-400 mb-2 font-semibold uppercase tracking-wide">
            Sources used
          </p>
          <div className="flex flex-col gap-2">
            {sources.map((s) => (
              <div
                key={s.source_id}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs"
              >
                <span className="text-violet-400 font-bold mr-2">
                  [{s.source_id}]
                </span>
                <span className="text-slate-300 font-medium">
                  {s.filename}
                </span>
                <span className="text-slate-500 ml-1">
                  chunk {s.chunk_index} · {(s.score * 100).toFixed(0)}% match
                </span>
                <p className="text-slate-400 mt-1 line-clamp-3">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-slate-700 px-4 py-3 bg-slate-900">
        <div className="flex items-center gap-2 mb-2">
          <button
            onClick={() => onToggleKnowledge(!useKnowledge)}
            role="switch"
            aria-checked={useKnowledge}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500 ${
              useKnowledge ? "bg-violet-600" : "bg-slate-600"
            }`}
            aria-label="Toggle knowledge mode"
          >
            <span
              className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
                useKnowledge ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </button>
          <span className="text-xs text-slate-400">
            {useKnowledge ? (
              <span className="text-violet-400 font-medium">
                Knowledge mode on
              </span>
            ) : (
              "Knowledge mode off"
            )}
          </span>
        </div>

        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading || disabled}
            placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
            aria-label="Message"
            className="flex-1 resize-none bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent disabled:opacity-50 max-h-40 overflow-auto"
            style={{ height: "auto" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
            }}
          />
          <button
            onClick={submit}
            disabled={isLoading || disabled || !draft.trim()}
            className="h-10 w-10 flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-violet-400"
            aria-label="Send message"
          >
            <svg
              className="w-4 h-4 text-white rotate-90"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden
            >
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1 text-right">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
