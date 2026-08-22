"""Contract tests for generated Swagger/OpenAPI documentation."""

from __future__ import annotations

from api.main import app


def test_openapi_exposes_documented_api_contract() -> None:
    schema = app.openapi()

    assert schema["info"]["title"] == "Dietary Recommendation API"
    assert schema["info"]["version"] == "1.1.0"
    assert {tag["name"] for tag in schema["tags"]} >= {
        "Health",
        "المصادقة",
        "المستخدم",
        "Recommendations",
        "Foods",
    }
    assert "/users/meal-logs/summary" in schema["paths"]
    assert "/users/food-feedback" in schema["paths"]
    assert "/users/food-feedback/readiness" in schema["paths"]
    assert "/recommendations/meal" in schema["paths"]
    assert "/auth/login" in schema["paths"]
