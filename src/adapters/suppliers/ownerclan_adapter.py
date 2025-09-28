"""OwnerClan 공급사 어댑터"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from src.core.ports.supplier_port import (
    SupplierPort, SupplierCredentials, RawItemData
)
from src.core.entities.account import TokenInfo
from src.shared.logging import get_logger

logger = get_logger(__name__)


class OwnerClanAdapter(SupplierPort):
    """OwnerClan API 어댑터"""

    def __init__(
        self,
        api_url: str,
        auth_url: str,
        timeout: int = 30
    ):
        self.api_url = api_url
        self.auth_url = auth_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def authenticate(self, credentials: SupplierCredentials) -> str:
        """OwnerClan 인증 및 JWT 토큰 발급"""
        auth_data = {
            "service": "ownerclan",
            "userType": "seller",
            "username": credentials.username,
            "password": credentials.password
        }

        try:
            response = await self.client.post(
                self.auth_url,
                json=auth_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            # JWT 토큰 추출
            token = response.text.strip()
            if not token.startswith('eyJ'):
                raise ValueError("Invalid JWT token format")

            return token

        except httpx.RequestError as e:
            logger.error(f"OwnerClan 인증 요청 실패: {e}")
            raise Exception(f"인증 요청 실패: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"OwnerClan 인증 실패: {e.response.status_code} - {e.response.text}")
            raise Exception(f"인증 실패: {e.response.status_code} - {e.response.text}")

    async def fetch_items(
        self,
        supplier_id: str,
        account_id: str,
        item_keys: Optional[List[str]] = None
    ) -> List[RawItemData]:
        """상품 데이터 수집"""
        # OwnerClan GraphQL 쿼리
        query = """
        query GetProducts($accountId: String!, $itemKeys: [String!]) {
            products(accountId: $accountId, itemKeys: $itemKeys) {
                id
                title
                brand
                price
                options
                images
                category
                description
                supplier_name
                supplier_url
                estimated_shipping_days
            }
        }
        """

        variables = {
            "accountId": account_id,
            "itemKeys": item_keys
        }

        try:
            # 임시 토큰 (실제로는 의존성 주입을 통해 받아야 함)
            # TODO: 토큰 관리를 위한 TokenStore 구현
            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username="",  # 실제로는 credentials에서 가져와야 함
                password=""
            ))

            response = await self._execute_query(query, variables, token)

            products_data = response.get("data", {}).get("products", [])

            return [
                self._map_to_raw_item(product_data)
                for product_data in products_data
            ]

        except Exception as e:
            logger.error(f"OwnerClan 상품 수집 실패: {e}")
            raise

    async def get_categories(self, supplier_id: str, account_id: str) -> List[Dict[str, Any]]:
        """카테고리 정보 조회"""
        query = """
        query GetCategories($accountId: String!) {
            categories(accountId: $accountId) {
                id
                name
                parent_id
                level
            }
        }
        """

        try:
            # 임시 토큰 (실제로는 TokenStore에서 가져와야 함)
            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username="",
                password=""
            ))

            response = await self._execute_query(query, {"accountId": account_id}, token)

            return response.get("data", {}).get("categories", [])

        except Exception as e:
            logger.error(f"OwnerClan 카테고리 조회 실패: {e}")
            raise

    async def check_credentials(self, credentials: SupplierCredentials) -> bool:
        """인증 정보 유효성 검증"""
        try:
            await self.authenticate(credentials)
            return True
        except Exception:
            return False

    async def _execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """GraphQL 쿼리 실행"""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=headers
        )
        response.raise_for_status()

        return response.json()

    def _map_to_raw_item(self, product_data: Dict[str, Any]) -> RawItemData:
        """OwnerClan 데이터를 RawItemData로 매핑"""
        return RawItemData(
            id=product_data["id"],
            title=product_data["title"],
            brand=product_data.get("brand", ""),
            price=product_data.get("price", {}),
            options=product_data.get("options", []),
            images=product_data.get("images", []),
            category=product_data.get("category", ""),
            description=product_data.get("description"),
            supplier_id=product_data.get("supplier_name", ""),
            fetched_at=datetime.now()
        )
