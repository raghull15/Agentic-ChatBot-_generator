from billing.database import get_db_session
from billing.models import User

with get_db_session() as db:
    user = (
        db.query(User).filter(User.mongo_user_id == "696a16b6df12cb59cd9bb66a").first()
    )
    if user:
        print(f"SQLite email: {user.email}")
    else:
        print("User not found in SQLite")
