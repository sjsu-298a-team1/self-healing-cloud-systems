import os
import sys

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
if DATA not in sys.path:
    sys.path.insert(0, DATA)
