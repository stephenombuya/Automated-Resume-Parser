# Makes all shell scripts in the scripts directory executable

echo "Making all shell scripts executable..."

# Find and make all .sh files executable
find scripts/ -type f -name "*.sh" -exec chmod +x {} \;

echo "✓ Scripts are now executable"
echo ""
echo "You can now run:"
echo "  ./scripts/setup.sh"
echo "  ./scripts/backup.sh"
echo "  ./scripts/cleanup.sh"
