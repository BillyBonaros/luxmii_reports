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

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Please login first.")
    st.stop()


# Load environment variables from .env file
load_dotenv()


def process_orders(orders, account):
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
            if account =="Test":
                invoice_response = requests.get(f"https://luxmii-jasmin.onrender.com/?orderid={order_id}&extra_disc=70")
            elif account=='Production':
                invoice_response = requests.get(f"https://luxmii-jasmin.onrender.com/production?orderid={order_id}&extra_disc=70") 
            
            st.write(invoice_response.text)

        except Exception as e:
            st.write(f"Invoice creation failed for order {order_id}: {str(e)}")
            results["failed_invoices"].append(order_id)
        
        # Update progress bar
        progress_bar.progress((i + 1) / total_orders)
        
        # Add a small delay to prevent API rate limiting
        time.sleep(2)
    
    return results

def main():
    st.set_page_config(page_title="Shopify Invoice Express App", layout="wide")
    
    st.title("Shopify Invoice Express App")
    
    # Create tabs for different functionalities
    
    st.header("Process Orders")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload your Excel file with order IDs", type=["csv"])

    
    account=st.radio('Account', ['Test','Production'])
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
                    results = process_orders(orders,account)
                    
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


if __name__ == "__main__":
    main()