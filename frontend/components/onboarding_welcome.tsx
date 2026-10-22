"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export type Sample = { title: string; doc_type: "ruleset" | "transcript" };

const DOC_TYPE_LABEL: Record<Sample["doc_type"], string> = {
  ruleset: "Ruleset",
  transcript: "Session transcript",
};

export function OnboardingWelcome({
  samples,
  onDone,
}: {
  samples: Sample[];
  onDone: () => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<"copy" | "skip" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAddExamples() {
    setBusy("copy");
    setError(null);
    try {
      await apiFetch("/api/onboarding/samples", { method: "POST" });
    } catch (err) {
      // 409: another tab already copied them, which is what we wanted anyway.
      if (!(err instanceof Error && err.message.startsWith("409"))) {
        setError("Couldn't add the examples. Please try again.");
        setBusy(null);
        return;
      }
    }
    router.push("/documents");
  }

  async function handleSkip() {
    setBusy("skip");
    setError(null);
    try {
      await apiFetch("/api/onboarding/skip", { method: "POST" });
      onDone();
    } catch {
      setError("Something went wrong. Please try again.");
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="engraver-title">Welcome to Loremaster</CardTitle>
        <CardDescription>
          {samples.length > 0
            ? "Your workspace is empty. Add a few example documents to try " +
              "out chat right away. You can delete them at any time."
            : "Upload your rulesets and session transcripts, then ask " +
              "questions about them in chat."}
        </CardDescription>
      </CardHeader>
      {samples.length > 0 && (
        <CardContent>
          <ul className="space-y-1">
            {samples.map((s) => (
              <li key={s.title} className="flex justify-between gap-3">
                <span className="truncate">{s.title}</span>
                <span className="shrink-0 text-muted-foreground">
                  {DOC_TYPE_LABEL[s.doc_type]}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
      {error && (
        <CardContent>
          <p className="text-red-600">{error}</p>
        </CardContent>
      )}
      <CardFooter className="gap-2">
        {samples.length > 0 ? (
          <>
            <Button onClick={handleAddExamples} disabled={busy !== null}>
              {busy === "copy" ? <span className="engraver-title">Adding examples...</span> : "Add examples"}
            </Button>
            <Button
              variant="outline"
              onClick={handleSkip}
              disabled={busy !== null}
            >
              Start empty
            </Button>
          </>
        ) : (
          <Button onClick={handleSkip} disabled={busy !== null}>
            Get started
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
