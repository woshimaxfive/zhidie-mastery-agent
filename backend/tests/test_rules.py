import pytest

from app.rules import (
    AnswerFormatError,
    diagnostic_hint,
    diagnose_diagnostic_answer,
    next_transfer_variant_id,
    parse_integer_list,
    parse_range_parameters,
    transfer_hint,
    transfer_variant,
)


def test_different_answers_produce_different_diagnoses():
    assert diagnose_diagnostic_answer([2, 5, 8, 10])[0] == "STOP_VALUE_INCLUDED"
    assert diagnose_diagnostic_answer([0, 3, 6, 9])[0] == "START_VALUE_IGNORED"
    assert diagnose_diagnostic_answer([2, 3, 4])[0] == "STEP_MISUNDERSTOOD"


def test_different_diagnoses_produce_different_progressive_hints():
    stop_hint = diagnostic_hint("STOP_VALUE_INCLUDED", 1)
    start_hint = diagnostic_hint("START_VALUE_IGNORED", 1)
    step_hint = diagnostic_hint("STEP_MISUNDERSTOOD", 1)
    assert len({stop_hint, start_hint, step_hint}) == 3
    assert "停止值" in stop_hint
    assert "第一项" in start_hint
    assert "第三个参数" in step_hint


def test_transfer_variants_rotate_and_remain_executable():
    next_id = next_transfer_variant_id("range-transfer-01")
    assert next_id == "range-transfer-02"
    variant = transfer_variant(next_id)
    assert list(variant.target_sequence) == [3, 7, 11, 15]
    assert parse_range_parameters("range(3, 16, 4)")[1] == list(variant.target_sequence)
    assert "15" in transfer_hint(variant.target_sequence, 2)
    assert "10" not in transfer_hint(variant.target_sequence, 2)


def test_parser_rejects_non_integer_list():
    with pytest.raises(AnswerFormatError):
        parse_integer_list("[2, '5', 8]")


def test_transfer_accepts_equivalent_stop_values():
    assert parse_range_parameters("range(1, 11, 3)")[1] == [1, 4, 7, 10]
    assert parse_range_parameters("(1, 13, 3)")[1] == [1, 4, 7, 10]


def test_transfer_rejects_large_range_before_list_allocation():
    with pytest.raises(AnswerFormatError, match="生成序列过长"):
        parse_range_parameters("range(0, 1000000000, 1)")


def test_transfer_rejects_range_longer_than_platform_size():
    with pytest.raises(AnswerFormatError, match="生成序列过长"):
        parse_range_parameters("range(0, 9223372036854775808, 1)")
