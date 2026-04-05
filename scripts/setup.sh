# Production setup script for Resume Parser

set -e

echo "=========================================="
echo "Resume Parser - Production Setup"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p uploads logs temp

# Set permissions
echo "Setting permissions..."
chmod 755 uploads logs temp

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration"
fi

# Initialize database
echo "Initializing database..."
export FLASK_APP=run.py
flask db upgrade

# Download spaCy model
echo "Downloading spaCy model..."
python -m spacy download en_core_web_sm

# Run environment check
echo "Running environment check..."
python run.py --check

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Run 'python run.py' to start the development server"
echo "3. For production, use: gunicorn -c gunicorn.conf.py wsgi:app"
echo ""
