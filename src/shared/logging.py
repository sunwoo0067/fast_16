"""구조화된 로깅 유틸리티"""
import logging
import logging.config
from typing import Optional
import sys


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """로거 인스턴스 반환"""

    # 기본 로그 설정
    if not level:
        level = "INFO"

    # 기본 로그 설정
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'stream': sys.stdout
            }
        },
        'loggers': {
            name: {
                'handlers': ['console'],
                'level': level,
                'propagate': False
            }
        },
        'root': {
            'handlers': ['console'],
            'level': level
        }
    }

    logging.config.dictConfig(log_config)
    return logging.getLogger(name)


class LoggerMixin:
    """로거 믹스인 클래스"""

    @property
    def logger(self) -> logging.Logger:
        """인스턴스 로거 반환"""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_product_sync(logger: logging.Logger, action: str, product_id: str, details: Optional[dict] = None):
    """상품 동기화 로그"""
    log_data = {
        'action': action,
        'product_id': product_id,
        'timestamp': logging.Formatter().formatTime(logging.makeLogRecord({}))
    }

    if details:
        log_data.update(details)

    logger.info(f"Product sync: {action}", extra=log_data)


def log_api_request(logger: logging.Logger, method: str, endpoint: str, status_code: int, duration: float):
    """API 요청 로그"""
    log_data = {
        'http_method': method,
        'endpoint': endpoint,
        'status_code': status_code,
        'duration_ms': duration * 1000
    }

    logger.info(f"API Request: {method} {endpoint} - {status_code}", extra=log_data)
