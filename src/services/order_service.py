"""주문 서비스 (헥사고날 아키텍처)"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.ports.repo_port import RepositoryPort
from src.core.entities.order import Order, OrderStatus, PaymentStatus, OrderItem, ShippingInfo
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """주문 서비스 파사드"""

    def __init__(
        self,
        repository: RepositoryPort
    ):
        self.repository = repository

    async def create_order(
        self,
        supplier_id: str,
        supplier_account_id: str,
        order_key: str,
        items: List[Dict[str, Any]],
        shipping_fee: int = 0,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        shipping_address: Optional[Dict[str, Any]] = None,
        orderer_note: Optional[str] = None
    ):
        """주문 생성"""
        try:
            # 주문 ID 생성 (실제로는 UUID 등 사용)
            order_id = f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 주문 아이템 변환
            order_items = []
            for item_data in items:
                order_item = OrderItem(
                    id=f"item_{len(order_items)}",
                    product_id=item_data['product_id'],
                    product_name=item_data['product_name'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    total_price=item_data['quantity'] * item_data['unit_price'],
                    options=item_data.get('options', {})
                )
                order_items.append(order_item)

            # 주문 생성
            order = Order(
                id=order_id,
                supplier_id=supplier_id,
                supplier_account_id=supplier_account_id,
                order_key=order_key,
                items=order_items,
                shipping_fee=shipping_fee,
                customer_name=customer_name,
                customer_phone=customer_phone,
                shipping_address=shipping_address,
                orderer_note=orderer_note
            )

            # 총 금액 계산
            order.calculate_totals()

            # TODO: 실제 리포지토리에 저장
            # await self.repository.save_order(order)

            return Success(order)

        except Exception as e:
            logger.error(f"주문 생성 실패: {e}")
            return Failure(f"주문 생성 실패: {str(e)}")

    async def get_orders(
        self,
        supplier_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ):
        """주문 목록 조회"""
        try:
            # TODO: 실제 리포지토리에서 조회
            orders = []  # 실제로는 데이터베이스에서 조회
            total = 0
            return Success((orders, total))

        except Exception as e:
            logger.error(f"주문 목록 조회 실패: {e}")
            return Failure(f"주문 목록 조회 실패: {str(e)}")

    async def get_order_by_id(self, order_id: str):
        """주문 상세 조회"""
        try:
            # TODO: 실제 리포지토리에서 조회
            order = None  # 실제로는 데이터베이스에서 조회
            return Success(order)

        except Exception as e:
            logger.error(f"주문 조회 실패: {e}")
            return Failure(f"주문 조회 실패: {str(e)}")

    async def update_order(
        self,
        order_id: str,
        status: Optional[str] = None,
        payment_status: Optional[str] = None,
        seller_note: Optional[str] = None,
        tracking_number: Optional[str] = None,
        shipping_company: Optional[str] = None
    ):
        """주문 수정"""
        try:
            # TODO: 실제 리포지토리에서 조회 및 업데이트
            order = None  # 실제로는 데이터베이스에서 조회

            if not order:
                return Failure("주문을 찾을 수 없습니다")

            # 상태 업데이트
            if status:
                try:
                    order.status = OrderStatus(status)
                except ValueError:
                    return Failure(f"유효하지 않은 주문 상태: {status}")

            if payment_status:
                try:
                    order.payment_status = PaymentStatus(payment_status)
                except ValueError:
                    return Failure(f"유효하지 않은 결제 상태: {payment_status}")

            if seller_note:
                order.seller_note = seller_note

            if tracking_number or shipping_company:
                if tracking_number:
                    order.shipping_info.tracking_number = tracking_number
                if shipping_company:
                    order.shipping_info.shipping_company = shipping_company

            order.updated_at = datetime.now()

            # TODO: 실제 리포지토리에 저장
            # await self.repository.save_order(order)

            return Success(order)

        except Exception as e:
            logger.error(f"주문 수정 실패: {e}")
            return Failure(f"주문 수정 실패: {str(e)}")

    async def ship_order(
        self,
        order_id: str,
        tracking_number: str,
        shipping_company: str
    ):
        """주문 발송"""
        try:
            # TODO: 실제 리포지토리에서 조회
            order = None  # 실제로는 데이터베이스에서 조회

            if not order:
                return Failure("주문을 찾을 수 없습니다")

            # 발송 처리
            order.mark_as_shipped(tracking_number, shipping_company)

            # TODO: 실제 리포지토리에 저장
            # await self.repository.save_order(order)

            return Success(order)

        except ValueError as e:
            return Failure(str(e))
        except Exception as e:
            logger.error(f"주문 발송 실패: {e}")
            return Failure(f"주문 발송 실패: {str(e)}")

    async def cancel_order(self, order_id: str, reason: str):
        """주문 취소"""
        try:
            # TODO: 실제 리포지토리에서 조회
            order = None  # 실제로는 데이터베이스에서 조회

            if not order:
                return Failure("주문을 찾을 수 없습니다")

            # 취소 처리
            order.cancel_order(reason)

            # TODO: 실제 리포지토리에 저장
            # await self.repository.save_order(order)

            return Success(order)

        except ValueError as e:
            return Failure(str(e))
        except Exception as e:
            logger.error(f"주문 취소 실패: {e}")
            return Failure(f"주문 취소 실패: {str(e)}")

    async def get_order_stats(self, supplier_id: Optional[str] = None):
        """주문 통계 조회"""
        try:
            # TODO: 실제 리포지토리에서 통계 조회
            stats = {
                'total_orders': 0,
                'pending_orders': 0,
                'shipped_orders': 0,
                'delivered_orders': 0,
                'cancelled_orders': 0,
                'total_revenue': 0,
                'average_order_value': 0.0
            }

            return Success(stats)

        except Exception as e:
            logger.error(f"주문 통계 조회 실패: {e}")
            return Failure(f"주문 통계 조회 실패: {str(e)}")
