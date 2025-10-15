
from flask import jsonify

class AppError(Exception):
    def __init__(self, message, *, error_code="APP_ERROR", status_code=400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        
class ValidationError(AppError):
    def __init__(self, message, *, error_code="VALIDATION_ERROR"):
        super().__init__(message, error_code=error_code, status_code=400)

class NotFoundError(AppError):
    def __init__(self, message, *, error_code="NOT_FOUND"):
        super().__init__(message, error_code=error_code, status_code=404)
