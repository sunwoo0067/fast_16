"""Item 엔티티 단위 테스트"""
import pytest
from datetime import datetime

from src.core.entities.item import Item, PricePolicy, ItemOption


class TestPricePolicy:
    """가격 정책 테스트"""

    def test_get_final_price_with_sale_price(self):
        """세일가가 있는 경우 세일가 반환"""
        policy = PricePolicy(
            original_price=10000,
            sale_price=8000,
            margin_rate=0.3
        )

        assert policy.get_final_price() == 8000

    def test_get_final_price_without_sale_price(self):
        """세일가가 없는 경우 마진율 적용"""
        policy = PricePolicy(
            original_price=10000,
            margin_rate=0.3
        )

        expected = int(10000 * 1.3)
        assert policy.get_final_price() == expected

    def test_is_profitable(self):
        """수익성 확인"""
        profitable_policy = PricePolicy(original_price=10000, margin_rate=0.3)
        unprofitable_policy = PricePolicy(original_price=10000, margin_rate=0.05)

        assert profitable_policy.is_profitable()
        assert not unprofitable_policy.is_profitable(min_margin_rate=0.1)


class TestItemOption:
    """상품 옵션 테스트"""

    def test_get_adjusted_price(self):
        """옵션별 조정가격 계산"""
        option = ItemOption(
            name="색상",
            value="빨강",
            price_adjustment=2000,
            stock_quantity=10
        )

        base_price = 10000
        adjusted_price = option.get_adjusted_price(base_price)

        assert adjusted_price == 12000


class TestItem:
    """상품 엔티티 테스트"""

    def test_item_creation(self):
        """상품 생성 테스트"""
        price = PricePolicy(original_price=10000, margin_rate=0.3)
        options = [
            ItemOption(name="색상", value="빨강", stock_quantity=10),
            ItemOption(name="사이즈", value="M", stock_quantity=5)
        ]

        item = Item(
            id="test-001",
            title="테스트 상품",
            brand="테스트 브랜드",
            price=price,
            options=options,
            images=["image1.jpg", "image2.jpg"],
            category_id="electronics",
            supplier_id="supplier-001"
        )

        assert item.id == "test-001"
        assert item.title == "테스트 상품"
        assert item.is_active == True
        assert len(item.options) == 2
        assert len(item.images) == 2

    def test_is_available(self):
        """상품 구매 가능 여부 확인"""
        # 구매 가능한 상품
        available_item = Item(
            id="available-001",
            title="구매 가능 상품",
            brand="브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[],
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=10
        )

        # 구매 불가능한 상품들
        no_stock_item = Item(
            id="no-stock-001",
            title="재고 없음",
            brand="브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[],
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=0
        )

        no_image_item = Item(
            id="no-image-001",
            title="이미지 없음",
            brand="브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[],
            images=[],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=10
        )

        inactive_item = Item(
            id="inactive-001",
            title="비활성 상품",
            brand="브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[],
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=10,
            is_active=False
        )

        assert available_item.is_available()
        assert not no_stock_item.is_available()
        assert not no_image_item.is_available()
        assert not inactive_item.is_available()

    def test_get_display_price(self):
        """표시 가격 확인"""
        price = PricePolicy(original_price=10000, margin_rate=0.3)
        options = [
            ItemOption(name="색상", value="빨강", price_adjustment=2000, stock_quantity=10),
            ItemOption(name="색상", value="파랑", price_adjustment=1000, stock_quantity=5)
        ]

        item = Item(
            id="test-001",
            title="테스트 상품",
            brand="브랜드",
            price=price,
            options=options,
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier"
        )

        # 가장 낮은 옵션 가격 반환
        expected_base_price = int(10000 * 1.3)  # 13000
        expected_display_price = expected_base_price + 1000  # 파랑 옵션

        assert item.get_display_price() == expected_display_price

    def test_can_fulfill_order(self):
        """주문 처리 가능 여부 확인"""
        price = PricePolicy(original_price=10000, margin_rate=0.3)
        options = [
            ItemOption(name="색상", value="빨강", stock_quantity=10),
            ItemOption(name="색상", value="파랑", stock_quantity=5)
        ]

        item = Item(
            id="test-001",
            title="테스트 상품",
            brand="브랜드",
            price=price,
            options=options,
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=20
        )

        # 기본 주문 (재고 확인)
        assert item.can_fulfill_order(5)
        assert item.can_fulfill_order(20)
        assert not item.can_fulfill_order(25)

        # 옵션별 주문
        assert item.can_fulfill_order(3, {"색상": "빨강"})  # 빨강 재고 10개
        assert item.can_fulfill_order(5, {"색상": "파랑"})  # 파랑 재고 5개
        assert not item.can_fulfill_order(7, {"색상": "파랑"})  # 파랑 재고 5개 부족

    def test_update_stock(self):
        """재고 업데이트"""
        item = Item(
            id="test-001",
            title="테스트 상품",
            brand="브랜드",
            price=PricePolicy(original_price=10000),
            options=[],
            images=["image.jpg"],
            category_id="category",
            supplier_id="supplier",
            stock_quantity=10
        )

        # 재고 증가
        item.update_stock(5)
        assert item.stock_quantity == 15

        # 재고 감소
        item.update_stock(-3)
        assert item.stock_quantity == 12

        # 0 미만으로 내려가지 않음
        item.update_stock(-20)
        assert item.stock_quantity == 0

    def test_hash_generation(self):
        """해시 생성 테스트"""
        item1 = Item(
            id="test-001",
            title="테스트 상품",
            brand="테스트 브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[ItemOption(name="색상", value="빨강")],
            images=["image.jpg"],
            category_id="electronics",
            supplier_id="supplier-001"
        )

        item2 = Item(
            id="test-002",
            title="테스트 상품",  # 같은 제목
            brand="테스트 브랜드",  # 같은 브랜드
            price=PricePolicy(original_price=10000, margin_rate=0.3),  # 같은 가격
            options=[ItemOption(name="색상", value="빨강")],  # 같은 옵션
            images=["image.jpg"],
            category_id="electronics",  # 같은 카테고리
            supplier_id="supplier-001"   # 같은 공급사
        )

        # 같은 내용이므로 같은 해시
        assert item1.hash_key == item2.hash_key

        # 다른 내용이면 다른 해시
        item3 = Item(
            id="test-003",
            title="다른 상품",
            brand="테스트 브랜드",
            price=PricePolicy(original_price=10000, margin_rate=0.3),
            options=[ItemOption(name="색상", value="빨강")],
            images=["image.jpg"],
            category_id="electronics",
            supplier_id="supplier-001"
        )

        assert item1.hash_key != item3.hash_key
