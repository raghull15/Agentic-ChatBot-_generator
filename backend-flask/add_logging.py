# Read the file
with open("billing/analytics_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add logging after get_users_collection
content = content.replace(
    "users_collection = get_users_collection()",
    'users_collection = get_users_collection()\n            logger.info(f"DEBUG: users_collection = {users_collection}")',
)

# Add logging in the loop
content = content.replace(
    "if users_collection:",
    'logger.info(f"DEBUG: Checking users_collection, is None: {users_collection is None}")\n                if users_collection:',
)

# Write back
with open("billing/analytics_service.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Added debug logging!")
