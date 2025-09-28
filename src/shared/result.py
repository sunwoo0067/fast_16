"""Result/Either 모나드 패턴"""
from typing import TypeVar, Generic, Union, Callable, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

T = TypeVar('T')
E = TypeVar('E')


@dataclass
class Success(Generic[T]):
    """성공 결과"""
    value: T

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

    def get_value(self) -> T:
        return self.value

    def get_error(self) -> None:
        return None

    def map(self, fn: Callable[[T], Any]) -> 'Result[Any]':
        try:
            return Success(fn(self.value))
        except Exception as e:
            return Failure(str(e))

    def flat_map(self, fn: Callable[[T], 'Result[Any]']) -> 'Result[Any]':
        try:
            return fn(self.value)
        except Exception as e:
            return Failure(str(e))


@dataclass
class Failure(Generic[T]):
    """실패 결과"""
    error: str
    value: T = None

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

    def get_value(self) -> T:
        return self.value

    def get_error(self) -> str:
        return self.error

    def map(self, fn: Callable[[T], Any]) -> 'Result[Any]':
        return Failure(self.error, self.value)

    def flat_map(self, fn: Callable[[T], 'Result[Any]']) -> 'Result[Any]':
        return Failure(self.error, self.value)


# Union type for type hints
Result = Union[Success[T], Failure[T]]


def success(value: T) -> Result[T]:
    """성공 결과 생성"""
    return Success(value)


def failure(error: str, value: T = None) -> Result[T]:
    """실패 결과 생성"""
    return Failure(error, value)


def try_catch(fn: Callable[[], T], error_message: str = "오류 발생") -> Result[T]:
    """함수 실행 결과를 Result로 래핑"""
    try:
        return Success(fn())
    except Exception as e:
        return Failure(f"{error_message}: {str(e)}")
