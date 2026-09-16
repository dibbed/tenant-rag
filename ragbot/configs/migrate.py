#!/usr/bin/env python3
"""
Configuration Migration Utility.

This script helps migrate configuration files between different versions
and formats of the RAG Telegram Bot.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

from ragbot.outputs.logger import logger


class ConfigurationMigrator:
    """Utility for migrating configuration files."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.migrations = [
            self._migrate_v1_to_v2,
            self._migrate_v2_to_v3,
        ]
    
    def detect_version(self, env_path: Path) -> str:
        """
        Detect the version of a configuration file.
        
        Args:
            env_path: Path to the environment file
            
        Returns:
            str: Detected version (v1, v2, v3, unknown)
        """
        if not env_path.exists():
            return "unknown"
        
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for version indicators
            if "# RAG Telegram Assistant Configuration" in content:
                if "MONITORING_" in content and "SECURITY_" in content:
                    return "v3"  # Current version
                elif "LLM_" in content and "EMBED_" in content:
                    return "v2"  # Intermediate version
                else:
                    return "v1"  # Early version
            
            # Legacy format detection
            if "BOT_TOKEN" in content and "OPENAI_API_KEY" in content:
                if "CHUNK_SIZE" in content:
                    return "v1"
                else:
                    return "legacy"
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"Failed to detect version: {str(e)}")
            return "unknown"
    
    def migrate_configuration(self, env_path: Path, target_version: str = "v3") -> bool:
        """
        Migrate a configuration file to the target version.
        
        Args:
            env_path: Path to the environment file
            target_version: Target version to migrate to
            
        Returns:
            bool: True if migration successful
        """
        current_version = self.detect_version(env_path)
        
        if current_version == "unknown":
            logger.error("Cannot detect configuration version")
            return False
        
        if current_version == target_version:
            logger.info(f"Configuration is already at version {target_version}")
            return True
        
        logger.info(f"Migrating configuration from {current_version} to {target_version}")
        
        # Create backup
        backup_path = env_path.with_suffix(f'.env.backup.{current_version}')
        try:
            import shutil
            shutil.copy2(env_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return False
        
        # Apply migrations
        try:
            config_data = self._load_env_file(env_path)
            
            # Apply migrations in sequence
            version_order = ["legacy", "v1", "v2", "v3"]
            current_idx = version_order.index(current_version)
            target_idx = version_order.index(target_version)
            
            for i in range(current_idx, target_idx):
                migration_func = self.migrations[i]
                config_data = migration_func(config_data)
                logger.info(f"Applied migration: {version_order[i]} -> {version_order[i+1]}")
            
            # Write migrated configuration
            self._write_env_file(env_path, config_data, target_version)
            logger.info("✅ Migration completed successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            
            # Restore backup
            try:
                import shutil
                shutil.copy2(backup_path, env_path)
                logger.info("Restored backup due to migration failure")
            except Exception:
                pass
            
            return False
    
    def _load_env_file(self, env_path: Path) -> Dict[str, str]:
        """Load environment file into a dictionary."""
        config_data = {}
        
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config_data[key.strip()] = value.strip()
        
        return config_data
    
    def _write_env_file(self, env_path: Path, config_data: Dict[str, str], version: str) -> None:
        """Write configuration data to environment file."""
        
        # Load the appropriate template
        template_path = self.project_root / ".env.example"
        if not template_path.exists():
            raise FileNotFoundError("Template file not found")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Replace template values with actual configuration
        output_lines = []
        
        for line in template_content.split('\n'):
            if '=' in line and not line.strip().startswith('#'):
                key = line.split('=')[0].strip()
                if key in config_data:
                    output_lines.append(f"{key}={config_data[key]}")
                else:
                    output_lines.append(line)  # Keep template default
            else:
                output_lines.append(line)
        
        # Write the migrated file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
    
    def _migrate_v1_to_v2(self, config_data: Dict[str, str]) -> Dict[str, str]:
        """Migrate from v1 to v2 format."""
        migrated = config_data.copy()
        
        # Rename old keys to new format
        key_mappings = {
            "CHUNK_SIZE": "RAG_CHUNK_SIZE",
            "CHUNK_OVERLAP": "RAG_CHUNK_OVERLAP", 
            "TOP_K": "RAG_TOP_K",
            "MAX_TOKENS": "LLM_MAX_TOKENS",
            "TEMPERATURE": "LLM_TEMPERATURE",
            "EMBED_MODEL": "EMBED_MODEL",
            "EMBED_PROVIDER": "EMBED_PROVIDER",
        }
        
        for old_key, new_key in key_mappings.items():
            if old_key in migrated:
                migrated[new_key] = migrated.pop(old_key)
        
        # Add new required settings with defaults
        new_settings = {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-3.5-turbo",
            "LLM_TIMEOUT": "30.0",
            "EMBED_BATCH_SIZE": "100",
            "EMBED_TIMEOUT": "30.0",
            "RAG_SIMILARITY_THRESHOLD": "0.7",
            "RAG_MAX_CHUNKS_PER_DOCUMENT": "1000",
        }
        
        for key, default_value in new_settings.items():
            if key not in migrated:
                migrated[key] = default_value
        
        return migrated
    
    def _migrate_v2_to_v3(self, config_data: Dict[str, str]) -> Dict[str, str]:
        """Migrate from v2 to v3 format."""
        migrated = config_data.copy()
        
        # Add new security settings
        security_settings = {
            "SECURITY_MAX_FILE_SIZE_MB": migrated.get("MAX_FILE_SIZE_MB", "50"),
            "SECURITY_ALLOWED_FILE_TYPES": "pdf,txt,docx,html",
            "SECURITY_RATE_LIMIT_REQUESTS": migrated.get("RATE_LIMIT_REQUESTS", "10"),
            "SECURITY_RATE_LIMIT_WINDOW": migrated.get("RATE_LIMIT_WINDOW", "60"),
            "SECURITY_ENABLE_USER_ALLOWLIST": "true",
        }
        
        # Add new monitoring settings
        monitoring_settings = {
            "MONITORING_ENABLE_METRICS": migrated.get("ENABLE_METRICS", "true"),
            "MONITORING_METRICS_PORT": migrated.get("METRICS_PORT", "8080"),
            "MONITORING_HEALTH_CHECK_INTERVAL": "30",
            "MONITORING_LOG_LEVEL": migrated.get("LOG_LEVEL", "INFO"),
        }
        
        # Add new database settings
        database_settings = {
            "DATABASE_URL": migrated.get("DATABASE_URL", "sqlite:///./data/ragbot.db"),
            "DATABASE_ECHO": "false",
            "DATABASE_POOL_SIZE": "5",
            "DATABASE_MAX_OVERFLOW": "10",
        }
        
        # Add new Redis settings
        redis_settings = {
            "REDIS_URL": migrated.get("REDIS_URL", "redis://localhost:6379/0"),
            "REDIS_MAX_CONNECTIONS": "10",
            "REDIS_SOCKET_TIMEOUT": "5.0",
        }
        
        # Merge all new settings
        migrated.update(security_settings)
        migrated.update(monitoring_settings)
        migrated.update(database_settings)
        migrated.update(redis_settings)
        
        # Remove old keys that have been replaced
        old_keys = [
            "MAX_FILE_SIZE_MB", "RATE_LIMIT_REQUESTS", "RATE_LIMIT_WINDOW",
            "ENABLE_METRICS", "METRICS_PORT", "LOG_LEVEL"
        ]
        
        for old_key in old_keys:
            migrated.pop(old_key, None)
        
        return migrated
    
    def validate_migration(self, env_path: Path) -> bool:
        """
        Validate a migrated configuration file.
        
        Args:
            env_path: Path to the migrated environment file
            
        Returns:
            bool: True if validation successful
        """
        try:
            from ragbot.configs.validator import ConfigurationValidator
            validator = ConfigurationValidator()
            return validator.validate_configuration()
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return False
    
    def generate_migration_report(self, env_path: Path) -> Dict[str, any]:
        """
        Generate a migration report for a configuration file.
        
        Args:
            env_path: Path to the environment file
            
        Returns:
            Dict: Migration report
        """
        current_version = self.detect_version(env_path)
        
        report = {
            "file_path": str(env_path),
            "current_version": current_version,
            "target_version": "v3",
            "migration_needed": current_version != "v3",
            "backup_recommended": True,
            "estimated_changes": [],
        }
        
        if current_version == "v1":
            report["estimated_changes"].extend([
                "Rename CHUNK_SIZE to RAG_CHUNK_SIZE",
                "Rename MAX_TOKENS to LLM_MAX_TOKENS", 
                "Add new LLM provider settings",
                "Add new security settings",
                "Add new monitoring settings",
            ])
        elif current_version == "v2":
            report["estimated_changes"].extend([
                "Add new security settings",
                "Add new monitoring settings",
                "Add new database settings",
                "Reorganize existing settings",
            ])
        
        return report


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="RAG Bot Configuration Migration")
    parser.add_argument("--detect", type=str, help="Detect version of configuration file")
    parser.add_argument("--migrate", type=str, help="Migrate configuration file")
    parser.add_argument("--target", type=str, default="v3", help="Target version for migration")
    parser.add_argument("--validate", type=str, help="Validate migrated configuration")
    parser.add_argument("--report", type=str, help="Generate migration report")
    parser.add_argument("--auto", action="store_true", help="Auto-migrate .env file if needed")
    
    args = parser.parse_args()
    
    migrator = ConfigurationMigrator()
    success = True
    
    if args.detect:
        env_path = Path(args.detect)
        version = migrator.detect_version(env_path)
        print(f"Configuration version: {version}")
    
    if args.migrate:
        env_path = Path(args.migrate)
        success = migrator.migrate_configuration(env_path, args.target) and success
    
    if args.validate:
        env_path = Path(args.validate)
        success = migrator.validate_migration(env_path) and success
    
    if args.report:
        env_path = Path(args.report)
        report = migrator.generate_migration_report(env_path)
        print(json.dumps(report, indent=2))
    
    if args.auto:
        env_path = Path(".env")
        if env_path.exists():
            version = migrator.detect_version(env_path)
            if version != "v3":
                logger.info(f"Auto-migrating .env from {version} to v3")
                success = migrator.migrate_configuration(env_path, "v3") and success
            else:
                logger.info("Configuration is already up to date")
        else:
            logger.warning(".env file not found")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
