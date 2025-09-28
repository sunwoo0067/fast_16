#!/usr/bin/env python3
"""
OwnerClan 인증 정보 설정 스크립트
실제 OwnerClan 계정 정보를 안전하게 설정합니다.
"""

import os
import sys
import getpass
from pathlib import Path

def setup_ownerclan_credentials():
    """OwnerClan 인증 정보 설정"""
    print("🔐 OwnerClan 계정 정보 설정")
    print("=" * 50)
    print("실제 OwnerClan 계정 정보를 입력해주세요.")
    print("입력된 정보는 ownerclan_credentials.py 파일에 저장됩니다.")
    print()

    # 계정 ID 입력
    account_id = input("OwnerClan 계정 ID (예: b00679540): ").strip()
    if not account_id:
        print("❌ 계정 ID를 입력해주세요.")
        return False

    # 비밀번호 입력 (숨김)
    password = getpass.getpass("OwnerClan 비밀번호: ").strip()
    if not password:
        print("❌ 비밀번호를 입력해주세요.")
        return False

    # 확인
    password_confirm = getpass.getpass("비밀번호 확인: ").strip()
    if password != password_confirm:
        print("❌ 비밀번호가 일치하지 않습니다.")
        return False

    try:
        # ownerclan_credentials.py 파일 업데이트
        credentials_file = Path(__file__).parent / "ownerclan_credentials.py"

        with open(credentials_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 계정 ID와 비밀번호 업데이트
        content = content.replace(
            'return "b00679540"',
            f'return "{account_id}"'
        )
        content = content.replace(
            'return "your_actual_password_here"',
            f'return "{password}"'
        )

        with open(credentials_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ OwnerClan 인증 정보가 성공적으로 설정되었습니다!")
        print(f"   계정 ID: {account_id}")
        print("   API URL: https://api.ownerclan.com/v1/graphql")
        print("   인증 URL: https://auth.ownerclan.com/auth")
        print()
        print("🚀 이제 다음 명령어로 상품 수집을 시작할 수 있습니다:")
        print("   python scripts/collect_ownerclan_products.py")
        print()
        print("⚠️  보안을 위해 이 파일을 .gitignore에 추가해주세요.")

        return True

    except Exception as e:
        print(f"❌ 설정 저장 중 오류가 발생했습니다: {e}")
        return False

if __name__ == "__main__":
    success = setup_ownerclan_credentials()
    if not success:
        sys.exit(1)
