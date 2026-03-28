import os

# --- SHARED DATABASE SETUP ---
SHARED_BASE_PATH = "/storage/emulated/0/Download/teligrambot/"
SHARED_VERIFIED_USERS_FILE = os.path.join(SHARED_BASE_PATH, "shared_bot_crosscheck_users.txt")

# Agar shared file nahi hai toh automatic bana dega
if not os.path.exists(SHARED_VERIFIED_USERS_FILE):
    if not os.path.exists(SHARED_BASE_PATH):
        try: os.makedirs(SHARED_BASE_PATH)
        except: pass
    with open(SHARED_VERIFIED_USERS_FILE, "w") as f:
        pass

def is_user_in_shared_db(user_id):
    """
    Check karna ki kya user ID shared file database me maujood hai?
    """
    user_id_str = str(user_id)
    try:
        with open(SHARED_VERIFIED_USERS_FILE, "r") as f:
            users = f.read().splitlines()
        return user_id_str in users
    except Exception:
        return False

def add_user_to_shared_db(user_id):
    """
    Shared file database me user ID add karna
    """
    if not is_user_in_shared_db(user_id):
        try:
            with open(SHARED_VERIFIED_USERS_FILE, "a") as f:
                f.write(f"{user_id}\n")
        except Exception as e:
            print(f"Database write error: {e}")
