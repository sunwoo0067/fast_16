"""의존성 주입 설정"""
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.ports.supplier_port import SupplierPort
from src.core.ports.market_port import MarketPort
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.usecases.normalize_items import NormalizeItemsUseCase
from src.core.usecases.publish_to_market import PublishToMarketUseCase
from src.core.usecases.collect_orders import CollectOrdersUseCase
from src.services.item_service import ItemService
from src.services.supplier_service import SupplierService
from src.services.order_service import OrderService
from src.shared.config import get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# 데이터베이스 의존성
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 제공"""
    # 테스트 환경에서는 동기 엔진 사용
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session

    engine = create_engine(
        settings.database_url,
        echo=settings.log_level == "DEBUG"
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.close()


# 포트 구현체 (실제로는 어댑터에서 주입받아야 함)
def get_supplier_port() -> SupplierPort:
    """공급사 포트 구현체"""
    from src.adapters.suppliers.ownerclan_adapter import OwnerClanAdapter
    return OwnerClanAdapter(
        api_url=settings.ownerclan_api_url,
        auth_url=settings.ownerclan_auth_url
    )


def get_market_port() -> MarketPort:
    """마켓 포트 구현체"""
    from src.adapters.markets.coupang_adapter import CoupangAdapter
    return CoupangAdapter(
        base_url=settings.coupang_api_url
    )


def get_repository() -> RepositoryPort:
    """리포지토리 포트 구현체"""
    from src.adapters.persistence.repositories import ItemRepository
    from src.adapters.persistence.models import get_db
    import asyncio

    # 동기 세션을 생성 (테스트 환경용)
    async def get_sync_session():
        async for session in get_db():
            return session
        return None

    # 테스트 환경에서는 동기 세션을 사용
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 이벤트 루프가 실행 중인 경우 동기 세션 생성
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine("sqlite:///./test_dropshipping.db", echo=False)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            return ItemRepository(db_session=SessionLocal())
        else:
            # 이벤트 루프가 없는 경우
            return ItemRepository(db_session=asyncio.run(get_sync_session()))
    except:
        # 예외 발생 시 동기 세션 사용
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine("sqlite:///./test_dropshipping.db", echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return ItemRepository(db_session=SessionLocal())


def get_clock() -> ClockPort:
    """클록 포트 구현체"""
    from src.adapters.persistence.clock_adapter import ClockAdapter
    return ClockAdapter()


# 유즈케이스 팩토리
def get_ingest_items_usecase(
    supplier_port: SupplierPort = Depends(get_supplier_port),
    repository: RepositoryPort = Depends(get_repository),
    clock: ClockPort = Depends(get_clock)
) -> IngestItemsUseCase:
    """상품 수집 유즈케이스"""
    return IngestItemsUseCase(supplier_port, repository, clock)


def get_normalize_items_usecase(
    repository: RepositoryPort = Depends(get_repository),
    clock: ClockPort = Depends(get_clock)
) -> NormalizeItemsUseCase:
    """상품 정규화 유즈케이스"""
    return NormalizeItemsUseCase(repository, clock)


def get_publish_to_market_usecase(
    market_port: MarketPort = Depends(get_market_port),
    repository: RepositoryPort = Depends(get_repository),
    clock: ClockPort = Depends(get_clock)
) -> PublishToMarketUseCase:
    """마켓 업로드 유즈케이스"""
    return PublishToMarketUseCase(market_port, repository, clock)


def get_collect_orders_usecase(
    supplier_port: SupplierPort = Depends(get_supplier_port),
    repository: RepositoryPort = Depends(get_repository),
    clock: ClockPort = Depends(get_clock)
) -> CollectOrdersUseCase:
    """주문 수집 유즈케이스"""
    return CollectOrdersUseCase(supplier_port, repository, clock)


def get_item_service(
    ingest_usecase: IngestItemsUseCase = Depends(get_ingest_items_usecase),
    normalize_usecase: NormalizeItemsUseCase = Depends(get_normalize_items_usecase),
    publish_usecase: PublishToMarketUseCase = Depends(get_publish_to_market_usecase),
    repository: RepositoryPort = Depends(get_repository)
) -> ItemService:
    """상품 서비스 파사드"""
    return ItemService(
        ingest_usecase=ingest_usecase,
        normalize_usecase=normalize_usecase,
        publish_usecase=publish_usecase,
        repository=repository
    )


def get_supplier_service(
    repository: RepositoryPort = Depends(get_repository),
    supplier_port: SupplierPort = Depends(get_supplier_port)
) -> SupplierService:
    """공급사 서비스 파사드"""
    return SupplierService(
        repository=repository,
        supplier_port=supplier_port
    )


def get_order_service(
    repository: RepositoryPort = Depends(get_repository)
) -> OrderService:
    """주문 서비스 파사드"""
    return OrderService(
        repository=repository
    )
