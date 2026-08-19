"use client";

import { useEffect, useReducer } from "react";
import ConvertButton from "@/components/ConvertButton";
import DocumentPreview from "@/components/DocumentPreview";
import DownloadButton from "@/components/DownloadButton";
import JobStatusBanner from "@/components/JobStatusBanner";
import UploadDropzone, { type UploadValidationError } from "@/components/UploadDropzone";
import { ApiError, correctJob, uploadFile } from "@/lib/apiClient";
import type { Job, JobErrorInfo, JobStatus } from "@/lib/types";
import { useJobPolling } from "@/lib/useJobPolling";
import styles from "./page.module.css";

type Phase = "idle" | "validation_error" | "uploading" | "upload_error" | JobStatus;

interface State {
  phase: Phase;
  jobId: string | null;
  job: Job | null;
  clientError: JobErrorInfo | null;
}

type Action =
  | { type: "FILE_VALIDATION_FAILED"; error: JobErrorInfo }
  | { type: "UPLOAD_STARTED" }
  | { type: "UPLOAD_SUCCEEDED"; jobId: string }
  | { type: "UPLOAD_FAILED"; error: JobErrorInfo }
  | { type: "JOB_UPDATED"; job: Job }
  | { type: "CONVERT_CLICKED" }
  | { type: "CONVERT_FAILED"; error: JobErrorInfo }
  | { type: "RESET" };

const initialState: State = { phase: "idle", jobId: null, job: null, clientError: null };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FILE_VALIDATION_FAILED":
      return { ...initialState, phase: "validation_error", clientError: action.error };

    case "UPLOAD_STARTED":
      return { ...initialState, phase: "uploading" };

    case "UPLOAD_SUCCEEDED":
      return { ...state, phase: "queued", jobId: action.jobId, clientError: null };

    case "UPLOAD_FAILED":
      return { ...state, phase: "upload_error", clientError: action.error };

    case "JOB_UPDATED":
      // Phase becomes job.status directly -- the reducer never independently
      // guesses backend state, it just mirrors what polling observed.
      return { ...state, phase: action.job.status, job: action.job, clientError: action.job.error ?? null };

    case "CONVERT_CLICKED":
      // Optimistically move detected -> correcting, matching the 202
      // response's own status field. Polling reconciles on its next tick.
      return {
        ...state,
        phase: "correcting",
        job: state.job ? { ...state.job, status: "correcting" } : state.job,
      };

    case "CONVERT_FAILED":
      return { ...state, phase: "failed", clientError: action.error };

    case "RESET":
      return initialState;

    default:
      return state;
  }
}

function toClientError(err: unknown, fallbackMessage: string): JobErrorInfo {
  if (err instanceof ApiError) {
    return { code: err.code, message: err.message };
  }
  return { code: "NETWORK_ERROR", message: fallbackMessage };
}

export default function Page() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { job } = useJobPolling(state.jobId);

  useEffect(() => {
    if (job) {
      dispatch({ type: "JOB_UPDATED", job });
    }
  }, [job]);

  async function handleFileAccepted(file: File) {
    dispatch({ type: "UPLOAD_STARTED" });
    try {
      const response = await uploadFile(file);
      dispatch({ type: "UPLOAD_SUCCEEDED", jobId: response.job_id });
    } catch (err) {
      dispatch({ type: "UPLOAD_FAILED", error: toClientError(err, "Could not reach the server. Please try again.") });
    }
  }

  function handleValidationError(error: UploadValidationError) {
    dispatch({ type: "FILE_VALIDATION_FAILED", error });
  }

  async function handleConvertClick() {
    if (!state.jobId) return;
    dispatch({ type: "CONVERT_CLICKED" });
    try {
      await correctJob(state.jobId);
      // Polling picks up the authoritative status on its next tick; the
      // optimistic "correcting" phase above already matches the 202 response.
    } catch (err) {
      dispatch({
        type: "CONVERT_FAILED",
        error: toClientError(err, "Could not start the conversion. Please try again."),
      });
    }
  }

  function handleReset() {
    dispatch({ type: "RESET" });
  }

  const showUpload = state.phase === "idle" || state.phase === "validation_error" || state.phase === "upload_error";
  const showPreview = Boolean(state.job?.blocks && state.job.blocks.length > 0);
  const isTerminal = state.phase === "corrected" || state.phase === "failed";
  const isUploading = state.phase === "uploading";

  // Once a jobId exists, `phase` only ever holds a real JobStatus value
  // (see the reducer above); this is the shared status passed to the
  // convert/download buttons, which don't know about the pre-job phases.
  const jobPhase: JobStatus | "idle" = state.jobId ? (state.phase as JobStatus) : "idle";

  return (
    <main className={styles.main}>
      <h1 className={styles.title}>PII Compliance Agent</h1>
      <p className={styles.subtitle}>
        Upload a document to detect personally identifiable information and generate a masked, PII-safe copy.
      </p>

      {showUpload && (
        <UploadDropzone
          onFileAccepted={handleFileAccepted}
          onValidationError={handleValidationError}
          disabled={isUploading}
        />
      )}

      <JobStatusBanner status={state.phase} error={state.clientError} />

      {showPreview && state.job?.blocks && (
        <DocumentPreview blocks={state.job.blocks} detections={state.job.detections ?? []} />
      )}

      <div className={styles.actions}>
        <ConvertButton status={jobPhase} onClick={handleConvertClick} />
        {state.jobId && <DownloadButton jobId={state.jobId} status={jobPhase} />}
        {isTerminal && (
          <button type="button" className={styles.resetButton} onClick={handleReset}>
            Start over
          </button>
        )}
      </div>
    </main>
  );
}
