from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def categories_info():
    """카테고리 정보"""
    return {"message": "카테고리 엔드포인트"}
