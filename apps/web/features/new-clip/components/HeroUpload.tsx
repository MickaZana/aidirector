"use client";

import { LogoMark } from "@/components/brand/LogoMark";
import { UploadDropzone } from "./UploadDropzone";

interface HeroUploadProps {
  file: File | null;
  onFileSelected: (file: File) => void;
}

/**
 * Hero section — large centered logo, title, subtitle, and upload dropzone.
 * The first thing users see. Must communicate the product within 10 seconds.
 */
export function HeroUpload({ file, onFileSelected }: HeroUploadProps) {
  return (
    <section className="text-center">
      {/* Logo */}
      <div className="flex justify-center">
        <div className="inline-flex items-center gap-3 rounded-2xl bg-white border border-slate-200 px-5 py-3 shadow-sm">
          <LogoMark className="h-8 w-8 text-emerald-500" />
          <span className="text-xl font-bold text-slate-900 tracking-tight">
            AI Director
          </span>
        </div>
      </div>

      {/* Title */}
      <h1 className="mt-8 text-[48px] font-bold leading-tight tracking-tight text-slate-900">
        Turn one video into professional clips
        <br />
        for every platform.
      </h1>

      {/* Subtitle */}
      <p className="mt-4 text-lg text-slate-500 max-w-xl mx-auto leading-relaxed">
        Upload once. Our AI finds the best moments, creates vertical clips,
        adds captions, and prepares everything ready to share.
      </p>

      {/* Upload area */}
      <div className="mt-10">
        <UploadDropzone onFileSelected={onFileSelected} file={file} />
      </div>
    </section>
  );
}
