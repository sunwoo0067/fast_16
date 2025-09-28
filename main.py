from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import uvicorn
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime, timedelta
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 모듈 import
from database import get_db, init_db, async_session, SupplierAccount
from services import SupplierService, SupplierAccountService, ProductService, CustomerService, CategoryService, CoupangWingService, CoupangProductService
from ownerclan_api import OwnerClanAPI, TokenManager

# Pydantic 모델
class SupplierCreate(BaseModel):
    name: str
    description: Optional[str] = None

class SupplierAccountCreate(BaseModel):
    supplier_id: int
    account_id: str
    password: str

class OwnerClanTest(BaseModel):
    supplier_id: int

class ProductCollectionRequest(BaseModel):
    supplier_id: int
    item_keys: Optional[List[str]] = None  # 특정 상품만 수집시 사용

class ProductQueryParams(BaseModel):
    limit: int = 50
    offset: int = 0

class ProductHistoryRequest(BaseModel):
    supplier_id: int
    item_key: Optional[str] = None
    days: int = 3  # 최근 N일간의 이력 조회

class RecentProductsRequest(BaseModel):
    supplier_id: int
    days: int = 3  # 최근 N일간의 변경 상품 수집

class OrderQueryParams(BaseModel):
    date_from: Optional[int] = None
    date_to: Optional[int] = None
    status: Optional[str] = None
    limit: int = 50

class OrderCreateRequest(BaseModel):
    supplier_id: int
    order_data: Dict[str, Any]

class OrderCancelRequest(BaseModel):
    supplier_id: int
    order_key: str

class OrderUpdateNotesRequest(BaseModel):
    supplier_id: int
    order_key: str
    note: str
    seller_notes: List[str]

class QnaQueryParams(BaseModel):
    search_type: Optional[str] = None
    receiver_name: Optional[str] = None
    date_from: Optional[int] = None
    date_to: Optional[int] = None
    limit: int = 50

class QnaCreateRequest(BaseModel):
    supplier_id: int
    qna_data: Dict[str, Any]

class EmergencyQueryParams(BaseModel):
    status: Optional[str] = None
    limit: int = 50

class NoticeQueryParams(BaseModel):
    notice_type: Optional[str] = None
    checked: Optional[bool] = None
    limit: int = 50

class RefundExchangeRequest(BaseModel):
    supplier_id: int
    order_key: str
    refund_data: Dict[str, Any]

class CategoryQueryParams(BaseModel):
    parent_key: Optional[str] = None
    include_tree: bool = False

class ShippingLocationQueryParams(BaseModel):
    limit: int = 50
    offset: int = 0

class ReturnLocationQueryParams(BaseModel):
    limit: int = 50
    offset: int = 0

class CoupangQueryParams(BaseModel):
    created_at_from: Optional[str] = None
    created_at_to: Optional[str] = None
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CategoryMetaParams(BaseModel):
    pass

class CategoryRecommendParams(BaseModel):
    keyword: str

class CategoryListParams(BaseModel):
    parent_category_id: Optional[str] = None
    has_children: Optional[bool] = None

class CategoryDetailParams(BaseModel):
    category_id: str

class CategoryValidateParams(BaseModel):
    category_id: str

class CoupangCredentialsCreate(BaseModel):
    supplier_id: int
    coupang_access_key: str
    coupang_secret_key: str
    coupang_vendor_id: str

class CoupangProductCreate(BaseModel):
    supplier_id: int
    product_data: Dict[str, Any]

class CoupangProductUpdate(BaseModel):
    supplier_id: int
    seller_product_id: str
    product_data: Dict[str, Any]
    requires_approval: bool = True

class CoupangProductQuery(BaseModel):
    supplier_id: int
    max: int = 50
    status: Optional[str] = None

class CoupangProductRegistrationStatusQuery(BaseModel):
    supplier_id: int
    max: int = 50
    status: Optional[str] = None
    created_at_from: Optional[str] = None
    created_at_to: Optional[str] = None
    updated_at_from: Optional[str] = None
    updated_at_to: Optional[str] = None

class CoupangProductPagedQuery(BaseModel):
    supplier_id: int
    max: int = 50
    status: Optional[str] = None
    vendor_item_id: Optional[str] = None
    seller_product_name: Optional[str] = None

class CoupangProductDateRangeQuery(BaseModel):
    supplier_id: int
    max: int = 50
    created_at_from: Optional[str] = None
    created_at_to: Optional[str] = None
    updated_at_from: Optional[str] = None
    updated_at_to: Optional[str] = None

class CoupangProductItemsQuery(BaseModel):
    supplier_id: int
    seller_product_id: str
    max: int = 50
    vendor_item_id: Optional[str] = None
    status: Optional[str] = None

class CoupangItemQuantityUpdate(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: str
    quantity: int

class CoupangItemPriceUpdate(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: str
    price: int
    sale_price: Optional[int] = None

class CoupangItemResumeRequest(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: str

class CoupangItemStopRequest(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: str

class CoupangItemDiscountUpdate(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: str
    discount_rate: float
    base_price: Optional[int] = None

class CoupangAutoOptionActivateRequest(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: Optional[str] = None  # None이면 전체 상품 단위

class CoupangAutoOptionDeactivateRequest(BaseModel):
    supplier_id: int
    seller_product_id: str
    item_id: Optional[str] = None  # None이면 전체 상품 단위

class CoupangShipmentListQuery(BaseModel):
    supplier_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangShipmentDetailQuery(BaseModel):
    supplier_id: int
    shipment_box_id: Optional[str] = None
    order_id: Optional[str] = None

class CoupangShipmentHistoryQuery(BaseModel):
    supplier_id: int
    shipment_box_id: str
    limit: int = 50
    offset: int = 0

class CoupangProductReadyRequest(BaseModel):
    supplier_id: int
    shipment_box_id: str
    data: Dict[str, Any]

class CoupangInvoiceRequest(BaseModel):
    supplier_id: int
    shipment_box_id: str
    data: Dict[str, Any]

class CoupangOrderCancelRequest(BaseModel):
    supplier_id: int
    order_id: str
    data: Dict[str, Any]

class CoupangLongDeliveryRequest(BaseModel):
    supplier_id: int
    order_id: str
    data: Dict[str, Any]

class CoupangReturnListQuery(BaseModel):
    supplier_id: int
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangReturnDetailQuery(BaseModel):
    supplier_id: int
    return_request_id: str

class CoupangReturnReceiptRequest(BaseModel):
    supplier_id: int
    return_request_id: str
    data: Dict[str, Any]

class CoupangReturnApproveRequest(BaseModel):
    supplier_id: int
    return_request_id: str
    data: Dict[str, Any]

class CoupangReturnHistoryQuery(BaseModel):
    supplier_id: int
    date_from: str
    date_to: str
    limit: int = 50
    offset: int = 0

class CoupangReturnHistoryByReceiptQuery(BaseModel):
    supplier_id: int
    receipt_number: str

class CoupangReturnInvoiceRequest(BaseModel):
    supplier_id: int
    return_request_id: str
    data: Dict[str, Any]

class CoupangExchangeListQuery(BaseModel):
    supplier_id: int
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangExchangeReceiptRequest(BaseModel):
    supplier_id: int
    exchange_request_id: str
    data: Dict[str, Any]

class CoupangExchangeRejectRequest(BaseModel):
    supplier_id: int
    exchange_request_id: str
    data: Dict[str, Any]

class CoupangExchangeInvoiceRequest(BaseModel):
    supplier_id: int
    exchange_request_id: str
    data: Dict[str, Any]

class CoupangProductInquiryQuery(BaseModel):
    supplier_id: int
    seller_product_id: str
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangProductInquiryReplyRequest(BaseModel):
    supplier_id: int
    seller_product_id: str
    inquiry_id: str
    data: Dict[str, Any]

class CoupangCSInquiryQuery(BaseModel):
    supplier_id: int
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangCSInquiryDetailQuery(BaseModel):
    supplier_id: int
    inquiry_id: str

class CoupangCSInquiryReplyRequest(BaseModel):
    supplier_id: int
    inquiry_id: str
    data: Dict[str, Any]

class CoupangCSInquiryConfirmRequest(BaseModel):
    supplier_id: int
    inquiry_id: str
    data: Dict[str, Any]

class CoupangSalesHistoryQuery(BaseModel):
    supplier_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

class CoupangPaymentHistoryQuery(BaseModel):
    supplier_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0

# 인증 스킴
security = HTTPBearer()

# FastAPI 앱 생성
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작시 실행
    await init_db()
    logger.info("앱 시작됨")

    # 백그라운드 토큰 갱신 작업 시작
    async def periodic_token_refresh():
        while True:
            try:
                async with async_session() as db:
                    token_manager = TokenManager(db, OwnerClanAPI())
                    results = await token_manager.refresh_all_tokens()
                    logger.info(f"정기 토큰 갱신 완료: {results}")
            except Exception as e:
                logger.error(f"정기 토큰 갱신 실패: {e}")

            # 24시간 대기
            await asyncio.sleep(24 * 60 * 60)

    # 백그라운드에서 실행
    asyncio.create_task(periodic_token_refresh())

    # 상품 수집 스케줄러 시작
    async def periodic_product_collection():
        while True:
            try:
                async with async_session() as db:
                    # 모든 활성화된 공급사의 상품을 수집
                    result = await db.execute(
                        select(SupplierAccount).where(SupplierAccount.is_active == True)
                    )
                    accounts = result.scalars().all()

                    for account in accounts:
                        try:
                            product_service = ProductService(db)
                            result = await product_service.collect_products(account.supplier_id)
                            logger.info(f"정기 상품 수집 완료 - supplier_id: {account.supplier_id}, 결과: {result}")
                        except Exception as e:
                            logger.error(f"공급사 {account.supplier_id} 상품 수집 실패: {e}")

            except Exception as e:
                logger.error(f"정기 상품 수집 실패: {e}")

            # 6시간마다 실행
            await asyncio.sleep(6 * 60 * 60)

    # 백그라운드에서 실행
    asyncio.create_task(periodic_product_collection())

    yield
    # 종료시 실행
    logger.info("앱 종료됨")

app = FastAPI(
    title="공급사 관리 시스템",
    description="오너클랜 API 연동 공급사 관리 시스템",
    version="1.0.0",
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

# 기본 헬스체크 엔드포인트
@app.get("/")
async def root():
    return {"message": "공급사 관리 시스템 API", "status": "running"}

# 공급사 관련 엔드포인트
@app.post("/suppliers")
async def create_supplier(supplier_data: SupplierCreate, db: AsyncSession = Depends(get_db)):
    """공급사 생성"""
    supplier_service = SupplierService(db)
    supplier = await supplier_service.create_supplier(
        name=supplier_data.name,
        description=supplier_data.description
    )
    return {"message": "공급사가 생성되었습니다", "supplier": supplier}

@app.get("/suppliers", response_model=List[dict])
async def get_suppliers(db: AsyncSession = Depends(get_db)):
    """공급사 목록 조회"""
    supplier_service = SupplierService(db)
    suppliers = await supplier_service.get_all_suppliers()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in suppliers
    ]

@app.get("/suppliers/{supplier_id}")
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """특정 공급사 조회"""
    supplier_service = SupplierService(db)
    supplier = await supplier_service.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="공급사를 찾을 수 없습니다")
    return {
        "id": supplier.id,
        "name": supplier.name,
        "description": supplier.description,
        "is_active": supplier.is_active,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None
    }

# 공급사계정 관련 엔드포인트
@app.post("/supplier-accounts")
async def create_supplier_account(
    account_data: SupplierAccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """공급사계정 생성"""
    try:
        print(f"계정 생성 시작: {account_data}")
        account_service = SupplierAccountService(db)
        print("계정 서비스 생성됨")
        account = await account_service.create_account(
            supplier_id=account_data.supplier_id,
            account_id=account_data.account_id,
            password=account_data.password
        )
        print(f"계정 생성 완료: {account}")
        return {"message": "공급사계정이 생성되었습니다", "account_id": account.id}
    except Exception as e:
        print(f"계정 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suppliers/{supplier_id}/accounts")
async def get_supplier_accounts(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """공급사의 계정 목록 조회"""
    account_service = SupplierAccountService(db)
    accounts = await account_service.get_accounts_by_supplier(supplier_id)
    return {
        "accounts": [
            {
                "id": acc.id,
                "account_id": acc.account_id,
                "token_expires_at": acc.token_expires_at.isoformat() if acc.token_expires_at else None,
                "last_used_at": acc.last_used_at.isoformat() if acc.last_used_at else None,
                "is_active": acc.is_active
            }
            for acc in accounts
        ]
    }

@app.post("/test-ownerclan-connection")
async def test_ownerclan_connection(test_data: OwnerClanTest, db: AsyncSession = Depends(get_db)):
    """오너클랜 API 연결 테스트"""
    account_service = SupplierAccountService(db)
    result = await account_service.test_ownerclan_connection(test_data.supplier_id)
    return result

# 토큰 관리 엔드포인트
@app.post("/token/refresh-all")
async def refresh_all_tokens(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """모든 토큰 일괄 갱신"""
    token_manager = TokenManager(db, OwnerClanAPI())

    # 백그라운드에서 실행
    background_tasks.add_task(_refresh_all_tokens_background, token_manager)

    return {"message": "토큰 갱신 작업이 백그라운드에서 시작되었습니다"}

@app.get("/token/status")
async def get_token_status(db: AsyncSession = Depends(get_db)):
    """토큰 상태 조회"""
    result = await db.execute(
        select(SupplierAccount).where(SupplierAccount.is_active == True)
    )
    accounts = result.scalars().all()

    now = datetime.now()
    status_summary = {
        "total": len(accounts),
        "valid": 0,
        "expired": 0,
        "expiring_soon": 0,
        "no_token": 0
    }

    account_details = []
    for account in accounts:
        expires_at = account.token_expires_at
        has_token = bool(account.access_token)

        if not has_token:
            status_summary["no_token"] += 1
            status = "no_token"
        elif expires_at and expires_at <= now:
            status_summary["expired"] += 1
            status = "expired"
        elif expires_at and now + timedelta(days=5) >= expires_at:
            status_summary["expiring_soon"] += 1
            status = "expiring_soon"
        else:
            status_summary["valid"] += 1
            status = "valid"

        account_details.append({
            "supplier_id": account.supplier_id,
            "account_id": account.account_id,
            "status": status,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
        })

    return {
        "summary": status_summary,
        "accounts": account_details
    }

@app.post("/token/refresh/{supplier_id}")
async def refresh_supplier_token(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """특정 공급사의 토큰 갱신"""
    token_manager = TokenManager(db, OwnerClanAPI())
    result = await token_manager.get_valid_token(supplier_id)

    if result:
        return {"message": "토큰이 성공적으로 갱신되었습니다", "supplier_id": supplier_id}
    else:
        raise HTTPException(status_code=400, detail="토큰 갱신에 실패했습니다")

@app.get("/token/usage/{supplier_id}")
async def get_token_usage_stats(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """특정 공급사의 토큰 사용 통계 조회"""
    token_manager = TokenManager(db, OwnerClanAPI())
    stats = await token_manager.get_token_usage_stats(supplier_id)

    if not stats:
        raise HTTPException(status_code=404, detail="공급사 계정을 찾을 수 없습니다")

    return {"usage_stats": stats}

@app.get("/token/usage")
async def get_all_token_usage_stats(db: AsyncSession = Depends(get_db)):
    """모든 공급사의 토큰 사용 통계 조회"""
    result = await db.execute(
        select(SupplierAccount).where(SupplierAccount.is_active == True)
    )
    accounts = result.scalars().all()

    all_stats = []
    for account in accounts:
        stats = {
            "supplier_id": account.supplier_id,
            "account_id": account.account_id,
            "usage_count": account.usage_count,
            "total_requests": account.total_requests,
            "successful_requests": account.successful_requests,
            "failed_requests": account.failed_requests,
            "success_rate": (account.successful_requests / account.total_requests * 100) if account.total_requests > 0 else 0,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
            "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None
        }
        all_stats.append(stats)

    return {"all_usage_stats": all_stats}

# 상품 수집 API
@app.post("/products/collect")
async def collect_products(
    collection_request: ProductCollectionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """상품 수집 (백그라운드에서 실행)"""
    product_service = ProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(_collect_products_background, product_service, collection_request)

    return {"message": "상품 수집 작업이 백그라운드에서 시작되었습니다", "supplier_id": collection_request.supplier_id}

@app.get("/products/{supplier_id}")
async def get_products(
    supplier_id: int,
    params: ProductQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """공급사의 상품 목록 조회"""
    product_service = ProductService(db)
    products = await product_service.get_products(
        supplier_id=supplier_id,
        limit=params.limit,
        offset=params.offset
    )
    return {"products": products}

@app.get("/products/{supplier_id}/stats")
async def get_product_stats(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """공급사의 상품 통계 조회"""
    product_service = ProductService(db)
    stats = await product_service.get_product_stats(supplier_id)
    return {"stats": stats}

@app.post("/products/history")
async def get_product_history(history_request: ProductHistoryRequest, db: AsyncSession = Depends(get_db)):
    """상품 변경 이력 조회"""
    product_service = ProductService(db)
    result = await product_service.get_product_history(
        supplier_id=history_request.supplier_id,
        item_key=history_request.item_key,
        days=history_request.days
    )
    return result

@app.post("/products/collect-recent")
async def collect_recent_products(recent_request: RecentProductsRequest, db: AsyncSession = Depends(get_db)):
    """최근 N일간 변경된 상품들을 수집"""
    product_service = ProductService(db)
    result = await product_service.collect_recent_products(
        supplier_id=recent_request.supplier_id,
        days=recent_request.days
    )
    return result

# 주문 관리 API
@app.get("/orders/{supplier_id}/{order_key}")
async def get_order(supplier_id: int, order_key: str, db: AsyncSession = Depends(get_db)):
    """단일 주문 정보 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_order(supplier_id, order_key)
    return result

@app.get("/orders/{supplier_id}")
async def get_orders(supplier_id: int, params: OrderQueryParams = Depends(), db: AsyncSession = Depends(get_db)):
    """복수 주문 내역 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_orders(
        supplier_id=supplier_id,
        date_from=params.date_from,
        date_to=params.date_to,
        status=params.status,
        limit=params.limit
    )
    return result

@app.post("/orders/simulate")
async def simulate_order(order_request: OrderCreateRequest, db: AsyncSession = Depends(get_db)):
    """주문 시뮬레이션"""
    customer_service = CustomerService(db)
    result = await customer_service.simulate_order(
        supplier_id=order_request.supplier_id,
        order_data=order_request.order_data
    )
    return result

@app.post("/orders/create")
async def create_order(order_request: OrderCreateRequest, db: AsyncSession = Depends(get_db)):
    """새 주문 생성"""
    customer_service = CustomerService(db)
    result = await customer_service.create_order(
        supplier_id=order_request.supplier_id,
        order_data=order_request.order_data
    )
    return result

@app.post("/orders/cancel")
async def cancel_order(cancel_request: OrderCancelRequest, db: AsyncSession = Depends(get_db)):
    """주문 취소"""
    customer_service = CustomerService(db)
    result = await customer_service.cancel_order(
        supplier_id=cancel_request.supplier_id,
        order_key=cancel_request.order_key
    )
    return result

@app.post("/orders/update-notes")
async def update_order_notes(update_request: OrderUpdateNotesRequest, db: AsyncSession = Depends(get_db)):
    """주문 메모 업데이트"""
    customer_service = CustomerService(db)
    result = await customer_service.update_order_notes(
        supplier_id=update_request.supplier_id,
        order_key=update_request.order_key,
        note=update_request.note,
        seller_notes=update_request.seller_notes
    )
    return result

# 고객 서비스 API
@app.get("/qna/{supplier_id}/{qna_key}")
async def get_qna_article(supplier_id: int, qna_key: str, db: AsyncSession = Depends(get_db)):
    """단일 1:1 문의 게시판 글 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_qna_article(supplier_id, qna_key)
    return result

@app.get("/qna/{supplier_id}")
async def get_qna_articles(supplier_id: int, params: QnaQueryParams = Depends(), db: AsyncSession = Depends(get_db)):
    """복수 1:1 문의 게시판 글 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_qna_articles(
        supplier_id=supplier_id,
        search_type=params.search_type,
        receiver_name=params.receiver_name,
        date_from=params.date_from,
        date_to=params.date_to,
        limit=params.limit
    )
    return result

@app.post("/qna/create")
async def create_qna_article(qna_request: QnaCreateRequest, db: AsyncSession = Depends(get_db)):
    """1:1 문의글 작성"""
    customer_service = CustomerService(db)
    result = await customer_service.create_qna_article(
        supplier_id=qna_request.supplier_id,
        qna_data=qna_request.qna_data
    )
    return result

@app.get("/emergency/{supplier_id}/{message_key}")
async def get_emergency_message(supplier_id: int, message_key: str, db: AsyncSession = Depends(get_db)):
    """단일 긴급 메시지 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_emergency_message(supplier_id, message_key)
    return result

@app.get("/emergency/{supplier_id}")
async def get_emergency_messages(supplier_id: int, params: EmergencyQueryParams = Depends(), db: AsyncSession = Depends(get_db)):
    """복수 긴급 메시지 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_emergency_messages(
        supplier_id=supplier_id,
        status=params.status,
        limit=params.limit
    )
    return result

@app.get("/notices/{supplier_id}/{memo_key}")
async def get_notice_memo(supplier_id: int, memo_key: str, db: AsyncSession = Depends(get_db)):
    """단일 알림 메모 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_notice_memo(supplier_id, memo_key)
    return result

@app.get("/notices/{supplier_id}")
async def get_notice_memos(supplier_id: int, params: NoticeQueryParams = Depends(), db: AsyncSession = Depends(get_db)):
    """복수 알림 메모 조회"""
    customer_service = CustomerService(db)
    result = await customer_service.get_notice_memos(
        supplier_id=supplier_id,
        notice_type=params.notice_type,
        checked=params.checked,
        limit=params.limit
    )
    return result

@app.post("/orders/refund-exchange")
async def request_refund_exchange(refund_request: RefundExchangeRequest, db: AsyncSession = Depends(get_db)):
    """주문 상품 반품/교환 신청"""
    customer_service = CustomerService(db)
    result = await customer_service.request_refund_exchange(
        supplier_id=refund_request.supplier_id,
        order_key=refund_request.order_key,
        refund_data=refund_request.refund_data
    )
    return result

# 카테고리 관리 API
@app.get("/categories/{supplier_id}/tree")
async def get_categories_tree(supplier_id: int, parent_key: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """카테고리 트리 조회"""
    category_service = CategoryService(db)
    result = await category_service.get_all_categories(supplier_id, parent_key)
    return result

@app.get("/categories/{supplier_id}/{category_key}")
async def get_category(supplier_id: int, category_key: str, db: AsyncSession = Depends(get_db)):
    """단일 카테고리 정보 조회"""
    category_service = CategoryService(db)
    result = await category_service.get_category(supplier_id, category_key)
    return result

@app.get("/categories/{supplier_id}/root")
async def get_root_categories(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """최상위 카테고리들 조회"""
    category_service = CategoryService(db)
    result = await category_service.get_root_categories(supplier_id)
    return result

# 쿠팡윙 API 엔드포인트
@app.post("/coupang/credentials")
async def set_coupangwing_credentials(
    credentials: CoupangCredentialsCreate,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡윙 API 인증 정보 설정"""
    try:
        # 기존 계정 조회
        result = await db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == credentials.supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="공급사 계정을 찾을 수 없습니다")

        # 쿠팡윙 인증 정보 업데이트 (API 키와 벤더 ID만 사용)
        await db.execute(
            update(SupplierAccount).where(
                SupplierAccount.id == account.id
            ).values(
                coupang_access_key=credentials.coupang_access_key,  # API 키
                coupang_vendor_id=credentials.coupang_vendor_id    # 벤더 ID
            )
        )
        await db.commit()

        return {
            "message": "쿠팡윙 인증 정보가 성공적으로 설정되었습니다",
            "supplier_id": credentials.supplier_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"쿠팡윙 인증 정보 설정 실패: {str(e)}")

@app.post("/coupang/test-connection")
async def test_coupangwing_connection(test_data: OwnerClanTest, db: AsyncSession = Depends(get_db)):
    """쿠팡윙 API 연결 테스트"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.test_coupangwing_connection(test_data.supplier_id)
    return result

@app.get("/coupang/{supplier_id}/vendor")
async def get_coupangwing_vendor_info(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """쿠팡윙 벤더 정보 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_vendor_info(supplier_id)
    return result

@app.get("/coupang/{supplier_id}/products")
async def get_coupangwing_products(
    supplier_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡윙 상품 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_products(
        supplier_id=supplier_id,
        limit=limit,
        offset=offset
    )
    return result

@app.get("/coupang/{supplier_id}/orders")
async def get_coupangwing_orders(
    supplier_id: int,
    params: CoupangQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡윙 주문 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_orders(
        supplier_id=supplier_id,
        created_at_from=params.created_at_from,
        created_at_to=params.created_at_to,
        status=params.status,
        limit=params.limit
    )
    return result

@app.get("/coupang/{supplier_id}/return-requests")
async def get_coupangwing_return_requests(
    supplier_id: int,
    params: CoupangQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡윙 반품 요청 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_requests(
        supplier_id=supplier_id,
        created_at_from=params.created_at_from,
        created_at_to=params.created_at_to,
        status=params.status,
        limit=params.limit
    )
    return result

# 출고지 및 반품지 관리 API
@app.get("/shipping-locations/{supplier_id}")
async def get_shipping_locations(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """출고지 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_shipping_locations(supplier_id)
    return result

@app.get("/return-locations/{supplier_id}")
async def get_return_locations(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """반품지 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_locations(supplier_id)
    return result

@app.get("/return-locations/{supplier_id}/{location_key}")
async def get_return_location_detail(supplier_id: int, location_key: str, db: AsyncSession = Depends(get_db)):
    """반품지 단건 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_location_detail(supplier_id, location_key)
    return result

# 쿠팡윙 고급 카테고리 API
@app.get("/coupang/{supplier_id}/categories/meta")
async def get_coupangwing_category_meta(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """카테고리 메타정보 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_category_meta_info(supplier_id)
    return result

@app.post("/coupang/{supplier_id}/categories/recommend")
async def recommend_coupangwing_categories(supplier_id: int, params: CategoryRecommendParams, db: AsyncSession = Depends(get_db)):
    """카테고리 추천"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.recommend_categories(supplier_id, params.keyword)
    return result

@app.get("/coupang/{supplier_id}/categories/auto-matching/consent")
async def check_coupangwing_category_auto_matching(supplier_id: int, db: AsyncSession = Depends(get_db)):
    """카테고리 자동 매칭 서비스 동의 확인"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.check_category_auto_matching(supplier_id)
    return result

@app.get("/coupang/{supplier_id}/categories/list")
async def get_coupangwing_categories_list(supplier_id: int, params: CategoryListParams = Depends(), db: AsyncSession = Depends(get_db)):
    """카테고리 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_categories_list(
        supplier_id=supplier_id,
        parent_category_id=params.parent_category_id,
        has_children=params.has_children
    )
    return result

@app.get("/coupang/{supplier_id}/categories/{category_id}")
async def get_coupangwing_category_detail(supplier_id: int, category_id: str, db: AsyncSession = Depends(get_db)):
    """카테고리 단건 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_category_detail(supplier_id, category_id)
    return result

@app.post("/coupang/{supplier_id}/categories/validate")
async def validate_coupangwing_category(supplier_id: int, params: CategoryValidateParams, db: AsyncSession = Depends(get_db)):
    """카테고리 유효성 검사"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.validate_category(supplier_id, params.category_id)
    return result

# 백그라운드 작업 함수
async def _collect_products_background(product_service: ProductService, collection_request: ProductCollectionRequest):
    """백그라운드에서 상품 수집"""
    logger.info(f"백그라운드 상품 수집 시작: supplier_id={collection_request.supplier_id}")
    try:
        result = await product_service.collect_products(
            supplier_id=collection_request.supplier_id,
            item_keys=collection_request.item_keys
        )
        logger.info(f"상품 수집 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 상품 수집 실패: {e}")

# 백그라운드 작업 함수
async def _refresh_all_tokens_background(token_manager: TokenManager):
    """백그라운드에서 모든 토큰 갱신"""
    logger.info("백그라운드 토큰 갱신 작업 시작")
    try:
        results = await token_manager.refresh_all_tokens()
        logger.info(f"토큰 갱신 완료: {results}")
    except Exception as e:
        logger.error(f"백그라운드 토큰 갱신 실패: {e}")

# 쿠팡 상품 API 엔드포인트
@app.post("/coupang/products/create")
async def create_coupang_product(
    product_request: CoupangProductCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 생성"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(_create_coupang_product_background, coupang_service, product_request)

    return {"message": "쿠팡 상품 생성 작업이 백그라운드에서 시작되었습니다", "supplier_id": product_request.supplier_id}

@app.post("/coupang/products/{seller_product_id}/approve")
async def request_coupang_approval(
    seller_product_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 승인 요청"""
    # supplier_id를 쿼리 파라미터나 헤더에서 받아야 하지만 여기서는 간단히 처리
    # 실제 구현에서는 인증 정보를 통해 supplier_id를 확인해야 합니다
    supplier_id = 1  # 임시로 하드코딩

    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(_request_coupang_approval_background, coupang_service, supplier_id, seller_product_id)

    return {"message": "쿠팡 상품 승인 요청 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id}

@app.get("/coupang/products")
async def get_coupang_products(
    query: CoupangProductQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 목록 조회"""
    coupang_service = CoupangProductService(db)
    result = await coupang_service.get_products(
        supplier_id=query.supplier_id,
        max=query.max,
        status=query.status
    )
    return result

@app.get("/coupang/products/{seller_product_id}")
async def get_coupang_product(
    seller_product_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 단일 상품 조회"""
    # supplier_id를 쿼리 파라미터나 헤더에서 받아야 하지만 여기서는 간단히 처리
    supplier_id = 1  # 임시로 하드코딩

    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(_get_coupang_product_background, coupang_service, supplier_id, seller_product_id)

    return {"message": "쿠팡 상품 조회 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id}

@app.put("/coupang/products/{seller_product_id}")
async def update_coupang_product(
    seller_product_id: str,
    update_request: CoupangProductUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 수정"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _update_coupang_product_background,
        coupang_service,
        update_request.supplier_id,
        seller_product_id,
        update_request.product_data,
        update_request.requires_approval
    )

    return {"message": "쿠팡 상품 수정 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id}

@app.get("/coupang/products/registration-status")
async def get_coupang_product_registration_status(
    query: CoupangProductRegistrationStatusQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 등록 현황 조회"""
    coupang_service = CoupangProductService(db)
    result = await coupang_service.get_product_registration_status(
        supplier_id=query.supplier_id,
        max=query.max,
        status=query.status,
        created_at_from=query.created_at_from,
        created_at_to=query.created_at_to,
        updated_at_from=query.updated_at_from,
        updated_at_to=query.updated_at_to
    )
    return result

@app.get("/coupang/products/paged")
async def get_coupang_products_paged(
    query: CoupangProductPagedQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 페이징 조회"""
    coupang_service = CoupangProductService(db)
    result = await coupang_service.get_products_paged(
        supplier_id=query.supplier_id,
        max=query.max,
        status=query.status,
        vendor_item_id=query.vendor_item_id,
        seller_product_name=query.seller_product_name
    )
    return result

@app.get("/coupang/products/date-range")
async def get_coupang_products_by_date_range(
    query: CoupangProductDateRangeQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 날짜 구간별 조회"""
    coupang_service = CoupangProductService(db)
    result = await coupang_service.get_products_by_date_range(
        supplier_id=query.supplier_id,
        max=query.max,
        created_at_from=query.created_at_from,
        created_at_to=query.created_at_to,
        updated_at_from=query.updated_at_from,
        updated_at_to=query.updated_at_to
    )
    return result

@app.get("/coupang/products/{seller_product_id}/summary")
async def get_coupang_product_summary(
    seller_product_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 요약 정보 조회"""
    # supplier_id를 쿼리 파라미터나 헤더에서 받아야 하지만 여기서는 간단히 처리
    supplier_id = 1  # 임시로 하드코딩

    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(_get_coupang_product_summary_background, coupang_service, supplier_id, seller_product_id)

    return {"message": "쿠팡 상품 요약 정보 조회 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id}

@app.get("/coupang/products/{seller_product_id}/items")
async def get_coupang_product_items(
    seller_product_id: str,
    query: CoupangProductItemsQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 수량/가격/상태 조회"""
    coupang_service = CoupangProductService(db)
    result = await coupang_service.get_product_items_status(
        supplier_id=query.supplier_id,
        seller_product_id=seller_product_id,
        max=query.max,
        vendor_item_id=query.vendor_item_id,
        status=query.status
    )
    return result

@app.put("/coupang/products/{seller_product_id}/items/{item_id}/quantity")
async def update_coupang_item_quantity(
    seller_product_id: str,
    item_id: str,
    update_request: CoupangItemQuantityUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 수량 변경"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _update_coupang_item_quantity_background,
        coupang_service,
        update_request.supplier_id,
        seller_product_id,
        item_id,
        update_request.quantity
    )

    return {"message": "쿠팡 상품 아이템 수량 변경 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "item_id": item_id}

@app.put("/coupang/products/{seller_product_id}/items/{item_id}/price")
async def update_coupang_item_price(
    seller_product_id: str,
    item_id: str,
    update_request: CoupangItemPriceUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 가격 변경"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _update_coupang_item_price_background,
        coupang_service,
        update_request.supplier_id,
        seller_product_id,
        item_id,
        update_request.price,
        update_request.sale_price
    )

    return {"message": "쿠팡 상품 아이템 가격 변경 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "item_id": item_id}

@app.post("/coupang/products/{seller_product_id}/items/{item_id}/resume")
async def resume_coupang_item_sale(
    seller_product_id: str,
    item_id: str,
    resume_request: CoupangItemResumeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 판매 재개"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _resume_coupang_item_sale_background,
        coupang_service,
        resume_request.supplier_id,
        seller_product_id,
        item_id
    )

    return {"message": "쿠팡 상품 아이템 판매 재개 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "item_id": item_id}

@app.post("/coupang/products/{seller_product_id}/items/{item_id}/stop")
async def stop_coupang_item_sale(
    seller_product_id: str,
    item_id: str,
    stop_request: CoupangItemStopRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 판매 중지"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _stop_coupang_item_sale_background,
        coupang_service,
        stop_request.supplier_id,
        seller_product_id,
        item_id
    )

    return {"message": "쿠팡 상품 아이템 판매 중지 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "item_id": item_id}

@app.put("/coupang/products/{seller_product_id}/items/{item_id}/price-by-discount-rate")
async def update_coupang_item_price_by_discount_rate(
    seller_product_id: str,
    item_id: str,
    discount_request: CoupangItemDiscountUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 상품 아이템별 할인율 기준 가격 변경"""
    coupang_service = CoupangProductService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _update_coupang_item_price_by_discount_rate_background,
        coupang_service,
        discount_request.supplier_id,
        seller_product_id,
        item_id,
        discount_request.discount_rate,
        discount_request.base_price
    )

    return {"message": "쿠팡 상품 아이템 할인율 기준 가격 변경 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "item_id": item_id}

@app.post("/coupang/products/{seller_product_id}/auto-generated-options/activate")
async def activate_coupang_auto_generated_options(
    seller_product_id: str,
    activate_request: CoupangAutoOptionActivateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 자동생성옵션 활성화"""
    coupang_service = CoupangProductService(db)

    if activate_request.item_id:
        # 옵션 상품 단위 활성화
        background_tasks.add_task(
            _activate_coupang_auto_generated_options_by_item_background,
            coupang_service,
            activate_request.supplier_id,
            seller_product_id,
            activate_request.item_id
        )
        return {"message": "쿠팡 자동생성옵션 활성화 작업이 백그라운드에서 시작되었습니다 (옵션 상품 단위)", "seller_product_id": seller_product_id, "item_id": activate_request.item_id}
    else:
        # 전체 상품 단위 활성화
        background_tasks.add_task(
            _activate_coupang_auto_generated_options_by_product_background,
            coupang_service,
            activate_request.supplier_id,
            seller_product_id
        )
        return {"message": "쿠팡 자동생성옵션 활성화 작업이 백그라운드에서 시작되었습니다 (전체 상품 단위)", "seller_product_id": seller_product_id}

@app.post("/coupang/products/{seller_product_id}/auto-generated-options/deactivate")
async def deactivate_coupang_auto_generated_options(
    seller_product_id: str,
    deactivate_request: CoupangAutoOptionDeactivateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 자동생성옵션 비활성화"""
    coupang_service = CoupangProductService(db)

    if deactivate_request.item_id:
        # 옵션 상품 단위 비활성화
        background_tasks.add_task(
            _deactivate_coupang_auto_generated_options_by_item_background,
            coupang_service,
            deactivate_request.supplier_id,
            seller_product_id,
            deactivate_request.item_id
        )
        return {"message": "쿠팡 자동생성옵션 비활성화 작업이 백그라운드에서 시작되었습니다 (옵션 상품 단위)", "seller_product_id": seller_product_id, "item_id": deactivate_request.item_id}
    else:
        # 전체 상품 단위 비활성화
        background_tasks.add_task(
            _deactivate_coupang_auto_generated_options_by_product_background,
            coupang_service,
            deactivate_request.supplier_id,
            seller_product_id
        )
        return {"message": "쿠팡 자동생성옵션 비활성화 작업이 백그라운드에서 시작되었습니다 (전체 상품 단위)", "seller_product_id": seller_product_id}

# 발주서 및 배송 처리 API 엔드포인트
@app.get("/coupang/shipments/daily")
async def get_coupang_shipment_list_daily(
    query: CoupangShipmentListQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """발주서 목록 조회 (일단위 페이징)"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_shipment_list_daily(
        supplier_id=query.supplier_id,
        date_from=query.date_from,
        date_to=query.date_to,
        status=query.status,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.get("/coupang/shipments/minute")
async def get_coupang_shipment_list_minute(
    query: CoupangShipmentListQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """발주서 목록 조회 (분단위 전체)"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_shipment_list_minute(
        supplier_id=query.supplier_id,
        date_from=query.date_from,
        date_to=query.date_to,
        status=query.status
    )
    return result

@app.get("/coupang/shipments/detail")
async def get_coupang_shipment_detail(
    query: CoupangShipmentDetailQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """발주서 단건 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    if query.shipment_box_id:
        result = await coupangwing_service.get_shipment_by_shipment_box_id(
            supplier_id=query.supplier_id,
            shipment_box_id=query.shipment_box_id
        )
    elif query.order_id:
        result = await coupangwing_service.get_shipment_by_order_id(
            supplier_id=query.supplier_id,
            order_id=query.order_id
        )
    else:
        return {"status": "error", "message": "shipment_box_id 또는 order_id 중 하나는 필수입니다"}

    return result

@app.get("/coupang/shipments/{shipment_box_id}/history")
async def get_coupang_shipment_history(
    shipment_box_id: str,
    query: CoupangShipmentHistoryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """배송상태 변경 히스토리 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_shipment_status_history(
        supplier_id=query.supplier_id,
        shipment_box_id=shipment_box_id,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.post("/coupang/shipments/{shipment_box_id}/product-ready")
async def process_coupang_product_ready(
    shipment_box_id: str,
    request: CoupangProductReadyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """상품준비중 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _process_coupang_product_ready_background,
        coupangwing_service,
        request.supplier_id,
        shipment_box_id,
        request.data
    )

    return {"message": "상품준비중 처리 작업이 백그라운드에서 시작되었습니다", "shipment_box_id": shipment_box_id}

@app.post("/coupang/shipments/{shipment_box_id}/invoice")
async def upload_coupang_invoice(
    shipment_box_id: str,
    request: CoupangInvoiceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """송장업로드 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _upload_coupang_invoice_background,
        coupangwing_service,
        request.supplier_id,
        shipment_box_id,
        request.data
    )

    return {"message": "송장업로드 처리 작업이 백그라운드에서 시작되었습니다", "shipment_box_id": shipment_box_id}

@app.put("/coupang/shipments/{shipment_box_id}/invoice")
async def update_coupang_invoice(
    shipment_box_id: str,
    request: CoupangInvoiceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """송장업데이트 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _update_coupang_invoice_background,
        coupangwing_service,
        request.supplier_id,
        shipment_box_id,
        request.data
    )

    return {"message": "송장업데이트 처리 작업이 백그라운드에서 시작되었습니다", "shipment_box_id": shipment_box_id}

@app.post("/coupang/shipments/{shipment_box_id}/shipping-stopped")
async def process_coupang_shipping_stopped(
    shipment_box_id: str,
    request: CoupangProductReadyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """출고중지완료 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _process_coupang_shipping_stopped_background,
        coupangwing_service,
        request.supplier_id,
        shipment_box_id,
        request.data
    )

    return {"message": "출고중지완료 처리 작업이 백그라운드에서 시작되었습니다", "shipment_box_id": shipment_box_id}

@app.post("/coupang/shipments/{shipment_box_id}/already-shipped")
async def process_coupang_already_shipped(
    shipment_box_id: str,
    request: CoupangProductReadyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """이미출고 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _process_coupang_already_shipped_background,
        coupangwing_service,
        request.supplier_id,
        shipment_box_id,
        request.data
    )

    return {"message": "이미출고 처리 작업이 백그라운드에서 시작되었습니다", "shipment_box_id": shipment_box_id}

@app.post("/coupang/orders/{order_id}/cancel")
async def cancel_coupang_order_item(
    order_id: str,
    request: CoupangOrderCancelRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """주문 상품 취소 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _cancel_coupang_order_item_background,
        coupangwing_service,
        request.supplier_id,
        order_id,
        request.data
    )

    return {"message": "주문 상품 취소 처리 작업이 백그라운드에서 시작되었습니다", "order_id": order_id}

@app.post("/coupang/orders/{order_id}/complete-long-delivery")
async def complete_coupang_long_delivery(
    order_id: str,
    request: CoupangLongDeliveryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """장기미배송 배송완료 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _complete_coupang_long_delivery_background,
        coupangwing_service,
        request.supplier_id,
        order_id,
        request.data
    )

    return {"message": "장기미배송 배송완료 처리 작업이 백그라운드에서 시작되었습니다", "order_id": order_id}

# 반품 및 교환 처리 API 엔드포인트
@app.get("/coupang/returns")
async def get_coupang_return_requests(
    query: CoupangReturnListQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """반품 취소 요청 목록 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_requests(
        supplier_id=query.supplier_id,
        status=query.status,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.get("/coupang/returns/{return_request_id}")
async def get_coupang_return_request_detail(
    return_request_id: str,
    query: CoupangReturnDetailQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """반품요청 단건 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_request_detail(
        supplier_id=query.supplier_id,
        return_request_id=return_request_id
    )
    return result

@app.post("/coupang/returns/{return_request_id}/receipt")
async def confirm_coupang_return_receipt(
    return_request_id: str,
    request: CoupangReturnReceiptRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """반품상품 입고 확인처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _confirm_coupang_return_receipt_background,
        coupangwing_service,
        request.supplier_id,
        return_request_id,
        request.data
    )

    return {"message": "반품상품 입고 확인처리 작업이 백그라운드에서 시작되었습니다", "return_request_id": return_request_id}

@app.post("/coupang/returns/{return_request_id}/approve")
async def approve_coupang_return_request(
    return_request_id: str,
    request: CoupangReturnApproveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """반품요청 승인 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _approve_coupang_return_request_background,
        coupangwing_service,
        request.supplier_id,
        return_request_id,
        request.data
    )

    return {"message": "반품요청 승인 처리 작업이 백그라운드에서 시작되었습니다", "return_request_id": return_request_id}

@app.get("/coupang/returns/history")
async def get_coupang_return_history_by_period(
    query: CoupangReturnHistoryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """반품철회 이력 기간별 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_withdrawal_history_by_period(
        supplier_id=query.supplier_id,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.get("/coupang/returns/history/{receipt_number}")
async def get_coupang_return_history_by_receipt(
    receipt_number: str,
    query: CoupangReturnHistoryByReceiptQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """반품철회 이력 접수번호로 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_return_withdrawal_history_by_receipt_number(
        supplier_id=query.supplier_id,
        receipt_number=receipt_number
    )
    return result

@app.post("/coupang/returns/{return_request_id}/invoice")
async def register_coupang_return_invoice(
    return_request_id: str,
    request: CoupangReturnInvoiceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """회수 송장 등록"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _register_coupang_return_invoice_background,
        coupangwing_service,
        request.supplier_id,
        return_request_id,
        request.data
    )

    return {"message": "회수 송장 등록 작업이 백그라운드에서 시작되었습니다", "return_request_id": return_request_id}

@app.get("/coupang/exchanges")
async def get_coupang_exchange_requests(
    query: CoupangExchangeListQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """교환요청 목록조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_exchange_requests(
        supplier_id=query.supplier_id,
        status=query.status,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.post("/coupang/exchanges/{exchange_request_id}/receipt")
async def confirm_coupang_exchange_receipt(
    exchange_request_id: str,
    request: CoupangExchangeReceiptRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """교환요청상품 입고 확인처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _confirm_coupang_exchange_receipt_background,
        coupangwing_service,
        request.supplier_id,
        exchange_request_id,
        request.data
    )

    return {"message": "교환요청상품 입고 확인처리 작업이 백그라운드에서 시작되었습니다", "exchange_request_id": exchange_request_id}

@app.post("/coupang/exchanges/{exchange_request_id}/reject")
async def reject_coupang_exchange_request(
    exchange_request_id: str,
    request: CoupangExchangeRejectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """교환요청 거부 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _reject_coupang_exchange_request_background,
        coupangwing_service,
        request.supplier_id,
        exchange_request_id,
        request.data
    )

    return {"message": "교환요청 거부 처리 작업이 백그라운드에서 시작되었습니다", "exchange_request_id": exchange_request_id}

@app.post("/coupang/exchanges/{exchange_request_id}/invoice")
async def upload_coupang_exchange_invoice(
    exchange_request_id: str,
    request: CoupangExchangeInvoiceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """교환상품 송장 업로드 처리"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _upload_coupang_exchange_invoice_background,
        coupangwing_service,
        request.supplier_id,
        exchange_request_id,
        request.data
    )

    return {"message": "교환상품 송장 업로드 처리 작업이 백그라운드에서 시작되었습니다", "exchange_request_id": exchange_request_id}

# 상품별 고객문의 및 쿠팡 고객센터 문의 API 엔드포인트
@app.get("/coupang/products/{seller_product_id}/inquiries")
async def get_coupang_product_inquiries(
    seller_product_id: str,
    query: CoupangProductInquiryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """상품별 고객문의 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_product_inquiries(
        supplier_id=query.supplier_id,
        seller_product_id=seller_product_id,
        status=query.status,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.post("/coupang/products/{seller_product_id}/inquiries/{inquiry_id}/reply")
async def reply_to_coupang_product_inquiry(
    seller_product_id: str,
    inquiry_id: str,
    request: CoupangProductInquiryReplyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """상품별 고객문의 답변"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _reply_to_coupang_product_inquiry_background,
        coupangwing_service,
        request.supplier_id,
        seller_product_id,
        inquiry_id,
        request.data
    )

    return {"message": "상품별 고객문의 답변 작업이 백그라운드에서 시작되었습니다", "seller_product_id": seller_product_id, "inquiry_id": inquiry_id}

@app.get("/coupang/cs-inquiries")
async def get_coupang_cs_inquiries(
    query: CoupangCSInquiryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 고객센터 문의조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_cs_inquiries(
        supplier_id=query.supplier_id,
        status=query.status,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.get("/coupang/cs-inquiries/{inquiry_id}")
async def get_coupang_cs_inquiry_detail(
    inquiry_id: str,
    query: CoupangCSInquiryDetailQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 고객센터 문의 단건 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_cs_inquiry_detail(
        supplier_id=query.supplier_id,
        inquiry_id=inquiry_id
    )
    return result

@app.post("/coupang/cs-inquiries/{inquiry_id}/reply")
async def reply_to_coupang_cs_inquiry(
    inquiry_id: str,
    request: CoupangCSInquiryReplyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 고객센터 문의답변"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _reply_to_coupang_cs_inquiry_background,
        coupangwing_service,
        request.supplier_id,
        inquiry_id,
        request.data
    )

    return {"message": "쿠팡 고객센터 문의답변 작업이 백그라운드에서 시작되었습니다", "inquiry_id": inquiry_id}

@app.post("/coupang/cs-inquiries/{inquiry_id}/confirm")
async def confirm_coupang_cs_inquiry(
    inquiry_id: str,
    request: CoupangCSInquiryConfirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """쿠팡 고객센터 문의확인"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)

    # 백그라운드에서 실행
    background_tasks.add_task(
        _confirm_coupang_cs_inquiry_background,
        coupangwing_service,
        request.supplier_id,
        inquiry_id,
        request.data
    )

    return {"message": "쿠팡 고객센터 문의확인 작업이 백그라운드에서 시작되었습니다", "inquiry_id": inquiry_id}

# 매출 및 지급 관련 API 엔드포인트
@app.get("/coupang/sales-history")
async def get_coupang_sales_history(
    query: CoupangSalesHistoryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """매출내역 조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_sales_history(
        supplier_id=query.supplier_id,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

@app.get("/coupang/payment-history")
async def get_coupang_payment_history(
    query: CoupangPaymentHistoryQuery = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """지급내역조회"""
    from services import CoupangWingService
    coupangwing_service = CoupangWingService(db)
    result = await coupangwing_service.get_payment_history(
        supplier_id=query.supplier_id,
        date_from=query.date_from,
        date_to=query.date_to,
        limit=query.limit,
        offset=query.offset
    )
    return result

# 쿠팡 상품 백그라운드 작업 함수들
async def _create_coupang_product_background(coupang_service: CoupangProductService, product_request: CoupangProductCreate):
    """백그라운드에서 쿠팡 상품 생성"""
    logger.info(f"백그라운드 쿠팡 상품 생성 시작: supplier_id={product_request.supplier_id}")
    try:
        result = await coupang_service.create_product(product_request.supplier_id, product_request.product_data)
        logger.info(f"쿠팡 상품 생성 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 생성 실패: {e}")

async def _request_coupang_approval_background(coupang_service: CoupangProductService, supplier_id: int, seller_product_id: str):
    """백그라운드에서 쿠팡 상품 승인 요청"""
    logger.info(f"백그라운드 쿠팡 상품 승인 요청 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.request_approval(supplier_id, seller_product_id)
        logger.info(f"쿠팡 상품 승인 요청 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 승인 요청 실패: {e}")

async def _get_coupang_product_background(coupang_service: CoupangProductService, supplier_id: int, seller_product_id: str):
    """백그라운드에서 쿠팡 상품 조회"""
    logger.info(f"백그라운드 쿠팡 상품 조회 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.get_product(supplier_id, seller_product_id)
        logger.info(f"쿠팡 상품 조회 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 조회 실패: {e}")

async def _update_coupang_product_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    product_data: Dict[str, Any],
    requires_approval: bool
):
    """백그라운드에서 쿠팡 상품 수정"""
    logger.info(f"백그라운드 쿠팡 상품 수정 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.update_product(
            supplier_id,
            seller_product_id,
            product_data,
            requires_approval=requires_approval
        )
        logger.info(f"쿠팡 상품 수정 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 수정 실패: {e}")

async def _get_coupang_product_summary_background(coupang_service: CoupangProductService, supplier_id: int, seller_product_id: str):
    """백그라운드에서 쿠팡 상품 요약 정보 조회"""
    logger.info(f"백그라운드 쿠팡 상품 요약 정보 조회 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.get_product_summary(supplier_id, seller_product_id)
        logger.info(f"쿠팡 상품 요약 정보 조회 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 요약 정보 조회 실패: {e}")

async def _update_coupang_item_quantity_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str,
    quantity: int
):
    """백그라운드에서 쿠팡 상품 아이템 수량 변경"""
    logger.info(f"백그라운드 쿠팡 상품 아이템 수량 변경 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.update_item_quantity(supplier_id, seller_product_id, item_id, quantity)
        logger.info(f"쿠팡 상품 아이템 수량 변경 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 아이템 수량 변경 실패: {e}")

async def _update_coupang_item_price_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str,
    price: int,
    sale_price: Optional[int] = None
):
    """백그라운드에서 쿠팡 상품 아이템 가격 변경"""
    logger.info(f"백그라운드 쿠팡 상품 아이템 가격 변경 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.update_item_price(supplier_id, seller_product_id, item_id, price, sale_price)
        logger.info(f"쿠팡 상품 아이템 가격 변경 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 아이템 가격 변경 실패: {e}")

async def _resume_coupang_item_sale_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str
):
    """백그라운드에서 쿠팡 상품 아이템 판매 재개"""
    logger.info(f"백그라운드 쿠팡 상품 아이템 판매 재개 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.resume_item_sale(supplier_id, seller_product_id, item_id)
        logger.info(f"쿠팡 상품 아이템 판매 재개 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 아이템 판매 재개 실패: {e}")

async def _stop_coupang_item_sale_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str
):
    """백그라운드에서 쿠팡 상품 아이템 판매 중지"""
    logger.info(f"백그라운드 쿠팡 상품 아이템 판매 중지 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.stop_item_sale(supplier_id, seller_product_id, item_id)
        logger.info(f"쿠팡 상품 아이템 판매 중지 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 아이템 판매 중지 실패: {e}")

async def _update_coupang_item_price_by_discount_rate_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str,
    discount_rate: float,
    base_price: Optional[int] = None
):
    """백그라운드에서 쿠팡 상품 아이템 할인율 기준 가격 변경"""
    logger.info(f"백그라운드 쿠팡 상품 아이템 할인율 기준 가격 변경 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.update_item_price_by_discount_rate(supplier_id, seller_product_id, item_id, discount_rate, base_price)
        logger.info(f"쿠팡 상품 아이템 할인율 기준 가격 변경 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 상품 아이템 할인율 기준 가격 변경 실패: {e}")

async def _activate_coupang_auto_generated_options_by_item_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str
):
    """백그라운드에서 쿠팡 자동생성옵션 활성화 (옵션 상품 단위)"""
    logger.info(f"백그라운드 쿠팡 자동생성옵션 활성화 시작 (옵션 상품 단위): supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.activate_auto_generated_options_by_item(supplier_id, seller_product_id, item_id)
        logger.info(f"쿠팡 자동생성옵션 활성화 완료 (옵션 상품 단위): {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 자동생성옵션 활성화 실패 (옵션 상품 단위): {e}")

async def _activate_coupang_auto_generated_options_by_product_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str
):
    """백그라운드에서 쿠팡 자동생성옵션 활성화 (전체 상품 단위)"""
    logger.info(f"백그라운드 쿠팡 자동생성옵션 활성화 시작 (전체 상품 단위): supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.activate_auto_generated_options_by_product(supplier_id, seller_product_id)
        logger.info(f"쿠팡 자동생성옵션 활성화 완료 (전체 상품 단위): {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 자동생성옵션 활성화 실패 (전체 상품 단위): {e}")

async def _deactivate_coupang_auto_generated_options_by_item_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str,
    item_id: str
):
    """백그라운드에서 쿠팡 자동생성옵션 비활성화 (옵션 상품 단위)"""
    logger.info(f"백그라운드 쿠팡 자동생성옵션 비활성화 시작 (옵션 상품 단위): supplier_id={supplier_id}, seller_product_id={seller_product_id}, item_id={item_id}")
    try:
        result = await coupang_service.deactivate_auto_generated_options_by_item(supplier_id, seller_product_id, item_id)
        logger.info(f"쿠팡 자동생성옵션 비활성화 완료 (옵션 상품 단위): {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 자동생성옵션 비활성화 실패 (옵션 상품 단위): {e}")

async def _deactivate_coupang_auto_generated_options_by_product_background(
    coupang_service: CoupangProductService,
    supplier_id: int,
    seller_product_id: str
):
    """백그라운드에서 쿠팡 자동생성옵션 비활성화 (전체 상품 단위)"""
    logger.info(f"백그라운드 쿠팡 자동생성옵션 비활성화 시작 (전체 상품 단위): supplier_id={supplier_id}, seller_product_id={seller_product_id}")
    try:
        result = await coupang_service.deactivate_auto_generated_options_by_product(supplier_id, seller_product_id)
        logger.info(f"쿠팡 자동생성옵션 비활성화 완료 (전체 상품 단위): {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 자동생성옵션 비활성화 실패 (전체 상품 단위): {e}")

# 배송 처리 백그라운드 작업 함수들
async def _process_coupang_product_ready_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    shipment_box_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 상품준비중 처리"""
    logger.info(f"백그라운드 상품준비중 처리 시작: supplier_id={supplier_id}, shipment_box_id={shipment_box_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.process_product_ready(shipment_box_id, data)
            logger.info(f"상품준비중 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 상품준비중 처리 실패: {e}")

async def _upload_coupang_invoice_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    shipment_box_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 송장업로드 처리"""
    logger.info(f"백그라운드 송장업로드 처리 시작: supplier_id={supplier_id}, shipment_box_id={shipment_box_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.upload_invoice(shipment_box_id, data)
            logger.info(f"송장업로드 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 송장업로드 처리 실패: {e}")

async def _update_coupang_invoice_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    shipment_box_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 송장업데이트 처리"""
    logger.info(f"백그라운드 송장업데이트 처리 시작: supplier_id={supplier_id}, shipment_box_id={shipment_box_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.update_invoice(shipment_box_id, data)
            logger.info(f"송장업데이트 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 송장업데이트 처리 실패: {e}")

async def _process_coupang_shipping_stopped_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    shipment_box_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 출고중지완료 처리"""
    logger.info(f"백그라운드 출고중지완료 처리 시작: supplier_id={supplier_id}, shipment_box_id={shipment_box_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.process_shipping_stopped(shipment_box_id, data)
            logger.info(f"출고중지완료 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 출고중지완료 처리 실패: {e}")

async def _process_coupang_already_shipped_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    shipment_box_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 이미출고 처리"""
    logger.info(f"백그라운드 이미출고 처리 시작: supplier_id={supplier_id}, shipment_box_id={shipment_box_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.process_already_shipped(shipment_box_id, data)
            logger.info(f"이미출고 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 이미출고 처리 실패: {e}")

async def _cancel_coupang_order_item_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    order_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 주문 상품 취소 처리"""
    logger.info(f"백그라운드 주문 상품 취소 처리 시작: supplier_id={supplier_id}, order_id={order_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.cancel_order_item(order_id, data)
            logger.info(f"주문 상품 취소 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 주문 상품 취소 처리 실패: {e}")

async def _complete_coupang_long_delivery_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    order_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 장기미배송 배송완료 처리"""
    logger.info(f"백그라운드 장기미배송 배송완료 처리 시작: supplier_id={supplier_id}, order_id={order_id}")
    try:
        from ownerclan_api import CoupangWingAPI
        credentials = await coupangwing_service.get_coupangwing_credentials(supplier_id)
        if credentials:
            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)
            result = await coupangwing_api.complete_long_delivery(order_id, data)
            logger.info(f"장기미배송 배송완료 처리 완료: {result}")
        else:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: supplier_id={supplier_id}")
    except Exception as e:
        logger.error(f"백그라운드 장기미배송 배송완료 처리 실패: {e}")

# 반품 및 교환 처리 백그라운드 작업 함수들
async def _confirm_coupang_return_receipt_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    return_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 반품상품 입고 확인처리"""
    logger.info(f"백그라운드 반품상품 입고 확인처리 시작: supplier_id={supplier_id}, return_request_id={return_request_id}")
    try:
        result = await coupangwing_service.confirm_return_receipt(supplier_id, return_request_id, data)
        logger.info(f"반품상품 입고 확인처리 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 반품상품 입고 확인처리 실패: {e}")

async def _approve_coupang_return_request_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    return_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 반품요청 승인 처리"""
    logger.info(f"백그라운드 반품요청 승인 처리 시작: supplier_id={supplier_id}, return_request_id={return_request_id}")
    try:
        result = await coupangwing_service.approve_return_request(supplier_id, return_request_id, data)
        logger.info(f"반품요청 승인 처리 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 반품요청 승인 처리 실패: {e}")

async def _register_coupang_return_invoice_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    return_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 회수 송장 등록"""
    logger.info(f"백그라운드 회수 송장 등록 시작: supplier_id={supplier_id}, return_request_id={return_request_id}")
    try:
        result = await coupangwing_service.register_return_invoice(supplier_id, return_request_id, data)
        logger.info(f"회수 송장 등록 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 회수 송장 등록 실패: {e}")

async def _confirm_coupang_exchange_receipt_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    exchange_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 교환요청상품 입고 확인처리"""
    logger.info(f"백그라운드 교환요청상품 입고 확인처리 시작: supplier_id={supplier_id}, exchange_request_id={exchange_request_id}")
    try:
        result = await coupangwing_service.confirm_exchange_receipt(supplier_id, exchange_request_id, data)
        logger.info(f"교환요청상품 입고 확인처리 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 교환요청상품 입고 확인처리 실패: {e}")

async def _reject_coupang_exchange_request_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    exchange_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 교환요청 거부 처리"""
    logger.info(f"백그라운드 교환요청 거부 처리 시작: supplier_id={supplier_id}, exchange_request_id={exchange_request_id}")
    try:
        result = await coupangwing_service.reject_exchange_request(supplier_id, exchange_request_id, data)
        logger.info(f"교환요청 거부 처리 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 교환요청 거부 처리 실패: {e}")

async def _upload_coupang_exchange_invoice_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    exchange_request_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 교환상품 송장 업로드 처리"""
    logger.info(f"백그라운드 교환상품 송장 업로드 처리 시작: supplier_id={supplier_id}, exchange_request_id={exchange_request_id}")
    try:
        result = await coupangwing_service.upload_exchange_invoice(supplier_id, exchange_request_id, data)
        logger.info(f"교환상품 송장 업로드 처리 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 교환상품 송장 업로드 처리 실패: {e}")

# 고객문의 백그라운드 작업 함수들
async def _reply_to_coupang_product_inquiry_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    seller_product_id: str,
    inquiry_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 상품별 고객문의 답변"""
    logger.info(f"백그라운드 상품별 고객문의 답변 시작: supplier_id={supplier_id}, seller_product_id={seller_product_id}, inquiry_id={inquiry_id}")
    try:
        result = await coupangwing_service.reply_to_product_inquiry(supplier_id, seller_product_id, inquiry_id, data)
        logger.info(f"상품별 고객문의 답변 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 상품별 고객문의 답변 실패: {e}")

async def _reply_to_coupang_cs_inquiry_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    inquiry_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 쿠팡 고객센터 문의답변"""
    logger.info(f"백그라운드 쿠팡 고객센터 문의답변 시작: supplier_id={supplier_id}, inquiry_id={inquiry_id}")
    try:
        result = await coupangwing_service.reply_to_cs_inquiry(supplier_id, inquiry_id, data)
        logger.info(f"쿠팡 고객센터 문의답변 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 고객센터 문의답변 실패: {e}")

async def _confirm_coupang_cs_inquiry_background(
    coupangwing_service: CoupangWingService,
    supplier_id: int,
    inquiry_id: str,
    data: Dict[str, Any]
):
    """백그라운드에서 쿠팡 고객센터 문의확인"""
    logger.info(f"백그라운드 쿠팡 고객센터 문의확인 시작: supplier_id={supplier_id}, inquiry_id={inquiry_id}")
    try:
        result = await coupangwing_service.confirm_cs_inquiry(supplier_id, inquiry_id, data)
        logger.info(f"쿠팡 고객센터 문의확인 완료: {result}")
    except Exception as e:
        logger.error(f"백그라운드 쿠팡 고객센터 문의확인 실패: {e}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
