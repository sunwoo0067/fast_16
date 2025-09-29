import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.database import Supplier, SupplierAccount, Product
from app.core.logging import get_logger
from ownerclan_api import OwnerClanAPI, TokenManager
from ownerclan_credentials import OwnerClanCredentials

logger = get_logger(__name__)

class OwnerClanCollector:
    """OwnerClan 실제 상품 데이터 수집기"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.api = OwnerClanAPI()
        self.token_manager = TokenManager(db, self.api)

    async def collect_products(self, supplier_account_id: int, limit: int = 100) -> Dict[str, Any]:
        """OwnerClan에서 상품 데이터 수집"""
        try:
            # 공급사 계정 정보 조회
            account = await self._get_supplier_account(supplier_account_id)
            if not account:
                return {"success": False, "error": "공급사 계정을 찾을 수 없습니다"}

            # OwnerClan API에서 상품 데이터 수집
            products_data = await self._fetch_products_from_ownerclan(account, limit)

            if not products_data:
                logger.warning("OwnerClan API에서 상품 데이터를 가져오지 못했습니다")
                return {
                    "success": False,
                    "error": "OwnerClan API에서 상품 데이터를 가져올 수 없습니다",
                    "collected": 0,
                    "saved": 0,
                    "supplier_account_id": supplier_account_id
                }

            # 수집된 데이터를 데이터베이스에 저장
            saved_count = await self._save_products_to_db(products_data, supplier_account_id)

            return {
                "success": True,
                "collected": len(products_data),
                "saved": saved_count,
                "supplier_account_id": supplier_account_id
            }

        except Exception as e:
            logger.error(f"상품 수집 실패: {e}")
            return {
                "success": False,
                "error": f"상품 수집 중 오류 발생: {str(e)}",
                "collected": 0,
                "saved": 0,
                "supplier_account_id": supplier_account_id
            }

    async def _get_supplier_account(self, account_id: int) -> Optional[SupplierAccount]:
        """공급사 계정 정보 조회"""
        result = await self.db.execute(
            select(SupplierAccount).where(SupplierAccount.id == account_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_products_from_ownerclan(self, account: SupplierAccount, limit: int) -> List[Dict[str, Any]]:
        """OwnerClan API에서 상품 데이터 가져오기"""
        try:
            # TokenManager를 사용하여 유효한 토큰 가져오기
            logger.info(f"토큰 조회 시작: supplier_id={account.supplier_id}")
            token = await self.token_manager.get_valid_token(account.supplier_id)
            if not token:
                logger.error(f"유효한 토큰을 가져올 수 없습니다: supplier_id={account.supplier_id}")
                return []
            else:
                logger.info(f"토큰 획득 성공: {token[:50]}...")

            # REST API 시도
            try:
                products_data = await self._fetch_products_rest_api(token, limit)
                if products_data:
                    return products_data
            except Exception as e:
                logger.warning(f"REST API 실패, GraphQL 시도: {e}")

            # GraphQL API 시도
            try:
                logger.info(f"GraphQL API 호출 시작: limit={limit}")
                products_data = await self._fetch_products_graphql_api(token, limit)
                logger.info(f"GraphQL API 응답: {len(products_data) if products_data else 0}개 상품")
                if products_data:
                    return products_data
            except Exception as e:
                logger.warning(f"GraphQL API 실패: {e}")

            # 모든 API 시도가 실패한 경우 빈 리스트 반환
            logger.warning("모든 OwnerClan API 호출 실패")
            return []

        except Exception as e:
            logger.error(f"OwnerClan 상품 데이터 수집 실패: {e}")
            return []

    async def _fetch_products_rest_api(self, token: str, limit: int) -> List[Dict[str, Any]]:
        """REST API로 상품 데이터 가져오기"""
        import httpx

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            endpoints = [
                'https://api.ownerclan.com/v1/products',
                'https://api.ownerclan.com/v1/items',
                'https://api.ownerclan.com/v1/seller/products'
            ]

            for endpoint in endpoints:
                try:
                    response = await client.get(
                        endpoint,
                        headers=headers,
                        params={'limit': limit, 'offset': 0}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # 다양한 응답 형식 처리
                        if isinstance(data, list):
                            products = data
                        elif isinstance(data, dict) and 'items' in data:
                            products = data['items']
                        elif isinstance(data, dict) and 'products' in data:
                            products = data['products']
                        else:
                            continue

                        return [
                            {
                                "item_key": f"OC_{product.get('id', i)}",
                                "name": product.get("name", f"상품 {i+1}"),
                                "price": product.get("price", 10000),
                                "sale_price": product.get("salePrice", product.get("price", 10000)),
                                "stock_quantity": product.get("stockQuantity", product.get("stock", 100)),
                                "category_id": product.get("category", {}).get("id") if isinstance(product.get("category"), dict) else product.get("categoryId"),
                                "category_name": product.get("category", {}).get("name") if isinstance(product.get("category"), dict) else product.get("categoryName", "기타"),
                                "description": product.get("description", f"상품 {i+1} 설명"),
                                "images": product.get("images", []),
                                "options": product.get("options", {}),
                                "is_active": product.get("isActive", product.get("active", True)),
                                "supplier_product_id": str(product.get("id", i)),
                                "supplier_name": "OwnerClan",
                                "supplier_url": f"https://ownerclan.com/product/{product.get('id', i)}",
                                "supplier_image_url": product.get("images", [{}])[0].get("url") if product.get("images") else None,
                                "estimated_shipping_days": 3,
                                "manufacturer": "OwnerClan",
                                "margin_rate": 0.3,
                                "sync_status": "synced"
                            }
                            for i, product in enumerate(products[:limit])
                        ]
                except Exception as e:
                    logger.warning(f"REST API {endpoint} 실패: {e}")
                    continue

        return []

    async def _fetch_products_graphql_api(self, token: str, limit: int) -> List[Dict[str, Any]]:
        """GraphQL API로 상품 데이터 가져오기"""
        query = """
        query GetProducts($first: Int!) {
            allItems(first: $first) {
                edges {
                    node {
                        id
                        key
                        name
                        model
                        price
                        fixedPrice
                        wholessalePrice
                        boxQuantity
                        category {
                            id
                            name
                        }
                        images
                        options {
                            key
                        }
                    }
                }
            }
        }
        """

        variables = {"first": limit}

        response = await self.api.execute_query(query, variables, token)
        
        # 응답 타입 확인
        logger.info(f"GraphQL 응답 타입: {type(response)}")
        logger.info(f"GraphQL 응답 내용: {response}")

        # GraphQL 응답 구조 확인 (success 필드가 없을 수 있음)
        if isinstance(response, dict) and response.get("data") and not response.get("errors"):
            # allItems는 edges 구조를 사용
            all_items = response["data"].get("allItems", {})
            edges = all_items.get("edges", [])
            products = [edge["node"] for edge in edges]
            
            logger.info(f"GraphQL API에서 {len(products)}개 상품 조회 성공")
            
            return [
                {
                    "id": f"OC_{product['key'] or product['id']}",  # 필수 필드
                    "item_key": f"OC_{product['key'] or product['id']}",
                    "title": product["name"],  # name -> title로 변경
                    "brand": "OwnerClan",  # 기본 브랜드
                    "stock_quantity": product.get("boxQuantity", 0),
                    "category_id": product.get("category", {}).get("id"),
                    "description": "",  # description 필드가 없으므로 빈 문자열
                    "images": json.dumps(product.get("images", [])),  # JSON 문자열로 저장
                    "options": json.dumps(product.get("options", [])),  # JSON 문자열로 저장 (배열)
                    "price_data": json.dumps({  # 가격 정보를 JSON으로 저장
                        "original": product.get("price", 0),
                        "sale": product.get("fixedPrice", product.get("price", 0)),
                        "wholesale": product.get("wholessalePrice", product.get("price", 0)),
                        "margin_rate": 0.3
                    }),
                    "is_active": True,
                    "supplier_product_id": str(product.get("key") or product["id"]),
                    "supplier_name": "OwnerClan",
                    "supplier_url": f"https://ownerclan.com/product/{product.get('key') or product['id']}",
                    "supplier_image_url": product.get("images", [None])[0] if product.get("images") else None,
                    "estimated_shipping_days": 3,
                    "sync_status": "synced"
                }
                for product in products
            ]

        return []



    async def _save_products_to_db(self, products_data: List[Dict[str, Any]], supplier_account_id: int) -> int:
        """수집된 상품 데이터를 데이터베이스에 저장"""
        saved_count = 0

        for product_data in products_data:
            try:
                # 기존 상품 확인 (supplier_account_id를 supplier_id로 사용)
                existing_product = await self.db.execute(
                    select(Product).where(
                        and_(
                            Product.supplier_id == str(supplier_account_id),  # String으로 변환
                            Product.supplier_product_id == product_data["supplier_product_id"]
                        )
                    )
                )
                existing = existing_product.scalar_one_or_none()

                if existing:
                    # 기존 상품 업데이트
                    for key, value in product_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now()
                    existing.sync_status = "synced"
                else:
                    # 새 상품 생성
                    product_data_copy = product_data.copy()
                    product_data_copy["supplier_id"] = str(supplier_account_id)  # String으로 변환
                    new_product = Product(**product_data_copy)
                    self.db.add(new_product)

                saved_count += 1

            except Exception as e:
                logger.error(f"상품 저장 실패: {product_data.get('name', 'Unknown')} - {e}")

        await self.db.commit()
        return saved_count

    async def get_collection_stats(self, supplier_account_id: int) -> Dict[str, Any]:
        """수집 통계 조회"""
        try:
            # OwnerClan 계정의 상품 수 확인
            result = await self.db.execute(
                select(Product).where(Product.supplier_id == supplier_account_id)  # supplier_account_id 대신 supplier_id 사용
            )
            products = result.scalars().all()

            stats = {
                "total_products": len(products),
                "active_products": len([p for p in products if p.is_active]),
                "synced_products": len([p for p in products if p.sync_status == "synced"]),
                "last_sync": None
            }

            if products:
                stats["last_sync"] = max(p.updated_at for p in products if p.updated_at).isoformat()

            return {"success": True, "stats": stats}

        except Exception as e:
            return {"success": False, "error": str(e)}
