/**
 * Typed endpoint functions. Components never call fetch directly — they
 * call one of these. Each function is one API contract, named for what
 * it does and not for the HTTP verb.
 */
import type { ApiClient } from "./client";
import type {
  DirectorPlan,
  Job,
  JobView,
  Upload,
  UsageEvent,
} from "./types";

export interface PresignUploadInput {
  filename: string;
  content_type: string;
  size_bytes: number;
  sport: string;
}

export interface PresignUploadResponse {
  upload_id: string;
  r2_key: string;
  url: string;
  fields: Record<string, string>;
}

export interface CreateJobInput {
  upload_id: string;
  intent?: string;
  cost_budget_cents?: number;
}

export interface DirectorPlanEnvelope {
  id: string;
  job_id: string;
  tenant_id: string;
  model: string;
  prompt_version: string;
  plan: DirectorPlan;
  created_at: string;
}

export class Endpoints {
  constructor(private readonly client: ApiClient) {}

  // --- Uploads ----------------------------------------------------------
  presignUpload(input: PresignUploadInput) {
    return this.client.post<PresignUploadResponse>("/api/uploads/presign", input);
  }
  completeUpload(uploadId: string) {
    return this.client.post<Upload>(`/api/uploads/${uploadId}/complete`, {});
  }
  listUploads() {
    return this.client.get<Upload[]>("/api/uploads");
  }
  getUpload(uploadId: string) {
    return this.client.get<Upload>(`/api/uploads/${uploadId}`);
  }

  // --- Jobs -------------------------------------------------------------
  createJob(input: CreateJobInput) {
    return this.client.post<Job>("/api/jobs", input);
  }
  listJobs() {
    return this.client.get<Job[]>("/api/jobs");
  }
  getJob(jobId: string) {
    return this.client.get<Job>(`/api/jobs/${jobId}`);
  }

  // --- Director plans ---------------------------------------------------
  getDirectorPlan(jobId: string) {
    return this.client.get<DirectorPlanEnvelope>(`/api/jobs/${jobId}/director-plan`);
  }
  saveDirectorPlan(jobId: string, plan: DirectorPlan) {
    return this.client.post<DirectorPlanEnvelope>(
      `/api/jobs/${jobId}/director-plan`,
      { plan },
    );
  }

  // --- Job "view" (composite query the dashboard needs) ----------------
  /**
   * A composite query: backend route to be added in Phase 9.5.
   * For now the client falls back to fixtures when this 404s.
   */
  getJobView(jobId: string) {
    return this.client.get<JobView>(`/api/jobs/${jobId}/view`);
  }

  // --- Usage / billing --------------------------------------------------
  listUsageEvents(params?: { since?: string; type?: string }) {
    const search = new URLSearchParams();
    if (params?.since) search.set("since", params.since);
    if (params?.type) search.set("type", params.type);
    const qs = search.toString();
    return this.client.get<UsageEvent[]>(
      `/api/usage_events${qs ? `?${qs}` : ""}`,
    );
  }
}
