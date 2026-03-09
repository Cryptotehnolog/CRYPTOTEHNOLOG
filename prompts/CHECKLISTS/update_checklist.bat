@echo off
REM Скрипт для обновления чек-листа из папки CHECKLISTS
REM Выполняет скрипт из scripts/ и показывает результат

echo Обновление чек-листа проекта CRYPTOTEHNOLOG...
echo ============================================

cd ..\..

REM Проверяем существование скрипта
if not exist "scripts\extract_checklists_v2.py" (
    echo ОШИБКА: Скрипт не найден в scripts\extract_checklists_v2.py
    echo Убедитесь, что проект правильно настроен.
    pause
    exit /b 1
)

REM Запускаем Python скрипт
python scripts\extract_checklists_v2.py

echo.
echo ============================================
echo Чек-лист обновлен: prompts\CHECKLISTS\CHECKLISTS_DETAILED.md
echo Для ручного запуска: python scripts\extract_checklists_v2.py
echo ============================================

pause