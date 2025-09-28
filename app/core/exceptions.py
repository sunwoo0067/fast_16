from typing import Optional, Dict, Any

class DropshippingError(Exception):
    """드랍싸핑 관련 기본 에러"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ProductSyncError(DropshippingError):
    """상품 동기화 에러"""
    pass

class ValidationError(DropshippingError):
    """데이터 검증 에러"""

    def __init__(self, message: str, field: str = None, value: Any = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.field = field
        self.value = value

class SupplierError(DropshippingError):
    """공급사 관련 에러"""
    pass

class OrderError(DropshippingError):
    """주문 관련 에러"""
    pass

class APIRateLimitError(DropshippingError):
    """API 호출 제한 에러"""
    pass

class AuthenticationError(DropshippingError):
    """인증 에러"""
    pass

class DatabaseError(DropshippingError):
    """데이터베이스 에러"""
    pass

class ExternalAPIError(DropshippingError):
    """외부 API 호출 에러"""

    def __init__(self, message: str, api_name: str = None, status_code: int = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.api_name = api_name
        self.status_code = status_code

# FastAPI에서 사용할 HTTP 예외들
from fastapi import HTTPException, status

def create_http_exception(error: DropshippingError, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> HTTPException:
    """드랍싸핑 에러를 HTTP 예외로 변환"""

    # 에러 타입별 상태코드 매핑
    error_type_mapping = {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        APIRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
        SupplierError: status.HTTP_404_NOT_FOUND,
        OrderError: status.HTTP_400_BAD_REQUEST,
        ExternalAPIError: status.HTTP_502_BAD_GATEWAY,
    }

    # 매핑된 상태코드가 있으면 사용
    for error_type, mapped_status in error_type_mapping.items():
        if isinstance(error, error_type):
            status_code = mapped_status
            break

    return HTTPException(
        status_code=status_code,
        detail={
            "message": error.message,
            "type": error.__class__.__name__,
            "details": error.details
        }
    )

