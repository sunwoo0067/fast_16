import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from app.models.database import Product, SupplierAccount, ProductSyncHistory
from app.core.logging import get_logger, LoggerMixin, log_product_sync
from app.core.exceptions import ExternalAPIError, ProductSyncError
from app.utils.async_task import AsyncTask

logger = get_logger(__name__)

class OwnerClanSyncService(LoggerMixin):
    """OwnerClan API 동기화 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.api_base_url = "https://api.ownerclan.com/v1/graphql"
        self.auth_url = "https://auth.ownerclan.com/auth"

    async def authenticate_supplier(self, account_id: str, password: str) -> Dict[str, Any]:
        """공급사 인증"""
        import httpx

        auth_data = {
            "service": "ownerclan",
            "userType": "seller",
            "username": account_id,
            "password": password
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.auth_url,
                    json=auth_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                response.raise_for_status()

                # JWT 토큰 반환
                token = response.text.strip()
                if token.startswith('eyJ'):
                    return {"access_token": token, "token_type": "bearer"}
                else:
                    return response.json()

            except httpx.RequestError as e:
                raise ExternalAPIError(f"OwnerClan 인증 요청 실패: {e}", api_name="ownerclan_auth")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIError(
                    f"OwnerClan 인증 실패: {e.response.status_code}",
                    api_name="ownerclan_auth",
                    status_code=e.response.status_code
                )

    async def get_products_from_ownerclan(
        self,
        account_id: str,
        password: str,
        item_keys: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """OwnerClan에서 상품 데이터 가져오기"""
        # 인증
        auth_result = await self.authenticate_supplier(account_id, password)
        token = auth_result.get("access_token")

        if not token:
            raise ExternalAPIError("인증 토큰을 받을 수 없습니다", api_name="ownerclan_auth")

        # GraphQL 쿼리
        query = """
        query GetProducts($itemKeys: [String!]) {
            products(itemKeys: $itemKeys) {
                itemKey
                name
                model
                brand
                category
                price
                options
                description
                images
                isActive
                lastUpdated
            }
        }
        """

        variables = {}
        if item_keys:
            variables["itemKeys"] = item_keys

        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_base_url,
                    json={"query": query, "variables": variables},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}"
                    },
                    timeout=60
                )
                response.raise_for_status()

                data = response.json()
                if "errors" in data:
                    raise ExternalAPIError(
                        f"OwnerClan API 오류: {data['errors']}",
                        api_name="ownerclan_api"
                    )

                products = data.get("data", {}).get("products", [])
                return products

            except httpx.RequestError as e:
                raise ExternalAPIError(f"OwnerClan API 요청 실패: {e}", api_name="ownerclan_api")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIError(
                    f"OwnerClan API 오류: {e.response.status_code}",
                    api_name="ownerclan_api",
                    status_code=e.response.status_code
                )

class ProductSyncService(LoggerMixin):
    """상품 동기화 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_service = OwnerClanSyncService(db)
        self.batch_size = 50

    async def sync_supplier_products(
        self,
        supplier_id: int,
        supplier_account_id: Optional[int] = None,
        item_keys: Optional[List[str]] = None,
        force_sync: bool = False
    ) -> Dict[str, Any]:
        """공급사의 상품 동기화"""
        start_time = datetime.now()
        result = {
            "total_products": 0,
            "new_products": 0,
            "updated_products": 0,
            "errors": [],
            "duration_ms": 0
        }

        try:
            # 공급사 계정 조회
            account_query = select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )

            if supplier_account_id:
                account_query = account_query.where(SupplierAccount.id == supplier_account_id)

            account_result = await self.db.execute(account_query)
            accounts = account_result.scalars().all()

            if not accounts:
                raise ProductSyncError(f"활성 공급사 계정을 찾을 수 없습니다: supplier_id={supplier_id}")

            # 각 계정에 대해 동기화
            for account in accounts:
                try:
                    account_result = await self._sync_account_products(
                        account, item_keys, force_sync
                    )

                    result["total_products"] += account_result["total_products"]
                    result["new_products"] += account_result["new_products"]
                    result["updated_products"] += account_result["updated_products"]
                    result["errors"].extend(account_result["errors"])

                except Exception as e:
                    result["errors"].append({
                        "account_id": account.account_id,
                        "error": str(e)
                    })

        except Exception as e:
            result["errors"].append(str(e))

        result["duration_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)
        return result

    async def _sync_account_products(
        self,
        account: SupplierAccount,
        item_keys: Optional[List[str]] = None,
        force_sync: bool = False
    ) -> Dict[str, Any]:
        """특정 계정의 상품 동기화"""
        result = {
            "total_products": 0,
            "new_products": 0,
            "updated_products": 0,
            "errors": []
        }

        try:
            # OwnerClan에서 상품 데이터 가져오기
            products_data = await self.ownerclan_service.get_products_from_ownerclan(
                account.account_id,
                account.account_password,
                item_keys
            )

            result["total_products"] = len(products_data)

            # 배치로 처리
            batches = [products_data[i:i + self.batch_size]
                      for i in range(0, len(products_data), self.batch_size)]

            for batch in batches:
                batch_result = await self._process_product_batch(batch, account, force_sync)
                result["new_products"] += batch_result["new_products"]
                result["updated_products"] += batch_result["updated_products"]
                result["errors"].extend(batch_result["errors"])

        except Exception as e:
            result["errors"].append(str(e))

        return result

    async def _process_product_batch(
        self,
        batch: List[Dict[str, Any]],
        account: SupplierAccount,
        force_sync: bool = False
    ) -> Dict[str, Any]:
        """상품 배치 처리"""
        result = {
            "new_products": 0,
            "updated_products": 0,
            "errors": []
        }

        for product_data in batch:
            try:
                # 상품 처리
                processed = await self._process_single_product(product_data, account, force_sync)

                if processed["action"] == "created":
                    result["new_products"] += 1
                elif processed["action"] == "updated":
                    result["updated_products"] += 1

            except Exception as e:
                result["errors"].append({
                    "item_key": product_data.get("itemKey"),
                    "error": str(e)
                })

        return result

    async def _process_single_product(
        self,
        product_data: Dict[str, Any],
        account: SupplierAccount,
        force_sync: bool = False
    ) -> Dict[str, Any]:
        """단일 상품 처리"""
        item_key = product_data.get("itemKey")

        # 기존 상품 조회
        existing_query = select(Product).where(
            and_(
                Product.item_key == item_key,
                Product.supplier_id == account.supplier_id
            )
        )
        existing_result = await self.db.execute(existing_query)
        existing_product = existing_result.scalar_one_or_none()

        # 상품 데이터 변환
        transformed_data = self._transform_product_data(product_data, account)

        if existing_product:
            # 기존 상품 업데이트
            if force_sync or self._needs_update(existing_product, product_data):
                await self._update_existing_product(existing_product, transformed_data, account)
                return {"action": "updated", "item_key": item_key}
            else:
                return {"action": "skipped", "item_key": item_key}
        else:
            # 새 상품 생성
            await self._create_new_product(transformed_data, account)
            return {"action": "created", "item_key": item_key}

    def _transform_product_data(self, product_data: Dict[str, Any], account: SupplierAccount) -> Dict[str, Any]:
        """OwnerClan 상품 데이터를 내부 모델로 변환"""
        return {
            "supplier_id": account.supplier_id,
            "supplier_account_id": account.id,
            "item_key": product_data.get("itemKey"),
            "name": product_data.get("name"),
            "price": product_data.get("price", 0),
            "sale_price": product_data.get("price", 0),  # 기본적으로 공급가와 동일
            "margin_rate": account.default_margin_rate or 0.3,
            "stock_quantity": 0,  # OwnerClan에서 재고 정보가 없을 수 있음
            "max_stock_quantity": None,
            "supplier_product_id": product_data.get("itemKey"),
            "supplier_name": account.account_id,
            "estimated_shipping_days": 7,  # 기본값
            "category_id": product_data.get("category"),
            "category_name": product_data.get("category"),
            "description": product_data.get("description"),
            "images": product_data.get("images", []),
            "options": product_data.get("options", {}),
            "is_active": product_data.get("isActive", True),
            "sync_status": "synced"
        }

    def _needs_update(self, existing_product: Product, new_product_data: Dict[str, Any]) -> bool:
        """업데이트 필요 여부 확인"""
        # 마지막 업데이트 시간 비교
        if existing_product.last_updated and new_product_data.get("lastUpdated"):
            new_updated = datetime.fromisoformat(new_product_data["lastUpdated"].replace('Z', '+00:00'))
            if new_updated <= existing_product.last_updated:
                return False

        # 중요 필드 변경 확인
        important_fields = ["name", "price", "description", "isActive"]
        for field in important_fields:
            if field in new_product_data:
                new_value = new_product_data[field]
                existing_value = getattr(existing_product, field.lower(), None)
                if new_value != existing_value:
                    return True

        return False

    async def _create_new_product(self, product_data: Dict[str, Any], account: SupplierAccount):
        """새 상품 생성"""
        new_product = Product(**product_data)
        new_product.last_updated = datetime.now()

        self.db.add(new_product)
        await self.db.flush()  # ID 생성

        # 동기화 이력 기록
        await self._record_sync_history(
            supplier_id=account.supplier_id,
            product_id=new_product.id,
            sync_type="create",
            status="success"
        )

        await self.db.commit()

        log_product_sync(
            product_data={
                "item_key": product_data["item_key"],
                "name": product_data["name"],
                "supplier_id": account.supplier_id
            },
            action="create",
            success=True
        )

    async def _update_existing_product(
        self,
        existing_product: Product,
        new_data: Dict[str, Any],
        account: SupplierAccount
    ):
        """기존 상품 업데이트"""
        # 이전 데이터 백업
        old_data = {
            "name": existing_product.name,
            "price": existing_product.price,
            "is_active": existing_product.is_active
        }

        # 업데이트
        for field, value in new_data.items():
            if hasattr(existing_product, field):
                setattr(existing_product, field, value)

        existing_product.last_updated = datetime.now()
        existing_product.sync_status = "synced"

        # 동기화 이력 기록
        await self._record_sync_history(
            supplier_id=account.supplier_id,
            product_id=existing_product.id,
            sync_type="update",
            status="success",
            old_data=old_data,
            new_data=new_data
        )

        await self.db.commit()

        log_product_sync(
            product_data={
                "item_key": existing_product.item_key,
                "name": existing_product.name,
                "supplier_id": account.supplier_id
            },
            action="update",
            success=True
        )

    async def _record_sync_history(
        self,
        supplier_id: int,
        product_id: int,
        sync_type: str,
        status: str,
        old_data: Optional[Dict] = None,
        new_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
        sync_duration_ms: Optional[int] = None
    ):
        """동기화 이력 기록"""
        history_record = ProductSyncHistory(
            supplier_id=supplier_id,
            product_id=product_id,
            sync_type=sync_type,
            status=status,
            old_data=json.dumps(old_data) if old_data else None,
            new_data=json.dumps(new_data) if new_data else None,
            error_message=error_message,
            sync_duration_ms=sync_duration_ms
        )

        self.db.add(history_record)
        await self.db.commit()

class CoupangSyncService(LoggerMixin):
    """쿠팡 동기화 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_coupang_products(
        self,
        supplier_id: int,
        supplier_account_id: int
    ) -> Dict[str, Any]:
        """쿠팡 상품 동기화"""
        # 쿠팡 API 연동 구현 (실제로는 CoupangWingAPI 사용)
        # 여기서는 더미 구현

        result = {
            "total_products": 0,
            "synced_products": 0,
            "errors": []
        }

        # 실제 구현에서는:
        # 1. 쿠팡 API 인증
        # 2. 상품 목록 조회
        # 3. 각 상품을 내부 모델로 변환
        # 4. 동기화 처리

        return result
