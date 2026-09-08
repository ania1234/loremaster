// Python: def greet(name: str) -> str: return f"Hi {name}"
function greet(name: string): string {
  return `Hi ${name}`;             // backticks, ${} instead of f""
}

// Python: greet = lambda name: f"Hi {name}"
const greet2 = (name: string): string => `Hi ${name}`;

// Python: items = [1, 2, 3];  doubled = [x * 2 for x in items]
const items: number[] = [1, 2, 3];
const doubled = items.map((x) => x * 2);
const evens = items.filter((x) => x % 2 === 0);

// Python: d = {"a": 1};  d["a"]
const d: Record<string, number> = { a: 1 };
console.log(d.a, d["a"]);          // both work

// Python: class + dataclass  ->  interface (types only, no runtime cost)
interface Document {
  id: string;
  title: string;
  status: "pending" | "processing" | "ready" | "failed";
  errorMessage?: string;           // ? means optional
}

// Python: async def get(): r = await client.get(url, headers={"Authorization": f"Bearer {token}"}); return r.json()
const TOKEN = "ey..."; // your Supabase access token (JWT)

async function getDocs(): Promise<Document[]> {
  const res = await fetch("http://localhost:8000/api/documents", {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

console.log(greet("Ada"));
getDocs().then(console.log).catch(console.error);
console.log(greet("Anna"));
