import type { CreateJobResponse, Job, JobErrorInfo } from "./types";

// Direct client-side fetch calls to the backend (CORS-enabled there for
// this frontend's origin) -- no Next.js rewrite proxy, per product decision.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * Uniform, typed error for any non-2xx API response, regardless of which
 * endpoint failed. Callers can branch on `.code` the same way the backend's
 * own error envelope (`{ status: "failed", error: { code, message } }`,
 * mvp-spec.md §9.5) does.
 */
export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  let code = "UNKNOWN_ERROR";
  let message = `Request failed with status ${response.status}`;

  try {
    const body: unknown = await response.json();
    const errorInfo = (body as { error?: Partial<JobErrorInfo> } | null)?.error;
    if (errorInfo?.code) code = errorInfo.code;
    if (errorInfo?.message) message = errorInfo.message;
  } catch {
    // Response body wasn't JSON (or was empty) -- fall back to the generic
    // status-based message above rather than throwing while handling an error.
  }

  return new ApiError(code, message);
}

async function handleJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw await parseErrorResponse(response);
  }
  return (await response.json()) as T;
}

/** POST /api/jobs/detect (multipart/form-data, field "file"). */
export async function uploadFile(file: File): Promise<CreateJobResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/jobs/detect`, {
    method: "POST",
    body: formData,
  });

  return handleJsonResponse<CreateJobResponse>(response);
}

/** GET /api/jobs/{jobId}. */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}`);
  return handleJsonResponse<Job>(response);
}

/** POST /api/jobs/{jobId}/correct (no body). */
export async function correctJob(jobId: string): Promise<CreateJobResponse> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/correct`, {
    method: "POST",
  });
  return handleJsonResponse<CreateJobResponse>(response);
}

/**
 * Plain URL for GET /api/jobs/{jobId}/download -- not a fetch. Meant to be
 * used directly as an <a href> so the browser streams the response and
 * honors the server's Content-Disposition filename.
 */
export function downloadUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/download`;
}
