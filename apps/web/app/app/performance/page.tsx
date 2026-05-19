import { TopBar } from "@/components/layout/TopBar";
import { PerformanceDashboard } from "@/features/performance/PerformanceDashboard";
import { Fixtures } from "@/lib/api";

export default function PerformancePage() {
  const jobId = Fixtures.FIXTURE_JOB.id;
  return (
    <>
      <TopBar
        title="Performance Feedback"
        subtitle="Trust-gradient evaluation · maturity · ranking snapshot audit"
      />
      <div className="px-6 lg:px-8 py-8">
        <PerformanceDashboard jobId={jobId} />
      </div>
    </>
  );
}
