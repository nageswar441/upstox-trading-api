import asyncio
from sqlalchemy.future import select
from database import engine, AsyncSessionLocal
from auth.models import Role, Permission, Account, OAuth2Client
from auth.utils import get_password_hash

async def seed_data():
    async with AsyncSessionLocal() as session:
        try:
            # 1. Create Permissions
            permissions_map = {
                "orders:read": "View orders",
                "orders:place": "Place new orders",
                "account:read": "View account details",
                "admin:manage": "Full administrative access"
            }
            
            created_perms = {}
            for name, desc in permissions_map.items():
                stmt = select(Permission).where(Permission.name == name)
                result = await session.execute(stmt)
                perm = result.scalars().first()
                if not perm:
                    perm = Permission(name=name, description=desc)
                    session.add(perm)
                    print(f"Adding permission: {name}")
                created_perms[name] = perm
            
            # 2. Create Roles
            roles_map = {
                "admin": ["orders:read", "orders:place", "account:read", "admin:manage"],
                "trader": ["orders:read", "orders:place", "account:read"]
            }
            
            for role_name, perm_names in roles_map.items():
                stmt = select(Role).where(Role.name == role_name)
                result = await session.execute(stmt)
                role = result.scalars().first()
                if not role:
                    role = Role(name=role_name, description=f"{role_name.capitalize()} role")
                    session.add(role)
                    print(f"Adding role: {role_name}")
                
                # Assign permissions
                # Note: relationships in async require awaiting or correct loading. 
                # For simplicity here, we assume new objects or handle cleanly.
                # In current session with new objects, we can just append if not present.
                # But safer to just ensures connection if we flush.
                
                # Check current perms
                # await session.refresh(role, attribute_names=["permissions"]) # specific loading if needed
                # For this script, we'll just set them if it's new.
                
                if not role.permissions:
                   for pname in perm_names:
                       if pname in created_perms:
                           role.permissions.append(created_perms[pname])

            await session.commit()
            print("Roles and Permissions seeded.")
            
            # 3. Create Admin User (if not exists)
            stmt = select(Account).where(Account.username == "admin")
            result = await session.execute(stmt)
            admin = result.scalars().first()
            
            if not admin:
                stmt_role = select(Role).where(Role.name == "admin")
                res_role = await session.execute(stmt_role)
                admin_role = res_role.scalars().first()
                
                admin = Account(
                    username="admin", 
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"), # Change in production
                    role=admin_role,
                    is_active=True
                )
                session.add(admin)
                print("Created admin user (pass: admin123)")
                await session.commit() # Commit to get ID
                
            # 4. Create OAuth Client for Admin
            stmt_client = select(OAuth2Client).where(OAuth2Client.client_id == "my_trading_bot")
            result_client = await session.execute(stmt_client)
            client = result_client.scalars().first()
            
            if not client:
                client = OAuth2Client(
                    client_id="my_trading_bot",
                    client_secret="bot_secret_123", # Plain text implementation as discussed
                    name="Trading Bot",
                    owner=admin
                )
                session.add(client)
                print("Created OAuth Client (id: my_trading_bot, secret: bot_secret_123)")
                await session.commit()

        except Exception as e:
            print(f"Error seeding data: {e}")
            await session.rollback()
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(seed_data())
