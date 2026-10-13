"""Sinh nhận xét cả lớp chạy nền (D-104): tiến độ, bỏ qua em đã có, dừng khi lỗi LLM rồi tiếp tục.

Runner giả (`job_queue`) nhận việc nhưng chỉ chạy khi test gọi `run()`, nên test xem được cả trạng
thái "đang chạy" lẫn "đã xong". Luồng thật (`start_in_thread`) chỉ là vỏ mỏng quanh `run_job`.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.analytics import repository as repo
from app.assistant.llm import LLMError, LLMNotConfigured, LLMReply, Message, ToolSpec
from app.auth.models import AuditLog, User
from app.classes.models import SchoolClass
from app.core.enums import AuditAction, ReportJobStatus, ReportStatus
from app.reports import facts as report_facts
from app.reports.models import Report, ReportJob
from tests.reports.conftest import FakeWriter, JobQueue

pytestmark = pytest.mark.db

GVCN_11A2 = "gvcn.11a2@example.com"
GVCN_11A1 = "gv.toan.11@example.com"  # chủ nhiệm 11A1, dạy Toán khối 11
GVBM_VAN_11 = "gv.van.11@example.com"
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"

REPORTS = "/api/v1/reports"
Headers = Callable[[str], dict[str, str]]
UseLlm = Callable[..., None]
CLASS_SIZE = 40


class FlakyWriter(FakeWriter):
    """Như FakeWriter nhưng ném LLMError ở lần gọi thứ `fail_on` (tính từ 1)."""

    def __init__(self, fail_on: int) -> None:
        super().__init__()
        self.fail_on = fail_on

    def chat(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMReply:
        if len(self.calls) + 1 == self.fail_on:
            self.calls.append(list(messages))
            raise LLMError("hết hạn mức")
        return super().chat(messages, tools)


def class_body(class_id: int, **extra: Any) -> dict[str, Any]:
    return {"type": "contact_slip", "semester": "1", "class_id": class_id, **extra}


@pytest.fixture
def start(
    api_client: TestClient,
    auth_headers: Headers,
    class_id_of: Callable[[str], int],
    use_llm: UseLlm,
) -> Callable[..., Any]:
    """Bấm "Sinh cả lớp" 11A2 bằng tài khoản `email` (mặc định GVCN 11A2)."""

    def post(email: str = GVCN_11A2, **extra: Any) -> Any:
        return api_client.post(
            REPORTS, json=class_body(class_id_of("11A2"), **extra), headers=auth_headers(email)
        )

    return post


def drafts(db_session: Session) -> list[Report]:
    return list(db_session.scalars(select(Report).order_by(Report.id)))


# --- Chạy trọn một lớp ------------------------------------------------------------------------


def test_the_whole_class_is_accepted_with_202_then_written_in_batches_of_five(
    db_session: Session, start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    response = start()

    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "running" and job["total"] == CLASS_SIZE and job["done"] == 0
    assert job["status_label"] == "Đang chạy"
    assert len(job_queue.pending) == 1 and writer.calls == []  # chưa chạy gì
    assert drafts(db_session) == []

    assert job_queue.run() == 1
    assert len(writer.calls) == CLASS_SIZE // 5  # 8 lần gọi cho 40 em
    reports = drafts(db_session)
    assert len(reports) == CLASS_SIZE
    assert all(r.status is ReportStatus.DRAFT and r.approved_by is None for r in reports)
    assert all(not r.needs_manual and r.draft_text for r in reports)

    finished = db_session.get(ReportJob, job["id"])
    assert finished is not None
    assert finished.status is ReportJobStatus.DONE and finished.finished_at is not None
    assert (finished.total, finished.done, finished.needs_manual) == (CLASS_SIZE, CLASS_SIZE, 0)


def test_progress_is_visible_through_the_job_endpoint(
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
) -> None:
    use_llm(FakeWriter())
    job_id = start().json()["id"]
    url = f"{REPORTS}/jobs/{job_id}"
    before = api_client.get(url, headers=auth_headers(GVCN_11A2)).json()
    assert before["status"] == "running" and before["done"] == 0

    job_queue.run()
    after = api_client.get(url, headers=auth_headers(GVCN_11A2)).json()
    assert after["status"] == "done" and after["done"] == CLASS_SIZE


def test_nothing_identifying_reaches_the_llm_when_writing_a_whole_class(
    db_session: Session,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    start()
    job_queue.run()

    sent = writer.sent()
    for student in repo.class_students(db_session, class_id_of("11A2")):
        assert student.full_name.casefold() not in sent
        assert student.student_code.casefold() not in sent
        guardian_name, guardian_phone = repo.student_guardian(db_session, student.student_id)
        assert not guardian_name or guardian_name.casefold() not in sent
        assert not guardian_phone or guardian_phone not in sent
    for key in ("date_of_birth", "guardian_name", "full_name"):
        assert key not in sent


def test_students_with_failing_text_are_counted_and_left_for_the_teacher(
    db_session: Session, start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    # HS_03 của mỗi nhóm 5 em luôn bị viết bằng từ cấm: 8 em cần giáo viên tự viết.
    writer = FakeWriter(bad={"HS_03"})
    use_llm(writer)
    job_id = start().json()["id"]
    job_queue.run()

    job = db_session.get(ReportJob, job_id)
    assert job is not None and job.status is ReportJobStatus.DONE
    assert (job.done, job.needs_manual) == (CLASS_SIZE, 8)
    manual = [r for r in drafts(db_session) if r.needs_manual]
    assert len(manual) == 8 and all(r.draft_text == "" for r in manual)
    assert len(writer.calls) == 8 + 8 * 2  # 8 nhóm, cộng 2 lần viết lại cho mỗi em lỗi


# --- Bỏ qua bản đã có, dừng và tiếp tục -------------------------------------------------------


def test_students_who_already_have_a_text_are_skipped_and_never_overwritten(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
    student_id_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter())
    headers = auth_headers(GVCN_11A2)
    an = student_id_of("HS1102001")
    first = api_client.post(
        REPORTS, json=class_body(class_id_of("11A2"), student_id=an), headers=headers
    ).json()
    edited = "Em học tập nghiêm túc, chăm chỉ và luôn hợp tác tốt với các thầy cô giáo trong lớp."
    api_client.put(
        f"{REPORTS}/{first['id']}", json={"text": edited, "approve": True}, headers=headers
    )

    job = start().json()
    assert job["total"] == CLASS_SIZE - 1
    job_queue.run()

    reports = drafts(db_session)
    assert len(reports) == CLASS_SIZE
    kept = db_session.get(Report, first["id"])
    assert kept is not None and kept.status is ReportStatus.APPROVED and kept.final_text == edited


def test_a_draft_the_teacher_already_edited_is_not_overwritten_by_the_job(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
    student_id_of: Callable[[str], int],
) -> None:
    use_llm(FakeWriter())
    headers = auth_headers(GVCN_11A2)
    first = api_client.post(
        REPORTS,
        json=class_body(class_id_of("11A2"), student_id=student_id_of("HS1102001")),
        headers=headers,
    ).json()
    mine = "Em học tập nghiêm túc, chăm chỉ và luôn hợp tác tốt với các thầy cô giáo trong lớp."
    api_client.put(f"{REPORTS}/{first['id']}", json={"text": mine}, headers=headers)  # chưa duyệt

    assert start().json()["total"] == CLASS_SIZE - 1
    job_queue.run()

    kept = db_session.get(Report, first["id"])
    assert kept is not None and kept.draft_text == mine and kept.status is ReportStatus.DRAFT
    assert len(drafts(db_session)) == CLASS_SIZE


def test_the_job_stops_when_the_teacher_is_no_longer_the_class_teacher(
    db_session: Session,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    job_id = start().json()["id"]
    # Trong lúc job đang chờ, Admin gỡ giáo viên khỏi vai trò chủ nhiệm lớp.
    db_session.execute(
        update(SchoolClass)
        .where(SchoolClass.id == class_id_of("11A2"))
        .values(homeroom_teacher_id=None)
    )
    db_session.commit()
    job_queue.run()

    job = db_session.get(ReportJob, job_id)
    assert job is not None
    assert job.status is ReportJobStatus.STOPPED and job.error_code == "forbidden"
    assert writer.calls == [] and drafts(db_session) == []


def test_an_llm_error_stops_the_job_keeps_what_was_written_and_a_second_run_finishes_it(
    db_session: Session, start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    use_llm(FlakyWriter(fail_on=3))  # hai nhóm đầu (10 em) xong, nhóm thứ ba gặp lỗi
    first = start().json()
    job_queue.run()

    stopped = db_session.get(ReportJob, first["id"])
    assert stopped is not None
    assert stopped.status is ReportJobStatus.STOPPED and stopped.error_code == "llm_error"
    assert (stopped.total, stopped.done) == (CLASS_SIZE, 10)
    written = {r.id: r.draft_text for r in drafts(db_session)}
    assert len(written) == 10

    use_llm(FakeWriter())  # hết lỗi: bấm lại, chỉ viết 30 em còn thiếu
    second = start()
    assert second.status_code == 202 and second.json()["id"] != first["id"]
    assert second.json()["total"] == CLASS_SIZE - 10
    job_queue.run()

    after = drafts(db_session)
    assert len(after) == CLASS_SIZE
    assert {r.id: r.draft_text for r in after if r.id in written} == written  # 10 em đầu giữ nguyên


def test_pressing_the_button_twice_gives_back_the_running_job(
    start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    use_llm(FakeWriter())
    first = start().json()
    second = start()
    assert second.status_code == 202 and second.json()["id"] == first["id"]
    assert len(job_queue.pending) == 1  # không chạy hai luồng cho cùng một lớp
    job_queue.run()


def test_a_class_that_is_already_complete_creates_a_finished_job_and_runs_nothing(
    start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    use_llm(FakeWriter())
    start()
    job_queue.run()
    again = start()
    assert again.status_code == 202
    assert again.json()["status"] == "done" and again.json()["total"] == 0
    assert job_queue.pending == []


def test_a_job_whose_thread_vanished_is_reported_as_stopped(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
) -> None:
    use_llm(FakeWriter())
    job_id = start().json()["id"]
    job = db_session.get(ReportJob, job_id)
    assert job is not None
    job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=30)  # backend khởi động lại giữa chừng
    db_session.commit()

    shown = api_client.get(f"{REPORTS}/jobs/{job_id}", headers=auth_headers(GVCN_11A2)).json()
    assert shown["status"] == "stopped" and shown["error_code"] == "interrupted"
    # Bấm lại được ngay (job cũ không còn "đang chạy").
    assert start().json()["id"] != job_id


# --- Lỗi và quyền -----------------------------------------------------------------------------


def test_an_unexpected_error_in_the_thread_marks_the_job_stopped(
    db_session: Session,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_llm(FakeWriter())
    job_id = start().json()["id"]

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("lỗi bất ngờ")

    monkeypatch.setattr(report_facts, "student_facts", boom)
    job_queue.run()  # run_job không được ném lỗi ra ngoài

    job = db_session.get(ReportJob, job_id)
    assert job is not None
    assert job.status is ReportJobStatus.STOPPED and job.error_code == "internal_error"


def test_the_job_is_rechecked_when_it_runs_so_a_locked_teacher_writes_nothing(
    db_session: Session,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    user_of: Callable[[str], User],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    job_id = start().json()["id"]
    user_of(GVCN_11A2).is_active = False  # Admin khoá tài khoản trong lúc job đang chờ
    db_session.commit()
    job_queue.run()

    job = db_session.get(ReportJob, job_id)
    assert job is not None
    assert job.status is ReportJobStatus.STOPPED and job.error_code == "forbidden"
    assert writer.calls == [] and drafts(db_session) == []


@pytest.mark.parametrize("email", [ADMIN, PRINCIPAL, GVBM_VAN_11, GVCN_11A1])
def test_only_the_class_teacher_can_start_a_whole_class_job(
    start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue, email: str
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    assert start(email).status_code == 403
    assert job_queue.pending == [] and writer.calls == []


@pytest.mark.parametrize("email", [ADMIN, PRINCIPAL, GVBM_VAN_11, GVCN_11A1])
def test_nobody_else_can_read_a_jobs_progress(
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    email: str,
) -> None:
    use_llm(FakeWriter())
    job_id = start().json()["id"]
    headers = auth_headers(email)
    assert api_client.get(f"{REPORTS}/jobs/{job_id}", headers=headers).status_code == 403
    assert api_client.get(f"{REPORTS}/jobs/999999", headers=headers).status_code == 403
    assert api_client.get(f"{REPORTS}/jobs/{job_id}").status_code == 401


def test_a_missing_llm_configuration_is_503_and_creates_no_job(
    db_session: Session, start: Callable[..., Any], use_llm: UseLlm, job_queue: JobQueue
) -> None:
    use_llm(error=LLMNotConfigured("thiếu khoá"))
    assert start().status_code == 503
    assert start(ADMIN).status_code == 403  # Admin bị chặn trước khi nói tới cấu hình
    assert db_session.scalars(select(ReportJob)).all() == []
    assert job_queue.pending == []


def test_the_job_is_audited_once_with_counts_and_no_text(
    db_session: Session,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    user_of: Callable[[str], User],
) -> None:
    use_llm(FakeWriter())
    job_id = start().json()["id"]
    job_queue.run()
    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.GENERATE_REPORT)
    ).all()
    assert len(logs) == 1
    assert logs[0].user_id == user_of(GVCN_11A2).id
    assert logs[0].details == {
        "job_id": job_id,
        "type": "contact_slip",
        "semester": "1",
        "count": CLASS_SIZE,
        "needs_manual": 0,
        "status": "done",
    }


def test_the_list_shows_the_latest_job_of_the_same_scope(
    api_client: TestClient,
    auth_headers: Headers,
    start: Callable[..., Any],
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
) -> None:
    use_llm(FlakyWriter(fail_on=2))
    started = start().json()
    job_queue.run()
    url = f"{REPORTS}?type=contact_slip&semester=1&class_id={class_id_of('11A2')}"
    listing = api_client.get(url, headers=auth_headers(GVCN_11A2)).json()
    assert listing["job"]["id"] == started["id"]
    assert listing["job"]["status"] == "stopped" and listing["job"]["done"] == 5
    assert sum(1 for i in listing["items"] if i["report"] is not None) == 5
    other = api_client.get(url.replace("semester=1", "semester=2"), headers=auth_headers(GVCN_11A2))
    assert other.json()["job"] is None


# --- Nhận xét môn cả lớp ----------------------------------------------------------------------


def test_the_subject_teacher_can_write_the_whole_class_for_her_own_subject(
    db_session: Session,
    api_client: TestClient,
    auth_headers: Headers,
    use_llm: UseLlm,
    job_queue: JobQueue,
    class_id_of: Callable[[str], int],
    subject_id_of: Callable[[str], int],
) -> None:
    writer = FakeWriter()
    use_llm(writer)
    van, toan = subject_id_of("Ngữ văn"), subject_id_of("Toán")
    body = {
        "type": "subject_comment",
        "semester": "1",
        "class_id": class_id_of("11A2"),
        "subject_id": van,
    }
    response = api_client.post(REPORTS, json=body, headers=auth_headers(GVBM_VAN_11))
    assert response.status_code == 202
    job_queue.run()

    reports = drafts(db_session)
    assert len(reports) == CLASS_SIZE and {r.subject_id for r in reports} == {van}
    sent = writer.sent()
    assert "toán" not in sent and "tiếng anh" not in sent  # chỉ số liệu môn Ngữ văn
    wrong = api_client.post(
        REPORTS, json={**body, "subject_id": toan}, headers=auth_headers(GVBM_VAN_11)
    )
    assert wrong.status_code == 403
    assert db_session.scalar(select(func.count()).select_from(Report)) == CLASS_SIZE
