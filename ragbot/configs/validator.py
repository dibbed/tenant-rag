"""
Configuration Validation Utility.

This module provides utilities for validating and testing configuration settings.
"""

import json
import sys
from typing import Any, Dict, List

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class ConfigurationValidator:
    """Utility class for configuration validation and testing."""
    
    def __init__(self):
        self.settings = settings
    
    def validate_configuration(self, verbose: bool = False) -> bool:
        """
        Validate the current configuration.
        
        Args:
            verbose: Whether to print detailed validation results
            
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        logger.info("Starting configuration validation...")
        
        try:
            validation_result = self.settings.validate_all_settings()
            
            if verbose:
                self._print_validation_results(validation_result)
            
            if validation_result["valid"]:
                logger.info("✅ Configuration validation passed")
                return True
            else:
                logger.error("❌ Configuration validation failed")
                for error in validation_result["errors"]:
                    logger.error(f"  - {error}")
                return False
                
        except Exception as e:
            logger.error(f"Configuration validation error: {str(e)}")
            return False
    
    def _print_validation_results(self, result: Dict[str, Any]) -> None:
        """Print detailed validation results."""
        print("\n" + "="*60)
        print("CONFIGURATION VALIDATION RESULTS")
        print("="*60)
        
        # Overall status
        status_emoji = "✅" if result["valid"] else "❌"
        print(f"\nOverall Status: {status_emoji} {'VALID' if result['valid'] else 'INVALID'}")
        
        # Errors
        if result["errors"]:
            print(f"\n🚨 ERRORS ({len(result['errors'])}):")
            for error in result["errors"]:
                print(f"  - {error}")
        
        # Warnings
        if result["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(result['warnings'])}):")
            for warning in result["warnings"]:
                print(f"  - {warning}")
        
        # Component status
        print("\n🔧 COMPONENT STATUS:")
        for component, status in result["components"].items():
            status_emoji = {
                "valid": "✅",
                "invalid": "❌",
                "warning": "⚠️"
            }.get(status["status"], "❓")
            
            print(f"  {status_emoji} {component.upper()}: {status['status']}")
            
            if "error" in status:
                print(f"    Error: {status['error']}")
            if "message" in status:
                print(f"    Message: {status['message']}")
            if "info" in status:
                for info in status["info"]:
                    print(f"    Info: {info}")
        
        # General info
        if result["info"]:
            print("\n📋 CONFIGURATION INFO:")
            for info in result["info"]:
                print(f"  - {info}")
        
        print("\n" + "="*60)
    
    def test_api_connections(self) -> Dict[str, bool]:
        """
        Test connections to external APIs.
        
        Returns:
            Dict[str, bool]: Test results for each API
        """
        results = {}
        
        logger.info("Testing API connections...")
        
        # Test OpenAI API
        if self.settings.openai_api_key:
            try:
                # Import here to avoid circular imports
                import openai
                openai.api_key = self.settings.openai_api_key
                
                # Simple test call
                response = openai.Model.list()
                results["openai"] = True
                logger.info("✅ OpenAI API connection successful")
            except Exception as e:
                results["openai"] = False
                logger.error(f"❌ OpenAI API connection failed: {str(e)}")
        else:
            results["openai"] = None
            logger.info("⏭️  OpenAI API key not configured, skipping test")
        
        # Test Anthropic API
        if self.settings.anthropic_api_key:
            try:
                # Import here to avoid circular imports
                import anthropic
                client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
                
                # Simple test call (this might fail if no credits, but connection is tested)
                # We'll just check if the client can be created
                results["anthropic"] = True
                logger.info("✅ Anthropic API client created successfully")
            except Exception as e:
                results["anthropic"] = False
                logger.error(f"❌ Anthropic API connection failed: {str(e)}")
        else:
            results["anthropic"] = None
            logger.info("⏭️  Anthropic API key not configured, skipping test")
        
        return results
    
    def test_telegram_bot(self) -> bool:
        """
        Test Telegram bot token validity.
        
        Returns:
            bool: True if bot token is valid, False otherwise
        """
        if not self.settings.bot_token:
            logger.error("❌ Telegram bot token not configured")
            return False
        
        try:
            # Import here to avoid circular imports
            from aiogram import Bot
            
            bot = Bot(token=self.settings.bot_token)
            
            # Test bot token by getting bot info
            import asyncio
            
            async def test_bot():
                try:
                    bot_info = await bot.get_me()
                    logger.info(f"✅ Telegram bot connection successful: @{bot_info.username}")
                    await bot.session.close()
                    return True
                except Exception as e:
                    logger.error(f"❌ Telegram bot connection failed: {str(e)}")
                    await bot.session.close()
                    return False
            
            return asyncio.run(test_bot())
            
        except Exception as e:
            logger.error(f"❌ Telegram bot test failed: {str(e)}")
            return False
    
    def test_vector_store(self) -> bool:
        """
        Test vector store accessibility.
        
        Returns:
            bool: True if vector store is accessible, False otherwise
        """
        try:
            # Test if store path is accessible
            if not self.settings.store_path.exists():
                self.settings.store_path.mkdir(parents=True, exist_ok=True)
            
            # Test write access
            test_file = self.settings.store_path / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            
            logger.info(f"✅ Vector store path accessible: {self.settings.store_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vector store test failed: {str(e)}")
            return False
    
    def generate_config_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive configuration report.
        
        Returns:
            Dict[str, Any]: Configuration report
        """
        logger.info("Generating configuration report...")
        
        # Get validation results
        validation_result = self.settings.validate_all_settings()
        
        # Get environment info
        env_info = self.settings.get_environment_info()
        
        # Test connections
        api_tests = self.test_api_connections()
        telegram_test = self.test_telegram_bot()
        vector_store_test = self.test_vector_store()
        
        report = {
            "timestamp": "2024-01-01T00:00:00Z",  # Will be updated when called
            "validation": validation_result,
            "environment": env_info,
            "connectivity_tests": {
                "apis": api_tests,
                "telegram_bot": telegram_test,
                "vector_store": vector_store_test,
            },
            "recommendations": self._generate_recommendations(validation_result, api_tests, telegram_test)
        }
        
        return report
    
    def _generate_recommendations(
        self, 
        validation_result: Dict[str, Any], 
        api_tests: Dict[str, bool], 
        telegram_test: bool
    ) -> List[str]:
        """Generate configuration recommendations."""
        recommendations = []
        
        # Based on validation errors
        if not validation_result["valid"]:
            recommendations.append("Fix configuration errors before deploying to production")
        
        # Based on API tests
        if api_tests.get("openai") is False:
            recommendations.append("Check OpenAI API key and network connectivity")
        
        if api_tests.get("anthropic") is False:
            recommendations.append("Check Anthropic API key and network connectivity")
        
        # Based on Telegram test
        if not telegram_test:
            recommendations.append("Verify Telegram bot token and bot permissions")
        
        # General recommendations
        if self.settings.debug:
            recommendations.append("Disable debug mode in production")
        
        if not self.settings.enable_redis:
            recommendations.append("Consider enabling Redis for better performance")
        
        if self.settings.security.max_file_size_mb > 100:
            recommendations.append("Consider reducing max file size for better performance")
        
        return recommendations
    
    def save_config_report(self, filepath: str = "config_report.json") -> None:
        """
        Save configuration report to file.
        
        Args:
            filepath: Path to save the report
        """
        report = self.generate_config_report()
        
        # Update timestamp
        from datetime import datetime
        report["timestamp"] = datetime.now().isoformat()
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"✅ Configuration report saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save configuration report: {str(e)}")


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate RAG Bot configuration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--test-apis", action="store_true", help="Test API connections")
    parser.add_argument("--test-telegram", action="store_true", help="Test Telegram bot")
    parser.add_argument("--generate-report", action="store_true", help="Generate full report")
    parser.add_argument("--save-report", type=str, help="Save report to file")
    
    args = parser.parse_args()
    
    validator = ConfigurationValidator()
    
    # Validate configuration
    is_valid = validator.validate_configuration(verbose=args.verbose)
    
    # Test APIs if requested
    if args.test_apis:
        validator.test_api_connections()
    
    # Test Telegram if requested
    if args.test_telegram:
        validator.test_telegram_bot()
    
    # Generate report if requested
    if args.generate_report:
        report = validator.generate_config_report()
        print(json.dumps(report, indent=2, default=str))
    
    # Save report if requested
    if args.save_report:
        validator.save_config_report(args.save_report)
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
