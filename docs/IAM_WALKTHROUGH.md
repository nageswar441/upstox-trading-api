# Implementation Log: Identity & Access Management (IAM) System

This document outlines the complete set of steps executed to implement the new Authentication and Authorization architecture using PostgreSQL.

## 1. Architecture Design
We designed a system separating concerns between data (Postgres), authentication (OAuth2), and authorization (RBAC).
- **Core Decision**: Switch from SQLite/Memory to **PostgreSQL** for persistence.
- **ORM**: Selected **SQLAlchemy (Async)** for non-blocking database operations.

## 2. Environment Setup
### Dependencies
Modified `requirements.txt` to include:
- `sqlalchemy[asyncio]`: Logic mapping to database.
- `asyncpg`: Async PostgreSQL driver.
- `alembic`: For future migrations (installed but not yet configured).

### Configuration
- **.env**: Added `DATABASE_URL` pointing to the local PostgreSQL instance.
- **database.py**: Created the database connection module establishing an asynchronous engine and session factory.

## 3. Data Modeling
Created `auth/models.py` defining the schema:
- **Account**: Users with username, email, and hashed password. It links to a Role.
- **Role**: Named roles (e.g., 'admin', 'trader') containing multiple Permissions.
- **Permission**: Granular capabilities (e.g., 'orders:place', 'account:read').
- **OAuth2Client**: Client ID/Secret pairs for machine-to-machine authentication, owned by an Account.

## 4. Authentication Implementation
### Utilities (`auth/utils.py`)
- Implemented password hashing using `passlib` with `pbkdf2_sha256` (and `bcrypt` compatibility) to securely store secrets.

### OAuth2 Router (`auth/router.py`)
- Implemented **Client Credentials Flow** at `/api/v1/auth/token`.
- Validates `client_id` and `client_secret`.
- Issues JWT Access Tokens signed with the application's secret key.

## 5. Authorization (RBAC) Implementation
### Permissions (`auth/permissions.py`)
- Created `require_permission(name)` dependency.
- This checks if the authenticated user's Role possesses the required Permission before allowing access to a route.

## 6. Main Application Integration
Updated `main.py` to:
- Import and register the new `auth_router`.
- Ensure all components are wired together.

## 7. Database Initialization & Seeding
Created utility scripts to bootstrap the environment:

1.  **`create_postgres_db.py`**:
    - Connects to the default `postgres` database.
    - Checks for `upstox_db` and creates it if missing.
2.  **`create_db.py`**:
    - Uses SQLAlchemy metadata to creating all defined tables in `upstox_db`.
3.  **`seed_data.py`**:
    - **Permissions**: Seeds `orders:read`, `orders:place`, `account:read`, `admin:manage`.
    - **Roles**: Seeds `admin` (all permissions) and `trader` (limited permissions).
    - **Users**: Creates a default `admin` user.
    - **Clients**: Creates a `my_trading_bot` client for testing.

## Summary of Commands Executed
To replicate this state on a fresh machine:
```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure .env with your DB credentials
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname

# 3. Initialize DB
python create_postgres_db.py
python create_db.py

# 4. Seed Data
python seed_data.py
```
