"""The Dodil side: a service-account token, DataK3 on the Postgres wire, and Dodil Models.

The remix generated the service account and put its id and secret into the repo's CI secrets;
.dodil/deploy.yaml hands them to the app as environment variables.
"""
import os
import threading
import time

import httpx
import psycopg

TOKEN_URL = "https://id.dodil.io/realms/dodil/protocol/openid-connect/token"
PG_HOST = os.environ.get("PG_HOST", "pg.uk-lon-1.dodil.io")
MODELS_BASE = os.environ.get("MODELS_BASE", "https://api.dodil.io/v1").rstrip("/")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "kimi-k2.6")

_lock, _tok = threading.Lock(), {"v": None, "exp": 0.0}


def token() -> str:
    """A short-lived service-account token (client_credentials), cached until near expiry.
    It is the DataK3 password AND the Models bearer."""
    with _lock:
        if _tok["v"] and time.time() < _tok["exp"] - 60:
            return _tok["v"]
        r = httpx.post(TOKEN_URL, timeout=15, data={
            "grant_type": "client_credentials",
            "client_id": os.environ["DODIL_SERVICE_ACCOUNT_ID"],
            "client_secret": os.environ["DODIL_SERVICE_ACCOUNT_SECRET"]})
        r.raise_for_status()
        d = r.json()
        _tok.update(v=d["access_token"], exp=time.time() + float(d.get("expires_in", 300)))
        return _tok["v"]


def connect() -> psycopg.Connection:
    """DataK3 speaks Postgres: the database is the bucket, TLS is required."""
    return psycopg.connect(host=PG_HOST, port=5432, dbname=os.environ["BUCKET"], user="token",
                           password=token(), sslmode="require", autocommit=True)


def chat(prompt: str) -> str:
    """One chat call to Dodil Models (OpenAI-compatible). The gateway wraps the OpenAI body as
    {"status": ..., "data": {...}}, so unwrap it before reading choices."""
    r = httpx.post(f"{MODELS_BASE}/chat/completions", timeout=120,
                   headers={"Authorization": f"Bearer {token()}"},
                   json={"model": CHAT_MODEL, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    body = r.json()
    inner = body.get("data")
    if isinstance(inner, dict) and "choices" in inner:
        body = inner
    return body["choices"][0]["message"]["content"] or ""


class ModelsAssistant:
    def checklist(self, card_title: str) -> list:
        text = chat("Break this task into a short checklist of 3 to 6 concrete steps. "
                    "One step per line, no numbering, nothing else.\n\nTask: " + card_title)
        return [line.strip("-*• ").strip() for line in text.splitlines() if line.strip()][:8]
