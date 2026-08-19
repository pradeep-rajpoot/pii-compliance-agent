import { buildSegments } from "./highlightSegments";
import type { Detection } from "./types";

function makeDetection(overrides: Partial<Detection>): Detection {
  return {
    id: "d1",
    block_id: "b1",
    pii_type: "email",
    value: "",
    start_offset: 0,
    end_offset: 0,
    confidence: 0.9,
    ...overrides,
  };
}

describe("buildSegments", () => {
  it("returns a single plain segment when there are no detections", () => {
    const segments = buildSegments("hello world", []);
    expect(segments).toEqual([{ text: "hello world", detection: null }]);
  });

  it("handles a single span in the middle of the text", () => {
    const text = "contact jane@example.com today";
    const detection = makeDetection({ id: "d1", start_offset: 8, end_offset: 24 });
    const segments = buildSegments(text, [detection]);

    expect(segments).toEqual([
      { text: "contact ", detection: null },
      { text: "jane@example.com", detection },
      { text: " today", detection: null },
    ]);
  });

  it("handles two adjacent spans with no gap (end of one == start of the next)", () => {
    const text = "abcdefghij";
    const first = makeDetection({ id: "d1", start_offset: 0, end_offset: 5 });
    const second = makeDetection({ id: "d2", start_offset: 5, end_offset: 10 });
    const segments = buildSegments(text, [first, second]);

    expect(segments).toEqual([
      { text: "abcde", detection: first },
      { text: "fghij", detection: second },
    ]);
  });

  it("clamps and truncates a partially overlapping second span rather than dropping it", () => {
    const text = "abcdefghij";
    // first: [0,6) "abcdef"; second overlaps into [3,10) "defghij"
    const first = makeDetection({ id: "d1", start_offset: 0, end_offset: 6 });
    const second = makeDetection({ id: "d2", start_offset: 3, end_offset: 10 });
    const segments = buildSegments(text, [first, second]);

    // second gets clamped to start at the cursor (6), so only "ghij" survives
    expect(segments).toEqual([
      { text: "abcdef", detection: first },
      { text: "ghij", detection: second },
    ]);
  });

  it("drops a span that is fully subsumed by a prior one", () => {
    const text = "abcdefghij";
    const outer = makeDetection({ id: "d1", start_offset: 0, end_offset: 10 });
    const inner = makeDetection({ id: "d2", start_offset: 2, end_offset: 5 });
    const segments = buildSegments(text, [outer, inner]);

    expect(segments).toEqual([{ text: "abcdefghij", detection: outer }]);
  });

  it("clamps an out-of-range end offset instead of throwing", () => {
    const text = "short";
    const detection = makeDetection({ id: "d1", start_offset: 2, end_offset: 999 });

    expect(() => buildSegments(text, [detection])).not.toThrow();
    const segments = buildSegments(text, [detection]);
    expect(segments).toEqual([
      { text: "sh", detection: null },
      { text: "ort", detection },
    ]);
  });

  it("clamps a negative/out-of-range start offset instead of throwing", () => {
    const text = "short";
    const detection = makeDetection({ id: "d1", start_offset: -5, end_offset: 3 });

    expect(() => buildSegments(text, [detection])).not.toThrow();
    const segments = buildSegments(text, [detection]);
    expect(segments).toEqual([{ text: "sho", detection }, { text: "rt", detection: null }]);
  });

  it("breaks ties for equal start_offset deterministically by longer span first", () => {
    const text = "abcdefghij";
    const shortSpan = makeDetection({ id: "short", start_offset: 0, end_offset: 3 });
    const longSpan = makeDetection({ id: "long", start_offset: 0, end_offset: 7 });

    // Regardless of input order, the longer span should win and the shorter
    // one (now fully subsumed) should be dropped.
    const segmentsA = buildSegments(text, [shortSpan, longSpan]);
    const segmentsB = buildSegments(text, [longSpan, shortSpan]);

    expect(segmentsA).toEqual([
      { text: "abcdefg", detection: longSpan },
      { text: "hij", detection: null },
    ]);
    expect(segmentsA).toEqual(segmentsB);
  });
});
