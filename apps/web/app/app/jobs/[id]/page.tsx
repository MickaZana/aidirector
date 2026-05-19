import { TopBar } from "@/components/layout/TopBar";
import { ProcessingTimeline } from "@/features/processing-timeline/ProcessingTimeline";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <TopBar
        title="Processing Timeline"
        subtitle={`Job ${id.split("-")[0]} · live pipeline view`}
      />
      <div className="px-6 lg:px-8 py-8">
        <ProcessingTimeline jobId={id} />
      </div>
    </>
  );
}
