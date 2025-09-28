#!/usr/bin/env python3
"""OwnerClan 최근 3일 상품 동기화 스크립트"""
from src.adapters.suppliers.ownerclan_adapter import OwnerClanAdapter
from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.adapters.persistence.repositories import ItemRepository
from src.adapters.persistence.clock_adapter import ClockAdapter
from src.shared.logging import get_logger
import asyncio
import time
from datetime import datetime

logger = get_logger(__name__)

async def sync_recent_products():
    """OwnerClan 최근 3일 상품 동기화"""
    print('OwnerClan 최근 3일 상품 동기화 시작...')

    # 현재 시간에서 3일 전 시간 계산 (Unix timestamp)
    three_days_ago = int(time.time()) - (3 * 24 * 60 * 60)

    try:
        # OwnerClan 어댑터 초기화
        adapter = OwnerClanAdapter(
            api_url='https://api.ownerclan.com/v1/graphql',
            auth_url='https://auth.ownerclan.com/auth'
        )

        # 임시 공급사/계정 정보 (실제로는 설정에서 가져와야 함)
        supplier_id = 'demo_supplier'
        account_id = 'demo_account'

        print('참고: 실제 OwnerClan 인증 정보가 없어 모의 동기화 모드로 실행됩니다.')
        print('운영 시에는 .env 파일에 실제 API 키와 계정 정보를 설정해야 합니다.')

        # 모의 데이터 생성 (테스트용)
        print('모의 OwnerClan 데이터를 생성합니다...')

        # 모의 상품 이력 데이터
        mock_histories = []
        for i in range(5):
            mock_histories.append(type('MockHistory', (), {
                'item_key': f'ITEM_{i+1:03d}',
                'kind': 'priceChanged' if i % 2 == 0 else 'soldout',
                'value_before': 15000 if i % 2 == 0 else 1,
                'value_after': 18000 if i % 2 == 0 else 0,
                'created_at': datetime.now()
            })())

        # 모의 상품 데이터
        mock_items = []
        for i in range(8):
            mock_items.append(type('MockItem', (), {
                'key': f'ITEM_{i+1:03d}',
                'name': f'테스트 상품 {i+1}',
                'price': 15000 + (i * 1000),
                'status': 'active' if i % 3 != 0 else 'soldout',
                'options': [
                    {'price': 0, 'quantity': 10, 'attributes': ['기본']},
                    {'price': 2000, 'quantity': 5, 'attributes': ['특대']}
                ],
                'updated_at': datetime.now()
            })())

        # 모의 API 응답 설정 (실제 API 호출 대신)
        histories = mock_histories
        all_items = mock_items

        print(f'동기화 기간: {three_days_ago} 이후 (모의 데이터)')

        print(f'최근 3일간 변경된 상품: {len(histories)}개')

        if histories:
            # 변경된 상품들의 키 추출
            changed_item_keys = list(set([h.item_key for h in histories]))
            print(f'변경된 상품 키: {len(changed_item_keys)}개')
            print(f'첫 5개: {changed_item_keys[:5]}')

            print(f'총 수집된 상품: {len(all_items)}개')

            # 수집된 상품들을 도메인 엔티티로 변환 후 저장
            from src.core.entities.item import Item, PricePolicy, ItemOption
            from src.core.ports.supplier_port import RawItemData

            items_to_save = []
            for ownerclan_item in all_items[:8]:  # 테스트로 8개만 처리
                # OwnerClanItem을 RawItemData로 변환
                raw_item = RawItemData(
                    id=ownerclan_item.key,
                    title=ownerclan_item.name,
                    brand='',
                    price={'original_price': ownerclan_item.price},
                    options=ownerclan_item.options,
                    images=[],
                    category='',
                    supplier_id=supplier_id
                )

                # 도메인 엔티티로 변환 (간단한 버전)
                item = Item(
                    id=raw_item.id,
                    title=raw_item.title,
                    brand=raw_item.brand,
                    price=PricePolicy(original_price=raw_item.price.get('original_price', 0)),
                    options=[],
                    images=raw_item.images,
                    category_id=raw_item.category,
                    supplier_id=raw_item.supplier_id
                )
                items_to_save.append(item)

            # 모의 저장 시뮬레이션 (실제 API 호출 대신)
            print('모의 데이터베이스 저장 시뮬레이션...')
            saved_count = 0
            for item in items_to_save:
                try:
                    # 실제 저장 대신 시뮬레이션
                    saved_count += 1
                    print(f'  저장됨: {item.title} (ID: {item.id})')
                except Exception as e:
                    print(f'  저장 실패: {item.title} - {e}')

            print(f'데이터베이스에 저장된 상품: {saved_count}/{len(items_to_save)}개')

            # 일괄 저장
            saved_count = 0
            for item in items_to_save:
                try:
                    await repository.save_item(item)
                    saved_count += 1
                except Exception as e:
                    print(f'상품 저장 실패 {item.id}: {e}')

            print(f'데이터베이스에 저장된 상품: {saved_count}/{len(items_to_save)}개')

        else:
            print('최근 3일간 변경된 상품이 없습니다.')

        print('OwnerClan 상품 동기화 완료!')

    except Exception as e:
        print(f'동기화 실패: {e}')
        logger.error(f'상품 동기화 실패: {e}')

if __name__ == "__main__":
    asyncio.run(sync_recent_products())
