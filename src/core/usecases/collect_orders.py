"""주문 수집 유즈케이스 (드랍십핑 자동화)"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from src.core.ports.supplier_port import SupplierPort
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.core.entities.order import Order, OrderStatus, PaymentStatus, OrderItem, ShippingInfo
from src.core.entities.sync_history import SyncHistory, SyncType, SyncStatus, SyncResult
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class CollectOrdersUseCase:
    """주문 수집 유즈케이스"""

    def __init__(
        self,
        supplier_port: SupplierPort,
        repository: RepositoryPort,
        clock: ClockPort
    ):
        self.supplier_port = supplier_port
        self.repository = repository
        self.clock = clock

    async def execute(
        self,
        supplier_id: str,
        account_id: str,
        external_orders: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> Result[List[Dict[str, Any]], str]:
        """외부몰 주문을 OwnerClan에 등록"""
        sync_history = SyncHistory(
            id=f"collect_orders_{supplier_id}_{self.clock.now().isoformat()}",
            supplier_id=supplier_id,
            sync_type=SyncType.INGEST,  # 주문 수집도 일종의 ingest
            status=SyncStatus.PENDING
        )

        try:
            # 동기화 이력 저장
            await self.repository.save_sync_history(sync_history)
            sync_history.start()

            if not external_orders:
                sync_history.complete(SyncResult())
                await self.repository.save_sync_history(sync_history)
                return Success([])

            # 병렬 처리로 주문 등록
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = [
                self._register_external_order(external_order, supplier_id, account_id, semaphore)
                for external_order in external_orders
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 처리
            registered_orders = []
            sync_result = SyncResult()

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    sync_result.add_failure(
                        external_orders[i].get("external_order_id", f"order_{i}"),
                        str(result)
                    )
                else:
                    registered_orders.append(result)
                    sync_result.add_success(external_orders[i].get("external_order_id", f"order_{i}"))

            # 동기화 완료
            sync_history.complete(sync_result)
            await self.repository.save_sync_history(sync_history)

            if sync_result.failure_count > 0:
                failure_msg = f"일부 주문 등록 실패: {sync_result.failure_count}/{sync_result.total_count}"
                return Failure(failure_msg, registered_orders)

            return Success(registered_orders)

        except Exception as e:
            error_msg = f"주문 수집 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            sync_history.fail(error_msg)
            await self.repository.save_sync_history(sync_history)
            return Failure(error_msg)

    async def _register_external_order(
        self,
        external_order: Dict[str, Any],
        supplier_id: str,
        account_id: str,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """외부 주문을 OwnerClan에 등록"""
        async with semaphore:
            try:
                # 외부 주문 데이터를 OwnerClan 형식으로 변환
                ownerclan_order_data = self._map_external_to_ownerclan_order(external_order)

                # OwnerClan에 주문 등록
                result = await self.supplier_port.create_order(
                    supplier_id=supplier_id,
                    account_id=account_id,
                    order_data=ownerclan_order_data
                )

                # 결과 처리 (주문이 분할될 수 있음)
                created_orders = result if isinstance(result, list) else [result]

                return {
                    "external_order_id": external_order.get("external_order_id"),
                    "ownerclan_orders": created_orders,
                    "created_at": self.clock.now().isoformat()
                }

            except Exception as e:
                logger.error(f"외부 주문 등록 실패 {external_order.get('external_order_id')}: {e}")
                raise

    def _map_external_to_ownerclan_order(self, external_order: Dict[str, Any]) -> Dict[str, Any]:
        """외부 주문 데이터를 OwnerClan 형식으로 매핑"""
        # 상품 매핑 (외부 상품 ID -> OwnerClan itemKey)
        products = []
        for item in external_order.get("items", []):
            # TODO: 실제 상품 매핑 로직 (상품 ID 매핑 테이블 사용)
            item_key = self._map_product_id_to_item_key(item.get("product_id"))

            products.append({
                "itemKey": item_key,
                "quantity": item.get("quantity", 1),
                "optionAttributes": item.get("options", [])
            })

        # 배송 정보 매핑
        shipping_address = external_order.get("shipping_address", {})
        recipient = {
            "name": external_order.get("customer_name", ""),
            "phoneNumber": external_order.get("customer_phone", ""),
            "destinationAddress": {
                "addr1": shipping_address.get("address1", ""),
                "addr2": shipping_address.get("address2", ""),
                "postalCode": shipping_address.get("postal_code", "")
            }
        }

        # 주문 데이터 구성
        order_data = {
            "sender": {
                "name": external_order.get("seller_name", "드랍십핑 셀러"),
                "phoneNumber": external_order.get("seller_phone", ""),
                "email": external_order.get("seller_email", "")
            },
            "recipient": recipient,
            "products": products,
            "note": external_order.get("external_order_id", ""),  # 외부 주문번호 기록
            "sellerNote": external_order.get("order_memo", ""),   # 판매자 메모
            "ordererNote": external_order.get("customer_note", "") # 구매자 요청사항
        }

        return order_data

    def _map_product_id_to_item_key(self, external_product_id: str) -> str:
        """외부 상품 ID를 OwnerClan itemKey로 매핑"""
        # TODO: 실제 상품 매핑 테이블에서 조회
        # 현재는 임시로 그대로 반환
        return external_product_id
