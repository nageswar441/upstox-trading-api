#!/usr/bin/env python3
"""
Environment Profile Manager for Upstox Trading API

This script helps switch between different environment profiles:
- dev (development)
- staging
- prod (production)

Usage:
    python profile_manager.py [profile]
    python profile_manager.py dev
    python profile_manager.py staging
    python profile_manager.py prod
"""

import os
import sys
import shutil
from pathlib import Path


class ProfileManager:
    """Manage environment profiles for the application"""
    
    VALID_PROFILES = ['dev', 'staging', 'prod']
    DEFAULT_PROFILE = 'dev'
    ENV_FILE = '.env'
    
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.current_profile = self.get_current_profile()
    
    def get_current_profile(self) -> str:
        """Get currently active profile"""
        env_file = self.root_dir / self.ENV_FILE
        
        if not env_file.exists():
            return "none"
        
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('APP_ENV='):
                        env = line.split('=')[1].strip()
                        if 'dev' in env.lower():
                            return 'dev'
                        elif 'staging' in env.lower():
                            return 'staging'
                        elif 'prod' in env.lower():
                            return 'prod'
        except Exception as e:
            print(f"⚠️  Error reading current profile: {e}")
        
        return "unknown"
    
    def switch_profile(self, profile: str) -> bool:
        """
        Switch to specified environment profile
        
        Args:
            profile: Target profile (dev, staging, prod)
            
        Returns:
            True if successful, False otherwise
        """
        if profile not in self.VALID_PROFILES:
            print(f"❌ Invalid profile: {profile}")
            print(f"   Valid profiles: {', '.join(self.VALID_PROFILES)}")
            return False
        
        source_file = self.root_dir / f".env.{profile}"
        target_file = self.root_dir / self.ENV_FILE
        
        if not source_file.exists():
            print(f"❌ Profile file not found: {source_file}")
            print(f"   Please create .env.{profile} file first")
            return False
        
        try:
            # Backup current .env if it exists
            if target_file.exists():
                backup_file = self.root_dir / ".env.backup"
                shutil.copy2(target_file, backup_file)
                print(f"📦 Backed up current .env to .env.backup")
            
            # Copy profile file to .env
            shutil.copy2(source_file, target_file)
            
            print(f"✅ Successfully switched to '{profile}' profile")
            print(f"   Active file: {target_file}")
            print(f"   Source: {source_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error switching profile: {e}")
            return False
    
    def show_status(self):
        """Show current profile status"""
        print("\n" + "="*50)
        print("   UPSTOX TRADING API - PROFILE STATUS")
        print("="*50)
        print(f"📍 Current Profile: {self.current_profile}")
        print(f"📂 Root Directory: {self.root_dir}")
        print()
        
        # Check available profiles
        print("Available Profiles:")
        for profile in self.VALID_PROFILES:
            profile_file = self.root_dir / f".env.{profile}"
            status = "✅ exists" if profile_file.exists() else "❌ missing"
            active = " (ACTIVE)" if profile == self.current_profile else ""
            print(f"  - {profile:8} : {status}{active}")
        
        print()
        print("="*50)
    
    def create_profile_files(self):
        """Create missing profile files from template"""
        example_file = self.root_dir / ".env.example"
        
        if not example_file.exists():
            print("❌ .env.example file not found")
            return
        
        created = []
        for profile in self.VALID_PROFILES:
            profile_file = self.root_dir / f".env.{profile}"
            
            if not profile_file.exists():
                try:
                    shutil.copy2(example_file, profile_file)
                    created.append(profile)
                    print(f"✅ Created {profile_file}")
                except Exception as e:
                    print(f"❌ Error creating {profile_file}: {e}")
        
        if created:
            print(f"\n📝 Created {len(created)} profile file(s)")
            print("   Please edit these files and add your credentials")
        else:
            print("ℹ️  All profile files already exist")


def main():
    manager = ProfileManager()
    
    # No arguments - show status and help
    if len(sys.argv) == 1:
        manager.show_status()
        print("\nUsage:")
        print("  python profile_manager.py <profile>")
        print("\nExamples:")
        print("  python profile_manager.py dev       # Switch to development")
        print("  python profile_manager.py staging   # Switch to staging")
        print("  python profile_manager.py prod      # Switch to production")
        print("  python profile_manager.py status    # Show current status")
        print("  python profile_manager.py create    # Create missing profile files")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        manager.show_status()
    elif command == 'create':
        manager.create_profile_files()
    elif command in manager.VALID_PROFILES:
        # Confirmation for production
        if command == 'prod':
            print("⚠️  WARNING: Switching to PRODUCTION environment!")
            response = input("   Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
        
        if manager.switch_profile(command):
            print(f"\n🚀 To start the server with {command} profile:")
            print(f"   python -m uvicorn main:app --reload" if command == 'dev' else f"   python -m uvicorn main:app")
    else:
        print(f"❌ Unknown command: {command}")
        print(f"   Valid commands: {', '.join(manager.VALID_PROFILES + ['status', 'create'])}")


if __name__ == "__main__":
    main()
