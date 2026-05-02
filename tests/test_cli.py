from pathlib import Path

import aoi.cli as cli


def test_serve_http_uses_fastapi_by_default(monkeypatch, tmp_path) -> None:
    called: dict[str, object] = {}

    def fake_create_app(*, db_path: Path, log_path: Path, storage_path: Path):
        called["create_app"] = {
            "db_path": db_path,
            "log_path": log_path,
            "storage_path": storage_path,
        }
        return "app-object"

    def fake_uvicorn_run(app, *, host: str, port: int) -> None:
        called["uvicorn_run"] = {
            "app": app,
            "host": host,
            "port": port,
        }

    monkeypatch.setattr(cli, "create_app", fake_create_app)
    monkeypatch.setattr(cli.uvicorn, "run", fake_uvicorn_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "aoi.cli",
            "serve-http",
            "--host",
            "127.0.0.1",
            "--port",
            "9000",
            "--output",
            str(tmp_path / "inference.jsonl"),
            "--db-path",
            str(tmp_path / "aoi.db"),
            "--storage-path",
            str(tmp_path / "storage"),
        ],
    )

    cli.main()

    assert called["create_app"] == {
        "db_path": tmp_path / "aoi.db",
        "log_path": tmp_path / "inference.jsonl",
        "storage_path": tmp_path / "storage",
    }
    assert called["uvicorn_run"] == {
        "app": "app-object",
        "host": "127.0.0.1",
        "port": 9000,
    }
