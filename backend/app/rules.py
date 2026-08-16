from __future__ import annotations

import ast
import re
from dataclasses import dataclass


DIAGNOSTIC_EXPECTED = [2, 5, 8]


@dataclass(frozen=True)
class TransferVariant:
    id: str
    target_sequence: tuple[int, ...]


TRANSFER_VARIANTS = (
    TransferVariant("range-transfer-01", (1, 4, 7, 10)),
    TransferVariant("range-transfer-02", (3, 7, 11, 15)),
    TransferVariant("range-transfer-03", (-2, 1, 4, 7)),
    TransferVariant("range-transfer-04", (10, 7, 4, 1)),
    TransferVariant("range-transfer-05", (2, 6, 10)),
)
DEFAULT_TRANSFER_VARIANT_ID = TRANSFER_VARIANTS[0].id
TRANSFER_EXPECTED = list(TRANSFER_VARIANTS[0].target_sequence)


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
    generated_range = range(*params)
    try:
        generated_length = len(generated_range)
    except OverflowError as exc:
        raise AnswerFormatError("生成序列过长，请检查停止值和步长。") from exc
    if generated_length > 100:
        raise AnswerFormatError("生成序列过长，请检查停止值和步长。")
    generated = list(generated_range)
    return params, generated


DEFAULT_DIAGNOSTIC_HINTS = {
    1: "先判断停止值本身是否会被包含。",
    2: "从起始值 2 开始，每次增加 3，并在到达停止边界前停下。",
    3: "依次检查 2、2+3、再加 3；下一次增加前先和停止值 10 比较。",
}

DIAGNOSTIC_HINTS_BY_CODE = {
    "STOP_VALUE_INCLUDED": {
        1: "先单独判断：range() 的停止值本身会不会进入序列？",
        2: "每次准备加入新值时，都要先确认它仍在停止边界以内。",
        3: "从 2 开始反复增加 3；当下一项到达或越过 10 时就停止。",
    },
    "START_VALUE_IGNORED": {
        1: "先确认三个参数中，哪一个决定序列的第一项。",
        2: "range(start, stop, step) 会从 start 指定的值开始，而不是默认从 0 开始。",
        3: "把第一个参数 2 直接写成首项，再从它开始按步长向后推。",
    },
    "STEP_MISUNDERSTOOD": {
        1: "观察第三个参数，它决定相邻两项之间相差多少。",
        2: "这里的步长是 3，得到一项后应增加 3，而不是增加 1。",
        3: "从起始值 2 开始，每次只做一次“当前值 + 3”，同时检查停止边界。",
    },
    "STOP_BOUNDARY_MISUNDERSTOOD": {
        1: "计算出下一项后，先判断它是否仍满足停止边界。",
        2: "停止值不是必须命中的终点；下一项越过停止值时也应停止。",
        3: "逐项增加 3，并只保留严格小于停止值 10 的结果。",
    },
    "SEQUENCE_MISMATCH": DEFAULT_DIAGNOSTIC_HINTS,
}

def diagnostic_hint(diagnosis_code: str | None, level: int) -> str:
    hints = DIAGNOSTIC_HINTS_BY_CODE.get(diagnosis_code, DEFAULT_DIAGNOSTIC_HINTS)
    return hints[level]


def transfer_hint(target_sequence: list[int] | tuple[int, ...], level: int) -> str:
    if level == 1:
        return "先从目标序列中相邻两项的差确定步长。"
    if level == 2:
        return (
            f"起始值是第一项；停止值必须让末项 {target_sequence[-1]} 被生成，"
            "但不能让下一项出现。"
        )
    return "把 start、stop、step 分别对应到第一项、停止边界和相邻项差，再执行检查。"


def transfer_variant(variant_id: str | None) -> TransferVariant:
    for variant in TRANSFER_VARIANTS:
        if variant.id == variant_id:
            return variant
    return TRANSFER_VARIANTS[0]


def next_transfer_variant_id(previous_variant_id: str | None) -> str:
    current = transfer_variant(previous_variant_id)
    current_index = TRANSFER_VARIANTS.index(current)
    return TRANSFER_VARIANTS[(current_index + 1) % len(TRANSFER_VARIANTS)].id
