class PrivateNoStoreMiddleware:
    """Authenticated JSON/HTML is never reusable as an offline schedule cache."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            response["Cache-Control"] = "private, no-store"
        return response
