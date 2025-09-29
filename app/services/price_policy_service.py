from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json
import uuid

from app.models.database import PricePolicy, PriceRule, PriceCalculationHistory, Product
from app.core.logging import get_logger, LoggerMixin
from app.core.exceptions import ProductSyncError, ValidationError

logger = get_logger(__name__)

class PricePolicyService(LoggerMixin):
    """가격 정책 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_price_policies(
        self,
        supplier_id: Optional[str] = None,
        category_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[PricePolicy]:
        """가격 정책 목록 조회"""
        query = select(PricePolicy)

        # 필터링 조건들
        if supplier_id is not None:
            query = query.where(PricePolicy.supplier_id == supplier_id)
        if category_id is not None:
            query = query.where(PricePolicy.category_id == category_id)
        if is_active is not None:
            query = query.where(PricePolicy.is_active == is_active)
        if search:
            # 정책명 검색
            query = query.where(PricePolicy.name.contains(search))

        query = query.order_by(PricePolicy.priority.desc(), PricePolicy.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_price_policy_by_id(self, policy_id: str) -> Optional[PricePolicy]:
        """ID로 가격 정책 조회"""
        result = await self.db.execute(
            select(PricePolicy).where(PricePolicy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def create_price_policy(
        self,
        name: str,
        supplier_id: str,
        description: Optional[str] = None,
        category_id: Optional[str] = None,
        base_margin_rate: float = 0.3,
        min_margin_rate: float = 0.1,
        max_margin_rate: float = 0.5,
        price_calculation_method: str = "margin",
        rounding_method: str = "round",
        discount_rate: float = 0.0,
        premium_rate: float = 0.0,
        min_price: int = 0,
        max_price: int = 10000000,
        priority: int = 0,
        conditions: Optional[Dict[str, Any]] = None,
        is_active: bool = True
    ) -> PricePolicy:
        """가격 정책 생성"""
        policy_id = f"POLICY_{uuid.uuid4().hex[:8].upper()}"
        
        # 가격 정책 생성
        new_policy = PricePolicy(
            id=policy_id,
            name=name,
            description=description,
            supplier_id=supplier_id,
            category_id=category_id,
            base_margin_rate=base_margin_rate,
            min_margin_rate=min_margin_rate,
            max_margin_rate=max_margin_rate,
            price_calculation_method=price_calculation_method,
            rounding_method=rounding_method,
            discount_rate=discount_rate,
            premium_rate=premium_rate,
            min_price=min_price,
            max_price=max_price,
            priority=priority,
            conditions=json.dumps(conditions) if conditions else None,
            is_active=is_active
        )
        
        self.db.add(new_policy)
        await self.db.commit()
        await self.db.refresh(new_policy)

        self.logger.info(f"가격 정책 생성 완료: {name} ({policy_id})")
        return new_policy

    async def update_price_policy(
        self,
        policy_id: str,
        **kwargs
    ) -> Optional[PricePolicy]:
        """가격 정책 정보 수정"""
        policy = await self.get_price_policy_by_id(policy_id)
        if not policy:
            return None

        # 업데이트할 필드들
        update_data = {}
        for field, value in kwargs.items():
            if value is not None and hasattr(policy, field):
                if field == 'conditions' and isinstance(value, dict):
                    update_data[field] = json.dumps(value)
                else:
                    update_data[field] = value

        update_data['updated_at'] = datetime.now()

        # 업데이트 실행
        await self.db.execute(
            update(PricePolicy).where(PricePolicy.id == policy_id).values(**update_data)
        )
        await self.db.commit()

        # 업데이트된 정책 조회
        await self.db.refresh(policy)

        self.logger.info(f"가격 정책 수정 완료: {policy.name} ({policy.id})")
        return policy

    async def delete_price_policy(self, policy_id: str) -> bool:
        """가격 정책 삭제"""
        try:
            policy = await self.get_price_policy_by_id(policy_id)
            if not policy:
                return False

            # 관련 가격 규칙들도 삭제
            await self.db.execute(
                delete(PriceRule).where(PriceRule.policy_id == policy_id)
            )

            # 가격 정책 삭제
            await self.db.execute(
                delete(PricePolicy).where(PricePolicy.id == policy_id)
            )
            await self.db.commit()

            self.logger.info(f"가격 정책 삭제 완료: {policy.name} ({policy.id})")
            return True

        except Exception as e:
            self.logger.error(f"가격 정책 삭제 실패: {e}")
            return False

    async def calculate_price(
        self,
        product_id: str,
        policy_id: str,
        original_price: int,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """가격 계산"""
        try:
            # 가격 정책 조회
            policy = await self.get_price_policy_by_id(policy_id)
            if not policy:
                raise ValidationError(f"가격 정책을 찾을 수 없습니다: {policy_id}")

            # 계산 과정 기록
            calculation_steps = []
            applied_rules = []

            # 기본 마진율 적용
            base_margin_rate = policy.base_margin_rate
            calculated_price = original_price * (1 + base_margin_rate)
            calculation_steps.append({
                "step": "base_margin",
                "description": f"기본 마진율 {base_margin_rate*100:.1f}% 적용",
                "original_price": original_price,
                "margin_rate": base_margin_rate,
                "calculated_price": calculated_price
            })

            # 할인/프리미엄 적용
            if policy.discount_rate > 0:
                discount_amount = calculated_price * policy.discount_rate
                calculated_price -= discount_amount
                calculation_steps.append({
                    "step": "discount",
                    "description": f"할인율 {policy.discount_rate*100:.1f}% 적용",
                    "discount_amount": discount_amount,
                    "calculated_price": calculated_price
                })

            if policy.premium_rate > 0:
                premium_amount = calculated_price * policy.premium_rate
                calculated_price += premium_amount
                calculation_steps.append({
                    "step": "premium",
                    "description": f"프리미엄율 {policy.premium_rate*100:.1f}% 적용",
                    "premium_amount": premium_amount,
                    "calculated_price": calculated_price
                })

            # 가격 범위 제한
            if calculated_price < policy.min_price:
                calculated_price = policy.min_price
                calculation_steps.append({
                    "step": "min_price_limit",
                    "description": f"최소 가격 제한: {policy.min_price}",
                    "calculated_price": calculated_price
                })

            if calculated_price > policy.max_price:
                calculated_price = policy.max_price
                calculation_steps.append({
                    "step": "max_price_limit",
                    "description": f"최대 가격 제한: {policy.max_price}",
                    "calculated_price": calculated_price
                })

            # 반올림 처리
            if policy.rounding_method == "round":
                calculated_price = round(calculated_price)
            elif policy.rounding_method == "floor":
                calculated_price = int(calculated_price)
            elif policy.rounding_method == "ceiling":
                calculated_price = int(calculated_price) + (1 if calculated_price % 1 > 0 else 0)

            calculation_steps.append({
                "step": "rounding",
                "description": f"{policy.rounding_method} 반올림",
                "calculated_price": calculated_price
            })

            # 최종 마진율 계산
            final_margin_rate = (calculated_price - original_price) / original_price if original_price > 0 else 0

            # 가격 계산 이력 저장
            history_id = f"HIST_{uuid.uuid4().hex[:8].upper()}"
            history = PriceCalculationHistory(
                id=history_id,
                product_id=product_id,
                policy_id=policy_id,
                original_price=original_price,
                calculated_price=int(calculated_price),
                margin_rate=final_margin_rate,
                discount_amount=int(calculated_price * policy.discount_rate) if policy.discount_rate > 0 else 0,
                premium_amount=int(calculated_price * policy.premium_rate) if policy.premium_rate > 0 else 0,
                calculation_steps=json.dumps(calculation_steps),
                calculation_method=policy.price_calculation_method,
                applied_rules=json.dumps(applied_rules),
                created_by=created_by
            )
            
            self.db.add(history)
            await self.db.commit()

            self.logger.info(f"가격 계산 완료: {original_price} -> {calculated_price} (마진율: {final_margin_rate*100:.1f}%)")

            return {
                "original_price": original_price,
                "calculated_price": int(calculated_price),
                "margin_rate": final_margin_rate,
                "discount_amount": int(calculated_price * policy.discount_rate) if policy.discount_rate > 0 else 0,
                "premium_amount": int(calculated_price * policy.premium_rate) if policy.premium_rate > 0 else 0,
                "calculation_steps": calculation_steps,
                "policy_id": policy_id,
                "history_id": history_id
            }

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"가격 계산 실패: {e}")
            raise ProductSyncError(f"가격 계산 실패: {str(e)}")

    async def bulk_calculate_prices(
        self,
        product_ids: List[str],
        policy_id: str,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """대량 가격 계산"""
        results = []
        success_count = 0
        failed_count = 0

        for product_id in product_ids:
            try:
                # 상품 정보 조회
                product_result = await self.db.execute(
                    select(Product).where(Product.id == product_id)
                )
                product = product_result.scalar_one_or_none()
                
                if not product:
                    failed_count += 1
                    results.append({
                        "product_id": product_id,
                        "status": "failed",
                        "error": "상품을 찾을 수 없습니다"
                    })
                    continue

                # 원가 추출
                price_data = json.loads(product.price_data or '{}')
                original_price = price_data.get('original', 0)
                
                if original_price <= 0:
                    failed_count += 1
                    results.append({
                        "product_id": product_id,
                        "status": "failed",
                        "error": "유효하지 않은 원가"
                    })
                    continue

                # 가격 계산
                calculation_result = await self.calculate_price(
                    product_id, policy_id, original_price, created_by
                )
                
                # 상품 가격 업데이트
                price_data['sale'] = calculation_result['calculated_price']
                price_data['margin_rate'] = calculation_result['margin_rate']
                
                await self.db.execute(
                    update(Product).where(Product.id == product_id).values(
                        price_data=json.dumps(price_data),
                        updated_at=datetime.now()
                    )
                )
                
                success_count += 1
                results.append({
                    "product_id": product_id,
                    "status": "success",
                    "original_price": original_price,
                    "calculated_price": calculation_result['calculated_price'],
                    "margin_rate": calculation_result['margin_rate']
                })

            except Exception as e:
                failed_count += 1
                results.append({
                    "product_id": product_id,
                    "status": "failed",
                    "error": str(e)
                })

        await self.db.commit()

        return {
            "total_products": len(product_ids),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results
        }

    async def get_price_calculation_history(
        self,
        product_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[PriceCalculationHistory]:
        """가격 계산 이력 조회"""
        query = select(PriceCalculationHistory)

        if product_id:
            query = query.where(PriceCalculationHistory.product_id == product_id)
        if policy_id:
            query = query.where(PriceCalculationHistory.policy_id == policy_id)

        query = query.order_by(PriceCalculationHistory.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_price_policy_stats(self, supplier_id: str) -> Dict[str, Any]:
        """가격 정책 통계 조회"""
        # 총 정책 수
        total_result = await self.db.execute(
            select(func.count(PricePolicy.id)).where(PricePolicy.supplier_id == supplier_id)
        )
        total_policies = total_result.scalar()

        # 활성 정책 수
        active_result = await self.db.execute(
            select(func.count(PricePolicy.id)).where(
                and_(
                    PricePolicy.supplier_id == supplier_id,
                    PricePolicy.is_active == True
                )
            )
        )
        active_policies = active_result.scalar()

        # 최근 계산 이력 수
        recent_calculations_result = await self.db.execute(
            select(func.count(PriceCalculationHistory.id)).where(
                PriceCalculationHistory.created_at >= datetime.now() - timedelta(days=7)
            )
        )
        recent_calculations = recent_calculations_result.scalar()

        return {
            "supplier_id": supplier_id,
            "total_policies": total_policies,
            "active_policies": active_policies,
            "recent_calculations": recent_calculations
        }
