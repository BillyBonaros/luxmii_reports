import streamlit as st
import requests
import json

with open("./guidelines.txt", "r", encoding="utf-8") as file:
    SYSTEM_MESSAGE = file.read()  # Reads the entire file as a string

# Set page config
st.set_page_config(
    page_title="Email Reply Assistant",
    page_icon="📧",
    layout="wide"
)

# Initialize session state for system message
if 'system_message' not in st.session_state:
    st.session_state.system_message = """You are a helpful customer service assistant. 
Please respond to customer emails in a professional and friendly manner. 
Always be polite, helpful, and provide accurate information."""

def save_system_message(message):
    """Save system message to session state"""
    st.session_state.system_message = message
    st.success("System message saved successfully!")

def call_api(email, subject, body, system_message):
    """Call the email processing API"""
    url = "https://shopify-order-assistant.onrender.com/process-email"
    
    payload = {
        "email": email,
        "subject": subject,
        "body": body,
        "system_message": system_message
    }
    
    try:
        with st.spinner("Generating reply..."):
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['email_response']
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None
    except json.JSONDecodeError:
        st.error("Invalid response format from API")
        return None

# Main app
st.title("📧 Email Reply Assistant")
st.markdown("Generate AI-powered replies to customer emails using your Shopify Order Assistant API")

# Create tabs
tab1, tab2 = st.tabs(["📝 Email Reply", "⚙️ System Settings"])

with tab1:
    st.header("Generate Email Reply")
    
    # Create two columns for better layout
    col1, col2 = st.columns([1, 1])
    
    st.subheader("Email Details")
    
    # Email input fields
    email = st.text_input(
        "Customer Email",
        placeholder="customer@example.com",
        help="Enter the customer's email address"
    )
    
    subject = st.text_input(
        "Email Subject",
        placeholder="Order inquiry",
        help="Enter the subject line of the email"
    )
    
    body = st.text_area(
        "Email Body",
        placeholder="Enter the customer's message here...",
        height=200,
        help="Paste the customer's email content"
    )
    

    
    if st.button("🚀 Generate Reply", type="primary", use_container_width=True):
        if not email or not subject or not body:
            st.error("Please fill in all required fields (Email, Subject, and Body)")
        else:
            # Call the API
            result = call_api(email, subject, body, st.session_state.system_message)
            
            if result:
                st.success("Reply generated successfully!")
                
                # Display the response
                st.subheader("Generated Reply")
                
                # Create a nice container for the reply
                with st.container():
                    st.markdown("**Reply:**")
                    st.text_area(
                        "Generated Response",
                        value=result,
                        height=200,
                        label_visibility="collapsed"
                    )
                    
                    # Copy to clipboard button (using st.code for easy copying)
                    st.markdown("**Copy-ready format:**")
                    st.code(result, language=None)
                


with tab2:
    st.header("System Message Configuration")
    st.markdown("Configure the AI assistant's behavior and personality")
    
    # System message editor
    new_system_message = st.text_area(
        "System Message",
        value=st.session_state.system_message,
        height=300,
        help="This message defines how the AI assistant should behave when responding to emails"
    )
    
    # Save button
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("💾 Save System Message", type="primary", use_container_width=True):
            save_system_message(new_system_message)
    
    # Reset to default button
    with col3:
        if st.button("🔄 Reset to Default", use_container_width=True):
            default_message = SYSTEM_MESSAGE
            save_system_message(default_message)
    