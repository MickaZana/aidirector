/** Supported video/content types for AI analysis */
export type VideoType = "football" | "podcast" | "basketball";

/** A single recent upload entry */
export interface RecentUpload {
  id: string;
  title: string;
  subtitle: string;
  emoji: string;
}
