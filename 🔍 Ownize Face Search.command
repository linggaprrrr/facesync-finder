#!/bin/bash
# Navigate to debug build (yang working)
cd "$(dirname "$0")/dist/FaceSearchApp_Debug"

# Set terminal title and appearance
echo -e "\033]0;Ownize Face Search\007"
printf '\e[8;30;90t'

# Clear screen and show Ownize branding
clear
echo ""
echo "  ╔══════════════════════════════════════════════════════════════════════════════╗"
echo "  ║                                                                              ║"
echo "  ║                            🔍 OWNIZE FACE SEARCH                            ║"
echo "  ║                         Advanced AI Photo Recognition                       ║"
echo "  ║                                                                              ║"
echo "  ╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  🚀 Starting Ownize Face Search..."
echo "  📱 Custom Ownize branding applied"
echo "  🎨 Look for Ownize logo in Dock when app runs"
echo ""
echo "  💡 Features:"
echo "     🤖 AI-powered face recognition"
echo "     📸 Real-time camera detection  "
echo "     🔍 Instant photo search"
echo "     🔒 Privacy-first processing"
echo ""
echo "  📋 Instructions:"
echo "     1. Click 'Search by Face' in the main window"
echo "     2. Allow camera access when prompted"
echo "     3. Position your face clearly in camera"
echo "     4. Search and find your photos instantly!"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run app
./FaceSearchApp_Debug

echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Ownize Face Search closed successfully"
echo "  🙏 Thank you for using Ownize products!"
echo ""
echo "  Press Enter to close this window..."
read
