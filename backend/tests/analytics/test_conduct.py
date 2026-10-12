from app.analytics.conduct import PeriodConduct, conduct_for_period, year_comment_result
from app.core.enums import CommentResult, ConductLevel, ConductPeriod

HK1, HK2, YEAR = ConductPeriod.HK1, ConductPeriod.HK2, ConductPeriod.YEAR


def test_semester_conduct_is_read_directly() -> None:
    records = {HK1: ConductLevel.GOOD, HK2: ConductLevel.FAIR}

    assert conduct_for_period(records, HK1) == PeriodConduct(ConductLevel.GOOD)
    assert conduct_for_period(records, HK2) == PeriodConduct(ConductLevel.FAIR)
    assert conduct_for_period({HK1: ConductLevel.GOOD}, HK2) == PeriodConduct(None)


def test_year_conduct_prefers_the_recorded_year_result() -> None:
    records = {HK1: ConductLevel.GOOD, HK2: ConductLevel.FAIR, YEAR: ConductLevel.PASS}

    assert conduct_for_period(records, YEAR) == PeriodConduct(ConductLevel.PASS, derived=False)


def test_year_conduct_falls_back_to_semester_2_and_is_marked_derived() -> None:
    records = {HK1: ConductLevel.GOOD, HK2: ConductLevel.FAIR}

    assert conduct_for_period(records, YEAR) == PeriodConduct(ConductLevel.FAIR, derived=True)


def test_year_conduct_is_unknown_without_semester_2_or_year() -> None:
    assert conduct_for_period({HK1: ConductLevel.GOOD}, YEAR) == PeriodConduct(None)
    assert conduct_for_period({}, YEAR) == PeriodConduct(None)


def test_comment_subject_year_result_is_semester_2_result() -> None:
    assert year_comment_result(CommentResult.PASS) is CommentResult.PASS
    assert year_comment_result(CommentResult.FAIL) is CommentResult.FAIL
    assert year_comment_result(None) is None
