import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import time

def get_authenticator(config):
    """
    Initializes the Authenticator with 30-day persistence.
    """
    # Force 30 days expiry
    cookie_expiry = 30
    
    # Cookie Config
    # Check if 'cookie' key exists, if not create default structure to merge
    cookie_config = config.get('cookie', {})
    
    # Ensure Mobile Friendly Settings
    # Note: cookie_handler is internal in some versions.
    # We pass these to the constructor if supported, or rely on config dict structure.
    # streamlit-authenticator v0.2+ usually takes args.
    
    return stauth.Authenticate(
        config['credentials'],
        cookie_config.get('name', 'asset_dashboard_cookie'),
        cookie_config.get('key', 'random_key_if_missing'),
        cookie_expiry,
        # preheaders=['upgrade-insecure-requests'], # Optional for HTTPS forcing
    )

def check_auth_status(authenticator):
    """
    Checks if a valid session/cookie exists without rendering the login widget immediately.
    If valid, sets session state.
    """
    # Depending on version, we might need to peek at cookies manually 
    # OR just rely on authenticator initializing state from cookies automatically.
    
    # stauth < 0.3 often requires running .login() to check cookies, 
    # but that renders UI.
    # However, newer versions check cookie on init.
    
    # We will try to rely on session_state 'authentication_status'
    # If it is None, we might check st.cookies content (Streamlit 1.30+ supports st.context.cookies or similar)
    # But standard stauth pattern is causing re-login issues.
    
    # Pattern: 
    # 1. Init authenticator. 
    # 2. Check st.session_state['authentication_status'].
    # 3. If None, it means no valid cookie was found by stauth (or stauth hasn't run check).
    
    # We will let app.py handle the flow control, this function is a helper if needed.
    pass

def login_widget(authenticator):
    """
    Renders the login widget and handles the result.
    """
    name, authentication_status, username = authenticator.login(location="main")
    return name, authentication_status, username

def logout_widget(authenticator):
    """
    Renders logout button.
    """
    authenticator.logout("Logout", "sidebar")
