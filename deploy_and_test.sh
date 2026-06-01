#!/usr/bin/env bash
set -e

EXT_ID="org.libreoffice.extensions.autosave"

echo -e "\033[0;36m1. Building the extension...\033[0m"
python3 build_oxt.py

echo -e "\033[0;36m2. Killing open LibreOffice instances...\033[0m"
# Ignore kill errors if LibreOffice isn't running
pkill -f soffice || true
pkill -f libreoffice || true
sleep 2

# Detect OS and set paths appropriately
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac OSX
    UNOPKG="/Applications/LibreOffice.app/Contents/MacOS/unopkg"
    SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
else
    # Linux (usually in PATH, but fallback to typical installation locations)
    UNOPKG=$(command -v unopkg || echo "/usr/lib/libreoffice/program/unopkg")
    SOFFICE=$(command -v libreoffice || command -v soffice || echo "/usr/bin/soffice")
fi

echo -e "\033[0;36m3. Uninstalling existing extension...\033[0m"
# We ignore the exit code here in case the extension isn't currently installed
"$UNOPKG" remove "$EXT_ID" 2>/dev/null || true

echo -e "\033[0;36m4. Installing the new extension...\033[0m"
"$UNOPKG" add -f dist/AutoSave.oxt

echo -e "\033[0;36m5. Starting LibreOffice Writer...\033[0m"
# Launch Writer as a detached background process
"$SOFFICE" --writer >/dev/null 2>&1 &

echo -e "\033[0;32mDeployment complete! Writer is launching in the background.\033[0m"
