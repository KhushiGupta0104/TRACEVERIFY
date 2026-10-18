"""Normalized event-type vocabulary shared by ingestion, rules and the UI."""

AUTH_ORIENT_TYPES = {
    "logon": "AUTH_LOGON",
    "logoff": "AUTH_LOGOFF",
    "tgs": "AUTH_TICKET",
    "tgt": "AUTH_TICKET",
    "authmap": "AUTH_MAP",
    "screenlock": "AUTH_SCREEN",
    "screenunlock": "AUTH_SCREEN",
}

EVENT_TYPE_LABELS = {
    "REDTEAM_COMPROMISE": "Red-team seed",
    "AUTH_LOGON": "Logon",
    "AUTH_LOGOFF": "Logoff",
    "AUTH_TICKET": "Kerberos ticket",
    "AUTH_MAP": "Auth mapping",
    "AUTH_SCREEN": "Screen lock/unlock",
    "AUTH_OTHER": "Authentication",
    "PROC_START": "Process start",
    "PROC_END": "Process end",
    "PROC_OTHER": "Process event",
    "DNS_RESOLVE": "DNS resolution",
    "NET_FLOW": "Network flow",
}


def auth_event_type(auth_orient: object) -> str:
    if not auth_orient:
        return "AUTH_OTHER"
    return AUTH_ORIENT_TYPES.get(str(auth_orient).strip().lower(), "AUTH_OTHER")


def proc_event_type(event_type: object) -> str:
    value = str(event_type or "").strip().lower()
    return {"start": "PROC_START", "end": "PROC_END"}.get(value, "PROC_OTHER")
