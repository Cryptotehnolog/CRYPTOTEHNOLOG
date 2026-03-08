#!/usr/bin/env python3
"""
Минимальный тест для проверки EnhancedEventBus.
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_minimal() -> None:
    """Минимальный тест."""
    try:
        # Импортируем только необходимое
        from src.cryptotechnolog.core.event import Event, Priority
        from src.cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
        
        print("✅ Импорты успешны")
        
        # Создать Event Bus
        bus = EnhancedEventBus(
            enable_persistence=False,
            redis_url=None,
            rate_limit=1000,
            backpressure_strategy="drop_low"
        )
        
        print("✅ EnhancedEventBus создан")
        
        # Запустить
        await bus.start()
        print("✅ EnhancedEventBus запущен")
        
        # Создать подписчика
        receiver = bus.subscribe()
        print("✅ Подписчик создан")
        
        # Создать и опубликовать событие
        event = Event.new("TEST_EVENT", "TEST_SOURCE", {"test": "data"})
        event.priority = Priority.NORMAL
        
        success = await bus.publish(event)
        print(f"✅ Событие опубликовано: {success}")
        
        # Получить событие
        received = await asyncio.wait_for(receiver.recv_timeout(1.0), timeout=2.0)
        if received:
            print(f"✅ Событие получено: {received.event_type} (приоритет: {received.priority.value})")
        else:
            print("❌ Событие не получено")
        
        # Проверить метрики
        metrics = bus.get_metrics()
        print(f"📊 Опубликовано: {metrics['bus_metrics']['published']}")
        print(f"📊 Доставлено: {metrics['bus_metrics']['delivered']}")
        
        # Завершить
        await bus.shutdown()
        print("✅ EnhancedEventBus завершен корректно")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_minimal())