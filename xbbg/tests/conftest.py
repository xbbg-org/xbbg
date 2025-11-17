import logging
import sys

import pytest


def pytest_addoption(parser):

    parser.addoption(
        '--with_bbg', action='store_true', default=False,
        help='Run tests with Bloomberg connections'
    )
    parser.addoption(
        '--run-xbbg-live', action='store_true', default=False,
        help='Run live Bloomberg endpoint tests (requires Bloomberg connection)'
    )
    parser.addoption(
        '--prompt-between-tests', action='store_true', default=False,
        help='Prompt before each test (interactive mode)'
    )
    parser.addoption(
        '--xbbg-version', action='store', default=None,
        help='Expected xbbg version (e.g., 0.7.7). Tests will validate the installed version matches.'
    )


def pytest_configure(config):
    """Register custom markers and configure pytest."""
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "live_endpoint: marks tests as live Bloomberg endpoint tests (requires --run-xbbg-live to run)",
    )

    # Configure logging levels based on pytest log_cli_level
    # This ensures loggers actually emit DEBUG/INFO messages when requested
    log_cli_level = config.getoption('--log-cli-level', default='WARNING')
    if log_cli_level:
        # Convert string level to logging constant
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }
        log_level = level_map.get(log_cli_level.upper(), logging.WARNING)

        # Set xbbg loggers to the requested level so they actually emit messages
        logging.getLogger('xbbg').setLevel(log_level)
        logging.getLogger('blpapi').setLevel(log_level)
        # Also set root logger if DEBUG/INFO requested
        if log_level <= logging.INFO:
            logging.getLogger().setLevel(log_level)

    print(config)
    sys.pytest_call = True  # type: ignore[attr-defined]  # Dynamic attribute for pytest session tracking
    # Store prompt option globally for use in hooks
    config._prompt_between_tests = config.getoption('--prompt-between-tests', default=False)


def pytest_ignore_collect(collection_path, config):
    """Exclude test_live_endpoints.py from collection unless --run-xbbg-live is set."""
    return collection_path.name == 'test_live_endpoints.py' and not config.getoption('--run-xbbg-live', default=False)


def pytest_collection_modifyitems(config, items):
    """Skip live endpoint tests unless --run-xbbg-live flag is provided."""
    if not config.getoption('--run-xbbg-live', default=False):
        skip_live = pytest.mark.skip(
            reason='Live Bloomberg tests skipped. Use --run-xbbg-live to enable.'
        )
        for item in items:
            # Skip tests marked with live_endpoint marker (backup check)
            if 'live_endpoint' in item.keywords:
                item.add_marker(skip_live)


def pytest_unconfigure(config):

    print(config)
    if hasattr(sys, 'pytest_call'):
        del sys.pytest_call  # type: ignore[attr-defined]
