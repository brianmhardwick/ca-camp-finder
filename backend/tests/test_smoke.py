"""Smoke tests — verifies the app can be imported without errors."""


def test_import_app():
    from app.main import app  # noqa: F401


def test_import_windows():
    from app.scheduler import windows  # noqa: F401


def test_import_runner():
    from app.scheduler import runner  # noqa: F401
