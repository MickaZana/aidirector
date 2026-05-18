import { auth } from "@clerk/nextjs/server";
import { UserButton } from "@clerk/nextjs";

export default async function Dashboard() {
  const { userId, orgId } = await auth();
  const tenantId = orgId ?? `user_${userId}`;

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="flex items-center justify-between mb-12">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-neutral-500 mt-1">
            tenant: <span className="font-mono">{tenantId}</span>
          </p>
        </div>
        <UserButton />
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <Card title="Jobs" value="—" hint="Phase 1" />
        <Card title="Clips this month" value="—" hint="Phase 1" />
        <Card title="Spend" value="—" hint="Phase 1" />
      </section>

      <section className="mt-12">
        <h2 className="text-lg font-medium mb-3">Upload</h2>
        <div className="rounded-lg border border-neutral-800 p-8 text-center text-neutral-500">
          Upload UI ships in Phase 1 (presigned R2 PUT).
        </div>
      </section>
    </main>
  );
}

function Card({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 p-5">
      <div className="text-sm text-neutral-500">{title}</div>
      <div className="mt-2 text-3xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-neutral-600">{hint}</div>
    </div>
  );
}
