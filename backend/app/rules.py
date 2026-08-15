from __future__ import annotations

import ast
import re


DIAGNOSTIC_EXPECTED = [2, 5, 8]
TRANSFER_EXPECTED = [1, 4, 7, 10]


class AnswerFormatError(ValueError):
    pass


def parse_integer_list(raw: str) -> list[int]:
    try:
        value = ast.literal_eval(raw.strip())
    except (ValueError, SyntaxError) as exc:
        raise AnswerFormatError("请输入类似 [2, 5, 8] 的整数列表。") from exc
    if not isinstance(value, (list, tuple)) or not value:
        raise AnswerFormatError("请输入非空整数列表，例如 [2, 5, 8]。")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise AnswerFormatError("列表中只能包含整数。")
    if len(value) > 20:
        raise AnswerFormatError("列表过长，请只填写题目生成的序列。")
    return list(value)


def diagnose_diagnostic_answer(answer: list[int]) -> tuple[str | None, str]:
    if answer == DIAGNOSTIC_EXPECTED:
        return None, "序列正确，下一步用迁移任务验证你能否独立应用规则。"
    if answer == [2, 5, 8, 10]:
        return "STOP_VALUE_INCLUDED", "你把停止值 10 也包含进结果了。"
    if answer and answer[0] == 0:
        return "START_VALUE_IGNORED", "你似乎忽略了起始值 2。"
    if len(answer) >= 2 and answer[0] == 2 and answer[1] == 3:
        return "STEP_MISUNDERSTOOD", "你把步长 3 理解成了每次增加 1。"
    if answer == [2, 5, 8, 11]:
        return "STOP_BOUNDARY_MISUNDERSTOOD", "步长计算正确，但序列越过停止边界后仍继续了。"
    return "SEQUENCE_MISMATCH", "当前序列与参数的执行过程不一致。"


def parse_range_parameters(raw: str) -> tuple[list[int], list[int]]:
    text = raw.strip()
    match = re.fullmatch(r"(?:range\s*\()?\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)?", text)
    if not match:
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise AnswerFormatError("请输入三个整数参数，例如 range(1, 11, 3)。") from exc
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise AnswerFormatError("请输入三个整数参数，例如 (1, 11, 3)。")
        params = list(value)
        if any(isinstance(item, bool) or not isinstance(item, int) for item in params):
            raise AnswerFormatError("range 参数必须是整数。")
    else:
        params = [int(group) for group in match.groups()]
    if params[2] == 0:
        raise AnswerFormatError("步长不能为 0。")
    generated = list(range(*params))
    if len(generated) > 100:
        raise AnswerFormatError("生成序列过长，请检查停止值和步长。")
    return params, generated


DIAGNOSTIC_HINTS = {
    1: "先判断停止值本身是否会被包含。",
    2: "从起始值 2 开始，每次增加 3，并在到达停止边界前停下。",
    3: "依次检查 2、2+3、再加 3；下一次增加前先和停止值 10 比较。",
}

TRANSFER_HINTS = {
    1: "先从相邻两项的差确定步长。",
    2: "起始值是第一项；停止值必须让 10 被生成，但不能让下一项出现。",
    3: "把 start、stop、step 分别对应到第一项、停止边界和相邻项差，再检查实际序列。",
}

