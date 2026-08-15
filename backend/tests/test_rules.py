import pytest

from app.rules import AnswerFormatError, diagnose_diagnostic_answer, parse_integer_list, parse_range_parameters


def test_different_answers_produce_different_diagnoses():
    assert diagnose_diagnostic_answer([2, 5, 8, 10])[0] == "STOP_VALUE_INCLUDED"
    assert diagnose_diagnostic_answer([0, 3, 6, 9])[0] == "START_VALUE_IGNORED"
    assert diagnose_diagnostic_answer([2, 3, 4])[0] == "STEP_MISUNDERSTOOD"


def test_parser_rejects_non_integer_list():
    with pytest.raises(AnswerFormatError):
        parse_integer_list("[2, '5', 8]")


def test_transfer_accepts_equivalent_stop_values():
    assert parse_range_parameters("range(1, 11, 3)")[1] == [1, 4, 7, 10]
    assert parse_range_parameters("(1, 13, 3)")[1] == [1, 4, 7, 10]

