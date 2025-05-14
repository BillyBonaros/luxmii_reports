import streamlit as st
import pandas as pd
import requests
import http.client
import json
import time
import os
from dotenv import load_dotenv
import traceback
import sys 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from functions import create_invoice

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Please login first.")
    st.stop()


# Load environment variables from .env file
load_dotenv()

# Configuration constants
API_KEY = os.getenv("INVOICEEXPRESS_KEY")
API_BASE_URL = "intervwovenunipes.app.invoicexpress.com"
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")  # Consider moving to .env

def get_exchange_rate():
    """Fetch the current AUD to EUR exchange rate."""
    try:
        response = requests.get(f'https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/AUD')
        response.raise_for_status()  # Raise exception for non-200 responses
        rate = response.json()['conversion_rates']['EUR']
        return rate
    except Exception as e:
        st.error(f"Failed to fetch exchange rate: {str(e)}")
        return None

def update_client(client_data):
    """Update client information in Invoice Express."""
    client_id = client_data['invoice']['client']['id']
    url = f"https://{API_BASE_URL}/clients/{client_id}.json"
    
    payload = {
        "client": {
            "name": client_data['invoice']['client']['name'],
            "code": client_data['invoice']['client']['code'],
            "address": client_data['invoice']['client']['address'],
            "city": client_data['invoice']['client']['city'],
            "postal_code": client_data['invoice']['client']['postal_code']
        }
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    params = {"api_key": API_KEY}
    
    response = requests.put(url, json=payload, headers=headers, params=params)
    response.raise_for_status()
    
    # Verify client was updated by fetching client data
    conn = http.client.HTTPSConnection(API_BASE_URL)
    headers = {'accept': "application/json"}
    conn.request("GET", f"/clients/{client_id}.json?api_key={API_KEY}", headers=headers)
    res = conn.getresponse()
    data = res.read()
    
    return data

def process_orders(orders):
    """Process each order to create invoice and update client."""
    results = {
        "successful": [],
        "failed_invoices": [],
        "failed_clients": []
    }
    
    total_orders = len(orders)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, order_id in enumerate(orders):
        status_text.text(f"Processing order {i+1}/{total_orders}: {order_id}")
        
        try:
            # Create invoice
            invoice_response = create_invoice(order_id)
            
            # Update client if invoice creation was successful
            try:
                client_data = json.loads(invoice_response)
                update_client(client_data)
                results["successful"].append(order_id)
            except Exception as e:
                st.write(f"Client update failed for order {order_id}: {str(e)}")
                results["failed_clients"].append(order_id)
                
        except Exception as e:
            st.write(f"Invoice creation failed for order {order_id}: {str(e)}")
            results["failed_invoices"].append(order_id)
        
        # Update progress bar
        progress_bar.progress((i + 1) / total_orders)
        
        # Add a small delay to prevent API rate limiting
        time.sleep(1)
    
    return results

def main():
    st.set_page_config(page_title="Shopify Invoice Express App", layout="wide")
    
    st.title("Shopify Invoice Express App")
    
    # Create tabs for different functionalities
    tab1, tab2 = st.tabs(["Process Orders", "Settings"])
    
    with tab1:
        st.header("Process Orders")
        
        # File uploader
        uploaded_file = st.file_uploader("Upload your Excel file with order IDs", type=["csv"])
        
        # Show a sample of the Excel format expected
        st.info("Excel file should contain a column named 'Id' with Shopify order IDs.")
        
        # Optional column selection
        id_column = "Id"  # Default column name
        
        if uploaded_file is not None:
            try:
                # Preview the Excel file
                df_preview = pd.read_csv(uploaded_file,dtype=str)
                st.write("Preview of uploaded file:")
                st.dataframe(df_preview.head())
                
                # Let user select which column contains order IDs
                # available_columns = df_preview.columns.tolist()
                # id_column = st.selectbox("Select column containing Order IDs:", available_columns, 
                #                          index=available_columns.index("Id") if "Id" in available_columns else 0)
            except Exception as e:
                st.error(f"Error previewing file: {str(e)}")
        
        # Process button with loading state
        if st.button("Process Orders"):
            if uploaded_file is not None:
                try:
                    with st.spinner("Reading file and preparing to process orders..."):
                        # Get exchange rate
                        exchange_rate = get_exchange_rate()
                        if exchange_rate:
                            st.info(f"Current AUD to EUR exchange rate: {exchange_rate}")
                        
                        # # Read Excel file and process orders
                        # df = pd.read_csv(uploaded_file)
                        
                        # if id_column not in df.columns:
                        #     st.error(f"Column 'Id' not found in the Excel file.")
                        #     return
                        
                        orders = list(df_preview['Id'].dropna().astype(str))
                        
                        if not orders:
                            st.warning("No order IDs found in the selected column.")
                            return
                        
                        st.info(f"Found {len(orders)} orders to process.")
                        
                        # Process orders
                        results = process_orders(orders)
                        
                        # Display results
                        st.success(f"Processing complete! Successfully processed {len(results['successful'])} orders.")
                        
                        if results["failed_invoices"]:
                            st.error(f"Failed to create invoices for {len(results['failed_invoices'])} orders.")
                            st.write("Failed invoice creation for order IDs:", results["failed_invoices"])
                        
                        if results["failed_clients"]:
                            st.warning(f"Failed to update clients for {len(results['failed_clients'])} orders.")
                            st.write("Failed client updates for order IDs:", results["failed_clients"])
                        
                        # Export results to CSV
                        results_df = pd.DataFrame({
                            "Order ID": orders,
                            "Status": ["Success" if order_id in results["successful"] 
                                      else "Failed Invoice" if order_id in results["failed_invoices"]
                                      else "Failed Client Update" if order_id in results["failed_clients"]
                                      else "Unknown" for order_id in orders]
                        })
                        
                        csv = results_df.to_csv(index=False)
                        st.download_button(
                            label="Download Results as CSV",
                            data=csv,
                            file_name="invoice_processing_results.csv",
                            mime="text/csv",
                        )
                
                except Exception as e:
                    st.error("An error occurred during processing:")
                    st.error(str(e))
                    st.error(traceback.format_exc())
            else:
                st.warning("Please upload an Excel file first.")
    
    with tab2:
        st.header("Settings")
        st.write("This section allows you to configure app settings.")
        
        st.subheader("API Configuration")
        st.info("For security, API keys should be stored in a .env file in the same directory as this app.")
        
        # Display current API configuration (without showing actual keys)
        if API_KEY:
            st.success("✅ Invoice Express API key is configured")
        else:
            st.error("❌ Invoice Express API key is missing. Add INVOICE_EXPRESS_API_KEY to your .env file.")
        
        if EXCHANGE_RATE_API_KEY:
            st.success("✅ Exchange Rate API key is configured")
        else:
            st.warning("⚠️ Exchange Rate API key is using default value. Add EXCHANGE_RATE_API_KEY to your .env file for better security.")
        
        # Test API connectivity
        if st.button("Test API Connectivity"):
            with st.spinner("Testing API connections..."):
                # Test Exchange Rate API
                try:
                    exchange_response = requests.get(f'https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/AUD')
                    if exchange_response.status_code == 200:
                        st.success("✅ Exchange Rate API connection successful")
                    else:
                        st.error(f"❌ Exchange Rate API error: {exchange_response.status_code} - {exchange_response.text}")
                except Exception as e:
                    st.error(f"❌ Exchange Rate API connection failed: {str(e)}")
                
                # Test Invoice Express API - just a simple endpoint check
                try:
                    conn = http.client.HTTPSConnection(API_BASE_URL)
                    conn.request("GET", f"/sequences.json?api_key={API_KEY}")
                    response = conn.getresponse()
                    if response.status == 200:
                        st.success("✅ Invoice Express API connection successful")
                    else:
                        st.error(f"❌ Invoice Express API error: {response.status} - {response.reason}")
                except Exception as e:
                    st.error(f"❌ Invoice Express API connection failed: {str(e)}")

if __name__ == "__main__":
    main()