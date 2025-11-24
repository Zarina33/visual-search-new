"""
HTTP request logging middleware.
"""
import time
from typing import Callable
from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования всех HTTP запросов.
    
    Логирует:
    - Входящие запросы (метод, путь, клиент)
    - Исходящие ответы (статус код, длительность)
    - Ошибки с полным traceback
    """
    
    def __init__(self, app: ASGIApp):
        """
        Инициализация middleware.
        
        Args:
            app: ASGI приложение
        """
        super().__init__(app)
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Обработка HTTP запроса с логированием.
        
        Args:
            request: HTTP запрос
            call_next: Следующий обработчик
            
        Returns:
            HTTP ответ
        """
        # Начало запроса
        start_time = time.time()
        request_id = id(request)
        
        # Получить информацию о клиенте
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        # Логируем входящий запрос
        logger.bind(access=True).info(
            f"→ {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_host": client_host,
                "client_port": client_port,
                "user_agent": request.headers.get("user-agent", "unknown"),
            }
        )
        
        # Обработка запроса
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Логируем успешный ответ
            log_level = "info" if response.status_code < 400 else "warning"
            log_func = getattr(logger.bind(access=True), log_level)
            
            log_func(
                f"← {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": duration,
                    "client_host": client_host,
                }
            )
            
            # Добавить заголовок с временем обработки
            response.headers["X-Process-Time"] = f"{duration:.3f}"
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Логируем ошибку
            logger.bind(access=True).error(
                f"✗ {request.method} {request.url.path} - ERROR - {duration:.3f}s",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration": duration,
                    "client_host": client_host,
                }
            )
            
            # Пробрасываем исключение дальше
            raise

