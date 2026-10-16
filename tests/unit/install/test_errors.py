"""Unit tests for install/errors.py exception types."""

import pytest

from apm_cli.deps.lockfile import LockfileConflictError, LockfileFormatError
from apm_cli.install.errors import (
    AuthenticationError,
    DirectDependencyError,  # noqa: F401
    PolicyViolationError,  # noqa: F401
    install_failure_message,
)


@pytest.mark.parametrize("error_type", [RuntimeError, OSError, LockfileFormatError])
def test_non_conflict_install_failures_keep_existing_prefix(error_type):
    assert install_failure_message(error_type("original cause")) == (
        "Error installing dependencies: original cause"
    )


def test_install_conflict_message_remains_canonical(tmp_path):
    error = LockfileConflictError(tmp_path / "apm.lock.yaml")
    assert install_failure_message(error) == str(error)


class TestAuthenticationError:
    """AuthenticationError attribute roundtrip and isinstance checks."""

    def test_carries_diagnostic_context(self):
        err = AuthenticationError(
            "Authentication failed for dev.azure.com",
            diagnostic_context="Try az login",
        )
        assert err.diagnostic_context == "Try az login"
        assert str(err) == "Authentication failed for dev.azure.com"

    def test_is_runtime_error(self):
        err = AuthenticationError("msg")
        assert isinstance(err, RuntimeError)

    def test_default_diagnostic_context_is_empty(self):
        err = AuthenticationError("msg")
        assert err.diagnostic_context == ""

    def test_multiline_diagnostic_preserved(self):
        diag = (
            "\n    ADO_APM_PAT is set, but the Azure DevOps request failed.\n"
            "    Generate a new PAT.\n"
        )
        err = AuthenticationError("msg", diagnostic_context=diag)
        assert "\n" in err.diagnostic_context
        assert "ADO_APM_PAT" in err.diagnostic_context
