from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import datetime
# Try relative import first, if it fails, assume running from root
try:
    from database import Base
except ImportError:
    from ..database import Base

# Association Table for Many-to-Many between Role and Permission
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles", lazy="selectin")
    accounts = relationship("Account", back_populates="role")

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False) # e.g., 'orders:read'
    description = Column(String, nullable=True)
    
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    role = relationship("Role", back_populates="accounts", lazy="selectin")
    
    oauth_clients = relationship("OAuth2Client", back_populates="owner")

class OAuth2Client(Base):
    __tablename__ = "oauth2_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True, nullable=False)
    client_secret = Column(String, nullable=False)  # Should be hashed in production
    name = Column(String, nullable=True)
    
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    owner = relationship("Account", back_populates="oauth_clients")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
