#!/bin/bash

echo "================================================"
echo "      🔍 OWNIZE FACE SEARCH (DEV MODE)         "
echo "================================================"
echo ""
echo "🚀 Starting Ownize Face Search Application..."
echo "📊 Development mode - detailed logs enabled"
echo ""
echo "💡 Tips:"
echo "• Camera permission may be requested on first use"
echo "• You can minimize this terminal window"
echo "• Do NOT close this window while app is running"
echo "• Watch this window for debug information"
echo ""
echo "================================================"
echo ""

# Navigate to working debug build
cd "$(dirname "$0")/dist/FaceSearchApp_Debug"

# Run app
./FaceSearchApp_Debug

echo ""
echo "✅ Ownize Face Search has closed"
echo "📊 Check above for any error messages"
echo "Press Enter to close this window..."
read
