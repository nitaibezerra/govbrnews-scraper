# conftest.py
import os
import sys

# Suppose your tests/ folder is at the same level as src/.
# This finds the parent directory (one level up) and adds it to sys.path.
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, project_root)
