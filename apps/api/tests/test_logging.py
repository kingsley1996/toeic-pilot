import json
import logging

from app.core.logging import JsonFormatter, TextFormatter, request_id_var


def _record(msg="something_happened", level=logging.INFO, **extra):
    record = logging.LogRecord("app.test", level, __file__, 1, msg, None, None)
    record.__dict__.update(extra)
    return record


def test_json_formatter_emits_parseable_json():
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["event"] == "something_happened"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert "ts" in payload


def test_json_formatter_includes_the_current_request_id():
    token = request_id_var.set("abc123")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "abc123"


def test_json_formatter_merges_extra_fields():
    payload = json.loads(JsonFormatter().format(_record(method="GET", path="/health", status=200)))
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status"] == 200


def test_json_formatter_does_not_leak_logrecord_internals():
    payload = json.loads(JsonFormatter().format(_record()))
    for structural in ("args", "msg", "levelno", "pathname", "lineno", "created"):
        assert structural not in payload


def test_json_formatter_survives_non_serialisable_extras():
    payload = json.loads(JsonFormatter().format(_record(obj=object())))
    assert "obj" in payload  # coerced via default=str rather than raising


def test_json_formatter_renders_exceptions():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys

        record = _record("request_failed", logging.ERROR)
        record.exc_info = sys.exc_info()
        payload = json.loads(JsonFormatter().format(record))
    assert "RuntimeError: boom" in payload["exception"]


def test_text_formatter_is_human_readable():
    token = request_id_var.set("deadbeefcafe")
    try:
        line = TextFormatter().format(_record(status=200))
    finally:
        request_id_var.reset(token)
    assert "something_happened" in line
    assert "deadbeef" in line  # request id shortened for reading
    assert "status=200" in line
