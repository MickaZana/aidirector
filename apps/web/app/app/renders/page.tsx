import { TopBar } from "@/components/layout/TopBar";
import { RenderCenter } from "@/features/render-center/RenderCenter";
import { Fixtures } from "@/lib/api";

export default function RendersPage() {
  const jobId = Fixtures.FIXTURE_JOB.id;
  return (
    <>
      <TopBar
        title="Render & Export Center"
        subtitle="Variant queue · render outputs · canonical export identity"
      />
      <div className="px-6 lg:px-8 py-8">
        <RenderCenter jobId={jobId} />
      </div>
    </>
  );
}
