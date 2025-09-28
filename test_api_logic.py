import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
from app.models.database import async_session

async def test_api_logic():
    try:
        # 데이터베이스 세션 생성
        async with async_session() as db:
            # 더미 상품 데이터 생성
            categories = ["전자제품", "의류", "도서", "스포츠", "뷰티", "식품"]
            dummy_products = []

            for i in range(2):
                category = categories[i % len(categories)]
                base_price = (i + 1) * 1000

                dummy_product = {
                    "item_key": f"OC_API_{i+1}",
                    "name": f"{category} API상품 {i+1}",
                    "price": base_price,
                    "sale_price": int(base_price * 1.2),
                    "stock_quantity": 50 + i * 5,
                    "category_id": f"CAT_{i%5 + 1}",
                    "category_name": category,
                    "description": f"API를 통한 더미 상품 {i+1}입니다. {category} 카테고리의 테스트 상품입니다.",
                    "images": json.dumps([f"https://dummyimage.com/300x300/000/fff&text=상품{i+1}"]),
                    "options": json.dumps({"색상": ["블랙", "화이트"], "사이즈": ["S", "M", "L"]}),
                    "is_active": True,
                    "supplier_product_id": f"API_{i+1}",
                    "supplier_name": "OwnerClan",
                    "supplier_url": f"https://ownerclan.com/product/api_{i+1}",
                    "supplier_image_url": f"https://dummyimage.com/300x300/000/fff&text=상품{i+1}",
                    "estimated_shipping_days": 3,
                    "manufacturer": "OwnerClan",
                    "margin_rate": 0.3,
                    "sync_status": "synced"
                }
                dummy_products.append(dummy_product)

            # 더미 데이터를 데이터베이스에 저장
            saved_count = 0
            for product_data in dummy_products:
                try:
                    from app.models.database import Product
                    new_product = Product(
                        supplier_id=1,
                        **product_data
                    )
                    db.add(new_product)
                    saved_count += 1
                except Exception as e:
                    print(f"상품 저장 실패: {product_data.get('name', 'Unknown')} - {e}")

            await db.commit()
            print(f"성공: {saved_count}개 상품 저장 완료")

    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_logic())
