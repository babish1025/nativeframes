import os
import sys

# Add project root directory to path for serverless imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import app

# Vercel entrypoint
app = app
