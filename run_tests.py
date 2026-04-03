#!/usr/bin/env python3
"""Single command to run the full test suite.

Usage:
    python run_tests.py            # run all tests (installs hashlib log filter first; quieter than `python -m pytest` on some Python builds)
    python run_tests.py -k fifo    # run only tests matching 'fifo'
    python run_tests.py --unit     # unit tests only (validators + database)
    python run_tests.py --integ    # integration tests only
    python run_tests.py --e2e      # end-to-end route tests only
"""

import sys

from runtime_logging_filter import install_hashlib_openssl_noise_filter

install_hashlib_openssl_noise_filter()

import pytest


def main():
    args = sys.argv[1:]

    if "--unit" in args:
        args.remove("--unit")
        args.extend(["tests/test_validators.py", "tests/test_database.py"])
    elif "--integ" in args:
        args.remove("--integ")
        args.append("tests/test_integration.py")
    elif "--e2e" in args:
        args.remove("--e2e")
        args.append("tests/test_routes.py")

    exit_code = pytest.main(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
