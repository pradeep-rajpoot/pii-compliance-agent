import type { Detection } from "./types";

export interface Segment {
  text: string;
  detection: Detection | null;
}

/**
 * Splits `blockText` into an ordered list of plain-text and highlighted
 * segments given the detections that apply to that block.
 *
 * Pure and React-free so it's unit-testable standalone.
 *
 * Algorithm (defends against overlapping/out-of-range offsets even though
 * the backend already dedupes/validates -- never let a UI regression there
 * crash rendering):
 *   1. Sort detections by start_offset ascending, then by span length
 *      descending (deterministic tie-break for equal start offsets).
 *   2. Walk the sorted list with a cursor. Clamp each detection's start/end
 *      into [cursor, blockText.length]. If the clamped start >= the clamped
 *      end, the detection is fully subsumed by a prior one (or was entirely
 *      out of range) -- drop it. A partially-overlapping detection is
 *      truncated to its non-overlapping remainder rather than dropped.
 *   3. Emit a plain-text segment for any gap before a surviving detection,
 *      then a highlighted segment for the (clamped) detection itself.
 *   4. Emit a trailing plain-text segment for anything after the last
 *      detection.
 */
export function buildSegments(blockText: string, blockDetections: Detection[]): Segment[] {
  const sorted = [...blockDetections].sort((a, b) => {
    if (a.start_offset !== b.start_offset) return a.start_offset - b.start_offset;
    const aLen = a.end_offset - a.start_offset;
    const bLen = b.end_offset - b.start_offset;
    return bLen - aLen;
  });

  const len = blockText.length;
  const segments: Segment[] = [];
  let cursor = 0;

  for (const detection of sorted) {
    const start = Math.min(Math.max(detection.start_offset, cursor), len);
    const end = Math.min(Math.max(detection.end_offset, cursor), len);

    if (start >= end) {
      // Fully subsumed by a prior detection (or degenerate/out-of-range).
      continue;
    }

    if (start > cursor) {
      segments.push({ text: blockText.slice(cursor, start), detection: null });
    }
    segments.push({ text: blockText.slice(start, end), detection });
    cursor = end;
  }

  if (cursor < len) {
    segments.push({ text: blockText.slice(cursor, len), detection: null });
  }

  return segments;
}
