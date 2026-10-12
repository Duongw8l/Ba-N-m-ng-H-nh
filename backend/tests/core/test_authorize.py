"""Ma trận phân quyền của authorize() trên dữ liệu seed mặc định (D-040).

Tài khoản (xem README): gv.dia.10 dạy Địa lí chỉ ở 10A1 (đúng khối, sai lớp ở 10A2 và 10A3);
gv.van.10 dạy Văn ở cả 3 lớp 10; gvcn.10a2 chỉ chủ nhiệm 10A2; gv.toan.10 chủ nhiệm 10A1 và dạy
Toán ở 10A1, 10A2, 10A3 (quyền cộng dồn); bgh1 là BGH; admin là Admin.
"""

from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.authorize import Access, AuthorizationError, authorize
from app.core.enums import UserRole

pytestmark = pytest.mark.db

NO_SUCH_CLASS = 999_999


@pytest.fixture
def user_of(db_session: Session) -> Callable[[str], User]:
    def find(email: str) -> User:
        user = db_session.scalar(select(User).where(func.lower(User.email) == email))
        assert user is not None, email
        return user

    return find


def denied(session: Session, user: User, **scope: int) -> bool:
    try:
        authorize(session, user, **scope)
    except AuthorizationError:
        return True
    return False


# --- Admin -----------------------------------------------------------------------------------


def test_admin_is_denied_everything(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    admin = user_of("admin@example.com")

    assert denied(db_session, admin, class_id=class_id_of("10A1"))
    assert denied(db_session, admin, class_id=class_id_of("12A3"))
    assert denied(db_session, admin, class_id=class_id_of("10A1"), subject_id=subject_id_of("Toán"))
    assert denied(db_session, admin, grade_level=10)
    assert denied(db_session, admin, class_id=NO_SUCH_CLASS)


# --- BGH -------------------------------------------------------------------------------------


def test_principal_may_see_every_class_subject_and_grade_including_guardian(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    principal = user_of("bgh1@example.com")

    for name in ("10A1", "11A2", "12A3"):
        access = authorize(db_session, principal, class_id=class_id_of(name))
        assert access == Access(UserRole.PRINCIPAL, class_id_of(name), False, None, True)
    assert authorize(
        db_session, principal, class_id=class_id_of("11A2"), subject_id=subject_id_of("Vật lí")
    ).allows_subject(subject_id_of("Vật lí"))
    for grade in (10, 11, 12):
        assert authorize(db_session, principal, grade_level=grade).can_view_guardian


# --- GVCN thuần ------------------------------------------------------------------------------


def test_homeroom_teacher_sees_every_subject_and_guardian_of_own_class_only(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    teacher = user_of("gvcn.10a2@example.com")
    own = class_id_of("10A2")

    access = authorize(db_session, teacher, class_id=own)
    assert (access.is_homeroom, access.subject_ids, access.can_view_guardian) == (True, None, True)
    for subject in ("Toán", "Ngữ văn", "Vật lí", "Âm nhạc"):  # mọi môn của lớp mình
        authorize(db_session, teacher, class_id=own, subject_id=subject_id_of(subject))

    assert denied(db_session, teacher, class_id=class_id_of("10A1"))  # cùng khối, khác lớp
    assert denied(db_session, teacher, class_id=class_id_of("10A3"))
    assert denied(db_session, teacher, class_id=class_id_of("11A2"))
    assert denied(
        db_session, teacher, class_id=class_id_of("10A1"), subject_id=subject_id_of("Toán")
    )
    assert denied(db_session, teacher, grade_level=10)  # dữ liệu cấp khối chỉ BGH
    assert denied(db_session, teacher, class_id=NO_SUCH_CLASS)


# --- GVBM ------------------------------------------------------------------------------------


def test_subject_teacher_is_limited_to_assigned_class_and_subject_without_guardian(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    teacher = user_of("gv.dia.10@example.com")
    geography = subject_id_of("Địa lí")

    access = authorize(db_session, teacher, class_id=class_id_of("10A1"))
    assert access == Access(
        UserRole.TEACHER, class_id_of("10A1"), False, frozenset({geography}), False
    )
    authorize(db_session, teacher, class_id=class_id_of("10A1"), subject_id=geography)

    # Đúng lớp, sai môn.
    assert denied(
        db_session, teacher, class_id=class_id_of("10A1"), subject_id=subject_id_of("Toán")
    )
    # Đúng môn, sai lớp (cùng khối 10 nhưng 10A2 và 10A3 không học Địa lí).
    assert denied(db_session, teacher, class_id=class_id_of("10A2"), subject_id=geography)
    assert denied(db_session, teacher, class_id=class_id_of("10A2"))
    assert denied(db_session, teacher, class_id=class_id_of("10A3"))
    # Sai khối.
    assert denied(db_session, teacher, class_id=class_id_of("11A1"))
    assert denied(db_session, teacher, grade_level=10)
    assert denied(db_session, teacher, class_id=NO_SUCH_CLASS)


def test_subject_teacher_of_several_classes_gets_each_of_them(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    teacher = user_of("gv.van.10@example.com")
    literature = subject_id_of("Ngữ văn")

    for name in ("10A1", "10A2", "10A3"):
        access = authorize(db_session, teacher, class_id=class_id_of(name))
        assert access.subject_ids == frozenset({literature})
        assert not access.can_view_guardian
    assert denied(db_session, teacher, class_id=class_id_of("11A1"))
    assert denied(
        db_session, teacher, class_id=class_id_of("10A2"), subject_id=subject_id_of("Toán")
    )


# --- Quyền cộng dồn --------------------------------------------------------------------------


def test_permissions_add_up_per_class_for_a_homeroom_teacher_who_also_teaches(
    db_session: Session,
    user_of: Callable[[str], User],
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    teacher = user_of("gv.toan.10@example.com")
    math, literature = subject_id_of("Toán"), subject_id_of("Ngữ văn")

    # Lớp chủ nhiệm 10A1: mọi môn và phụ huynh.
    homeroom = authorize(db_session, teacher, class_id=class_id_of("10A1"), subject_id=literature)
    assert (homeroom.is_homeroom, homeroom.subject_ids, homeroom.can_view_guardian) == (
        True,
        None,
        True,
    )

    # Lớp chỉ dạy Toán (10A2, 10A3): đúng môn Toán, không phụ huynh, không môn khác.
    for name in ("10A2", "10A3"):
        access = authorize(db_session, teacher, class_id=class_id_of(name), subject_id=math)
        assert (access.is_homeroom, access.subject_ids, access.can_view_guardian) == (
            False,
            frozenset({math}),
            False,
        )
        assert denied(db_session, teacher, class_id=class_id_of(name), subject_id=literature)

    # Khối khác: không có quyền gì (gv.toan.11 mới là GVCN 11A1).
    assert denied(db_session, teacher, class_id=class_id_of("11A1"))
    assert denied(db_session, teacher, grade_level=10)


# --- Dữ liệu cả lớp (mọi môn) --------------------------------------------------------------------


def test_require_all_subjects_passes_for_homeroom_and_principal_but_not_subject_teachers(
    db_session: Session, user_of: Callable[[str], User], class_id_of: Callable[[str], int]
) -> None:
    ten_a1 = class_id_of("10A1")

    # BGH và GVCN của lớp: mọi môn
    authorize(db_session, user_of("bgh1@example.com"), class_id=ten_a1).require_all_subjects()
    authorize(db_session, user_of("gv.toan.10@example.com"), class_id=ten_a1).require_all_subjects()
    # GVBM (Văn ở 10A1) và người cộng dồn khi ở lớp chỉ dạy Toán (10A2): không phải mọi môn
    with pytest.raises(AuthorizationError):
        authorize(
            db_session, user_of("gv.van.10@example.com"), class_id=ten_a1
        ).require_all_subjects()
    with pytest.raises(AuthorizationError):
        authorize(
            db_session, user_of("gv.toan.10@example.com"), class_id=class_id_of("10A2")
        ).require_all_subjects()


# --- Gọi sai -----------------------------------------------------------------------------------


def test_programming_errors_raise_value_error_not_a_silent_deny_or_allow(
    db_session: Session, user_of: Callable[[str], User], class_id_of: Callable[[str], int]
) -> None:
    principal = user_of("bgh1@example.com")

    with pytest.raises(ValueError, match="class_id"):
        authorize(db_session, principal, subject_id=1)  # môn mà không có lớp
    with pytest.raises(ValueError, match="đúng một"):
        authorize(db_session, principal)  # không chỉ phạm vi nào
    with pytest.raises(ValueError, match="đúng một"):
        authorize(db_session, principal, class_id=class_id_of("10A1"), grade_level=10)
