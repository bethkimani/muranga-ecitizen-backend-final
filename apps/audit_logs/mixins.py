from auditlog.context import set_actor


class AuditActorMixin:
    """Records request.user as the actor for audit log entries made during an API call."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # JWT authentication runs here
        self._actor_ctx = set_actor(request.user)
        self._actor_ctx.__enter__()

    def finalize_response(self, request, response, *args, **kwargs):
        ctx = getattr(self, '_actor_ctx', None)
        if ctx is not None:
            ctx.__exit__(None, None, None)
            self._actor_ctx = None
        return super().finalize_response(request, response, *args, **kwargs)