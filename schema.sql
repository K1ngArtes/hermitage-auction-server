-- Hermitage Auction Server Database Schema
-- SQLite database schema for auction items, user accounts, bids, and donations

-- Auction items table
CREATE TABLE IF NOT EXISTS "items" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    img_location TEXT NOT NULL,
    author VARCHAR NOT NULL,
    author_description TEXT,
    min_bid INTEGER NOT NULL,
    year INTEGER NOT NULL,
    description TEXT NOT NULL,
    show_order INTEGER UNIQUE NOT NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE
);

-- User accounts table
CREATE TABLE IF NOT EXISTS "accounts" (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Bids table
CREATE TABLE IF NOT EXISTS "bids" (
    uuid TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES accounts(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Donations table
CREATE TABLE IF NOT EXISTS "donations" (
    uuid TEXT PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    amount INTEGER NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES accounts(id)
);
