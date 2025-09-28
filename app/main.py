from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models.database import init_db
from app.api.v1.router import api_router
from app.core.exceptions import create_http_exception, DropshippingError
import logging

# 설정 로드
settings = get_settings()

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작시 실행
    logger.info("드랍싸핑 셀러 관리 시스템 시작")
    await init_db()
    logger.info("데이터베이스 초기화 완료")

    yield

    # 종료시 실행
    logger.info("드랍싸핑 셀러 관리 시스템 종료")

# FastAPI 앱 생성
app = FastAPI(
    title="드랍싸핑 셀러 관리 시스템",
    description="드랍싸핑 이커머스 셀러를 위한 상품 관리 및 동기화 시스템",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(
    api_router,
    prefix=settings.api_prefix
)

# 기본 헬스체크 엔드포인트
@app.get("/")
async def root():
    return {
        "message": "드랍싸핑 셀러 관리 시스템 API",
        "version": "2.0.0",
        "status": "running",
        "docs_url": "/docs"
    }

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """시스템 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": "2025-09-28T06:00:00Z",
        "version": "2.0.0"
    }

# 전역 예외 핸들러
@app.exception_handler(DropshippingError)
async def dropshipping_exception_handler(request: Request, exc: DropshippingError):
    """드랍싸핑 관련 예외 처리"""
    logger.error(f"드랍싸핑 예외 발생: {exc.message}", extra={"error_details": exc.details})

    # HTTP 예외로 변환
    http_exception = create_http_exception(exc)

    return {
        "error": {
            "message": exc.message,
            "type": exc.__class__.__name__,
            "details": exc.details
        }
    }

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 처리"""
    logger.error(f"예상치 못한 예외 발생: {str(exc)}", exc_info=True)

    return {
        "error": {
            "message": "서버 내부 오류가 발생했습니다",
            "type": "InternalServerError"
        }
    }

if __name__ == "__main__":
    import uvicorn

    logger.info(f"서버 시작: {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

