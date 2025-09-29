# asyncpg를 먼저 import해서 async 드라이버 우선 로드
import asyncpg

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, create_engine, text
from sqlalchemy.sql import func
from typing import AsyncGenerator
import os
from datetime import datetime, timedelta
from app.core.config import get_settings

settings = get_settings()

# 엔진 생성을 지연시키는 함수
def get_async_engine():
    return create_async_engine(settings.database_url, echo=settings.debug)

def get_sync_engine():
    # 동기 엔진은 사용하지 않으므로 None 반환
    return None

# 지연 초기화를 위한 전역 변수
_async_engine = None
_sync_engine = None
_async_session_factory = None

def get_async_session_factory():
    global _async_engine, _async_session_factory
    if _async_engine is None:
        _async_engine = get_async_engine()
        _async_session_factory = async_sessionmaker(_async_engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory

# 기존 호환성을 위한 별칭 (지연 초기화)
class AsyncSessionProxy:
    def __call__(self):
        return get_async_session_factory()()
    
    def __getattr__(self, name):
        return getattr(get_async_session_factory(), name)

async_session = AsyncSessionProxy()

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

    # 기본 필드들
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, index=True, nullable=False)
    
    # 계정 정보
    account_name = Column(String, index=True, nullable=False)  # 계정명
    username = Column(String, nullable=False)  # 사용자명 (b00679540)
    password_encrypted = Column(String, nullable=False)  # 암호화된 비밀번호 (ehdgod1101*)
    
    # 토큰 관리
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime(timezone=True))
    
    # 상태 관리
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    
    # 통계 정보
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

    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

# 상품 테이블
class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)  # Integer -> String으로 변경
    supplier_id = Column(String, index=True, nullable=False)  # Integer -> String으로 변경

    # 기본 상품 정보 (실제 데이터베이스 스키마에 맞춤)
    item_key = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)  # name -> title로 변경
    brand = Column(String)
    category_id = Column(String)
    description = Column(Text)
    images = Column(Text)
    options = Column(Text)
    is_active = Column(Boolean, default=True)
    price_data = Column(Text)  # JSON 형태로 가격 정보
    stock_quantity = Column(Integer, default=0)
    max_stock_quantity = Column(Integer)
    
    # OwnerClan 특화 필드들
    supplier_product_id = Column(String)
    supplier_name = Column(String)
    supplier_url = Column(String)
    supplier_image_url = Column(String)
    estimated_shipping_days = Column(Integer, default=7)
    sync_status = Column(String, default="pending")
    last_synced_at = Column(DateTime(timezone=True))
    sync_error_message = Column(Text)
    
    # 추가 필드들
    hash_key = Column(String)
    normalized_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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

    id = Column(String, primary_key=True, index=True)  # String으로 변경
    name = Column(String, nullable=False)  # 카테고리 이름
    parent_id = Column(String, index=True)  # 상위 카테고리 ID
    level = Column(Integer, default=0)  # 카테고리 레벨 (ROOT=0)
    supplier_id = Column(String, index=True)  # String으로 변경
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
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session

async def init_db():
    """비동기로 테이블 생성"""
    async_engine = get_async_engine()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def update_supplier_accounts_table():
    """supplier_accounts 테이블에 쿠팡 인증 컬럼 추가"""
    # 비동기 엔진 사용
    async_engine = get_async_engine()

    try:
        async with async_engine.begin() as conn:
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
            account_name="Coupang Seller Account",
            username="coupang_seller",
            password_encrypted="dummy_password",
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

# 가격 정책 테이블
class PricePolicy(Base):
    __tablename__ = "price_policies"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 정책명
    description = Column(Text)  # 정책 설명
    supplier_id = Column(String, index=True)  # 공급사 ID
    category_id = Column(String, index=True)  # 카테고리 ID (선택적)
    
    # 가격 정책 설정
    base_margin_rate = Column(Float, default=0.3)  # 기본 마진율 (30%)
    min_margin_rate = Column(Float, default=0.1)   # 최소 마진율 (10%)
    max_margin_rate = Column(Float, default=0.5)   # 최대 마진율 (50%)
    
    # 가격 계산 규칙
    price_calculation_method = Column(String, default="margin")  # margin, markup, fixed
    rounding_method = Column(String, default="round")  # round, floor, ceiling
    
    # 할인/프리미엄 설정
    discount_rate = Column(Float, default=0.0)  # 할인율
    premium_rate = Column(Float, default=0.0)   # 프리미엄율
    
    # 가격 범위 제한
    min_price = Column(Integer, default=0)  # 최소 가격
    max_price = Column(Integer, default=10000000)  # 최대 가격
    
    # 상태 관리
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # 우선순위 (높을수록 우선)
    
    # 적용 조건 (JSON)
    conditions = Column(Text)  # JSON 형태로 조건 저장
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 가격 규칙 테이블
class PriceRule(Base):
    __tablename__ = "price_rules"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 규칙명
    description = Column(Text)  # 규칙 설명
    policy_id = Column(String, index=True)  # 가격 정책 ID
    
    # 규칙 조건
    rule_type = Column(String, nullable=False)  # condition, action
    field_name = Column(String)  # 적용 필드명 (price, margin_rate 등)
    operator = Column(String)  # 연산자 (>, <, =, >=, <=, !=, contains, in)
    value = Column(Text)  # 조건 값 (JSON 형태로 복잡한 값 저장)
    
    # 규칙 실행 설정
    priority = Column(Integer, default=0)  # 우선순위
    is_active = Column(Boolean, default=True)
    
    # 메타데이터
    created_by = Column(String)  # 생성자
    tags = Column(Text)  # JSON 형태로 태그 저장
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 가격 계산 이력 테이블
class PriceCalculationHistory(Base):
    __tablename__ = "price_calculation_history"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, index=True)  # 상품 ID
    policy_id = Column(String, index=True)  # 가격 정책 ID
    
    # 가격 정보
    original_price = Column(Integer)  # 원가
    calculated_price = Column(Integer)  # 계산된 가격
    margin_rate = Column(Float)  # 적용된 마진율
    discount_amount = Column(Integer, default=0)  # 할인 금액
    premium_amount = Column(Integer, default=0)  # 프리미엄 금액
    
    # 계산 과정 (JSON)
    calculation_steps = Column(Text)  # JSON 형태로 계산 과정 저장
    
    # 메타데이터
    calculation_method = Column(String)  # 계산 방법
    applied_rules = Column(Text)  # JSON 형태로 적용된 규칙들
    created_by = Column(String)  # 계산 실행자
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 재고 정보 테이블
class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, unique=True, index=True, nullable=False)  # 상품 ID
    supplier_id = Column(String, index=True)  # 공급사 ID
    
    # 재고 수량
    available_quantity = Column(Integer, default=0)  # 가용 재고
    reserved_quantity = Column(Integer, default=0)  # 예약된 재고
    total_quantity = Column(Integer, default=0)  # 총 재고 (가용 + 예약)
    
    # 재고 임계값
    low_stock_threshold = Column(Integer, default=10)  # 재고 부족 임계값
    out_of_stock_threshold = Column(Integer, default=0)  # 품절 임계값
    
    # 재고 상태
    stock_status = Column(String, default="in_stock")  # in_stock, low_stock, out_of_stock
    last_synced_at = Column(DateTime(timezone=True))  # 마지막 동기화 시각
    
    # 알림 설정
    enable_low_stock_alert = Column(Boolean, default=True)  # 재고 부족 알림 활성화
    last_alerted_at = Column(DateTime(timezone=True))  # 마지막 알림 시각
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# 재고 변동 이력 테이블
class InventoryHistory(Base):
    __tablename__ = "inventory_history"

    id = Column(String, primary_key=True, index=True)
    inventory_id = Column(String, index=True)  # 재고 ID
    product_id = Column(String, index=True)  # 상품 ID
    
    # 변동 정보
    change_type = Column(String, nullable=False)  # increase, decrease, sync, adjust
    quantity_before = Column(Integer)  # 변동 전 수량
    quantity_after = Column(Integer)  # 변동 후 수량
    quantity_changed = Column(Integer)  # 변동량
    
    # 변동 사유
    reason = Column(String)  # order, return, sync, manual, damaged 등
    reference_id = Column(String)  # 참조 ID (주문 ID, 동기화 ID 등)
    notes = Column(Text)  # 비고
    
    # 메타데이터
    created_by = Column(String)  # 변동 실행자
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 재고 알림 테이블
class InventoryAlert(Base):
    __tablename__ = "inventory_alerts"

    id = Column(String, primary_key=True, index=True)
    inventory_id = Column(String, index=True)  # 재고 ID
    product_id = Column(String, index=True)  # 상품 ID
    supplier_id = Column(String, index=True)  # 공급사 ID
    
    # 알림 정보
    alert_type = Column(String, nullable=False)  # low_stock, out_of_stock, critical
    alert_level = Column(String, default="warning")  # info, warning, error, critical
    
    # 재고 상태
    current_quantity = Column(Integer)  # 현재 재고
    threshold_quantity = Column(Integer)  # 임계값
    
    # 알림 메시지
    title = Column(String)  # 알림 제목
    message = Column(Text)  # 알림 메시지
    
    # 알림 상태
    is_read = Column(Boolean, default=False)  # 읽음 여부
    is_resolved = Column(Boolean, default=False)  # 해결 여부
    resolved_at = Column(DateTime(timezone=True))  # 해결 시각
    resolved_by = Column(String)  # 해결자
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# 재고 동기화 이력 테이블
class InventorySyncHistory(Base):
    __tablename__ = "inventory_sync_history"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, index=True)  # 공급사 ID
    
    # 동기화 정보
    sync_type = Column(String, default="manual")  # manual, auto, scheduled
    sync_status = Column(String, default="pending")  # pending, running, completed, failed
    
    # 동기화 결과
    total_products = Column(Integer, default=0)  # 총 상품 수
    synced_products = Column(Integer, default=0)  # 동기화된 상품 수
    failed_products = Column(Integer, default=0)  # 실패한 상품 수
    
    # 동기화 시간
    started_at = Column(DateTime(timezone=True))  # 시작 시각
    completed_at = Column(DateTime(timezone=True))  # 완료 시각
    duration_seconds = Column(Integer)  # 소요 시간 (초)
    
    # 에러 정보
    error_message = Column(Text)  # 에러 메시지
    error_details = Column(Text)  # JSON 형태의 상세 에러 정보
    
    # 메타데이터
    created_by = Column(String)  # 실행자
    created_at = Column(DateTime(timezone=True), server_default=func.now())

