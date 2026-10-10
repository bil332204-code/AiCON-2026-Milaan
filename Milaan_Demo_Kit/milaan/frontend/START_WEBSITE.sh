#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
echo 'Keep the backend running on port 8000. Open http://localhost:8080.'
exec python3 -m http.server 8080 --bind 127.0.0.1 --directory dist
