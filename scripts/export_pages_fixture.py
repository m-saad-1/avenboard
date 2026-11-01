"""Export labeled local QA records for the read-only GitHub Pages build."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from tests.preview import app


def main():
    with TestClient(app) as client:
        identity_response = client.get("/api/me")
        workspaces_response = client.get("/api/workspaces")
        identity_response.raise_for_status()
        workspaces_response.raise_for_status()
        workspaces = workspaces_response.json()
        if not workspaces:
            raise RuntimeError("QA preview did not create its sample workspace")
        workspace = workspaces[0]
        snapshot_response = client.get(f"/api/workspaces/{workspace['id']}/snapshot")
        snapshot_response.raise_for_status()
        payload = {
            "identity": identity_response.json(),
            "workspaces": workspaces,
            "snapshot": snapshot_response.json(),
        }

    output = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "public"
        / "demo"
        / "workspace.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Exported labeled sample fixture to {output}")


if __name__ == "__main__":
    main()
