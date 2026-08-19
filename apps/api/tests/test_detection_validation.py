from src.agents.detection_validation import validate_and_merge
from src.models.block import TextBlock
from src.models.detection import RawDetection
from src.models.locator import CsvLocator


def _block(id_: str, text: str) -> TextBlock:
    return TextBlock(id=id_, text=text, locator=CsvLocator(row=0, column=0))


def test_exact_match_accepted():
    text = "email me at a@b.com please"
    block = _block("b1", text)
    start = text.index("a@b.com")
    end = start + len("a@b.com")
    raw = RawDetection(
        block_id="b1",
        matched_text="a@b.com",
        pii_type="email",
        start_offset=start,
        end_offset=end,
        confidence=0.95,
    )

    detections = validate_and_merge([raw], [block], job_id="job1")

    assert len(detections) == 1
    d = detections[0]
    assert d.id == "d1"
    assert d.value == "a@b.com"
    assert d.start_offset == start
    assert d.end_offset == end


def test_reanchor_on_offset_drift():
    text = "prefix a@b.com suffix"
    block = _block("b1", text)
    # Claimed offsets are wrong (drifted), but matched_text is correct and
    # unique in the block -- should be re-anchored to the real position.
    raw = RawDetection(
        block_id="b1",
        matched_text="a@b.com",
        pii_type="email",
        start_offset=0,
        end_offset=7,
        confidence=0.9,
    )

    detections = validate_and_merge([raw], [block], job_id="job1")

    assert len(detections) == 1
    real_start = text.index("a@b.com")
    assert detections[0].start_offset == real_start
    assert detections[0].end_offset == real_start + len("a@b.com")


def test_unresolvable_detection_is_dropped():
    text = "nothing to see here"
    block = _block("b1", text)
    raw = RawDetection(
        block_id="b1",
        matched_text="totally-not-present@example.com",
        pii_type="email",
        start_offset=0,
        end_offset=5,
        confidence=0.5,
    )

    detections = validate_and_merge([raw], [block], job_id="job1")

    assert detections == []


def test_unknown_pii_type_dropped():
    text = "some text with a@b.com"
    block = _block("b1", text)
    raw = RawDetection(
        block_id="b1",
        matched_text="a@b.com",
        pii_type="not_a_real_category",
        start_offset=text.index("a@b.com"),
        end_offset=text.index("a@b.com") + len("a@b.com"),
        confidence=0.9,
    )

    detections = validate_and_merge([raw], [block], job_id="job1")

    assert detections == []


def test_out_of_bounds_offsets_dropped():
    text = "short"
    block = _block("b1", text)
    raw = RawDetection(
        block_id="b1",
        matched_text="short",
        pii_type="name",
        start_offset=0,
        end_offset=999,
        confidence=0.9,
    )

    detections = validate_and_merge([raw], [block], job_id="job1")

    assert detections == []


def test_dedup_merge_overlapping_same_type_spans():
    text = "John Jacob Smith lives here"
    block = _block("b1", text)
    # Two overlapping "name" detections for "John Jacob" and "Jacob Smith".
    raw1 = RawDetection(
        block_id="b1",
        matched_text="John Jacob",
        pii_type="name",
        start_offset=text.index("John Jacob"),
        end_offset=text.index("John Jacob") + len("John Jacob"),
        confidence=0.8,
    )
    raw2 = RawDetection(
        block_id="b1",
        matched_text="Jacob Smith",
        pii_type="name",
        start_offset=text.index("Jacob Smith"),
        end_offset=text.index("Jacob Smith") + len("Jacob Smith"),
        confidence=0.9,
    )

    detections = validate_and_merge([raw1, raw2], [block], job_id="job1")

    assert len(detections) == 1
    merged = detections[0]
    assert merged.value == "John Jacob Smith"
    assert merged.confidence == 0.9  # max of merged
    assert merged.id == "d1"


def test_non_overlapping_same_type_spans_not_merged():
    text = "call bob@x.com or alice@y.com today"
    block = _block("b1", text)
    raw1 = RawDetection(
        block_id="b1",
        matched_text="bob@x.com",
        pii_type="email",
        start_offset=text.index("bob@x.com"),
        end_offset=text.index("bob@x.com") + len("bob@x.com"),
        confidence=0.7,
    )
    raw2 = RawDetection(
        block_id="b1",
        matched_text="alice@y.com",
        pii_type="email",
        start_offset=text.index("alice@y.com"),
        end_offset=text.index("alice@y.com") + len("alice@y.com"),
        confidence=0.8,
    )

    detections = validate_and_merge([raw1, raw2], [block], job_id="job1")

    assert len(detections) == 2
    assert {d.value for d in detections} == {"bob@x.com", "alice@y.com"}
