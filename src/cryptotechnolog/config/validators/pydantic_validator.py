"""
Валидатор конфигурации через Pydantic.

Реализует интерфейс IConfigValidator для валидации конфигурации
с использованием Pydantic моделей.

Все docstrings на русском языке.
"""

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from cryptotechnolog.config.protocols import IConfigValidator

if TYPE_CHECKING:
    from cryptotechnolog.config.models import SystemConfig

T = TypeVar("T", bound=BaseModel)


class ValidationError(Exception):
    """
    Ошибка валидации конфигурации.

    Атрибуты:
        errors: Список ошибок валидации
    """

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        """
        Инициализировать ошибку валидации.

        Аргументы:
            errors: Список ошибок валидации
        """
        self.errors = errors
        message = self._format_errors(errors)
        super().__init__(message)

    @staticmethod
    def _format_errors(errors: list[dict[str, Any]]) -> str:
        """
        Форматировать ошибки в читаемый вид.

        Аргументы:
            errors: Список ошибок

        Returns:
            Отформатированная строка ошибок
        """
        lines = ["Ошибки валидации конфигурации:"]
        for err in errors:
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Неизвестная ошибка")
            err_type = err.get("type", "unknown")
            lines.append(f"  - {loc}: {msg} ({err_type})")
        return "\n".join(lines)


class PydanticValidator(IConfigValidator):
    """
    Валидатор конфигурации через Pydantic модели.

    Принимает словарь с конфигурацией и валидирует его
    через указанную Pydantic модель.

    Пример использования:
        validator = PydanticValidator(schema=SystemConfig)
        config = validator.validate(data)
    """

    def __init__(self, schema: type[BaseModel]) -> None:
        """
        Инициализировать валидатор.

        Аргументы:
            schema: Pydantic модель для валидации
        """
        self._schema = schema

    def validate(self, data: dict[str, Any]) -> "SystemConfig":
        """
        Валидировать данные и вернуть типизированную модель.

        Аргументы:
            data: Словарь с конфигурацией

        Returns:
            Валидированная модель SystemConfig

        Raises:
            ValidationError: При ошибке валидации
        """
        if not isinstance(data, dict):
            raise ValidationError([
                {
                    "loc": (),
                    "msg": f"Ожидался словарь, получен {type(data).__name__}",
                    "type": "type_error",
                }
            ])

        try:
            # Валидируем данные через Pydantic
            return self._schema.model_validate(data)  # type: ignore[return-value]

        except PydanticValidationError as e:
            # Преобразуем ошибки Pydantic в наш формат
            errors = [
                {
                    "loc": err["loc"],
                    "msg": err["msg"],
                    "type": err["type"],
                    "input": str(err.get("input", ""))[:100],  # Ограничиваем вывод
                }
                for err in e.errors()
            ]
            raise ValidationError(errors) from e
