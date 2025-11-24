"""
Logging configuration for the application.
"""
import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logging() -> None:
    """
    Настроить логирование для приложения.
    
    Конфигурирует loguru для вывода в консоль и файлы с ротацией.
    """
    # Удалить дефолтный handler
    logger.remove()
    
    # Console logging
    if settings.debug:
        # Development: красивые цветные логи
        logger.add(
            sys.stdout,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )
    else:
        # Production: JSON logging для парсинга
        logger.add(
            sys.stdout,
            serialize=True,
            level="INFO"
        )
    
    # File logging с ротацией
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Application logs (все уровни)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Новый файл каждый день
        retention="30 days",  # Хранить 30 дней
        compression="zip",  # Сжимать старые логи
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        enqueue=True,  # Асинхронная запись
    )
    
    # Error logs (отдельный файл для ошибок)
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",  # Ошибки хранить дольше
        compression="zip",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        enqueue=True,
        backtrace=True,  # Полный traceback
        diagnose=True,  # Детальная диагностика
    )
    
    # Access logs (HTTP requests)
    logger.add(
        log_dir / "access_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="14 days",
        compression="zip",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        filter=lambda record: "access" in record["extra"],
        enqueue=True,
    )
    
    logger.info("✅ Logging configured successfully")
    logger.debug(f"Log directory: {log_dir.absolute()}")


def get_logger_for_module(module_name: str):
    """
    Получить logger для конкретного модуля.
    
    Args:
        module_name: Имя модуля
        
    Returns:
        Настроенный logger
    """
    return logger.bind(module=module_name)

