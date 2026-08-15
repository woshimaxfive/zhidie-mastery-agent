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
