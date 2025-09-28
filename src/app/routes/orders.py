"""주문 관련 라우트 (헥사고날 아키텍처)"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.app.di import get_order_service
from src.services.order_service import OrderService
from src.presentation.schemas.orders import (
    OrderCreateRequest,
    OrderUpdateRequest,
    OrderResponse,
    OrderListResponse,
    OrderStatusUpdateRequest,
    ShippingUpdateRequest,
    OrderCancellationRequest,
    OrderStatsResponse
)
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderCreateRequest,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 생성 (헥사고날 아키텍처)"""
    try:
        result = await order_service.create_order(
            supplier_id=request.supplier_id,
            supplier_account_id=request.supplier_account_id,
            order_key=request.order_key,
            items=request.items,
            shipping_fee=request.shipping_fee,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            shipping_address=request.shipping_address,
            orderer_note=request.orderer_note
        )

        if result.is_success():
            order = result.get_value()
            return OrderResponse(
                id=order.id,
                supplier_id=order.supplier_id,
                supplier_account_id=order.supplier_account_id,
                order_key=order.order_key,
                status=order.status.value,
                payment_status=order.payment_status.value,
                items=[
                    {
                        'id': item.id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price,
                        'options': item.options
                    }
                    for item in order.items
                ],
                subtotal=order.subtotal,
                shipping_fee=order.shipping_fee,
                total_amount=order.total_amount,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                shipping_address=order.shipping_address,
                shipping_info={
                    'tracking_number': order.shipping_info.tracking_number,
                    'shipping_company': order.shipping_info.shipping_company,
                    'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                    'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                    'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                },
                orderer_note=order.orderer_note,
                seller_note=order.seller_note,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 생성 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=OrderListResponse)
async def get_orders(
    supplier_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 목록 조회 (헥사고날 아키텍처)"""
    try:
        result = await order_service.get_orders(
            supplier_id=supplier_id,
            status=status,
            limit=limit,
            offset=offset
        )

        if result.is_success():
            orders, total = result.get_value()
            return OrderListResponse(
                orders=[
                    OrderResponse(
                        id=order.id,
                        supplier_id=order.supplier_id,
                        supplier_account_id=order.supplier_account_id,
                        order_key=order.order_key,
                        status=order.status.value,
                        payment_status=order.payment_status.value,
                        items=[
                            {
                                'id': item.id,
                                'product_id': item.product_id,
                                'product_name': item.product_name,
                                'quantity': item.quantity,
                                'unit_price': item.unit_price,
                                'total_price': item.total_price,
                                'options': item.options
                            }
                            for item in order.items
                        ],
                        subtotal=order.subtotal,
                        shipping_fee=order.shipping_fee,
                        total_amount=order.total_amount,
                        customer_name=order.customer_name,
                        customer_phone=order.customer_phone,
                        shipping_address=order.shipping_address,
                        shipping_info={
                            'tracking_number': order.shipping_info.tracking_number,
                            'shipping_company': order.shipping_info.shipping_company,
                            'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                            'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                            'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                        },
                        orderer_note=order.orderer_note,
                        seller_note=order.seller_note,
                        created_at=order.created_at,
                        updated_at=order.updated_at
                    )
                    for order in orders
                ],
                total=total,
                page=offset // limit + 1,
                page_size=limit,
                has_next=offset + limit < total,
                has_prev=offset > 0
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 목록 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 상세 조회 (헥사고날 아키텍처)"""
    try:
        result = await order_service.get_order_by_id(order_id)

        if result.is_success():
            order = result.get_value()
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="주문을 찾을 수 없습니다"
                )

            return OrderResponse(
                id=order.id,
                supplier_id=order.supplier_id,
                supplier_account_id=order.supplier_account_id,
                order_key=order.order_key,
                status=order.status.value,
                payment_status=order.payment_status.value,
                items=[
                    {
                        'id': item.id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price,
                        'options': item.options
                    }
                    for item in order.items
                ],
                subtotal=order.subtotal,
                shipping_fee=order.shipping_fee,
                total_amount=order.total_amount,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                shipping_address=order.shipping_address,
                shipping_info={
                    'tracking_number': order.shipping_info.tracking_number,
                    'shipping_company': order.shipping_info.shipping_company,
                    'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                    'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                    'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                },
                orderer_note=order.orderer_note,
                seller_note=order.seller_note,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    request: OrderUpdateRequest,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 수정 (헥사고날 아키텍처)"""
    try:
        result = await order_service.update_order(
            order_id=order_id,
            status=request.status,
            payment_status=request.payment_status,
            seller_note=request.seller_note,
            tracking_number=request.tracking_number,
            shipping_company=request.shipping_company
        )

        if result.is_success():
            order = result.get_value()
            return OrderResponse(
                id=order.id,
                supplier_id=order.supplier_id,
                supplier_account_id=order.supplier_account_id,
                order_key=order.order_key,
                status=order.status.value,
                payment_status=order.payment_status.value,
                items=[
                    {
                        'id': item.id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price,
                        'options': item.options
                    }
                    for item in order.items
                ],
                subtotal=order.subtotal,
                shipping_fee=order.shipping_fee,
                total_amount=order.total_amount,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                shipping_address=order.shipping_address,
                shipping_info={
                    'tracking_number': order.shipping_info.tracking_number,
                    'shipping_company': order.shipping_info.shipping_company,
                    'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                    'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                    'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                },
                orderer_note=order.orderer_note,
                seller_note=order.seller_note,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 수정 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{order_id}/ship", response_model=OrderResponse)
async def ship_order(
    order_id: str,
    request: ShippingUpdateRequest,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 발송 (헥사고날 아키텍처)"""
    try:
        result = await order_service.ship_order(
            order_id=order_id,
            tracking_number=request.tracking_number,
            shipping_company=request.shipping_company
        )

        if result.is_success():
            order = result.get_value()
            return OrderResponse(
                id=order.id,
                supplier_id=order.supplier_id,
                supplier_account_id=order.supplier_account_id,
                order_key=order.order_key,
                status=order.status.value,
                payment_status=order.payment_status.value,
                items=[
                    {
                        'id': item.id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price,
                        'options': item.options
                    }
                    for item in order.items
                ],
                subtotal=order.subtotal,
                shipping_fee=order.shipping_fee,
                total_amount=order.total_amount,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                shipping_address=order.shipping_address,
                shipping_info={
                    'tracking_number': order.shipping_info.tracking_number,
                    'shipping_company': order.shipping_info.shipping_company,
                    'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                    'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                    'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                },
                orderer_note=order.orderer_note,
                seller_note=order.seller_note,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 발송 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    request: OrderCancellationRequest,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 취소 (헥사고날 아키텍처)"""
    try:
        result = await order_service.cancel_order(
            order_id=order_id,
            reason=request.reason
        )

        if result.is_success():
            order = result.get_value()
            return OrderResponse(
                id=order.id,
                supplier_id=order.supplier_id,
                supplier_account_id=order.supplier_account_id,
                order_key=order.order_key,
                status=order.status.value,
                payment_status=order.payment_status.value,
                items=[
                    {
                        'id': item.id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'quantity': item.quantity,
                        'unit_price': item.unit_price,
                        'total_price': item.total_price,
                        'options': item.options
                    }
                    for item in order.items
                ],
                subtotal=order.subtotal,
                shipping_fee=order.shipping_fee,
                total_amount=order.total_amount,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                shipping_address=order.shipping_address,
                shipping_info={
                    'tracking_number': order.shipping_info.tracking_number,
                    'shipping_company': order.shipping_info.shipping_company,
                    'shipped_at': order.shipping_info.shipped_at.isoformat() if order.shipping_info.shipped_at else None,
                    'estimated_delivery_date': order.shipping_info.estimated_delivery_date.isoformat() if order.shipping_info.estimated_delivery_date else None,
                    'actual_delivery_date': order.shipping_info.actual_delivery_date.isoformat() if order.shipping_info.actual_delivery_date else None
                },
                orderer_note=order.orderer_note,
                seller_note=order.seller_note,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 취소 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats", response_model=OrderStatsResponse)
async def get_order_stats(
    supplier_id: Optional[str] = None,
    order_service: OrderService = Depends(get_order_service)
):
    """주문 통계 조회 (헥사고날 아키텍처)"""
    try:
        result = await order_service.get_order_stats(supplier_id=supplier_id)

        if result.is_success():
            stats = result.get_value()
            return OrderStatsResponse(
                total_orders=stats['total_orders'],
                pending_orders=stats['pending_orders'],
                shipped_orders=stats['shipped_orders'],
                delivered_orders=stats['delivered_orders'],
                cancelled_orders=stats['cancelled_orders'],
                total_revenue=stats['total_revenue'],
                average_order_value=stats['average_order_value']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get_error()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 통계 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
