import { TopBar } from "@/components/layout/TopBar";
import { RankedClipsBoard } from "@/features/ranked-clips/RankedClipsBoard";
import { Fixtures } from "@/lib/api";

/**
 * Phase 9 demo: this defaults to the fixture job. Phase 9.5 will accept
 * a query parameter and resolve the most recent job per tenant.
 */
export default function ClipsPage() {
  const jobId = Fixtures.FIXTURE_JOB.id;
  return (
    <>
      <TopBar
        title="Ranked Clips Board"
        subtitle="Every candidate, sorted by final rank score with engagement-boost badges"
      />
      <div className="px-6 lg:px-8 py-8">
        <RankedClipsBoard jobId={jobId} />
      </div>
    </>
  );
}
