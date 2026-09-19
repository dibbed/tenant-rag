#!/usr/bin/env python3
"""
Configuration Setup Utility.

This script helps users set up their environment configuration files
and validate their settings before running the bot.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional

from ragbot.outputs.logger import logger


class ConfigurationSetup:
    """Utility for setting up configuration files."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.env_templates = {
            "development": self.project_root / ".env.development",
            "production": self.project_root / ".env.production", 
            "testing": self.project_root / ".env.testing",
            "example": self.project_root / ".env.example",
        }
        self.target_env = self.project_root / ".env"
    
    def list_templates(self) -> None:
        """List available environment templates."""
        print("Available environment templates:")
        print("=" * 40)
        
        for env_name, template_path in self.env_templates.items():
            if template_path.exists():
                print(f"✅ {env_name:<12} - {template_path.name}")
                
                # Show first few lines as preview
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        description_lines = [line.strip() for line in lines[:10] 
                                           if line.strip() and line.startswith('#')]
                        if description_lines:
                            print(f"   Description: {description_lines[1].replace('# ', '')}")
                except Exception:
                    pass
                print()
            else:
                print(f"❌ {env_name:<12} - Template not found")
    
    def copy_template(self, template_name: str, force: bool = False) -> bool:
        """
        Copy a template to .env file.
        
        Args:
            template_name: Name of the template to copy
            force: Whether to overwrite existing .env file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if template_name not in self.env_templates:
            logger.error(f"Template '{template_name}' not found")
            return False
        
        template_path = self.env_templates[template_name]
        if not template_path.exists():
            logger.error(f"Template file not found: {template_path}")
            return False
        
        # Check if .env already exists
        if self.target_env.exists() and not force:
            logger.warning(f".env file already exists at {self.target_env}")
            response = input("Do you want to overwrite it? (y/N): ").lower().strip()
            if response not in ['y', 'yes']:
                logger.info("Operation cancelled")
                return False
        
        try:
            # Create backup if .env exists
            if self.target_env.exists():
                backup_path = self.target_env.with_suffix('.env.backup')
                shutil.copy2(self.target_env, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Copy template
            shutil.copy2(template_path, self.target_env)
            logger.info(f"✅ Copied {template_name} template to .env")
            
            # Make it writable
            os.chmod(self.target_env, 0o600)
            logger.info("Set .env file permissions to 600 (owner read/write only)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy template: {str(e)}")
            return False
    
    def validate_env_file(self, env_path: Optional[Path] = None) -> bool:
        """
        Validate an environment file.
        
        Args:
            env_path: Path to env file (defaults to .env)
            
        Returns:
            bool: True if valid, False otherwise
        """
        if env_path is None:
            env_path = self.target_env
        
        if not env_path.exists():
            logger.error(f"Environment file not found: {env_path}")
            return False
        
        try:
            # Load the environment file temporarily
            from dotenv import load_dotenv
            load_dotenv(env_path, override=True)
            
            # Import and validate settings
            from ragbot.configs.settings import Settings
            settings = Settings()
            
            validation_result = settings.validate_all_settings()
            
            if validation_result["valid"]:
                logger.info("✅ Environment configuration is valid")
                return True
            else:
                logger.error("❌ Environment configuration has errors:")
                for error in validation_result["errors"]:
                    logger.error(f"  - {error}")
                
                if validation_result["warnings"]:
                    logger.warning("⚠️  Warnings:")
                    for warning in validation_result["warnings"]:
                        logger.warning(f"  - {warning}")
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to validate environment file: {str(e)}")
            return False
    
    def interactive_setup(self) -> bool:
        """
        Interactive setup wizard for configuration.
        
        Returns:
            bool: True if setup completed successfully
        """
        print("🤖 RAG Telegram Bot Configuration Setup")
        print("=" * 50)
        
        # Step 1: Choose environment
        print("\n1. Choose your environment:")
        self.list_templates()
        
        while True:
            env_choice = input("Enter environment name (development/production/testing): ").lower().strip()
            if env_choice in self.env_templates:
                break
            print("Invalid choice. Please choose from: development, production, testing")
        
        # Step 2: Copy template
        print(f"\n2. Setting up {env_choice} environment...")
        if not self.copy_template(env_choice):
            return False
        
        # Step 3: Guide user through required settings
        print("\n3. Please update the following required settings in your .env file:")
        print("   📝 Open .env file in your text editor")
        
        required_settings = [
            ("BOT_TOKEN", "Get from @BotFather on Telegram"),
            ("OPENAI_API_KEY", "Get from https://platform.openai.com/api-keys"),
            ("ALLOW_USERS", "Your Telegram user ID (optional but recommended)"),
        ]
        
        for setting, description in required_settings:
            print(f"   • {setting}: {description}")
        
        print("\n4. Optional settings you may want to customize:")
        optional_settings = [
            ("DEFAULT_LANG", "Response language (fa/en)"),
            ("LLM_MODEL", "AI model to use"),
            ("RAG_CHUNK_SIZE", "Text processing chunk size"),
            ("SECURITY_MAX_FILE_SIZE_MB", "Maximum upload file size"),
        ]
        
        for setting, description in optional_settings:
            print(f"   • {setting}: {description}")
        
        # Step 4: Wait for user to edit
        input("\nPress Enter after you've updated the .env file...")
        
        # Step 5: Validate configuration
        print("\n5. Validating configuration...")
        if self.validate_env_file():
            print("\n✅ Setup completed successfully!")
            print("You can now run the bot with: python main.py")
            return True
        else:
            print("\n❌ Configuration validation failed.")
            print("Please fix the errors and run the validation again.")
            return False
    
    def create_directories(self) -> None:
        """Create necessary directories for the application."""
        directories = [
            self.project_root / "data",
            self.project_root / "data" / "vector_store",
            self.project_root / "logs",
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {str(e)}")
    
    def check_dependencies(self) -> Dict[str, bool]:
        """
        Check if required dependencies are installed.
        
        Returns:
            Dict[str, bool]: Dependency check results
        """
        dependencies = {
            "fastapi": "HTTP API framework",
            "openai": "OpenAI API client",
            "faiss-cpu": "Vector similarity search",
            "pydantic": "Data validation",
            "python-dotenv": "Environment file loading",
            "loguru": "Advanced logging",
        }
        
        results = {}
        
        for package, description in dependencies.items():
            try:
                __import__(package.replace("-", "_"))
                results[package] = True
                logger.info(f"✅ {package}: {description}")
            except ImportError:
                results[package] = False
                logger.error(f"❌ {package}: {description} - NOT INSTALLED")
        
        return results
    
    def install_dependencies(self) -> bool:
        """
        Install missing dependencies.
        
        Returns:
            bool: True if installation successful
        """
        try:
            import subprocess
            
            logger.info("Installing dependencies from requirements.txt...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", 
                str(self.project_root / "requirements.txt")
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Dependencies installed successfully")
                return True
            else:
                logger.error(f"❌ Failed to install dependencies: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install dependencies: {str(e)}")
            return False


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="RAG Bot Configuration Setup")
    parser.add_argument("--list", action="store_true", help="List available templates")
    parser.add_argument("--template", type=str, help="Copy specific template to .env")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing .env")
    parser.add_argument("--validate", action="store_true", help="Validate current .env file")
    parser.add_argument("--interactive", action="store_true", help="Run interactive setup")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies")
    parser.add_argument("--create-dirs", action="store_true", help="Create necessary directories")
    
    args = parser.parse_args()
    
    setup = ConfigurationSetup()
    
    # If no arguments provided, run interactive setup
    if not any(vars(args).values()):
        args.interactive = True
    
    success = True
    
    if args.list:
        setup.list_templates()
    
    if args.template:
        success = setup.copy_template(args.template, args.force) and success
    
    if args.validate:
        success = setup.validate_env_file() and success
    
    if args.check_deps:
        deps = setup.check_dependencies()
        success = all(deps.values()) and success
    
    if args.install_deps:
        success = setup.install_dependencies() and success
    
    if args.create_dirs:
        setup.create_directories()
    
    if args.interactive:
        success = setup.interactive_setup() and success
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
