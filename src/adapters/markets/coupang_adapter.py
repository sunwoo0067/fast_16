"""쿠팡 마켓 어댑터"""
import httpx
import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from datetime import datetime
import json
import logging

from src.core.ports.market_port import (
    MarketPort, MarketCredentials, MarketProduct, UploadResult, SyncStatus, MarketType
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class CoupangAdapter(MarketPort):
    """쿠팡 API 어댑터"""

    def __init__(
        self,
        base_url: str = "https://api-gateway.coupang.com",
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def authenticate(self, credentials: MarketCredentials) -> bool:
        """쿠팡 인증 (액세스 키 검증)"""
        try:
            # 쿠팡은 사전 서명된 요청으로 인증
            test_request = await self._make_signed_request(
                "GET",
                "/v2/providers/seller_api/apis/api/v1/marketplace/meta/vendors",
                credentials
            )

            return test_request.status_code == 200

        except Exception as e:
            logger.error(f"쿠팡 인증 실패: {e}")
            return False

    async def upload_product(
        self,
        credentials: MarketCredentials,
        product: MarketProduct
    ) -> UploadResult:
        """쿠팡 상품 업로드"""
        try:
            payload = self._build_product_payload(product)

            response = await self._make_signed_request(
                "POST",
                "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
                credentials,
                payload
            )

            if response.status_code == 200:
                result_data = response.json()
                return UploadResult(
                    success=True,
                    product_id=result_data.get("productId"),
                    channel_product_no=result_data.get("channelProductNo")
                )
            else:
                return UploadResult(
                    success=False,
                    error_message=f"업로드 실패: {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"쿠팡 상품 업로드 실패: {e}")
            return UploadResult(
                success=False,
                error_message=str(e)
            )

    async def update_product(
        self,
        credentials: MarketCredentials,
        product_id: str,
        product: MarketProduct
    ) -> UploadResult:
        """쿠팡 상품 수정"""
        try:
            payload = self._build_product_payload(product)

            response = await self._make_signed_request(
                "PUT",
                f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{product_id}",
                credentials,
                payload
            )

            if response.status_code == 200:
                return UploadResult(success=True, product_id=product_id)
            else:
                return UploadResult(
                    success=False,
                    error_message=f"수정 실패: {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"쿠팡 상품 수정 실패: {e}")
            return UploadResult(
                success=False,
                error_message=str(e)
            )

    async def get_product_status(
        self,
        credentials: MarketCredentials,
        product_id: str
    ) -> SyncStatus:
        """쿠팡 상품 동기화 상태 조회"""
        try:
            response = await self._make_signed_request(
                "GET",
                f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{product_id}",
                credentials
            )

            if response.status_code == 200:
                product_data = response.json()
                return SyncStatus(
                    last_synced_at=datetime.now(),
                    status=product_data.get("status", "unknown")
                )
            else:
                return SyncStatus(
                    last_synced_at=datetime.now(),
                    status="error",
                    error_message=f"조회 실패: {response.status_code}"
                )

        except Exception as e:
            logger.error(f"쿠팡 상품 상태 조회 실패: {e}")
            return SyncStatus(
                last_synced_at=datetime.now(),
                status="error",
                error_message=str(e)
            )

    async def update_inventory(
        self,
        credentials: MarketCredentials,
        product_id: str,
        quantity: int
    ) -> bool:
        """쿠팡 재고 업데이트"""
        try:
            payload = {
                "sellerProductId": product_id,
                "quantity": quantity
            }

            response = await self._make_signed_request(
                "PUT",
                "/v2/providers/seller_api/apis/api/v1/inventories",
                credentials,
                payload
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"쿠팡 재고 업데이트 실패: {e}")
            return False

    async def update_price(
        self,
        credentials: MarketCredentials,
        product_id: str,
        price: int
    ) -> bool:
        """쿠팡 가격 업데이트"""
        try:
            payload = {
                "sellerProductId": product_id,
                "price": price
            }

            response = await self._make_signed_request(
                "PUT",
                "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/prices",
                credentials,
                payload
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"쿠팡 가격 업데이트 실패: {e}")
            return False

    def _make_signed_request(
        self,
        method: str,
        path: str,
        credentials: MarketCredentials,
        data: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """쿠팡 서명된 요청 생성"""
        timestamp = str(int(time.time() * 1000))
        url = f"{self.base_url}{path}"

        # 요청 데이터 준비
        body = json.dumps(data) if data else ""

        # 서명 문자열 생성
        message = f"{method}{path}{timestamp}{body}"
        signature = hmac.new(
            credentials.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 헤더 생성
        headers = {
            "Content-Type": "application/json",
            "X-Coupang-Signature": signature,
            "X-Coupang-Access-Key": credentials.api_key,
            "X-Coupang-Timestamp": timestamp
        }

        # 요청 실행
        if method.upper() == "GET":
            return self.client.get(url, headers=headers)
        elif method.upper() == "POST":
            return self.client.post(url, headers=headers, content=body)
        elif method.upper() == "PUT":
            return self.client.put(url, headers=headers, content=body)
        else:
            raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")

    def _build_product_payload(self, product: MarketProduct) -> Dict[str, Any]:
        """쿠팡 상품 페이로드 생성"""
        return {
            "sellerProductName": product.title,
            "sellerProductId": product.id,
            "salePrice": product.price,
            "maximumQuantity": product.stock,
            "images": [
                {"imageUrl": img_url} for img_url in product.images
            ],
            "categoryCode": product.category_id,
            "attributes": product.attributes,
            "description": product.description or ""
        }
