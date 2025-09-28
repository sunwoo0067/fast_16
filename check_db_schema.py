#!/usr/bin/env python3
"""데이터베이스 스키마 점검 스크립트"""
import sqlite3
import os

def check_database_schema():
    """데이터베이스 스키마 점검"""

    # 데이터베이스 파일 경로 확인
    db_files = ['dropshipping.db', 'test_dropshipping.db']
    db_path = None

    for file in db_files:
        if os.path.exists(file):
            db_path = file
            break

    if not db_path:
        print('❌ 데이터베이스 파일을 찾을 수 없습니다.')
        print('다음 파일들을 확인해보세요:')
        for file in db_files:
            print(f'   • {file}')
        return

    print(f'데이터베이스 파일 발견: {db_path}')

    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 테이블 목록 조회
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()

    print(f'\n생성된 테이블들 ({len(tables)}개):')
    print('=' * 50)

    for table in tables:
        table_name = table[0]
        print(f'\n테이블: {table_name}')

        # 각 테이블의 스키마 조회
        cursor.execute(f'PRAGMA table_info({table_name});')
        columns = cursor.fetchall()

        print('   컬럼 정보:')
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, is_pk = col
            pk_mark = ' (PK)' if is_pk else ''
            not_null_mark = ' NOT NULL' if not_null else ' NULL'
            default_mark = f' DEFAULT {default_val}' if default_val else ''
            print(f'     - {col_name} ({col_type}){pk_mark}{not_null_mark}{default_mark}')

        # 인덱스 정보 조회
        cursor.execute(f'PRAGMA index_list({table_name});')
        indexes = cursor.fetchall()

        if indexes:
            print('   인덱스 정보:')
            for idx in indexes:
                idx_seq, idx_name, is_unique, origin, partial = idx
                unique_mark = ' UNIQUE' if is_unique else ''
                print(f'     - {idx_name}{unique_mark}')

    # 데이터베이스 통계
    print(f'\n데이터베이스 통계:')
    print('=' * 50)

    for table in tables:
        table_name = table[0]
        cursor.execute(f'SELECT COUNT(*) FROM {table_name};')
        count = cursor.fetchone()[0]
        print(f'   {table_name}: {count}개 레코드')

    conn.close()
    print(f'\n데이터베이스 점검 완료!')

if __name__ == "__main__":
    check_database_schema()
