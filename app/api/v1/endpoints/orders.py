from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def orders_info():
    """주문 정보"""
    return {"message": "주문 엔드포인트"}
