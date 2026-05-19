import { TopBar } from "@/components/layout/TopBar";
import { UploadStudio } from "@/features/upload-studio/UploadStudio";

export default function UploadPage() {
  return (
    <>
      <TopBar
        title="Upload Studio"
        subtitle="Primary entry point · drop a match, pick targets, watch the pipeline run"
      />
      <UploadStudio />
    </>
  );
}
