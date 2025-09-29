from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.database import Category, Product
from app.core.logging import get_logger, LoggerMixin
from app.core.exceptions import ProductSyncError, ValidationError

logger = get_logger(__name__)

class CategoryService(LoggerMixin):
    """카테고리 서비스 (간단 버전)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_categories(
        self,
        supplier_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        level: Optional[int] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Category]:
        """카테고리 목록 조회"""
        query = select(Category)

        # 필터링 조건들
        if supplier_id is not None:
            query = query.where(Category.supplier_id == supplier_id)
        if parent_id is not None:
            query = query.where(Category.parent_id == parent_id)
        if level is not None:
            query = query.where(Category.level == level)
        if is_active is not None:
            query = query.where(Category.is_active == is_active)
        if search:
            # 카테고리명 검색
            query = query.where(Category.name.contains(search))

        query = query.order_by(Category.level, Category.name).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_category_by_id(self, category_id: str) -> Optional[Category]:
        """ID로 카테고리 조회"""
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def create_category(
        self,
        category_id: str,
        name: str,
        supplier_id: str,
        parent_id: Optional[str] = None,
        level: Optional[int] = None,
        is_active: bool = True
    ) -> Category:
        """카테고리 생성"""
        # 중복 체크
        existing = await self.get_category_by_id(category_id)
        if existing:
            raise ValidationError(f"이미 존재하는 카테고리입니다: {category_id}")

        # 레벨 계산
        if level is None:
            if parent_id:
                parent_category = await self.get_category_by_id(parent_id)
                if parent_category:
                    level = parent_category.level + 1
                else:
                    level = 1
            else:
                level = 0  # 루트 카테고리

        # 카테고리 생성
        new_category = Category(
            id=category_id,
            name=name,
            parent_id=parent_id,
            level=level,
            supplier_id=supplier_id,
            is_active=is_active
        )
        
        self.db.add(new_category)
        await self.db.commit()
        await self.db.refresh(new_category)

        self.logger.info(f"카테고리 생성 완료: {name} ({category_id})")
        return new_category

    async def update_category(
        self,
        category_id: str,
        **kwargs
    ) -> Optional[Category]:
        """카테고리 정보 수정"""
        category = await self.get_category_by_id(category_id)
        if not category:
            return None

        # 업데이트할 필드들
        update_data = {}
        for field, value in kwargs.items():
            if value is not None and hasattr(category, field):
                update_data[field] = value

        update_data['updated_at'] = datetime.now()

        # 업데이트 실행
        await self.db.execute(
            update(Category).where(Category.id == category_id).values(**update_data)
        )
        await self.db.commit()

        # 업데이트된 카테고리 조회
        await self.db.refresh(category)

        self.logger.info(f"카테고리 수정 완료: {category.name} ({category.id})")
        return category

    async def delete_category(self, category_id: str) -> bool:
        """카테고리 삭제"""
        try:
            category = await self.get_category_by_id(category_id)
            if not category:
                return False

            # 하위 카테고리가 있는지 확인
            children_count = await self._count_children(category.id)
            if children_count > 0:
                raise ValidationError(f"하위 카테고리가 있는 카테고리는 삭제할 수 없습니다: {category.name}")

            # 삭제 실행
            await self.db.execute(
                delete(Category).where(Category.id == category_id)
            )
            await self.db.commit()

            self.logger.info(f"카테고리 삭제 완료: {category.name} ({category.id})")
            return True

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"카테고리 삭제 실패: {e}")
            return False

    async def get_category_tree(self, supplier_id: str) -> Dict[str, Any]:
        """계층형 카테고리 트리 구조 조회"""
        # 모든 카테고리 조회
        categories = await self.get_categories(supplier_id=supplier_id)
        
        # 카테고리를 딕셔너리로 변환
        category_dict = {}
        for category in categories:
            category_dict[category.id] = {
                "id": category.id,
                "name": category.name,
                "level": category.level,
                "parent_id": category.parent_id,
                "is_active": category.is_active,
                "children": []
            }

        # 트리 구조 생성
        tree = []
        for category in categories:
            category_data = category_dict[category.id]
            if category.parent_id is None:
                tree.append(category_data)
            else:
                if category.parent_id in category_dict:
                    category_dict[category.parent_id]["children"].append(category_data)

        return {
            "supplier_id": supplier_id,
            "categories": tree,
            "total_count": len(categories)
        }

    async def get_category_stats(self, supplier_id: str) -> Dict[str, Any]:
        """카테고리 통계 조회"""
        # 총 카테고리 수
        total_result = await self.db.execute(
            select(func.count(Category.id)).where(Category.supplier_id == supplier_id)
        )
        total_categories = total_result.scalar()

        # 활성 카테고리 수
        active_result = await self.db.execute(
            select(func.count(Category.id)).where(
                and_(
                    Category.supplier_id == supplier_id,
                    Category.is_active == True
                )
            )
        )
        active_categories = active_result.scalar()

        # 레벨별 카테고리 수
        level_stats = []
        for level in range(0, 5):  # 0-4 레벨
            level_result = await self.db.execute(
                select(func.count(Category.id)).where(
                    and_(
                        Category.supplier_id == supplier_id,
                        Category.level == level
                    )
                )
            )
            count = level_result.scalar()
            if count > 0:
                level_stats.append({"level": level, "count": count})

        # 상품이 있는 카테고리 수
        categories_with_products_result = await self.db.execute(
            select(func.count(func.distinct(Product.category_id))).where(
                Product.supplier_id == supplier_id
            )
        )
        categories_with_products = categories_with_products_result.scalar()

        return {
            "supplier_id": supplier_id,
            "total_categories": total_categories,
            "active_categories": active_categories,
            "level_stats": level_stats,
            "categories_with_products": categories_with_products
        }

    async def _count_children(self, category_id: str) -> int:
        """하위 카테고리 수 조회"""
        result = await self.db.execute(
            select(func.count(Category.id)).where(Category.parent_id == category_id)
        )
        return result.scalar() or 0
