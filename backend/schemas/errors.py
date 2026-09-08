from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    stage: str
    retryable: bool = False
    request_id: str | None = None
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        stage: str,
        retryable: bool = False,
        request_id: str | None = None,
        retry_after_seconds: int | None = None,
        status_code: int = 400,
    ) -> None:
        self.detail = ErrorDetail(
            code=code,
            message=message,
            stage=stage,
            retryable=retryable,
            request_id=request_id,
            retry_after_seconds=retry_after_seconds,
        )
        self.status_code = status_code
        super().__init__(message)
