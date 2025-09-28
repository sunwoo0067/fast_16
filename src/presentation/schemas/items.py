"""상품 관련 DTO 스키마"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProductCreateRequest(BaseModel):
    """상품 생성 요청"""
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


class ProductUpdateRequest(BaseModel):
    """상품 업데이트 요청"""
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
    """상품 응답"""
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

    # 메타데이터
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """상품 목록 응답"""
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class ProductSyncRequest(BaseModel):
    """상품 동기화 요청"""
    supplier_id: int
    item_keys: Optional[List[str]] = None
    force_sync: bool = False


class ProductSyncResponse(BaseModel):
    """상품 동기화 응답"""
    success: bool
    message: str
    processed_count: int
    success_count: int
    failure_count: int
    errors: List[Dict[str, str]] = []


class IngestItemsRequest(BaseModel):
    """상품 수집 요청"""
    supplier_id: str
    account_id: str
    item_keys: Optional[List[str]] = None
    dry_run: bool = False


class IngestItemsResponse(BaseModel):
    """상품 수집 응답"""
    success: bool
    message: str
    items_count: int
    processed_items: List[str] = []


class NormalizeItemsRequest(BaseModel):
    """상품 정규화 요청"""
    supplier_id: Optional[str] = None
    item_ids: Optional[List[str]] = None
    batch_size: int = 100


class NormalizeItemsResponse(BaseModel):
    """상품 정규화 응답"""
    success: bool
    message: str
    processed_count: int
    normalized_count: int
    errors: List[Dict[str, str]] = []


class PublishToMarketRequest(BaseModel):
    """마켓 업로드 요청"""
    market_type: str
    item_ids: List[str]
    account_name: str
    dry_run: bool = False


class PublishToMarketResponse(BaseModel):
    """마켓 업로드 응답"""
    success: bool
    message: str
    processed_count: int
    success_count: int
    failure_count: int
    results: List[Dict[str, Any]] = []
