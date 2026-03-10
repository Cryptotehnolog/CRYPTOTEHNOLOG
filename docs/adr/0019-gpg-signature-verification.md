# GPG Верификация подписей конфигурации

**Дата:** 2026-03-08  
**Статус:** Принято  

## Контекст
Фаза 4 проекта CRYPTOTEHNOLOG — реализация Config Manager.

- **Фаза:** 4 (Config Manager)
- **Класс стратегии:** SFT (Slow-Frequency Trading)
- **Компонент:** `src/cryptotechnolog/config/signers/gpg_signer.py`

Необходимо обеспечить целостность и аутентичность конфигурационных файлов через GPG подписи.

## Рассмотренные альтернативы
1. **Вариант А:** HMAC (простой, но менее безопасен)
2. **Вариант Б:** JSON Web Signatures (JWS)
3. **Вариант В:** X.509 сертификаты
4. **Вариант Г (выбрано):** GPG подписи (стандарт для инфраструктуры)

## Решение
Реализован GPGSigner с использованием библиотеки `python-gnupg`:

### GPGSigner
```python
class GPGSigner:
    """Проверка GPG подписей конфигурационных файлов."""
    
    def __init__(self, keyring_path: Path) -> None:
        self._gnupg = GPG(gnupghome=str(keyring_path))
    
    async def verify(self, path: Path) -> bool:
        """
        Проверить подпись файла.
        
        Returns:
            True если подпись валидна, иначе False.
        """
        with open(path, "rb") as f:
            data = f.read()
        
        # Проверка подписи
        result = self._gnupg.verify(data)
        return result.valid
```

### Интеграция с ConfigManager
```python
class ConfigManager:
    async def load(self) -> SystemConfig:
        """Загрузить и валидировать конфигурацию."""
        
        # 1. Загрузка
        raw_data = await self._loader.load(self._source)
        
        # 2. GPG верификация (если включена)
        if self._signer:
            is_valid = await self._signer.verify(self._source)
            if not is_valid:
                raise ConfigSecurityError("GPG подпись невалидна")
        
        # 3. Парсинг
        config_dict = self._parser.parse(raw_data)
        
        # 4. Валидация
        validated = self._validator.validate(config_dict)
        
        # 5. Сохранение версии
        await self._repository.save_version(
            version=validated.version,
            content_hash=validated.content_hash,
            config_yaml=raw_data.decode(),
            loaded_by="config_manager"
        )
        
        return validated
```

### Безопасность
- Применяется `ConfigSecurityError` при невалидной подписи
- Логирование попыток подделки
- Поддержка множественных ключей (keyring)

## Последствия
- **Плюсы:**
  - Стандартная криптография
  - Аутентичность источника
  - Широкое распространение в DevOps
- **Минусы:**
  - Управление ключами
  - Дополнительная зависимость (python-gnupg)

## Связанные ADR
- ADR-0017: Config Manager Architecture SOLID (основа)
- ADR-0018: Config Hot Reload Strategy (дополняет)
