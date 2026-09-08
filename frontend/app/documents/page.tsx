"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Doc = {
  id: string;
  title: string;
  doc_type: string;
  status: "pending" | "processing" | "ready" | "failed";
  error_message: string | null;
  page_count: number | null;
};

const TERMINAL = new Set(["ready", "failed"]);

const DOC_TYPE_BY_EXT: Record<string, string> = {
  pdf: "ruleset",
  md: "transcript",
};

function titleFromFileName(name: string): string {
  return name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("ruleset");

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setFileName(file?.name ?? null);
    if (!file) return;
    setTitle(titleFromFileName(file.name));
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (ext in DOC_TYPE_BY_EXT) setDocType(DOC_TYPE_BY_EXT[ext]);
  }

  const load = useCallback(async () => {
    const res = await apiFetch("/api/documents");
    setDocs(await res.json());
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll only while something is still in flight, and always clean up.
  useEffect(() => {
    const pending = docs.some((d) => !TERMINAL.has(d.status));
    if (!pending) return;
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [docs, load]);

  async function handleDownload(id: string) {
    const res = await apiFetch(`/api/documents/download/${id}`);
    const { link } = await res.json();
    window.open(link, "_blank");
  }

  async function handleDelete(id: string) {
    await apiFetch(`/api/documents/${id}`, { method: "DELETE" });
    await load();
  }

  async function handleUpload(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    setBusy(true);
    try {
      const form = new FormData(formEl);
      await apiFetch("/api/documents", { method: "POST", body: form });
      formEl.reset();
      setFileName(null);
      setTitle("");
      setDocType("ruleset");
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-8">
      <h1 className="text-2xl font-semibold">Your materials</h1>

      <form onSubmit={handleUpload} className="space-y-3 rounded border p-4">
        <input name="title" placeholder="Title" required
               value={title} onChange={(e) => setTitle(e.target.value)}
               className="w-full rounded border px-3 py-2" />
        <select name="doc_type" value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="w-full rounded border px-3 py-2">
          <option value="ruleset">Ruleset</option>
          <option value="transcript">Session transcript</option>
        </select>
        <div className="space-y-2">
          <p className={`text-sm ${fileName ? "text-gray-700" : "text-gray-400"}`}>
            {fileName ?? "No file selected"}
          </p>
          <div className="flex items-center gap-3">
            <label className="cursor-pointer rounded border px-4 py-2 hover:bg-gray-50">
              Choose file
              <input
                type="file"
                name="file"
                accept=".pdf,.md"
                required
                className="sr-only"
                onChange={handleFileChange}
              />
            </label>
            <button disabled={busy}
                    className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
              {busy ? "Uploading..." : "Upload"}
            </button>
          </div>
        </div>
      </form>

      <ul className="space-y-2">
        {docs.map((d) => (
          <li key={d.id} className="rounded border p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">{d.title}</span>
              <StatusBadge status={d.status} />
            </div>
            {d.status === "failed" && d.error_message && (
              <p className="mt-2 text-sm text-red-700">{d.error_message}</p>
            )}
            {d.status === "ready" && (
              <p className="mt-1 text-sm text-gray-500">
                {d.page_count} pages -- ready to search
              </p>
            )}
            {(d.status === "ready" || d.status === "failed") && (
              <div className="mt-2 flex gap-2">
                {d.status === "ready" && (
                  <button
                    onClick={() => handleDownload(d.id)}
                    className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
                  >
                    Download
                  </button>
                )}
                <button
                  onClick={() => handleDelete(d.id)}
                  className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}

function StatusBadge({ status }: { status: Doc["status"] }) {
  const styles: Record<Doc["status"], string> = {
    pending: "bg-gray-100 text-gray-700",
    processing: "bg-blue-100 text-blue-700",
    ready: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${styles[status]}`}>
      {status}
    </span>
  );
}