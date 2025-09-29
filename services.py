from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_, or_
from database import Supplier, SupplierAccount, Product, Order, OrderProduct, QnaArticle, EmergencyMessage, NoticeMemo, Category, ShippingLocation, ReturnLocation
from ownerclan_api import TokenManager, OwnerClanAPI, CoupangWingAPI, CoupangProductAPI
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class SupplierService:
    """공급사 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_suppliers(self) -> List[Supplier]:
        """모든 공급사 조회"""
        result = await self.db.execute(
            select(Supplier).where(Supplier.is_active == True)
        )
        return result.scalars().all()

    async def get_supplier_by_id(self, supplier_id: int) -> Optional[Supplier]:
        """ID로 공급사 조회"""
        result = await self.db.execute(
            select(Supplier).where(
                and_(
                    Supplier.id == supplier_id,
                    Supplier.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_supplier(self, name: str, description: str = None) -> Supplier:
        """공급사 생성"""
        new_supplier = Supplier(
            name=name,
            description=description,
            is_active=True
        )
        self.db.add(new_supplier)
        await self.db.commit()
        await self.db.refresh(new_supplier)
        return new_supplier

class SupplierAccountService:
    """공급사계정 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_api = OwnerClanAPI()
        self.token_manager = TokenManager(db, self.ownerclan_api)

    async def get_accounts_by_supplier(self, supplier_id: int) -> List[SupplierAccount]:
        """공급사의 모든 계정 조회"""
        result = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        return result.scalars().all()

    async def create_account(
        self,
        supplier_id: int,
        account_id: str,
        password: str
    ) -> SupplierAccount:
        """공급사계정 생성"""
        try:
            # OwnerClanAPI 인증 시도
            try:
                auth_response = await self.ownerclan_api.authenticate(account_id, password)
                access_token = auth_response.get("access_token")
                refresh_token = auth_response.get("refresh_token")
            except Exception as e:
                # OwnerClan 인증 실패시 더미 토큰 생성 (쿠팡 전용 계정용)
                logger.warning(f"OwnerClan 인증 실패, 더미 토큰 생성: {e}")
                access_token = f"dummy_token_{account_id}_{datetime.now().isoformat()}"
                refresh_token = None

            new_account = SupplierAccount(
                supplier_id=supplier_id,
                account_name=f"OwnerClan Account {supplier_id}",
                username=account_id,
                password_encrypted=password,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=datetime.now() + timedelta(days=30) if access_token else None,
                is_active=True
            )

            self.db.add(new_account)
            await self.db.commit()
            await self.db.refresh(new_account)

            return new_account

        except Exception as e:
            await self.db.rollback()
            raise Exception(f"계정 생성 실패: {e}")

    async def get_valid_token(self, supplier_id: int) -> Optional[str]:
        """유효한 토큰 조회"""
        return await self.token_manager.get_valid_token(supplier_id)

    async def test_ownerclan_connection(self, supplier_id: int) -> dict:
        """오너클랜 API 연결 테스트"""
        try:
            # 먼저 계정 정보를 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            token = await self.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            async with self.ownerclan_api:
                # 테스트 쿼리 실행
                test_query = """
                query {
                    item(key: "W000000") {
                        name
                        model
                    }
                }"""

                result = await self.ownerclan_api.execute_query(
                    test_query,
                    token=token,
                    account_id=account.id
                )

                if "errors" in result:
                    # 통계 업데이트 (실패)
                    await self.token_manager.update_request_stats(account.id, success=False)
                    return {"status": "error", "message": "API 호출 실패", "details": result["errors"]}

                # 통계 업데이트 (성공)
                await self.token_manager.update_request_stats(account.id, success=True)

                return {
                    "status": "success",
                    "message": "오너클랜 API 연결 성공",
                    "data": result.get("data")
                }

        except Exception as e:
            return {"status": "error", "message": f"연결 테스트 실패: {str(e)}"}

class ProductService:
    """상품 수집 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_api = OwnerClanAPI()
        self.token_manager = TokenManager(db, self.ownerclan_api)

    async def collect_products(self, supplier_id: int, item_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """상품 수집"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            collected_count = 0
            updated_count = 0
            failed_count = 0

            if item_keys:
                # 특정 상품들만 수집 (여러 키를 한번에 조회)
                if len(item_keys) > 1:
                    # 여러 키를 한번에 조회
                    collected_count, updated_count, failed_count = await self._collect_multiple_products(
                        item_keys, supplier_id, token, account.id
                    )
                else:
                    # 단일 상품 수집
                    try:
                        success, is_update = await self._collect_single_product(
                            item_keys[0], supplier_id, token, account.id
                        )
                        if success:
                            if is_update:
                                updated_count += 1
                            else:
                                collected_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"상품 수집 실패 {item_keys[0]}: {e}")
                        failed_count += 1
            else:
                # 전체 상품 목록 수집 (페이징 처리)
                try:
                    collected_count, updated_count, failed_count = await self._collect_products_batch(
                        supplier_id, token, account.id,
                        collected_count, updated_count, failed_count
                    )
                except Exception as e:
                    logger.error(f"상품 목록 수집 실패: {e}")

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "상품 수집 완료",
                "collected": collected_count,
                "updated": updated_count,
                "failed": failed_count,
                "total": collected_count + updated_count
            }

        except Exception as e:
            return {"status": "error", "message": f"상품 수집 실패: {str(e)}"}

    async def _collect_products_batch(
        self,
        supplier_id: int,
        token: str,
        account_id: int,
        collected_count: int,
        updated_count: int,
        failed_count: int
    ) -> tuple[int, int, int]:  # (collected, updated, failed)
        """상품 배치 수집"""
        try:
            # 상품 목록 조회 쿼리 (페이징 지원)
            items_query = """
            query {
                allItems(first: 50) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            key
                            name
                            model
                        }
                    }
                }
            }"""

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    items_query,
                    token=token,
                    account_id=account_id
                )

            if "errors" in result:
                logger.error(f"상품 목록 조회 실패: {result['errors']}")
                return collected_count, updated_count, failed_count + 1

            all_items_data = result.get("data", {}).get("allItems", {})
            if not all_items_data:
                logger.warning("상품 목록 데이터를 찾을 수 없습니다")
                return collected_count, updated_count, failed_count + 1

            edges = all_items_data.get("edges", [])
            if not edges:
                logger.info("조회할 상품이 없습니다")
                return collected_count, updated_count, failed_count

            # 각 상품에 대해 상세 정보 수집 (순차 처리)
            for i, edge in enumerate(edges[:10]):  # 테스트로 10개만 수집
                node = edge.get("node", {})
                item_key = node.get("key")

                if item_key:
                    try:
                        success, is_update = await self._collect_single_product(
                            item_key, supplier_id, token, account_id
                        )
                        if success:
                            if is_update:
                                updated_count += 1
                            else:
                                collected_count += 1
                        else:
                            failed_count += 1

                        # 요청 간격 조절 (너무 빠른 요청 방지)
                        if i < 9:  # 마지막 요청은 대기하지 않음
                            await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(f"상품 수집 실패 {item_key}: {e}")
                        failed_count += 1

            return collected_count, updated_count, failed_count

        except Exception as e:
            logger.error(f"배치 상품 수집 실패: {e}")
            return collected_count, updated_count, failed_count + 1

    async def _collect_multiple_products(
        self,
        item_keys: List[str],
        supplier_id: int,
        token: str,
        account_id: int
    ) -> tuple[int, int, int]:  # (collected, updated, failed)
        """여러 상품을 한번에 수집"""
        try:
            # 여러 키를 한번에 조회하는 쿼리 (문서에 따른 형식)
            keys_str = '", "'.join(item_keys)
            multiple_query = """
            query {
                items(keys: ["%s"]) {
                    key
                    name
                    model
                    production
                    origin
                    price
                    category {
                        id
                        name
                    }
                    options {
                        price
                        quantity
                        optionAttributes {
                            name
                            value
                        }
                    }
                    images
                }
            }""" % keys_str

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    multiple_query,
                    token=token,
                    account_id=account_id
                )

            if "errors" in result:
                logger.error(f"여러 상품 조회 실패: {result['errors']}")
                return 0, 0, len(item_keys)

            items_data = result.get("data", {}).get("items", [])
            if not items_data:
                logger.warning("상품 데이터를 찾을 수 없습니다")
                return 0, 0, len(item_keys)

            collected_count = 0
            updated_count = 0
            failed_count = 0

            # 각 상품 저장
            for item_data in items_data:
                try:
                    item_key = item_data.get("key")
                    if not item_key:
                        continue

                    # 기존 상품 확인
                    existing_result = await self.db.execute(
                        select(Product).where(
                            and_(
                                Product.supplier_id == supplier_id,
                                Product.item_key == item_key
                            )
                        )
                    )
                    existing_product = existing_result.scalar_one_or_none()

                    # 옵션 정보 JSON 변환
                    options_json = json.dumps(item_data.get("options", []))
                    images_json = json.dumps(item_data.get("images", []))
                    category_json = json.dumps(item_data.get("category", {}))

                    product_data = {
                        "supplier_id": supplier_id,
                        "item_key": item_data.get("key", item_key),
                        "name": item_data.get("name", ""),
                        "model": item_data.get("model", ""),
                        "brand": item_data.get("production", ""),
                        "category": item_data.get("origin", ""),
                        "price": float(item_data.get("price", 0)) if item_data.get("price") else None,
                        "options": options_json,
                        "images": images_json,
                        "last_updated": datetime.now()
                    }

                    if existing_product:
                        # 업데이트
                        await self.db.execute(
                            update(Product).where(
                                and_(
                                    Product.supplier_id == supplier_id,
                                    Product.item_key == item_key
                                )
                            ).values(**product_data)
                        )
                        updated_count += 1
                    else:
                        # 새 상품 생성
                        new_product = Product(**product_data)
                        self.db.add(new_product)
                        collected_count += 1

                    await self.db.commit()

                except Exception as e:
                    logger.error(f"상품 저장 실패 {item_key}: {e}")
                    failed_count += 1

            return collected_count, updated_count, failed_count

        except Exception as e:
            logger.error(f"여러 상품 수집 실패: {e}")
            return 0, 0, len(item_keys)

        except Exception as e:
            return {"status": "error", "message": f"상품 수집 실패: {str(e)}"}

    async def _collect_single_product(
        self,
        item_key: str,
        supplier_id: int,
        token: Optional[str] = None,
        account_id: Optional[int] = None
    ) -> tuple[bool, bool]:  # (success, is_update)
        """단일 상품 정보 수집"""
        try:
            # 토큰과 계정 정보가 없으면 조회
            if not token or not account_id:
                token = await self.token_manager.get_valid_token(supplier_id)
                if not token:
                    logger.error(f"토큰 조회 실패: supplier_id={supplier_id}")
                    return False, False

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
                    logger.error(f"계정 조회 실패: supplier_id={supplier_id}")
                    return False, False
                account_id = account.id

            # 상품 상세 정보 쿼리 (문서에 따른 올바른 필드들)
            product_query = """
            query {
                item(key: "%s") {
                    key
                    name
                    model
                    production
                    origin
                    price
                    pricePolicy
                    fixedPrice
                    category {
                        id
                        name
                    }
                    shippingFee
                    shippingType
                    status
                    options {
                        price
                        quantity
                        optionAttributes {
                            name
                            value
                        }
                    }
                    taxFree
                    adultOnly
                    returnable
                    images
                    createdAt
                    updatedAt
                }
            }""" % item_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    product_query,
                    token=token,
                    account_id=account_id
                )

            if "errors" in result:
                logger.error(f"상품 정보 조회 실패 {item_key}: {result['errors']}")
                return False, False

            item_data = result.get("data", {}).get("item")
            if not item_data:
                logger.warning(f"상품 데이터를 찾을 수 없습니다: {item_key}")
                return False, False

            # 기존 상품 확인
            existing_result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.item_key == item_key
                    )
                )
            )
            existing_product = existing_result.scalar_one_or_none()

            # 옵션 정보 JSON 변환
            options_json = json.dumps(item_data.get("options", []))

            # 이미지 정보 JSON 변환
            images_json = json.dumps(item_data.get("images", []))

            # 카테고리 정보 JSON 변환
            category_json = json.dumps(item_data.get("category", {}))

            product_data = {
                "supplier_id": supplier_id,
                "item_key": item_data.get("key", item_key),
                "name": item_data.get("name", ""),
                "model": item_data.get("model", ""),
                "brand": item_data.get("production", ""),  # 제조사
                "category": item_data.get("origin", ""),   # 제조국가 (문서의 origin 필드)
                "price": float(item_data.get("price", 0)) if item_data.get("price") else None,
                "options": options_json,
                "images": images_json,
                "last_updated": datetime.now()
            }

            if existing_product:
                # 업데이트
                await self.db.execute(
                    update(Product).where(
                        and_(
                            Product.supplier_id == supplier_id,
                            Product.item_key == item_key
                        )
                    ).values(**product_data)
                )
                await self.db.commit()
                return True, True
            else:
                # 새 상품 생성
                new_product = Product(**product_data)
                self.db.add(new_product)
                await self.db.commit()
                await self.db.refresh(new_product)
                return True, False

        except Exception as e:
            logger.error(f"상품 수집 중 오류 {item_key}: {e}")
            return False, False

    def _get_base_price(self, options: List[Dict]) -> Optional[int]:
        """옵션에서 기본 가격 추출"""
        if not options:
            return None

        # 첫 번째 옵션의 가격을 기본 가격으로 사용
        first_option = options[0]
        return first_option.get("price")

    async def get_products(self, supplier_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """공급사의 상품 목록 조회"""
        result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.is_active == True
                )
            ).order_by(Product.last_updated.desc()).limit(limit).offset(offset)
        )
        products = result.scalars().all()

        return [
            {
                "id": p.id,
                "item_key": p.item_key,
                "name": p.name,
                "model": p.model,
                "price": p.price,
                "options": json.loads(p.options) if p.options else [],
                "last_updated": p.last_updated.isoformat() if p.last_updated else None,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in products
        ]

    async def get_product_stats(self, supplier_id: int) -> Dict[str, Any]:
        """상품 통계 조회"""
        total_result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.is_active == True
                )
            )
        )
        total_count = len(total_result.scalars().all())

        # 최근 업데이트된 상품 수
        # 최근 업데이트된 상품 수 (1일 이내)
        recent_result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.supplier_id == supplier_id,
                    Product.is_active == True,
                    Product.last_updated >= datetime.now() - timedelta(days=1)
                )
            )
        )
        recent_count = len(recent_result.scalars().all())

        return {
            "total_products": total_count,
            "recently_updated": recent_count,
            "supplier_id": supplier_id
        }

    async def get_product_history(self, supplier_id: int, item_key: Optional[str] = None, days: int = 3) -> Dict[str, Any]:
        """상품 변경 이력 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 최근 3일간의 타임스탬프 계산
            since_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())

            # 상품 변경 이력 쿼리 (최근 3일간)
            if item_key:
                history_query = """
                query {
                    itemHistories(first: 100, itemKey: "%s", dateFrom: %d) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                itemKey
                                kind
                                createdAt
                            }
                        }
                    }
                }""" % (item_key, since_timestamp)
            else:
                history_query = """
                query {
                    itemHistories(first: 100, dateFrom: %d) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        edges {
                            node {
                                itemKey
                                kind
                                createdAt
                            }
                        }
                    }
                }""" % since_timestamp

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    history_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"이력 조회 실패: {result['errors']}"}

            histories_data = result.get("data", {}).get("itemHistories", {})
            if not histories_data:
                return {"status": "success", "message": "이력 데이터가 없습니다", "histories": []}

            edges = histories_data.get("edges", [])
            histories = [
                {
                    "item_key": edge.get("node", {}).get("itemKey"),
                    "kind": edge.get("node", {}).get("kind"),
                    "created_at": edge.get("node", {}).get("createdAt")
                }
                for edge in edges
            ]

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": f"최근 {days}일간 이력 조회 완료",
                "histories": histories,
                "total": len(histories),
                "days": days
            }

        except Exception as e:
            return {"status": "error", "message": f"이력 조회 실패: {str(e)}"}

    async def collect_recent_products(self, supplier_id: int, days: int = 3) -> Dict[str, Any]:
        """최근 N일간 변경된 상품들을 수집"""
        try:
            # 먼저 최근 변경 이력 조회
            history_result = await self.get_product_history(supplier_id, days=days)
            if history_result["status"] != "success":
                return history_result

            histories = history_result["histories"]
            if not histories:
                return {"status": "success", "message": "최근 변경된 상품이 없습니다", "collected": 0}

            # 변경된 상품 키들 추출 (중복 제거)
            changed_item_keys = list(set([h["item_key"] for h in histories if h["item_key"]]))

            logger.info(f"최근 {days}일간 변경된 상품 키들: {changed_item_keys}")

            # 변경된 상품들 수집
            collected_count = 0
            updated_count = 0
            failed_count = 0

            for item_key in changed_item_keys[:20]:  # 최대 20개만 수집
                try:
                    success, is_update = await self._collect_single_product(
                        item_key, supplier_id, None, None  # 토큰과 계정 ID는 메서드 내에서 조회
                    )
                    if success:
                        if is_update:
                            updated_count += 1
                        else:
                            collected_count += 1
                    else:
                        failed_count += 1

                    # 요청 간격 조절
                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.error(f"상품 수집 실패 {item_key}: {e}")
                    failed_count += 1

            return {
                "status": "success",
                "message": f"최근 {days}일간 변경된 상품 수집 완료",
                "collected": collected_count,
                "updated": updated_count,
                "failed": failed_count,
                "total_changed": len(changed_item_keys),
                "total_processed": collected_count + updated_count
            }

        except Exception as e:
            return {"status": "error", "message": f"최근 상품 수집 실패: {str(e)}"}

class CustomerService:
    """고객 서비스 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_api = OwnerClanAPI()
        self.token_manager = TokenManager(db, self.ownerclan_api)

    async def get_qna_article(self, supplier_id: int, qna_key: str) -> Dict[str, Any]:
        """단일 1:1 문의 게시판 글 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 1:1 문의글 조회 쿼리
            qna_query = """
            query {
                sellerQnaArticle(key: "%s") {
                    key
                    id
                    type
                    isSecret
                    title
                    content
                    files
                    relatedItemKey
                    relatedOrderKey
                    createdAt
                    recipientName
                    comments
                    subArticles {
                        key
                        id
                        type
                        isSecret
                        title
                        content
                        files
                        relatedItemKey
                        relatedOrderKey
                        createdAt
                        recipientName
                        comments
                    }
                }
            }""" % qna_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    qna_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"문의글 조회 실패: {result['errors']}"}

            qna_data = result.get("data", {}).get("sellerQnaArticle")
            if not qna_data:
                return {"status": "error", "message": "문의글 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "문의글 조회 완료",
                "qna_article": qna_data
            }

        except Exception as e:
            return {"status": "error", "message": f"문의글 조회 실패: {str(e)}"}

    async def get_qna_articles(self, supplier_id: int, search_type: Optional[str] = None,
                              receiver_name: Optional[str] = None, date_from: Optional[int] = None,
                              date_to: Optional[int] = None, limit: int = 50) -> Dict[str, Any]:
        """복수 1:1 문의 게시판 글 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 기본 날짜 설정 (90일 전부터 현재까지)
            if not date_from:
                date_from = int((datetime.now() - timedelta(days=90)).timestamp())
            if not date_to:
                date_to = int(datetime.now().timestamp())

            # 검색 조건 구성
            search_conditions = []
            if search_type:
                search_conditions.append(f'type: {search_type}')
            if receiver_name:
                search_conditions.append(f'receiverName: "{receiver_name}"')

            search_str = ', '.join(search_conditions)
            if search_str:
                search_str = f', search: {{{search_str}}}'

            # 문의글 목록 쿼리
            qna_list_query = """
            query {
                sellerQnaArticles(first: %d, dateFrom: %d, dateTo: %d%s) {
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                        startCursor
                        endCursor
                    }
                    edges {
                        cursor
                        node {
                            key
                            id
                            type
                            isSecret
                            title
                            content
                            relatedItemKey
                            relatedOrderKey
                            createdAt
                            recipientName
                        }
                    }
                }
            }""" % (limit, date_from, date_to, search_str)

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    qna_list_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"문의글 목록 조회 실패: {result['errors']}"}

            qna_list_data = result.get("data", {}).get("sellerQnaArticles", {})
            if not qna_list_data:
                return {"status": "success", "message": "문의글 데이터가 없습니다", "qna_articles": []}

            edges = qna_list_data.get("edges", [])
            qna_articles = [
                {
                    "cursor": edge.get("cursor"),
                    "qna_article": edge.get("node")
                }
                for edge in edges
            ]

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "문의글 목록 조회 완료",
                "qna_articles": qna_articles,
                "page_info": qna_list_data.get("pageInfo", {}),
                "total": len(qna_articles)
            }

        except Exception as e:
            return {"status": "error", "message": f"문의글 목록 조회 실패: {str(e)}"}

    async def create_qna_article(self, supplier_id: int, qna_data: Dict[str, Any]) -> Dict[str, Any]:
        """1:1 문의글 작성"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 문의글 작성 쿼리
            create_qna_query = """
            mutation {
                createSellerQnaArticle(input: %s) {
                    key
                    id
                    type
                    title
                    content
                    createdAt
                }
            }""" % json.dumps(qna_data)

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    create_qna_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"문의글 작성 실패: {result['errors']}"}

            created_qna = result.get("data", {}).get("createSellerQnaArticle")
            if not created_qna:
                return {"status": "error", "message": "문의글 작성 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "문의글 작성 완료",
                "qna_article": created_qna
            }

        except Exception as e:
            return {"status": "error", "message": f"문의글 작성 실패: {str(e)}"}

    async def get_emergency_message(self, supplier_id: int, message_key: str) -> Dict[str, Any]:
        """단일 긴급 메시지 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 긴급 메시지 조회 쿼리
            emergency_query = """
            query {
                emergencyMessage(key: "%s") {
                    key
                    id
                    createdAt
                    type
                    itemKey
                    content
                    url
                    penalty
                    status
                    repliedAt
                    reply
                }
            }""" % message_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    emergency_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"긴급 메시지 조회 실패: {result['errors']}"}

            message_data = result.get("data", {}).get("emergencyMessage")
            if not message_data:
                return {"status": "error", "message": "긴급 메시지 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "긴급 메시지 조회 완료",
                "emergency_message": message_data
            }

        except Exception as e:
            return {"status": "error", "message": f"긴급 메시지 조회 실패: {str(e)}"}

    async def get_emergency_messages(self, supplier_id: int, status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """복수 긴급 메시지 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 긴급 메시지 목록 쿼리
            status_filter = f', status: {status}' if status else ''
            emergency_list_query = """
            query {
                emergencyMessages(first: %d%s) {
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                        startCursor
                        endCursor
                    }
                    edges {
                        cursor
                        node {
                            key
                            id
                            createdAt
                            type
                            itemKey
                            content
                            url
                            penalty
                            status
                            repliedAt
                            reply
                        }
                    }
                }
            }""" % (limit, status_filter)

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    emergency_list_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"긴급 메시지 목록 조회 실패: {result['errors']}"}

            messages_data = result.get("data", {}).get("emergencyMessages", {})
            if not messages_data:
                return {"status": "success", "message": "긴급 메시지 데이터가 없습니다", "emergency_messages": []}

            edges = messages_data.get("edges", [])
            emergency_messages = [
                {
                    "cursor": edge.get("cursor"),
                    "emergency_message": edge.get("node")
                }
                for edge in edges
            ]

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "긴급 메시지 목록 조회 완료",
                "emergency_messages": emergency_messages,
                "page_info": messages_data.get("pageInfo", {}),
                "total": len(emergency_messages)
            }

        except Exception as e:
            return {"status": "error", "message": f"긴급 메시지 목록 조회 실패: {str(e)}"}

    async def get_notice_memo(self, supplier_id: int, memo_key: str) -> Dict[str, Any]:
        """단일 알림 메모 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 알림 메모 조회 쿼리
            notice_query = """
            query {
                noticeMemo(key: "%s") {
                    key
                    id
                    createdAt
                    type
                    content
                    relatedItemKeys
                    relatedOrderKeys
                    checkedAt
                }
            }""" % memo_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    notice_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"알림 메모 조회 실패: {result['errors']}"}

            memo_data = result.get("data", {}).get("noticeMemo")
            if not memo_data:
                return {"status": "error", "message": "알림 메모 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "알림 메모 조회 완료",
                "notice_memo": memo_data
            }

        except Exception as e:
            return {"status": "error", "message": f"알림 메모 조회 실패: {str(e)}"}

    async def get_notice_memos(self, supplier_id: int, notice_type: Optional[str] = None,
                              checked: Optional[bool] = None, limit: int = 50) -> Dict[str, Any]:
        """복수 알림 메모 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 필터 조건 구성
            filter_conditions = []
            if notice_type:
                filter_conditions.append(f'type: {notice_type}')
            if checked is not None:
                filter_conditions.append(f'checked: {str(checked).lower()}')

            filter_str = ', '.join(filter_conditions)
            if filter_str:
                filter_str = f', {filter_str}'

            # 알림 메모 목록 쿼리
            notice_list_query = """
            query {
                noticeMemos(first: %d%s) {
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                        startCursor
                        endCursor
                    }
                    edges {
                        cursor
                        node {
                            key
                            id
                            createdAt
                            type
                            content
                            relatedItemKeys
                            relatedOrderKeys
                            checkedAt
                        }
                    }
                }
            }""" % (limit, filter_str)

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    notice_list_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"알림 메모 목록 조회 실패: {result['errors']}"}

            memos_data = result.get("data", {}).get("noticeMemos", {})
            if not memos_data:
                return {"status": "success", "message": "알림 메모 데이터가 없습니다", "notice_memos": []}

            edges = memos_data.get("edges", [])
            notice_memos = [
                {
                    "cursor": edge.get("cursor"),
                    "notice_memo": edge.get("node")
                }
                for edge in edges
            ]

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "알림 메모 목록 조회 완료",
                "notice_memos": notice_memos,
                "page_info": memos_data.get("pageInfo", {}),
                "total": len(notice_memos)
            }

        except Exception as e:
            return {"status": "error", "message": f"알림 메모 목록 조회 실패: {str(e)}"}

    async def request_refund_exchange(self, supplier_id: int, order_key: str, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """주문 상품 반품/교환 신청"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 반품/교환 신청 쿼리
            refund_query = """
            mutation {
                requestRefundExchangeOrder(key: "%s", input: %s) {
                    key
                    id
                    status
                    updatedAt
                }
            }""" % (order_key, json.dumps(refund_data))

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    refund_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"반품/교환 신청 실패: {result['errors']}"}

            refund_result = result.get("data", {}).get("requestRefundExchangeOrder")
            if not refund_result:
                return {"status": "error", "message": "반품/교환 신청 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "반품/교환 신청 완료",
                "refund_result": refund_result
            }

        except Exception as e:
            return {"status": "error", "message": f"반품/교환 신청 실패: {str(e)}"}

class CategoryService:
    """카테고리 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ownerclan_api = OwnerClanAPI()
        self.token_manager = TokenManager(db, self.ownerclan_api)

    async def get_category(self, supplier_id: int, category_key: str) -> Dict[str, Any]:
        """단일 카테고리 정보 조회"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 카테고리 정보 쿼리
            category_query = """
            query {
                category(key: "%s") {
                    key
                    id
                    name
                    fullName
                    attributes
                    parent {
                        key
                        id
                        name
                    }
                    children {
                        key
                        id
                        name
                    }
                    ancestors {
                        key
                        id
                        name
                    }
                    descendants(first: 100) {
                        pageInfo {
                            hasNextPage
                            hasPreviousPage
                            startCursor
                            endCursor
                        }
                        edges {
                            cursor
                            node {
                                key
                                id
                                name
                            }
                        }
                    }
                }
            }""" % category_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    category_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"카테고리 조회 실패: {result['errors']}"}

            category_data = result.get("data", {}).get("category")
            if not category_data:
                return {"status": "error", "message": "카테고리 데이터를 찾을 수 없습니다"}

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "카테고리 조회 완료",
                "category": category_data
            }

        except Exception as e:
            return {"status": "error", "message": f"카테고리 조회 실패: {str(e)}"}

    async def get_root_categories(self, supplier_id: int) -> Dict[str, Any]:
        """최상위 카테고리들 조회 (ROOT 카테고리의 하위)"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # ROOT 카테고리 조회 쿼리
            root_query = """
            query {
                category(key: "00000000") {
                    key
                    id
                    name
                    children {
                        key
                        id
                        name
                        fullName
                        attributes
                    }
                }
            }"""

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    root_query,
                    token=token,
                    account_id=account.id
                )

            if "errors" in result:
                return {"status": "error", "message": f"카테고리 조회 실패: {result['errors']}"}

            root_data = result.get("data", {}).get("category")
            if not root_data:
                return {"status": "error", "message": "ROOT 카테고리 데이터를 찾을 수 없습니다"}

            children = root_data.get("children", [])

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "최상위 카테고리 조회 완료",
                "root_category": root_data,
                "categories": children,
                "total": len(children)
            }

        except Exception as e:
            return {"status": "error", "message": f"카테고리 조회 실패: {str(e)}"}

    async def get_all_categories(self, supplier_id: int, parent_key: Optional[str] = None) -> Dict[str, Any]:
        """전체 카테고리 조회 (트리 구조)"""
        try:
            # 토큰 조회
            token = await self.token_manager.get_valid_token(supplier_id)
            if not token:
                return {"status": "error", "message": "유효한 토큰이 없습니다"}

            # 계정 정보 조회
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
                return {"status": "error", "message": "공급사 계정을 찾을 수 없습니다"}

            # 모든 카테고리 조회를 위한 재귀적 접근
            # ROOT 카테고리부터 시작해서 모든 하위 카테고리를 수집
            all_categories = []
            await self._collect_category_tree(supplier_id, token, account.id, "00000000", all_categories, 0)

            # 통계 업데이트
            await self.token_manager.update_request_stats(account.id, success=True)

            return {
                "status": "success",
                "message": "전체 카테고리 조회 완료",
                "categories": all_categories,
                "total": len(all_categories)
            }

        except Exception as e:
            return {"status": "error", "message": f"카테고리 조회 실패: {str(e)}"}

    async def _collect_category_tree(self, supplier_id: int, token: str, account_id: int,
                                   category_key: str, result_list: List, level: int):
        """카테고리 트리를 재귀적으로 수집"""
        try:
            # 현재 카테고리 정보 조회
            category_query = """
            query {
                category(key: "%s") {
                    key
                    id
                    name
                    fullName
                    attributes
                    children {
                        key
                        id
                        name
                    }
                }
            }""" % category_key

            async with self.ownerclan_api:
                result = await self.ownerclan_api.execute_query(
                    category_query,
                    token=token,
                    account_id=account_id
                )

            if "errors" in result:
                logger.error(f"카테고리 조회 실패 {category_key}: {result['errors']}")
                return

            category_data = result.get("data", {}).get("category")
            if not category_data:
                return

            # 현재 카테고리 정보 저장
            category_info = {
                "key": category_data.get("key"),
                "id": category_data.get("id"),
                "name": category_data.get("name"),
                "full_name": category_data.get("fullName"),
                "attributes": category_data.get("attributes", []),
                "level": level,
                "children": []
            }

            result_list.append(category_info)

            # 하위 카테고리들 조회
            children = category_data.get("children", [])
            for child in children:
                child_key = child.get("key")
                if child_key:
                    await self._collect_category_tree(
                        supplier_id, token, account_id, child_key,
                        category_info["children"], level + 1
                    )

        except Exception as e:
            logger.error(f"카테고리 트리 수집 실패 {category_key}: {e}")

    async def get_category_meta_info(self, supplier_id: int) -> Dict[str, Any]:
        """카테고리 메타정보 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 카테고리 메타정보 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/categories/meta"
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 메타정보 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 메타정보 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 메타정보 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 메타정보 조회 실패: {str(e)}"
            }

    async def recommend_categories(self, supplier_id: int, keyword: str) -> Dict[str, Any]:
        """카테고리 추천"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 카테고리 추천 요청
            result = await coupangwing_api.make_request(
                "POST",
                f"/vendors/{vendor_id}/categories/recommend",
                {"keyword": keyword}
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 추천 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 추천 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 추천 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 추천 실패: {str(e)}"
            }

    async def check_category_auto_matching(self, supplier_id: int) -> Dict[str, Any]:
        """카테고리 자동 매칭 서비스 동의 확인"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 카테고리 자동 매칭 동의 확인
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/categories/auto-matching/consent"
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 자동 매칭 동의 확인 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 자동 매칭 동의 확인 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 자동 매칭 동의 확인 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 자동 매칭 동의 확인 실패: {str(e)}"
            }

    async def get_categories_list(self, supplier_id: int, parent_category_id: Optional[str] = None,
                                 has_children: Optional[bool] = None) -> Dict[str, Any]:
        """카테고리 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 쿼리 파라미터 구성
            query_params = {}
            if parent_category_id:
                query_params["parentCategoryId"] = parent_category_id
            if has_children is not None:
                query_params["hasChildren"] = str(has_children).lower()

            # 카테고리 목록 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/categories",
                query_params
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 목록 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 목록 조회 실패: {str(e)}"
            }

    async def get_category_detail(self, supplier_id: int, category_id: str) -> Dict[str, Any]:
        """카테고리 단건 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 카테고리 단건 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/categories/{category_id}"
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 단건 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 단건 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 단건 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 단건 조회 실패: {str(e)}"
            }

    async def validate_category(self, supplier_id: int, category_id: str) -> Dict[str, Any]:
        """카테고리 유효성 검사"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 카테고리 유효성 검사
            result = await coupangwing_api.make_request(
                "POST",
                f"/vendors/{vendor_id}/categories/validate",
                {"categoryId": category_id}
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "카테고리 유효성 검사 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"카테고리 유효성 검사 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"카테고리 유효성 검사 실패: {e}")
            return {
                "status": "error",
                "message": f"카테고리 유효성 검사 실패: {str(e)}"
            }

class CoupangWingService:
    """쿠팡윙 API 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_coupangwing_credentials(self, supplier_id: int) -> Optional[tuple[str, str]]:
        """쿠팡윙 API 인증 정보 조회"""
        try:
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

            # SupplierAccount 테이블에 쿠팡윙 인증 정보를 저장
            api_key = getattr(account, 'coupang_access_key', None)
            vendor_id = getattr(account, 'coupang_vendor_id', None)

            if api_key and vendor_id:
                return api_key, vendor_id
            else:
                logger.warning(f"쿠팡윙 인증 정보가 설정되지 않음: supplier_id={supplier_id}")
                return None

        except Exception as e:
            logger.error(f"쿠팡윙 인증 정보 조회 실패: {e}")
            return None

    async def test_coupangwing_connection(self, supplier_id: int) -> Dict[str, Any]:
        """쿠팡윙 API 연결 테스트"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials

            # 쿠팡윙 API 클라이언트 생성
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 테스트 요청 (벤더 정보 조회)
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}"
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡윙 API 연결 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡윙 API 연결 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡윙 연결 테스트 실패: {e}")
            return {
                "status": "error",
                "message": f"연결 테스트 실패: {str(e)}"
            }

    async def get_return_requests(
        self,
        supplier_id: int,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """반품 요청 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 쿼리 파라미터 구성
            query_params = {}
            if created_at_from:
                query_params["createdAtFrom"] = created_at_from
            if created_at_to:
                query_params["createdAtTo"] = created_at_to
            if status:
                query_params["status"] = status
            if limit:
                query_params["max"] = str(limit)

            # 반품 요청 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/return-requests",
                query_params
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품 요청 목록 조회 성공",
                    "data": result.get("data", {}),
                    "total": len(result.get("data", {}).get("data", []))
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품 요청 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품 요청 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품 요청 조회 실패: {str(e)}"
            }

    async def get_orders(
        self,
        supplier_id: int,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """주문 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 쿼리 파라미터 구성
            query_params = {}
            if created_at_from:
                query_params["createdAtFrom"] = created_at_from
            if created_at_to:
                query_params["createdAtTo"] = created_at_to
            if status:
                query_params["status"] = status
            if limit:
                query_params["max"] = str(limit)

            # 주문 목록 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/orders",
                query_params
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "주문 목록 조회 성공",
                    "data": result.get("data", {}),
                    "total": len(result.get("data", {}).get("data", []))
                }
            else:
                return {
                    "status": "error",
                    "message": f"주문 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"주문 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"주문 목록 조회 실패: {str(e)}"
            }

    async def get_products(
        self,
        supplier_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """상품 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 쿼리 파라미터 구성
            query_params = {
                "max": str(limit),
                "offset": str(offset)
            }

            # 상품 목록 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/products",
                query_params
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "상품 목록 조회 성공",
                    "data": result.get("data", {}),
                    "total": len(result.get("data", {}).get("data", []))
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 목록 조회 실패: {str(e)}"
            }

    async def get_vendor_info(self, supplier_id: int) -> Dict[str, Any]:
        """벤더 정보 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 벤더 정보 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}"
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "벤더 정보 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"벤더 정보 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"벤더 정보 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"벤더 정보 조회 실패: {str(e)}"
            }

    async def get_shipping_locations(self, supplier_id: int) -> Dict[str, Any]:
        """출고지 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 출고지 목록 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/shipping-locations"
            )

            if result["status"] == "success":
                shipping_locations = result.get("data", [])

                # 데이터베이스에 저장
                for location in shipping_locations:
                    await self._save_shipping_location(supplier_id, location)

                return {
                    "status": "success",
                    "message": "출고지 목록 조회 및 저장 완료",
                    "data": shipping_locations,
                    "total": len(shipping_locations)
                }
            else:
                return {
                    "status": "error",
                    "message": f"출고지 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"출고지 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"출고지 목록 조회 실패: {str(e)}"
            }

    async def _save_shipping_location(self, supplier_id: int, location_data: Dict[str, Any]):
        """출고지 정보를 데이터베이스에 저장"""
        try:
            location_key = location_data.get("key")
            if not location_key:
                return

            # 기존 출고지 확인
            existing_result = await self.db.execute(
                select(ShippingLocation).where(
                    and_(
                        ShippingLocation.supplier_id == supplier_id,
                        ShippingLocation.location_key == location_key
                    )
                )
            )
            existing_location = existing_result.scalar_one_or_none()

            location_info = {
                "supplier_id": supplier_id,
                "location_key": location_data.get("key"),
                "location_id": location_data.get("id"),
                "name": location_data.get("name"),
                "address": json.dumps(location_data.get("address", {})),
                "contact_info": json.dumps(location_data.get("contactInfo", {})),
                "location_type": location_data.get("type"),
                "is_active": True,
                "is_default": location_data.get("isDefault", False)
            }

            if existing_location:
                # 업데이트
                await self.db.execute(
                    update(ShippingLocation).where(
                        and_(
                            ShippingLocation.supplier_id == supplier_id,
                            ShippingLocation.location_key == location_key
                        )
                    ).values(**location_info)
                )
            else:
                # 새 출고지 생성
                new_location = ShippingLocation(**location_info)
                self.db.add(new_location)

            await self.db.commit()

        except Exception as e:
            logger.error(f"출고지 저장 실패 {location_key}: {e}")

    async def get_return_locations(self, supplier_id: int) -> Dict[str, Any]:
        """반품지 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 반품지 목록 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/return-locations"
            )

            if result["status"] == "success":
                return_locations = result.get("data", [])

                # 데이터베이스에 저장
                for location in return_locations:
                    await self._save_return_location(supplier_id, location)

                return {
                    "status": "success",
                    "message": "반품지 목록 조회 및 저장 완료",
                    "data": return_locations,
                    "total": len(return_locations)
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품지 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품지 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품지 목록 조회 실패: {str(e)}"
            }

    async def _save_return_location(self, supplier_id: int, location_data: Dict[str, Any]):
        """반품지 정보를 데이터베이스에 저장"""
        try:
            location_key = location_data.get("key")
            if not location_key:
                return

            # 기존 반품지 확인
            existing_result = await self.db.execute(
                select(ReturnLocation).where(
                    and_(
                        ReturnLocation.supplier_id == supplier_id,
                        ReturnLocation.location_key == location_key
                    )
                )
            )
            existing_location = existing_result.scalar_one_or_none()

            location_info = {
                "supplier_id": supplier_id,
                "location_key": location_data.get("key"),
                "location_id": location_data.get("id"),
                "name": location_data.get("name"),
                "address": json.dumps(location_data.get("address", {})),
                "contact_info": json.dumps(location_data.get("contactInfo", {})),
                "location_type": location_data.get("type"),
                "is_active": True,
                "is_default": location_data.get("isDefault", False)
            }

            if existing_location:
                # 업데이트
                await self.db.execute(
                    update(ReturnLocation).where(
                        and_(
                            ReturnLocation.supplier_id == supplier_id,
                            ReturnLocation.location_key == location_key
                        )
                    ).values(**location_info)
                )
            else:
                # 새 반품지 생성
                new_location = ReturnLocation(**location_info)
                self.db.add(new_location)

            await self.db.commit()

        except Exception as e:
            logger.error(f"반품지 저장 실패 {location_key}: {e}")

    async def get_return_location_detail(self, supplier_id: int, location_key: str) -> Dict[str, Any]:
        """반품지 단건 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            # 반품지 단건 조회
            result = await coupangwing_api.make_request(
                "GET",
                f"/vendors/{vendor_id}/return-locations/{location_key}"
            )

            if result["status"] == "success":
                return_location = result.get("data", {})

                # 데이터베이스에 저장
                await self._save_return_location(supplier_id, return_location)

                return {
                    "status": "success",
                    "message": "반품지 단건 조회 및 저장 완료",
                    "data": return_location
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품지 단건 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품지 단건 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품지 단건 조회 실패: {str(e)}"
            }

    async def get_shipment_list_daily(
        self,
        supplier_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """발주서 목록 조회 (일단위 페이징)"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_shipment_list_daily(
                date_from=date_from,
                date_to=date_to,
                status=status,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "발주서 목록 조회 성공 (일단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"발주서 목록 조회 실패 (일단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"발주서 목록 조회 실패 (일단위): {e}")
            return {
                "status": "error",
                "message": f"발주서 목록 조회 실패 (일단위): {str(e)}"
            }

    async def get_shipment_list_minute(
        self,
        supplier_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """발주서 목록 조회 (분단위 전체)"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_shipment_list_minute(
                date_from=date_from,
                date_to=date_to,
                status=status
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "발주서 목록 조회 성공 (분단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"발주서 목록 조회 실패 (분단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"발주서 목록 조회 실패 (분단위): {e}")
            return {
                "status": "error",
                "message": f"발주서 목록 조회 실패 (분단위): {str(e)}"
            }

    async def get_shipment_by_shipment_box_id(self, supplier_id: int, shipment_box_id: str) -> Dict[str, Any]:
        """발주서 단건 조회 (shipmentBoxId)"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_shipment_by_shipment_box_id(shipment_box_id)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "발주서 단건 조회 성공 (shipmentBoxId)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"발주서 단건 조회 실패 (shipmentBoxId): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"발주서 단건 조회 실패 (shipmentBoxId): {e}")
            return {
                "status": "error",
                "message": f"발주서 단건 조회 실패 (shipmentBoxId): {str(e)}"
            }

    async def get_shipment_by_order_id(self, supplier_id: int, order_id: str) -> Dict[str, Any]:
        """발주서 단건 조회 (orderId)"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_shipment_by_order_id(order_id)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "발주서 단건 조회 성공 (orderId)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"발주서 단건 조회 실패 (orderId): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"발주서 단건 조회 실패 (orderId): {e}")
            return {
                "status": "error",
                "message": f"발주서 단건 조회 실패 (orderId): {str(e)}"
            }

    async def get_shipment_status_history(
        self,
        supplier_id: int,
        shipment_box_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """배송상태 변경 히스토리 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_shipment_status_history(
                shipment_box_id=shipment_box_id,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "배송상태 변경 히스토리 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"배송상태 변경 히스토리 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"배송상태 변경 히스토리 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"배송상태 변경 히스토리 조회 실패: {str(e)}"
            }

    # 반품 관련 메서드들
    async def get_return_requests(
        self,
        supplier_id: int,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """반품 취소 요청 목록 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_return_requests(
                status=status,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품 취소 요청 목록 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품 취소 요청 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품 취소 요청 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품 취소 요청 목록 조회 실패: {str(e)}"
            }

    async def get_return_request_detail(self, supplier_id: int, return_request_id: str) -> Dict[str, Any]:
        """반품요청 단건 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_return_request_detail(return_request_id)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품요청 단건 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품요청 단건 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품요청 단건 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품요청 단건 조회 실패: {str(e)}"
            }

    async def confirm_return_receipt(self, supplier_id: int, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """반품상품 입고 확인처리"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.confirm_return_receipt(return_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품상품 입고 확인처리 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품상품 입고 확인처리 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품상품 입고 확인처리 실패: {e}")
            return {
                "status": "error",
                "message": f"반품상품 입고 확인처리 실패: {str(e)}"
            }

    async def approve_return_request(self, supplier_id: int, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """반품요청 승인 처리"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.approve_return_request(return_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품요청 승인 처리 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품요청 승인 처리 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품요청 승인 처리 실패: {e}")
            return {
                "status": "error",
                "message": f"반품요청 승인 처리 실패: {str(e)}"
            }

    async def get_return_withdrawal_history_by_period(
        self,
        supplier_id: int,
        date_from: str,
        date_to: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """반품철회 이력 기간별 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_return_withdrawal_history_by_period(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품철회 이력 기간별 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품철회 이력 기간별 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품철회 이력 기간별 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품철회 이력 기간별 조회 실패: {str(e)}"
            }

    async def get_return_withdrawal_history_by_receipt_number(self, supplier_id: int, receipt_number: str) -> Dict[str, Any]:
        """반품철회 이력 접수번호로 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_return_withdrawal_history_by_receipt_number(receipt_number)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "반품철회 이력 접수번호로 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"반품철회 이력 접수번호로 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"반품철회 이력 접수번호로 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"반품철회 이력 접수번호로 조회 실패: {str(e)}"
            }

    async def register_return_invoice(self, supplier_id: int, return_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """회수 송장 등록"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.register_return_invoice(return_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "회수 송장 등록 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"회수 송장 등록 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"회수 송장 등록 실패: {e}")
            return {
                "status": "error",
                "message": f"회수 송장 등록 실패: {str(e)}"
            }

    # 교환 관련 메서드들
    async def get_exchange_requests(
        self,
        supplier_id: int,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """교환요청 목록조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_exchange_requests(
                status=status,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "교환요청 목록조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"교환요청 목록조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"교환요청 목록조회 실패: {e}")
            return {
                "status": "error",
                "message": f"교환요청 목록조회 실패: {str(e)}"
            }

    async def confirm_exchange_receipt(self, supplier_id: int, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환요청상품 입고 확인처리"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.confirm_exchange_receipt(exchange_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "교환요청상품 입고 확인처리 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"교환요청상품 입고 확인처리 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"교환요청상품 입고 확인처리 실패: {e}")
            return {
                "status": "error",
                "message": f"교환요청상품 입고 확인처리 실패: {str(e)}"
            }

    async def reject_exchange_request(self, supplier_id: int, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환요청 거부 처리"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.reject_exchange_request(exchange_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "교환요청 거부 처리 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"교환요청 거부 처리 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"교환요청 거부 처리 실패: {e}")
            return {
                "status": "error",
                "message": f"교환요청 거부 처리 실패: {str(e)}"
            }

    async def upload_exchange_invoice(self, supplier_id: int, exchange_request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """교환상품 송장 업로드 처리"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.upload_exchange_invoice(exchange_request_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "교환상품 송장 업로드 처리 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"교환상품 송장 업로드 처리 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"교환상품 송장 업로드 처리 실패: {e}")
            return {
                "status": "error",
                "message": f"교환상품 송장 업로드 처리 실패: {str(e)}"
            }

    # 상품별 고객문의 관련 메서드들
    async def get_product_inquiries(
        self,
        supplier_id: int,
        seller_product_id: str,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """상품별 고객문의 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_product_inquiries(
                seller_product_id=seller_product_id,
                status=status,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "상품별 고객문의 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품별 고객문의 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품별 고객문의 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"상품별 고객문의 조회 실패: {str(e)}"
            }

    async def reply_to_product_inquiry(
        self,
        supplier_id: int,
        seller_product_id: str,
        inquiry_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """상품별 고객문의 답변"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.reply_to_product_inquiry(
                seller_product_id=seller_product_id,
                inquiry_id=inquiry_id,
                data=data
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "상품별 고객문의 답변 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품별 고객문의 답변 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품별 고객문의 답변 실패: {e}")
            return {
                "status": "error",
                "message": f"상품별 고객문의 답변 실패: {str(e)}"
            }

    # 쿠팡 고객센터 문의 관련 메서드들
    async def get_cs_inquiries(
        self,
        supplier_id: int,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """쿠팡 고객센터 문의조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_cs_inquiries(
                status=status,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 고객센터 문의조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 고객센터 문의조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 고객센터 문의조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 고객센터 문의조회 실패: {str(e)}"
            }

    async def get_cs_inquiry_detail(self, supplier_id: int, inquiry_id: str) -> Dict[str, Any]:
        """쿠팡 고객센터 문의 단건 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_cs_inquiry_detail(inquiry_id)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 고객센터 문의 단건 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 고객센터 문의 단건 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 고객센터 문의 단건 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 고객센터 문의 단건 조회 실패: {str(e)}"
            }

    async def reply_to_cs_inquiry(
        self,
        supplier_id: int,
        inquiry_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """쿠팡 고객센터 문의답변"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.reply_to_cs_inquiry(inquiry_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 고객센터 문의답변 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 고객센터 문의답변 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 고객센터 문의답변 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 고객센터 문의답변 실패: {str(e)}"
            }

    async def confirm_cs_inquiry(
        self,
        supplier_id: int,
        inquiry_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """쿠팡 고객센터 문의확인"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.confirm_cs_inquiry(inquiry_id, data)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 고객센터 문의확인 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 고객센터 문의확인 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 고객센터 문의확인 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 고객센터 문의확인 실패: {str(e)}"
            }

    # 매출 및 지급 관련 메서드들
    async def get_sales_history(
        self,
        supplier_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """매출내역 조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_sales_history(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "매출내역 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"매출내역 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"매출내역 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"매출내역 조회 실패: {str(e)}"
            }

    async def get_payment_history(
        self,
        supplier_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """지급내역조회"""
        try:
            credentials = await self.get_coupangwing_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡윙 인증 정보가 설정되지 않았습니다"
                }

            api_key, vendor_id = credentials
            coupangwing_api = CoupangWingAPI(api_key, vendor_id)

            result = await coupangwing_api.get_payment_history(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset
            )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "지급내역조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"지급내역조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"지급내역조회 실패: {e}")
            return {
                "status": "error",
                "message": f"지급내역조회 실패: {str(e)}"
            }


class CoupangProductService:
    """쿠팡 상품 API 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_coupang_credentials(self, supplier_id: int) -> Optional[tuple[str, str, str]]:
        """쿠팡 API 인증 정보 조회"""
        try:
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

            # SupplierAccount 테이블에 쿠팡 인증 정보를 저장
            access_key = getattr(account, 'coupang_access_key', None)
            secret_key = getattr(account, 'coupang_secret_key', None)
            vendor_id = getattr(account, 'coupang_vendor_id', None)

            if access_key and secret_key and vendor_id:
                return access_key, secret_key, vendor_id
            else:
                logger.warning(f"쿠팡 인증 정보가 설정되지 않음: supplier_id={supplier_id}")
                return None

        except Exception as e:
            logger.error(f"쿠팡 인증 정보 조회 실패: {e}")
            return None

    async def create_product(self, supplier_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """쿠팡 상품 생성"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.create_product(product_data)

            if result["status"] == "success":
                product_response = result.get("data", {})

                # 생성된 상품 정보를 데이터베이스에 저장
                await self._save_coupang_product(supplier_id, product_response)

                return {
                    "status": "success",
                    "message": "쿠팡 상품이 성공적으로 생성되었습니다",
                    "data": product_response
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 생성 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 생성 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 생성 실패: {str(e)}"
            }

    async def request_approval(self, supplier_id: int, seller_product_id: str) -> Dict[str, Any]:
        """쿠팡 상품 승인 요청"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.request_approval(seller_product_id)

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 상품 승인 요청이 완료되었습니다",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 승인 요청 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 승인 요청 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 승인 요청 실패: {str(e)}"
            }

    async def get_products(self, supplier_id: int, max: int = 50, status: Optional[str] = None) -> Dict[str, Any]:
        """쿠팡 상품 목록 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_products(max=max, status=status)

            if result["status"] == "success":
                products_data = result.get("data", {})

                # 상품 정보를 데이터베이스에 저장/업데이트
                products = products_data.get("data", [])
                for product in products:
                    await self._save_coupang_product(supplier_id, product)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 목록 조회 성공",
                    "data": products_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 목록 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 목록 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 목록 조회 실패: {str(e)}"
            }

    async def get_product(self, supplier_id: int, seller_product_id: str) -> Dict[str, Any]:
        """쿠팡 단일 상품 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_product(seller_product_id)

            if result["status"] == "success":
                product_data = result.get("data", {})

                # 상품 정보를 데이터베이스에 저장/업데이트
                await self._save_coupang_product(supplier_id, product_data)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 조회 성공",
                    "data": product_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 조회 실패: {str(e)}"
            }

    async def update_product(
        self,
        supplier_id: int,
        seller_product_id: str,
        product_data: Dict[str, Any],
        requires_approval: bool = True
    ) -> Dict[str, Any]:
        """쿠팡 상품 수정"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.update_product(
                    seller_product_id,
                    product_data,
                    requires_approval=requires_approval
                )

            if result["status"] == "success":
                updated_product = result.get("data", {})

                # 수정된 상품 정보를 데이터베이스에 저장
                await self._save_coupang_product(supplier_id, updated_product)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 수정이 완료되었습니다",
                    "data": updated_product
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 수정 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 수정 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 수정 실패: {str(e)}"
            }

    async def get_product_registration_status(
        self,
        supplier_id: int,
        max: int = 50,
        status: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """쿠팡 상품 등록 현황 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_product_registration_status(
                    max=max,
                    status=status,
                    created_at_from=created_at_from,
                    created_at_to=created_at_to,
                    updated_at_from=updated_at_from,
                    updated_at_to=updated_at_to
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "쿠팡 상품 등록 현황 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 등록 현황 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 등록 현황 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 등록 현황 조회 실패: {str(e)}"
            }

    async def get_products_paged(
        self,
        supplier_id: int,
        max: int = 50,
        status: Optional[str] = None,
        vendor_item_id: Optional[str] = None,
        seller_product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """쿠팡 상품 페이징 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_products_paged(
                    max=max,
                    status=status,
                    vendor_item_id=vendor_item_id,
                    seller_product_name=seller_product_name
                )

            if result["status"] == "success":
                products_data = result.get("data", {})

                # 상품 정보를 데이터베이스에 저장/업데이트
                products = products_data.get("data", [])
                for product in products:
                    await self._save_coupang_product(supplier_id, product)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 페이징 조회 성공",
                    "data": products_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 페이징 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 페이징 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 페이징 조회 실패: {str(e)}"
            }

    async def get_products_by_date_range(
        self,
        supplier_id: int,
        max: int = 50,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """쿠팡 상품 날짜 구간별 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_products_by_date_range(
                    max=max,
                    created_at_from=created_at_from,
                    created_at_to=created_at_to,
                    updated_at_from=updated_at_from,
                    updated_at_to=updated_at_to
                )

            if result["status"] == "success":
                products_data = result.get("data", {})

                # 상품 정보를 데이터베이스에 저장/업데이트
                products = products_data.get("data", [])
                for product in products:
                    await self._save_coupang_product(supplier_id, product)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 날짜 구간별 조회 성공",
                    "data": products_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 날짜 구간별 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 날짜 구간별 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 날짜 구간별 조회 실패: {str(e)}"
            }

    async def get_product_summary(self, supplier_id: int, seller_product_id: str) -> Dict[str, Any]:
        """쿠팡 상품 요약 정보 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_product_summary(seller_product_id)

            if result["status"] == "success":
                summary_data = result.get("data", {})

                # 요약 정보를 데이터베이스에 업데이트
                await self._update_product_summary(supplier_id, seller_product_id, summary_data)

                return {
                    "status": "success",
                    "message": "쿠팡 상품 요약 정보 조회 성공",
                    "data": summary_data
                }
            else:
                return {
                    "status": "error",
                    "message": f"쿠팡 상품 요약 정보 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"쿠팡 상품 요약 정보 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"쿠팡 상품 요약 정보 조회 실패: {str(e)}"
            }

    async def get_product_items_status(
        self,
        supplier_id: int,
        seller_product_id: str,
        max: int = 50,
        vendor_item_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 수량/가격/상태 조회"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.get_product_items_status(
                    seller_product_id=seller_product_id,
                    max=max,
                    vendor_item_id=vendor_item_id,
                    status=status
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "상품 아이템별 상태 조회 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템별 상태 조회 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템별 상태 조회 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템별 상태 조회 실패: {str(e)}"
            }

    async def update_item_quantity(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        """상품 아이템별 수량 변경"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.update_item_quantity(
                    seller_product_id=seller_product_id,
                    item_id=item_id,
                    quantity=quantity
                )

            if result["status"] == "success":
                # 수량 변경 성공시 데이터베이스 업데이트
                await self._update_item_quantity_in_db(supplier_id, seller_product_id, item_id, quantity)

                return {
                    "status": "success",
                    "message": "상품 아이템 수량 변경 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템 수량 변경 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템 수량 변경 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템 수량 변경 실패: {str(e)}"
            }

    async def update_item_price(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str,
        price: int,
        sale_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 가격 변경"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.update_item_price(
                    seller_product_id=seller_product_id,
                    item_id=item_id,
                    price=price,
                    sale_price=sale_price
                )

            if result["status"] == "success":
                # 가격 변경 성공시 데이터베이스 업데이트
                await self._update_item_price_in_db(supplier_id, seller_product_id, item_id, price, sale_price)

                return {
                    "status": "success",
                    "message": "상품 아이템 가격 변경 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템 가격 변경 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템 가격 변경 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템 가격 변경 실패: {str(e)}"
            }

    async def resume_item_sale(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """상품 아이템별 판매 재개"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.resume_item_sale(
                    seller_product_id=seller_product_id,
                    item_id=item_id
                )

            if result["status"] == "success":
                # 판매 재개 성공시 데이터베이스 업데이트
                await self._update_item_status_in_db(supplier_id, seller_product_id, item_id, "ACTIVE")

                return {
                    "status": "success",
                    "message": "상품 아이템 판매 재개 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템 판매 재개 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템 판매 재개 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템 판매 재개 실패: {str(e)}"
            }

    async def stop_item_sale(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """상품 아이템별 판매 중지"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.stop_item_sale(
                    seller_product_id=seller_product_id,
                    item_id=item_id
                )

            if result["status"] == "success":
                # 판매 중지 성공시 데이터베이스 업데이트
                await self._update_item_status_in_db(supplier_id, seller_product_id, item_id, "STOPPED")

                return {
                    "status": "success",
                    "message": "상품 아이템 판매 중지 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템 판매 중지 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템 판매 중지 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템 판매 중지 실패: {str(e)}"
            }

    async def update_item_price_by_discount_rate(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str,
        discount_rate: float,
        base_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """상품 아이템별 할인율 기준 가격 변경"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.update_item_price_by_discount_rate(
                    seller_product_id=seller_product_id,
                    item_id=item_id,
                    discount_rate=discount_rate,
                    base_price=base_price
                )

            if result["status"] == "success":
                # 할인율 기준 가격 변경 성공시 데이터베이스 업데이트
                updated_price = result.get("data", {}).get("calculatedPrice")
                if updated_price:
                    await self._update_item_price_in_db(supplier_id, seller_product_id, item_id, updated_price)

                return {
                    "status": "success",
                    "message": "상품 아이템 할인율 기준 가격 변경 성공",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"상품 아이템 할인율 기준 가격 변경 실패: {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"상품 아이템 할인율 기준 가격 변경 실패: {e}")
            return {
                "status": "error",
                "message": f"상품 아이템 할인율 기준 가격 변경 실패: {str(e)}"
            }

    async def activate_auto_generated_options_by_item(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 활성화 (옵션 상품 단위)"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.activate_auto_generated_options_by_item(
                    seller_product_id=seller_product_id,
                    item_id=item_id
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "자동생성옵션 활성화 성공 (옵션 상품 단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"자동생성옵션 활성화 실패 (옵션 상품 단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"자동생성옵션 활성화 실패 (옵션 상품 단위): {e}")
            return {
                "status": "error",
                "message": f"자동생성옵션 활성화 실패 (옵션 상품 단위): {str(e)}"
            }

    async def activate_auto_generated_options_by_product(
        self,
        supplier_id: int,
        seller_product_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 활성화 (전체 상품 단위)"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.activate_auto_generated_options_by_product(
                    seller_product_id=seller_product_id
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "자동생성옵션 활성화 성공 (전체 상품 단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"자동생성옵션 활성화 실패 (전체 상품 단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"자동생성옵션 활성화 실패 (전체 상품 단위): {e}")
            return {
                "status": "error",
                "message": f"자동생성옵션 활성화 실패 (전체 상품 단위): {str(e)}"
            }

    async def deactivate_auto_generated_options_by_item(
        self,
        supplier_id: int,
        seller_product_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 비활성화 (옵션 상품 단위)"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.deactivate_auto_generated_options_by_item(
                    seller_product_id=seller_product_id,
                    item_id=item_id
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "자동생성옵션 비활성화 성공 (옵션 상품 단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"자동생성옵션 비활성화 실패 (옵션 상품 단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"자동생성옵션 비활성화 실패 (옵션 상품 단위): {e}")
            return {
                "status": "error",
                "message": f"자동생성옵션 비활성화 실패 (옵션 상품 단위): {str(e)}"
            }

    async def deactivate_auto_generated_options_by_product(
        self,
        supplier_id: int,
        seller_product_id: str
    ) -> Dict[str, Any]:
        """자동생성옵션 비활성화 (전체 상품 단위)"""
        try:
            credentials = await self.get_coupang_credentials(supplier_id)
            if not credentials:
                return {
                    "status": "error",
                    "message": "쿠팡 인증 정보가 설정되지 않았습니다"
                }

            access_key, secret_key, vendor_id = credentials

            async with CoupangProductAPI(access_key, secret_key, vendor_id) as api:
                result = await api.deactivate_auto_generated_options_by_product(
                    seller_product_id=seller_product_id
                )

            if result["status"] == "success":
                return {
                    "status": "success",
                    "message": "자동생성옵션 비활성화 성공 (전체 상품 단위)",
                    "data": result.get("data", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"자동생성옵션 비활성화 실패 (전체 상품 단위): {result.get('message', '알 수 없는 오류')}"
                }

        except Exception as e:
            logger.error(f"자동생성옵션 비활성화 실패 (전체 상품 단위): {e}")
            return {
                "status": "error",
                "message": f"자동생성옵션 비활성화 실패 (전체 상품 단위): {str(e)}"
            }

    async def _save_coupang_product(self, supplier_id: int, product_data: Dict[str, Any]):
        """쿠팡 상품 정보를 데이터베이스에 저장"""
        try:
            seller_product_id = product_data.get("sellerProductId")
            if not seller_product_id:
                return

            # 기존 상품 확인
            existing_result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.coupang_product_id == seller_product_id
                    )
                )
            )
            existing_product = existing_result.scalar_one_or_none()

            # 상품 정보 변환
            product_info = {
                "supplier_id": supplier_id,
                "coupang_product_id": seller_product_id,
                "item_key": product_data.get("sellerProductItemKey"),
                "name": product_data.get("sellerProductName"),
                "price": product_data.get("originalPrice"),
                "sale_price": product_data.get("salePrice"),
                "status": product_data.get("status"),
                "category_id": product_data.get("categoryId"),
                "brand": product_data.get("brand"),
                "manufacturer": product_data.get("manufacturer"),
                "coupang_product_data": json.dumps(product_data, ensure_ascii=False),
                "last_updated": datetime.now()
            }

            if existing_product:
                # 업데이트
                await self.db.execute(
                    update(Product).where(
                        and_(
                            Product.supplier_id == supplier_id,
                            Product.coupang_product_id == seller_product_id
                        )
                    ).values(**product_info)
                )
            else:
                # 새 상품 생성
                new_product = Product(**product_info)
                self.db.add(new_product)

            await self.db.commit()

        except Exception as e:
            logger.error(f"쿠팡 상품 저장 실패 {seller_product_id}: {e}")

    async def _update_product_summary(self, supplier_id: int, seller_product_id: str, summary_data: Dict[str, Any]):
        """쿠팡 상품 요약 정보를 데이터베이스에 업데이트"""
        try:
            # 기존 상품 확인
            existing_result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.coupang_product_id == seller_product_id
                    )
                )
            )
            existing_product = existing_result.scalar_one_or_none()

            if existing_product:
                # 요약 정보 업데이트
                update_data = {
                    "coupang_summary_data": json.dumps(summary_data, ensure_ascii=False),
                    "last_updated": datetime.now()
                }

                await self.db.execute(
                    update(Product).where(
                        and_(
                            Product.supplier_id == supplier_id,
                            Product.coupang_product_id == seller_product_id
                        )
                    ).values(**update_data)
                )
                await self.db.commit()
                logger.info(f"쿠팡 상품 요약 정보 업데이트 완료: {seller_product_id}")
            else:
                logger.warning(f"업데이트할 쿠팡 상품을 찾을 수 없음: {seller_product_id}")

        except Exception as e:
            logger.error(f"쿠팡 상품 요약 정보 업데이트 실패 {seller_product_id}: {e}")

    async def _update_item_quantity_in_db(self, supplier_id: int, seller_product_id: str, item_id: str, quantity: int):
        """상품 아이템 수량을 데이터베이스에서 업데이트"""
        try:
            # 상품 옵션 정보에서 해당 아이템의 수량을 업데이트
            result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.coupang_product_id == seller_product_id
                    )
                )
            )
            product = result.scalar_one_or_none()

            if product and product.options:
                try:
                    options = json.loads(product.options)
                    for option in options:
                        if option.get("id") == item_id:
                            option["quantity"] = quantity
                            break

                    # 업데이트된 옵션 정보 저장
                    await self.db.execute(
                        update(Product).where(
                            and_(
                                Product.supplier_id == supplier_id,
                                Product.coupang_product_id == seller_product_id
                            )
                        ).values(
                            options=json.dumps(options),
                            last_updated=datetime.now()
                        )
                    )
                    await self.db.commit()
                    logger.info(f"상품 아이템 수량 업데이트 완료: {item_id}")
                except json.JSONDecodeError:
                    logger.warning(f"상품 옵션 정보 파싱 실패: {seller_product_id}")

        except Exception as e:
            logger.error(f"상품 아이템 수량 DB 업데이트 실패 {item_id}: {e}")

    async def _update_item_price_in_db(self, supplier_id: int, seller_product_id: str, item_id: str, price: int, sale_price: Optional[int] = None):
        """상품 아이템 가격을 데이터베이스에서 업데이트"""
        try:
            # 상품 옵션 정보에서 해당 아이템의 가격을 업데이트
            result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.coupang_product_id == seller_product_id
                    )
                )
            )
            product = result.scalar_one_or_none()

            if product and product.options:
                try:
                    options = json.loads(product.options)
                    for option in options:
                        if option.get("id") == item_id:
                            option["price"] = price
                            if sale_price is not None:
                                option["salePrice"] = sale_price
                            break

                    # 업데이트된 옵션 정보 저장
                    await self.db.execute(
                        update(Product).where(
                            and_(
                                Product.supplier_id == supplier_id,
                                Product.coupang_product_id == seller_product_id
                            )
                        ).values(
                            options=json.dumps(options),
                            last_updated=datetime.now()
                        )
                    )
                    await self.db.commit()
                    logger.info(f"상품 아이템 가격 업데이트 완료: {item_id}")
                except json.JSONDecodeError:
                    logger.warning(f"상품 옵션 정보 파싱 실패: {seller_product_id}")

        except Exception as e:
            logger.error(f"상품 아이템 가격 DB 업데이트 실패 {item_id}: {e}")

    async def _update_item_status_in_db(self, supplier_id: int, seller_product_id: str, item_id: str, status: str):
        """상품 아이템 상태를 데이터베이스에서 업데이트"""
        try:
            # 상품 옵션 정보에서 해당 아이템의 상태를 업데이트
            result = await self.db.execute(
                select(Product).where(
                    and_(
                        Product.supplier_id == supplier_id,
                        Product.coupang_product_id == seller_product_id
                    )
                )
            )
            product = result.scalar_one_or_none()

            if product and product.options:
                try:
                    options = json.loads(product.options)
                    for option in options:
                        if option.get("id") == item_id:
                            option["status"] = status
                            break

                    # 업데이트된 옵션 정보 저장
                    await self.db.execute(
                        update(Product).where(
                            and_(
                                Product.supplier_id == supplier_id,
                                Product.coupang_product_id == seller_product_id
                            )
                        ).values(
                            options=json.dumps(options),
                            last_updated=datetime.now()
                        )
                    )
                    await self.db.commit()
                    logger.info(f"상품 아이템 상태 업데이트 완료: {item_id}")
                except json.JSONDecodeError:
                    logger.warning(f"상품 옵션 정보 파싱 실패: {seller_product_id}")

        except Exception as e:
            logger.error(f"상품 아이템 상태 DB 업데이트 실패 {item_id}: {e}")

