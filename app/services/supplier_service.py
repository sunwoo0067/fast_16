from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.database import Supplier, SupplierAccount
from app.core.logging import get_logger, LoggerMixin
from app.core.exceptions import SupplierError

logger = get_logger(__name__)

class SupplierService(LoggerMixin):
    """공급사 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_suppliers(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[Supplier]:
        """모든 공급사 조회"""
        query = select(Supplier)

        # 기본적으로 활성화된 공급사만 조회
        if is_active is None:
            is_active = True
        query = query.where(Supplier.is_active == is_active)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
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

    async def create_supplier(
        self,
        name: str,
        description: str = None,
        api_key: str = None,
        api_secret: str = None,
        base_url: str = None
    ) -> Supplier:
        """공급사 생성"""
        # 중복 이름 체크
        existing = await self.db.execute(
            select(Supplier).where(Supplier.name == name)
        )
        if existing.scalar_one_or_none():
            raise SupplierError(f"이미 존재하는 공급사 이름입니다: {name}")

        new_supplier = Supplier(
            name=name,
            description=description,
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            is_active=True
        )
        self.db.add(new_supplier)
        await self.db.commit()
        await self.db.refresh(new_supplier)

        self.logger.info(f"공급사 생성 완료: {name} (ID: {new_supplier.id})")
        return new_supplier

    async def update_supplier(
        self,
        supplier_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Supplier]:
        """공급사 정보 수정"""
        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return None

        # 업데이트할 필드들
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if description is not None:
            update_data['description'] = description
        if api_key is not None:
            update_data['api_key'] = api_key
        if api_secret is not None:
            update_data['api_secret'] = api_secret
        if base_url is not None:
            update_data['base_url'] = base_url
        if is_active is not None:
            update_data['is_active'] = is_active

        update_data['updated_at'] = datetime.now()

        # 업데이트 실행
        await self.db.execute(
            update(Supplier).where(Supplier.id == supplier_id).values(**update_data)
        )
        await self.db.commit()

        # 업데이트된 공급사 조회
        await self.db.refresh(supplier)
        self.logger.info(f"공급사 수정 완료: {supplier.name} (ID: {supplier_id})")
        return supplier

    async def delete_supplier(self, supplier_id: int) -> bool:
        """공급사 삭제 (논리적 삭제)"""
        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return False

        # 논리적 삭제 (is_active = False)
        await self.db.execute(
            update(Supplier).where(Supplier.id == supplier_id).values(is_active=False)
        )
        await self.db.commit()

        self.logger.info(f"공급사 삭제 완료: {supplier.name} (ID: {supplier_id})")
        return True

    async def get_supplier_accounts(self, supplier_id: int) -> Optional[List[SupplierAccount]]:
        """공급사의 계정 목록 조회"""
        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return None

        result = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        return result.scalars().all()

    async def create_supplier_account(
        self,
        supplier_id: int,
        account_name: str,
        username: str,
        password: str,
        default_margin_rate: float = 0.3,
        is_active: bool = True,
        sync_enabled: bool = True
    ) -> SupplierAccount:
        """공급사 계정 생성"""
        # 중복 계정명 체크
        existing = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.account_name == account_name
                )
            )
        )
        if existing.scalar_one_or_none():
            raise SupplierError(f"이미 존재하는 계정명입니다: {account_name}")

        new_account = SupplierAccount(
            supplier_id=supplier_id,
            account_name=account_name,
            username=username,
            password_encrypted=password,  # 실제 환경에서는 해시화 필요
            default_margin_rate=default_margin_rate,
            is_active=is_active,
            sync_enabled=sync_enabled,
            usage_count=0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0
        )
        self.db.add(new_account)
        await self.db.commit()
        await self.db.refresh(new_account)

        self.logger.info(f"공급사 계정 생성 완료: {account_name} (ID: {new_account.id})")
        return new_account

    async def update_supplier_account(
        self,
        supplier_id: int,
        account_id: int,
        account_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        default_margin_rate: Optional[float] = None,
        is_active: Optional[bool] = None,
        sync_enabled: Optional[bool] = None
    ) -> Optional[SupplierAccount]:
        """공급사 계정 정보 수정"""
        # 계정 존재 확인
        result = await self.db.execute(
            select(SupplierAccount).where(
                and_(
                    SupplierAccount.id == account_id,
                    SupplierAccount.supplier_id == supplier_id,
                    SupplierAccount.is_active == True
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return None

        # 업데이트할 필드들
        update_data = {}
        if account_name is not None:
            update_data['account_name'] = account_name
        if username is not None:
            update_data['username'] = username
        if password is not None:
            update_data['password_encrypted'] = password  # 실제 환경에서는 해시화 필요
        if default_margin_rate is not None:
            update_data['default_margin_rate'] = default_margin_rate
        if is_active is not None:
            update_data['is_active'] = is_active
        if sync_enabled is not None:
            update_data['sync_enabled'] = sync_enabled

        update_data['updated_at'] = datetime.now()

        # 업데이트 실행
        await self.db.execute(
            update(SupplierAccount).where(SupplierAccount.id == account_id).values(**update_data)
        )
        await self.db.commit()

        # 업데이트된 계정 조회
        await self.db.refresh(account)
        self.logger.info(f"공급사 계정 수정 완료: {account.account_name} (ID: {account_id})")
        return account

