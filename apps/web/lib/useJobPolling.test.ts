import { act, renderHook } from "@testing-library/react";
import { useJobPolling } from "./useJobPolling";
import type { Job } from "./types";

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

function makeJob(status: Job["status"], overrides: Partial<Job> = {}): Job {
  return { job_id: "job-1", status, ...overrides };
}

/** Advances fake timers and flushes the microtask queue enough times for
 * chained `await`s inside the polled fetch (fetch -> response.json() ->
 * state update) to settle. */
async function flush(ms = 0) {
  await act(async () => {
    await jest.advanceTimersByTimeAsync(ms);
  });
}

describe("useJobPolling", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("polls through queued -> detecting -> detected -> correcting -> corrected, WITHOUT stopping at detected", async () => {
    const sequence: Job["status"][] = ["queued", "detecting", "detected", "correcting", "corrected"];
    let callIndex = 0;
    const fetchMock = jest.fn(async () => {
      const status = sequence[Math.min(callIndex, sequence.length - 1)];
      callIndex += 1;
      return jsonResponse(makeJob(status));
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useJobPolling("job-1", { intervalMs: 1000 }));

    await flush(); // immediate fetch on mount
    expect(result.current.status).toBe("queued");
    expect(result.current.isPolling).toBe(true);

    await flush(1000);
    expect(result.current.status).toBe("detecting");
    expect(result.current.isPolling).toBe(true);

    await flush(1000);
    expect(result.current.status).toBe("detected");
    // Critical: "detected" is not terminal. Polling must continue.
    expect(result.current.isPolling).toBe(true);

    await flush(1000);
    expect(result.current.status).toBe("correcting");
    expect(result.current.isPolling).toBe(true);

    await flush(1000);
    expect(result.current.status).toBe("corrected");
    expect(result.current.isPolling).toBe(false);
    expect(result.current.error).toBeNull();

    const callsAtStop = fetchMock.mock.calls.length;
    await flush(10000);
    expect(fetchMock.mock.calls.length).toBe(callsAtStop);
  });

  it("stops polling after a failed status and surfaces the backend error", async () => {
    const sequence: Job["status"][] = ["queued", "detecting", "failed"];
    let callIndex = 0;
    const fetchMock = jest.fn(async () => {
      const status = sequence[Math.min(callIndex, sequence.length - 1)];
      callIndex += 1;
      const error = status === "failed" ? { code: "LLM_ERROR", message: "boom" } : null;
      return jsonResponse(makeJob(status, { error }));
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useJobPolling("job-1", { intervalMs: 1000 }));

    await flush();
    await flush(1000);
    await flush(1000);

    expect(result.current.status).toBe("failed");
    expect(result.current.isPolling).toBe(false);
    expect(result.current.error).toEqual({ code: "LLM_ERROR", message: "boom" });

    const callsAtStop = fetchMock.mock.calls.length;
    await flush(10000);
    expect(fetchMock.mock.calls.length).toBe(callsAtStop);
  });

  it("retries a small number of times on raw network failures before giving up", async () => {
    const fetchMock = jest.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useJobPolling("job-1", { intervalMs: 1000 }));

    await flush(); // failure 1 -- should keep polling
    expect(result.current.isPolling).toBe(true);
    expect(result.current.error).toBeNull();

    await flush(1000); // failure 2 -- should still keep polling
    expect(result.current.isPolling).toBe(true);
    expect(result.current.error).toBeNull();

    await flush(1000); // failure 3 -- exhausts the retry budget
    expect(result.current.isPolling).toBe(false);
    expect(result.current.error).not.toBeNull();
    expect(result.current.status).toBe("failed");
  });

  it("produces no further fetch calls after unmount", async () => {
    const fetchMock = jest.fn(async () => jsonResponse(makeJob("detecting")));
    global.fetch = fetchMock as unknown as typeof fetch;

    const { unmount } = renderHook(() => useJobPolling("job-1", { intervalMs: 1000 }));

    await flush();
    const callsBeforeUnmount = fetchMock.mock.calls.length;

    unmount();
    await flush(10000);

    expect(fetchMock.mock.calls.length).toBe(callsBeforeUnmount);
  });

  it("resets cleanly when jobId changes to a different job", async () => {
    const fetchMock = jest.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("job-1")) return jsonResponse(makeJob("detecting", { job_id: "job-1" }));
      return jsonResponse(makeJob("queued", { job_id: "job-2" }));
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result, rerender } = renderHook(({ jobId }) => useJobPolling(jobId, { intervalMs: 1000 }), {
      initialProps: { jobId: "job-1" as string | null },
    });

    await flush();
    expect(result.current.job?.job_id).toBe("job-1");
    expect(result.current.status).toBe("detecting");

    act(() => {
      rerender({ jobId: "job-2" });
    });

    // Resets immediately, independent of the new job's fetch resolving.
    expect(result.current.job).toBeNull();
    expect(result.current.status).toBeNull();

    await flush();
    expect(result.current.job?.job_id).toBe("job-2");
    expect(result.current.status).toBe("queued");
  });

  it("does not poll when jobId is null", () => {
    const fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useJobPolling(null));

    expect(result.current.isPolling).toBe(false);
    expect(result.current.job).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
