from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="User Service - Marketplace",
    description="Микросервис управления пользователями",
    version="1.0.0"
)

@app.get("/health", summary="Check application health")
async def health_check():
    """
    Эндпоинт для проверки жизнеспособности сервиса.
    Должен возвращать 200 OK.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "service": "user_service"}
    )