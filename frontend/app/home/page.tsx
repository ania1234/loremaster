"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { OnboardingWelcome, type Sample } from "@/components/onboarding_welcome";

type Onboarding = { onboarded: boolean; samples: Sample[] };

const LOADING_QUIPS = [
  "Loremaster is getting dressed",
  "Loremaster is getting undressed",
  "Comparing your stats",
  "Surveying your teammates",
  "Fixing your love life",
  "Slaying monsters for you",
  "Finding NPCs",
  "Doing taxes",
  "Rolling for initiative",
  "Bribing the dungeon master",
  "Feeding the dragon",
];

function randomQuipIndex(exclude: number | null) {
  let next;
  do {
    next = Math.floor(Math.random() * LOADING_QUIPS.length);
  } while (next === exclude);
  return next;
}

function LoadingQuips() {
  // Picked after mount: a random first line would differ between the server
  // render and hydration.
  const [index, setIndex] = useState<number | null>(null);

  useEffect(() => {
    const pick = () => setIndex((i) => randomQuipIndex(i));
    const first = setTimeout(pick, 0);
    const timer = setInterval(pick, 2000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, []);

  if (index === null) return null;

  return (
    <p
      key={index}
      className="animate-in fade-in text-center text-sm text-gray-500 duration-500"
    >
      {LOADING_QUIPS[index]}...
    </p>
  );
}

export default function HomePage() {
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stale = false;
    apiFetch("/api/onboarding")
      .then((res) => res.json())
      .then((data: Onboarding) => {
        if (!stale) setOnboarding(data);
      })
      .catch(() => {}) // the greeting is optional; the links work without it
      .finally(() => {
        if (!stale) setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, []);

  if (loading) {
    return (
      <main className="mx-auto mt-24 max-w-md p-8">
        <LoadingQuips />
      </main>
    );
  }

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
