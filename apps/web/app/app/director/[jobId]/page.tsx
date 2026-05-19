import { TopBar } from "@/components/layout/TopBar";
import { DirectorReviewWorkspace } from "@/features/director-review/DirectorReviewWorkspace";

export default async function DirectorReviewPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return (
    <>
      <TopBar
        title="AI Director Review"
        subtitle="Editorial intent · base / engagement / final score breakdown"
      />
      <div className="px-6 lg:px-8 py-8">
        <DirectorReviewWorkspace jobId={jobId} />
      </div>
    </>
  );
}
