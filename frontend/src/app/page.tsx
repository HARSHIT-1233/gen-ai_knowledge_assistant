"use client";

import { useCallback, useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import KnowledgeLibrary from "@/components/KnowledgeLibrary";
import Sidebar from "@/components/Sidebar";
import {
  ApiError,
  checkHealth,
  createConversation,
  deleteConversation,
  deleteDocument,
  getConversation,
  indexDocument,
  listConversations,
  listDocuments,
  sendMessage,
  uploadDocument,
  type ConversationMessage,
  type ConversationSummary,
  type DocumentSummary,
  type KnowledgeSource,
} from "@/lib/api";

function message(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return fallback;
}

export default function Page() {
  // Conversations
  const [conversations, setConversations] = useState<ConversationSummary[]>(
    []
  );
  const [convLoading, setConvLoading] = useState(true);
  const [convError, setConvError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // Chat
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [msgError, setMsgError] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [useKnowledge, setUseKnowledge] = useState(false);

  // Documents
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Backend health
  const [online, setOnline] = useState<boolean | null>(null);

  // Layout (mobile drawers)
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations());
      setConvError(null);
    } catch (e) {
      setConvError(message(e, "Could not load conversations."));
    } finally {
      setConvLoading(false);
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments());
      setDocsError(null);
    } catch (e) {
      setDocsError(message(e, "Could not load documents."));
    } finally {
      setDocsLoading(false);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      await checkHealth();
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    // Defer the initial loads inside an async task so state updates
    // happen asynchronously rather than during the effect body.
    void (async () => {
      await Promise.all([
        refreshConversations(),
        refreshDocuments(),
        refreshHealth(),
      ]);
    })();
  }, [refreshConversations, refreshDocuments, refreshHealth]);

  useEffect(() => {
    const timer = setInterval(refreshHealth, 20_000);
    return () => clearInterval(timer);
  }, [refreshHealth]);

  const handleNewConversation = useCallback(async () => {
    setCreating(true);
    setConvError(null);
    try {
      const created = await createConversation("New conversation");
      setConversations((prev) => [
        created,
        ...prev.filter((c) => c.id !== created.id),
      ]);
      setActiveId(created.id);
      setMessages([]);
      setSources([]);
      setMsgError(null);
      setPendingMessage(null);
      setSidebarOpen(false);
    } catch (e) {
      setConvError(message(e, "Could not create a conversation."));
    } finally {
      setCreating(false);
    }
  }, []);

  const handleSelectConversation = useCallback(async (id: string) => {
    setActiveId(id);
    setMessages([]);
    setSources([]);
    setMsgError(null);
    setPendingMessage(null);
    setMsgLoading(true);
    setSidebarOpen(false);
    try {
      const detail = await getConversation(id);
      setMessages(detail.messages);
    } catch (e) {
      setMsgError(message(e, "Could not load this conversation."));
    } finally {
      setMsgLoading(false);
    }
  }, []);

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      setConvError(null);
      try {
        await deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeId === id) {
          setActiveId(null);
          setMessages([]);
          setSources([]);
          setMsgError(null);
          setPendingMessage(null);
        }
      } catch (e) {
        setConvError(message(e, "Could not delete the conversation."));
      }
    },
    [activeId]
  );

  const handleSend = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || msgLoading) return;
      setMsgError(null);
      setPendingMessage(null);

      let conversationId = activeId;
      try {
        if (!conversationId) {
          const created = await createConversation(trimmed.slice(0, 60));
          conversationId = created.id;
          setActiveId(conversationId);
          setConversations((prev) => [
            created,
            ...prev.filter((c) => c.id !== created.id),
          ]);
        }
      } catch (e) {
        setMsgError(message(e, "Could not start a conversation."));
        return;
      }

      const optimistic: ConversationMessage = {
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);
      setMsgLoading(true);

      try {
        const reply = await sendMessage(
          conversationId,
          trimmed,
          useKnowledge
        );
        setMessages(reply.messages);
        setSources(reply.sources);
        refreshConversations();
      } catch (e) {
        setMessages((prev) => prev.filter((m) => m !== optimistic));
        setMsgError(
          message(
            e,
            "The assistant could not respond. Check that Ollama is running."
          )
        );
        setPendingMessage(trimmed);
      } finally {
        setMsgLoading(false);
      }
    },
    [activeId, msgLoading, useKnowledge, refreshConversations]
  );

  const handleRetry = useCallback(() => {
    if (pendingMessage) handleSend(pendingMessage);
  }, [pendingMessage, handleSend]);

  const handleUpload = useCallback(
    async (file: File, onProgress: (pct: number) => void) => {
      await uploadDocument(file, onProgress);
      await refreshDocuments();
    },
    [refreshDocuments]
  );

  const handleIndex = useCallback(
    async (id: string) => {
      await indexDocument(id);
      await refreshDocuments();
    },
    [refreshDocuments]
  );

  const handleDeleteDocument = useCallback(
    async (id: string) => {
      await deleteDocument(id);
      await refreshDocuments();
    },
    [refreshDocuments]
  );

  return (
    <div className="flex h-dvh flex-col bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-3">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open conversations"
            className="lg:hidden h-9 w-9 flex items-center justify-center rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
          >
            ☰
          </button>
          <h1 className="text-sm sm:text-base font-semibold truncate">
            GenAI Knowledge Assistant
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2" title="Backend status">
            <span
              className={`h-2 w-2 rounded-full ${
                online === true
                  ? "bg-emerald-500"
                  : online === false
                    ? "bg-red-500"
                    : "bg-slate-500"
              }`}
            />
            <span className="text-xs text-slate-400">
              {online === true
                ? "Backend online"
                : online === false
                  ? "Backend offline"
                  : "Checking…"}
            </span>
          </div>
          <button
            onClick={() => setLibraryOpen((v) => !v)}
            className="xl:hidden rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800"
          >
            Library
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="relative flex flex-1 min-h-0">
        {/* Sidebar drawer */}
        {sidebarOpen && (
          <div
            onClick={() => setSidebarOpen(false)}
            className="absolute inset-0 z-30 bg-black/50 lg:hidden"
            aria-hidden
          />
        )}
        <aside
          className={`absolute inset-y-0 left-0 z-40 w-72 max-w-[80vw] transform border-r border-slate-800 bg-slate-900 transition-transform duration-200 lg:static lg:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Sidebar
            conversations={conversations}
            activeId={activeId}
            loading={convLoading}
            error={convError}
            creating={creating}
            onNew={handleNewConversation}
            onSelect={handleSelectConversation}
            onDelete={handleDeleteConversation}
            onRefresh={refreshConversations}
          />
        </aside>

        {/* Main chat */}
        <main className="flex flex-1 min-w-0 flex-col min-h-0">
          <ChatPanel
            messages={messages}
            sources={sources}
            isLoading={msgLoading}
            error={msgError}
            onRetry={handleRetry}
            useKnowledge={useKnowledge}
            onToggleKnowledge={setUseKnowledge}
            onSend={handleSend}
          />
        </main>

        {/* Library drawer */}
        {libraryOpen && (
          <div
            onClick={() => setLibraryOpen(false)}
            className="absolute inset-0 z-30 bg-black/50 xl:hidden"
            aria-hidden
          />
        )}
        <aside
          className={`absolute inset-y-0 right-0 z-40 w-80 max-w-[85vw] transform border-l border-slate-800 bg-slate-900 transition-transform duration-200 xl:static xl:translate-x-0 ${
            libraryOpen ? "translate-x-0" : "translate-x-full"
          }`}
        >
          <KnowledgeLibrary
            documents={documents}
            loading={docsLoading}
            error={docsError}
            onRefresh={refreshDocuments}
            onUpload={handleUpload}
            onIndex={handleIndex}
            onDelete={handleDeleteDocument}
          />
        </aside>
      </div>
    </div>
  );
}
