"""
NativeFrames — Vercel Serverless Entrypoint
This module is the WSGI application callable that Vercel's Python runtime invokes.
It must export a variable named `app` that is a WSGI callable.
"""
import os
import sys

# Ensure the project root is on the path so `app` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use production config on Vercel; fall back to development locally
from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'production'))
