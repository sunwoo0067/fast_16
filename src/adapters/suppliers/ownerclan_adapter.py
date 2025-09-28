"""OwnerClan 공급사 어댑터 (드랍십핑 자동화)"""
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import json
import logging

from src.core.ports.supplier_port import (
    SupplierPort, SupplierCredentials, RawItemData
)
from src.core.entities.account import TokenInfo
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OwnerClanItem:
    """OwnerClan 상품 정보 (실제 API 구조)"""
    key: str
    name: str
    model: Optional[str] = None
    production: Optional[str] = None
    origin: Optional[str] = None
    id: Optional[str] = None
    price: int = 0
    price_policy: Optional[Dict[str, Any]] = None
    fixed_price: Optional[int] = None
    search_keywords: Optional[str] = None
    category: Optional[Dict[str, str]] = None
    content: Optional[str] = None
    shipping_fee: Optional[int] = None
    shipping_type: Optional[str] = None
    images: List[str] = field(default_factory=list)
    status: str = "active"
    options: List[Dict[str, Any]] = field(default_factory=list)
    tax_free: bool = False
    adult_only: bool = False
    returnable: bool = True
    no_return_reason: Optional[str] = None
    guaranteed_shipping_period: Optional[int] = None
    openmarket_sellable: bool = True
    box_quantity: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    closing_time: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class OwnerClanOrder:
    """OwnerClan 주문 정보"""
    key: str
    status: str
    tracking_number: Optional[str] = None
    shipping_company_name: Optional[str] = None
    shipped_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class OwnerClanItemHistory:
    """OwnerClan 상품 변경 이력"""
    item_key: str
    kind: str  # soldout, priceChanged, etc.
    value_before: Any
    value_after: Any
    created_at: datetime


@dataclass
class OwnerClanQnaArticle:
    """OwnerClan 1:1 문의글"""
    key: str
    type: str
    title: str
    content: str
    created_at: datetime
    related_order_key: Optional[str] = None


@dataclass
class OwnerClanEmergencyMessage:
    """OwnerClan 긴급 메시지"""
    key: str
    type: str
    content: str
    penalty: int
    status: str  # Unanswered, Answered, etc.
    created_at: datetime


class OwnerClanAdapter(SupplierPort):
    """OwnerClan API 어댑터 (실제 API 연동)"""

    def __init__(
        self,
        api_url: str = "https://api-sandbox.ownerclan.com/v1/graphql",
        auth_url: str = "https://auth.ownerclan.com/auth",
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

    async def fetch_items_by_price_range(
        self,
        supplier_id: str,
        account_id: str,
        min_price: int,
        max_price: int,
        first: int = 100
    ) -> List[OwnerClanItem]:
        """가격 범위로 상품 조회"""
        query = """
        query GetItemsByPrice($minPrice: Int!, $maxPrice: Int!, $first: Int!) {
            allItems(priceFrom: $minPrice, priceTo: $maxPrice, first: $first) {
                edges {
                    node {
                        createdAt
                        updatedAt
                        key
                        name
                        price
                        category {
                            key
                            name
                        }
                        status
                        options {
                            price
                            quantity
                        }
                    }
                }
            }
        }
        """

        variables = {
            "minPrice": min_price,
            "maxPrice": max_price,
            "first": first
        }

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            items_data = response.get("data", {}).get("allItems", {})

            items = []
            for edge in items_data.get("edges", []):
                node = edge.get("node", {})
                item = OwnerClanItem(
                    key=node.get("key", ""),
                    name=node.get("name", ""),
                    price=node.get("price", 0),
                    status=node.get("status", "active"),
                    category=node.get("category"),
                    created_at=datetime.fromisoformat(node.get("createdAt")) if node.get("createdAt") else None,
                    updated_at=datetime.fromisoformat(node.get("updatedAt")) if node.get("updatedAt") else None,
                    options=node.get("options", [])
                )
                items.append(item)

            return items

        except Exception as e:
            logger.error(f"OwnerClan 가격 범위 상품 조회 실패: {e}")
            raise

    async def fetch_items_by_category(
        self,
        supplier_id: str,
        account_id: str,
        category_key: str,
        first: int = 100
    ) -> List[OwnerClanItem]:
        """카테고리로 상품 조회"""
        query = """
        query GetItemsByCategory($categoryKey: String!, $first: Int!) {
            allItems(categoryKey: $categoryKey, first: $first) {
                edges {
                    node {
                        createdAt
                        updatedAt
                        key
                        name
                        price
                        status
                        category {
                            key
                            name
                        }
                    }
                }
            }
        }
        """

        variables = {
            "categoryKey": category_key,
            "first": first
        }

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            items_data = response.get("data", {}).get("allItems", {})

            items = []
            for edge in items_data.get("edges", []):
                node = edge.get("node", {})
                item = OwnerClanItem(
                    key=node.get("key", ""),
                    name=node.get("name", ""),
                    price=node.get("price", 0),
                    status=node.get("status", "active"),
                    category=node.get("category"),
                    created_at=datetime.fromisoformat(node.get("createdAt")) if node.get("createdAt") else None,
                    updated_at=datetime.fromisoformat(node.get("updatedAt")) if node.get("updatedAt") else None
                )
                items.append(item)

            return items

        except Exception as e:
            logger.error(f"OwnerClan 카테고리 상품 조회 실패: {e}")
            raise

    async def fetch_items_by_vendor(
        self,
        supplier_id: str,
        account_id: str,
        vendor_code: str,
        first: int = 100
    ) -> List[OwnerClanItem]:
        """벤더 코드로 상품 조회"""
        query = """
        query GetItemsByVendor($vendorCode: String!, $first: Int!) {
            allItems(vendorCode: $vendorCode, first: $first) {
                edges {
                    node {
                        createdAt
                        updatedAt
                        key
                        name
                        price
                        status
                        origin
                    }
                }
            }
        }
        """

        variables = {
            "vendorCode": vendor_code,
            "first": first
        }

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            items_data = response.get("data", {}).get("allItems", {})

            items = []
            for edge in items_data.get("edges", []):
                node = edge.get("node", {})
                item = OwnerClanItem(
                    key=node.get("key", ""),
                    name=node.get("name", ""),
                    price=node.get("price", 0),
                    status=node.get("status", "active"),
                    origin=node.get("origin"),
                    created_at=datetime.fromisoformat(node.get("createdAt")) if node.get("createdAt") else None,
                    updated_at=datetime.fromisoformat(node.get("updatedAt")) if node.get("updatedAt") else None
                )
                items.append(item)

            return items

        except Exception as e:
            logger.error(f"OwnerClan 벤더 상품 조회 실패: {e}")
            raise

    async def fetch_all_items(
        self,
        supplier_id: str,
        account_id: str,
        first: int = 100,
        after: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None
    ) -> Tuple[List[OwnerClanItem], Optional[str]]:
        """페이징을 지원하는 전체 상품 조회 (실제 OwnerClan API 구조)"""
        query = """
        query GetAllItems($first: Int!, $after: String, $dateFrom: Int, $dateTo: Int) {
            allItems(first: $first, after: $after, dateFrom: $dateFrom, dateTo: $dateTo) {
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
                    node {
                        createdAt
                        updatedAt
                        key
                        name
                        model
                        production
                        origin
                        id
                        price
                        pricePolicy
                        fixedPrice
                        searchKeywords
                        category {
                            key
                            name
                        }
                        content
                        shippingFee
                        shippingType
                        images(size: large)
                        status
                        options {
                            optionAttributes {
                                name
                                value
                            }
                            price
                            quantity
                            key
                        }
                        taxFree
                        adultOnly
                        returnable
                        noReturnReason
                        guaranteedShippingPeriod
                        openmarketSellable
                        boxQuantity
                        attributes
                        closingTime
                        metadata
                    }
                }
            }
        }
        """

        variables = {
            "first": first,
            "after": after,
            "dateFrom": date_from,
            "dateTo": date_to
        }

        # None 값은 제외
        variables = {k: v for k, v in variables.items() if v is not None}

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            items_data = response.get("data", {}).get("allItems", {})

            edges = items_data.get("edges", [])
            page_info = items_data.get("pageInfo", {})

            items = []
            for edge in edges:
                node = edge.get("node", {})
                item = OwnerClanItem(
                    key=node.get("key", ""),
                    name=node.get("name", ""),
                    model=node.get("model"),
                    production=node.get("production"),
                    origin=node.get("origin"),
                    id=node.get("id"),
                    price=node.get("price", 0),
                    price_policy=node.get("pricePolicy"),
                    fixed_price=node.get("fixedPrice"),
                    search_keywords=node.get("searchKeywords"),
                    category=node.get("category"),
                    content=node.get("content"),
                    shipping_fee=node.get("shippingFee"),
                    shipping_type=node.get("shippingType"),
                    images=[img.get("url") if isinstance(img, dict) else img for img in node.get("images", [])],
                    status=node.get("status", "active"),
                    options=[
                        {
                            "optionAttributes": opt.get("optionAttributes", []),
                            "price": opt.get("price", 0),
                            "quantity": opt.get("quantity", 0),
                            "key": opt.get("key")
                        }
                        for opt in node.get("options", [])
                    ],
                    tax_free=node.get("taxFree", False),
                    adult_only=node.get("adultOnly", False),
                    returnable=node.get("returnable", True),
                    no_return_reason=node.get("noReturnReason"),
                    guaranteed_shipping_period=node.get("guaranteedShippingPeriod"),
                    openmarket_sellable=node.get("openmarketSellable", True),
                    box_quantity=node.get("boxQuantity"),
                    attributes=node.get("attributes"),
                    closing_time=datetime.fromisoformat(node.get("closingTime")) if node.get("closingTime") else None,
                    metadata=node.get("metadata"),
                    created_at=datetime.fromisoformat(node.get("createdAt")) if node.get("createdAt") else None,
                    updated_at=datetime.fromisoformat(node.get("updatedAt")) if node.get("updatedAt") else None
                )
                items.append(item)

            next_cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None
            return items, next_cursor

        except Exception as e:
            logger.error(f"OwnerClan 전체 상품 조회 실패: {e}")
            raise

    async def fetch_item_histories(
        self,
        supplier_id: str,
        account_id: str,
        first: int = 100,
        date_from: Optional[int] = None,
        kind: Optional[str] = None
    ) -> List[OwnerClanItemHistory]:
        """상품 변경 이력 조회"""
        query = """
        query GetItemHistories($first: Int!, $dateFrom: Int, $kind: String) {
            itemHistories(first: $first, dateFrom: $dateFrom, kind: $kind) {
                edges {
                    node {
                        itemKey
                        kind
                        valueBefore
                        valueAfter
                        createdAt
                    }
                }
            }
        }
        """

        variables = {
            "first": first,
            "dateFrom": date_from,
            "kind": kind
        }

        # None 값은 쿼리에서 제외
        if date_from is None:
            del variables["dateFrom"]
        if kind is None:
            del variables["kind"]

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            histories_data = response.get("data", {}).get("itemHistories", {})

            histories = []
            for edge in histories_data.get("edges", []):
                node = edge.get("node", {})
                history = OwnerClanItemHistory(
                    item_key=node.get("itemKey", ""),
                    kind=node.get("kind", ""),
                    value_before=node.get("valueBefore"),
                    value_after=node.get("valueAfter"),
                    created_at=datetime.fromisoformat(node.get("createdAt"))
                )
                histories.append(history)

            return histories

        except Exception as e:
            logger.error(f"OwnerClan 상품 이력 조회 실패: {e}")
            raise

    async def create_order(
        self,
        supplier_id: str,
        account_id: str,
        order_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """주문 생성"""
        mutation = """
        mutation CreateOrder($input: OrderInput!) {
            createOrder(input: $input) {
                key
                status
                products {
                    itemKey
                    quantity
                }
            }
        }
        """

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(mutation, {"input": order_data}, token)
            order_result = response.get("data", {}).get("createOrder", {})

            return order_result

        except Exception as e:
            logger.error(f"OwnerClan 주문 생성 실패: {e}")
            raise

    async def fetch_orders(
        self,
        supplier_id: str,
        account_id: str,
        first: int = 50,
        shipped_after: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[OwnerClanOrder]:
        """주문 목록 조회"""
        query = """
        query GetOrders($first: Int!, $shippedAfter: Int, $status: String) {
            allOrders(first: $first, shippedAfter: $shippedAfter, status: $status) {
                edges {
                    node {
                        key
                        status
                        trackingNumber
                        shippingCompanyName
                        shippedDate
                        createdAt
                    }
                }
            }
        }
        """

        variables = {
            "first": first,
            "shippedAfter": shipped_after,
            "status": status
        }

        # None 값은 쿼리에서 제외
        if shipped_after is None:
            del variables["shippedAfter"]
        if status is None:
            del variables["status"]

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            orders_data = response.get("data", {}).get("allOrders", {})

            orders = []
            for edge in orders_data.get("edges", []):
                node = edge.get("node", {})
                order = OwnerClanOrder(
                    key=node.get("key", ""),
                    status=node.get("status", ""),
                    tracking_number=node.get("trackingNumber"),
                    shipping_company_name=node.get("shippingCompanyName"),
                    shipped_date=datetime.fromisoformat(node.get("shippedDate")) if node.get("shippedDate") else None,
                    created_at=datetime.fromisoformat(node.get("createdAt")) if node.get("createdAt") else None
                )
                orders.append(order)

            return orders

        except Exception as e:
            logger.error(f"OwnerClan 주문 조회 실패: {e}")
            raise

    async def cancel_order(
        self,
        supplier_id: str,
        account_id: str,
        order_key: str
    ) -> Dict[str, Any]:
        """주문 취소"""
        mutation = """
        mutation CancelOrder($key: String!) {
            cancelOrder(key: $key) {
                key
                status
            }
        }
        """

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(mutation, {"key": order_key}, token)
            cancel_result = response.get("data", {}).get("cancelOrder", {})

            return cancel_result

        except Exception as e:
            logger.error(f"OwnerClan 주문 취소 실패: {e}")
            raise

    async def request_refund_or_exchange(
        self,
        supplier_id: str,
        account_id: str,
        order_key: str,
        refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """반품/교환 요청"""
        mutation = """
        mutation RequestRefundOrExchange($key: String!, $input: RefundExchangeOrderInput!) {
            requestRefundOrExchange(key: $key, input: $input) {
                key
                status
                refundDetails {
                    status
                    reason
                }
            }
        }
        """

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(
                mutation,
                {"key": order_key, "input": refund_data},
                token
            )
            refund_result = response.get("data", {}).get("requestRefundOrExchange", {})

            return refund_result

        except Exception as e:
            logger.error(f"OwnerClan 반품/교환 요청 실패: {e}")
            raise

    async def fetch_qna_articles(
        self,
        supplier_id: str,
        account_id: str,
        first: int = 10,
        date_from: Optional[int] = None
    ) -> List[OwnerClanQnaArticle]:
        """1:1 문의글 조회"""
        query = """
        query GetQnaArticles($first: Int!, $dateFrom: Int) {
            allSellerQnaArticles(first: $first, dateFrom: $dateFrom) {
                edges {
                    node {
                        key
                        type
                        title
                        content
                        createdAt
                        relatedOrderKey
                    }
                }
            }
        }
        """

        variables = {
            "first": first,
            "dateFrom": date_from
        }

        if date_from is None:
            del variables["dateFrom"]

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            qna_data = response.get("data", {}).get("allSellerQnaArticles", {})

            articles = []
            for edge in qna_data.get("edges", []):
                node = edge.get("node", {})
                article = OwnerClanQnaArticle(
                    key=node.get("key", ""),
                    type=node.get("type", ""),
                    title=node.get("title", ""),
                    content=node.get("content", ""),
                    created_at=datetime.fromisoformat(node.get("createdAt")),
                    related_order_key=node.get("relatedOrderKey")
                )
                articles.append(article)

            return articles

        except Exception as e:
            logger.error(f"OwnerClan 문의글 조회 실패: {e}")
            raise

    async def fetch_emergency_messages(
        self,
        supplier_id: str,
        account_id: str,
        first: int = 5,
        status: Optional[str] = None
    ) -> List[OwnerClanEmergencyMessage]:
        """긴급 메시지 조회"""
        query = """
        query GetEmergencyMessages($first: Int!, $status: String) {
            allEmergencyMessages(first: $first, status: $status) {
                edges {
                    node {
                        key
                        type
                        content
                        penalty
                        status
                        createdAt
                    }
                }
            }
        }
        """

        variables = {
            "first": first,
            "status": status
        }

        if status is None:
            del variables["status"]

        try:
            # 실제 인증 정보 로드 (환경변수에서)
            import os
            username = os.getenv('OWNERCLAN_USERNAME', '')
            password = os.getenv('OWNERCLAN_PASSWORD', '')

            if not username or not password:
                raise ValueError("OwnerClan 인증 정보가 설정되지 않았습니다")

            token = await self.authenticate(SupplierCredentials(
                supplier_id=supplier_id,
                account_id=account_id,
                username=username,
                password=password
            ))

            response = await self._execute_query(query, variables, token)
            messages_data = response.get("data", {}).get("allEmergencyMessages", {})

            messages = []
            for edge in messages_data.get("edges", []):
                node = edge.get("node", {})
                message = OwnerClanEmergencyMessage(
                    key=node.get("key", ""),
                    type=node.get("type", ""),
                    content=node.get("content", ""),
                    penalty=node.get("penalty", 0),
                    status=node.get("status", ""),
                    created_at=datetime.fromisoformat(node.get("createdAt"))
                )
                messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"OwnerClan 긴급 메시지 조회 실패: {e}")
            raise

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
