from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from app.models.database import get_db, Product, ProductSyncHistory
from app.services.product_service import ProductService, ProductSyncService
from app.core.exceptions import create_http_exception, ProductSyncError, ValidationError
from app.core.logging import get_logger, log_product_sync, log_sync_stats

router = APIRouter()
logger = get_logger(__name__)

# Pydantic 모델들
class ProductCreate(BaseModel):
    supplier_id: int
    supplier_account_id: int
    item_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., gt=0)
    sale_price: Optional[int] = Field(None, gt=0)
    margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    max_stock_quantity: Optional[int] = Field(None, ge=0)

    # 드랍싸핑 특화 필드들
    supplier_product_id: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_url: Optional[str] = None
    supplier_image_url: Optional[str] = None
    estimated_shipping_days: Optional[int] = Field(None, ge=1, le=30)

    # 카테고리 정보
    category_id: Optional[str] = None
    category_name: Optional[str] = None

    # 상품 설명 및 이미지
    description: Optional[str] = None
    images: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None

    # 쿠팡 상품 정보
    coupang_product_id: Optional[str] = None
    coupang_status: Optional[str] = None
    coupang_category_id: Optional[str] = None
    manufacturer: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    price: Optional[int] = Field(None, gt=0)
    sale_price: Optional[int] = Field(None, gt=0)
    margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    max_stock_quantity: Optional[int] = Field(None, ge=0)

    # 드랍싸핑 특화 필드들
    supplier_product_id: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_url: Optional[str] = None
    supplier_image_url: Optional[str] = None
    estimated_shipping_days: Optional[int] = Field(None, ge=1, le=30)

    # 카테고리 정보
    category_id: Optional[str] = None
    category_name: Optional[str] = None

    # 상품 설명 및 이미지
    description: Optional[str] = None
    images: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None

    # 상태
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_account_id: int
    item_key: str
    name: str
    price: int
    sale_price: Optional[int]
    margin_rate: float
    stock_quantity: int
    max_stock_quantity: Optional[int]

    # 드랍싸핑 특화 필드들
    supplier_product_id: Optional[str]
    supplier_name: Optional[str]
    supplier_url: Optional[str]
    supplier_image_url: Optional[str]
    estimated_shipping_days: Optional[int]

    # 상품 상태 및 동기화
    is_active: bool
    sync_status: str
    last_synced_at: Optional[datetime]
    sync_error_message: Optional[str]

    # 카테고리 정보
    category_id: Optional[str]
    category_name: Optional[str]

    # 쿠팡 상품 정보
    coupang_product_id: Optional[str]
    coupang_status: Optional[str]
    coupang_category_id: Optional[str]
    manufacturer: Optional[str]

    # 상품 설명 및 이미지
    description: Optional[str]
    images: Optional[List[str]]
    options: Optional[Dict[str, Any]]

    created_at: datetime
    updated_at: datetime

class ProductCollectionRequest(BaseModel):
    supplier_id: int
    supplier_account_id: Optional[int] = None
    item_keys: Optional[List[str]] = None  # 특정 상품만 수집시 사용
    force_sync: bool = False  # 강제 동기화 여부

class ProductSyncResponse(BaseModel):
    success: int
    failed: int
    total: int
    duration_ms: int
    errors: List[Dict[str, Any]]

class ProductQueryParams(BaseModel):
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    supplier_id: Optional[int] = None
    category_id: Optional[str] = None
    is_active: Optional[bool] = None
    sync_status: Optional[str] = None
    search: Optional[str] = None  # 상품명 검색

@router.post("/bulk", response_model=ProductSyncResponse)
async def bulk_create_products(
    products_data: List[ProductCreate],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """대량 상품 등록 (드랍싸핑 특화)"""
    try:
        logger.info(f"대량 상품 등록 요청: {len(products_data)}개 상품")

        product_sync_service = ProductSyncService(db)

        # 백그라운드에서 실행
        background_tasks.add_task(
            _bulk_create_products_background,
            product_sync_service,
            products_data
        )

        return {
            "success": 0,  # 실제 결과는 백그라운드 완료 후 확인
            "failed": 0,
            "total": len(products_data),
            "duration_ms": 0,
            "errors": []
        }

    except Exception as e:
        logger.error(f"대량 상품 등록 요청 실패: {e}")
        raise create_http_exception(ProductSyncError(f"대량 상품 등록 요청 실패: {str(e)}"))

@router.post("/collect", response_model=Dict[str, str])
async def collect_products(
    collection_request: ProductCollectionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """상품 수집 (백그라운드에서 실행)"""
    try:
        logger.info(f"상품 수집 요청: supplier_id={collection_request.supplier_id}")

        product_service = ProductService(db)

        # 백그라운드에서 실행
        background_tasks.add_task(
            _collect_products_background,
            product_service,
            collection_request
        )

        return {
            "message": "상품 수집 작업이 백그라운드에서 시작되었습니다",
            "supplier_id": collection_request.supplier_id
        }

    except Exception as e:
        logger.error(f"상품 수집 요청 실패: {e}")
        raise create_http_exception(ProductSyncError(f"상품 수집 요청 실패: {str(e)}"))

@router.get("/", response_model=List[ProductResponse])
async def get_products(
    params: ProductQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """상품 목록 조회"""
    try:
        product_service = ProductService(db)
        products = await product_service.get_products(
            supplier_id=params.supplier_id,
            category_id=params.category_id,
            is_active=params.is_active,
            sync_status=params.sync_status,
            search=params.search,
            limit=params.limit,
            offset=params.offset
        )

        return [
            ProductResponse(
                id=product.id,
                supplier_id=product.supplier_id,
                supplier_account_id=product.supplier_account_id,
                item_key=product.item_key,
                name=product.name,
                price=product.price,
                sale_price=product.sale_price,
                margin_rate=product.margin_rate,
                stock_quantity=product.stock_quantity,
                max_stock_quantity=product.max_stock_quantity,
                supplier_product_id=product.supplier_product_id,
                supplier_name=product.supplier_name,
                supplier_url=product.supplier_url,
                supplier_image_url=product.supplier_image_url,
                estimated_shipping_days=product.estimated_shipping_days,
                is_active=product.is_active,
                sync_status=product.sync_status,
                last_synced_at=product.last_synced_at,
                sync_error_message=product.sync_error_message,
                category_id=product.category_id,
                category_name=product.category_name,
                coupang_product_id=product.coupang_product_id,
                coupang_status=product.coupang_status,
                coupang_category_id=product.coupang_category_id,
                manufacturer=product.manufacturer,
                description=product.description,
                images=json.loads(product.images) if product.images else None,
                options=json.loads(product.options) if product.options else None,
                created_at=product.created_at,
                updated_at=product.updated_at
            )
            for product in products
        ]

    except Exception as e:
        logger.error(f"상품 목록 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"상품 목록 조회 실패: {str(e)}"))

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """특정 상품 조회"""
    try:
        product_service = ProductService(db)
        product = await product_service.get_product_by_id(product_id)

        if not product:
            raise ProductSyncError(f"상품을 찾을 수 없습니다 (ID: {product_id})")

        return ProductResponse(
            id=product.id,
            supplier_id=product.supplier_id,
            supplier_account_id=product.supplier_account_id,
            item_key=product.item_key,
            name=product.name,
            price=product.price,
            sale_price=product.sale_price,
            margin_rate=product.margin_rate,
            stock_quantity=product.stock_quantity,
            max_stock_quantity=product.max_stock_quantity,
            supplier_product_id=product.supplier_product_id,
            supplier_name=product.supplier_name,
            supplier_url=product.supplier_url,
            supplier_image_url=product.supplier_image_url,
            estimated_shipping_days=product.estimated_shipping_days,
            is_active=product.is_active,
            sync_status=product.sync_status,
            last_synced_at=product.last_synced_at,
            sync_error_message=product.sync_error_message,
            category_id=product.category_id,
            category_name=product.category_name,
            coupang_product_id=product.coupang_product_id,
            coupang_status=product.coupang_status,
            coupang_category_id=product.coupang_category_id,
            manufacturer=product.manufacturer,
            description=product.description,
            images=json.loads(product.images) if product.images else None,
            options=json.loads(product.options) if product.options else None,
            created_at=product.created_at,
            updated_at=product.updated_at
        )

    except ProductSyncError:
        raise
    except Exception as e:
        logger.error(f"상품 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"상품 조회 실패: {str(e)}"))

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """상품 정보 수정"""
    try:
        logger.info(f"상품 수정 요청: ID={product_id}")
        product_service = ProductService(db)

        product = await product_service.update_product(
            product_id=product_id,
            name=product_data.name,
            price=product_data.price,
            sale_price=product_data.sale_price,
            margin_rate=product_data.margin_rate,
            stock_quantity=product_data.stock_quantity,
            max_stock_quantity=product_data.max_stock_quantity,
            supplier_product_id=product_data.supplier_product_id,
            supplier_name=product_data.supplier_name,
            supplier_url=product_data.supplier_url,
            supplier_image_url=product_data.supplier_image_url,
            estimated_shipping_days=product_data.estimated_shipping_days,
            category_id=product_data.category_id,
            category_name=product_data.category_name,
            description=product_data.description,
            images=product_data.images,
            options=product_data.options,
            is_active=product_data.is_active
        )

        if not product:
            raise ProductSyncError(f"상품을 찾을 수 없습니다 (ID: {product_id})")

        logger.info(f"상품 수정 완료: ID={product_id}")
        return ProductResponse(
            id=product.id,
            supplier_id=product.supplier_id,
            supplier_account_id=product.supplier_account_id,
            item_key=product.item_key,
            name=product.name,
            price=product.price,
            sale_price=product.sale_price,
            margin_rate=product.margin_rate,
            stock_quantity=product.stock_quantity,
            max_stock_quantity=product.max_stock_quantity,
            supplier_product_id=product.supplier_product_id,
            supplier_name=product.supplier_name,
            supplier_url=product.supplier_url,
            supplier_image_url=product.supplier_image_url,
            estimated_shipping_days=product.estimated_shipping_days,
            is_active=product.is_active,
            sync_status=product.sync_status,
            last_synced_at=product.last_synced_at,
            sync_error_message=product.sync_error_message,
            category_id=product.category_id,
            category_name=product.category_name,
            coupang_product_id=product.coupang_product_id,
            coupang_status=product.coupang_status,
            coupang_category_id=product.coupang_category_id,
            manufacturer=product.manufacturer,
            description=product.description,
            images=json.loads(product.images) if product.images else None,
            options=json.loads(product.options) if product.options else None,
            created_at=product.created_at,
            updated_at=product.updated_at
        )

    except ProductSyncError:
        raise
    except Exception as e:
        logger.error(f"상품 수정 실패: {e}")
        raise create_http_exception(ProductSyncError(f"상품 수정 실패: {str(e)}"))

@router.get("/stats/{supplier_id}")
async def get_product_stats(
    supplier_id: int,
    db: AsyncSession = Depends(get_db)
):
    """공급사의 상품 통계 조회"""
    try:
        product_service = ProductService(db)
        stats = await product_service.get_product_stats(supplier_id)

        return stats

    except Exception as e:
        logger.error(f"상품 통계 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"상품 통계 조회 실패: {str(e)}"))

@router.post("/sync-history")
async def get_product_sync_history(
    supplier_id: int,
    product_id: Optional[int] = None,
    sync_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """상품 동기화 이력 조회"""
    try:
        product_service = ProductService(db)
        history = await product_service.get_sync_history(
            supplier_id=supplier_id,
            product_id=product_id,
            sync_type=sync_type,
            status=status,
            limit=limit,
            offset=offset
        )

        return history

    except Exception as e:
        logger.error(f"동기화 이력 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"동기화 이력 조회 실패: {str(e)}"))

# 백그라운드 작업 함수들
async def _bulk_create_products_background(
    product_sync_service: ProductSyncService,
    products_data: List[Dict[str, Any]]
):
    """백그라운드에서 대량 상품 등록"""
    start_time = datetime.now()
    logger.info(f"백그라운드 대량 상품 등록 시작: {len(products_data)}개 상품")

    try:
        result = await product_sync_service.bulk_create_products(products_data)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        log_sync_stats({
            "action": "bulk_create_products",
            "total_products": len(products_data),
            "success": result["success"],
            "failed": result["failed"],
            "duration_ms": duration_ms
        })

        logger.info(f"대량 상품 등록 완료: 성공={result['success']}, 실패={result['failed']}")

        # 실패한 상품들의 로그 기록
        for error in result["errors"]:
            log_product_sync(
                product_data=error.get("product", {}),
                action="bulk_create",
                success=False,
                error=error.get("error")
            )

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.error(f"백그라운드 대량 상품 등록 실패: {e}")
        log_sync_stats({
            "action": "bulk_create_products",
            "total_products": len(products_data),
            "success": 0,
            "failed": len(products_data),
            "duration_ms": duration_ms,
            "error": str(e)
        })

async def _collect_products_background(
    product_service: ProductService,
    collection_request: ProductCollectionRequest
):
    """백그라운드에서 상품 수집"""
    start_time = datetime.now()
    logger.info(f"백그라운드 상품 수집 시작: supplier_id={collection_request.supplier_id}")

    try:
        result = await product_service.collect_products(
            supplier_id=collection_request.supplier_id,
            supplier_account_id=collection_request.supplier_account_id,
            item_keys=collection_request.item_keys,
            force_sync=collection_request.force_sync
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        log_sync_stats({
            "action": "collect_products",
            "supplier_id": collection_request.supplier_id,
            "total_products": result.get("total_products", 0),
            "new_products": result.get("new_products", 0),
            "updated_products": result.get("updated_products", 0),
            "duration_ms": duration_ms
        })

        logger.info(f"상품 수집 완료: supplier_id={collection_request.supplier_id}")

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.error(f"백그라운드 상품 수집 실패: {e}")
        log_sync_stats({
            "action": "collect_products",
            "supplier_id": collection_request.supplier_id,
            "success": 0,
            "failed": 1,
            "duration_ms": duration_ms,
            "error": str(e)
        })

