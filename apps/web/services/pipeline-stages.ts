/**
 * Derive the canonical product-loop pipeline view from a JobView.
 *
 * The Processing Timeline component is presentation-first — it just
 * renders an array of PipelineStage rows. The logic that turns rows in
 * the DB into stage statuses lives here, in services, where it can be
 * unit-tested without a React tree.
 */
import type {
  JobView,
  PipelineStage,
  PipelineStageKey,
  UsageEventType,
} from "@/lib/api/types";

interface StageDescriptor {
  key: PipelineStageKey;
  label: string;
  startedBy: UsageEventType[];
  finishedBy: UsageEventType[];
  failureKeys: UsageEventType[];
}

const STAGES: StageDescriptor[] = [
  {
    key: "upload",
    label: "Upload",
    startedBy: ["upload_created"],
    finishedBy: ["analysis_started", "analysis_completed"],
    failureKeys: ["job_failed"],
  },
  {
    key: "analysis",
    label: "Analysis",
    startedBy: ["analysis_started"],
    finishedBy: ["analysis_completed", "ranking_started"],
    failureKeys: ["job_failed"],
  },
  {
    key: "ranking",
    label: "Ranking",
    startedBy: ["ranking_started", "candidate_created"],
    finishedBy: ["ranking_completed", "director_plan_created"],
    failureKeys: ["job_failed"],
  },
  {
    key: "directing",
    label: "Directing",
    startedBy: ["director_plan_created"],
    finishedBy: ["render_started"],
    failureKeys: ["job_failed"],
  },
  {
    key: "rendering",
    label: "Rendering",
    startedBy: ["render_started"],
    finishedBy: ["render_completed"],
    failureKeys: ["job_failed"],
  },
  {
    key: "exporting",
    label: "Exporting",
    startedBy: ["render_completed"],
    finishedBy: ["export_created"],
    failureKeys: ["job_failed"],
  },
  {
    key: "feedback",
    label: "Feedback",
    startedBy: ["engagement_ingested"],
    finishedBy: ["ranking_feedback_applied"],
    failureKeys: ["job_failed"],
  },
];

export function derivePipelineStages(view: JobView | null): PipelineStage[] {
  if (!view) return STAGES.map(toIdleStage);

  const events = [...view.usage_events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  return STAGES.map((desc) => {
    const startedEvt = events.find((e) => desc.startedBy.includes(e.event_type));
    const finishedEvt = events.find((e) => desc.finishedBy.includes(e.event_type));
    const failureEvt = events.find((e) => desc.failureKeys.includes(e.event_type));

    let status: PipelineStage["status"] = "idle";
    if (failureEvt) status = "failed";
    else if (finishedEvt) status = "succeeded";
    else if (startedEvt) status = "running";

    const elapsed = startedEvt
      ? ((finishedEvt ? new Date(finishedEvt.created_at).getTime() : Date.now()) -
          new Date(startedEvt.created_at).getTime()) / 1000
      : null;

    return {
      key: desc.key,
      label: desc.label,
      status,
      started_at: startedEvt?.created_at ?? null,
      finished_at: finishedEvt?.created_at ?? null,
      elapsed_seconds: elapsed,
      detail: finishedEvt?.event_metadata ?? startedEvt?.event_metadata ?? null,
    };
  });
}

function toIdleStage(d: StageDescriptor): PipelineStage {
  return {
    key: d.key,
    label: d.label,
    status: "idle",
    started_at: null,
    finished_at: null,
    elapsed_seconds: null,
    detail: null,
  };
}

/** Convenience: which stage is currently active (or last completed). */
export function currentStage(stages: PipelineStage[]): PipelineStage {
  return (
    stages.find((s) => s.status === "running") ??
    [...stages].reverse().find((s) => s.status === "succeeded") ??
    stages[0]
  );
}
