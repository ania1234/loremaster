"use client";

import { useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Citation = {
  n: number;
  chunk_id: string;
  document_title: string;
  page_from: number | null;
  heading_path: string | null;
};

type Panel = {
  citation: Citation;
  content: string | null; // null while still loading
  error: string | null;
};

function subtitle(c: Citation) {
  return [c.page_from ? `p.${c.page_from}` : null, c.heading_path]
    .filter(Boolean)
    .join(" -- ");
}

export function AnswerWithCitations({
  answer,
  citations,
  verified = true,
}: {
  answer: string;
  citations: Citation[];
  verified?: boolean;
}) {
  const [panel, setPanel] = useState<Panel | null>(null);
  const request = useRef(0);

  // Derived, not stored: a new answer drops the panel unless it cites the same
  // chunk, in which case we re-read the label from the fresh citation list.
  const open = panel
    ? citations.find((c) => c.chunk_id === panel.citation.chunk_id)
    : undefined;

  async function show(citation: Citation) {
    const id = ++request.current;
    setPanel({ citation, content: null, error: null });

    try {
      const res = await apiFetch(`/api/chunks/${citation.chunk_id}`);
      const chunk = await res.json();
      // Ignore a response that a later click has already superseded.
      if (id !== request.current) return;
      setPanel({ citation, content: chunk.text, error: null });
    } catch (err) {
      if (id !== request.current) return;
      const message = err instanceof Error ? err.message : String(err);
      setPanel({ citation, content: null, error: message });
    }
  }

  // Split on [n] and keep the delimiters, so we can map them to buttons.
  const parts = answer.split(/(\[\d+\])/g);

  return (
    <div className="flex gap-6">
      <div className="min-w-0 flex-1 space-y-4">
        <p className="whitespace-pre-wrap leading-relaxed">
          {parts.map((part, i) => {
            const match = part.match(/^\[(\d+)\]$/);
            if (!match) return <span key={i}>{part}</span>;

            const n = Number(match[1]);
            const citation = citations.find((c) => c.n === n);
            if (!citation) return <span key={i}>{part}</span>; // no silent break

            const active = open?.n === n;
            return (
              <button
                key={i}
                onClick={() => show(citation)}
                title={`${citation.document_title}${
                  citation.page_from ? `, p.${citation.page_from}` : ""
                }`}
                className={`mx-0.5 rounded px-1 text-xs font-medium
                            hover:bg-blue-200 ${
                              active
                                ? "bg-blue-600 text-white hover:bg-blue-600"
                                : "bg-blue-100 text-blue-800"
                            }`}
              >
                {n}
              </button>
            );
          })}
        </p>

        {!verified && (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-800">
            Unverified: this answer referenced a source that could not be
            matched. Check the citations carefully.
          </p>
        )}

        {citations.length > 0 && (
          <ul className="space-y-1 border-t pt-3 text-sm text-gray-600">
            {citations.map((c) => {
              const active = open?.n === c.n;
              return (
                <li key={c.n}>
                  <button
                    onClick={() => show(c)}
                    className={`text-left hover:underline ${
                      active ? "font-medium text-blue-800" : ""
                    }`}
                  >
                    [{c.n}] {c.document_title}
                    {subtitle(c) ? `, ${subtitle(c)}` : ""}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {panel && open && (
        <aside className="sticky top-8 h-fit w-80 shrink-0 rounded border bg-gray-50 p-4">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div className="text-xs text-gray-500">
              <div className="font-medium text-gray-800">
                [{open.n}] {open.document_title}
              </div>
              {subtitle(open) && <div>{subtitle(open)}</div>}
            </div>
            <button
              onClick={() => setPanel(null)}
              className="shrink-0 text-gray-400 hover:text-gray-600"
            >
              close
            </button>
          </div>

          {panel.error ? (
            <p className="text-sm text-red-700">
              Could not load this source: {panel.error}
            </p>
          ) : panel.content === null ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : (
            <p className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">
              {panel.content}
            </p>
          )}
        </aside>
      )}
    </div>
  );
}
