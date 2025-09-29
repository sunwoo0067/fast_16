import logging
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime
from app.core.config import get_settings

settings = get_settings()

class ProductSyncFormatter(logging.Formatter):
    """상품 동기화 전용 로그 포맷터"""

    def format(self, record):
        # 로그 레코드에 추가 정보가 있는 경우 JSON으로 변환
        if hasattr(record, 'product_data'):
            record.product_info = json.dumps(record.product_data, ensure_ascii=False, default=str)
        else:
            record.product_info = ""
            
        if hasattr(record, 'sync_stats'):
            record.sync_stats_info = json.dumps(record.sync_stats, ensure_ascii=False, default=str)
        else:
            record.sync_stats_info = ""
            
        return super().format(record)

class DropshippingFormatter(logging.Formatter):
    """드랍싸핑 관련 로그 포맷터"""

    def format(self, record):
        if hasattr(record, 'supplier_id'):
            record.supplier_context = f"SupplierID:{record.supplier_id}"
        if hasattr(record, 'product_count'):
            record.batch_context = f"Products:{record.product_count}"
        return super().format(record)

def setup_logging():
    """로깅 설정"""
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (상품 동기화 전용)
    try:
        import os
        os.makedirs("logs", exist_ok=True)

        file_handler = RotatingFileHandler(
            settings.log_file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(ProductSyncFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(product_info)s - %(sync_stats_info)s - %(message)s'
        ))
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"파일 로거 설정 실패: {e}")

    return root_logger

def get_logger(name: str):
    """이름으로 로거 반환"""
    return logging.getLogger(name)

class LoggerMixin:
    """로깅 믹스인 클래스"""

    @property
    def logger(self):
        """인스턴스별 로거"""
        class_name = self.__class__.__name__
        return get_logger(f"{class_name}")

def log_product_sync(product_data: dict, action: str, success: bool = True, error: str = None):
    """상품 동기화 로그 기록"""
    logger = get_logger("product_sync")

    extra_data = {
        'product_data': product_data,
        'action': action,
        'success': success,
        'timestamp': datetime.now().isoformat()
    }

    if success:
        logger.info(f"상품 동기화 성공: {action}", extra=extra_data)
    else:
        logger.error(f"상품 동기화 실패: {action} - {error}", extra=extra_data)

def log_sync_stats(stats: dict):
    """동기화 통계 로그 기록"""
    logger = get_logger("product_sync")

    extra_data = {
        'sync_stats': stats,
        'timestamp': datetime.now().isoformat()
    }

    logger.info("동기화 통계", extra=extra_data)

