import logging
import sys


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
    sys.pytest_call = True
    # Store prompt option globally for use in hooks
    config._prompt_between_tests = config.getoption('--prompt-between-tests', default=False)


def pytest_unconfigure(config):

    print(config)
    if hasattr(sys, 'pytest_call'):
        del sys.pytest_call
