export interface PlatformOption {
  id: string;
  label: string;
}

/**
 * Supported publishing platforms.
 * Add new platforms here — they'll appear automatically in the selector.
 */
export const PLATFORMS: PlatformOption[] = [
  { id: "youtube_shorts", label: "YouTube Shorts" },
  { id: "tiktok", label: "TikTok" },
  { id: "instagram_reels", label: "Instagram Reels" },
  { id: "facebook_reels", label: "Facebook Reels" },
];
