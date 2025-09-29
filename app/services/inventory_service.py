"""
재고 관리 서비스
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from app.models.database import (
    Inventory, 
    InventoryHistory, 
    InventoryAlert, 
    InventorySyncHistory,
    Product
)
from app.core.logging import LoggerMixin


class InventoryService(LoggerMixin):
    """재고 관리 서비스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ===== 재고 CRUD =====
    
    async def get_inventories(
        self,
        supplier_id: Optional[str] = None,
        stock_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Inventory]:
        """재고 목록 조회"""
        query = select(Inventory)
        
        conditions = []
        if supplier_id:
            conditions.append(Inventory.supplier_id == supplier_id)
        if stock_status:
            conditions.append(Inventory.stock_status == stock_status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(Inventory.updated_at)).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_inventory_by_product_id(self, product_id: str) -> Optional[Inventory]:
        """상품 ID로 재고 조회"""
        query = select(Inventory).where(Inventory.product_id == product_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_or_update_inventory(
        self,
        product_id: str,
        supplier_id: str,
        available_quantity: int,
        low_stock_threshold: Optional[int] = 10,
        created_by: Optional[str] = "system"
    ) -> Inventory:
        """재고 생성 또는 업데이트"""
        # 기존 재고 확인
        inventory = await self.get_inventory_by_product_id(product_id)
        
        if inventory:
            # 재고 업데이트
            quantity_before = inventory.total_quantity
            inventory.available_quantity = available_quantity
            inventory.total_quantity = available_quantity
            inventory.last_synced_at = datetime.utcnow()
            
            # 재고 상태 업데이트
            inventory.stock_status = self._calculate_stock_status(
                available_quantity,
                inventory.low_stock_threshold,
                inventory.out_of_stock_threshold
            )
            
            # 변동 이력 기록
            if quantity_before != available_quantity:
                await self._create_inventory_history(
                    inventory_id=inventory.id,
                    product_id=product_id,
                    quantity_before=quantity_before,
                    quantity_after=available_quantity,
                    quantity_changed=available_quantity - quantity_before,
                    change_type="sync",
                    reason="auto_sync",
                    created_by=created_by
                )
            
            # 재고 부족 알림 확인
            await self._check_and_create_alert(inventory)
            
            self.logger.info(f"재고 업데이트: {product_id} ({quantity_before} -> {available_quantity})")
        else:
            # 신규 재고 생성
            inventory = Inventory(
                id=f"INV_{uuid.uuid4().hex[:8].upper()}",
                product_id=product_id,
                supplier_id=supplier_id,
                available_quantity=available_quantity,
                total_quantity=available_quantity,
                low_stock_threshold=low_stock_threshold,
                stock_status=self._calculate_stock_status(
                    available_quantity,
                    low_stock_threshold,
                    0
                ),
                last_synced_at=datetime.utcnow()
            )
            self.session.add(inventory)
            
            # 변동 이력 기록
            await self._create_inventory_history(
                inventory_id=inventory.id,
                product_id=product_id,
                quantity_before=0,
                quantity_after=available_quantity,
                quantity_changed=available_quantity,
                change_type="increase",
                reason="initial_stock",
                created_by=created_by
            )
            
            self.logger.info(f"재고 생성: {product_id} (수량: {available_quantity})")
        
        await self.session.commit()
        await self.session.refresh(inventory)
        return inventory
    
    async def adjust_inventory(
        self,
        product_id: str,
        quantity_change: int,
        reason: str = "manual",
        reference_id: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = "admin"
    ) -> Inventory:
        """재고 조정 (증가/감소)"""
        inventory = await self.get_inventory_by_product_id(product_id)
        if not inventory:
            raise ValueError(f"재고를 찾을 수 없습니다: {product_id}")
        
        quantity_before = inventory.available_quantity
        quantity_after = quantity_before + quantity_change
        
        if quantity_after < 0:
            raise ValueError(f"재고가 부족합니다: 현재 {quantity_before}, 요청 {quantity_change}")
        
        # 재고 업데이트
        inventory.available_quantity = quantity_after
        inventory.total_quantity = quantity_after + inventory.reserved_quantity
        
        # 재고 상태 업데이트
        inventory.stock_status = self._calculate_stock_status(
            quantity_after,
            inventory.low_stock_threshold,
            inventory.out_of_stock_threshold
        )
        
        # 변동 이력 기록
        change_type = "increase" if quantity_change > 0 else "decrease"
        await self._create_inventory_history(
            inventory_id=inventory.id,
            product_id=product_id,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            quantity_changed=quantity_change,
            change_type=change_type,
            reason=reason,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by
        )
        
        # 재고 부족 알림 확인
        await self._check_and_create_alert(inventory)
        
        await self.session.commit()
        await self.session.refresh(inventory)
        
        self.logger.info(f"재고 조정: {product_id} ({quantity_before} -> {quantity_after})")
        return inventory
    
    async def reserve_inventory(
        self,
        product_id: str,
        quantity: int,
        reference_id: str,
        created_by: Optional[str] = "system"
    ) -> Inventory:
        """재고 예약 (주문 시)"""
        inventory = await self.get_inventory_by_product_id(product_id)
        if not inventory:
            raise ValueError(f"재고를 찾을 수 없습니다: {product_id}")
        
        if inventory.available_quantity < quantity:
            raise ValueError(f"재고가 부족합니다: 현재 {inventory.available_quantity}, 요청 {quantity}")
        
        # 가용 재고 감소, 예약 재고 증가
        inventory.available_quantity -= quantity
        inventory.reserved_quantity += quantity
        
        # 재고 상태 업데이트
        inventory.stock_status = self._calculate_stock_status(
            inventory.available_quantity,
            inventory.low_stock_threshold,
            inventory.out_of_stock_threshold
        )
        
        # 변동 이력 기록
        await self._create_inventory_history(
            inventory_id=inventory.id,
            product_id=product_id,
            quantity_before=inventory.available_quantity + quantity,
            quantity_after=inventory.available_quantity,
            quantity_changed=-quantity,
            change_type="decrease",
            reason="order_reserved",
            reference_id=reference_id,
            notes=f"주문 예약: {quantity}개",
            created_by=created_by
        )
        
        await self.session.commit()
        await self.session.refresh(inventory)
        
        self.logger.info(f"재고 예약: {product_id} ({quantity}개)")
        return inventory
    
    async def release_reservation(
        self,
        product_id: str,
        quantity: int,
        reference_id: str,
        created_by: Optional[str] = "system"
    ) -> Inventory:
        """재고 예약 해제 (주문 취소 시)"""
        inventory = await self.get_inventory_by_product_id(product_id)
        if not inventory:
            raise ValueError(f"재고를 찾을 수 없습니다: {product_id}")
        
        if inventory.reserved_quantity < quantity:
            raise ValueError(f"예약된 재고가 부족합니다: 현재 {inventory.reserved_quantity}, 요청 {quantity}")
        
        # 가용 재고 증가, 예약 재고 감소
        inventory.available_quantity += quantity
        inventory.reserved_quantity -= quantity
        
        # 재고 상태 업데이트
        inventory.stock_status = self._calculate_stock_status(
            inventory.available_quantity,
            inventory.low_stock_threshold,
            inventory.out_of_stock_threshold
        )
        
        # 변동 이력 기록
        await self._create_inventory_history(
            inventory_id=inventory.id,
            product_id=product_id,
            quantity_before=inventory.available_quantity - quantity,
            quantity_after=inventory.available_quantity,
            quantity_changed=quantity,
            change_type="increase",
            reason="order_cancelled",
            reference_id=reference_id,
            notes=f"주문 취소: {quantity}개",
            created_by=created_by
        )
        
        await self.session.commit()
        await self.session.refresh(inventory)
        
        self.logger.info(f"재고 예약 해제: {product_id} ({quantity}개)")
        return inventory
    
    # ===== 재고 이력 =====
    
    async def _create_inventory_history(
        self,
        inventory_id: str,
        product_id: str,
        quantity_before: int,
        quantity_after: int,
        quantity_changed: int,
        change_type: str,
        reason: str,
        reference_id: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = "system"
    ) -> InventoryHistory:
        """재고 변동 이력 생성"""
        history = InventoryHistory(
            id=f"INVHIST_{uuid.uuid4().hex[:8].upper()}",
            inventory_id=inventory_id,
            product_id=product_id,
            change_type=change_type,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            quantity_changed=quantity_changed,
            reason=reason,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by
        )
        self.session.add(history)
        return history
    
    async def get_inventory_history(
        self,
        product_id: Optional[str] = None,
        inventory_id: Optional[str] = None,
        change_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InventoryHistory]:
        """재고 변동 이력 조회"""
        query = select(InventoryHistory)
        
        conditions = []
        if product_id:
            conditions.append(InventoryHistory.product_id == product_id)
        if inventory_id:
            conditions.append(InventoryHistory.inventory_id == inventory_id)
        if change_type:
            conditions.append(InventoryHistory.change_type == change_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(InventoryHistory.created_at)).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    # ===== 재고 알림 =====
    
    async def _check_and_create_alert(self, inventory: Inventory):
        """재고 부족 알림 확인 및 생성"""
        if not inventory.enable_low_stock_alert:
            return
        
        # 이미 최근에 알림을 보냈으면 중복 방지
        if inventory.last_alerted_at:
            time_since_last_alert = datetime.utcnow() - inventory.last_alerted_at
            if time_since_last_alert < timedelta(hours=1):
                return
        
        alert_type = None
        alert_level = None
        title = None
        message = None
        
        # 재고 상태에 따라 알림 생성
        if inventory.stock_status == "out_of_stock":
            alert_type = "out_of_stock"
            alert_level = "error"
            title = "품절 알림"
            message = f"상품 {inventory.product_id}의 재고가 품절되었습니다."
        elif inventory.stock_status == "low_stock":
            alert_type = "low_stock"
            alert_level = "warning"
            title = "재고 부족 알림"
            message = f"상품 {inventory.product_id}의 재고가 부족합니다. (현재: {inventory.available_quantity})"
        
        if alert_type:
            alert = InventoryAlert(
                id=f"INVALERT_{uuid.uuid4().hex[:8].upper()}",
                inventory_id=inventory.id,
                product_id=inventory.product_id,
                supplier_id=inventory.supplier_id,
                alert_type=alert_type,
                alert_level=alert_level,
                current_quantity=inventory.available_quantity,
                threshold_quantity=inventory.low_stock_threshold,
                title=title,
                message=message
            )
            self.session.add(alert)
            
            # 마지막 알림 시각 업데이트
            inventory.last_alerted_at = datetime.utcnow()
            
            self.logger.warning(f"재고 알림 생성: {inventory.product_id} - {alert_type}")
    
    async def get_inventory_alerts(
        self,
        supplier_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InventoryAlert]:
        """재고 알림 목록 조회"""
        query = select(InventoryAlert)
        
        conditions = []
        if supplier_id:
            conditions.append(InventoryAlert.supplier_id == supplier_id)
        if alert_type:
            conditions.append(InventoryAlert.alert_type == alert_type)
        if is_read is not None:
            conditions.append(InventoryAlert.is_read == is_read)
        if is_resolved is not None:
            conditions.append(InventoryAlert.is_resolved == is_resolved)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(InventoryAlert.created_at)).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def mark_alert_as_read(self, alert_id: str) -> InventoryAlert:
        """알림 읽음 처리"""
        query = select(InventoryAlert).where(InventoryAlert.id == alert_id)
        result = await self.session.execute(query)
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise ValueError(f"알림을 찾을 수 없습니다: {alert_id}")
        
        alert.is_read = True
        await self.session.commit()
        await self.session.refresh(alert)
        
        self.logger.info(f"알림 읽음 처리: {alert_id}")
        return alert
    
    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: Optional[str] = "admin"
    ) -> InventoryAlert:
        """알림 해결 처리"""
        query = select(InventoryAlert).where(InventoryAlert.id == alert_id)
        result = await self.session.execute(query)
        alert = result.scalar_one_or_none()
        
        if not alert:
            raise ValueError(f"알림을 찾을 수 없습니다: {alert_id}")
        
        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = resolved_by
        await self.session.commit()
        await self.session.refresh(alert)
        
        self.logger.info(f"알림 해결 처리: {alert_id}")
        return alert
    
    # ===== 재고 동기화 =====
    
    async def create_sync_history(
        self,
        supplier_id: str,
        sync_type: str = "manual",
        created_by: Optional[str] = "system"
    ) -> InventorySyncHistory:
        """재고 동기화 이력 생성"""
        sync_history = InventorySyncHistory(
            id=f"INVSYNC_{uuid.uuid4().hex[:8].upper()}",
            supplier_id=supplier_id,
            sync_type=sync_type,
            sync_status="pending",
            started_at=datetime.utcnow(),
            created_by=created_by
        )
        self.session.add(sync_history)
        await self.session.commit()
        await self.session.refresh(sync_history)
        
        self.logger.info(f"재고 동기화 이력 생성: {sync_history.id}")
        return sync_history
    
    async def update_sync_history(
        self,
        sync_id: str,
        sync_status: str,
        total_products: Optional[int] = None,
        synced_products: Optional[int] = None,
        failed_products: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> InventorySyncHistory:
        """재고 동기화 이력 업데이트"""
        query = select(InventorySyncHistory).where(InventorySyncHistory.id == sync_id)
        result = await self.session.execute(query)
        sync_history = result.scalar_one_or_none()
        
        if not sync_history:
            raise ValueError(f"동기화 이력을 찾을 수 없습니다: {sync_id}")
        
        sync_history.sync_status = sync_status
        
        if total_products is not None:
            sync_history.total_products = total_products
        if synced_products is not None:
            sync_history.synced_products = synced_products
        if failed_products is not None:
            sync_history.failed_products = failed_products
        
        if sync_status in ["completed", "failed"]:
            sync_history.completed_at = datetime.utcnow()
            if sync_history.started_at:
                duration = sync_history.completed_at - sync_history.started_at
                sync_history.duration_seconds = int(duration.total_seconds())
        
        if error_message:
            sync_history.error_message = error_message
        if error_details:
            sync_history.error_details = json.dumps(error_details, ensure_ascii=False)
        
        await self.session.commit()
        await self.session.refresh(sync_history)
        
        self.logger.info(f"재고 동기화 이력 업데이트: {sync_id} - {sync_status}")
        return sync_history
    
    async def get_sync_history(
        self,
        supplier_id: Optional[str] = None,
        sync_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InventorySyncHistory]:
        """재고 동기화 이력 조회"""
        query = select(InventorySyncHistory)
        
        conditions = []
        if supplier_id:
            conditions.append(InventorySyncHistory.supplier_id == supplier_id)
        if sync_status:
            conditions.append(InventorySyncHistory.sync_status == sync_status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(InventorySyncHistory.created_at)).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    # ===== 재고 통계 =====
    
    async def get_inventory_stats(self, supplier_id: Optional[str] = None) -> Dict[str, Any]:
        """재고 통계 조회"""
        query = select(Inventory)
        if supplier_id:
            query = query.where(Inventory.supplier_id == supplier_id)
        
        result = await self.session.execute(query)
        inventories = result.scalars().all()
        
        # 통계 계산
        total_inventories = len(inventories)
        in_stock = len([inv for inv in inventories if inv.stock_status == "in_stock"])
        low_stock = len([inv for inv in inventories if inv.stock_status == "low_stock"])
        out_of_stock = len([inv for inv in inventories if inv.stock_status == "out_of_stock"])
        
        total_quantity = sum(inv.total_quantity for inv in inventories)
        available_quantity = sum(inv.available_quantity for inv in inventories)
        reserved_quantity = sum(inv.reserved_quantity for inv in inventories)
        
        # 미해결 알림 수
        alert_query = select(func.count(InventoryAlert.id)).where(
            InventoryAlert.is_resolved == False
        )
        if supplier_id:
            alert_query = alert_query.where(InventoryAlert.supplier_id == supplier_id)
        
        alert_result = await self.session.execute(alert_query)
        unresolved_alerts = alert_result.scalar()
        
        return {
            "total_inventories": total_inventories,
            "in_stock_count": in_stock,
            "low_stock_count": low_stock,
            "out_of_stock_count": out_of_stock,
            "total_quantity": total_quantity,
            "available_quantity": available_quantity,
            "reserved_quantity": reserved_quantity,
            "unresolved_alerts": unresolved_alerts
        }
    
    # ===== 유틸리티 메서드 =====
    
    def _calculate_stock_status(
        self,
        available_quantity: int,
        low_stock_threshold: int,
        out_of_stock_threshold: int
    ) -> str:
        """재고 상태 계산"""
        if available_quantity <= out_of_stock_threshold:
            return "out_of_stock"
        elif available_quantity <= low_stock_threshold:
            return "low_stock"
        else:
            return "in_stock"
