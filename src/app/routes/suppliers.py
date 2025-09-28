"""공급사 관련 라우트 (헥사고날 아키텍처)"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.app.di import get_supplier_service
from src.services.supplier_service import SupplierService
from src.presentation.schemas.suppliers import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
    SupplierResponse,
    SupplierAccountCreateRequest,
    SupplierAccountUpdateRequest,
    SupplierAccountResponse,
    SupplierAccountListResponse,
    SupplierTestRequest,
    SupplierTestResponse
)
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    request: SupplierCreateRequest,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 생성 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.create_supplier(
            name=request.name,
            description=request.description,
            api_key=request.api_key,
            api_secret=request.api_secret,
            base_url=request.base_url
        )

        if result.is_success():
            supplier = result.get_value()
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
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 생성 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=List[SupplierResponse])
async def get_suppliers(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 목록 조회 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.get_all_suppliers(
            skip=skip,
            limit=limit,
            is_active=is_active if is_active is not None else True
        )

        if result.is_success():
            suppliers = result.get_value()
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
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 상세 조회 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.get_supplier_by_id(supplier_id)

        if result.is_success():
            supplier = result.get_value()
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="공급사를 찾을 수 없습니다"
                )

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
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    request: SupplierUpdateRequest,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 수정 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.update_supplier(
            supplier_id=supplier_id,
            name=request.name,
            description=request.description,
            api_key=request.api_key,
            api_secret=request.api_secret,
            base_url=request.base_url,
            is_active=request.is_active
        )

        if result.is_success():
            supplier = result.get_value()
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
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 수정 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 삭제 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.delete_supplier(supplier_id)

        if result.is_success():
            return {"message": "공급사가 삭제되었습니다"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 삭제 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{supplier_id}/accounts", response_model=SupplierAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_account(
    supplier_id: int,
    request: SupplierAccountCreateRequest,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 계정 생성 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.create_supplier_account(
            supplier_id=supplier_id,
            account_name=request.account_name,
            username=request.username,
            password=request.password,
            default_margin_rate=request.default_margin_rate,
            sync_enabled=request.sync_enabled
        )

        if result.is_success():
            account = result.get_value()
            return SupplierAccountResponse(
                id=account.id,
                supplier_id=account.supplier_id,
                account_name=account.account_name,
                username=account.username,
                is_active=account.is_active,
                usage_count=account.usage_count,
                total_requests=account.total_requests,
                successful_requests=account.successful_requests,
                failed_requests=account.failed_requests,
                success_rate=account.get_success_rate(),
                default_margin_rate=account.default_margin_rate,
                sync_enabled=account.sync_enabled,
                last_used_at=account.last_used_at,
                last_sync_at=account.last_sync_at,
                created_at=account.created_at,
                updated_at=account.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 계정 생성 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{supplier_id}/accounts", response_model=SupplierAccountListResponse)
async def get_supplier_accounts(
    supplier_id: int,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 계정 목록 조회 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.get_supplier_accounts(
            supplier_id=supplier_id,
            skip=skip,
            limit=limit,
            is_active=is_active
        )

        if result.is_success():
            accounts, total = result.get_value()
            return SupplierAccountListResponse(
                accounts=[
                    SupplierAccountResponse(
                        id=account.id,
                        supplier_id=account.supplier_id,
                        account_name=account.account_name,
                        username=account.username,
                        is_active=account.is_active,
                        usage_count=account.usage_count,
                        total_requests=account.total_requests,
                        successful_requests=account.successful_requests,
                        failed_requests=account.failed_requests,
                        success_rate=account.get_success_rate(),
                        default_margin_rate=account.default_margin_rate,
                        sync_enabled=account.sync_enabled,
                        last_used_at=account.last_used_at,
                        last_sync_at=account.last_sync_at,
                        created_at=account.created_at,
                        updated_at=account.updated_at
                    )
                    for account in accounts
                ],
                total=total,
                page=skip // limit + 1,
                page_size=limit
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공급사 계정 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/test-connection", response_model=SupplierTestResponse)
async def test_supplier_connection(
    request: SupplierTestRequest,
    supplier_service: SupplierService = Depends(get_supplier_service)
):
    """공급사 연결 테스트 (헥사고날 아키텍처)"""
    try:
        result = await supplier_service.test_supplier_connection(
            supplier_id=request.supplier_id,
            account_name=request.account_name
        )

        return SupplierTestResponse(
            success=result.is_success(),
            message=result.get_error() if result.is_failure() else "연결 성공",
            account_info=result.get_value() if result.is_success() else None
        )

    except Exception as e:
        logger.error(f"공급사 연결 테스트 중 오류: {e}")
        return SupplierTestResponse(
            success=False,
            message=str(e)
        )
