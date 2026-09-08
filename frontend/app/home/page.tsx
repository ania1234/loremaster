import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto mt-24 max-w-sm space-y-4 p-8">
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
    </main>
  );
}
