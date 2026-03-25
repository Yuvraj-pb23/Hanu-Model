#!/bin/bash
source ../.venv/bin/activate
python3 ../manage.py runserver 0.0.0.0:8000 > ../server.log 2>&1 &
SERVER_PID=$!
sleep 45
python3 test_transcription.py
kill $SERVER_PID
