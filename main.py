from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import aiosqlite
import os

db_connection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection

    db_path = "/app/data/auction.db"

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db_connection = await aiosqlite.connect(db_path)
    print(f"Database connected: {db_path}")

    yield

    # Shutdown: Close connection
    await db_connection.close()
    print("Database connection closed")

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
                "status": "healthy",
                "database": "connected",
                "check": "passed"
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Database check failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database unhealthy: {str(e)}"
        )
