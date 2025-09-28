import re
from typing import Dict, Any, List, Optional
from decimal import Decimal
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

class ProductValidator:
    """상품 데이터 검증 클래스"""

    # 검증 규칙 상수들
    MIN_NAME_LENGTH = 1
    MAX_NAME_LENGTH = 200
    MIN_PRICE = 0
    MAX_PRICE = 100000000  # 1억원
    MIN_MARGIN_RATE = 0.01  # 1%
    MAX_MARGIN_RATE = 0.95  # 95%
    MIN_SHIPPING_DAYS = 1
    MAX_SHIPPING_DAYS = 30
    MAX_IMAGES = 20
    MAX_OPTIONS = 100

    # 필수 필드들
    REQUIRED_FIELDS = [
        "item_key", "name", "price", "supplier_id", "supplier_account_id"
    ]

    # 선택적 필드들 (드랍싸핑 특화)
    OPTIONAL_FIELDS = [
        "sale_price", "margin_rate", "stock_quantity", "max_stock_quantity",
        "supplier_product_id", "supplier_name", "supplier_url", "supplier_image_url",
        "estimated_shipping_days", "category_id", "category_name", "description",
        "images", "options", "coupang_product_id", "manufacturer"
    ]

    @classmethod
    def validate_product_data(cls, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """상품 데이터 전체 검증"""
        errors = []

        try:
            # 1. 필수 필드 검증
            errors.extend(cls._validate_required_fields(product_data))

            # 2. 데이터 타입 및 형식 검증
            errors.extend(cls._validate_data_types(product_data))

            # 3. 비즈니스 규칙 검증
            errors.extend(cls._validate_business_rules(product_data))

            # 4. 드랍싸핑 특화 검증
            errors.extend(cls._validate_dropshipping_fields(product_data))

            if errors:
                error_messages = [error["message"] for error in errors]
                raise ValidationError(
                    f"상품 데이터 검증 실패: {'; '.join(error_messages[:3])}",
                    details={"errors": errors}
                )

            return product_data

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"상품 데이터 검증 중 오류 발생: {str(e)}")

    @classmethod
    def _validate_required_fields(cls, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """필수 필드 검증"""
        errors = []

        for field in cls.REQUIRED_FIELDS:
            if field not in product_data or product_data[field] is None:
                errors.append({
                    "field": field,
                    "message": f"필수 필드 누락: {field}",
                    "value": product_data.get(field)
                })

        return errors

    @classmethod
    def _validate_data_types(cls, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """데이터 타입 및 형식 검증"""
        errors = []

        # 문자열 필드 검증
        string_fields = {
            "item_key": (1, 50),
            "name": (cls.MIN_NAME_LENGTH, cls.MAX_NAME_LENGTH),
            "supplier_product_id": (1, 100),
            "supplier_name": (1, 100),
            "category_id": (1, 50),
            "category_name": (1, 100),
            "manufacturer": (1, 100)
        }

        for field, (min_len, max_len) in string_fields.items():
            value = product_data.get(field)
            if value is not None:
                if not isinstance(value, str):
                    errors.append({
                        "field": field,
                        "message": f"문자열이어야 합니다: {field}",
                        "value": value
                    })
                elif len(value) < min_len or len(value) > max_len:
                    errors.append({
                        "field": field,
                        "message": f"길이가 {min_len}-{max_len}자 사이여야 합니다: {field}",
                        "value": value
                    })

        # 숫자 필드 검증
        int_fields = {
            "price": (cls.MIN_PRICE, cls.MAX_PRICE),
            "sale_price": (cls.MIN_PRICE, cls.MAX_PRICE),
            "stock_quantity": (0, 1000000),
            "max_stock_quantity": (0, 1000000),
            "estimated_shipping_days": (cls.MIN_SHIPPING_DAYS, cls.MAX_SHIPPING_DAYS)
        }

        for field, (min_val, max_val) in int_fields.items():
            value = product_data.get(field)
            if value is not None:
                if not isinstance(value, int):
                    errors.append({
                        "field": field,
                        "message": f"정수여야 합니다: {field}",
                        "value": value
                    })
                elif value < min_val or value > max_val:
                    errors.append({
                        "field": field,
                        "message": f"{min_val}-{max_val} 사이의 값이어야 합니다: {field}",
                        "value": value
                    })

        # 부동소수점 필드 검증
        float_fields = {
            "margin_rate": (cls.MIN_MARGIN_RATE, cls.MAX_MARGIN_RATE)
        }

        for field, (min_val, max_val) in float_fields.items():
            value = product_data.get(field)
            if value is not None:
                if not isinstance(value, (int, float)):
                    errors.append({
                        "field": field,
                        "message": f"숫자여야 합니다: {field}",
                        "value": value
                    })
                elif value < min_val or value > max_val:
                    errors.append({
                        "field": field,
                        "message": f"{min_val}-{max_val} 사이의 값이어야 합니다: {field}",
                        "value": value
                    })

        # 불린 필드 검증
        bool_fields = ["is_active"]
        for field in bool_fields:
            value = product_data.get(field)
            if value is not None and not isinstance(value, bool):
                errors.append({
                    "field": field,
                    "message": f"불린값이어야 합니다: {field}",
                    "value": value
                })

        return errors

    @classmethod
    def _validate_business_rules(cls, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """비즈니스 규칙 검증"""
        errors = []

        # 판매가가 공급가보다 높아야 함
        price = product_data.get("price")
        sale_price = product_data.get("sale_price")

        if price is not None and sale_price is not None:
            if sale_price < price:
                errors.append({
                    "field": "sale_price",
                    "message": "판매가는 공급가보다 높아야 합니다",
                    "value": sale_price
                })

        # 마진율 검증
        margin_rate = product_data.get("margin_rate")
        if margin_rate is not None and price is not None and sale_price is not None:
            expected_margin = (sale_price - price) / sale_price
            if abs(expected_margin - margin_rate) > 0.01:  # 1% 오차 허용
                errors.append({
                    "field": "margin_rate",
                    "message": "마진율이 가격과 일치하지 않습니다",
                    "value": margin_rate
                })

        # 재고 검증
        stock_quantity = product_data.get("stock_quantity")
        max_stock_quantity = product_data.get("max_stock_quantity")

        if stock_quantity is not None and max_stock_quantity is not None:
            if stock_quantity > max_stock_quantity:
                errors.append({
                    "field": "stock_quantity",
                    "message": "현재 재고가 최대 재고를 초과할 수 없습니다",
                    "value": stock_quantity
                })

        return errors

    @classmethod
    def _validate_dropshipping_fields(cls, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """드랍싸핑 특화 필드 검증"""
        errors = []

        # 공급처 URL 형식 검증
        supplier_url = product_data.get("supplier_url")
        if supplier_url:
            if not cls._is_valid_url(supplier_url):
                errors.append({
                    "field": "supplier_url",
                    "message": "유효한 URL 형식이 아닙니다",
                    "value": supplier_url
                })

        # 이미지 URL 검증
        images = product_data.get("images", [])
        if images:
            if not isinstance(images, list):
                errors.append({
                    "field": "images",
                    "message": "이미지는 리스트 형식이어야 합니다",
                    "value": images
                })
            elif len(images) > cls.MAX_IMAGES:
                errors.append({
                    "field": "images",
                    "message": f"이미지는 최대 {cls.MAX_IMAGES}개까지 등록 가능합니다",
                    "value": len(images)
                })
            else:
                for i, image_url in enumerate(images):
                    if not cls._is_valid_url(image_url):
                        errors.append({
                            "field": f"images[{i}]",
                            "message": f"유효한 URL 형식이 아닙니다: {image_url}",
                            "value": image_url
                        })

        # 옵션 검증
        options = product_data.get("options", {})
        if options:
            if not isinstance(options, dict):
                errors.append({
                    "field": "options",
                    "message": "옵션은 딕셔너리 형식이어야 합니다",
                    "value": options
                })
            elif len(options) > cls.MAX_OPTIONS:
                errors.append({
                    "field": "options",
                    "message": f"옵션은 최대 {cls.MAX_OPTIONS}개까지 등록 가능합니다",
                    "value": len(options)
                })

        # 아이템 키 형식 검증 (영문, 숫자, 하이픈, 언더스코어만 허용)
        item_key = product_data.get("item_key")
        if item_key:
            if not re.match(r'^[A-Za-z0-9_-]+$', item_key):
                errors.append({
                    "field": "item_key",
                    "message": "아이템 키는 영문, 숫자, 하이픈, 언더스코어만 사용 가능합니다",
                    "value": item_key
                })

        return errors

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """URL 형식 검증"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return url_pattern.match(url) is not None

    @classmethod
    def validate_bulk_products(cls, products_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """대량 상품 데이터 검증"""
        result = {
            "valid_products": [],
            "invalid_products": [],
            "total_count": len(products_data)
        }

        for i, product_data in enumerate(products_data):
            try:
                validated_data = cls.validate_product_data(product_data)
                result["valid_products"].append(validated_data)
            except ValidationError as e:
                result["invalid_products"].append({
                    "index": i,
                    "data": product_data,
                    "errors": e.details.get("errors", [])
                })

        return result

class SupplierValidator:
    """공급사 데이터 검증 클래스"""

    @staticmethod
    def validate_supplier_data(supplier_data: Dict[str, Any]) -> Dict[str, Any]:
        """공급사 데이터 검증"""
        errors = []

        # 필수 필드 검증
        required_fields = ["name"]
        for field in required_fields:
            if field not in supplier_data or not supplier_data[field]:
                errors.append(f"필수 필드 누락: {field}")

        # 이름 길이 검증
        name = supplier_data.get("name", "")
        if len(name) < 1 or len(name) > 100:
            errors.append("공급사 이름은 1-100자 사이여야 합니다")

        # 설명 길이 검증
        description = supplier_data.get("description", "")
        if len(description) > 500:
            errors.append("설명은 500자를 초과할 수 없습니다")

        # URL 형식 검증
        base_url = supplier_data.get("base_url")
        if base_url and not ProductValidator._is_valid_url(base_url):
            errors.append("유효한 URL 형식이 아닙니다")

        if errors:
            raise ValidationError(f"공급사 데이터 검증 실패: {'; '.join(errors)}")

        return supplier_data

class ValidationUtils:
    """검증 유틸리티"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """문자열 정리"""
        if not value:
            return ""

        # HTML 태그 제거 (기본적인 것만)
        value = re.sub(r'<[^>]+>', '', value)

        # 앞뒤 공백 제거
        value = value.strip()

        # 길이 제한
        if len(value) > max_length:
            value = value[:max_length]

        return value

    @staticmethod
    def sanitize_number(value: Any, min_val: float = 0, max_val: float = float('inf')) -> Optional[float]:
        """숫자 정리 및 검증"""
        if value is None:
            return None

        try:
            num_value = float(value)
            if num_value < min_val or num_value > max_val:
                return None
            return num_value
        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_margin_rate(margin_rate: Any, default_rate: float = 0.3) -> float:
        """마진율 정규화"""
        sanitized = ValidationUtils.sanitize_number(margin_rate, 0.01, 0.95)
        return sanitized if sanitized is not None else default_rate
