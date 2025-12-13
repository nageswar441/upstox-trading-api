# Architecture & Implementation Plan: Identity & Access Management (IAM)

## Goal Description
Enhance the Upstox Trading API with a robust Identity and Access Management (IAM) system. This involves switching to a PostgreSQL database, introducing `Account` models with authentication fields, implementing OAuth2 Client Credentials flow for machine-to-machine communication, and designing a Role-Based Access Control (RBAC) system for granular route permissions.

## User Review Required
> [!IMPORTANT]
> **Database Transition**: We are adding PostgreSQL. You will need a running PostgreSQL instance.
> **Dependency Changes**: Adding `sqlalchemy`, `asyncpg`, `alembic` (for migrations), and `bcrypt`.

## Proposed Architecture

### Database Schema (ERD Concept)
- **Roles**: `id`, `name`, `description`
- **Permissions**: `id`, `name`, `resource`, `action`
- **RolePermissions**: Many-to-Many map between Roles and Permissions.
- **Accounts**: `id`, `username`, `email`, `hashed_password`, `role_id`, `is_active`
- **Clients** (for OAuth): `client_id`, `client_secret`, `account_id` (owner), `scopes`
- **RoutePermissions**: `path`, `method`, `required_permission_id` (Dynamic permission checking)

### Authentication Flows
1.  **User Login**: Standard Username/Password -> JWT (Access Token).
2.  **Client/API Login**: Client ID + Secret -> JWT (Access Token) via OAuth2 Client Credentials flow.

### Authorization (RBAC)
- **Middleware/Dependency**: A `permission_dependency` will run on protected routes.
- It determines the route being accessed.
- Checks if the authenticated user (or client) has the required permission/role for that route.

## Proposed Changes

### Configuration
#### [NEW] [database.py](file:///c:/Users/nageswart/Downloads/upstox-trading-api/database.py)
- Async SQLAlchemy engine setup.
- `get_db` dependency.

### Models
#### [NEW] [auth/models.py](file:///c:/Users/nageswart/Downloads/upstox-trading-api/auth/models.py)
- SQLAlchemy models for `Account`, `Role`, `Permission`, `OAuth2Client`.

### Authentication
#### [MODIFY] [auth/oauth.py](file:///c:/Users/nageswart/Downloads/upstox-trading-api/auth/oauth.py)
- Update to support Client Credentials flow using the new database models.

### Permissions
#### [NEW] [auth/permissions.py](file:///c:/Users/nageswart/Downloads/upstox-trading-api/auth/permissions.py)
- Logic for checking permissions.
- Dependency `require_permission(permission_name)`.

## Verification Plan
### Automated Tests
- Test database connection.
- Test user creation.
- Test token generation to ensure `client_id`/`secret` works.
- Test access control on a dummy route (allow vs deny).
