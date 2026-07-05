/**
 * Typed endpoint functions. Components never call fetch directly — they
 * call one of these. Each function is one API contract, named for what
 * it does and not for the HTTP verb.
 */
import type { ApiClient } from "./client";
import type {
  BriefTemplate,
  BriefTemplateCreate,
  DirectorPlan,
  Job,
  JobEvents,
  JobView,
  Upload,
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
   * Composite query backing the entire job page in one round-trip.
   * Backed by `GET /api/jobs/{id}/view` (Phase 9.5).
   */
  getJobView(jobId: string) {
    return this.client.get<JobView>(`/api/jobs/${jobId}/view`);
  }

  /**
   * Cheap status refresh — polled by `PollingTransport`. Bumping
   * `revision` on the server side is the signal to refetch `getJobView`.
   */
  getJobEvents(jobId: string) {
    return this.client.get<JobEvents>(`/api/jobs/${jobId}/events`);
  }

  // --- DSR (GDPR) -------------------------------------------------------
  /**
   * Request account deletion. Returns deletion_scheduled_for date.
   */
  requestDsrDeletion() {
    return this.client.post<{
      tenant_id: string;
      deletion_requested_at: string;
      deletion_scheduled_for: string;
      grace_days: number;
      message: string;
    }>("/api/v1/dsr/deletion", {});
  }

  /**
   * Cancel a pending deletion request.
   */
  cancelDsrDeletion() {
    return this.client.delete<{ tenant_id: string; message: string }>("/api/v1/dsr/deletion");
  }

  /**
   * Check the status of a pending deletion request.
   */
  getDsrDeletionStatus() {
    return this.client.get<{
      tenant_id: string;
      deletion_requested: boolean;
      deletion_requested_at: string | null;
      deletion_scheduled_for: string | null;
      deletion_cancelled: boolean;
      grace_days: number;
      days_remaining: number | null;
    }>("/api/v1/dsr/deletion");
  }

  /**
   * Export all personal data (GDPR Article 20).
   */
  exportDsrData() {
    return this.client.post<{
      generated_at: string;
      schema_version: string;
      account: Record<string, unknown>;
      uploads: unknown[];
      jobs: unknown[];
    }>("/api/v1/dsr/export", {});
  }

  // --- Brief templates ----------------------------------------------------
  listBriefTemplates(sport?: string) {
    const params = sport ? `?sport=${encodeURIComponent(sport)}` : "";
    return this.client.get<BriefTemplate[]>(`/api/brief-templates${params}`);
  }
  createBriefTemplate(input: BriefTemplateCreate) {
    return this.client.post<BriefTemplate>("/api/brief-templates", input);
  }
  deleteBriefTemplate(id: string) {
    return this.client.delete<void>(`/api/brief-templates/${id}`);
  }

}
