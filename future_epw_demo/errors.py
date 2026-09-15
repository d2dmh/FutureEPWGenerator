from __future__ import annotations


class WorkflowUserError(RuntimeError):
    code = "WorkflowError"

    def __init__(self, message: str, *, recovery: str = "", progress_safe: bool = True):
        super().__init__(message)
        self.message = message
        self.recovery = recovery
        self.progress_safe = progress_safe

    def user_text(self, translator=None) -> str:
        if translator is None:
            return self.message if not self.recovery else f"{self.message}\n\n{self.recovery}"
        message_key = f"error.{self.code}.message"
        recovery_key = f"error.{self.code}.recovery"
        message = translator.text(message_key)
        recovery = translator.text(recovery_key)
        if message == message_key:
            message = self.message
        if recovery == recovery_key:
            recovery = self.recovery
        return message if not recovery else f"{message}\n\n{recovery}"


class ProjectConflictError(WorkflowUserError):
    code = "ProjectConflict"


class InvalidBaselineError(WorkflowUserError):
    code = "InvalidBaseline"


class BaselineFingerprintMismatchError(WorkflowUserError):
    code = "BaselineFingerprintMismatch"


class PreflightFailedError(WorkflowUserError):
    code = "PreflightFailed"


class NetworkProviderFailureError(WorkflowUserError):
    code = "NetworkProviderFailure"


class CacheIncompleteError(WorkflowUserError):
    code = "CacheIncomplete"


class BackendProcessFailureError(WorkflowUserError):
    code = "BackendProcessFailure"


class ValidationFailureError(WorkflowUserError):
    code = "ValidationFailure"


class WeatherNetworkError(WorkflowUserError):
    code = "WeatherNetwork"


class WeatherDownloadError(WorkflowUserError):
    code = "WeatherDownload"


class WeatherArchiveError(WorkflowUserError):
    code = "WeatherArchive"


class WeatherEPWNotFoundError(WorkflowUserError):
    code = "WeatherEPWNotFound"


class WeatherValidationError(WorkflowUserError):
    code = "WeatherValidation"


class WeatherWriteError(WorkflowUserError):
    code = "WeatherWrite"
