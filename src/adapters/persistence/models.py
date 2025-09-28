"""SQLAlchemy 모델 (헥사고날 아키텍처)"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, create_engine, text, Index
from sqlalchemy.sql import func
from typing import AsyncGenerator
import os
from datetime import datetime

from src.shared.config import get_settings

settings = get_settings()

# 동기 엔진 (Alembic에서 사용)
sync_engine = create_engine(settings.database_url, echo=settings.log_level == "DEBUG")

# 비동기 엔진 (애플리케이션에서 사용) - SQLite URL이 아닐 때만 생성
if settings.database_url.startswith("sqlite"):
    async_engine = None
    async_session = None
else:
    async_engine = create_async_engine(settings.database_url, echo=settings.log_level == "DEBUG")
    async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# 데이터베이스 모델 베이스
class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 제공"""
    if settings.database_url.startswith("sqlite"):
        # SQLite의 경우 동기 세션 반환 (async generator지만 동기 세션을 yield)
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(settings.database_url, echo=settings.log_level == "DEBUG")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as session:
            try:
                yield session
            finally:
                session.close()
    else:
        # PostgreSQL 등 async 지원 DB의 경우
        if async_session is None:
            raise ValueError("Async session not initialized for non-SQLite database")

        async with async_session() as session:
            try:
                yield session
            finally:
                await session.close()


# 공급사 테이블
class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    api_key = Column(String)
    api_secret = Column(String)
    base_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# 공급사 계정 테이블
class SupplierAccount(Base):
    __tablename__ = "supplier_accounts"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    account_name = Column(String, index=True, nullable=False)
    username = Column(String, nullable=False)
    password_encrypted = Column(String, nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)

    # 쿠팡 API 인증 정보
    coupang_access_key = Column(String)
    coupang_secret_key = Column(String)
    coupang_vendor_id = Column(String)

    # 드랍싸핑 설정
    default_margin_rate = Column(Float, default=0.3)
    sync_enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 인덱스
    __table_args__ = (
        Index('ix_supplier_accounts_supplier_active', 'supplier_id', 'is_active'),
        Index('ix_supplier_accounts_last_used', 'last_used_at'),
    )


# 마켓 계정 테이블
class MarketAccount(Base):
    __tablename__ = "market_accounts"

    id = Column(Integer, primary_key=True, index=True)
    market_type = Column(String, index=True, nullable=False)  # 'coupang', 'naver', 'elevenst'
    account_name = Column(String, index=True, nullable=False)
    api_key = Column(String, nullable=False)
    api_secret = Column(String, nullable=False)
    vendor_id = Column(String)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)

    # 설정
    default_margin_rate = Column(Float, default=0.3)
    sync_enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 인덱스
    __table_args__ = (
        Index('ix_market_accounts_type_active', 'market_type', 'is_active'),
        Index('ix_market_accounts_last_used', 'last_used_at'),
    )


# 상품 테이블 (헥사고날 아키텍처용)
class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)  # UUID나 해시 기반 ID
    supplier_id = Column(String, index=True, nullable=False)

    # 기본 상품 정보
    item_key = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    brand = Column(String)
    category_id = Column(String, index=True)
    description = Column(Text)
    images = Column(Text)  # JSON array
    options = Column(Text)  # JSON array
    is_active = Column(Boolean, default=True)

    # 가격 정보 (JSONB로 확장 가능)
    price_data = Column(Text, nullable=False)  # JSON: {"original": 10000, "sale": 8000, "margin_rate": 0.3}

    # 재고 정보
    stock_quantity = Column(Integer, default=0)
    max_stock_quantity = Column(Integer)

    # 공급사 정보
    supplier_product_id = Column(String)
    supplier_name = Column(String)
    supplier_url = Column(String)
    supplier_image_url = Column(String)

    # 배송 정보
    estimated_shipping_days = Column(Integer, default=7)

    # 동기화 정보
    sync_status = Column(String, default="pending")
    last_synced_at = Column(DateTime(timezone=True))
    sync_error_message = Column(Text)

    # 해시 (중복 검사용)
    hash_key = Column(String, index=True)

    # 메타데이터
    normalized_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 인덱스
    __table_args__ = (
        Index('ix_products_supplier_active', 'supplier_id', 'is_active'),
        Index('ix_products_category_sync', 'category_id', 'sync_status'),
        Index('ix_products_hash_key', 'hash_key'),
        Index('ix_products_last_synced', 'last_synced_at'),
    )


# 동기화 이력 테이블
class SyncHistory(Base):
    __tablename__ = "sync_history"

    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, index=True)
    supplier_id = Column(String, index=True)
    market_type = Column(String, index=True)
    sync_type = Column(String, nullable=False)  # 'ingest', 'normalize', 'upload', 'price_update', 'stock_update'
    status = Column(String, nullable=False)  # 'pending', 'in_progress', 'success', 'failed', 'cancelled'

    # 결과 정보
    result_data = Column(Text)  # JSON: 성공/실패 카운트, 에러 메시지 등

    # 상세 정보
    details = Column(Text)  # JSON: 추가 정보
    error_message = Column(Text)

    # 시간 정보
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)

    # 재시도 정보
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 인덱스
    __table_args__ = (
        Index('ix_sync_history_supplier_type', 'supplier_id', 'sync_type'),
        Index('ix_sync_history_status_created', 'status', 'created_at'),
        Index('ix_sync_history_item_status', 'item_id', 'status'),
    )


# 카테고리 테이블
class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(String, index=True)
    level = Column(Integer, default=1)
    supplier_id = Column(String, index=True)
    is_active = Column(Boolean, default=True)

    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 인덱스
    __table_args__ = (
        Index('ix_categories_supplier_level', 'supplier_id', 'level'),
        Index('ix_categories_parent_active', 'parent_id', 'is_active'),
    )
