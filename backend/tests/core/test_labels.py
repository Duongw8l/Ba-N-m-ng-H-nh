import enum

import pytest

from app.core import enums
from app.core.enums import CommentResult, ConductLevel
from app.core.labels import LABELS_VI, label_vi

ALL_ENUMS = [
    obj
    for obj in vars(enums).values()
    if isinstance(obj, type) and issubclass(obj, enum.StrEnum) and obj is not enum.StrEnum
]


@pytest.mark.parametrize("enum_cls", ALL_ENUMS, ids=lambda cls: cls.__name__)
def test_every_enum_member_has_a_vietnamese_label(enum_cls: type[enum.StrEnum]) -> None:
    labels = LABELS_VI[enum_cls]

    assert set(labels) == set(enum_cls)
    assert all(text.strip() for text in labels.values())


def test_enums_with_same_value_do_not_share_labels() -> None:
    # CommentResult.PASS == ConductLevel.PASS == "pass" vì StrEnum so sánh theo chuỗi,
    # nên nhãn phải tra theo lớp enum.
    assert label_vi(CommentResult.PASS) == "Đạt"
    assert label_vi(ConductLevel.GOOD) == "Tốt"
    assert label_vi(ConductLevel.PASS) == "Đạt"
    assert label_vi(ConductLevel.FAIL) == "Chưa đạt"
