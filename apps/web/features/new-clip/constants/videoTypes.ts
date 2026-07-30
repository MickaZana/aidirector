import type { VideoType } from "../types";

export interface VideoTypeOption {
  id: VideoType;
  emoji: string;
  label: string;
}

/**
 * Supported video types.
 * Add new sports here — they'll appear automatically in the selector.
 */
export const VIDEO_TYPES: VideoTypeOption[] = [
  { id: "football", emoji: "⚽", label: "Football" },
  { id: "podcast", emoji: "🎙", label: "Podcast" },
  { id: "basketball", emoji: "🏀", label: "Basketball" },
];
