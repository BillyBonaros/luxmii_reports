import streamlit as st
import pandas as pd
import os
import requests
import time
from requests.exceptions import RequestException
import requests
import datetime
import time
from requests.exceptions import RequestException
import os
from dotenv import load_dotenv
import pandas as pd
import datetime
from datetime import timezone
import sys

load_dotenv()
API_KEY = os.getenv("shopify_key")
# Disable SSL warnings (optional, not for production)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Your provided functions (keeping them as they are)
def get_shopify_data(order_id, max_retries=3):
    url = f"https://luxmii.com/admin/api/2024-10/orders/{order_id}.json"
    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': API_KEY
    }
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.request("GET", url, headers=headers, data=payload, verify=False)
            response.raise_for_status()
            data = response.json()
            return data['order']
        except RequestException as e:
            retries += 1
            if retries > max_retries:
                raise Exception(f"Failed to fetch data after {max_retries} retries: {str(e)}")
            wait_time = 2 ** retries
            time.sleep(wait_time)

def get_item_status(order_id, max_retries=3):
    url = f"https://luxmii.com/admin/api/2024-04/orders/{order_id}/fulfillment_orders.json"
    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': API_KEY
    }
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.request("GET", url, headers=headers, data=payload, verify=False)
            f = pd.DataFrame((response.json()['fulfillment_orders']))
            statuses = f.apply(lambda x: {i['line_item_id']: x['status'] for i in x['line_items']}, axis=1)
            merged_dict = {}
            for d in statuses:
                merged_dict.update(d)
            return merged_dict
        except RequestException as e:
            retries += 1
            if retries > max_retries:
                raise Exception(f"Failed to fetch data after {max_retries} retries: {str(e)}")
            wait_time = 2 ** retries
            time.sleep(wait_time)

def search_orders_by_email_or_name(query, field='email', max_retries=3):
    assert field in ['email', 'name']
    url = f"https://luxmii.com/admin/api/2024-10/orders.json?status=any&{field}={query}"
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': API_KEY
    }
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            return response.json().get("orders", [])
        except RequestException as e:
            retries += 1
            if retries > max_retries:
                raise Exception(f"Failed to search orders: {str(e)}")
            time.sleep(2 ** retries)

def get_eligibility_options(is_final_sale, days_held_count, has_discount):
    """Return eligibility options based on item conditions"""
    if is_final_sale:
        return "FINAL SALE", "❌", "Cannot be returned"
    
    if days_held_count is not None and days_held_count > 30:
        return "EXPIRED", "⛔", "Return period expired (must be within 30 days)"
    
    if has_discount:
        return "ELIGIBLE", "✅", [
            "Store credit (-$20 USD label)",
            "Item exchange (-$20 USD label)", 
            "Alteration subsidy: 10% refund + $20 USD gift voucher"
        ]
    else:
        return "ELIGIBLE", "✅", [
            "120% store credit + **free** returns",
            "Item exchange (-$20 USD label)",
            "Refund (-$30 USD label)",
            "Alteration subsidy: 10% refund + $20 USD gift voucher"
        ]

# Streamlit UI with improved styling
st.set_page_config(page_title="Returns Portal", page_icon="📦", layout="wide")

st.title("📦 Returns Portal")
st.markdown("---")

# Search section with improved layout
col1, col2 = st.columns([1, 2])
with col1:
    search_method = st.selectbox("🔍 Search by", ["Order ID", "Email", "Order Name"])
with col2:
    query_input = st.text_input(f"Enter {search_method}", placeholder=f"Type your {search_method.lower()} here...")

selected_order_id = None

if query_input:
    if search_method == "Order ID":
        selected_order_id = query_input
    else:
        field = 'email' if search_method == 'Email' else 'name'
        try:
            with st.spinner("Searching orders..."):
                orders = search_orders_by_email_or_name(query_input, field=field)
            if not orders:
                st.warning("🔍 No matching orders found.")
            else:
                order_options = {
                    f"{o['name']} ({o['email']}) - {o['created_at'][:10]}": o['id']
                    for o in orders
                }
                selected_label = st.selectbox("📋 Select an order", list(order_options.keys()))
                selected_order_id = order_options[selected_label]
        except Exception as e:
            st.error(f"❌ Search error: {str(e)}")

# Load order details if an order was selected
if selected_order_id:
    try:
        with st.spinner("Loading order details..."):
            order_data = get_shopify_data(selected_order_id)
            status_map = get_item_status(selected_order_id)

        line_items = order_data.get("line_items", [])
        fulfillments = order_data.get("fulfillments", [])
        discounts = order_data.get("discount_codes", [])
        discount_codes = ", ".join([d['code'] for d in discounts]) if discounts else "None"
        # Order header with better styling
        st.success(f"✅ **Order #{order_data['name']}** — {order_data['email']}")
        st.write(f"**Name:** {order_data['billing_address']['name']}")
        st.write(f"**Country:** {order_data['billing_address']['country']}")
        st.write(f"**Total Price (after discounts):** {order_data['total_price_set']['presentment_money']['amount']} {order_data['total_price_set']['presentment_money']['currency_code']}")
        st.write(f"**Tags:** {order_data['tags']}")
        st.markdown("---")

        # Process items
        item_rows = []
        for item in line_items:
            line_id = item['id']
            item_status = status_map.get(line_id, "Unknown")
            sent_date, delivered_date = None, None
            discount_ammount=(sum(float(i['amount_set']['presentment_money']['amount']) for i in item.get("discount_allocations", [])) if item.get("discount_allocations") else 0)

            properties = [i['value'] for i in item['properties']]
            is_final_sale = 'Final Sale' in properties
            
            for fulfillment in fulfillments:
                for f_item in fulfillment.get("line_items", []):
                    if f_item["id"] == line_id:
                        sent_date = fulfillment.get("created_at")
                        if fulfillment.get("shipment_status") == "delivered":
                            delivered_date = fulfillment.get("updated_at")

            item_rows.append({
                "item": item,
                "status": item_status,
                "is_final_sale": is_final_sale,
                "sent_date": sent_date,
                "delivered_date": delivered_date,
                "discount_codes": discount_codes,
                "discount_ammount": discount_ammount
            })

        # Display items in a more organized way
        for i, row in enumerate(item_rows):
            # Calculate dates and eligibility
            sent_at_fmt = (
                datetime.datetime.fromisoformat(row["sent_date"]).strftime("%B %d, %Y")
                if row["sent_date"] else "Not sent yet"
            )

            delivered_at_fmt = "Not delivered yet"
            days_held_count = None
            if row["delivered_date"]:
                delivered_dt = datetime.datetime.fromisoformat(row["delivered_date"])
                delivered_at_fmt = delivered_dt.strftime("%B %d, %Y")
                now = datetime.datetime.now(tz=timezone.utc).astimezone(delivered_dt.tzinfo)
                days_held_count = (now - delivered_dt).days

            has_discount = row["discount_codes"] != "None"
            eligibility_status, status_icon, eligibility_options = get_eligibility_options(
                row["is_final_sale"], days_held_count, has_discount
            )

            # Create expandable item card
            with st.expander(f"📦 {row['item']['name']} — {status_icon} {eligibility_status}", expanded=True):
                # Create three columns for better layout
                col1, col2, col3 = st.columns([2, 2, 3])
                
                with col1:
                    st.markdown("**📋 Item Details**")
                    st.write(f"**Quantity:** {row['item']['quantity']}")
                    st.write(f"**Price:** {row['item']['price_set']['presentment_money']['amount']} - {row['discount_ammount']} {row['item']['price_set']['presentment_money']['currency_code']}")
                    st.write(f"**Final Price:** {float(row['item']['price_set']['presentment_money']['amount'])-float(row['discount_ammount'])} {row['item']['price_set']['presentment_money']['currency_code']}")
                    st.write(f"**Status:** `{row['status']}`")
                    st.write(f"**Final Sale:** {'✅ Yes' if row['is_final_sale'] else '❌ No'}")
                    if row["discount_codes"] != "None":
                        st.write(f"**Discount Code:** {row['discount_codes']}")

                with col2:
                    st.markdown("**📅 Shipping Info**")
                    st.write(f"**Sent:** {sent_at_fmt}")
                    st.write(f"**Delivered:** {delivered_at_fmt}")
                    if days_held_count is not None:
                        st.write(f"**Days Held:** {days_held_count} day(s)")
                    else:
                        st.write("**Days Held:** N/A")

                with col3:
                    st.markdown("**🔄 Return Eligibility**")
                    
                    if eligibility_status == "FINAL SALE":
                        st.error("❌ FINAL SALE — Cannot be returned")
                    elif eligibility_status == "EXPIRED":
                        st.error("⛔ Return period expired (must be within 30 days of delivery)")
                    else:
                        st.success("✅ Eligible for return")
                        st.markdown("**Available options:**")
                        for j, option in enumerate(eligibility_options, 1):
                            st.write(f"{j}. {option}")

            # Add some spacing between items
            if i < len(item_rows) - 1:
                st.markdown("<br>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Error loading order details: {str(e)}")

# Add footer
st.markdown("---")
st.markdown("*Returns Portal v2.0*")
