"use client";

import { createContext, use, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Parent, PhrasingContent, Root, RootContent } from "mdast";
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

// Turns each [n] in the answer's text into a link to #cite-n, which
// CitationLink renders as a button. Code spans aren't text nodes, so an [n]
// inside one stays as written.
function remarkCitations() {
  return (tree: Root) => splitCitations(tree);
}

function splitCitations(node: Parent) {
  node.children = node.children.flatMap<RootContent>((child) => {
    if (child.type === "text") return citationNodes(child.value);
    // A citation can't become a link inside a link.
    if ("children" in child && child.type !== "link" && child.type !== "linkReference") {
      splitCitations(child);
    }
    return [child];
  });
}

function citationNodes(value: string) {
  return value
    .split(/(\[\d+\])/g)
    .filter(Boolean)
    .map((part): PhrasingContent => {
      const match = part.match(/^\[(\d+)\]$/);
      return match
        ? { type: "link", url: `#cite-${match[1]}`, children: [{ type: "text", value: part }] }
        : { type: "text", value: part };
    });
}

// Module-level, so the markdown keeps its elements across renders instead of
// remounting them, which would drop focus from a clicked citation.
const CitationContext = createContext<{
  citations: Citation[];
  open: Citation | undefined;
  show: (c: Citation) => void;
} | null>(null);

function CitationLink({ href, children }: React.ComponentProps<"a">) {
  const { citations, open, show } = use(CitationContext)!;
  const n = href?.match(/^#cite-(\d+)$/)?.[1];
  if (!n) {
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }

  const citation = citations.find((c) => c.n === Number(n));
  if (!citation) return <>{children}</>; // no silent break

  const active = open?.n === citation.n;
  return (
    <button
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
      {citation.n}
    </button>
  );
}

const remarkPlugins = [remarkGfm, remarkCitations];
const markdownComponents = { a: CitationLink };

export function AnswerWithCitations({
  answer,
  citations,
  verified = true,
  collapsed = false,
}: {
  answer: string;
  citations: Citation[];
  verified?: boolean;
  collapsed?: boolean; // the source list's default; the user can still toggle it
}) {
  const [panel, setPanel] = useState<Panel | null>(null);
  const request = useRef(0);
  const [expanded, setExpanded] = useState(!collapsed);
  const [wasCollapsed, setWasCollapsed] = useState(collapsed);

  // A newer answer arriving folds this one's sources away, even if the user
  // had opened them.
  if (collapsed !== wasCollapsed) {
    setWasCollapsed(collapsed);
    setExpanded(!collapsed);
  }

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

  return (
    <div className="flex gap-6">
      <div className="min-w-0 flex-1 space-y-4">
        <div className="prose max-w-none leading-relaxed">
          <CitationContext value={{ citations, open, show }}>
            <Markdown remarkPlugins={remarkPlugins} components={markdownComponents}>
              {answer}
            </Markdown>
          </CitationContext>
        </div>

        {!verified && (
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-800">
            Unverified: this answer referenced a source that could not be
            matched. Check the citations carefully.
          </p>
        )}

        {citations.length > 0 && (
          <div className="border-t pt-3 text-sm text-gray-600">
            <button
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-800"
            >
              <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>
                ▸
              </span>
              Sources ({citations.length})
            </button>

            {expanded && (
              <ul className="mt-2 space-y-1">
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
        )}
      </div>

      {panel && open && (
        <aside className="engraver-panel sticky top-8 h-fit w-80 shrink-0 border p-4">
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
            <p className="engraver-title text-sm text-gray-500">Loading...</p>
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
