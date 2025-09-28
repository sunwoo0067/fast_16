"""헥사고날 아키텍처 예외 처리"""
from fastapi import HTTPException


def create_http_exception(error):
    """HTTP 예외 생성"""
    if isinstance(error, str):
        return HTTPException(status_code=500, detail=error)
    return HTTPException(status_code=500, detail=str(error))


class DropshippingError(Exception):
    """드랍십핑 기본 예외"""
    pass
