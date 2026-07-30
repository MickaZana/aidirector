"use client";

import { VIDEO_TYPES } from "../constants/videoTypes";
import type { VideoType } from "../types";
import { SelectionCard } from "./SelectionCard";

interface VideoTypeSelectorProps {
  value: VideoType | null;
  onChange: (type: VideoType) => void;
}

/**
 * Video type selector — three large cards, single selection.
 * Data sourced from constants/videoTypes.ts for easy extensibility.
 * Ask: "What type of video is this?"
 */
export function VideoTypeSelector({ value, onChange }: VideoTypeSelectorProps) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-slate-900">
        What type of video is this?
      </h2>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {VIDEO_TYPES.map((opt) => (
          <SelectionCard
            key={opt.id}
            selected={value === opt.id}
            onClick={() => onChange(opt.id)}
            ariaLabel={opt.label}
          >
            <div className="flex flex-col items-center text-center gap-2">
              <span className="text-3xl">{opt.emoji}</span>
              <span className="text-base font-medium text-slate-800">
                {opt.label}
              </span>
            </div>
          </SelectionCard>
        ))}
      </div>
    </section>
  );
}
