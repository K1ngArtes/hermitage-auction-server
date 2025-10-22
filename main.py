import os
import uuid
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Depends, Response, Cookie
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
    isClosed: bool

    class Config:
        populate_by_name = True


class LoginRequest(BaseModel):
    name: str
    email: str


class LoginResponse(BaseModel):
    id: int


class BidRequest(BaseModel):
    item_id: int
    amount: int


db_connection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection

    logger.info("Application starting up")

    db_path = "/app/data/auction.db"

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db_connection = await aiosqlite.connect(db_path)

    # Enable WAL mode for better concurrent access
    await db_connection.execute("PRAGMA journal_mode=WAL")

    # Set busy timeout to 5 seconds
    await db_connection.execute("PRAGMA busy_timeout=5000")

    logger.info(f"Database connected: {db_path} (WAL mode enabled)")

    yield

    logger.info("Application shutting down")
    await db_connection.close()
    logger.info("Database connection closed")


app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:80",
        "http://localhost",
        "https://auriform-derrick-spectrographic.ngrok-free.dev",
    ],
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
            """SELECT
                   i.id,
                   i.title,
                   i.img_location,
                   i.author,
                   i.author_description,
                   MAX(i.min_bid, COALESCE(MAX(b.amount), 0)) as minimum_bid,
                   i.year,
                   i.description,
                   i.show_order,
                   i.is_closed
               FROM items i
               LEFT JOIN bids b ON i.id = b.item_id
               GROUP BY i.id, i.title, i.img_location, i.author, i.author_description,
                        i.min_bid, i.year, i.description, i.show_order, i.is_closed
               ORDER BY i.show_order"""
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
                showOrder=row[8],
                isClosed=bool(row[9])
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


@app.get("/item/{id}", response_model=Item)
async def get_item(id: int, db: aiosqlite.Connection = Depends(get_db)):
    """Get a single auction item by ID"""
    try:
        logger.info(f"Fetching item {id} from database")
        cursor = await db.execute(
            """SELECT
                   i.id,
                   i.title,
                   i.img_location,
                   i.author,
                   i.author_description,
                   MAX(i.min_bid, COALESCE(MAX(b.amount), 0)) as minimum_bid,
                   i.year,
                   i.description,
                   i.show_order,
                   i.is_closed
               FROM items i
               LEFT JOIN bids b ON i.id = b.item_id
               WHERE i.id = ?
               GROUP BY i.id, i.title, i.img_location, i.author, i.author_description,
                        i.min_bid, i.year, i.description, i.show_order, i.is_closed""",
            (id,)
        )
        row = await cursor.fetchone()
        await cursor.close()

        if not row:
            logger.warning(f"Item {id} not found")
            raise HTTPException(status_code=404, detail="Item not found")

        item = Item(
            id=row[0],
            title=row[1],
            image=row[2],
            author=row[3],
            authorDescription=row[4],
            minimumBid=row[5],
            year=row[6],
            description=row[7],
            showOrder=row[8],
            isClosed=bool(row[9])
        )

        logger.info(f"Successfully fetched item {id}")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch item {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch item from database"
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
            "UPDATE accounts SET name = ? WHERE email = ? RETURNING id",
            (request.name, request.email,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        await db.commit()

        if row:
            user_id = row[0]
            logger.info(f"Updated name for existing user id {user_id}: {request.email}")
        else:
            logger.error(f"Database inconsistency for email: {request.email}")
            raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Login failed for {request.email}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")

    session_token = create_session_token(user_id)

    response = Response(
        content='{"success": true, "message": "Logged in successfully"}',
        media_type="application/json"
    )

    response.set_cookie(
        key="session",
        value=session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,  # Change to True in production with HTTPS
        samesite="none",
        path="/"
    )

    logger.info(f"Session cookie set for user {user_id}")
    return response


@app.post("/logout")
async def logout():
    """Logout by clearing the session cookie"""
    response = Response(
        content='{"success": true, "message": "Logged out successfully"}',
        media_type="application/json"
    )

    response.delete_cookie(
        key="session",
        path="/",
        samesite="none",
        secure=True
    )

    logger.info("User logged out - session cookie cleared")
    return response


@app.post("/bid")
async def place_bid(
        request: BidRequest,
        db: aiosqlite.Connection = Depends(get_db),
        session: str | None = Cookie(None)
):
    """Place a bid on an auction item"""
    # Validate session cookie
    if not session:
        logger.warning("Bid attempt without session cookie")
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = validate_session_token(session)
    if not user_id:
        logger.warning("Bid attempt with invalid session token")
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        logger.info(f"Bid attempt by user {user_id} for item {request.item_id}: ${request.amount}")

        cursor = await db.execute(
            "SELECT min_bid, is_closed FROM items WHERE id = ?",
            (request.item_id,)
        )
        item_row = await cursor.fetchone()
        await cursor.close()

        if not item_row:
            logger.warning(f"Bid attempt for non-existent item {request.item_id}")
            raise HTTPException(status_code=404, detail="Item not found")

        min_bid = item_row[0]
        is_closed = bool(item_row[1])

        if is_closed:
            raise HTTPException(
                status_code=400,
                detail="Bidding for this item has closed"
            )

        if request.amount < min_bid:
            logger.info(f"Bid rejected: amount ${request.amount} below minimum ${min_bid}")
            raise HTTPException(
                status_code=400,
                detail=f"Bid amount must be at least ${min_bid}"
            )

        # Check for existing higher bids
        cursor = await db.execute(
            "SELECT MAX(amount) FROM bids WHERE item_id = ?",
            (request.item_id,)
        )
        max_bid_row = await cursor.fetchone()
        await cursor.close()

        max_existing_bid = max_bid_row[0] if max_bid_row and max_bid_row[0] else 0

        if request.amount <= max_existing_bid:
            logger.info(f"Bid rejected: amount ${request.amount} not higher than current bid ${max_existing_bid}")
            raise HTTPException(
                status_code=400,
                detail=f"There is a new higher bid of £{max_existing_bid}!"
            )

        # Insert the bid
        bid_uuid = str(uuid.uuid4())
        cursor = await db.execute(
            "INSERT INTO bids (uuid, user_id, item_id, amount) VALUES (?, ?, ?, ?)",
            (bid_uuid, user_id, request.item_id, request.amount)
        )
        await db.commit()
        await cursor.close()

        logger.info(f"Bid placed successfully: {bid_uuid} by user {user_id} for ${request.amount}")
        return {"message": "Bid placed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to place bid: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to place bid")


@app.get("/bid/{item_id}")
async def get_user_bid(
        item_id: int,
        db: aiosqlite.Connection = Depends(get_db),
        session: str | None = Cookie(None)
):
    """Get user's latest bid for a specific item"""
    if not session:
        logger.info(f"Bid retrieval attempt for item {item_id} without session cookie")
        raise HTTPException(status_code=404, detail="Not found")

    user_id = validate_session_token(session)
    if not user_id:
        logger.info(f"Bid retrieval attempt for item {item_id} with invalid session")
        raise HTTPException(status_code=404, detail="Not found")

    try:
        cursor = await db.execute(
            """SELECT uuid, amount
               FROM bids
               WHERE user_id = ? AND item_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (user_id, item_id)
        )
        bid_row = await cursor.fetchone()
        await cursor.close()

        if not bid_row:
            raise HTTPException(status_code=404, detail="Not found")

        bid_uuid = bid_row[0]
        user_amount = bid_row[1]

        cursor = await db.execute(
            """SELECT MAX(amount)
               FROM bids
               WHERE item_id = ?""",
            (item_id,)
        )
        max_bid_row = await cursor.fetchone()
        await cursor.close()

        max_amount = max_bid_row[0] if max_bid_row and max_bid_row[0] else 0
        is_highest = user_amount >= max_amount

        return {"uid": bid_uuid, "amount": user_amount, "is_highest": is_highest}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve bid: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve bid")

@app.delete("/bid/{id}")
async def delete_bid(
    id: str,
    db: aiosqlite.Connection = Depends(get_db),
    session: str | None = Cookie(None)
):
    """Delete user's bid by UUID"""
    if not session:
        logger.warning("Bid deletion attempt without session cookie")
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = validate_session_token(session)
    if not user_id:
        logger.warning("Bid deletion attempt with invalid session token")
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        logger.info(f"Bid deletion attempt by user {user_id} for bid {id}")

        cursor = await db.execute(
            "SELECT item_id FROM bids WHERE uuid = ? AND user_id = ?",
            (id, user_id)
        )
        bid_row = await cursor.fetchone()
        await cursor.close()

        if not bid_row:
            logger.warning(f"Bid {id} not found or doesn't belong to user {user_id}")
            raise HTTPException(status_code=404, detail="Bid not found")

        item_id = bid_row[0]

        cursor = await db.execute(
            "SELECT is_closed FROM items WHERE id = ?",
            (item_id,)
        )
        item_row = await cursor.fetchone()
        await cursor.close()

        if item_row and bool(item_row[0]):
            logger.info(f"Bid deletion rejected: item {item_id} is closed")
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel bid - bidding for this item has closed"
            )

        cursor = await db.execute(
            "DELETE FROM bids WHERE uuid = ? AND user_id = ?",
            (id, user_id)
        )
        await cursor.close()
        await db.commit()

        logger.info(f"Bid {id} deleted successfully by user {user_id}")
        return {"message": "Bid deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete bid: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete bid")
