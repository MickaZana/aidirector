"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer, Typography, AppIcon } from "@/features/design-system";
import { analytics } from "@/services/analytics";
import { toast } from "@/stores/toast-store";
import { HeroUpload } from "@/features/new-clip/components/HeroUpload";
import { RecentUploads } from "@/features/new-clip/components/RecentUploads";
import { OnboardingOverlay } from "@/features/onboarding";
import { QuickSetup } from "@/features/new-clip/components/QuickSetup";
import { HowItWorks } from "@/features/new-clip/components/HowItWorks";
import { HelpCard } from "@/features/new-clip/components/HelpCard";
import { FAQAccordion } from "@/features/new-clip/components/FAQAccordion";
import { Footer } from "@/features/new-clip/components/Footer";
import { PLATFORMS } from "@/features/new-clip/constants/platforms";
import type { VideoType, RecentUpload } from "@/features/new-clip/types";

/**
 * Mock recent uploads — will be replaced by real data in Phase 2.2.
 * Shows "Continue Working" card with last 3 uploads.
 */
const MOCK_RECENT_UPLOADS: RecentUpload[] = [
  {
    id: "1",
    title: "Liverpool vs Chelsea",
    subtitle: "Uploaded yesterday",
    emoji: "⚽",
  },
  {
    id: "2",
    title: "Manchester United Highlights",
    subtitle: "Uploaded 3 days ago",
    emoji: "⚽",
  },
  {
    id: "3",
    title: "The Joe Rogan Experience",
    subtitle: "Uploaded last week",
    emoji: "🎙",
  },
];

/**
 * New Clip page — Screen 1 of the 3-screen creator-first experience.
 * Uses design-system PageContainer and Typography for consistent layout.
 */
export default function NewClipPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [file, setFile] = useState<File | null>(null);
  const [videoType, setVideoType] = useState<VideoType | null>(null);
  const [platforms, setPlatforms] = useState<string[]>(["youtube_shorts"]);
  const [clipCount, setClipCount] = useState(12);
  const [loading, setLoading] = useState(false);

  // Track that user started using the product
  useEffect(() => {
    analytics.track("project_started");
  }, []);

  // Show cancellation toast if returning from cancelled processing
  useEffect(() => {
    if (searchParams.get("cancelled") === "true") {
      toast.warning("Processing cancelled", "You can start a new project whenever you're ready.");
      // Clean up the URL
      window.history.replaceState(null, "", "/app/upload");
    }
  }, [searchParams]);

  // Show offline warning when user tries to upload while offline
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    setOffline(!navigator.onLine);
    const handleOffline = () => setOffline(true);
    const handleOnline = () => setOffline(false);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  const handleFileSelected = useCallback((f: File) => {
    setFile(f);
    analytics.track("upload_completed", { fileName: f.name, fileSize: f.size });
  }, []);

  const handleCreateClips = useCallback(() => {
    if (!file) return;
    setLoading(true);
    analytics.track("processing_started", { clipCount, platforms });
    // Navigate to processing screen — the real upload happens there
    router.push("/app/processing" as never);
  }, [file, clipCount, platforms, router]);

  return (
    <PageContainer className="space-y-12 md:space-y-16">
      {/* Offline warning */}
      {offline && (
        <div
          className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4"
          role="alert"
        >
          <AppIcon name="alertCircle" size="md" className="text-amber-500 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-amber-900">You&apos;re offline</p>
            <p className="text-sm text-amber-700">
              Uploads are disabled until your connection is restored. Your projects will be
              saved locally.
            </p>
          </div>
        </div>
      )}

      {/* 1. Hero + Upload */}
      <HeroUpload file={file} onFileSelected={handleFileSelected} />

      {/* 2. Recent Uploads — "Continue Working" */}
      <RecentUploads uploads={MOCK_RECENT_UPLOADS} />

      {/* 3. Quick Setup */}
      <QuickSetup
        videoType={videoType}
        onVideoTypeChange={setVideoType}
        platforms={PLATFORMS}
        onPlatformsChange={setPlatforms}
        clipCount={clipCount}
        onClipCountChange={setClipCount}
        canCreate={file !== null}
        loading={loading}
        onCreateClips={handleCreateClips}
      />

      {/* 4. How It Works */}
      <HowItWorks />

      {/* 5. Need Help? + FAQ — side by side on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        <div className="lg:col-span-2">
          <HelpCard />
        </div>
        <div className="lg:col-span-3">
          <FAQAccordion />
        </div>
      </div>

      {/* 6. Empty-state encouragement — only when no recent uploads */}
      {MOCK_RECENT_UPLOADS.length === 0 && (
        <Typography variant="small" className="text-center">
          Upload your first video to get started. We&apos;ll turn it into
          platform-ready clips in minutes.
        </Typography>
      )}

      {/* 7. Footer */}
      <Footer />

      {/* First-run onboarding overlay */}
      <OnboardingOverlay />
    </PageContainer>
  );
}
