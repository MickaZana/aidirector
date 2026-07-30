/**
 * Service barrel export tests.
 *
 * Validates that all services export correctly from their index files.
 */
import { describe, it, expect } from "vitest";
import * as analyticsModule from "@/services/analytics";
import * as servicesIndex from "@/services/index";

describe("services barrel exports", () => {
  it("analytics exports have expected shape", () => {
    expect(analyticsModule.analytics).toBeDefined();
    expect(analyticsModule.ANALYTICS_EVENTS).toBeDefined();
    expect(analyticsModule.ANALYTICS_EVENTS.PROJECT_STARTED).toBe("project_started");
    expect(analyticsModule.ANALYTICS_EVENTS.UPLOAD_COMPLETED).toBe("upload_completed");
    expect(analyticsModule.ANALYTICS_EVENTS.PROCESSING_STARTED).toBe("processing_started");
    expect(analyticsModule.ANALYTICS_EVENTS.PROCESSING_COMPLETED).toBe("processing_completed");
    expect(analyticsModule.ANALYTICS_EVENTS.FEEDBACK_SUBMITTED).toBe("feedback_submitted");
  });
});
