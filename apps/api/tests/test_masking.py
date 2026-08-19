from src.agents.masking import apply_masks, mask
from src.models.detection import Detection


def test_mask_is_length_preserving():
    text = "call 555-010-1234 now"
    start, end = text.index("555-010-1234"), text.index("555-010-1234") + len(
        "555-010-1234"
    )
    masked = mask(text, start, end)
    assert len(masked) == len(text)
    assert masked == "call XXXXXXXXXXXX now"
    assert masked[:start] == text[:start]
    assert masked[end:] == text[end:]


def test_mask_untouched_content_outside_span():
    text = "prefix-SECRET-suffix"
    start, end = text.index("SECRET"), text.index("SECRET") + len("SECRET")
    masked = mask(text, start, end)
    assert masked.startswith("prefix-")
    assert masked.endswith("-suffix")
    assert "SECRET" not in masked


def test_apply_masks_order_independent_for_non_overlapping_spans():
    text = "email a@b.com phone 555-1234 end"
    d1 = Detection(
        id="d1",
        block_id="b",
        pii_type="email",
        value="a@b.com",
        start_offset=text.index("a@b.com"),
        end_offset=text.index("a@b.com") + len("a@b.com"),
        confidence=0.9,
    )
    d2 = Detection(
        id="d2",
        block_id="b",
        pii_type="phone",
        value="555-1234",
        start_offset=text.index("555-1234"),
        end_offset=text.index("555-1234") + len("555-1234"),
        confidence=0.9,
    )

    forward = apply_masks(text, [d1, d2])
    backward = apply_masks(text, [d2, d1])

    assert forward == backward
    assert len(forward) == len(text)
    assert "a@b.com" not in forward
    assert "555-1234" not in forward
    assert forward.startswith("email ")
    assert forward.endswith(" end")
