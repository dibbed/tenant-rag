"""
Plugin Validator

This module provides validation functionality for plugins,
including security checks, compatibility validation, and dependency verification.
"""

import ast
from pathlib import Path
from typing import List, Dict, Any, Optional

from ragbot.outputs.logger import logger
from .base_plugin import BasePlugin, PluginType


class PluginValidationError(Exception):
    """Exception raised when plugin validation fails"""

    pass


class PluginValidator:
    """
    Validator for plugins to ensure security and compatibility

    Provides comprehensive validation including:
    - Security analysis
    - Dependency checking
    - Code quality validation
    - Metadata verification
    - API compatibility checks
    """

    def __init__(
        self,
        allowed_imports: Optional[List[str]] = None,
        banned_functions: Optional[List[str]] = None,
    ):
        """
        Initialize plugin validator

        Args:
            allowed_imports: List of allowed import modules
            banned_functions: List of banned function calls
        """
        self.allowed_imports = allowed_imports or [
            "ragbot",
            "typing",
            "datetime",
            "pathlib",
            "dataclasses",
            "abc",
            "asyncio",
            "json",
            "logging",
            "collections",
            "statistics",
        ]

        self.banned_functions = banned_functions or [
            "eval",
            "exec",
            "__import__",
            "compile",
            "open",
            "input",
            "raw_input",
            "execfile",
            "file",
            "apply",
        ]

    async def validate_plugin_file(self, plugin_path: str) -> Dict[str, Any]:
        """
        Validate a plugin file

        Args:
            plugin_path: Path to plugin file

        Returns:
            Validation results dictionary
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "security_score": 100,
            "quality_score": 100,
        }

        try:
            plugin_path = Path(plugin_path)

            if not plugin_path.exists():
                results["errors"].append(f"Plugin file does not exist: {plugin_path}")
                results["valid"] = False
                return results

            # Basic file validation
            if plugin_path.suffix != ".py":
                results["errors"].append("Plugin file must be a Python file (.py)")
                results["valid"] = False

            # Read and parse file
            with open(plugin_path, "r", encoding="utf-8") as f:
                content = f.read()

            # AST analysis
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                results["errors"].append(f"Syntax error in plugin file: {e}")
                results["valid"] = False
                return results

            # Security validation
            security_issues = await self._validate_security(tree, plugin_path.name)
            results["errors"].extend(security_issues)
            results["security_score"] = max(0, 100 - len(security_issues) * 20)

            # Code quality validation
            quality_issues = await self._validate_code_quality(tree)
            results["warnings"].extend(quality_issues)
            results["quality_score"] = max(0, 100 - len(quality_issues) * 10)

            # Structure validation
            structure_issues = await self._validate_structure(tree)
            results["errors"].extend(structure_issues)

            # Dependency validation
            dependency_issues = await self._validate_dependencies(tree)
            results["warnings"].extend(dependency_issues)

            # Check for required components
            required_issues = await self._validate_required_components(tree)
            results["errors"].extend(required_issues)

            # Overall validation
            if results["errors"]:
                results["valid"] = False

        except Exception as e:
            logger.error(f"Validation error for {plugin_path}: {e}")
            results["errors"].append(f"Validation process failed: {e}")
            results["valid"] = False

        return results

    async def validate_plugin_instance(self, plugin: BasePlugin) -> Dict[str, Any]:
        """
        Validate a plugin instance

        Args:
            plugin: Plugin instance to validate

        Returns:
            Validation results dictionary
        """
        results = {"valid": True, "errors": [], "warnings": [], "metadata_valid": True}

        try:
            # Check metadata
            try:
                metadata = plugin.get_metadata()

                # Validate required metadata fields
                required_fields = [
                    "name",
                    "version",
                    "description",
                    "author",
                    "plugin_type",
                ]
                for field in required_fields:
                    if not hasattr(metadata, field) or not getattr(metadata, field):
                        results["errors"].append(
                            f"Missing required metadata field: {field}"
                        )
                        results["metadata_valid"] = False

                # Validate plugin type
                if not isinstance(metadata.plugin_type, PluginType):
                    results["errors"].append("Invalid plugin type")
                    results["metadata_valid"] = False

            except Exception as e:
                results["errors"].append(f"Metadata validation failed: {e}")
                results["metadata_valid"] = False

            # Check required methods
            required_methods = ["initialize", "execute", "cleanup"]
            for method_name in required_methods:
                if not hasattr(plugin, method_name):
                    results["errors"].append(f"Missing required method: {method_name}")

                elif not callable(getattr(plugin, method_name)):
                    results["errors"].append(
                        f"Required method {method_name} is not callable"
                    )

            # Validate configuration
            try:
                config_errors = plugin.validate_config()
                results["errors"].extend(config_errors)
            except Exception as e:
                results["warnings"].append(f"Config validation failed: {e}")

            # Check for hooks registration
            if hasattr(plugin, "hooks") and plugin.hooks:
                for hook_type, hooks in plugin.hooks.items():
                    for hook in hooks:
                        if not callable(hook):
                            results["errors"].append(
                                f"Invalid hook function for {hook_type}"
                            )

            # Validation errors make plugin invalid
            if results["errors"]:
                results["valid"] = False

        except Exception as e:
            logger.error(f"Plugin instance validation error: {e}")
            results["errors"].append(f"Plugin instance validation failed: {e}")
            results["valid"] = False

        return results

    async def _validate_security(self, tree: ast.AST, filename: str) -> List[str]:
        """
        Validate plugin security

        Args:
            tree: AST of plugin file
            filename: Name of plugin file

        Returns:
            List of security issues
        """
        issues = []

        # Check for dangerous imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not self._is_import_allowed(module_name):
                        issues.append(f"Banned import: {module_name}")

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module
                if not self._is_import_allowed(module_name):
                    issues.append(f"Banned import from: {module_name}")

        # Check for dangerous function calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None

                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name and func_name in self.banned_functions:
                    issues.append(f"Dangerous function call: {func_name}")

        # Check for file system access
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    issues.append("Direct file access detected - use approved methods")

        # Check for network operations (example - customize as needed)
        network_modules = ["socket", "urllib", "requests", "http"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in network_modules:
                        issues.append(f"Network access detected: {alias.name}")

        return issues

    async def _validate_code_quality(self, tree: ast.AST) -> List[str]:
        """
        Validate code quality

        Args:
            tree: AST of plugin file

        Returns:
            List of quality issues
        """
        issues = []

        # Check for overly complex functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)
                if complexity > 10:
                    issues.append(
                        f"Complex function detected: {node.name} (complexity: {complexity})"
                    )

        # Check for missing docstrings
        functions_without_docstrings = 0
        total_functions = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_functions += 1
                if not ast.get_docstring(node):
                    functions_without_docstrings += 1

        if total_functions > 0:
            docstring_ratio = functions_without_docstrings / total_functions
            if docstring_ratio > 0.5:
                issues.append(
                    f"Many functions without docstrings: {docstring_ratio:.1%}"
                )

        return issues

    async def _validate_structure(self, tree: ast.AST) -> List[str]:
        """
        Validate plugin structure

        Args:
            tree: AST of plugin file

        Returns:
            List of structure issues
        """
        issues = []

        # Look for plugin class
        has_plugin_class = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from BasePlugin
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BasePlugin":
                        has_plugin_class = True
                        break

        if not has_plugin_class:
            issues.append("No plugin class found (must inherit from BasePlugin)")

        return issues

    async def _validate_dependencies(self, tree: ast.AST) -> List[str]:
        """
        Validate dependencies

        Args:
            tree: AST of plugin file

        Returns:
            List of dependency warnings
        """
        issues = []
        imports = set()

        # Collect all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        # Check for external dependencies
        external_deps = []
        for imp in imports:
            if imp not in self.allowed_imports and not imp.startswith("ragbot"):
                external_deps.append(imp)

        if external_deps:
            issues.append(f"External dependencies detected: {', '.join(external_deps)}")

        return issues

    async def _validate_required_components(self, tree: ast.AST) -> List[str]:
        """
        Validate required components exist

        Args:
            tree: AST of plugin file

        Returns:
            List of missing component issues
        """
        issues = []

        # Check for required methods (basic check without loading)
        has_execute = False
        has_initialize = False
        has_cleanup = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ["execute", "initialize", "cleanup"]:
                    if "execute" == node.name:
                        has_execute = True
                    elif "initialize" == node.name:
                        has_initialize = True
                    elif "cleanup" == node.name:
                        has_cleanup = True

        if not has_execute:
            issues.append("Required method 'execute' not found")

        if not has_initialize:
            issues.append("Required method 'initialize' not found")

        if not has_cleanup:
            issues.append("Required method 'cleanup' not found")

        return issues

    def _is_import_allowed(self, module_name: str) -> bool:
        """
        Check if import is allowed

        Args:
            module_name: Name of module to check

        Returns:
            True if allowed, False otherwise
        """
        return module_name in self.allowed_imports

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """
        Calculate cyclomatic complexity

        Args:
            node: Function definition node

        Returns:
            Complexity score
        """
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity
