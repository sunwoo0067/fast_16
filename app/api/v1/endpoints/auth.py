from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def auth_info():
    """인증 정보"""
    return {"message": "인증 엔드포인트"}
