import streamlit as st
import bcrypt
import time
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()


# Sample User Data (In a real app, store this securely in a database)
users = {
os.getenv("APP_USERNAME"): bcrypt.hashpw(os.getenv("APP_PASSWORD").encode(), bcrypt.gensalt())
}

# Login Function
def login(username, password):
    if username in users:
        return bcrypt.checkpw(password.encode(), users[username])
    return False

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Check if Remember Me Cookie Exists
query_params = st.session_state.get('query_params', {})
if "remember_me" in query_params and query_params["remember_me"][0] == "true":
    st.session_state.authenticated = True


if not st.session_state.authenticated:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    remember_me = st.checkbox("Remember Me")

    if st.button("Login"):
        if login(username, password):
            st.session_state.authenticated = True
            st.success("Login successful!")
            if remember_me:
                st.session_state.query_params = {'remember_me': 'true'}
            else:
                st.session_state.query_params = {}
            time.sleep(1)
            st.rerun()
        else:
            st.error("Invalid username or password.")
else:
    st.title("Home Page")
    st.write("Welcome back!")
    st.write("### Available Apps:")
    st.write("- **Inventory App:** Sums up the items of the orders for the Atelier.")
    st.write("- **Rename Invoices:** Rename the invoices from invoiceexpress with the order ID.")
    st.write("- **Invoice Express:** Uses a CSV from Shopify and creates invoices.")


    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

