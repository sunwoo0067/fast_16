import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from ownerclan_api import OwnerClanAPI
from ownerclan_credentials import OwnerClanCredentials

async def test_simple_query():
    try:
        # 인증 정보 가져오기
        credentials = OwnerClanCredentials.get_api_config()
        print(f'[INFO] 인증 정보: 계정={credentials["account_id"]}')

        api = OwnerClanAPI()
        async with api:
            # 인증
            auth_result = await api.authenticate(credentials['account_id'], credentials['password'])
            if not auth_result.get('success'):
                print(f'[ERROR] 인증 실패: {auth_result}')
                return

            token = auth_result['access_token']
            print('[SUCCESS] 인증 성공, 토큰 획득')

            # 간단한 쿼리부터 시도
            query = '''query {
                products(limit: 5, offset: 0) {
                    items {
                        id
                        name
                    }
                    totalCount
                }
            }'''

            response = await api.execute_query(query, {}, token)

            print(f'[DEBUG] API 응답: {response}')

            if response.get('success') and response.get('data'):
                products = response['data'].get('products', {}).get('items', [])
                total_count = response['data'].get('products', {}).get('totalCount', 0)

                print(f'[SUCCESS] 상품 조회 완료! 총 {total_count}개 중 {len(products)}개 조회')

                for i, product in enumerate(products, 1):
                    print(f'[PRODUCT {i}] ID: {product["id"]}, 이름: {product["name"]}')
            else:
                print(f'[ERROR] 상품 조회 실패: {response}')

    except Exception as e:
        print(f'[ERROR] 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_query())
