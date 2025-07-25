#!/bin/bash
# build_with_logo.sh - Build debug app + apply Ownize logo + create launchers

echo "🚀 Building Face Search with Ownize Logo"
echo "========================================"
echo

# Check if build exists or build new one
if [ ! -d "dist/FaceSearchApp_Debug" ]; then
    echo "❌ Debug build not found. Building it first..."
    
    # Clean previous builds
    rm -rf build dist *.spec
    
    # Build debug version (yang working)
    pyinstaller \
      --onedir \
      --console \
      --name "FaceSearchApp_Debug" \
      --exclude-module matplotlib \
      --exclude-module pandas \
      --exclude-module scipy \
      --exclude-module jupyter \
      --exclude-module notebook \
      --exclude-module IPython \
      --add-data ".env:." \
      --add-data "Info.plist:." \
      --osx-bundle-identifier "com.ownize.facesearch.debug" \
      main.py
    
    # Copy Info.plist for camera permissions
    if [ -f "Info.plist" ] && [ -d "dist/FaceSearchApp_Debug.app" ]; then
        cp Info.plist "dist/FaceSearchApp_Debug.app/Contents/Info.plist"
        echo "✅ Camera permissions added"
    fi
    
    echo "✅ Debug build completed"
else
    echo "✅ Using existing debug build"
fi

echo ""
echo "🎨 Applying Ownize Logo"
echo "======================"

# Check for Ownize logo
if [ -f "assets/ownize_logo.png" ]; then
    echo "✅ Found Ownize logo: assets/ownize_logo.png"
    
    # Create app icon from Ownize logo
    echo "🔄 Creating app icon..."
    if command -v sips >/dev/null 2>&1; then
        sips -z 512 512 "assets/ownize_logo.png" --out "app_icon.png" >/dev/null 2>&1
        echo "✅ Resized logo to 512x512"
    else
        cp "assets/ownize_logo.png" "app_icon.png"
        echo "✅ Using original logo size"
    fi
    
    # Create ICNS version
    cp "app_icon.png" "app_icon.icns"
    
    # Apply logo to .app bundle
    echo "📱 Applying logo to app bundle..."
    if [ -d "dist/FaceSearchApp_Debug.app" ]; then
        # Create Resources directory
        mkdir -p "dist/FaceSearchApp_Debug.app/Contents/Resources"
        
        # Copy icon files
        cp "app_icon.icns" "dist/FaceSearchApp_Debug.app/Contents/Resources/app_icon.icns"
        cp "app_icon.png" "dist/FaceSearchApp_Debug.app/Contents/Resources/app_icon.png"
        
        # Update Info.plist with icon reference
        if [ -f "dist/FaceSearchApp_Debug.app/Contents/Info.plist" ]; then
            # Remove existing icon reference if any
            sed -i '' '/CFBundleIconFile/,+1d' "dist/FaceSearchApp_Debug.app/Contents/Info.plist" 2>/dev/null
            
            # Add new icon reference
            sed -i '' 's|</dict>|    <key>CFBundleIconFile</key>\
    <string>app_icon</string>\
</dict>|' "dist/FaceSearchApp_Debug.app/Contents/Info.plist"
            
            echo "✅ Updated Info.plist with icon reference"
        fi
        
        # Update bundle identifier to Ownize
        sed -i '' 's|com.yourcompany.facesearchapp.debug|com.ownize.facesearch|g' "dist/FaceSearchApp_Debug.app/Contents/Info.plist" 2>/dev/null
        
        echo "✅ Logo applied to app bundle"
    fi
    
    # Force refresh icons
    echo "🔄 Refreshing icon cache..."
    
    # Clear Dock cache
    rm -rf ~/Library/Caches/com.apple.dock/ 2>/dev/null
    
    # Touch app bundle to update timestamp
    touch "dist/FaceSearchApp_Debug.app"
    touch "dist/FaceSearchApp_Debug.app/Contents/Info.plist" 2>/dev/null
    
    # Restart Dock to refresh icons
    killall Dock 2>/dev/null
    
    echo "✅ Icon cache refreshed"
    
else
    echo "⚠️ Ownize logo not found at: assets/ownize_logo.png"
    echo "💡 App will work without custom icon"
fi

echo ""
echo "🚀 Creating Ownize Launchers"
echo "============================"

# Create main Ownize-branded launcher
cat > "🔍 Ownize Face Search.command" << 'EOF'
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
EOF

chmod +x "🔍 Ownize Face Search.command"

# Create simple launcher for quick access
cat > "FaceSearch.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/dist/FaceSearchApp_Debug"
echo -e "\033]0;Ownize Face Search\007"
clear
echo "🔍 Starting Ownize Face Search..."
echo "📱 App will open in a moment..."
echo ""
./FaceSearchApp_Debug
EOF

chmod +x "FaceSearch.command"

# Create AppleScript .app launcher (no terminal window)
cat > "create_app_launcher.scpt" << 'EOF'
tell application "Finder"
    set appPath to (path to me as string) & "dist:FaceSearchApp_Debug:FaceSearchApp_Debug"
    set appPOSIX to POSIX path of (appPath as alias)
end tell

do shell script appPOSIX
EOF

# Convert to .app if osascript available
if command -v osacompile >/dev/null 2>&1; then
    osacompile -o "Ownize Face Search.app" "create_app_launcher.scpt"
    rm "create_app_launcher.scpt"
    
    # Apply Ownize logo to launcher .app too
    if [ -f "app_icon.icns" ] && [ -d "Ownize Face Search.app" ]; then
        mkdir -p "Ownize Face Search.app/Contents/Resources"
        cp "app_icon.icns" "Ownize Face Search.app/Contents/Resources/app_icon.icns"
        
        # Update launcher .app Info.plist
        if [ -f "Ownize Face Search.app/Contents/Info.plist" ]; then
            sed -i '' 's|</dict>|    <key>CFBundleIconFile</key>\
    <string>app_icon</string>\
</dict>|' "Ownize Face Search.app/Contents/Info.plist"
        fi
        
        echo "✅ Applied logo to launcher .app bundle"
    fi
fi

# Create development launcher (with detailed logs)
cat > "launch_facesearch_dev.sh" << 'EOF'
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
EOF

chmod +x "launch_facesearch_dev.sh"

echo ""
echo "🎉 Build Complete with Ownize Branding!"
echo "========================================"
echo ""
echo "✅ Created:"
echo "   📱 dist/FaceSearchApp_Debug/ (main app)"
if [ -d "dist/FaceSearchApp_Debug.app" ]; then
    echo "   📱 dist/FaceSearchApp_Debug.app (with Ownize logo)"
fi
if [ -f "app_icon.icns" ]; then
    echo "   🎨 app_icon.icns (Ownize logo icon)"
fi
echo "   🚀 🔍 Ownize Face Search.command (main launcher)"
echo "   🚀 FaceSearch.command (simple launcher)"
if [ -f "Ownize Face Search.app" ]; then
    echo "   📱 Ownize Face Search.app (no terminal launcher)"
fi
echo "   🛠️ launch_facesearch_dev.sh (development launcher)"
echo ""
echo "🎯 To use your Ownize Face Search:"
echo "   🥇 Double-click: 🔍 Ownize Face Search.command (RECOMMENDED)"
echo "   🥈 Double-click: FaceSearch.command (simple)"
if [ -f "Ownize Face Search.app" ]; then
    echo "   🥉 Double-click: Ownize Face Search.app (cleanest - no terminal)"
fi
echo ""
echo "🎨 Ownize Logo Features:"
if [ -f "assets/ownize_logo.png" ]; then
    echo "   ✅ Custom Ownize icon in app bundles"
    echo "   ✅ Ownize branding in terminal launcher"
    echo "   ✅ Ownize logo in Dock when app runs"
    echo "   ✅ Professional Ownize appearance"
else
    echo "   ⚠️ No logo applied (assets/ownize_logo.png not found)"
    echo "   💡 Add logo and run script again to get branded version"
fi
echo ""
echo "🔍 Your Ownize Face Search app is ready!"
echo "📱 Click 'Search by Face' to start searching photos"
echo ""