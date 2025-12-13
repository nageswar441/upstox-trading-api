from fastapi import Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import get_db
from auth.models import Account, Role, Permission      # Import from your models file
from auth.jwt_handler import get_current_user

# Dependency to check permissions
class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self, 
        user_data: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        user_id = user_data.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User not authenticated"
            )

        # Fetch user with roles and permissions
        stmt = (
            select(Account)
            .options(selectinload(Account.role).selectinload(Role.permissions))
            .where(Account.id == int(user_id))  # Assuming user_id in token is int
        )
        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        if not user.role:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="User has no role assigned"
            )
            
        # Check if role has the required permission
        user_permissions = [p.name for p in user.role.permissions]
        
        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Operation not permitted. Required: {self.required_permission}"
            )
            
        return user

def require_permission(permission_name: str):
    return PermissionChecker(permission_name)
