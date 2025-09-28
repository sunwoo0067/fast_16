"""상품 도메인 엔티티"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json


@dataclass
class PricePolicy:
    """가격 정책"""
    original_price: int
    sale_price: Optional[int] = None
    margin_rate: float = 0.3

    def get_final_price(self) -> int:
        """최종 판매가 계산"""
        if self.sale_price:
            return self.sale_price
        return int(self.original_price * (1 + self.margin_rate))

    def is_profitable(self, min_margin_rate: float = 0.1) -> bool:
        """수익성 있는 가격인지 확인"""
        return self.margin_rate >= min_margin_rate


@dataclass
class ItemOption:
    """상품 옵션 (색상, 사이즈 등)"""
    name: str
    value: str
    price_adjustment: int = 0
    stock_quantity: int = 0

    def get_adjusted_price(self, base_price: int) -> int:
        """옵션별 조정가격 계산"""
        return base_price + self.price_adjustment


@dataclass
class Item:
    """상품 도메인 엔티티"""
    id: str
    title: str
    brand: str
    price: PricePolicy
    options: List[ItemOption]
    images: List[str]
    category_id: str
    supplier_id: str
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    estimated_shipping_days: int = 7
    stock_quantity: int = 0
    max_stock_quantity: Optional[int] = None
    is_active: bool = True
    normalized_at: datetime = field(default_factory=datetime.now)
    hash_key: Optional[str] = None

    def __post_init__(self):
        """해시 키 자동 생성"""
        if not self.hash_key:
            self.hash_key = self._generate_hash()

    def _generate_hash(self) -> str:
        """상품 중복 검사용 해시 생성"""
        content = {
            'title': self.title,
            'brand': self.brand,
            'price': self.price.original_price,
            'options': sorted([f"{opt.name}:{opt.value}" for opt in self.options]),
            'category': self.category_id,
            'supplier': self.supplier_id
        }
        return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()

    def is_available(self) -> bool:
        """상품 구매 가능 여부 확인"""
        return (
            self.is_active and
            self.stock_quantity > 0 and
            len(self.images) > 0 and
            self.price.is_profitable()
        )

    def get_display_price(self) -> int:
        """표시 가격 반환 (가장 낮은 옵션 가격)"""
        if not self.options:
            return self.price.get_final_price()

        base_price = self.price.get_final_price()
        return min(opt.get_adjusted_price(base_price) for opt in self.options)

    def has_option_combination(self, option_values: Dict[str, str]) -> bool:
        """특정 옵션 조합 존재 여부 확인"""
        for option in self.options:
            if option.name in option_values and option.value != option_values[option.name]:
                return False
        return True

    def get_option_by_name(self, name: str) -> Optional[ItemOption]:
        """옵션명으로 옵션 조회"""
        for option in self.options:
            if option.name == name:
                return option
        return None

    def get_option_by_name_and_value(self, name: str, value: str) -> Optional[ItemOption]:
        """옵션명과 값으로 옵션 조회"""
        for option in self.options:
            if option.name == name and option.value == value:
                return option
        return None

    def can_fulfill_order(self, quantity: int, option_values: Optional[Dict[str, str]] = None) -> bool:
        """주문 처리 가능 여부 확인"""
        if not self.is_available():
            return False

        # 옵션별 재고 확인
        if option_values:
            for name, value in option_values.items():
                option = self.get_option_by_name_and_value(name, value)
                if option and option.stock_quantity < quantity:
                    return False

        return self.stock_quantity >= quantity

    def update_stock(self, quantity_change: int) -> None:
        """재고 업데이트"""
        self.stock_quantity = max(0, self.stock_quantity + quantity_change)

    def update_price(self, new_price: int, margin_rate: Optional[float] = None) -> None:
        """가격 업데이트"""
        self.price.original_price = new_price
        if margin_rate is not None:
            self.price.margin_rate = margin_rate

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        return {
            'id': self.id,
            'title': self.title,
            'brand': self.brand,
            'price': {
                'original_price': self.price.original_price,
                'sale_price': self.price.sale_price,
                'margin_rate': self.price.margin_rate,
                'final_price': self.price.get_final_price()
            },
            'options': [
                {
                    'name': opt.name,
                    'value': opt.value,
                    'price_adjustment': opt.price_adjustment,
                    'stock_quantity': opt.stock_quantity
                }
                for opt in self.options
            ],
            'images': self.images,
            'category_id': self.category_id,
            'supplier_id': self.supplier_id,
            'description': self.description,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'estimated_shipping_days': self.estimated_shipping_days,
            'stock_quantity': self.stock_quantity,
            'max_stock_quantity': self.max_stock_quantity,
            'is_active': self.is_active,
            'normalized_at': self.normalized_at.isoformat() if self.normalized_at else None,
            'hash_key': self.hash_key
        }
