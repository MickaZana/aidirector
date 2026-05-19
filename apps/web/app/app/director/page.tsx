import { redirect } from "next/navigation";
import { Fixtures } from "@/lib/api";

export default function DirectorIndexPage() {
  // Phase 9.5: resolve most recent job per tenant. For now, the fixture job.
  redirect(`/app/director/${Fixtures.FIXTURE_JOB.id}`);
}
