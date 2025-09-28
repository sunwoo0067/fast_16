"""헥사고날 아키텍처 통합 테스트"""
import pytest
import pytest_asyncio
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator

from src.app.main import create_app
from src.adapters.persistence.models import Base, get_db
from src.shared.config import get_settings

settings = get_settings()


@pytest.fixture(scope="session")
def test_database_url():
    """테스트용 데이터베이스 URL"""
    return "sqlite+aiosqlite:///./test_dropshipping.db"


@pytest.fixture(scope="session")
async def test_engine(test_database_url):
    """테스트용 데이터베이스 엔진"""
    engine = create_async_engine(
        test_database_url,
        echo=settings.log_level == "DEBUG"
    )

    # 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 테스트 완료 후 정리
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """테스트용 데이터베이스 세션"""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@pytest.fixture
def test_app():
    """테스트용 FastAPI 애플리케이션"""

    # 테스트용 get_db 오버라이드 (동기 세션 사용)
    def override_get_db():
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine("sqlite:///./test_dropshipping.db", echo=False)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            return SessionLocal()
        finally:
            pass

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.fixture
def test_client(test_app):
    """테스트용 HTTP 클라이언트"""
    return TestClient(test_app)


@pytest.mark.asyncio
class TestHexagonalArchitectureIntegration:
    """헥사고날 아키텍처 통합 테스트"""

    def test_health_check(self, test_client):
        """헬스체크 통합 테스트"""
        response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "service" in data

    def test_products_api_structure(self, test_client):
        """상품 API 구조 테스트"""
        # 상품 수집 엔드포인트 테스트
        response = test_client.post("/api/v1/products/ingest", json={
            "supplier_id": "test_supplier",
            "account_id": "test_account",
            "item_keys": ["test_item_1", "test_item_2"]
        })

        # 아직 구현되지 않았으므로 501 반환 예상
        assert response.status_code == 501

    def test_suppliers_api_structure(self, test_client):
        """공급사 API 구조 테스트"""
        # 공급사 생성 엔드포인트 테스트
        response = test_client.post("/api/v1/suppliers/", json={
            "name": "테스트 공급사",
            "description": "테스트용 공급사"
        })

        # 아직 실제 구현되지 않았으므로 500 또는 501 반환 예상
        assert response.status_code in [500, 501]

    def test_database_integration(self):
        """데이터베이스 통합 테스트"""
        from src.adapters.persistence.repositories import ItemRepository
        from src.core.entities.item import Item, PricePolicy, ItemOption

        # 동기 데이터베이스 세션 생성 (완전히 독립된 테스트 DB 사용)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.adapters.persistence.models import Base
        import tempfile
        import os

        # 완전히 독립된 임시 DB 파일 생성
        import uuid
        temp_db_name = f"test_{uuid.uuid4().hex}.db"
        engine = create_engine(f"sqlite:///{temp_db_name}", echo=False)

        # 테스트 데이터베이스에 테이블 생성
        Base.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()

        # 리포지토리 인스턴스 생성
        repository = ItemRepository(db_session)

        test_item = Item(
            id="test_item_001",
            title="테스트 상품",
            brand="테스트 브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[ItemOption(name="색상", value="빨강", stock_quantity=10)],
            images=["test_image.jpg"],
            category_id="test_category",
            supplier_id="test_supplier"
        )

        # 동기 함수 호출 (테스트 환경에서는 동기로 실행)
        if hasattr(repository, 'save_item'):
            if asyncio.iscoroutinefunction(repository.save_item):
                asyncio.run(repository.save_item(test_item))
            else:
                repository.save_item(test_item)

        # 상품 조회 테스트
        if asyncio.iscoroutinefunction(repository.get_item_by_id):
            retrieved_item = asyncio.run(repository.get_item_by_id("test_item_001"))
        else:
            retrieved_item = repository.get_item_by_id("test_item_001")

        assert retrieved_item is not None
        assert retrieved_item.title == "테스트 상품"
        assert retrieved_item.brand == "테스트 브랜드"

        # 해시 기반 중복 체크 테스트
        if asyncio.iscoroutinefunction(repository.find_item_by_hash):
            duplicate_item = asyncio.run(repository.find_item_by_hash(test_item.hash_key))
        else:
            duplicate_item = repository.find_item_by_hash(test_item.hash_key)
        assert duplicate_item is not None

        db_session.close()

    def test_api_documentation(self, test_client):
        """API 문서 접근 테스트"""
        # Swagger UI 접근
        response = test_client.get("/docs")
        assert response.status_code == 200
        assert "swagger-ui" in response.text.lower()

        # OpenAPI 스키마 접근
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_cors_headers(self, test_client):
        """CORS 헤더 테스트"""
        response = test_client.options("/api/v1/health")

        # CORS 헤더 확인
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers


if __name__ == "__main__":
    # 직접 실행 시 pytest 실행
    pytest.main([__file__, "-v"])
