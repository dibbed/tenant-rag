"""Question answering components"""

from .chain import QAChain
from .prompting import PromptBuilder, PromptTemplate


class QAGenerator(QAChain):
    """Question Answering Generator component based on QAChain."""
    pass


__all__ = ["PromptBuilder", "PromptTemplate", "QAChain", "QAGenerator"]

