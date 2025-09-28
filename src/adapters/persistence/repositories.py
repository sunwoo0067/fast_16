"""리포지토리 구현체"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_, or_, func

from src.core.ports.repo_port import RepositoryPort, Item, SupplierAccount, MarketAccount, ProductSyncHistory
from src.core.entities.account import AccountType, TokenInfo, ApiCredentials
from src.core.entities.sync_history import SyncType, SyncStatus, SyncResult
from src.adapters.persistence.models import Product, SupplierAccount as SupplierAccountModel, MarketAccount as MarketAccountModel, SyncHistory as SyncHistoryModel
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ItemRepository(RepositoryPort):
    """상품 리포지토리 구현체"""

    def __init__(self, db_session: AsyncSession = None):
        self.db_session = db_session

    async def save_item(self, item: Item) -> None:
        """상품 저장"""
        try:
            # 도메인 엔티티를 SQLAlchemy 모델로 변환
            product_data = {
                'id': item.id,
                'supplier_id': item.supplier_id,
                'item_key': item.id,
                'title': item.title,
                'brand': item.brand,
                'category_id': item.category_id,
                'description': item.description,
                'images': json.dumps(item.images),
                'options': json.dumps([opt.__dict__ for opt in item.options]),
                'is_active': item.is_active,
                'price_data': json.dumps({
                    'original_price': item.price.original_price,
                    'sale_price': item.price.sale_price,
                    'margin_rate': item.price.margin_rate,
                    'final_price': item.price.get_final_price()
                }),
                'stock_quantity': item.stock_quantity,
                'max_stock_quantity': item.max_stock_quantity,
                'supplier_product_id': None,  # TODO: 매핑 필요
                'supplier_name': "",  # TODO: 매핑 필요
                'estimated_shipping_days': item.estimated_shipping_days,
                'sync_status': 'synced',
                'hash_key': item.hash_key,
                'normalized_at': item.normalized_at
            }

            # 중복 체크
            existing = await self.db_session.get(Product, item.id)
            if existing:
                # 업데이트
                for key, value in product_data.items():
                    setattr(existing, key, value)
            else:
                # 생성
                new_product = Product(**product_data)
                self.db_session.add(new_product)

            await self.db_session.commit()
            logger.info(f"상품 저장 완료: {item.id}")

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"상품 저장 실패: {e}")
            raise

    async def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """상품 ID로 조회"""
        try:
            result = await self.db_session.get(Product, item_id)
            if not result:
                return None

            return self._map_product_to_item(result)

        except Exception as e:
            logger.error(f"상품 조회 실패: {e}")
            return None

    async def get_items_by_supplier(
        self,
        supplier_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Item]:
        """공급사별 상품 목록 조회"""
        try:
            query = select(Product).where(
                Product.supplier_id == supplier_id,
                Product.is_active == True
            ).order_by(Product.created_at.desc()).limit(limit).offset(offset)

            result = await self.db_session.execute(query)
            products = result.scalars().all()

            return [self._map_product_to_item(product) for product in products]

        except Exception as e:
            logger.error(f"공급사 상품 목록 조회 실패: {e}")
            return []

    async def find_item_by_hash(self, hash_key: str) -> Optional[Item]:
        """해시로 상품 중복 체크"""
        try:
            query = select(Product).where(Product.hash_key == hash_key)
            result = await self.db_session.execute(query)
            product = result.scalar_one_or_none()

            if product:
                return self._map_product_to_item(product)
            return None

        except Exception as e:
            logger.error(f"상품 해시 조회 실패: {e}")
            return None

    async def update_item(self, item_id: str, updates: Dict[str, Any]) -> None:
        """상품 업데이트"""
        try:
            query = update(Product).where(Product.id == item_id).values(**updates)
            await self.db_session.execute(query)
            await self.db_session.commit()
            logger.info(f"상품 업데이트 완료: {item_id}")

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"상품 업데이트 실패: {e}")
            raise

    async def save_supplier_account(self, account: SupplierAccount) -> None:
        """공급사 계정 저장"""
        try:
            account_data = {
                'supplier_id': int(account.id),  # TODO: 실제 ID 매핑
                'account_name': account.account_name,
                'username': account.username,
                'password_encrypted': account.password_encrypted,
                'is_active': account.is_active,
                'last_used_at': account.last_used_at,
                'usage_count': account.usage_count,
                'total_requests': account.total_requests,
                'successful_requests': account.successful_requests,
                'failed_requests': account.failed_requests,
                'default_margin_rate': account.default_margin_rate,
                'sync_enabled': account.sync_enabled,
                'last_sync_at': account.last_sync_at
            }

            # 토큰 정보
            if account.token_info:
                account_data.update({
                    'access_token': account.token_info.access_token,
                    'refresh_token': account.token_info.refresh_token,
                    'token_expires_at': account.token_info.expires_at
                })

            # API 인증 정보
            if account.api_credentials:
                account_data.update({
                    'coupang_access_key': account.api_credentials.access_key,
                    'coupang_secret_key': account.api_credentials.secret_key,
                    'coupang_vendor_id': account.api_credentials.vendor_id
                })

            # 중복 체크
            existing = await self.db_session.get(SupplierAccountModel, account.id)
            if existing:
                for key, value in account_data.items():
                    setattr(existing, key, value)
            else:
                new_account = SupplierAccountModel(**account_data)
                self.db_session.add(new_account)

            await self.db_session.commit()
            logger.info(f"공급사 계정 저장 완료: {account.account_name}")

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"공급사 계정 저장 실패: {e}")
            raise

    async def get_supplier_account(self, supplier_id: str, account_name: str) -> Optional[SupplierAccount]:
        """공급사 계정 조회"""
        try:
            query = select(SupplierAccountModel).where(
                SupplierAccountModel.supplier_id == int(supplier_id),
                SupplierAccountModel.account_name == account_name
            )
            result = await self.db_session.execute(query)
            account_model = result.scalar_one_or_none()

            if account_model:
                return self._map_supplier_account_model_to_entity(account_model)
            return None

        except Exception as e:
            logger.error(f"공급사 계정 조회 실패: {e}")
            return None

    async def save_market_account(self, account: MarketAccount) -> None:
        """마켓 계정 저장"""
        try:
            account_data = {
                'market_type': account.id,  # TODO: 실제 마켓 타입 매핑
                'account_name': account.account_name,
                'api_key': account.api_key,
                'api_secret': account.api_secret,
                'vendor_id': account.vendor_id,
                'is_active': account.is_active,
                'last_used_at': account.last_used_at,
                'usage_count': account.usage_count,
                'total_requests': account.total_requests,
                'successful_requests': account.successful_requests,
                'failed_requests': account.failed_requests,
                'default_margin_rate': account.default_margin_rate,
                'sync_enabled': account.sync_enabled,
                'last_sync_at': account.last_sync_at
            }

            # 토큰 정보
            if account.token_info:
                account_data.update({
                    'access_token': account.token_info.access_token,
                    'refresh_token': account.token_info.refresh_token,
                    'token_expires_at': account.token_info.expires_at
                })

            # 중복 체크
            existing = await self.db_session.get(MarketAccountModel, account.id)
            if existing:
                for key, value in account_data.items():
                    setattr(existing, key, value)
            else:
                new_account = MarketAccountModel(**account_data)
                self.db_session.add(new_account)

            await self.db_session.commit()
            logger.info(f"마켓 계정 저장 완료: {account.account_name}")

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"마켓 계정 저장 실패: {e}")
            raise

    async def get_market_account(self, market_type: str, account_name: str) -> Optional[MarketAccount]:
        """마켓 계정 조회"""
        try:
            query = select(MarketAccountModel).where(
                MarketAccountModel.market_type == market_type,
                MarketAccountModel.account_name == account_name
            )
            result = await self.db_session.execute(query)
            account_model = result.scalar_one_or_none()

            if account_model:
                return self._map_market_account_model_to_entity(account_model)
            return None

        except Exception as e:
            logger.error(f"마켓 계정 조회 실패: {e}")
            return None

    async def save_sync_history(self, history: ProductSyncHistory) -> None:
        """동기화 이력 저장"""
        try:
            history_data = {
                'id': history.id,
                'item_id': history.item_id,
                'supplier_id': history.supplier_id,
                'market_type': history.market_type,
                'sync_type': history.sync_type.value,
                'status': history.status.value,
                'result_data': json.dumps({
                    'success_count': history.result.success_count if history.result else 0,
                    'failure_count': history.result.failure_count if history.result else 0,
                    'total_count': history.result.total_count if history.result else 0,
                    'success_rate': history.result.get_success_rate() if history.result else 0,
                    'errors': history.result.errors if history.result else {}
                }) if history.result else None,
                'details': json.dumps(history.details) if history.details else None,
                'error_message': history.error_message,
                'started_at': history.started_at,
                'completed_at': history.completed_at,
                'duration_seconds': history.duration_seconds,
                'retry_count': history.retry_count,
                'max_retries': history.max_retries
            }

            # 중복 체크
            existing = await self.db_session.get(SyncHistoryModel, history.id)
            if existing:
                for key, value in history_data.items():
                    setattr(existing, key, value)
            else:
                new_history = SyncHistoryModel(**history_data)
                self.db_session.add(new_history)

            await self.db_session.commit()
            logger.info(f"동기화 이력 저장 완료: {history.id}")

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"동기화 이력 저장 실패: {e}")
            raise

    async def get_sync_history(
        self,
        item_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        sync_type: Optional[str] = None,
        limit: int = 50
    ) -> List[ProductSyncHistory]:
        """동기화 이력 조회"""
        try:
            query = select(SyncHistoryModel)

            if item_id:
                query = query.where(SyncHistoryModel.item_id == item_id)
            if supplier_id:
                query = query.where(SyncHistoryModel.supplier_id == supplier_id)
            if sync_type:
                query = query.where(SyncHistoryModel.sync_type == sync_type)

            query = query.order_by(SyncHistoryModel.created_at.desc()).limit(limit)
            result = await self.db_session.execute(query)
            histories = result.scalars().all()

            return [self._map_sync_history_model_to_entity(history) for history in histories]

        except Exception as e:
            logger.error(f"동기화 이력 조회 실패: {e}")
            return []

    def _map_product_to_item(self, product: Product) -> Item:
        """SQLAlchemy Product를 도메인 Item으로 변환"""
        # 가격 데이터 파싱
        price_data = json.loads(product.price_data) if product.price_data else {}

        # 옵션 데이터 파싱
        options_data = json.loads(product.options) if product.options else []
        options = [
            ItemOption(
                name=opt.get('name', ''),
                value=opt.get('value', ''),
                price_adjustment=opt.get('price_adjustment', 0),
                stock_quantity=opt.get('stock_quantity', 0)
            )
            for opt in options_data
        ]

        # 이미지 데이터 파싱
        images = json.loads(product.images) if product.images else []

        return Item(
            id=product.id,
            title=product.title,
            brand=product.brand or "",
            price=PricePolicy(
                original_price=price_data.get('original_price', 0),
                sale_price=price_data.get('sale_price'),
                margin_rate=price_data.get('margin_rate', 0.3)
            ),
            options=options,
            images=images,
            category_id=product.category_id or "",
            supplier_id=product.supplier_id,
            description=product.description,
            estimated_shipping_days=product.estimated_shipping_days or 7,
            stock_quantity=product.stock_quantity or 0,
            max_stock_quantity=product.max_stock_quantity,
            is_active=product.is_active,
            normalized_at=product.normalized_at,
            hash_key=product.hash_key
        )

    def _map_supplier_account_model_to_entity(self, account_model: SupplierAccountModel) -> SupplierAccount:
        """SQLAlchemy SupplierAccount를 도메인 엔티티로 변환"""
        return SupplierAccount(
            id=str(account_model.id),
            account_type=AccountType.SUPPLIER,
            account_name=account_model.account_name,
            username=account_model.username,
            password_encrypted=account_model.password_encrypted,
            token_info=TokenInfo(
                access_token=account_model.access_token or "",
                refresh_token=account_model.refresh_token,
                expires_at=account_model.token_expires_at
            ) if account_model.access_token else None,
            api_credentials=ApiCredentials(
                api_key=account_model.api_key,
                api_secret=account_model.api_secret,
                access_key=account_model.coupang_access_key,
                secret_key=account_model.coupang_secret_key,
                vendor_id=account_model.coupang_vendor_id
            ),
            status=AccountStatus.ACTIVE if account_model.is_active else AccountStatus.INACTIVE,
            is_active=account_model.is_active,
            last_used_at=account_model.last_used_at,
            usage_count=account_model.usage_count,
            total_requests=account_model.total_requests,
            successful_requests=account_model.successful_requests,
            failed_requests=account_model.failed_requests,
            default_margin_rate=account_model.default_margin_rate or 0.3,
            sync_enabled=account_model.sync_enabled,
            last_sync_at=account_model.last_sync_at
        )

    def _map_market_account_model_to_entity(self, account_model: MarketAccountModel) -> MarketAccount:
        """SQLAlchemy MarketAccount를 도메인 엔티티로 변환"""
        return MarketAccount(
            id=account_model.market_type,  # TODO: 실제 ID 매핑
            account_type=AccountType.MARKET,
            account_name=account_model.account_name,
            username="",  # 마켓 계정은 username이 없음
            password_encrypted="",  # 마켓 계정은 password가 없음
            api_credentials=ApiCredentials(
                api_key=account_model.api_key,
                api_secret=account_model.api_secret,
                vendor_id=account_model.vendor_id
            ),
            token_info=TokenInfo(
                access_token=account_model.access_token or "",
                refresh_token=account_model.refresh_token,
                expires_at=account_model.token_expires_at
            ) if account_model.access_token else None,
            status=AccountStatus.ACTIVE if account_model.is_active else AccountStatus.INACTIVE,
            is_active=account_model.is_active,
            last_used_at=account_model.last_used_at,
            usage_count=account_model.usage_count,
            total_requests=account_model.total_requests,
            successful_requests=account_model.successful_requests,
            failed_requests=account_model.failed_requests,
            default_margin_rate=account_model.default_margin_rate or 0.3,
            sync_enabled=account_model.sync_enabled,
            last_sync_at=account_model.last_sync_at
        )

    def _map_sync_history_model_to_entity(self, history_model: SyncHistoryModel) -> ProductSyncHistory:
        """SQLAlchemy SyncHistory를 도메인 엔티티로 변환"""
        # 결과 데이터 파싱
        result_data = json.loads(history_model.result_data) if history_model.result_data else {}
        result = SyncResult(
            success_count=result_data.get('success_count', 0),
            failure_count=result_data.get('failure_count', 0),
            total_count=result_data.get('total_count', 0),
            errors=result_data.get('errors', {})
        )

        return ProductSyncHistory(
            id=history_model.id,
            item_id=history_model.item_id,
            supplier_id=history_model.supplier_id,
            market_type=history_model.market_type,
            sync_type=SyncType(history_model.sync_type),
            status=SyncStatus(history_model.status),
            result=result,
            details=json.loads(history_model.details) if history_model.details else None,
            error_message=history_model.error_message,
            started_at=history_model.started_at,
            completed_at=history_model.completed_at,
            duration_seconds=history_model.duration_seconds,
            retry_count=history_model.retry_count,
            max_retries=history_model.max_retries
        )
