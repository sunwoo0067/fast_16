"""주문 도메인 엔티티"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"           # 주문 대기
    CONFIRMED = "confirmed"       # 주문 확인됨
    PROCESSING = "processing"     # 처리 중
    SHIPPED = "shipped"          # 발송됨
    DELIVERED = "delivered"      # 배송 완료
    CANCELLED = "cancelled"      # 취소됨
    RETURNED = "returned"        # 반품됨
    EXCHANGED = "exchanged"      # 교환됨


class PaymentStatus(Enum):
    """결제 상태"""
    PENDING = "pending"           # 결제 대기
    PAID = "paid"                # 결제 완료
    FAILED = "failed"            # 결제 실패
    REFUNDED = "refunded"        # 환불됨
    PARTIALLY_REFUNDED = "partially_refunded"  # 부분 환불


@dataclass
class OrderItem:
    """주문 상품"""
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: int
    total_price: int
    options: Dict[str, Any] = field(default_factory=dict)  # 상품 옵션 정보

    def calculate_total(self) -> int:
        """상품 총 금액 계산"""
        return self.quantity * self.unit_price


@dataclass
class ShippingInfo:
    """배송 정보"""
    tracking_number: Optional[str] = None
    shipping_company: Optional[str] = None
    shipped_at: Optional[datetime] = None
    estimated_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None


@dataclass
class Order:
    """주문 도메인 엔티티"""
    id: str
    supplier_id: str
    supplier_account_id: str
    order_key: str  # 공급사 주문 키
    status: OrderStatus = OrderStatus.PENDING
    payment_status: PaymentStatus = PaymentStatus.PENDING

    # 주문 정보
    items: List[OrderItem] = field(default_factory=list)
    subtotal: int = 0  # 상품 금액 합계
    shipping_fee: int = 0  # 배송비
    total_amount: int = 0  # 총 금액

    # 배송 정보
    shipping_info: ShippingInfo = field(default_factory=ShippingInfo)

    # 고객 정보 (익명화된 정보)
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    shipping_address: Optional[Dict[str, Any]] = None

    # 메모 및 특이사항
    orderer_note: Optional[str] = None  # 구매자 요청사항
    seller_note: Optional[str] = None   # 판매자 메모

    # 시스템 정보
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def calculate_totals(self) -> None:
        """주문 총 금액 계산"""
        self.subtotal = sum(item.calculate_total() for item in self.items)
        self.total_amount = self.subtotal + self.shipping_fee

    def can_cancel(self) -> bool:
        """주문 취소 가능 여부"""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]

    def can_ship(self) -> bool:
        """주문 발송 가능 여부"""
        return self.status == OrderStatus.CONFIRMED and self.payment_status == PaymentStatus.PAID

    def mark_as_shipped(self, tracking_number: str, shipping_company: str) -> None:
        """주문 발송 처리"""
        if not self.can_ship():
            raise ValueError("발송할 수 없는 주문 상태입니다")

        self.status = OrderStatus.SHIPPED
        self.shipping_info.tracking_number = tracking_number
        self.shipping_info.shipping_company = shipping_company
        self.shipping_info.shipped_at = datetime.now()
        self.updated_at = datetime.now()

    def mark_as_delivered(self) -> None:
        """주문 배송 완료 처리"""
        if self.status != OrderStatus.SHIPPED:
            raise ValueError("배송 완료할 수 없는 주문 상태입니다")

        self.status = OrderStatus.DELIVERED
        self.shipping_info.actual_delivery_date = datetime.now()
        self.updated_at = datetime.now()

    def cancel_order(self, reason: str) -> None:
        """주문 취소"""
        if not self.can_cancel():
            raise ValueError("취소할 수 없는 주문 상태입니다")

        self.status = OrderStatus.CANCELLED
        self.seller_note = f"취소 사유: {reason}"
        self.updated_at = datetime.now()

    def add_item(self, item: OrderItem) -> None:
        """주문에 상품 추가"""
        self.items.append(item)
        self.calculate_totals()

    def remove_item(self, item_id: str) -> None:
        """주문에서 상품 제거"""
        self.items = [item for item in self.items if item.id != item_id]
        self.calculate_totals()

    def get_item_count(self) -> int:
        """주문 상품 개수"""
        return sum(item.quantity for item in self.items)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        return {
            'id': self.id,
            'supplier_id': self.supplier_id,
            'supplier_account_id': self.supplier_account_id,
            'order_key': self.order_key,
            'status': self.status.value,
            'payment_status': self.payment_status.value,
            'items': [
                {
                    'id': item.id,
                    'product_id': item.product_id,
                    'product_name': item.product_name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price,
                    'options': item.options
                }
                for item in self.items
            ],
            'subtotal': self.subtotal,
            'shipping_fee': self.shipping_fee,
            'total_amount': self.total_amount,
            'shipping_info': {
                'tracking_number': self.shipping_info.tracking_number,
                'shipping_company': self.shipping_info.shipping_company,
                'shipped_at': self.shipping_info.shipped_at.isoformat() if self.shipping_info.shipped_at else None,
                'estimated_delivery_date': self.shipping_info.estimated_delivery_date.isoformat() if self.shipping_info.estimated_delivery_date else None,
                'actual_delivery_date': self.shipping_info.actual_delivery_date.isoformat() if self.shipping_info.actual_delivery_date else None
            },
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'shipping_address': self.shipping_address,
            'orderer_note': self.orderer_note,
            'seller_note': self.seller_note,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
