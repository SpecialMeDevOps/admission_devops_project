import io

import pytest

from app.backend.app import create_app


@pytest.fixture()
def client(tmp_path):
    database = tmp_path / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{database}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    return application.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_admission_submission_stores_file(client):
    response = client.post(
        "/api/admissions",
        data={
            "student_name": "Amina Yusuf",
            "email": "amina@example.com",
            "document": (io.BytesIO(b"document contents"), "transcript.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.json["message"] == "Admission submitted successfully."


def test_admission_requires_document(client):
    response = client.post(
        "/api/admissions",
        data={"student_name": "Amina Yusuf", "email": "amina@example.com"},
    )
    assert response.status_code == 400
