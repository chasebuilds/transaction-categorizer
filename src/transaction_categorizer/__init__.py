"""Categorize bank and card transactions with an editable rules file."""

from transaction_categorizer.core import Rule, Txn, categorize, find_duplicates, load_rules

__all__ = ["Rule", "Txn", "categorize", "find_duplicates", "load_rules"]
__version__ = "0.1.0"
