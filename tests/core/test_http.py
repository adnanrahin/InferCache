"""HTTP URL scheme guard."""

from urllib.request import Request

import pytest

from infercache.http import require_http_url, urlopen


def test_require_http_url_allows_http_https():
    assert require_http_url("http://127.0.0.1:11434/api/tags") == "http://127.0.0.1:11434/api/tags"
    assert require_http_url("https://api.openai.com/v1/chat/completions").startswith("https://")


def test_require_http_url_rejects_file_and_custom_schemes():
    with pytest.raises(ValueError, match="file"):
        require_http_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="ftp"):
        require_http_url("ftp://example.com/model.bin")
    with pytest.raises(ValueError, match="scheme"):
        require_http_url("/local/path")


def test_urlopen_rejects_file_scheme_on_request():
    req = Request("file:///etc/passwd")
    with pytest.raises(ValueError, match="file"):
        urlopen(req, timeout=1)


def test_urlopen_rejects_file_and_ftp_string_urls():
    with pytest.raises(ValueError, match="file"):
        urlopen("file:///etc/passwd", timeout=1)
    with pytest.raises(ValueError, match="ftp"):
        urlopen("ftp://example.com/model.bin", timeout=1)
