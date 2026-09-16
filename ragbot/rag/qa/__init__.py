"""Question answering components"""

from .chain import QAChain
from .prompting import PromptBuilder


class QAGenerator(QAChain):
    """Question Answering Generator component based on QAChain."""
    pass


__all__ = ["QAChain", "PromptBuilder", "QAGenerator"]

