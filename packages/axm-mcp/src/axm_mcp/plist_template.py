"""Launchd plist template for the AXM MCP server."""

from __future__ import annotations

__all__ = ["PLIST_TEMPLATE"]

PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>io.axm.mcp-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>{bin_path}</string>
        <string>serve</string>
        <string>--port</string>
        <string>{port}</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/stderr.log</string>
</dict>
</plist>
"""
