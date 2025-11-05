#!/bin/bash
echo "Starting deployment..."
pip install -r requirements.txt
echo "Dependencies installed"
uvicorn app.main:app --host 0.0.0.0 --port $PORT


