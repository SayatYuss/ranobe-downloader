@echo off
title RanobeLib Downloader
color 0B
echo.
echo ================================================
echo    Запуск RanobeLib Downloader
echo ================================================
echo.

:: Проверка наличия Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не установлен или не добавлен в PATH
    echo Установите Python с сайта: https://www.python.org/downloads/
    echo Не забудьте отметить опцию "Add Python to PATH" при установке
    timeout /t 10
    exit /b 1
)

:: Проверка версии Python
for /f "tokens=2 delims=." %%a in ('python -c "import sys; print(sys.version_info[1])"') do (
    set minor=%%a
)
if %minor% lss 8 (
    echo ОШИБКА: Требуется Python версии 3.8 или выше
    echo Текущая версия: 
    python --version
    timeout /t 10
    exit /b 1
)

:: Создание виртуального окружения
if not exist "venv\" (
    echo Создание виртуального окружения...
    python -m venv venv
)

:: Активация виртуального окружения
call venv\Scripts\activate.bat

:: Установка зависимостей
echo Установка необходимых библиотек...
pip install -r requirements.txt

:: Запуск приложения
echo Запуск программы...
python main.py

:: Пауза перед закрытием
echo.
echo ================================================
echo    Программа завершена. Можно закрыть это окно
echo ================================================
pause