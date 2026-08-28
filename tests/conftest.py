"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_infercache_home(tmp_path, monkeypatch):
    """Keep every test away from the real ~/.infercache."""
    monkeypatch.setenv("INFERCACHE_HOME", str(tmp_path / "infercache-home"))
