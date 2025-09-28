"""FastAPI 애플리케이션 메인 파일 (헥사고날 아키텍처)"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from src.app.routes import health, items, products, suppliers, orders, order_collection
from src.shared.config import get_settings
from src.shared.logging import get_logger
from src.adapters.persistence.models import get_db
from src.core.exceptions import create_http_exception, DropshippingError

logger = get_logger(__name__)
settings = get_settings()


# 라우터 등록
def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """애플리케이션 생명주기 관리"""
        # 시작시 실행
        logger.info("드랍싸핑 셀러 관리 시스템 시작 (헥사고날 아키텍처)")

        # 데이터베이스 연결 테스트
        try:
            # 테스트 데이터베이스 파일이 있는지 확인
            import os
            db_path = "test_dropshipping.db"
            if os.path.exists(db_path):
                logger.info("데이터베이스 연결 확인 완료")
            else:
                logger.warning("테스트 데이터베이스 파일이 존재하지 않습니다")
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise

        yield

        # 종료시 실행
        logger.info("드랍싸핑 셀러 관리 시스템 종료")

    app = FastAPI(
        title="드랍싸핑 셀러 관리 시스템",
        description="드랍싸핑 이커머스 셀러를 위한 상품 관리 및 동기화 시스템 (헥사고날 아키텍처)",
        version="2.0.0",
        lifespan=lifespan
    )

    # CORS 미들웨어
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 실제 운영시 특정 도메인만 허용
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 라우터 등록
    api_router = APIRouter(prefix="/api/v1")

    # 라우트 등록
    api_router.include_router(health.router, tags=["health"])
    api_router.include_router(items.router, prefix="/items", tags=["items"])
    api_router.include_router(products.router, prefix="/products", tags=["products"])
    api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
    api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
    api_router.include_router(order_collection.router, prefix="/order-collection", tags=["order-collection"])

    app.include_router(api_router)

    return app


# 애플리케이션 인스턴스
app = create_app()


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "드랍십핑 API 서버",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
