"""
Auth Errors Module

Exception types shared by the auth framework.

They live here, not in ``service.py``, because both the service and the providers it
constructs need to raise them: ``service.py`` imports ``providers.py``, so a provider
importing back from the service would be a circular import. ``AuthService`` re-exports
``PassthroughAuthError`` for callers that already import it from there.
"""


class PassthroughAuthError(Exception):
    """Raised when a user auth artifact is required/present but unusable, and no
    lower-priority credential may be substituted (fail-fast)."""
    pass
