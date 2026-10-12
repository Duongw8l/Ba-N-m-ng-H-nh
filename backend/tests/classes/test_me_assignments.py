from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db

URL = "/api/v1/me/assignments"


def fetch(
    client: TestClient, headers: Callable[[str], dict[str, str]], email: str
) -> dict[str, object]:
    response = client.get(URL, headers=headers(email))
    assert response.status_code == 200
    return response.json()


def test_requires_login(api_client: TestClient) -> None:
    response = api_client.get(URL)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_subject_teacher_sees_only_assigned_class_subject_pairs(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "gv.dia.10@example.com")

    assert body["homeroom_classes"] == []
    assert body["grades"] == []
    teaching = body["teaching"]
    assert isinstance(teaching, list)
    assert [(t["class_name"], t["subject_name"]) for t in teaching] == [("10A1", "Địa lí")]
    assert teaching[0]["grade_level"] == 10


def test_subject_teacher_of_three_classes(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "gv.van.10@example.com")

    assert [(t["class_name"], t["subject_name"]) for t in body["teaching"]] == [  # type: ignore[attr-defined]
        ("10A1", "Ngữ văn"),
        ("10A2", "Ngữ văn"),
        ("10A3", "Ngữ văn"),
    ]


def test_homeroom_only_teacher_sees_the_homeroom_class_and_nothing_to_teach(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "gvcn.10a2@example.com")

    assert [c["name"] for c in body["homeroom_classes"]] == ["10A2"]  # type: ignore[attr-defined]
    assert body["teaching"] == []


def test_teacher_who_is_both_gets_homeroom_and_teaching_lists(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "gv.toan.11@example.com")

    assert [c["name"] for c in body["homeroom_classes"]] == ["11A1"]  # type: ignore[attr-defined]
    assert [(t["class_name"], t["subject_name"]) for t in body["teaching"]] == [  # type: ignore[attr-defined]
        ("11A1", "Toán"),
        ("11A2", "Toán"),
        ("11A3", "Toán"),
    ]


def test_principal_sees_the_three_grades_and_no_assignments(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "bgh1@example.com")

    assert body["grades"] == [10, 11, 12]
    assert (body["homeroom_classes"], body["teaching"]) == ([], [])
    assert body["user"]["role"] == "principal"  # type: ignore[index]


def test_admin_gets_empty_lists(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "admin@example.com")

    assert (body["homeroom_classes"], body["teaching"], body["grades"]) == ([], [], [])
    assert body["user"]["role"] == "admin"  # type: ignore[index]


def test_user_part_never_contains_the_password_hash(
    api_client: TestClient, auth_headers: Callable[[str], dict[str, str]]
) -> None:
    body = fetch(api_client, auth_headers, "gv.toan.10@example.com")

    assert set(body["user"]) == {"id", "email", "full_name", "role"}  # type: ignore[arg-type]
    assert set(body) == {"user", "homeroom_classes", "teaching", "grades"}
