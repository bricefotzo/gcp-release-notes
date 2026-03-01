"""Authentication: login, signup, session management."""

from datetime import datetime, timezone

import bcrypt
import streamlit as st
from pymongo.database import Database


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def register_user(
    db: Database, email: str, display_name: str, password: str
) -> dict | None:
    """Register a new user. Returns user doc or None if email already exists."""
    if db.users.find_one({"email": email}):
        return None
    user = {
        "email": email,
        "display_name": display_name,
        "password_hash": hash_password(password),
        "preferences": {
            "products": [],
            "types": [],
        },
        "created_at": datetime.now(timezone.utc),
        "last_login": datetime.now(timezone.utc),
    }
    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return user


def authenticate_user(db: Database, email: str, password: str) -> dict | None:
    """Authenticate a user by email and password. Returns user doc or None."""
    user = db.users.find_one({"email": email})
    if not user or not verify_password(password, user["password_hash"]):
        return None
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )
    return user


def get_current_user() -> dict | None:
    """Get current user from session state."""
    return st.session_state.get("user")


def logout():
    """Clear user session."""
    for key in ("user", "user_id"):
        st.session_state.pop(key, None)


def _set_session_user(user: dict):
    """Store user info in session state."""
    st.session_state["user"] = {
        "id": str(user["_id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "preferences": user.get("preferences", {"products": [], "types": []}),
    }


def show_auth_ui(db: Database) -> dict | None:
    """Display login/register UI in sidebar. Returns user dict if authenticated."""
    if "user" in st.session_state:
        user = st.session_state["user"]
        st.markdown(f"**{user['display_name']}**")
        st.caption(user["email"])
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()
        return user

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.form_submit_button("Login", use_container_width=True):
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    user = authenticate_user(db, email, password)
                    if user:
                        _set_session_user(user)
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form"):
            new_email = st.text_input("Email", key="reg_email")
            new_name = st.text_input("Display name", key="reg_name")
            new_pass = st.text_input("Password", type="password", key="reg_pass")
            confirm_pass = st.text_input(
                "Confirm password", type="password", key="reg_pass2"
            )
            if st.form_submit_button("Create account", use_container_width=True):
                if not new_email or not new_name or not new_pass:
                    st.error("Please fill in all fields.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                elif len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    user = register_user(db, new_email, new_name, new_pass)
                    if user:
                        _set_session_user(user)
                        st.success("Account created!")
                        st.rerun()
                    else:
                        st.error("An account with this email already exists.")

    return None
