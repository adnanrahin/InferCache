"""Payload-kind detector: JSON/code must not be rewritten."""

from infercache.optimization.payload import PayloadKind, classify_payload, should_rewrite


def test_prose_is_rewritable():
    text = "Please explain HTTP caching in simple terms."
    assert classify_payload(text) is PayloadKind.PROSE
    assert should_rewrite(text) is True


def test_json_object_is_not_rewritten():
    text = '{"url": "https://example.com", "retries": 3}'
    assert classify_payload(text) is PayloadKind.JSON
    assert should_rewrite(text) is False


def test_json_array_is_not_rewritten():
    text = '[{"role": "user", "content": "hi"}]'
    assert classify_payload(text) is PayloadKind.JSON
    assert should_rewrite(text) is False


def test_fenced_code_is_not_rewritten():
    text = "```python\ndef add(a, b):\n    return a + b\n```"
    assert classify_payload(text) is PayloadKind.CODE
    assert should_rewrite(text) is False


def test_python_module_without_fences():
    text = (
        "import os\n"
        "def main():\n"
        "    print(os.getcwd())\n"
        "    return 0\n"
    )
    assert classify_payload(text) is PayloadKind.CODE
