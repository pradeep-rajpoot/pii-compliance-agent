import { render, screen } from "@testing-library/react";
import DocumentPreview from "./DocumentPreview";
import type { Detection, TextBlock } from "@/lib/types";

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

describe("DocumentPreview", () => {
  it("renders non-overlapping highlighted segments for a block with two adjacent detections", () => {
    const blocks: TextBlock[] = [{ id: "b1", text: "abcdefghij", locator: { paragraph: 1 } }];
    const detections: Detection[] = [
      makeDetection({ id: "d1", block_id: "b1", pii_type: "name", start_offset: 0, end_offset: 5 }),
      makeDetection({ id: "d2", block_id: "b1", pii_type: "email", start_offset: 5, end_offset: 10 }),
    ];

    render(<DocumentPreview blocks={blocks} detections={detections} />);

    const marks = screen.getAllByText((_, element) => element?.tagName === "MARK");
    expect(marks).toHaveLength(2);
    expect(marks[0]).toHaveTextContent("abcde");
    expect(marks[1]).toHaveTextContent("fghij");
  });

  it("truncates overlapping detections instead of double-rendering the overlapped text", () => {
    const blocks: TextBlock[] = [{ id: "b1", text: "abcdefghij", locator: {} }];
    const detections: Detection[] = [
      makeDetection({ id: "d1", block_id: "b1", start_offset: 0, end_offset: 6 }),
      makeDetection({ id: "d2", block_id: "b1", start_offset: 3, end_offset: 10 }),
    ];

    render(<DocumentPreview blocks={blocks} detections={detections} />);

    const marks = screen.getAllByText((_, element) => element?.tagName === "MARK");
    expect(marks).toHaveLength(2);
    expect(marks.map((m) => m.textContent)).toEqual(["abcdef", "ghij"]);
  });

  it("silently ignores a detection whose block_id matches no block", () => {
    const blocks: TextBlock[] = [{ id: "b1", text: "hello world", locator: {} }];
    const detections: Detection[] = [
      makeDetection({ id: "orphan", block_id: "does-not-exist", start_offset: 0, end_offset: 5 }),
    ];

    render(<DocumentPreview blocks={blocks} detections={detections} />);

    expect(screen.queryAllByText((_, element) => element?.tagName === "MARK")).toHaveLength(0);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("falls back gracefully for an unrecognized pii_type without crashing", () => {
    const blocks: TextBlock[] = [{ id: "b1", text: "some medical record data", locator: {} }];
    const detections: Detection[] = [
      makeDetection({ id: "d1", block_id: "b1", pii_type: "medical_record_number", start_offset: 5, end_offset: 12 }),
    ];

    expect(() => render(<DocumentPreview blocks={blocks} detections={detections} />)).not.toThrow();
    const mark = screen.getByText("medical");
    expect(mark.tagName).toBe("MARK");
    expect(mark).toHaveAttribute("title", expect.stringContaining("Medical Record Number"));
  });

  it("renders a locator badge derived from whatever locator keys are present", () => {
    const blocks: TextBlock[] = [
      { id: "b1", text: "sheet cell", locator: { sheet: "Sheet1", cell: "B7" } },
      { id: "b2", text: "pdf text", locator: { page: 2 } },
      { id: "b3", text: "docx text", locator: { paragraph: 12 } },
      { id: "b4", text: "json leaf", locator: { path: ["contacts", 0, "phone"] } },
    ];

    render(<DocumentPreview blocks={blocks} detections={[]} />);

    expect(screen.getByText("Sheet1!B7")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(screen.getByText("Paragraph 12")).toBeInTheDocument();
    expect(screen.getByText("contacts[0].phone")).toBeInTheDocument();
  });

  it("shows exactly the distinct pii_types present in the legend", () => {
    const blocks: TextBlock[] = [{ id: "b1", text: "a b c", locator: {} }];
    const detections: Detection[] = [
      makeDetection({ id: "d1", block_id: "b1", pii_type: "email", start_offset: 0, end_offset: 1 }),
      makeDetection({ id: "d2", block_id: "b1", pii_type: "email", start_offset: 2, end_offset: 3 }),
      makeDetection({ id: "d3", block_id: "b1", pii_type: "ssn", start_offset: 4, end_offset: 5 }),
    ];

    render(<DocumentPreview blocks={blocks} detections={detections} />);

    const legend = screen.getByRole("list", { name: "PII type legend" });
    expect(legend).toHaveTextContent("Email");
    expect(legend).toHaveTextContent("SSN");
    expect(legend.querySelectorAll("li")).toHaveLength(2);
  });
});
