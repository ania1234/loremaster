"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { OnboardingWelcome, type Sample } from "@/components/onboarding_welcome";

type Onboarding = { onboarded: boolean; samples: Sample[] };

export default function HomePage() {
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);

  useEffect(() => {
    let stale = false;
    apiFetch("/api/onboarding")
      .then((res) => res.json())
      .then((data: Onboarding) => {
        if (!stale) setOnboarding(data);
      })
      .catch(() => {}); // the greeting is optional; the links work without it
    return () => {
      stale = true;
    };
  }, []);

  return (
    <main className="mx-auto mt-24 max-w-md space-y-6 p-8">
      {onboarding && !onboarding.onboarded && (
        <OnboardingWelcome
          samples={onboarding.samples}
          onDone={() => setOnboarding({ ...onboarding, onboarded: true })}
        />
      )}
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Loremaster</h1>
        <p className="text-sm text-gray-500">Where would you like to go?</p>
        <div className="space-y-3">
          <Link
            href="/documents"
            className="block w-full rounded bg-black px-3 py-2 text-center text-white"
          >
            Go to documents
          </Link>
          <Link
            href="/chat"
            className="block w-full rounded border px-3 py-2 text-center"
          >
            Go to chat
          </Link>
        </div>
      </div>
    </main>
  );
}
