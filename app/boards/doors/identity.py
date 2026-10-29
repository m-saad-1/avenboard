"""Who is calling. The Dodil gateway signs the person in through the app's user pool and passes
them as the X-Dodil-User header (JSON: sub, email, app_roles). It strips any copy a client sends,
so the app trusts it and ships no login code of its own.

Local development: set DEV_USER=you@example.com to act as that person without the gateway.
"""
import json
import os
from typing import Optional

from boards.domain.model import Person

DEV_USER = os.environ.get("DEV_USER", "").strip().lower()


def person_from(headers) -> Optional[Person]:
    raw = headers.get("x-dodil-user")
    if raw:
        try:
            user = json.loads(raw)
        except ValueError:
            return None
        email = (user.get("email") or user.get("sub") or "").strip().lower()
        return Person(email=email) if email else None
    return Person(email=DEV_USER) if DEV_USER else None
