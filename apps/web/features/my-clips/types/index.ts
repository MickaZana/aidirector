/**
 * Clip and project types for the My Clips screen.
 */
export interface Clip {
  id: string;
  title: string;
  duration: string;
  /** Placeholder: real thumbnails will come from the API */
  thumbnailUrl?: string;
  /** Quality score 0–10 */
  score: number;
  platforms: string[];
  status: "ready" | "processing" | "failed";
  videoUrl?: string;
  createdAt: string;
}

export interface Project {
  videoName: string;
  uploadDate: string;
  clipCount: number;
  processingTime: string;
  platforms: string[];
}
