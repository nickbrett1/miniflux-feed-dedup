"""Smoke test: the src-layout package installs and imports cleanly."""


def test_package_imports():
    import miniflux_feed_dedup

    assert miniflux_feed_dedup.__version__
