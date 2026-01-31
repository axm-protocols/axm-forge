# quickstart.tape
# Generate with: vhs docs/tutorials/tapes/quickstart.tape

Output docs/assets/quickstart.gif

Set FontSize 16
Set Width 1200
Set Height 600
Set Theme "Dracula"
Set TypingSpeed 50ms

# Title
Type "# AXM Quickstart Demo"
Enter
Sleep 500ms

# Check version
Type "axm version"
Enter
Sleep 1s

# Initialize project
Type "axm init demo-project"
Enter
Sleep 4s

# Navigate and audit
Type "cd demo-project/demo-project"
Enter
Sleep 500ms

Type "axm audit"
Enter
Sleep 3s

# Show success
Type "# ✅ Grade A achieved!"
Enter
Sleep 2s
