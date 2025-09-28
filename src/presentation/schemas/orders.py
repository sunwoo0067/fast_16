"""주문 관련 DTO 스키마"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class OrderItemCreateRequest(BaseModel):
    """주문 상품 생성 요청"""
    product_id: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: int = Field(..., gt=0)
    options: Optional[Dict[str, Any]] = None


class OrderCreateRequest(BaseModel):
    """주문 생성 요청"""
    supplier_id: str
    supplier_account_id: str
    order_key: str
    items: List[OrderItemCreateRequest]
    shipping_fee: int = 0
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    shipping_address: Optional[Dict[str, Any]] = None
    orderer_note: Optional[str] = None


class OrderUpdateRequest(BaseModel):
    """주문 업데이트 요청"""
    status: Optional[str] = None
    payment_status: Optional[str] = None
    seller_note: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_company: Optional[str] = None


class OrderItemResponse(BaseModel):
    """주문 상품 응답"""
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: int
    total_price: int
    options: Dict[str, Any]


class OrderResponse(BaseModel):
    """주문 응답"""
    id: str
    supplier_id: str
    supplier_account_id: str
    order_key: str
    status: str
    payment_status: str
    items: List[OrderItemResponse]
    subtotal: int
    shipping_fee: int
    total_amount: int
    customer_name: Optional[str]
    customer_phone: Optional[str]
    shipping_address: Optional[Dict[str, Any]]
    shipping_info: Dict[str, Any]
    orderer_note: Optional[str]
    seller_note: Optional[str]
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    """주문 목록 응답"""
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class OrderStatusUpdateRequest(BaseModel):
    """주문 상태 업데이트 요청"""
    status: str
    reason: Optional[str] = None


class ShippingUpdateRequest(BaseModel):
    """배송 정보 업데이트 요청"""
    tracking_number: str
    shipping_company: str


class OrderCancellationRequest(BaseModel):
    """주문 취소 요청"""
    reason: str


class OrderStatsResponse(BaseModel):
    """주문 통계 응답"""
    total_orders: int
    pending_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_revenue: int
    average_order_value: float
