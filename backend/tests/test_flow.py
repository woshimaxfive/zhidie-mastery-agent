from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_independent_transfer_updates_mastery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "flow.db"))
    with TestClient(app) as client:
        created = client.post("/api/v1/sessions", json={"knowledge_point_id": "python.range"})
        assert created.status_code == 201
        session = created.json()["session"]

        diagnostic = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": session["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": session["revision"],
            },
        )
        assert diagnostic.status_code == 200
        transfer_session = diagnostic.json()["session"]
        assert transfer_session["session_phase"] == "transfer_check"

        transfer = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": transfer_session["task"]["id"],
                "answer": "range(1, 11, 3)",
                "expected_revision": transfer_session["revision"],
            },
        )
        assert transfer.status_code == 200
        assert transfer.json()["mastery"]["mastery_state"] == "mastered"
        assert transfer.json()["mastery"]["evidence_level"] == "transfer_verified"


def test_hint_assisted_answer_does_not_master(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "assisted.db"))
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", json={}).json()["session"]
        hinted = client.post(
            f"/api/v1/sessions/{session['session_id']}/hints",
            json={"task_id": session["task"]["id"], "expected_revision": session["revision"]},
        ).json()["session"]
        result = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": hinted["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": hinted["revision"],
            },
        ).json()
        assert result["mastery"]["mastery_state"] == "pending_verification"
        assert result["mastery"]["evidence_level"] == "assisted"


def test_invalid_answer_preserves_revision(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "invalid.db"))
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", json={}).json()["session"]
        invalid = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": session["task"]["id"],
                "answer": "我不知道",
                "expected_revision": session["revision"],
            },
        )
        assert invalid.status_code == 422
        restored = client.get(f"/api/v1/sessions/{session['session_id']}").json()["session"]
        assert restored["revision"] == session["revision"]
        trace = client.get(f"/api/v1/sessions/{session['session_id']}/trace").json()["items"]
        assert trace[-1]["tool"] == "parse_answer"
        assert trace[-1]["status"] == "failed"


def test_transfer_hint_survives_wrong_attempt_and_prevents_false_mastery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "hint-retention.db"))
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", json={}).json()["session"]
        transfer = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": session["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": session["revision"],
            },
        ).json()["session"]
        hinted = client.post(
            f"/api/v1/sessions/{session['session_id']}/hints",
            json={"task_id": transfer["task"]["id"], "expected_revision": transfer["revision"]},
        ).json()["session"]
        wrong = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": hinted["task"]["id"],
                "answer": "range(1, 10, 3)",
                "expected_revision": hinted["revision"],
            },
        ).json()["session"]
        assert wrong["hint"]["level"] == 1

        corrected = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": wrong["task"]["id"],
                "answer": "range(1, 11, 3)",
                "expected_revision": wrong["revision"],
            },
        ).json()
        assert corrected["attempt"]["assistance_level"] == 1
        assert corrected["mastery"]["mastery_state"] == "pending_verification"
        assert corrected["mastery"]["evidence_level"] == "assisted"


def test_pending_verification_can_start_fresh_transfer_session(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "retry-transfer.db"))
    with TestClient(app) as client:
        first = client.post("/api/v1/sessions", json={}).json()["session"]
        transfer = client.post(
            f"/api/v1/sessions/{first['session_id']}/attempts",
            json={
                "task_id": first["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": first["revision"],
            },
        ).json()["session"]
        hinted = client.post(
            f"/api/v1/sessions/{first['session_id']}/hints",
            json={"task_id": transfer["task"]["id"], "expected_revision": transfer["revision"]},
        ).json()["session"]
        assisted = client.post(
            f"/api/v1/sessions/{first['session_id']}/attempts",
            json={
                "task_id": hinted["task"]["id"],
                "answer": "range(1, 11, 3)",
                "expected_revision": hinted["revision"],
            },
        ).json()
        assert assisted["mastery"]["mastery_state"] == "pending_verification"

        home = client.get("/api/v1/home").json()
        assert home["recommendation"]["action"] == "start_transfer_verification"
        retry = client.post("/api/v1/sessions", json={}).json()["session"]
        assert retry["session_phase"] == "transfer_check"
        assert retry["hint"] is None

        verified = client.post(
            f"/api/v1/sessions/{retry['session_id']}/attempts",
            json={
                "task_id": retry["task"]["id"],
                "answer": "range(1, 11, 3)",
                "expected_revision": retry["revision"],
            },
        ).json()
        assert verified["mastery"]["mastery_state"] == "mastered"


def test_mastery_profile_and_evidence_survive_new_session(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "profile.db"))
    with TestClient(app) as client:
        first = client.post("/api/v1/sessions", json={}).json()["session"]
        transfer = client.post(
            f"/api/v1/sessions/{first['session_id']}/attempts",
            json={
                "task_id": first["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": first["revision"],
            },
        ).json()["session"]
        client.post(
            f"/api/v1/sessions/{first['session_id']}/attempts",
            json={
                "task_id": transfer["task"]["id"],
                "answer": "range(1, 11, 3)",
                "expected_revision": transfer["revision"],
            },
        )

        second = client.post("/api/v1/sessions", json={}).json()
        assert second["mastery"]["mastery_state"] == "mastered"
        assert second["mastery"]["evidence_level"] == "transfer_verified"
        home = client.get("/api/v1/home").json()
        assert home["mastery"]["mastery_state"] == "mastered"
        evidence = client.get("/api/v1/knowledge-points/python.range/evidence").json()
        assert evidence["mastery"]["mastery_state"] == "mastered"
        assert {item["session_id"] for item in evidence["items"]} == {first["session_id"]}


def test_validation_errors_use_api_error_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "validation.db"))
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", json={}).json()["session"]
        response = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={"task_id": session["task"]["id"], "expected_revision": session["revision"]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
        assert response.json()["error"]["field"] == "answer"


def test_oversized_range_returns_answer_format_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "oversized-range.db"))
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", json={}).json()["session"]
        transfer = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": session["task"]["id"],
                "answer": "[2, 5, 8]",
                "expected_revision": session["revision"],
            },
        ).json()["session"]
        response = client.post(
            f"/api/v1/sessions/{session['session_id']}/attempts",
            json={
                "task_id": transfer["task"]["id"],
                "answer": "range(0, 9223372036854775808, 1)",
                "expected_revision": transfer["revision"],
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ANSWER_FORMAT"
        assert response.json()["error"]["field"] == "answer"


def test_persistence_errors_use_api_error_contract(tmp_path: Path, monkeypatch):
    startup_database = tmp_path / "startup.db"
    monkeypatch.setenv("MASTERY_DB_PATH", str(startup_database))
    with TestClient(app, raise_server_exceptions=False) as client:
        invalid_database_path = tmp_path / "database-directory"
        invalid_database_path.mkdir()
        monkeypatch.setenv("MASTERY_DB_PATH", str(invalid_database_path))
        response = client.get("/api/v1/home")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PERSISTENCE_FAILED"
        assert response.json()["error"]["retryable"] is True


def test_unclassified_errors_use_api_error_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MASTERY_DB_PATH", str(tmp_path / "internal.db"))
    monkeypatch.setattr("app.main.get_home", lambda: (_ for _ in ()).throw(RuntimeError("secret detail")))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/home")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "secret detail" not in response.text
