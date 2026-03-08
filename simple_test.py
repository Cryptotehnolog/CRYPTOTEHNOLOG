#!/usr/bin/env python3
"""Упрощенный тест базовой функциональности."""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.cryptotechnolog.core.event import Event, Priority
    from src.cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
    print("✅ Импорты успешны")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)


async def test_basic() -> None:
    """Тест базовой функциональности."""
    print("\n🚀 Тест базовой функциональности Enhanced Event Bus")
    print("=" * 60)
    
    # Создать Event Bus без persistence (для простоты)
    bus = EnhancedEventBus(
        enable_persistence=False,
        redis_url=None,
        rate_limit=1000,
        backpressure_strategy="drop_low"
    )
    
    try:
        await bus.start()
        print("✅ EnhancedEventBus запущен")
        
        # Подписаться на события
        receiver = bus.subscribe()
        print("✅ Подписчик создан")
        
        # Опубликовать событие
        event = Event.new("TEST_EVENT", "TEST_SOURCE", {"test": "data"})
        event.priority = Priority.NORMAL
        
        success = await bus.publish(event)
        print(f"✅ Событие опубликовано: {success}")
        
        # Получить событие
        received = await asyncio.wait_for(receiver.recv_timeout(1.0), timeout=2.0)
        if received:
            print(f"✅ Событие получено: {received.event_type}")
            print(f"  Приоритет: {received.priority.value}")
            print(f"  Источник: {received.source}")
        else:
            print("❌ Событие не получено")
        
        # Проверить метрики
        metrics = bus.get_metrics()
        print(f"📊 Метрики: {metrics['bus_metrics']}")
        
        await bus.shutdown()
        print("✅ EnhancedEventBus завершен корректно")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        try:
            await bus.shutdown()
        except:
            pass


async def test_priorities() -> None:
    """Тест приоритетов."""
    print("\n📊 Тест системы приоритетов")
    print("=" * 60)
    
    bus = EnhancedEventBus(
        enable_persistence=False,
        rate_limit=1000,
        backpressure_strategy="drop_low"
    )
    
    try:
        await bus.start()
        
        receiver = bus.subscribe()
        received_order = []
        
        # Функция для сбора событий
        async def collect_events(count: int):
            for _ in range(count):
                event = await receiver.recv_timeout(0.5)
                if event:
                    received_order.append((event.priority.value, event.event_type))
        
        # Запустить сборщик
        collector = asyncio.create_task(collect_events(4))
        
        # Опубликовать события в обратном порядке приоритета
        priorities = [
            (Priority.LOW, "LOW_EVENT"),
            (Priority.NORMAL, "NORMAL_EVENT"),
            (Priority.HIGH, "HIGH_EVENT"),
            (Priority.CRITICAL, "CRITICAL_EVENT"),
        ]
        
        for priority, event_type in priorities:
            event = Event.new(event_type, "TEST", {"priority": priority.value})
            event.priority = priority
            await bus.publish(event)
            print(f"📨 Опубликовано: {event_type} ({priority.value})")
        
        # Дождаться сбора
        await asyncio.wait_for(collector, timeout=3.0)
        
        print(f"\n📊 Порядок получения: {received_order}")
        
        # Проверить, что CRITICAL получен первым (хотя опубликован последним)
        if received_order and received_order[0][0] == "critical":
            print("✅ CRITICAL событие получено первым (система приоритетов работает)")
        else:
            print(f"⚠️  Первым получен {received_order[0][0] if received_order else 'None'}")
        
        await bus.shutdown()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        try:
            await bus.shutdown()
        except:
            pass


async def main() -> None:
    """Основная функция."""
    print("🔧 УПРОЩЕННЫЙ ТЕСТ ENHANCED EVENT BUS")
    print("=" * 60)
    
    await test_basic()
    await test_priorities()
    
    print("\n" + "=" * 60)
    print("🏁 ТЕСТ ЗАВЕРШЕН")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())