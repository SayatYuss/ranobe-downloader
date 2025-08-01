#!/bin/bash

# Функция для отображения сообщения об ошибке и выходе
error_exit() {
    echo "ОШИБКА: $1"
    echo "================================================"
    echo "Пожалуйста, исправьте ошибку и попробуйте снова."
    echo "Если проблема сохраняется, создайте issue на GitHub:"
    echo "https://github.com/yourusername/ranobe-downloader/issues"
    echo "================================================"
    exit 1
}

# Очистка экрана и отображение заголовка
clear
echo "================================================"
echo "   Запуск RanobeLib Downloader для macOS/Linux"
echo "================================================"
echo

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    error_exit "Python 3 не установлен. Пожалуйста, установите Python 3.8 или новее."
fi

# Проверка версии Python
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
IFS='.' read -ra VERSION_PARTS <<< "$PYTHON_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}

if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]; }; then
    error_exit "Требуется Python 3.8 или выше. Установленная версия: $PYTHON_VERSION"
fi

# Проверка и создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv || error_exit "Не удалось создать виртуальное окружение"
fi

# Активация виртуального окружения
echo "Активация виртуального окружения..."
source venv/bin/activate || error_exit "Не удалось активировать виртуальное окружение"

# Установка/обновление pip
echo "Обновление pip..."
python3 -m pip install --upgrade pip || error_exit "Не удалось обновить pip"

# Установка зависимостей
if [ -f "requirements.txt" ]; then
    echo "Установка необходимых библиотек..."
    pip install -r requirements.txt || error_exit "Не удалось установить зависимости"
else
    error_exit "Файл requirements.txt не найден!"
fi

# Запуск приложения
echo "Запуск программы..."
python3 main.py

# Деактивация виртуального окружения
deactivate

echo
echo "================================================"
echo "   Программа завершена. Можно закрыть терминал"
echo "================================================"