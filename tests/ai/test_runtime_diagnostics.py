from __future__ import annotations


def test_runtime_diagnostic_sanitizer_redacts_and_bounds_nested_payloads() -> None:
    from apeiria.ai.diagnostics import sanitize_runtime_diagnostics

    sanitized = sanitize_runtime_diagnostics(
        {
            "api_key": "sk-secret",
            "message": "Authorization: Bearer sk-secret",
            "nested": {
                "password": "hidden",
                "items": [{"token": "nested-secret"} for _ in range(25)],
            },
            "long": "x" * 400,
        }
    )

    assert sanitized["api_key"] == "[redacted]"
    assert sanitized["message"] == "Authorization: Bearer [redacted]"
    assert sanitized["nested"] == {
        "password": "[redacted]",
        "items": [{"token": "[redacted]"} for _ in range(20)],
    }
    assert sanitized["long"] == "x" * 200
