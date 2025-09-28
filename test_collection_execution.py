import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from app.models.database import async_session
from app.services.ownerclan_collector import OwnerClanCollector

async def test_product_collection():
    async with async_session() as session:
        collector = OwnerClanCollector(session)

        print('[INFO] OwnerClan 상품 수집 시작...')
        result = await collector.collect_products(supplier_account_id=1, limit=5)

        print(f'[INFO] 수집 결과: {result}')

        if result['success']:
            print(f'[SUCCESS] {result["collected"]}개 상품 수집, {result["saved"]}개 저장 완료')

            # 통계 확인
            stats_result = await collector.get_collection_stats(1)
            if stats_result['success']:
                stats = stats_result['stats']
                print('[STATS] 현재 데이터베이스 상태:')
                print(f'  총 상품: {stats["total_products"]}개')
                print(f'  활성 상품: {stats["active_products"]}개')
                print(f'  동기화된 상품: {stats["synced_products"]}개')
        else:
            print(f'[ERROR] 수집 실패: {result["error"]}')

if __name__ == "__main__":
    asyncio.run(test_product_collection())
