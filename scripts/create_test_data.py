#!/usr/bin/env python3
"""
드랍싸핑 셀러 관리 시스템 테스트 데이터 생성 스크립트
"""

import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.models.database import async_session, Supplier, SupplierAccount, Product
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

# 테스트 데이터 상수들
SUPPLIERS_DATA = [
    {
        "name": "중국 도매 공급업체 A",
        "description": "중국 심천 소재 전자제품 도매업체",
        "base_url": "https://api.supplier-a.com",
        "default_margin_rate": 0.35
    },
    {
        "name": "한국 중소기업 공급업체",
        "description": "국내 중소기업 제품 공급",
        "base_url": "https://api.korean-supplier.com",
        "default_margin_rate": 0.25
    },
    {
        "name": "해외 직구 플랫폼",
        "description": "해외 직구 상품 공급 플랫폼",
        "base_url": "https://api.overseas-direct.com",
        "default_margin_rate": 0.4
    }
]

ACCOUNTS_DATA = [
    {
        "account_id": "supplier_a_seller",
        "account_password": "secure_password_123",
        "default_margin_rate": 0.35
    },
    {
        "account_id": "korean_sme_seller",
        "account_password": "korean_password_456",
        "default_margin_rate": 0.25
    },
    {
        "account_id": "overseas_direct_seller",
        "account_password": "overseas_password_789",
        "default_margin_rate": 0.4
    }
]

CATEGORIES = [
    "스마트폰 액세서리", "블루투스 이어폰", "충전기", "케이블",
    "휴대폰 케이스", "보호필름", "거치대", "무선 충전기",
    "컴퓨터 주변기기", "키보드", "마우스", "웹캠",
    "게이밍 용품", "헤드셋", "스피커", "마이크",
    "스마트 홈", "스마트 플러그", "전구", "CCTV",
    "생활용품", "주방용품", "욕실용품", "청소용품"
]

SUPPLIERS = [
    "중국 공급업체", "한국 중소기업", "해외 직구", "알리바바", "아마존",
    "이베이", "테무", "쉬인", "타오바오", "라쿠텐"
]

class TestDataGenerator:
    """테스트 데이터 생성기"""

    def __init__(self):
        self.created_suppliers = []
        self.created_accounts = []
        self.created_products = []

    async def create_suppliers_and_accounts(self):
        """공급사 및 계정 생성"""
        async with async_session() as session:
            # 공급사 생성
            for supplier_data in SUPPLIERS_DATA:
                supplier = Supplier(
                    name=supplier_data["name"],
                    description=supplier_data["description"],
                    is_active=True
                )
                session.add(supplier)
                await session.flush()  # ID 생성을 위해
                self.created_suppliers.append(supplier)

                # 해당 공급사의 계정 생성
                account_data = ACCOUNTS_DATA[len(self.created_suppliers) - 1]
                account = SupplierAccount(
                    supplier_id=supplier.id,
                    account_id=account_data["account_id"],
                    account_password=account_data["account_password"],
                    access_token=f"test_token_{supplier.id}_{datetime.now().isoformat()}",
                    token_expires_at=datetime.now() + timedelta(days=30),
                    is_active=True,
                    default_margin_rate=account_data["default_margin_rate"],
                    sync_enabled=True
                )
                session.add(account)
                self.created_accounts.append(account)

                print(f"공급사 생성: {supplier.name} (ID: {supplier.id})")
                print(f"   계정 생성: {account.account_id}")

            await session.commit()

    async def create_products(self, count: int = 50):
        """테스트 상품 생성"""
        async with async_session() as session:
            for i in range(count):
                # 랜덤 공급사 선택
                supplier = random.choice(self.created_suppliers)
                account = next(acc for acc in self.created_accounts if acc.supplier_id == supplier.id)

                # 상품 데이터 생성
                product_data = self._generate_product_data(i, supplier, account)
                product = Product(**product_data)
                session.add(product)
                self.created_products.append(product)

                if (i + 1) % 10 == 0:
                    print(f"상품 생성 진행: {i + 1}/{count}")

            await session.commit()
            print(f"총 {len(self.created_products)}개 상품 생성 완료")

    def _generate_product_data(self, index: int, supplier: Supplier, account: SupplierAccount) -> Dict[str, Any]:
        """상품 데이터 생성"""
        category = random.choice(CATEGORIES)
        supplier_name = random.choice(SUPPLIERS)
        base_price = random.randint(5000, 100000)
        margin_rate = account.default_margin_rate or 0.3
        sale_price = int(base_price * (1 + margin_rate))

        return {
            "supplier_id": supplier.id,
            "supplier_account_id": account.id,
            "item_key": f"ITEM_{index:06d}",
            "name": f"{category} {random.choice(['프리미엄', '고급', '표준', '베이직'])} {index}",
            "price": base_price,
            "sale_price": sale_price,
            "margin_rate": margin_rate,
            "stock_quantity": random.randint(0, 1000),
            "max_stock_quantity": random.randint(100, 2000),
            "supplier_product_id": f"SUP_{index:06d}",
            "supplier_name": supplier_name,
            "supplier_url": f"https://supplier-{supplier_name.lower()}.com/product/{index}",
            "supplier_image_url": f"https://cdn.supplier.com/images/product_{index}.jpg",
            "estimated_shipping_days": random.randint(3, 14),
            "category_id": f"CAT_{random.randint(1, 20):03d}",
            "category_name": category,
            "description": f"이 상품은 {category} 카테고리의 고품질 제품입니다. {supplier_name}에서 공급받는 제품으로, 안정적인 품질을 보장합니다.",
            "images": [
                f"https://cdn.supplier.com/images/product_{index}_1.jpg",
                f"https://cdn.supplier.com/images/product_{index}_2.jpg",
                f"https://cdn.supplier.com/images/product_{index}_3.jpg"
            ],
            "options": {
                "color": ["블랙", "화이트", "실버"],
                "size": ["S", "M", "L"]
            } if random.random() > 0.5 else {},
            "is_active": random.random() > 0.1,  # 90% 활성화
            "sync_status": random.choice(["synced", "pending", "failed"]),
            "coupang_product_id": f"CP_{random.randint(100000, 999999)}" if random.random() > 0.5 else None,
            "manufacturer": random.choice(["삼성전자", "LG전자", "Apple", "Sony", "기타"])
        }

    async def create_coupang_supplier(self):
        """쿠팡 공급사 생성 (기존 코드 활용)"""
        from app.models.database import create_coupang_supplier
        try:
            supplier_id, account_id = await create_coupang_supplier()
            print(f"쿠팡 공급사 생성: supplier_id={supplier_id}, account_id={account_id}")
        except Exception as e:
            print(f"쿠팡 공급사 생성 실패: {e}")

    async def generate_csv_data(self):
        """CSV 파일용 데이터 생성"""
        csv_data = []

        for product in self.created_products:
            csv_data.append({
                "상품코드": product.item_key,
                "상품명": product.name,
                "공급가": product.price,
                "판매가": product.sale_price,
                "마진율": product.margin_rate,
                "재고": product.stock_quantity,
                "최대재고": product.max_stock_quantity or "",
                "공급처상품ID": product.supplier_product_id or "",
                "공급처명": product.supplier_name or "",
                "공급처URL": product.supplier_url or "",
                "이미지URL": product.supplier_image_url or "",
                "예상배송일": product.estimated_shipping_days or "",
                "카테고리ID": product.category_id or "",
                "카테고리명": product.category_name or "",
                "설명": product.description or "",
                "활성화": "예" if product.is_active else "아니오",
                "동기화상태": product.sync_status or "",
                "쿠팡상품ID": product.coupang_product_id or "",
                "제조사": product.manufacturer or ""
            })

        # CSV 파일 저장
        filename = f"test_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        import csv

        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if csv_data:
                fieldnames = csv_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)

        print(f"CSV 파일 생성 완료: {filename} ({len(csv_data)}개 상품)")
        return filename

    async def main():
        """메인 함수"""
        print("드랍싸핑 셀러 관리 시스템 테스트 데이터 생성 시작")

        # 로깅 설정
        setup_logging()

        generator = TestDataGenerator()

        try:
            # 1. 공급사 및 계정 생성
            print("\n1단계: 공급사 및 계정 생성")
            await generator.create_suppliers_and_accounts()

            # 2. 쿠팡 공급사 생성
            print("\n2단계: 쿠팡 공급사 생성")
            await generator.create_coupang_supplier()

            # 3. 테스트 상품 생성
            print("\n3단계: 테스트 상품 생성")
            await generator.create_products(count=100)

            # 4. CSV 파일 생성
            print("\n4단계: CSV 파일 생성")
            csv_filename = await generator.generate_csv_data()

            print("\n테스트 데이터 생성 완료!")
            print(f"   - 공급사: {len(generator.created_suppliers)}개")
            print(f"   - 계정: {len(generator.created_accounts)}개")
            print(f"   - 상품: {len(generator.created_products)}개")
            print(f"   - CSV 파일: {csv_filename}")

            print("\n이제 다음 명령어로 애플리케이션을 실행할 수 있습니다:")
            print("   python -m app.main")

        except Exception as e:
            print(f"테스트 데이터 생성 실패: {e}")
            logger.error(f"테스트 데이터 생성 실패: {e}")

if __name__ == "__main__":
    async def main():
        """메인 함수"""
        print("드랍싸핑 셀러 관리 시스템 테스트 데이터 생성 시작")

        # 로깅 설정
        setup_logging()

        generator = TestDataGenerator()

        try:
            # 1. 공급사 및 계정 생성
            print("\n1단계: 공급사 및 계정 생성")
            await generator.create_suppliers_and_accounts()

            # 2. 쿠팡 공급사 생성
            print("\n2단계: 쿠팡 공급사 생성")
            await generator.create_coupang_supplier()

            # 3. 테스트 상품 생성
            print("\n3단계: 테스트 상품 생성")
            await generator.create_products(count=100)

            # 4. CSV 파일 생성
            print("\n4단계: CSV 파일 생성")
            csv_filename = await generator.generate_csv_data()

            print("\n테스트 데이터 생성 완료!")
            print(f"   - 공급사: {len(generator.created_suppliers)}개")
            print(f"   - 계정: {len(generator.created_accounts)}개")
            print(f"   - 상품: {len(generator.created_products)}개")
            print(f"   - CSV 파일: {csv_filename}")

            print("\n이제 다음 명령어로 애플리케이션을 실행할 수 있습니다:")
            print("   python -m app.main")

        except Exception as e:
            print(f"테스트 데이터 생성 실패: {e}")
            logger.error(f"테스트 데이터 생성 실패: {e}")

    asyncio.run(main())
