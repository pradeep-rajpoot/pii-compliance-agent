"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, getJob } from "./apiClient";
import { DEFAULT_POLL_INTERVAL_MS, MAX_CONSECUTIVE_NETWORK_FAILURES } from "./constants";
import type { Detection, Job, JobErrorInfo, JobStatus } from "./types";

export interface UseJobPollingOptions {
  intervalMs?: number;
}

export interface UseJobPollingResult {
  job: Job | null;
  status: JobStatus | null;
  detections: Detection[];
  error: JobErrorInfo | null;
  isPolling: boolean;
}

// "detected" is NOT terminal -- the workflow continues through "correcting"
// to "corrected". Only these two statuses stop polling.
const TERMINAL_STATUSES: readonly JobStatus[] = ["corrected", "failed"];

/**
 * Polls GET /api/jobs/{jobId} on an interval until the job reaches a
 * terminal state. No-ops when jobId is null. Fires an immediate fetch on
 * mount/jobId-change so the first paint doesn't wait a full interval.
 */
export function useJobPolling(
  jobId: string | null,
  options: UseJobPollingOptions = {},
): UseJobPollingResult {
  const intervalMs = options.intervalMs ?? DEFAULT_POLL_INTERVAL_MS;

  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<JobErrorInfo | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const intervalIdRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const failureCountRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // Reset per-job state whenever the target job id changes.
    setJob(null);
    setError(null);
    failureCountRef.current = 0;

    if (intervalIdRef.current !== null) {
      clearInterval(intervalIdRef.current);
      intervalIdRef.current = null;
    }

    if (!jobId) {
      setIsPolling(false);
      return;
    }

    let cancelled = false;
    setIsPolling(true);

    const stop = () => {
      if (intervalIdRef.current !== null) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
      if (mountedRef.current && !cancelled) {
        setIsPolling(false);
      }
    };

    const tick = async () => {
      try {
        const nextJob = await getJob(jobId);
        if (cancelled || !mountedRef.current) return;

        failureCountRef.current = 0;
        setJob(nextJob);

        if (TERMINAL_STATUSES.includes(nextJob.status)) {
          setError(nextJob.status === "failed" ? (nextJob.error ?? { code: "UNKNOWN_ERROR", message: "The job failed." }) : null);
          stop();
        }
      } catch (err) {
        if (cancelled || !mountedRef.current) return;

        if (err instanceof ApiError) {
          // A well-formed backend error response (e.g. 404 JOB_NOT_FOUND) is
          // a definitive answer, not a transient blip -- stop immediately.
          const errorInfo: JobErrorInfo = { code: err.code, message: err.message };
          setError(errorInfo);
          setJob((prev) => ({
            job_id: jobId,
            status: "failed",
            file_type: prev?.file_type,
            blocks: prev?.blocks,
            detections: prev?.detections,
            error: errorInfo,
          }));
          stop();
          return;
        }

        // Raw network/fetch exception, not covered by the backend's error
        // model at all -- retry a few times (a slow LLM call can cause an
        // occasional transient blip) before giving up.
        failureCountRef.current += 1;
        if (failureCountRef.current >= MAX_CONSECUTIVE_NETWORK_FAILURES) {
          const errorInfo: JobErrorInfo = {
            code: "NETWORK_ERROR",
            message: "Lost connection to the server while checking job status.",
          };
          setError(errorInfo);
          setJob((prev) =>
            prev
              ? { ...prev, status: "failed", error: errorInfo }
              : { job_id: jobId, status: "failed", error: errorInfo },
          );
          stop();
        }
        // Otherwise: swallow this failure and let the next interval tick retry.
      }
    };

    tick();
    intervalIdRef.current = setInterval(tick, intervalMs);

    return () => {
      cancelled = true;
      if (intervalIdRef.current !== null) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
    };
  }, [jobId, intervalMs]);

  return {
    job,
    status: job?.status ?? null,
    detections: job?.detections ?? [],
    error,
    isPolling,
  };
}
