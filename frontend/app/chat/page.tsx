"use client";

import { useState } from "react";
import { EventSourceParserStream } from "eventsource-parser/stream";
import { supabase } from "@/lib/supabase";
import { AnswerWithCitations } from "@/components/answer_with_citations";

type Citation = {
  n: number;
  chunk_id: string;
  document_title: string;
  page_from: number | null;
  heading_path: string | null;
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [verified, setVerified] = useState(true);
  const [phase, setPhase] = useState<"idle" | "searching" | "streaming">("idle");

  async function ask(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setAnswer("");
    setCitations([]);
    setVerified(true);
    setPhase("searching");

    const { data } = await supabase.auth.getSession();
    const res = await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${data.session?.access_token}`,
      },
      body: JSON.stringify({ question }),
    });

    const events = res.body!
      .pipeThrough(new TextDecoderStream())
      .pipeThrough(new EventSourceParserStream())
      .getReader();

    while (true) {
      const { done, value } = await events.read();
      if (done) break;

      if (value.event === "token") {
        setPhase("streaming");
        setAnswer((prev) => prev + value.data);
      } else if (value.event === "citations") {
        const parsed = JSON.parse(value.data);
        setCitations(parsed.citations);
        setVerified(parsed.verified);
      }
    }
    setPhase("idle");
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <form onSubmit={ask} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your materials..."
          className="flex-1 rounded border px-3 py-2"
        />
        <button className="rounded bg-black px-4 py-2 text-white">Ask</button>
      </form>

      {phase === "searching" && (
        <p className="text-sm text-gray-500">Searching your materials...</p>
      )}

      {answer && (
        <AnswerWithCitations
          answer={answer}
          citations={citations}
          verified={verified}
        />
      )}

    </main>
  );
}