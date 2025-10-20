import os
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Depends, Response
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Session configuration
SECRET_KEY = os.getenv("SECRET_KEY", "4peK4Z*Q4vRW")
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds

# Initialize serializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Security warning
if SECRET_KEY == "dev-secret-key-change-in-production":
    logger.warning("Using default SECRET_KEY - NOT SECURE for production!")

def create_session_token(user_id: int) -> str:
    """Create signed session token containing user ID"""
    return serializer.dumps(user_id)

def validate_session_token(token: str) -> int | None:
    """Validate and extract user ID from session token"""
    try:
        user_id = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return user_id
    except (SignatureExpired, BadSignature) as e:
        logger.warning(f"Invalid session token: {str(e)}")
        return None

# Pydantic Models
class Item(BaseModel):
    id: int
    title: str
    image: str
    author: str
    authorDescription: str | None
    minimumBid: int
    year: int
    description: str
    showOrder: int

    class Config:
        populate_by_name = True

class LoginRequest(BaseModel):
    name: str
    email: str

class LoginResponse(BaseModel):
    id: int

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
    """Get all auction items ordered by show_order"""
    try:
        logger.info("Fetching items from database")
        cursor = await db.execute(
            """SELECT id, title, img_location, author, author_description,
                      min_bid, year, description, show_order
               FROM items
               ORDER BY show_order"""
        )
        rows = await cursor.fetchall()
        await cursor.close()

        items = [
            Item(
                id=row[0],
                title=row[1],
                image=row[2],
                author=row[3],
                authorDescription=row[4],
                minimumBid=row[5],
                year=row[6],
                description=row[7],
                showOrder=row[8]
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

@app.post("/login")
async def login(request: LoginRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Login or create user account and set session cookie"""
    try:
        logger.info(f"Login attempt for email: {request.email}")

        cursor = await db.execute(
            "INSERT INTO accounts (name, email) VALUES (?, ?)",
            (request.name, request.email)
        )
        await db.commit()
        user_id = cursor.lastrowid
        await cursor.close()
        logger.info(f"Created new user with id {user_id}: {request.email}")

    except aiosqlite.IntegrityError:
        logger.info(f"User already exists: {request.email}")
        cursor = await db.execute(
            "SELECT id FROM accounts WHERE email = ?",
            (request.email,)
        )
        row = await cursor.fetchone()
        await cursor.close()

        if row:
            user_id = row[0]
        else:
            logger.error(f"Database inconsistency for email: {request.email}")
            raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Login failed for {request.email}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")

    # Create session token
    session_token = create_session_token(user_id)

    # Create response with cookie
    response = Response(
        content='{"success": true, "message": "Logged in successfully"}',
        media_type="application/json"
    )

    response.set_cookie(
        key="session",
        value=session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=False,  # Change to True in production with HTTPS
        samesite="lax",
        path="/"
    )

    logger.info(f"Session cookie set for user {user_id}")
    return response
