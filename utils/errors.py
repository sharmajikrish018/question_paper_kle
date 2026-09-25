"""
utils/errors.py
Centralized custom exception classes.
"""


class QPAgentError(Exception):
    """Base error class for QP Agent."""
    pass


class ConfigurationError(QPAgentError):
    """Configuration or environment error."""
    pass


class BlueprintError(QPAgentError):
    """Blueprint generation or validation error."""
    pass


class QuestionBankError(QPAgentError):
    """Question bank parsing or validation error."""
    pass


class GenerationError(QPAgentError):
    """Paper generation pipeline error."""
    pass


class ValidationError(QPAgentError):
    """Paper validation rule failure."""
    pass


class ExportError(QPAgentError):
    """Paper export or rendering error."""
    pass


class DatabaseError(QPAgentError):
    """Database operation error."""
    pass


class FileError(QPAgentError):
    """File upload or access error."""
    pass


class LLMError(QPAgentError):
    """LLM provider or generation error."""
    pass


class ApprovalError(QPAgentError):
    """Operation requires faculty approval that has not been granted."""
    pass
