from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import aiosqlite
import os
from logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

db_connection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection

    logger.info("Application starting up")

    db_path = "/app/data/auction.db"

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db_connection = await aiosqlite.connect(db_path)
    logger.info(f"Database connected: {db_path}")

    yield

    logger.info("Application shutting down")
    await db_connection.close()
    logger.info("Database connection closed")

app = FastAPI(lifespan=lifespan)

async def get_db():
    return db_connection

@app.get("/")
async def read_root():
    return {"message": "Hello World!"}

@app.get("/healthcheck")
async def health_check(db: aiosqlite.Connection = Depends(get_db)):
    try:
        cursor = await db.execute("SELECT 1")
        result = await cursor.fetchone()
        await cursor.close()

        if result and result[0] == 1:
            return {
                "status": "healthy"
            }
        else:
            logger.error("Health check failed: unexpected query result")
            raise HTTPException(
                status_code=503,
                detail="Database check failed"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Database unhealthy: {str(e)}"
        )
