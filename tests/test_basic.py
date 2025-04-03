"""Basic tests for the oyez-scraping project."""


def test_environment() -> None:
    """Test that the test environment is properly set up."""
    assert True, "Basic assertion passes"


def test_version_import() -> None:
    """Test that we can import the version."""
    from src._version import __version__

    assert isinstance(__version__, str), "Version should be a string"
    assert len(__version__) > 0, "Version should not be empty"
