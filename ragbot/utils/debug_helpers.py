"""
Debug helpers for troubleshooting pydantic and other errors.
"""

import traceback
from typing import Any, Dict, Optional

from ragbot.outputs.logger import logger


def log_pydantic_error(error: Exception, context: str = "", **kwargs: Any) -> None:
    """
    Log pydantic-related errors with detailed information.

    Args:
        error: The exception that occurred
        context: Additional context about where the error occurred
        **kwargs: Additional debugging information
    """
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "traceback": traceback.format_exc(),
        **kwargs,
    }

    logger.error_with_traceback(
        f"Pydantic error in {context}: {error}", exc_info=True, **error_info
    )


def inspect_pydantic_model(
    model_class: Any, instance: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Inspect a pydantic model for potential field naming issues.

    Args:
        model_class: The pydantic model class
        instance: Optional instance of the model

    Returns:
        Dict containing inspection results
    """
    inspection = {
        "model_name": getattr(model_class, "__name__", "Unknown"),
        "model_module": getattr(model_class, "__module__", "Unknown"),
        "fields": {},
        "potential_issues": [],
    }

    try:
        # Check for fields with leading underscores
        if hasattr(model_class, "model_fields"):
            for field_name, field_info in model_class.model_fields.items():
                inspection["fields"][field_name] = {
                    "type": str(field_info.annotation),
                    "default": getattr(field_info, "default", None),
                    "has_leading_underscore": field_name.startswith("_"),
                }

                if field_name.startswith("_"):
                    inspection["potential_issues"].append(
                        f"Field '{field_name}' starts with underscore"
                    )

        # Check for private attributes
        if hasattr(model_class, "__private_attributes__"):
            for attr_name in model_class.__private_attributes__:
                inspection["potential_issues"].append(
                    f"Private attribute '{attr_name}' found"
                )

        # Check instance if provided
        if instance:
            inspection["instance_fields"] = {}
            for field_name in dir(instance):
                if not field_name.startswith("__"):
                    value = getattr(instance, field_name, None)
                    inspection["instance_fields"][field_name] = {
                        "type": type(value).__name__,
                        "has_leading_underscore": field_name.startswith("_"),
                    }

                    if field_name.startswith("_"):
                        inspection["potential_issues"].append(
                            f"Instance field '{field_name}' starts with underscore"
                        )

    except Exception as e:
        inspection["inspection_error"] = str(e)
        inspection["potential_issues"].append(f"Inspection failed: {e}")

    return inspection


def log_model_inspection(
    model_class: Any, instance: Optional[Any] = None, context: str = ""
) -> None:
    """
    Log detailed inspection of a pydantic model.

    Args:
        model_class: The pydantic model class
        instance: Optional instance of the model
        context: Context for logging
    """
    inspection = inspect_pydantic_model(model_class, instance)

    logger.info(
        f"Pydantic model inspection for {context}",
        model_name=inspection["model_name"],
        model_module=inspection["model_module"],
        field_count=len(inspection["fields"]),
        potential_issues=inspection["potential_issues"],
    )

    if inspection["potential_issues"]:
        logger.warning(
            f"Potential pydantic issues found in {context}",
            issues=inspection["potential_issues"],
        )

    # Log detailed field information
    for field_name, field_info in inspection["fields"].items():
        logger.debug(
            f"Field '{field_name}' in {context}",
            field_name=field_name,
            field_type=field_info["type"],
            has_leading_underscore=field_info["has_leading_underscore"],
        )


def safe_pydantic_operation(
    operation_name: str, operation_func, *args, **kwargs
) -> Any:
    """
    Safely execute a pydantic operation with detailed error logging.

    Args:
        operation_name: Name of the operation for logging
        operation_func: Function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the operation or None if it failed
    """
    try:
        result = operation_func(*args, **kwargs)
        logger.debug(f"Pydantic operation '{operation_name}' completed successfully")
        return result

    except Exception as e:
        log_pydantic_error(
            e,
            context=f"pydantic_operation_{operation_name}",
            operation_name=operation_name,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
        )
        return None


def check_pydantic_compatibility() -> Dict[str, Any]:
    """
    Check pydantic version and compatibility.

    Returns:
        Dict containing compatibility information
    """
    compatibility_info = {
        "pydantic_version": "Unknown",
        "pydantic_v2": False,
        "issues": [],
    }

    try:
        import pydantic

        compatibility_info["pydantic_version"] = getattr(
            pydantic, "__version__", "Unknown"
        )

        # Check if it's pydantic v2
        if hasattr(pydantic, "BaseModel"):
            compatibility_info["pydantic_v2"] = True

        # Check for common compatibility issues
        if compatibility_info["pydantic_v2"]:
            compatibility_info["issues"].append(
                "Using Pydantic v2 - check for field naming restrictions"
            )

    except ImportError:
        compatibility_info["issues"].append("Pydantic not available")

    return compatibility_info
