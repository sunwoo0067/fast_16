from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def coupang_info():
    """쿠팡 정보"""
    return {"message": "쿠팡 엔드포인트"}
