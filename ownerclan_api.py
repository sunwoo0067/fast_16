import httpx
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import logging
import os
import time
import hmac, hashlib
import urllib.parse
import urllib.request
import ssl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from database import SupplierAccount

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OwnerClanAPI:
    """오너클랜 API 클라이언트"""

    def __init__(self, api_url: str = None, auth_url: str = None):
        from ownerclan_credentials import OwnerClanCredentials

        credentials = OwnerClanCredentials.get_api_config()
        self.base_url = api_url or credentials["api_url"]
        self.auth_url = auth_url or credentials["auth_url"]
        self.client = httpx.AsyncClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 클라이언트를 닫지 않도록 수정 (재사용 가능)
        pass

    async def authenticate(self, account_id: str, password: str) -> Dict[str, Any]:
        """JWT 토큰 발급"""
        auth_data = {
            "service": "ownerclan",
            "userType": "seller",
            "username": account_id,
            "password": password
        }

        try:
            response = await self.client.post(
                self.auth_url,
                json=auth_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            # 응답이 JWT 토큰 문자열인 경우 그대로 반환
            content = response.text.strip()
            if content.startswith('eyJ'):  # JWT 토큰 형식 확인
                return {
                    "access_token": content,
                    "token_type": "bearer"
                }
            else:
                # JSON 형태로 시도
                try:
                    return response.json()
                except:
                    return {
                        "access_token": content,
                        "token_type": "bearer"
                    }
        except httpx.RequestError as e:
            raise Exception(f"인증 요청 실패: {e}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"인증 실패: {e.response.status_code} - {e.response.text}")

    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """GraphQL 쿼리 실행"""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await self.client.post(
                self.base_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            # 요청 성공시 통계 업데이트
            if account_id:
                await self._update_request_stats(account_id, success=True)

            return response.json()
        except httpx.RequestError as e:
            # 요청 실패시 통계 업데이트
            if account_id:
                await self._update_request_stats(account_id, success=False)
            raise Exception(f"GraphQL 요청 실패: {e}")
        except httpx.HTTPStatusError as e:
            # 요청 실패시 통계 업데이트
            if account_id:
                await self._update_request_stats(account_id, success=False)
            raise Exception(f"GraphQL 오류: {e.response.status_code} - {e.response.text}")

    async def _update_request_stats(self, account_id: int, success: bool):
        """요청 통계 업데이트 (내부 메서드)"""
        # 이 부분은 실제로는 TokenManager를 통해 처리해야 하지만
        # 여기서는 간단하게 처리하겠습니다
        pass

    async def get_item_info(self, item_key: str, token: str) -> Dict[str, Any]:
        """상품 정보 조회"""
        query = """
        query {
            item(key: "%s") {
                name
                model
                options {
                    price
                    quantity
                    optionAttributes {
                        name
                        value
                    }
                }
            }
        }""" % item_key

        return await self.execute_query(query, token=token)

class CoupangProductAPI:
    """쿠팡 상품 API 클라이언트"""

    def __init__(self, access_key: str, secret_key: str, vendor_id: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.vendor_id = vendor_id
        # 쿠팡 상품 API 엔드포인트
        self.base_url = "https://api-gateway.coupang.com"
        self.client = httpx.AsyncClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _generate_signature(self, method: str, path: str, query_string: str = "", body: str = "") -> str:
        """쿠팡 API HMAC-SHA256 서명 생성"""
        # RFC 3986에서 예약된 문자를 제외하고 인코딩
        path = urllib.parse.quote(path, safe='')

        # 요청 시간 (밀리초)
        timestamp = str(int(time.time() * 1000))

        # 서명할 메시지 구성
        message_parts = [
            method.upper(),
            path,
            query_string,
            body,
            timestamp
        ]
        message = '\n'.join(message_parts)

        # HMAC-SHA256 서명 생성
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    async def make_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """쿠팡 상품 API 요청"""
        # 쿼리 파라미터 인코딩
        query_string = ""
        if query_params:
            query_string = urllib.parse.urlencode(query_params)

        # 요청 URL 구성
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"

        # 기본 헤더
        default_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"CoupangAPIV2 {self.access_key}",
            "X-Coupang-API-Version": "1"
        }

        # 사용자 정의 헤더 추가
        if headers:
            default_headers.update(headers)

        # 요청 바디
        body = ""
        if data:
            body = json.dumps(data, separators=(',', ':'), ensure_ascii=False)

        # 서명 생성
        signature = self._generate_signature(method, path, query_string, body)

        # 서명 헤더 추가
        default_headers["X-Coupang-Signature"] = signature

        try:
            # 요청 실행
            response = await self.client.request(
                method=method.upper(),
                url=url,
                headers=default_headers,
                json=data if data else None
            )
            response.raise_for_status()

            # 응답이 JSON인 경우 파싱
            try:
                return {"status": "success", "data": response.json()}
            except json.JSONDecodeError:
                return {"status": "success", "data": {"message": response.text}}

        except httpx.RequestError as e:
            return {"status": "error", "message": f"요청 실패: {str(e)}"}
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP 오류: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_message += f" - {error_data.get('message', e.response.text)}"
            except:
                error_message += f" - {e.response.text}"

            return {"status": "error", "message": error_message, "code": e.response.status_code}

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """상품 생성"""
        return await self.make_request(
            "POST",
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
            data=product_data
        )

    async def request_approval(self, seller_product_id: str) -> Dict[str, Any]:
        """상품 승인 요청"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/requests/approval"
        )

    async def get_products(
        self,
        max: int = 50,
        next_token: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 목록 조회"""
        query_params = {"max": str(max)}
        if next_token:
            query_params["nextToken"] = next_token
        if status:
            query_params["status"] = status

        return await self.make_request(
            "GET",
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
            query_params=query_params
        )

    async def get_product(self, seller_product_id: str) -> Dict[str, Any]:
        """단일 상품 조회 (승인불필요)"""
        return await self.make_request(
            "GET",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}"
        )

    async def update_product(
        self,
        seller_product_id: str,
        product_data: Dict[str, Any],
        requires_approval: bool = True
    ) -> Dict[str, Any]:
        """상품 수정"""
        endpoint = f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}"
        if not requires_approval:
            endpoint += "/no-approval"

        return await self.make_request(
            "PUT",
            endpoint,
            data=product_data
        )

    async def get_product_registration_status(
        self,
        max: int = 50,
        next_token: Optional[str] = None,
        status: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 등록 현황 조회"""
        query_params = {"max": str(max)}
        if next_token:
            query_params["nextToken"] = next_token
        if status:
            query_params["status"] = status
        if created_at_from:
            query_params["createdAtFrom"] = created_at_from
        if created_at_to:
            query_params["createdAtTo"] = created_at_to
        if updated_at_from:
            query_params["updatedAtFrom"] = updated_at_from
        if updated_at_to:
            query_params["updatedAtTo"] = updated_at_to

        return await self.make_request(
            "GET",
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/registration-status",
            query_params=query_params
        )

    async def get_products_paged(
        self,
        max: int = 50,
        next_token: Optional[str] = None,
        status: Optional[str] = None,
        vendor_item_id: Optional[str] = None,
        seller_product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 목록 페이징 조회"""
        query_params = {"max": str(max)}
        if next_token:
            query_params["nextToken"] = next_token
        if status:
            query_params["status"] = status
        if vendor_item_id:
            query_params["vendorItemId"] = vendor_item_id
        if seller_product_name:
            query_params["sellerProductName"] = seller_product_name

        return await self.make_request(
            "GET",
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
            query_params=query_params
        )

    async def get_products_by_date_range(
        self,
        max: int = 50,
        next_token: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 목록 구간 조회 (날짜 기준)"""
        query_params = {"max": str(max)}
        if next_token:
            query_params["nextToken"] = next_token
        if created_at_from:
            query_params["createdAtFrom"] = created_at_from
        if created_at_to:
            query_params["createdAtTo"] = created_at_to
        if updated_at_from:
            query_params["updatedAtFrom"] = updated_at_from
        if updated_at_to:
            query_params["updatedAtTo"] = updated_at_to

        return await self.make_request(
            "GET",
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
            query_params=query_params
        )

    async def get_product_summary(self, seller_product_id: str) -> Dict[str, Any]:
        """상품 요약 정보 조회"""
        return await self.make_request(
            "GET",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/summary"
        )

    async def get_product_items_status(
        self,
        seller_product_id: str,
        max: int = 50,
        next_token: Optional[str] = None,
        vendor_item_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 수량/가격/상태 조회"""
        query_params = {"max": str(max)}
        if next_token:
            query_params["nextToken"] = next_token
        if vendor_item_id:
            query_params["vendorItemId"] = vendor_item_id
        if status:
            query_params["status"] = status

        return await self.make_request(
            "GET",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items",
            query_params=query_params
        )

    async def update_item_quantity(
        self,
        seller_product_id: str,
        item_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        """상품 아이템별 수량 변경"""
        data = {
            "itemId": item_id,
            "quantity": quantity
        }

        return await self.make_request(
            "PUT",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/quantity",
            data=data
        )

    async def update_item_price(
        self,
        seller_product_id: str,
        item_id: str,
        price: int,
        sale_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 가격 변경"""
        data = {
            "itemId": item_id,
            "price": price
        }
        if sale_price is not None:
            data["salePrice"] = sale_price

        return await self.make_request(
            "PUT",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/price",
            data=data
        )

    async def resume_item_sale(
        self,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """상품 아이템별 판매 재개"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/resume"
        )

    async def stop_item_sale(
        self,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """상품 아이템별 판매 중지"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/stop"
        )

    async def update_item_price_by_discount_rate(
        self,
        seller_product_id: str,
        item_id: str,
        discount_rate: float,
        base_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 할인율 기준 가격 변경"""
        data = {
            "itemId": item_id,
            "discountRate": discount_rate
        }
        if base_price is not None:
            data["basePrice"] = base_price

        return await self.make_request(
            "PUT",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/price-by-discount-rate",
            data=data
        )

    async def activate_auto_generated_options_by_item(
        self,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 활성화 (옵션 상품 단위)"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/auto-generated-options/activate"
        )

    async def activate_auto_generated_options_by_product(
        self,
        seller_product_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 활성화 (전체 상품 단위)"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/auto-generated-options/activate"
        )

    async def deactivate_auto_generated_options_by_item(
        self,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 비활성화 (옵션 상품 단위)"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/items/{item_id}/auto-generated-options/deactivate"
        )

    async def deactivate_auto_generated_options_by_product(
        self,
        seller_product_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 비활성화 (전체 상품 단위)"""
        return await self.make_request(
            "POST",
            f"/v2/providers/seller_api/apis/api/v1/marketplace/seller-products/{seller_product_id}/auto-generated-options/deactivate"
        )


class CoupangWingAPI:
    """쿠팡윙 API 클라이언트"""

    def __init__(self, api_key: str, vendor_id: str):
        self.api_key = api_key
        self.vendor_id = vendor_id
        # 쿠팡윙 API 엔드포인트 (실제 엔드포인트는 문서 확인 필요)
        # 가능한 엔드포인트들: https://api-wing.coupang.com, https://wing-api.coupang.com
        self.base_url = "https://api-wing.coupang.com"

    def _generate_auth_header(self, method: str, path: str, query: str = "") -> str:
        """쿠팡윙 인증 헤더 생성"""
        # 쿠팡윙은 API 키 방식 또는 JWT 토큰 방식을 사용
        # 실제 구현은 쿠팡윙 문서에 따라야 함
        return f"CoupangWing {self.api_key}"

    async def make_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """쿠팡 API 요청"""
        # 쿼리 파라미터 인코딩
        query_string = ""
        if query_params:
            query_string = urllib.parse.urlencode(query_params)

        # 인증 헤더 생성
        auth_header = self._generate_auth_header(method, path, query_string)

        # 요청 URL 구성
        url = f"{self.base_url}{path}"
        if query_string:
            url += f"?{query_string}"

        # 헤더 설정
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": auth_header
        }

        # SSL 컨텍스트 설정 (HTTPS 인증서 검증 비활성화)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            # 동기 HTTP 요청을 asyncio에서 실행
            loop = asyncio.get_event_loop()

            if method.upper() == "GET":
                # urllib을 사용하여 동기 요청 실행
                req = urllib.request.Request(url, headers=headers)
                req.get_method = lambda: method

                response = await loop.run_in_executor(
                    None,
                    lambda: urllib.request.urlopen(req, context=ctx)
                )

                # 응답 데이터 읽기
                response_data = response.read().decode(response.headers.get_content_charset() or 'utf-8')
                return {"status": "success", "data": json.loads(response_data)}

            elif method.upper() == "POST" and data:
                # POST 요청의 경우 JSON 데이터 전송
                json_data = json.dumps(data).encode('utf-8')

                req = urllib.request.Request(url, data=json_data, headers=headers)
                req.get_method = lambda: method

                response = await loop.run_in_executor(
                    None,
                    lambda: urllib.request.urlopen(req, context=ctx)
                )

                response_data = response.read().decode(response.headers.get_content_charset() or 'utf-8')
                return {"status": "success", "data": json.loads(response_data)}

            else:
                return {"status": "error", "message": f"지원하지 않는 메소드: {method}"}

        except urllib.request.HTTPError as e:
            error_message = f"HTTP 오류: {e.code}"
            if e.code == 404:
                error_message = "요청한 리소스를 찾을 수 없습니다 (404)"
            elif e.code == 401:
                error_message = "인증 실패 (401)"
            elif e.code == 403:
                error_message = "접근 권한 없음 (403)"
            elif e.code == 429:
                error_message = "요청 제한 초과 (429)"

            return {"status": "error", "message": error_message, "code": e.code}

        except urllib.request.URLError as e:
            return {"status": "error", "message": f"URL 오류: {e.reason}"}

        except Exception as e:
            return {"status": "error", "message": f"요청 중 오류 발생: {str(e)}"}

    async def get_shipment_list_daily(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """발주서 목록 조회 (일단위 페이징)"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to
        if status:
            query_params["status"] = status

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/shipment-list/daily",
            query_params=query_params
        )

    async def get_shipment_list_minute(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """발주서 목록 조회 (분단위 전체)"""
        query_params = {}
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to
        if status:
            query_params["status"] = status

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/shipment-list/minute",
            query_params=query_params
        )

    async def get_shipment_by_shipment_box_id(self, shipment_box_id: str) -> Dict[str, Any]:
        """발주서 단건 조회 (shipmentBoxId)"""
        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}"
        )

    async def get_shipment_by_order_id(self, order_id: str) -> Dict[str, Any]:
        """발주서 단건 조회 (orderId)"""
        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/shipments/order/{order_id}"
        )

    async def get_shipment_status_history(
        self,
        shipment_box_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """배송상태 변경 히스토리 조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/status-history",
            query_params=query_params
        )

    async def process_product_ready(self, shipment_box_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """상품준비중 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/product-ready",
            data=data
        )

    async def upload_invoice(self, shipment_box_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """송장업로드 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/invoice",
            data=data
        )

    async def update_invoice(self, shipment_box_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """송장업데이트 처리"""
        return await self.make_request(
            "PUT",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/invoice",
            data=data
        )

    async def process_shipping_stopped(self, shipment_box_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """출고중지완료 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/shipping-stopped",
            data=data
        )

    async def process_already_shipped(self, shipment_box_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """이미출고 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/shipments/{shipment_box_id}/already-shipped",
            data=data
        )

    async def cancel_order_item(self, order_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """주문 상품 취소 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/orders/{order_id}/cancel",
            data=data
        )

    async def complete_long_delivery(self, order_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """장기미배송 배송완료 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/orders/{order_id}/complete-long-delivery",
            data=data
        )

    # 반품 관련 API
    async def get_return_requests(
        self,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """반품 취소 요청 목록 조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if status:
            query_params["status"] = status
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/return-requests",
            query_params=query_params
        )

    async def get_return_request_detail(self, return_request_id: str) -> Dict[str, Any]:
        """반품요청 단건 조회"""
        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/return-requests/{return_request_id}"
        )

    async def confirm_return_receipt(self, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """반품상품 입고 확인처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/return-requests/{return_request_id}/receipt",
            data=data
        )

    async def approve_return_request(self, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """반품요청 승인 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/return-requests/{return_request_id}/approve",
            data=data
        )

    async def get_return_withdrawal_history_by_period(
        self,
        date_from: str,
        date_to: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """반품철회 이력 기간별 조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset),
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/return-withdrawal-history",
            query_params=query_params
        )

    async def get_return_withdrawal_history_by_receipt_number(self, receipt_number: str) -> Dict[str, Any]:
        """반품철회 이력 접수번호로 조회"""
        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/return-withdrawal-history/{receipt_number}"
        )

    async def register_return_invoice(self, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """회수 송장 등록"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/return-requests/{return_request_id}/invoice",
            data=data
        )

    # 교환 관련 API
    async def get_exchange_requests(
        self,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """교환요청 목록조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if status:
            query_params["status"] = status
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/exchange-requests",
            query_params=query_params
        )

    async def confirm_exchange_receipt(self, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환요청상품 입고 확인처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/exchange-requests/{exchange_request_id}/receipt",
            data=data
        )

    async def reject_exchange_request(self, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환요청 거부 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/exchange-requests/{exchange_request_id}/reject",
            data=data
        )

    async def upload_exchange_invoice(self, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환상품 송장 업로드 처리"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/exchange-requests/{exchange_request_id}/invoice",
            data=data
        )

    # 상품별 고객문의 관련 API
    async def get_product_inquiries(
        self,
        seller_product_id: str,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """상품별 고객문의 조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if status:
            query_params["status"] = status
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/products/{seller_product_id}/inquiries",
            query_params=query_params
        )

    async def reply_to_product_inquiry(
        self,
        seller_product_id: str,
        inquiry_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """상품별 고객문의 답변"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/products/{seller_product_id}/inquiries/{inquiry_id}/reply",
            data=data
        )

    # 쿠팡 고객센터 문의 관련 API
    async def get_cs_inquiries(
        self,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """쿠팡 고객센터 문의조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if status:
            query_params["status"] = status
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/cs-inquiries",
            query_params=query_params
        )

    async def get_cs_inquiry_detail(self, inquiry_id: str) -> Dict[str, Any]:
        """쿠팡 고객센터 문의 단건 조회"""
        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/cs-inquiries/{inquiry_id}"
        )

    async def reply_to_cs_inquiry(
        self,
        inquiry_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """쿠팡 고객센터 문의답변"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/cs-inquiries/{inquiry_id}/reply",
            data=data
        )

    async def confirm_cs_inquiry(self, inquiry_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """쿠팡 고객센터 문의확인"""
        return await self.make_request(
            "POST",
            f"/vendors/{self.vendor_id}/cs-inquiries/{inquiry_id}/confirm",
            data=data
        )

    # 매출 및 지급 관련 API
    async def get_sales_history(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """매출내역 조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/sales-history",
            query_params=query_params
        )

    async def get_payment_history(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """지급내역조회"""
        query_params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        if date_from:
            query_params["dateFrom"] = date_from
        if date_to:
            query_params["dateTo"] = date_to

        return await self.make_request(
            "GET",
            f"/vendors/{self.vendor_id}/payment-history",
            query_params=query_params
        )

class TokenManager:
    """토큰 관리 클래스"""

    def __init__(self, db: AsyncSession, ownerclan_api: OwnerClanAPI):
        self.db = db
        self.ownerclan_api = ownerclan_api
        self.token_refresh_threshold = timedelta(days=25)  # 30일 중 25일 후 갱신

    async def get_valid_token(self, supplier_id: int) -> Optional[str]:
        """유효한 토큰 조회 또는 갱신"""
        result = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.warning(f"공급사 계정을 찾을 수 없습니다: supplier_id={supplier_id}")
            return None

        now = datetime.now(account.token_expires_at.tzinfo) if account.token_expires_at else datetime.now()

        # 토큰 만료 확인
        if account.token_expires_at and account.token_expires_at <= now:
            # 토큰 만료됨 - 갱신 시도
            logger.info(f"토큰 만료로 갱신 시도: supplier_id={supplier_id}")
            return await self.refresh_token(account)
        elif account.access_token:
            # 토큰이 유효하지만 갱신 임계점 확인
            if self._should_refresh_token(account.token_expires_at):
                logger.info(f"토큰 갱신 임계점 도달, 사전 갱신: supplier_id={supplier_id}")
                refreshed_token = await self.refresh_token(account)
                if refreshed_token:
                    return refreshed_token

            # 유효한 토큰이 있으면 사용 횟수 업데이트 후 반환
            await self.update_last_used(account.id)
            logger.info(f"유효한 토큰 재사용: supplier_id={supplier_id}")
            return account.access_token

        logger.warning(f"유효한 토큰이 없습니다: supplier_id={supplier_id}")
        return None

    def _should_refresh_token(self, expires_at: datetime) -> bool:
        """토큰을 갱신해야 하는지 확인"""
        if not expires_at:
            return False
        now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
        return now + self.token_refresh_threshold >= expires_at

    async def refresh_all_tokens(self) -> Dict[str, Any]:
        """모든 계정의 토큰을 일괄 갱신"""
        result = await self.db.execute(
            select(SupplierAccount).where(SupplierAccount.is_active == True)
        )
        accounts = result.scalars().all()

        results = {
            "total": len(accounts),
            "refreshed": 0,
            "failed": 0,
            "skipped": 0
        }

        for account in accounts:
            try:
                if self._should_refresh_token(account.token_expires_at):
                    new_token = await self.refresh_token(account)
                    if new_token:
                        results["refreshed"] += 1
                        logger.info(f"토큰 갱신 성공: supplier_id={account.supplier_id}")
                    else:
                        results["failed"] += 1
                        logger.error(f"토큰 갱신 실패: supplier_id={account.supplier_id}")
                else:
                    results["skipped"] += 1
            except Exception as e:
                results["failed"] += 1
                logger.error(f"토큰 갱신 중 오류: supplier_id={account.supplier_id}, error={e}")

        return results

    async def refresh_token(self, account: SupplierAccount) -> Optional[str]:
        """토큰 갱신"""
        try:
            # 새로운 토큰 발급
            auth_response = await self.ownerclan_api.authenticate(
                account.username,
                account.password_encrypted
            )

            # 토큰 정보 업데이트
            await self.db.execute(
                update(SupplierAccount).where(
                    SupplierAccount.id == account.id
                ).values(
                    access_token=auth_response.get("access_token"),
                    refresh_token=auth_response.get("refresh_token"),
                    token_expires_at=datetime.now() + timedelta(days=30),
                    last_used_at=datetime.now()
                )
            )
            await self.db.commit()

            return auth_response.get("access_token")
        except Exception as e:
            print(f"토큰 갱신 실패: {e}")
            return None

    async def update_last_used(self, account_id: int):
        """마지막 사용 시간 및 사용량 업데이트"""
        await self.db.execute(
            update(SupplierAccount).where(
                SupplierAccount.id == account_id
            ).values(
                last_used_at=datetime.now(),
                usage_count=SupplierAccount.usage_count + 1,
                total_requests=SupplierAccount.total_requests + 1
            )
        )
        await self.db.commit()

    async def update_request_stats(self, account_id: int, success: bool = True):
        """요청 통계 업데이트"""
        update_values = {
            "total_requests": SupplierAccount.total_requests + 1
        }
        if success:
            update_values["successful_requests"] = SupplierAccount.successful_requests + 1
        else:
            update_values["failed_requests"] = SupplierAccount.failed_requests + 1

        await self.db.execute(
            update(SupplierAccount).where(
                SupplierAccount.id == account_id
            ).values(**update_values)
        )
        await self.db.commit()

    async def get_token_usage_stats(self, supplier_id: int) -> Optional[Dict[str, Any]]:
        """토큰 사용 통계 조회"""
        result = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            return None

        return {
            "account_id": account.account_id,
            "usage_count": account.usage_count,
            "total_requests": account.total_requests,
            "successful_requests": account.successful_requests,
            "failed_requests": account.failed_requests,
            "success_rate": (account.successful_requests / account.total_requests * 100) if account.total_requests > 0 else 0,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
            "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None
        }

    async def create_account(
        self,
        supplier_id: int,
        account_id: str,
        password: str
    ) -> SupplierAccount:
        """공급사계정 생성 및 초기 토큰 발급"""
        try:
            # 초기 토큰 발급
            auth_response = await self.ownerclan_api.authenticate(account_id, password)

            new_account = SupplierAccount(
                supplier_id=supplier_id,
                account_name=f"OwnerClan Account {supplier_id}",
                username=account_id,
                password_encrypted=password,
                access_token=auth_response.get("access_token"),
                refresh_token=auth_response.get("refresh_token"),
                token_expires_at=datetime.now() + timedelta(days=30),
                is_active=True
            )

            self.db.add(new_account)
            await self.db.commit()
            await self.db.refresh(new_account)

            return new_account
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"계정 생성 실패: {e}")

# 전역 인스턴스
ownerclan_api = OwnerClanAPI()
