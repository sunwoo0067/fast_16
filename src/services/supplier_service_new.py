"""공급사 서비스 (헥사고날 아키텍처)"""
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from src.core.ports.repo_port import RepositoryPort
from src.core.ports.supplier_port import SupplierPort, SupplierCredentials
from src.shared.result import Result, Success, Failure
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SupplierService:
    """공급사 서비스 파사드"""

    def __init__(
        self,
        repository: RepositoryPort,
        supplier_port: SupplierPort
    ):
        self.repository = repository
        self.supplier_port = supplier_port

    async def create_supplier(
        self,
        name: str,
        description: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """공급사 생성"""
        try:
            # TODO: Supplier 엔티티 생성 및 저장
            # 현재는 간단한 구현
            supplier_data = {
                'id': 1,  # 실제로는 자동 생성
                'name': name,
                'description': description,
                'is_active': True,
                'api_key': api_key,
                'api_secret': api_secret,
                'base_url': base_url,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }

            return Success(supplier_data)

        except Exception as e:
            logger.error(f"공급사 생성 실패: {e}")
            return Failure(f"공급사 생성 실패: {str(e)}")

    async def get_all_suppliers(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: bool = True
    ):
        """공급사 목록 조회"""
        try:
            # TODO: 실제 리포지토리에서 조회
            suppliers = []  # 실제로는 데이터베이스에서 조회
            return Success(suppliers)

        except Exception as e:
            logger.error(f"공급사 목록 조회 실패: {e}")
            return Failure(f"공급사 목록 조회 실패: {str(e)}")

    async def get_supplier_by_id(self, supplier_id: int):
        """공급사 상세 조회"""
        try:
            # TODO: 실제 리포지토리에서 조회
            supplier = None  # 실제로는 데이터베이스에서 조회
            return Success(supplier)

        except Exception as e:
            logger.error(f"공급사 조회 실패: {e}")
            return Failure(f"공급사 조회 실패: {str(e)}")

    async def update_supplier(
        self,
        supplier_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        is_active: Optional[bool] = None
    ):
        """공급사 수정"""
        try:
            # TODO: 실제 리포지토리에서 업데이트
            supplier_data = {
                'id': supplier_id,
                'name': name,
                'description': description,
                'is_active': is_active,
                'api_key': api_key,
                'api_secret': api_secret,
                'base_url': base_url,
                'updated_at': datetime.now()
            }

            return Success(supplier_data)

        except Exception as e:
            logger.error(f"공급사 수정 실패: {e}")
            return Failure(f"공급사 수정 실패: {str(e)}")

    async def delete_supplier(self, supplier_id: int):
        """공급사 삭제"""
        try:
            # TODO: 실제 리포지토리에서 삭제
            return Success(True)

        except Exception as e:
            logger.error(f"공급사 삭제 실패: {e}")
            return Failure(f"공급사 삭제 실패: {str(e)}")

    async def create_supplier_account(
        self,
        supplier_id: int,
        account_name: str,
        username: str,
        password: str,
        default_margin_rate: Optional[float] = None,
        sync_enabled: bool = True
    ):
        """공급사 계정 생성"""
        try:
            # TODO: Account 엔티티 생성 및 저장
            account_data = {
                'id': 1,  # 실제로는 자동 생성
                'supplier_id': supplier_id,
                'account_name': account_name,
                'username': username,
                'password_encrypted': password,  # 실제로는 암호화해야 함
                'is_active': True,
                'usage_count': 0,
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'default_margin_rate': default_margin_rate or 0.3,
                'sync_enabled': sync_enabled,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }

            return Success(account_data)

        except Exception as e:
            logger.error(f"공급사 계정 생성 실패: {e}")
            return Failure(f"공급사 계정 생성 실패: {str(e)}")

    async def get_supplier_accounts(
        self,
        supplier_id: int,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ):
        """공급사 계정 목록 조회"""
        try:
            # TODO: 실제 리포지토리에서 조회
            accounts = []  # 실제로는 데이터베이스에서 조회
            total = 0
            return Success((accounts, total))

        except Exception as e:
            logger.error(f"공급사 계정 목록 조회 실패: {e}")
            return Failure(f"공급사 계정 목록 조회 실패: {str(e)}")

    async def test_supplier_connection(
        self,
        supplier_id: int,
        account_name: str
    ):
        """공급사 연결 테스트"""
        try:
            # 공급사 계정 조회
            account_result = await self.repository.get_supplier_account(
                str(supplier_id),
                account_name
            )

            if account_result is None:
                return Failure(f"공급사 계정을 찾을 수 없습니다: {account_name}")

            # 연결 테스트
            credentials = SupplierCredentials(
                supplier_id=str(supplier_id),
                account_id=account_name,
                username=account_result.username,
                password=""  # 실제로는 암호화된 비밀번호를 복호화해야 함
            )

            is_valid = await self.supplier_port.check_credentials(credentials)

            if is_valid:
                return Success({
                    'account_name': account_name,
                    'supplier_id': supplier_id,
                    'status': 'connected',
                    'message': '연결 성공'
                })
            else:
                return Failure("공급사 연결에 실패했습니다")

        except Exception as e:
            logger.error(f"공급사 연결 테스트 실패: {e}")
            return Failure(f"연결 테스트 실패: {str(e)}")
