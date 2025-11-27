from django.http import JsonResponse
from django.utils.timezone import now


def api_root(request):
    """
    Lightweight health/info endpoint for load balancers and humans.
    """
    docs_url = request.build_absolute_uri("/api/v1/docs/")
    return JsonResponse(
        {
            "service": "Test24 Backend",
            "status": "ok",
            "version": "v1",
            "docs": docs_url,
            "timestamp": now().isoformat(),
        }
    )


