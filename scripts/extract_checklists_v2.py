#!/usr/bin/env python3
"""
Улучшенный скрипт для извлечения всех чек-листов из промтов проекта CRYPTOTEHNOLOG.

Особенности:
- Автоопределение кодировки файлов (UTF-8, UTF-16, UTF-16-LE)
- Группировка по фазам (Фаза 0, Фаза 1 и т.д.)
- Умное извлечение чек-листов (распознает различные форматы)
- Статистика по фазам и общая
- Исключение файлов из директории plan/
"""

import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import sys

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CHECKLISTS_DIR = PROMPTS_DIR / "CHECKLISTS"
OUTPUT_FILE = CHECKLISTS_DIR / "CHECKLISTS_DETAILED.md"

# Регулярные выражения для поиска чек-листов
CHECKBOX_PATTERN = re.compile(r'^\s*[-*+]\s*\[([ x])\]\s*(.+)$', re.MULTILINE)
# Также ищем чекбоксы в таблицах
TABLE_CHECKBOX_PATTERN = re.compile(r'\|\s*\[([ x])\]\s*\|', re.MULTILINE)

# Определение фазы из имени файла
PHASE_PATTERN = re.compile(r'ФАЗА[_\s]*(\d+)', re.IGNORECASE)

# Кодировки для попытки
ENCODINGS = ['utf-8', 'utf-16', 'utf-16-le', 'cp1251']

def detect_file_encoding(filepath: Path) -> str:
    """
    Определяет кодировку файла.
    """
    # Простая эвристика: проверяем BOM
    with open(filepath, 'rb') as f:
        raw = f.read(4)
    
    if raw.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif raw.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    elif raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    else:
        # Пробуем декодировать с разными кодировками
        for encoding in ENCODINGS:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    f.read(1024)
                return encoding
            except UnicodeDecodeError:
                continue
    
    # По умолчанию UTF-8
    return 'utf-8'

def read_file_with_encoding(filepath: Path) -> Optional[str]:
    """
    Читает файл с автоматическим определением кодировки.
    """
    encoding = detect_file_encoding(filepath)
    try:
        return filepath.read_text(encoding=encoding)
    except Exception as e:
        print(f"  Ошибка чтения файла {filepath} с кодировкой {encoding}: {e}")
        return None

def extract_phase_info(filename: str, content: str) -> Tuple[int, str]:
    """
    Извлекает информацию о фазе из имени файла и содержимого.
    
    Возвращает (номер_фазы, название_фазы)
    """
    # Пытаемся извлечь номер фазы из имени файла
    match = PHASE_PATTERN.search(filename)
    phase_num = -1
    if match:
        phase_num = int(match.group(1))
    
    # Пытаемся найти название фазы в содержимом
    phase_name = filename.replace('.md', '').replace('_', ' ')
    
    # Ищем заголовок с названием фазы
    title_pattern = re.compile(r'^#+\s*(ФАЗА\s*\d+[:\s]*.*)$', re.MULTILINE | re.IGNORECASE)
    title_match = title_pattern.search(content)
    if title_match:
        phase_name = title_match.group(1)
    
    return phase_num, phase_name

def extract_checklists(content: str) -> Dict[str, List[str]]:
    """
    Извлекает чек-листы из содержимого файла.
    
    Возвращает словарь {раздел: [список_пунктов]}
    """
    sections = {}
    current_section = "Общие"
    current_items = []
    
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Определяем заголовки разделов (## или ###)
        if line.startswith('## ') and not line.startswith('###'):
            # Сохраняем предыдущий раздел
            if current_items:
                sections[current_section] = current_items.copy()
                current_items = []
            current_section = line[3:].strip()
            i += 1
            continue
        
        # Ищем чекбоксы в обычном формате
        checkbox_match = CHECKBOX_PATTERN.match(line)
        if checkbox_match:
            status = checkbox_match.group(1)
            text = checkbox_match.group(2)
            
            # Собираем многострочное описание
            full_text = text
            j = i + 1
            while j < len(lines) and lines[j].startswith('   '):
                full_text += ' ' + lines[j].strip()
                j += 1
            
            # Форматируем пункт
            item = f"- [{'x' if status == 'x' else ' '}] {full_text}"
            current_items.append(item)
            i = j
            continue
        
        # Ищем чекбоксы в таблицах (простой вариант)
        if '|' in line and '[ ]' in line or '[x]' in line:
            # Упрощенно: извлекаем всю строку как пункт
            simplified = line.replace('|', ' | ').strip()
            if simplified not in current_items:
                current_items.append(f"- [ ] {simplified}")
        
        i += 1
    
    # Добавляем последний раздел
    if current_items:
        sections[current_section] = current_items
    
    return sections

def format_statistics(phase_data: Dict[int, Dict]) -> str:
    """
    Форматирует статистику по фазам.
    """
    total_items = 0
    completed_items = 0
    phase_stats = []
    
    for phase_num in sorted(phase_data.keys()):
        phase_info = phase_data[phase_num]
        phase_total = phase_info['total']
        phase_completed = phase_info['completed']
        
        total_items += phase_total
        completed_items += phase_completed
        
        if phase_total > 0:
            percentage = (phase_completed / phase_total) * 100
            phase_stats.append(
                f"- Фаза {phase_num}: {phase_completed}/{phase_total} "
                f"({percentage:.1f}%)"
            )
    
    # Общая статистика
    stats = ["## 📊 Статистика выполнения\n"]
    
    if total_items > 0:
        overall_percentage = (completed_items / total_items) * 100
        stats.append(f"### Общая статистика\n")
        stats.append(f"- Всего пунктов: **{total_items}**")
        stats.append(f"- Выполнено: **{completed_items}**")
        stats.append(f"- Осталось: **{total_items - completed_items}**")
        stats.append(f"- Общий прогресс: **{overall_percentage:.1f}%**\n")
    
    stats.append("### Прогресс по фазам\n")
    stats.extend(phase_stats)
    
    return '\n'.join(stats)

def main():
    """Основная функция."""
    if not PROMPTS_DIR.exists():
        print(f"Директория промтов не найдена: {PROMPTS_DIR}")
        sys.exit(1)
    
    # Собираем все файлы промтов (кроме plan/)
    prompt_files = []
    for item in PROMPTS_DIR.iterdir():
        if item.is_file() and item.suffix == '.md':
            # Проверяем, не в директории ли plan
            if 'plan' not in str(item.relative_to(PROMPTS_DIR)):
                prompt_files.append(item)
    
    print(f"Найдено файлов промтов: {len(prompt_files)}")
    
    # Структура для хранения данных по фазам
    # phase_data[номер_фазы] = {
    #   'name': 'Название фазы',
    #   'files': [список файлов],
    #   'sections': {раздел: [пункты]},
    #   'total': общее_количество,
    #   'completed': выполнено
    # }
    phase_data = {}
    
    # Обрабатываем каждый файл
    for filepath in prompt_files:
        filename = filepath.name
        print(f"Обработка: {filename}")
        
        content = read_file_with_encoding(filepath)
        if content is None:
            continue
        
        # Извлекаем информацию о фазе
        phase_num, phase_name = extract_phase_info(filename, content)
        
        # Извлекаем чек-листы
        sections = extract_checklists(content)
        
        # Если не нашли фазу в имени файла, пытаемся определить из содержания
        if phase_num == -1:
            # Эвристика: ищем номер фазы в тексте
            for i in range(0, 10):
                if f"фаза {i}" in content.lower() or f"phase {i}" in content.lower():
                    phase_num = i
                    break
        
        # Создаем запись для фазы, если ее нет
        if phase_num not in phase_data:
            phase_data[phase_num] = {
                'name': phase_name,
                'files': [],
                'sections': {},
                'total': 0,
                'completed': 0
            }
        
        # Добавляем файл
        phase_data[phase_num]['files'].append(filename)
        
        # Объединяем разделы
        for section_name, items in sections.items():
            if section_name not in phase_data[phase_num]['sections']:
                phase_data[phase_num]['sections'][section_name] = []
            
            phase_data[phase_num]['sections'][section_name].extend(items)
            
            # Подсчет статистики
            for item in items:
                phase_data[phase_num]['total'] += 1
                if '[x]' in item:
                    phase_data[phase_num]['completed'] += 1
    
    # Формируем итоговый Markdown
    output_lines = []
    
    # Заголовок
    output_lines.append("# 📋 ДЕТАЛЬНЫЙ ЧЕК-ЛИСТ ПРОЕКТА CRYPTOTEHNOLOG\n")
    output_lines.append("*Автоматически сгенерировано из промтов проекта*\n")
    
    # Содержание по фазам
    for phase_num in sorted(phase_data.keys()):
        phase_info = phase_data[phase_num]
        
        if phase_num == -1:
            phase_header = "## 📄 Общие чек-листы"
        else:
            phase_header = f"## 🚀 Фаза {phase_num}: {phase_info['name']}"
        
        output_lines.append(phase_header)
        output_lines.append("")
        
        # Файлы, включенные в фазу
        if phase_info['files']:
            output_lines.append(f"**Файлы:** {', '.join(phase_info['files'])}\n")
        
        # Разделы
        for section_name, items in phase_info['sections'].items():
            if not items:
                continue
            
            output_lines.append(f"### {section_name}\n")
            
            for item in items:
                output_lines.append(item)
            
            output_lines.append("")
    
    # Статистика
    output_lines.append(format_statistics(phase_data))
    
    # Сохраняем
    OUTPUT_FILE.write_text('\n'.join(output_lines), encoding='utf-8')
    print(f"\n✅ Детализированные чек-листы сохранены в: {OUTPUT_FILE}")
    
    # Выводим краткую статистику
    print("\n📊 Краткая статистика:")
    for phase_num in sorted(phase_data.keys()):
        phase_info = phase_data[phase_num]
        if phase_info['total'] > 0:
            percentage = (phase_info['completed'] / phase_info['total']) * 100
            if phase_num == -1:
                print(f"  Общие: {phase_info['completed']}/{phase_info['total']} ({percentage:.1f}%)")
            else:
                print(f"  Фаза {phase_num}: {phase_info['completed']}/{phase_info['total']} ({percentage:.1f}%)")

if __name__ == "__main__":
    main()