# Hermitage Auction Server

A FastAPI-based auction server application for managing auction items, bids, and donations.

## Features

- Browse and view auction items
- User authentication with session-based cookies
- Place, view, and cancel bids
- Donation management
- Real-time bid validation
- SQLite database with web viewer
- CORS support for cross-origin requests

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite
- **Package Manager**: uv
- **Server**: Uvicorn (ASGI)
- **Frontend**: React (separate app)
- **Database Viewer**: sqlite-web + nginx

## Prerequisites

- Docker and Docker Compose
- `.htpasswd` file for database viewer authentication. This is needed because SQLite-web doesn't have auth

## Setup & Running

1. **Initialize the database**

   Create the database and schema:
   ```bash
   mkdir -p data
   sqlite3 data/auction.db < schema.sql
   ```

2. **Copy environment configuration**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**

   Edit `.env` and set your SECRET_KEY:
   ```bash
   # Generate a secure key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. **Start the application**
   ```bash
   docker-compose up -d
   ```

## Accessing the Application

- **Frontend UI**: http://localhost:8000
- **API Server**: http://localhost:8002
- **Database Viewer**: http://localhost:8004 (password-protected)

### API Endpoints

**Public:**
- `GET /items` - List all auction items
- `GET /item/{id}` - Get item details
- `POST /login` - User login/registration
- `POST /logout` - Logout

**Authenticated (requires session cookie):**
- `POST /bid` - Place a bid
- `GET /bid/{item_id}` - Get user's bid
- `DELETE /bid/{id}` - Cancel a bid
- `POST /donate` - Create/update donation
- `GET /donations` - Get user's donation

## Environment Variables

See `.env.example` for all available configuration options.
