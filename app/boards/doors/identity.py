"""Only an appid pool identity injected by the trusted Ignite gateway is an end user."""

import json
import os
from boards.domain.model import Person


def person_from(headers):
    pool = os.environ.get("DODIL_USER_POOL", "").strip()
    if not pool or headers.get("x-dodil-auth-source", "").lower() != "pool":
        return None
    try:
        user = json.loads(headers.get("x-dodil-user", ""))
        subject = user.get("sub")
        email = user.get("email", "")
        if not isinstance(subject, str) or not subject or not isinstance(email, str):
            return None
        # The documented convenience header does not attest email verification.
        # Invitation activation therefore requires owner confirmation by default.
        return Person(
            subject=subject,
            email=email.lower(),
            pool=pool,
            name=email.split("@")[0],
            email_verified=False,
        )
    except (TypeError, ValueError, AttributeError):
        return None
