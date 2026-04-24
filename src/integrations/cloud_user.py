"""Resolved cloud user id for Blaxel workspace layout (replace with auth later)."""

HARDCODED_CLOUD_USER_ID = "dev-user-1"


def effective_cloud_user_id() -> str:
    """Stable id for one VM + ``koraku/users/…`` tree until Clerk (or similar) supplies ``sub``."""
    return HARDCODED_CLOUD_USER_ID
