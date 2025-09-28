"""헬스체크 라우트"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.app.di import get_db
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """서비스 헬스체크"""
    try:
        # 간단한 헬스체크 (데이터베이스 연결은 생명주기에서 확인)
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "dropshipping-api-hexagonal",
            "version": "2.0.0"
        }

    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
