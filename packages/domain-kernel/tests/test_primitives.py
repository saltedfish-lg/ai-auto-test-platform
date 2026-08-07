from datetime import UTC

import pytest
from platform_domain import InvariantViolation, NonBlankText, SystemClock, UuidGenerator


def test_non_blank_text_is_immutable_and_normalized() -> None:
    value = NonBlankText("  platform  ")

    assert value.value == "platform"


def test_non_blank_text_rejects_missing_content() -> None:
    with pytest.raises(InvariantViolation, match="must not be blank"):
        NonBlankText("  ")


def test_clock_and_id_generator_produce_valid_values() -> None:
    assert SystemClock().now().tzinfo is UTC
    assert len(UuidGenerator().new_id()) == 36
