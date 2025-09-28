"""주문 수집 라우트 (드랍십핑 자동화)"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from src.app.di import get_collect_orders_usecase
from src.core.usecases.collect_orders import CollectOrdersUseCase
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/collect")
async def collect_external_orders(
    external_orders: List[Dict[str, Any]],
    supplier_id: str,
    account_id: str,
    usecase: CollectOrdersUseCase = Depends(get_collect_orders_usecase)
):
    """외부몰 주문을 OwnerClan에 수집 (드랍십핑 자동화)"""
    try:
        # 요청 데이터 검증
        if not external_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="주문 데이터가 비어있습니다"
            )

        result = await usecase.execute(
            supplier_id=supplier_id,
            account_id=account_id,
            external_orders=external_orders
        )

        if result.is_success():
            return {
                "success": True,
                "message": f"주문 수집 완료: {len(result.get_value())}개",
                "collected_orders": result.get_value()
            }
        else:
            return {
                "success": False,
                "message": result.get_error(),
                "collected_orders": result.get_value() or []
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 수집 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/collect/{external_order_id}")
async def collect_single_order(
    external_order_id: str,
    order_data: Dict[str, Any],
    supplier_id: str,
    account_id: str,
    usecase: CollectOrdersUseCase = Depends(get_collect_orders_usecase)
):
    """단일 외부 주문을 OwnerClan에 등록 (드랍십핑 자동화)"""
    try:
        # 단일 주문 데이터를 리스트로 변환
        external_orders = [{
            "external_order_id": external_order_id,
            **order_data
        }]

        result = await usecase.execute(
            supplier_id=supplier_id,
            account_id=account_id,
            external_orders=external_orders
        )

        if result.is_success():
            collected_orders = result.get_value()
            if collected_orders:
                return {
                    "success": True,
                    "message": "주문 등록 완료",
                    "collected_order": collected_orders[0]
                }
            else:
                return {
                    "success": False,
                    "message": "주문 등록 실패",
                    "collected_order": None
                }
        else:
            return {
                "success": False,
                "message": result.get_error(),
                "collected_order": None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"단일 주문 수집 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/test-connection")
async def test_ownerclan_connection(
    supplier_id: str,
    account_id: str
):
    """OwnerClan 연결 테스트"""
    try:
        # TODO: 실제 연결 테스트 구현
        # 현재는 간단한 응답
        return {
            "success": True,
            "message": "OwnerClan 연결 성공",
            "supplier_id": supplier_id,
            "account_id": account_id
        }

    except Exception as e:
        logger.error(f"OwnerClan 연결 테스트 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"연결 테스트 실패: {str(e)}"
        )
