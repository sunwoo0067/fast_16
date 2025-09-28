from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.models.database import get_db, Supplier, SupplierAccount
from app.services.supplier_service import SupplierService
from app.core.exceptions import create_http_exception, SupplierError
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Pydantic 모델들
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None

class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None

class SupplierResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    api_key: Optional[str]
    base_url: Optional[str]
    created_at: datetime
    updated_at: datetime

@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_data: SupplierCreate,
    db: AsyncSession = Depends(get_db)
):
    """공급사 생성"""
    try:
        logger.info(f"공급사 생성 요청: {supplier_data.name}")
        supplier_service = SupplierService(db)

        supplier = await supplier_service.create_supplier(
            name=supplier_data.name,
            description=supplier_data.description,
            api_key=supplier_data.api_key,
            api_secret=supplier_data.api_secret,
            base_url=supplier_data.base_url
        )

        logger.info(f"공급사 생성 완료: ID={supplier.id}")
        return SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            description=supplier.description,
            is_active=supplier.is_active,
            api_key=supplier.api_key,
            base_url=supplier.base_url,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at
        )

    except Exception as e:
        logger.error(f"공급사 생성 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 생성 실패: {str(e)}"))

@router.get("/", response_model=List[SupplierResponse])
async def get_suppliers(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """공급사 목록 조회"""
    try:
        supplier_service = SupplierService(db)
        suppliers = await supplier_service.get_all_suppliers(
            skip=skip,
            limit=limit,
            is_active=is_active if is_active is not None else True
        )

        return [
            SupplierResponse(
                id=supplier.id,
                name=supplier.name,
                description=supplier.description,
                is_active=supplier.is_active,
                api_key=supplier.api_key,
                base_url=supplier.base_url,
                created_at=supplier.created_at,
                updated_at=supplier.updated_at
            )
            for supplier in suppliers
        ]

    except Exception as e:
        logger.error(f"공급사 목록 조회 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 목록 조회 실패: {str(e)}"))

@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db)
):
    """특정 공급사 조회"""
    try:
        supplier_service = SupplierService(db)
        supplier = await supplier_service.get_supplier_by_id(supplier_id)

        if not supplier:
            raise SupplierError(f"공급사를 찾을 수 없습니다 (ID: {supplier_id})")

        return SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            description=supplier.description,
            is_active=supplier.is_active,
            api_key=supplier.api_key,
            base_url=supplier.base_url,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at
        )

    except SupplierError:
        raise
    except Exception as e:
        logger.error(f"공급사 조회 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 조회 실패: {str(e)}"))

@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    db: AsyncSession = Depends(get_db)
):
    """공급사 정보 수정"""
    try:
        logger.info(f"공급사 수정 요청: ID={supplier_id}")
        supplier_service = SupplierService(db)

        supplier = await supplier_service.update_supplier(
            supplier_id=supplier_id,
            name=supplier_data.name,
            description=supplier_data.description,
            api_key=supplier_data.api_key,
            api_secret=supplier_data.api_secret,
            base_url=supplier_data.base_url,
            is_active=supplier_data.is_active
        )

        if not supplier:
            raise SupplierError(f"공급사를 찾을 수 없습니다 (ID: {supplier_id})")

        logger.info(f"공급사 수정 완료: ID={supplier_id}")
        return SupplierResponse(
            id=supplier.id,
            name=supplier.name,
            description=supplier.description,
            is_active=supplier.is_active,
            api_key=supplier.api_key,
            base_url=supplier.base_url,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at
        )

    except SupplierError:
        raise
    except Exception as e:
        logger.error(f"공급사 수정 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 수정 실패: {str(e)}"))

@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db)
):
    """공급사 삭제"""
    try:
        logger.info(f"공급사 삭제 요청: ID={supplier_id}")
        supplier_service = SupplierService(db)

        deleted = await supplier_service.delete_supplier(supplier_id)
        if not deleted:
            raise SupplierError(f"공급사를 찾을 수 없습니다 (ID: {supplier_id})")

        logger.info(f"공급사 삭제 완료: ID={supplier_id}")
        return {"message": "공급사가 삭제되었습니다"}

    except SupplierError:
        raise
    except Exception as e:
        logger.error(f"공급사 삭제 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 삭제 실패: {str(e)}"))

@router.get("/{supplier_id}/accounts")
async def get_supplier_accounts(
    supplier_id: int,
    db: AsyncSession = Depends(get_db)
):
    """공급사의 계정 목록 조회"""
    try:
        supplier_service = SupplierService(db)
        accounts = await supplier_service.get_supplier_accounts(supplier_id)

        if accounts is None:
            raise SupplierError(f"공급사를 찾을 수 없습니다 (ID: {supplier_id})")

        return {
            "supplier_id": supplier_id,
            "accounts": [
                {
                    "id": account.id,
                    "account_id": account.account_id,
                    "is_active": account.is_active,
                    "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
                    "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
                    "usage_count": account.usage_count,
                    "default_margin_rate": account.default_margin_rate,
                    "sync_enabled": account.sync_enabled,
                    "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
                    "coupang_vendor_id": account.coupang_vendor_id
                }
                for account in accounts
            ]
        }

    except SupplierError:
        raise
    except Exception as e:
        logger.error(f"공급사 계정 목록 조회 실패: {e}")
        raise create_http_exception(SupplierError(f"공급사 계정 목록 조회 실패: {str(e)}"))

