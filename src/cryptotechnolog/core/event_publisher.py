"""
Event Publisher - Utilities for publishing events.

Вынесено из __init__.py для избежания циклических зависимостей.
"""

from __future__ import annotations

import uuid
from typing import Any

from .event import Event, Priority, SystemEventSource, SystemEventType
from ..config import get_logger


def get_event_bus():
    """Получить глобальный Event Bus."""
    from .enhanced_event_bus import EnhancedEventBus
    from . import _GlobalEventBusInstance
    return _GlobalEventBusInstance.get_instance()


def publish_event(
    event_type: str,
    source: str,
    payload: dict[str, object],
    priority: Priority = Priority.NORMAL,
    correlation_id: str | None = None,
    timeout: float = 5.0,
) -> bool:
    """
    Опубликовать событие через глобальный Enhanced Event Bus.

    ГАРАНТИИ:
    - Синхронный вызов (не требует async контекста)
    - Timeout для предотвращения блокировки
    - Логирование ошибок
    - Возвращает True только если событие успешно поставлено в очередь

    Аргументы:
        event_type: Тип события
        source: Источник события
        payload: Данные события
        priority: Приоритет события
        correlation_id: Опциональный correlation ID
        timeout: Таймаут в секундах для асинхронной публикации

    Возвращает:
        True если событие успешно поставлено в очередь, False в случае ошибки или таймаута
    """
    import asyncio
    
    logger = get_logger(__name__)
    
    # Создать событие
    event = Event.new(event_type, source, payload)
    event.priority = priority
    
    if correlation_id:
        event.correlation_id = uuid.UUID(correlation_id)

    # Получить глобальный Event Bus
    bus = get_event_bus()
    
    try:
        # Попробовать найти running loop
        loop = asyncio.get_running_loop()
        
        # Создать Future для публикации
        future = loop.create_task(bus.publish(event))
        
        # Ждать с таймаутом
        try:
            loop.call_later(timeout, future.cancel)
            success = asyncio.run_coroutine_threadsafe(
                future,
                loop
            ).result(timeout=timeout)
            
            if success:
                logger.debug(
                    "Событие опубликовано успешно",
                    event_type=event_type,
                    priority=priority.value,
                    source=source,
                )
            else:
                logger.warning(
                    "Событие не опубликовано (backpressure или отсутствие подписчиков)",
                    event_type=event_type,
                    priority=priority.value,
                    source=source,
                )
            
            return success
            
        except asyncio.TimeoutError:
            logger.error(
                "Таймаут публикации события",
                event_type=event_type,
                priority=priority.value,
                timeout=timeout,
            )
            future.cancel()
            return False
        except Exception as e:
            logger.error(
                "Ошибка публикации события",
                event_type=event_type,
                priority=priority.value,
                error=str(e),
            )
            return False
            
    except RuntimeError:
        # Нет running loop - это критическая ошибка для production
        # Для CRITICAL/HIGH событий нужно как-то сохранить
        logger.critical(
            "Нет running event loop для публикации события",
            event_type=event_type,
            priority=priority.value,
            source=source,
        )
        
        # Для CRITICAL событий можно попробовать синхронную публикацию
        if priority in (Priority.CRITICAL, Priority.HIGH):
            # Пытаемся создать новый event loop
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(
                    asyncio.wait_for(bus.publish(event), timeout=timeout)
                )
                loop.close()
                
                if success:
                    logger.info(
                        "CRITICAL/HIGH событие опубликовано в emergency loop",
                        event_type=event_type,
                        priority=priority.value,
                    )
                else:
                    logger.error(
                        "Не удалось опубликовать CRITICAL/HIGH событие в emergency loop",
                        event_type=event_type,
                        priority=priority.value,
                    )
                
                return success
            except Exception as e:
                logger.critical(
                    "Критическая ошибка публикации события (нет event loop)",
                    event_type=event_type,
                    priority=priority.value,
                    error=str(e),
                )
        
        return False


async def publish_alert(
    message: str,
    severity: str = "warning",
    component: str = "SYSTEM",
    priority: Priority = Priority.HIGH,
) -> bool:
    """
    Опубликовать alert через глобальный Enhanced Event Bus.

    Аргументы:
        message: Сообщение alert
        severity: Уровень серьёзности (info, warning, error, critical)
        component: Компонент-источник
        priority: Приоритет события

    Возвращает:
        True если alert опубликован
    """
    event = Event.new(
        SystemEventType.WATCHDOG_ALERT,
        SystemEventSource.WATCHDOG,
        {
            "message": message,
            "severity": severity,
            "component": component,
        },
    )
    event.priority = priority
    
    bus = get_event_bus()
    return await bus.publish(event)
