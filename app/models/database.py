from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, create_engine, text
from sqlalchemy.sql import func
from typing import AsyncGenerator
import os
from datetime import datetime, timedelta
from app.core.config import get_settings

settings = get_settings()

# 비동기 엔진 생성
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 데이터베이스 모델 베이스
class Base(DeclarativeBase):
    pass

# 공급사 테이블 (개선됨)
class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    api_key = Column(String)  # 공급사 API 키
    api_secret = Column(String)  # 공급사 API 시크릿
    base_url = Column(String)  # 공급사 API 베이스 URL
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 공급사계정 테이블 (개선됨)
class SupplierAccount(Base):
    __tablename__ = "supplier_accounts"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    account_id = Column(String, index=True, nullable=False)  # b00679540
    account_password = Column(String, nullable=False)  # ehdgod1101*
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)  # 토큰 사용 횟수
    total_requests = Column(Integer, default=0)  # 총 API 요청 수
    successful_requests = Column(Integer, default=0)  # 성공한 요청 수
    failed_requests = Column(Integer, default=0)  # 실패한 요청 수

    # 쿠팡 API 인증 정보
    coupang_access_key = Column(String)  # 쿠팡 API Access Key
    coupang_secret_key = Column(String)  # 쿠팡 API Secret Key
    coupang_vendor_id = Column(String)   # 쿠팡 벤더 ID

    # 드랍싸핑 설정
    default_margin_rate = Column(Float, default=0.3)  # 기본 마진율
    sync_enabled = Column(Boolean, default=True)  # 동기화 활성화 여부
    last_sync_at = Column(DateTime(timezone=True))  # 마지막 동기화 시간

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 상품 테이블
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)

    # 기본 상품 정보 (실제 테이블 구조에 맞춤)
    item_key = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    model = Column(String)
    brand = Column(String)
    category = Column(String)
    price = Column(Integer)
    options = Column(Text)
    description = Column(Text)
    images = Column(Text)
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # OwnerClan 특화 필드들 (확장)
    supplier_product_id = Column(String)
    supplier_name = Column(String)
    supplier_url = Column(String)
    supplier_image_url = Column(String)
    estimated_shipping_days = Column(Integer, default=7)
    sync_status = Column(String, default="pending")
    margin_rate = Column(Float, default=0.3)
    sale_price = Column(Integer)
    stock_quantity = Column(Integer, default=0)
    max_stock_quantity = Column(Integer)
    category_id = Column(String)
    category_name = Column(String)
    manufacturer = Column(String)
    last_synced_at = Column(DateTime(timezone=True))
    sync_error_message = Column(Text)

# 상품 동기화 이력 테이블 (새로 추가)
class ProductSyncHistory(Base):
    __tablename__ = "product_sync_history"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    product_id = Column(Integer, index=True, nullable=False)
    sync_type = Column(String, nullable=False)  # 'create', 'update', 'delete', 'price_change'
    status = Column(String, nullable=False)  # 'success', 'failed'
    old_data = Column(Text)  # JSON 형태로 이전 데이터
    new_data = Column(Text)  # JSON 형태로 새 데이터
    error_message = Column(Text)
    sync_duration_ms = Column(Integer)  # 동기화 소요 시간 (밀리초)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 주문 테이블 (개선됨)
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    order_key = Column(String, index=True, nullable=False)  # 오너클랜 주문 코드
    order_id = Column(String, index=True)  # API ID
    status = Column(String, index=True)  # 주문 상태
    products = Column(Text)  # JSON 형태로 주문 상품 정보 저장
    quantity = Column(Integer)  # 주문 수량
    total_price = Column(Integer)  # 총 가격
    shipping_fee = Column(Integer)  # 배송비
    shipping_type = Column(String)  # 배송비 부과 타입
    tracking_number = Column(String)  # 운송장 번호
    shipping_company = Column(String)  # 택배사 이름
    shipped_date = Column(DateTime(timezone=True))  # 운송장 입력 일시
    sender_info = Column(Text)  # JSON 형태로 보내는 사람 정보
    recipient_info = Column(Text)  # JSON 형태로 받는 사람 정보
    destination_address = Column(Text)  # JSON 형태로 주소 정보
    note = Column(String)  # 원장주문코드
    seller_note = Column(String)  # 판매자 메모
    orderer_note = Column(String)  # 구매자 배송 요청 사항
    tax_free = Column(Boolean, default=False)  # 면세 여부
    is_being_mediated = Column(Boolean, default=False)  # 중재 여부
    adjustments = Column(Text)  # JSON 형태로 조정 내역
    transactions = Column(Text)  # JSON 형태로 적립금 사용 내역
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 주문 상품 테이블 (주문 내 개별 상품)
class OrderProduct(Base):
    __tablename__ = "order_products"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, index=True, nullable=False)
    product_key = Column(String, index=True, nullable=False)  # 상품 키
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)  # 수량 반영 전 가격
    item_option_info = Column(Text)  # JSON 형태로 옵션 정보
    additional_attributes = Column(Text)  # JSON 형태로 추가 속성
    seller_note = Column(String)  # 주문 상품별 판매자 메모
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 1:1 문의 테이블
class QnaArticle(Base):
    __tablename__ = "qna_articles"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    qna_key = Column(String, index=True, nullable=False)  # QnA 글 key
    qna_id = Column(String, index=True)  # API ID
    type = Column(String, index=True)  # 문의글 타입
    is_secret = Column(Boolean, default=False)  # 비밀글 여부
    title = Column(String, nullable=False)  # 글 제목
    content = Column(Text, nullable=False)  # 글 내용
    files = Column(Text)  # JSON 형태로 첨부파일 URL
    related_item_key = Column(String)  # 연관 상품 키
    related_order_key = Column(String)  # 연관 주문 키
    recipient_name = Column(String)  # 주문자 이름
    comments = Column(Text)  # JSON 형태로 댓글 목록
    sub_articles = Column(Text)  # JSON 형태로 하위 글 목록
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 긴급 메시지 테이블
class EmergencyMessage(Base):
    __tablename__ = "emergency_messages"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    message_key = Column(String, index=True, nullable=False)  # 메시지 key
    message_id = Column(String, index=True)  # API ID
    type = Column(String, index=True)  # 메시지 타입
    item_key = Column(String)  # 관련 상품 키
    content = Column(Text, nullable=False)  # 메시지 내용
    url = Column(String)  # 관련 URL
    penalty = Column(Integer, default=0)  # 페널티 점수
    status = Column(String, index=True)  # 상태
    replied_at = Column(DateTime(timezone=True))  # 답변 시각
    reply = Column(Text)  # 답변 내용
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 알림 메모 테이블
class NoticeMemo(Base):
    __tablename__ = "notice_memos"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    memo_key = Column(String, index=True, nullable=False)  # 메모 key
    memo_id = Column(String, index=True)  # API ID
    type = Column(String, index=True)  # 메모 타입
    content = Column(Text, nullable=False)  # 메모 내용
    related_item_keys = Column(Text)  # JSON 형태로 연관 상품 키들
    related_order_keys = Column(Text)  # JSON 형태로 연관 주문 키들
    checked_at = Column(DateTime(timezone=True))  # 확인 시각
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 카테고리 테이블
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    category_key = Column(String, index=True, nullable=False)  # 카테고리 key
    category_id = Column(String, index=True)  # API ID
    name = Column(String, nullable=False)  # 카테고리 이름
    full_name = Column(String)  # 전체 이름 (상위 카테고리 포함)
    attributes = Column(Text)  # JSON 형태로 카테고리 속성
    parent_key = Column(String)  # 상위 카테고리 key
    children_keys = Column(Text)  # JSON 형태로 하위 카테고리 key들
    ancestors_keys = Column(Text)  # JSON 형태로 상위 카테고리 key들
    descendants_count = Column(Integer, default=0)  # 하위 카테고리 수
    level = Column(Integer, default=0)  # 카테고리 레벨 (ROOT=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 출고지 테이블
class ShippingLocation(Base):
    __tablename__ = "shipping_locations"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    location_key = Column(String, index=True, nullable=False)  # 출고지 key
    location_id = Column(String, index=True)  # API ID
    name = Column(String, nullable=False)  # 출고지 이름
    address = Column(Text)  # JSON 형태로 주소 정보
    contact_info = Column(Text)  # JSON 형태로 연락처 정보
    location_type = Column(String)  # 출고지 타입
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 기본 출고지 여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 반품지 테이블
class ReturnLocation(Base):
    __tablename__ = "return_locations"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    supplier_account_id = Column(Integer, index=True, nullable=False)
    location_key = Column(String, index=True, nullable=False)  # 반품지 key
    location_id = Column(String, index=True)  # API ID
    name = Column(String, nullable=False)  # 반품지 이름
    address = Column(Text)  # JSON 형태로 주소 정보
    contact_info = Column(Text)  # JSON 형태로 연락처 정보
    location_type = Column(String)  # 반품지 타입
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 기본 반품지 여부
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 생성"""
    async with async_session() as session:
        yield session

async def init_db():
    """비동기로 테이블 생성"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def update_supplier_accounts_table():
    """supplier_accounts 테이블에 쿠팡 인증 컬럼 추가"""
    # 동기 엔진 생성
    sync_engine = create_engine(settings.database_url.replace("asyncpg", "psycopg2"))

    try:
        with sync_engine.connect() as conn:
            # 쿠팡 인증 정보 컬럼 추가
            conn.execute(text("""
                ALTER TABLE supplier_accounts
                ADD COLUMN IF NOT EXISTS coupang_access_key VARCHAR,
                ADD COLUMN IF NOT EXISTS coupang_secret_key VARCHAR,
                ADD COLUMN IF NOT EXISTS coupang_vendor_id VARCHAR,
                ADD COLUMN IF NOT EXISTS default_margin_rate FLOAT DEFAULT 0.3,
                ADD COLUMN IF NOT EXISTS sync_enabled BOOLEAN DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP WITH TIME ZONE
            """))
            conn.commit()
            print("✅ supplier_accounts 테이블 업데이트 완료")
    except Exception as e:
        print(f"❌ 테이블 업데이트 실패: {e}")
    finally:
        sync_engine.dispose()

async def create_coupang_supplier():
    """쿠팡 공급사 및 계정 생성"""
    async with async_session() as session:
        # 쿠팡 공급사 생성
        supplier = Supplier(
            name="쿠팡 마켓플레이스",
            description="쿠팡 마켓플레이스 공급사",
            is_active=True
        )
        session.add(supplier)
        await session.flush()  # ID 생성을 위해

        # 쿠팡 계정 생성
        account = SupplierAccount(
            supplier_id=supplier.id,
            account_id="coupang_seller",
            account_password="dummy_password",
            access_token="dummy_token_coupang_seller_2025-09-28T05:31:52",
            token_expires_at=datetime.now() + timedelta(days=30),
            is_active=True,
            coupang_access_key="a825d408-a53d-4234-bdaa-be67acd67e5d",
            coupang_secret_key="856d45fae108cbf8029eaa0544bcbeed2a21f9d4",
            coupang_vendor_id="A01282691"
        )
        session.add(account)
        await session.commit()

        print(f"쿠팡 공급사 생성 완료 - ID: {supplier.id}, 계정 ID: {account.id}")
        return supplier.id, account.id

