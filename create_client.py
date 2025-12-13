import asyncio
import secrets
import string
from sqlalchemy.future import select
from database import AsyncSessionLocal
from auth.models import Account, OAuth2Client

def generate_secure_string(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

async def create_client(username: str, client_name: str):
    async with AsyncSessionLocal() as session:
        # 1. Find the user (Account)
        stmt = select(Account).where(Account.username == username)
        result = await session.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            print(f"Error: User '{username}' not found. Please create the user first.")
            return

        # 2. Generate Credentials
        client_id = f"client_{generate_secure_string(16)}"
        client_secret = generate_secure_string(48)
        
        # 3. Save to Database
        new_client = OAuth2Client(
            client_id=client_id,
            client_secret=client_secret, # Storing plain text as per current simple implementation
            name=client_name,
            owner=user
        )
        session.add(new_client)
        await session.commit()
        
        print("\n" + "="*50)
        print("✅ OAuth2 Client Created Successfully")
        print("="*50)
        print(f"Owner:         {username}")
        print(f"Client Name:   {client_name}")
        print("-" * 50)
        print(f"Client ID:     {client_id}")
        print(f"Client Secret: {client_secret}")
        print("-" * 50)
        print("⚠️  KEEP THESE CREDENTIALS SAFE! ⚠️")
        print("="*50 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python create_client.py <username> [client_name]")
        print("Example: python create_client.py admin 'Mobile App'")
        sys.exit(1)
        
    username_arg = sys.argv[1]
    client_name_arg = sys.argv[2] if len(sys.argv) > 2 else "New Client"
    
    asyncio.run(create_client(username_arg, client_name_arg))
