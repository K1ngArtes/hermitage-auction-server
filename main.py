import os
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Pydantic Models
class Item(BaseModel):
    id: int
    image: str
    title: str
    minimumBid: int
    details: str

    class Config:
        populate_by_name = True

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

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

@app.get("/items", response_model=list[Item])
async def get_items(db: aiosqlite.Connection = Depends(get_db)):
    """Get all auction items"""
    try:
        cursor = await db.execute(
            "SELECT id, img_location, title, min_bid, details FROM items"
        )
        rows = await cursor.fetchall()
        await cursor.close()

        items = [
            Item(
                id=row[0],
                image=row[1],
                title=row[2],
                minimumBid=row[3],
                details=row[4]
            )
            for row in rows
        ]

        logger.info(f"Successfully fetched {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"Failed to fetch items: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch items from database"
        )
