#!/usr/bin/env python3
"""
RAGBot - API Backend Entry Point
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ragbot.main import main

if __name__ == "__main__":
    main()
