// Mirrors the backend's JSON contracts exactly (see specs/mvp-spec.md §9).
// The `string` fallback on PiiType and JobErrorInfo["code"] is deliberate:
// the backend's PII taxonomy and error codes are both documented as
// extensible, so an unrecognized value must render (with a sensible
// fallback) instead of failing type checks or crashing the UI at runtime.

export type JobStatus =
  | "queued"
  | "detecting"
  | "detected"
  | "correcting"
  | "corrected"
  | "failed";

export interface Locator {
  paragraph?: number;
  page?: number;
  sheet?: string;
  cell?: string;
  row?: number;
  column?: string | number;
  /** JSON locator: dict keys (string) / list indices (number) from the document root to the leaf. */
  path?: Array<string | number>;
  [k: string]: unknown;
}

export interface TextBlock {
  id: string;
  text: string;
  locator: Locator;
}

export type PiiType =
  | "name"
  | "email"
  | "phone"
  | "address"
  | "ssn"
  | "date_of_birth"
  | "credit_card"
  | "bank_account"
  | "ip_address"
  | "drivers_license"
  | "passport"
  | string;

export interface Detection {
  id: string;
  block_id: string;
  pii_type: PiiType;
  value: string;
  start_offset: number;
  end_offset: number;
  confidence: number;
}

export interface JobErrorInfo {
  code:
    | "UNSUPPORTED_FILE_TYPE"
    | "FILE_TOO_LARGE"
    | "PARSE_ERROR"
    | "LLM_ERROR"
    | "JOB_NOT_FOUND"
    | "INVALID_JOB_STATE"
    | "FILE_NOT_READY"
    | "CORRECTION_ERROR"
    | string;
  message: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  file_type?: string;
  blocks?: TextBlock[];
  detections?: Detection[];
  error?: JobErrorInfo | null;
}

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
}
