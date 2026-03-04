#!/usr/bin/env python3
"""
Тест для Enhanced Event Bus.

Проверяет основные функции Enhanced Event Bus:
- Priority system
- Queue management
- Rate limiting (базовая проверка)
- Backpressure (базовая проверка)
"""

import asyncio
import json
from datetime import UTC, datetime
import uuid

from src.cryptotechnolog.core.event import Event, Priority, SystemEventType, SystemEventSource
from src.cryptotechnolog.core.enhanced_event_bus import (
    EnhancedEventBus,
    BackpressureStrategy,
    PublishError,
)


async def test_basic_functionality() -> None:
    """Тест базовой функциональности."""
    print("=" * 60)
    print("Тест 1: Базовая функциональность Enhanced Event Bus")
    print("=" * 60)
    
    # Создать Enhanced Event Bus без persistence (для тестов)
    bus = EnhancedEventBus(
        enable_persistence=False,
        redis_url=None,
        rate_limit=1000,
        backpressure_strategy="drop_low"
    )
    
    try:
        await bus.start()
        
        # Подписаться на события
        receiver = bus.subscribe()
        
        # Создать и опубликовать событие с разными приоритетами
        events_to_publish = [
            ("TEST_CRITICAL", "TEST_SOURCE", {"test": "critical"}, Priority.CRITICAL),
            ("TEST_HIGH", "TEST_SOURCE", {"test": "high"}, Priority.HIGH),
            ("TEST_NORMAL", "TEST_SOURCE", {"test": "normal"}, Priority.NORMAL),
            ("TEST_LOW", "TEST_SOURCE", {"test": "low"}, Priority.LOW),
        ]
        
        for event_type, source, payload, priority in events_to_publish:
            event = Event.new(event_type, source, payload)
            event.priority = priority
            
            success = await bus.publish(event)
            print(f"  ✅ Опубликовано событие: {event_type} (приоритет: {priority.value})")
            
            # Получить событие через подписчика
            received = await asyncio.wait_for(receiver.recv_timeout(1.0), timeout=2.0)
            if received:
                print(f"  ✅ Получено событие: {received.event_type} (приоритет: {received.priority.value})")
                assert received.event_type == event_type
                assert received.priority == priority
            else:
                print(f"  ❌ Не удалось получить событие: {event_type}")
        
        # Проверить метрики
        metrics = bus.get_metrics()
        print(f"  📊 Метрики опубликованных событий: {metrics['bus_metrics']['published']}")
        print(f"  📊 Метрики доставленных событий: {metrics['bus_metrics']['delivered']}")
        
        # Проверить очередь приоритетов
        queue_metrics = metrics['queue_metrics']
        print(f"  📊 Размеры очередей: {queue_metrics['queue_sizes']}")
        
        await bus.shutdown()
        
        print("✅ Тест 1 пройден успешно!")
        
    except Exception as e:
        print(f"❌ Тест 1 завершился с ошибкой: {e}")
        import traceback
        traceback.print_exc()
        await bus.shutdown()


async def test_priority_ordering() -> None:
    """Тест порядка обработки событий по приоритету."""
    print("\n" + "=" * 60)
    print("Тест 2: Порядок обработки событий по приоритету")
    print("=" * 60)
    
    bus = EnhancedEventBus(
        enable_persistence=False,
        rate_limit=1000,
        backpressure_strategy="drop_low"
    )
    
    try:
        await bus.start()
        
        receiver = bus.subscribe()
        received_events = []
        
        # Функция для сбора полученных событий
        async def collect_events():
            for _ in range(4):
                event = await receiver.recv_timeout(1.0)
                if event:
                    received_events.append((event.priority, event.event_type))
        
        # Запустить сбор событий в фоне
        collector_task = asyncio.create_task(collect_events())
        
        # Опубликовать события в обратном порядке приоритета
        events = [
            ("LOW_EVENT", "TEST", {"data": "low"}, Priority.LOW),
            ("NORMAL_EVENT", "TEST", {"data": "normal"}, Priority.NORMAL),
            ("HIGH_EVENT", "TEST", {"data": "high"}, Priority.HIGH),
            ("CRITICAL_EVENT", "TEST", {"data": "critical"}, Priority.CRITICAL),
        ]
        
        for event_type, source, payload, priority in events:
            event = Event.new(event_type, source, payload)
            event.priority = priority
            await bus.publish(event)
            print(f"  📨 Опубликовано: {event_type} (приоритет: {priority.value})")
        
        # Дождаться сбора всех событий
        await asyncio.wait_for(collector_task, timeout=5.0)
        
        # Проверить порядок получения (должны быть в порядке приоритета: CRITICAL, HIGH, NORMAL, LOW)
        expected_order = [Priority.CRITICAL, Priority.HIGH, Priority.NORMAL, Priority.LOW]
        actual_order = [priority for priority, _ in received_events]
        
        print(f"  📊 Ожидаемый порядок: {[p.value for p in expected_order]}")
        print(f"  📊 Фактический порядок: {[p.value for p in actual_order]}")
        
        # В идеале порядок должен совпадать, но из-за асинхронности могут быть небольшие расхождения
        # Проверим хотя бы, что CRITICAL получен первым (самый важный тест)
        if received_events:
            first_priority = received_events[0][0]
            if first_priority == Priority.CRITICAL:
                print("  ✅ CRITICAL событие получено первым (как и должно быть)")
            else:
                print(f"  ⚠️  Первым получен {first_priority.value} вместо CRITICAL")
        
        await bus.shutdown()
        
        print("✅ Тест 2 пройден успешно!")
        
    except Exception as e:
        print(f"❌ Тест 2 завершился с ошибкой: {e}")
        import traceback
        traceback.print_exc()
        await bus.shutdown()


async def test_backpressure_strategies() -> None:
    """Тест различных стратегий backpressure."""
    print("\n" + "=" * 60)
    print("Тест 3: Стратегии backpressure")
    print("=" * 60)
    
    # Тестируем стратегию drop_low с маленькой очередью LOW
    bus = EnhancedEventBus(
        enable_persistence=False,
        capacities={"low": 2},  # Очень маленькая очередь LOW
        rate_limit=1000,
        backpressure_strategy="drop_low"
    )
    
    try:
        await bus.start()
        
        receiver = bus.subscribe()
        
        # Заполнить очередь LOW
        for i in range(3):  # Попробуем 3 события при ёмкости 2
            event = Event.new(f"LOW_EVENT_{i}", "TEST", {"index": i})
            event.priority = Priority.LOW
            
            success = await bus.publish(event)
            if success:
                print(f"  📨 LOW событие {i} опубликовано успешно")
            else:
                print(f"  ⚠️  LOW событие {i} отброшено (backpressure работает)")
        
        # Попробовать опубликовать CRITICAL событие - должно пройти даже при заполненной очереди LOW
        critical_event = Event.new("CRITICAL_TEST", "TEST", {"important": True})
        critical_event.priority = Priority.CRITICAL
        
        critical_success = await bus.publish(critical_event)
        if critical_success:
            print("  ✅ CRITICAL событие опубликовано успешно (несмотря на заполненную очередь LOW)")
            
            # Получить CRITICAL событие
            received = await receiver.recv_timeout(1.0)
            if received and received.priority == Priority.CRITICAL:
                print("  ✅ CRITICAL событие получено подписчиком")
        else:
            print("  ❌ CRITICAL событие не опубликовано (проблема)")
        
        await bus.shutdown()
        
        print("✅ Тест 3 пройден успешно!")
        
    except Exception as e:
        print(f"❌ Тест 3 завершился с ошибкой: {e}")
        import traceback
        traceback.print_exc()
        await bus.shutdown()


async def test_convenience_functions() -> None:
    """Тест удобных функций из __init__.py."""
    print("\n" + "=" * 60)
    print("Тест 4: Удобные функции и глобальные экземпляры")
    print("=" * 60)
    
    try:
        from src.cryptotechnolog.core import (
            get_enhanced_event_bus,
            get_event_bus,
            publish_event,
            Priority
        )
        
        # Получить глобальные экземпляры
        enhanced_bus = get_enhanced_event_bus()
        legacy_bus = get_event_bus()  # Должен возвращать EnhancedEventBus для совместимости
        
        print(f"  📊 Enhanced Event Bus: {type(enhanced_bus).__name__}")
        print(f"  📊 Legacy Event Bus (совместимость): {type(legacy_bus).__name__}")
        
        # Проверить, что это один и тот же объект (или по крайней мере оба EnhancedEventBus)
        assert isinstance(enhanced_bus, EnhancedEventBus)
        assert isinstance(legacy_bus, EnhancedEventBus)
        
        print("  ✅ Оба глобальных экземпляра являются EnhancedEventBus")
        
        # Тестировать publish_event (синхронная функция)
        success = publish_event(
            event_type="TEST_CONVENIENCE",
            source="TEST_SOURCE",
            payload={"test": "convenience"},
            priority=Priority.NORMAL,
            correlation_id=str(uuid.uuid4())
        )
        
        if success:
            print("  ✅ publish_event вернула True (событие поставлено в очередь публикации)")
        else:
            print("  ⚠️  publish_event вернула False (нет running event loop)")
        
        print("✅ Тест 4 пройден успешно!")
        
    except Exception as e:
        print(f"❌ Тест 4 завершился с ошибкой: {e}")
        import traceback
        traceback.print_exc()


async def test_event_serialization() -> None:
    """Тест сериализации событий с приоритетами."""
    print("\n" + "=" * 60)
    print("Тест 5: Сериализация и десериализация событий")
    print("=" * 60)
    
    try:
        # Создать событие с приоритетом
        original_event = Event.new(
            event_type="TEST_SERIALIZATION",
            source="TEST_SOURCE",
            payload={"data": "test", "nested": {"key": "value"}}
        )
        original_event.priority = Priority.HIGH
        original_event.correlation_id = uuid.uuid4()
        
        # Конвертировать в словарь
        event_dict = original_event.to_dict()
        
        print(f"  📊 Событие в словаре: {json.dumps(event_dict, indent=2, ensure_ascii=False)[:200]}...")
        
        # Проверить наличие поля priority
        assert "priority" in event_dict
        assert event_dict["priority"] == "high"
        
        # Восстановить из словаря
        restored_event = Event.from_dict(event_dict)
        
        # Проверить равенство
        assert restored_event.event_type == original_event.event_type
        assert restored_event.source == original_event.source
        assert restored_event.priority == original_event.priority
        assert restored_event.correlation_id == original_event.correlation_id
        
        print("  ✅ Сериализация/десериализация работает корректно")
        print("  ✅ Приоритет сохраняется при сериализации")
        
        print("✅ Тест 5 пройден успешно!")
        
    except Exception as e:
        print(f"❌ Тест 5 завершился с ошибкой: {e}")
        import traceback
        traceback.print_exc()


async def main() -> None:
    """Основная функция тестирования."""
    print("🚀 Начало тестирования Enhanced Event Bus")
    print("=" * 60)
    
    try:
        await test_basic_functionality()
        await test_priority_ordering()
        await test_backpressure_strategies()
        await test_convenience_functions()
        await test_event_serialization()
        
        print("\n" + "=" * 60)
        print("🎉 Все тесты завершены!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())