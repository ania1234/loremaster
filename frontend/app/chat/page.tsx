"use client";

import { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EventSourceParserStream } from "eventsource-parser/stream";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";
import { AnswerWithCitations } from "@/components/answer_with_citations";

type Citation = {
  n: number;
  chunk_id: string;
  document_title: string;
  page_from: number | null;
  heading_path: string | null;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
};

// The exchange still streaming in, shown until it can be read back as history.
type Pending = {
  question: string;
  answer: string;
  citations: Citation[];
  verified: boolean;
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Stored messages don't carry the stream's `verified` flag, but it can be
// recovered: chat.py keeps every citation up to the highest [n] the answer
// uses, so an [n] without a stored citation is one that matched no source (or
// whose document has since been deleted).
function isVerified(m: Message) {
  const stored = new Set(m.citations.map((c) => c.n));
  return [...m.content.matchAll(/\[(\d+)\]/g)].every(([, n]) =>
    stored.has(Number(n)),
  );
}

async function fetchConversation(id: string): Promise<{ title: string | null }> {
  const res = await apiFetch(`/api/conversations/${id}`);
  return res.json();
}

// Oldest first.
async function fetchMessages(conversationId: string): Promise<Message[]> {
  const res = await apiFetch(`/api/conversations/${conversationId}/messages`);
  return res.json();
}

export default function ChatPage() {
  // useSearchParams needs a Suspense boundary, or `next build` fails here.
  return (
    <Suspense>
      <ChatRoute />
    </Suspense>
  );
}

// Ties the chat to ?c=<conversation id>, so a reload or a link reopens it.
function ChatRoute() {
  const urlId = useSearchParams().get("c");
  const [view, setView] = useState({
    key: 0,
    opened: urlId, // the conversation the chat was mounted with
    url: urlId, // the id last seen in the URL
    adopted: null as string | null, // an id the chat put in the URL itself
  });

  // Compared against `url`, not `adopted`: Next applies replaceState in a
  // transition, so a render can see `adopted` before the URL catches up.
  if (urlId !== view.url) {
    setView(
      urlId !== null && urlId === view.adopted
        ? // A new conversation got its id mid-answer: keep the chat mounted.
          { ...view, url: urlId }
        : // Navigated to another conversation (side nav, back/forward).
          { key: view.key + 1, opened: urlId, url: urlId, adopted: null },
    );
  }

  function adopt(id: string) {
    setView((v) => ({ ...v, adopted: id }));
    window.history.replaceState(null, "", `?c=${id}`);
  }

  return <Chat key={view.key} initialId={view.opened} onCreated={adopt} />;
}

function Chat({
  initialId,
  onCreated,
}: {
  initialId: string | null;
  onCreated: (id: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<"loading" | "ready" | "failed">(
    initialId ? "loading" : "ready",
  );
  const [pending, setPending] = useState<Pending | null>(null);
  const [phase, setPhase] = useState<"idle" | "searching" | "streaming">("idle");
  const [conversationId, setConversationId] = useState(initialId);
  const [title, setTitle] = useState<string | null>(null);
  // An answer keeps streaming after the user navigates away; by then the URL
  // belongs to another page, and its conversation id must stay out of it.
  const mounted = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  // Follow the newest message only while the user is at the bottom, so
  // scrolling up to reread something isn't undone by the next token.
  const following = useRef(true);

  function onScroll() {
    const el = scroller.current!;
    following.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }

  // Before paint, so a streamed token never shows up a frame before the
  // scroll that reveals it.
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && following.current) el.scrollTop = el.scrollHeight;
  }, [messages, pending, phase, history]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Reopened from the URL. Another conversation gets a fresh mount instead.
  useEffect(() => {
    if (!initialId) return;
    Promise.all([fetchConversation(initialId), fetchMessages(initialId)])
      .then(([conversation, stored]) => {
        setTitle(conversation.title);
        setMessages(stored);
        setHistory("ready");
      })
      .catch(() => setHistory("failed"));
  }, [initialId]);

  // Only the newest answer shows its sources; a pending one outranks history.
  const latestAssistantId = pending
    ? null
    : messages.findLast((m) => m.role === "assistant")?.id;

  async function ask(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const asked = question;
    setQuestion("");
    following.current = true; // a new question always brings the answer into view
    setPending({ question: asked, answer: "", citations: [], verified: true });
    setPhase("searching");

    try {
      const { data } = await supabase.auth.getSession();
      const res = await fetch(`${BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${data.session?.access_token}`,
        },
        body: JSON.stringify({ question: asked, conversation_id: conversationId }),
      });

      const events = res.body!
        .pipeThrough(new TextDecoderStream())
        .pipeThrough(new EventSourceParserStream())
        .getReader();

      let id = conversationId;
      while (true) {
        const { done, value } = await events.read();
        if (done) break;

        if (value.event === "conversation") {
          if (id === null) {
            // Not awaited, so the answer keeps streaming while the title loads.
            fetchConversation(value.data).then((c) => setTitle(c.title));
            if (mounted.current) onCreated(value.data);
          }
          id = value.data;
          setConversationId(id);
        } else if (value.event === "token") {
          setPhase("streaming");
          setPending((p) => p && { ...p, answer: p.answer + value.data });
        } else if (value.event === "citations") {
          const parsed = JSON.parse(value.data);
          setPending((p) => p && {
            ...p,
            citations: parsed.citations,
            verified: parsed.verified,
          });
        }
      }

      // Both sides of the exchange are stored by now, so the history takes
      // over from the live copy. If this fetch fails, the live copy stays.
      if (id) setMessages(await fetchMessages(id));
      setPending(null);
    } finally {
      setPhase("idle");
    }
  }

  return (
    <main className="flex h-full flex-col">
      <h1 className="mx-auto min-h-8 w-full max-w-5xl px-8 pt-8 pb-4 text-2xl font-semibold">
        {title ?? (initialId ? "" : "New conversation")}
      </h1>

      {/* Full width, so the wheel scrolls the chat anywhere over it. */}
      <div
        ref={scroller}
        onScroll={onScroll}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        <div className="mx-auto max-w-5xl space-y-6 px-8 py-2">

          {history === "loading" && (
            <p className="text-sm text-gray-500">Loading conversation...</p>
          )}
          {history === "failed" && (
            <p className="text-sm text-red-700">Could not load this conversation.</p>
          )}

          {messages.map((m) =>
            m.role === "user" ? (
              <UserMessage key={m.id} content={m.content} />
            ) : (
              <AssistantMessage key={m.id}>
                <AnswerWithCitations
                  answer={m.content}
                  citations={m.citations}
                  verified={isVerified(m)}
                  collapsed={m.id !== latestAssistantId}
                />
              </AssistantMessage>
            ),
          )}

          {pending && (
            <>
              <UserMessage content={pending.question} />
              <AssistantMessage>
                {phase === "searching" ? (
                  <p className="text-sm text-gray-500">Searching your materials...</p>
                ) : (
                  <AnswerWithCitations
                    answer={pending.answer}
                    citations={pending.citations}
                    verified={pending.verified}
                  />
                )}
              </AssistantMessage>
            </>
          )}
        </div>
      </div>

      <form onSubmit={ask} className="mx-auto flex w-full max-w-5xl gap-2 px-8 py-4">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your materials..."
          maxLength={2000}
          required
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          disabled={phase !== "idle" || history !== "ready"}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </main>
  );
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[75%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-gray-100 px-4 py-2">
        {content}
      </p>
    </div>
  );
}

function AssistantMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-gray-500">Loremaster</p>
      {children}
    </div>
  );
}
