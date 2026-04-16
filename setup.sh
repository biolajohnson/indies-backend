#!/bin/bash
# Run this once to get the backend fully set up

set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "⚙️  Setting up environment..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "   Created .env — update it with your real keys before running in production"
fi

echo "🗄️  Initialising database migrations..."
flask db init
flask db migrate -m "Initial schema: filmmakers, campaigns, donations"
flask db upgrade

echo "🌱 Seeding sample data..."
python seed.py

echo ""
echo "✅ Setup complete! Start the server with:"
echo "   flask run"
echo ""
echo "API endpoints:"
echo "   GET  /api/health"
echo "   GET  /api/campaigns/"
echo "   GET  /api/campaigns/<id>"
echo "   POST /api/campaigns/           (JWT required)"
echo "   GET  /api/filmmakers/"
echo "   GET  /api/filmmakers/<id>"
echo "   POST /api/auth/register"
echo "   POST /api/auth/login"
echo "   GET  /api/auth/me              (JWT required)"
echo "   POST /api/donations/"
