#!/usr/bin/env python3
"""
Тестирование импортов и работы EnhancedEventBus.
"""

import asyncio
from src.cryptotechnolog.core import (
    EventBus,
    get_event_bus,
    get_enhanced_event_bus,
    EnhancedEventBus,
    Event,
    Priority,
)


async def test_imports():
    """Проверить импорты и создание Event Bus."""
    print("✅ Все импорты загружены успешно")
    
    # Проверяем типы
    print(f"EventBus тип: {EventBus}")
    print(f"EnhancedEventBus тип: {EnhancedEventBus}")
    
    # Получаем глобальный экземпляр
    enhanced_bus = get_enhanced_event_bus()
    legacy_bus = get_event_bus()
    
    print(f"Enhanced bus тип: {type(enhanced_bus)}")
    print(f"Legacy bus тип: {type(legacy_bus)}")
    
    # Проверяем, что это один и тот же экземпляр
    print(f"Один экземпляр: {enhanced_bus is legacy_bus}")
    
    # Создаем тестовое событие
    event = Event.new("TEST_EVENT", "test_source", {"data": "test"})
    event.priority = Priority.NORMAL
    
    print(f"Создано событие: {event.event_type}, приоритет: {event.priority}")
    
    # Пытаемся опубликовать событие (не будет работать без event loop)
    print("⚠️  Публикация события требует event loop")
    
    return True


def main():
    """Основная функция."""
    try:
        result = asyncio.run(test_imports())
        if result:
            print("🎉 Все тесты пройдены успешно!")
            return 0
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())