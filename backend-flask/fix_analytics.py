# Read the file
with open("billing/analytics_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the condition
content = content.replace(
    'if "@placeholder.local" in email and users_collection:', "if users_collection:"
)

# Write back
with open("billing/analytics_service.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed! Removed placeholder check.")
