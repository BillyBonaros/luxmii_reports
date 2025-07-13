import streamlit as st
import pandas as pd
import os
import requests
import time
from requests.exceptions import RequestException
import datetime
from datetime import timezone
import sys
from dotenv import load_dotenv
import urllib3

# Disable SSL warnings and load environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()
API_KEY = os.getenv("shopify_key")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [Keep all your existing API functions unchanged]
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

def get_eligibility_options(is_final_sale, days_held_count, has_discount, discount_percentage, order_count):
    """Return eligibility options based on item conditions"""
    if is_final_sale:
        return "FINAL SALE", "❌", "Cannot be returned"
    
    if days_held_count is not None and days_held_count > 30:
        return "EXPIRED", "⛔", "Return period expired (must be within 30 days)"
    
    if discount_percentage >= 30:
        return "More than 30% off", "❌", "Cannot be returned"

    if order_count == 1:
        return "ELIGIBLE", "✅", [
            "120% store credit + **free** returns",
            "Item exchange (-$20 USD label)",
            "Refund (-$30 USD label)",
            "Alteration subsidy: 10% refund + $20 USD gift voucher"
        ]
    else:
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

def get_sale_items():
    url = "https://luxmii.com/admin/api/2024-04/products.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": os.environ.get("shopify_key")
    }

    sale_items = []
    limit = 250
    page_info = None

    while True:
        params = {"limit": limit}
        if page_info:
            params["page_info"] = page_info

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print("Error:", response.status_code, response.text)
            break

        products = response.json().get("products", [])

        for product in products:
            for variant in product["variants"]:
                price = float(variant["price"])
                compare_price = float(variant["compare_at_price"] or 0)

                if compare_price > price:
                    sale_items.append({
                        "product_title": product["title"],
                        "sku": variant["sku"],
                        "variant_title": variant["title"],
                        "price": price,
                        "compare_at_price": compare_price,
                        "product_id": product["id"],
                        "variant_id": variant["id"],
                        "product_url": f"https://luxmii.com/products/{product['handle']}"
                    })

        # Handle pagination
        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            import re
            match = re.search(r'<([^>]+)>; rel="next"', link_header)
            if match:
                next_url = match.group(1)
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(next_url)
                page_info = parse_qs(parsed.query)['page_info'][0]
            else:
                break
        else:
            break

    return sale_items

def generate_customer_response(order_data, selected_items):
    """Generate a professional customer response email using order data with optimized format"""
    
    if not selected_items:
        return "No items selected for return processing."
    
    # Extract customer details from order data
    customer_name = order_data['billing_address']['name']
    order_name = order_data['name']
    customer_email = order_data['email']
    
    # Get customer order count to determine if first-time customer
    url = f"https://luxmii.com/admin/api/2024-04/customers/{order_data['customer']['id']}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": os.environ.get('shopify_key')
    }
    response = requests.get(url, headers=headers)
    order_count = response.json()['customer']['orders_count']
    
    # Get discount information
    discounts = order_data.get("discount_codes", [])
    discount_code = discounts[0]['code'] if discounts else None
    
    # Count eligible vs non-eligible items
    eligible_items = [item for item in selected_items if item['eligibility_status'] == 'ELIGIBLE']
    non_eligible_items = [item for item in selected_items if item['eligibility_status'] != 'ELIGIBLE']
    
    # Start building the response
    response_text = f"""Dear {customer_name},

Thank you for sharing your feedback!

"""
    
    # Handle non-eligible items first
    if non_eligible_items:
        for item in non_eligible_items:
            if item['eligibility_status'] == 'FINAL SALE':
                response_text += f"Regarding your {item['name']}, this item was marked as Final Sale at the time of purchase and unfortunately cannot be returned or exchanged. We appreciate your understanding with our Final Sale policy.\n\n"
            elif item['eligibility_status'] == 'EXPIRED':
                response_text += f"Regarding your {item['name']}, the return period has expired as returns must be initiated within 30 days of delivery. We appreciate your understanding with our return timeframe policy.\n\n"
            elif item['eligibility_status'] == 'More than 30% off':
                response_text += f"Regarding your {item['name']}, this item had a discount of 30% or more and falls under our promotional return policy where returns are not available. We appreciate your understanding.\n\n"
    
    # Handle eligible items
    if eligible_items:
        # Create item list for the response
        item_names = []
        for item in eligible_items:
            if item['quantity'] > 1:
                item_names.append(f"{item['name']} (x{item['quantity']})")
            else:
                item_names.append(item['name'])
        
        if len(item_names) == 1:
            items_text = item_names[0]
        elif len(item_names) == 2:
            items_text = f"{item_names[0]} and {item_names[1]}"
        else:
            items_text = ", ".join(item_names[:-1]) + f", and {item_names[-1]}"
        
        response_text += f"We're sorry to hear our {items_text} didn't meet your expectations. You're always welcome to try a different size if you'd like, as we hope that will offer a better fit for you. If you're comfortable sharing your body measurements (bust, waist and hips), we'll be able to suggest the best size for you.\n\n"
        
        # Check if first-time customer
        if order_count == 1:
            response_text += f"If you'd like to return the item{'s' if len(eligible_items) > 1 else ''}, then please know that we're here to help. As a valued new customer, we want to ensure you have a great experience with us. We have several flexible return options available:\n\n"
            
            response_text += "Once you've confirmed how you'd like to proceed, we'll create a return shipping label for you and guide you through the next steps.\n\n"
            
            response_text += "1. 120% Lifetime Digital Store Credit Voucher:\n"
            response_text += "   Enjoy a bonus 20% credit plus free return shipping.\n\n"
            
            response_text += "2. Exchange for a Different Size or Item:\n"
            response_text += "   Utilise a subsidised returns label for $20 USD, and we'll cover the outbound shipping for your exchange.\n\n"
            
            response_text += "3. Full Refund:\n"
            response_text += "   Utilise a subsidised returns label for $30 USD for a complete refund to your original payment method.\n\n"
            
            response_text += "4. 10% Alteration Subsidy + $20 USD Gift Voucher:\n"
            response_text += "   Love the style but need a tweak? Keep the item and enjoy a 10% discount for local alterations plus a $20 USD gift voucher as a token of our appreciation.\n\n"
        
        else:
            # Returning customer logic
            if discount_code:
                response_text += f"If you'd like to return the item{'s' if len(eligible_items) > 1 else ''}, then please know that we're here to help. As your order was placed using the {discount_code} discount code, it falls under our promotional return policy. While we're unable to offer a refund, we do have a few flexible return options available that hopefully will work for you.\n\n"
                
                response_text += "Once you've confirmed how you'd like to proceed, we'll create a return shipping label for you and guide you through the next steps.\n\n"
                
                response_text += "1. Lifetime Digital Store Credit Voucher:\n"
                response_text += "   Utilise a subsidised returns label for $20 USD.\n\n"
                
                response_text += "2. Exchange for a Different Size or Item:\n"
                response_text += "   Utilise a subsidised returns label for $20 USD, and we'll cover the outbound shipping for your exchange.\n\n"
                
                response_text += "3. 10% Alteration Subsidy + $20 USD Gift Voucher:\n"
                response_text += "   Love the style but need a tweak? Keep the item and enjoy a 10% discount for local alterations plus a $20 USD gift voucher as a token of our appreciation.\n\n"
            
            else:
                # Returning customer without discount
                response_text += f"If you'd like to return the item{'s' if len(eligible_items) > 1 else ''}, then please know that we're here to help. We have several flexible return options available:\n\n"
                
                response_text += "Once you've confirmed how you'd like to proceed, we'll create a return shipping label for you and guide you through the next steps.\n\n"
                
                response_text += "1. 120% Lifetime Digital Store Credit Voucher:\n"
                response_text += "   Enjoy a bonus 20% credit plus free return shipping.\n\n"
                
                response_text += "2. Exchange for a Different Size or Item:\n"
                response_text += "   Utilise a subsidised returns label for $20 USD, and we'll cover the outbound shipping for your exchange.\n\n"
                
                response_text += "3. Full Refund:\n"
                response_text += "   Utilise a subsidised returns label for $30 USD for a complete refund to your original payment method.\n\n"
                
                response_text += "4. 10% Alteration Subsidy + $20 USD Gift Voucher:\n"
                response_text += "   Love the style but need a tweak? Keep the item and enjoy a 10% discount for local alterations plus a $20 USD gift voucher as a token of our appreciation.\n\n"
        
        response_text += "To start the return process, please reply to this email with your preferred option.\n\n"
    
    # Add closing
    response_text += "Please feel free to reach out if there's anything you need—we're here to assist!\n\n"
    response_text += "Best regards,\n"
    response_text += "Customer Service Team\n"
    response_text += "Luxmii"
    
    return response_text

# Initialize session state
if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []
if 'current_order_data' not in st.session_state:
    st.session_state.current_order_data = None
if 'item_rows' not in st.session_state:
    st.session_state.item_rows = []
if 'order_count' not in st.session_state:
    st.session_state.order_count = 0

# Load sale items data
@st.cache_data
def load_sales_data():
    try:
        sale_items = get_sale_items()
        sales = pd.DataFrame(sale_items)
        sales['percentage'] = round((1 - sales['price'] / sales['compare_at_price']) * 100)
        return sales.set_index('sku')[['percentage']].to_dict()
    except:
        return {'percentage': {}}

sales = load_sales_data()

# # Enhanced UI Configuration
# st.set_page_config(
#     page_title="Returns Portal Pro", 
#     page_icon="📦", 
#     layout="wide"
# )

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .item-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: #f9f9f9;
    }
    .eligible-item {
        border-left: 4px solid #4CAF50;
    }
    .non-eligible-item {
        border-left: 4px solid #f44336;
    }
    .response-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📦 Returns Portal Pro</h1>
    <p>Advanced Return Management System</p>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2 = st.tabs(["🔍 Order Search & Review", "📝 Response Generator"])

with tab1:
    # Search section - IMPROVED WITHOUT SEARCH BUTTON
    st.subheader("🔍 Order Search")

    col1, col2 = st.columns([1, 3])  # Adjusted column ratios for better layout
    with col1:
        search_method = st.selectbox("Search by", ["Order ID", "Email", "Order Name"])
    with col2:
        query_input = st.text_input(
            f"Enter {search_method}", 
            placeholder=f"Type your {search_method.lower()} here and press Enter...",
            key="search_input",
            help="Press Enter to search"  # Added helpful hint
        )

    selected_order_id = None

    # REMOVED search_button condition - now only triggers on query_input
    if query_input:
        if search_method == "Order ID":
            selected_order_id = query_input
        else:
            field = 'email' if search_method == 'Email' else 'name'
            try:
                with st.spinner("🔍 Searching orders..."):
                    orders = search_orders_by_email_or_name(query_input, field=field)
                if not orders:
                    st.warning("🔍 No matching orders found.")
                else:
                    st.success(f"Found {len(orders)} matching orders")
                    order_options = {
                        f"{o['name']} ({o['email']}) - {o['created_at'][:10]}": o['id']
                        for o in orders
                    }
                    selected_label = st.selectbox("📋 Select an order", list(order_options.keys()))
                    selected_order_id = order_options[selected_label]
            except Exception as e:
                st.error(f"❌ Search error: {str(e)}")


    # Load and display order details
    if selected_order_id:
        try:
            with st.spinner("📦 Loading order details..."):
                order_data = get_shopify_data(selected_order_id)
                status_map = get_item_status(selected_order_id)
                
                # Store order data in session state
                st.session_state.current_order_data = order_data

            # Get customer data
            url = f"https://luxmii.com/admin/api/2024-04/customers/{order_data['customer']['id']}.json"
            headers = {
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": os.environ.get('shopify_key')
            }
            response = requests.get(url, headers=headers)
            order_count = response.json()['customer']['orders_count']
            st.session_state.order_count = order_count

            line_items = order_data.get("line_items", [])
            fulfillments = order_data.get("fulfillments", [])
            discounts = order_data.get("discount_codes", [])
            discount_codes = ", ".join([d['code'] for d in discounts]) if discounts else "None"

            # Enhanced order header
            st.markdown("---")
            st.subheader("📋 Order Details")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.success(f"✅ **Order #{order_data['name']}** — {order_data['email']}")
                customer_status = "🟢 First-time Customer" if order_count == 1 else f"🔵 Returning Customer - {order_count} orders"
                st.write(f"**Customer:** {order_data['billing_address']['name']} - {customer_status}")
                st.write(f"**Country:** {order_data['billing_address']['country']}")
                st.write(f"**Total:** {order_data['total_price_set']['presentment_money']['amount']} {order_data['total_price_set']['presentment_money']['currency_code']}")
                if order_data['tags']:
                    st.write(f"**Tags:** {order_data['tags']}")
            
            with col2:
                st.metric("Order Count", order_count)
                st.metric("Items", len(line_items))

            # Process items for display
            st.markdown("---")
            st.subheader("📦 Items Review")
            
            item_rows = []
            for item in line_items:
                line_id = item['id']
                sku = item['sku']
                item_status = status_map.get(line_id, "Unknown")
                sent_date, delivered_date = None, None
                discount_amount = (sum(float(i['amount_set']['presentment_money']['amount']) 
                                     for i in item.get("discount_allocations", [])) 
                                 if item.get("discount_allocations") else 0)

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
                    'sku': sku,
                    "sent_date": sent_date,
                    "delivered_date": delivered_date,
                    "discount_codes": discount_codes,
                    "discount_amount": discount_amount,
                    "line_id": line_id
                })

            # Store item rows in session state for use in tab 2
            st.session_state.item_rows = item_rows

            # Display items (read-only in this tab)
            for i, row in enumerate(item_rows):
                # Calculate eligibility
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
                discount_percentage = sales['percentage'].get(row['sku'], 0)
                eligibility_status, status_icon, eligibility_options = get_eligibility_options(
                    row["is_final_sale"], days_held_count, has_discount, discount_percentage, order_count
                )

                with st.expander(f"📦 {row['item']['name']} — {status_icon} {eligibility_status}", expanded=True):
                    col1, col2, col3 = st.columns([2, 2, 3])
                    
                    with col1:
                        st.markdown("**📋 Item Details**")
                        st.write(f"**Quantity:** {row['item']['quantity']}")
                        st.write(f"**Price:** {row['item']['price_set']['presentment_money']['amount']} {row['item']['price_set']['presentment_money']['currency_code']}")
                        st.write(f"**Final Price:** {float(row['item']['price_set']['presentment_money']['amount'])-float(row['discount_amount'])} {row['item']['price_set']['presentment_money']['currency_code']}")
                        st.write(f"**Status:** `{row['status']}`")
                        st.write(f"**Final Sale:** {'✅ Yes' if row['is_final_sale'] else '❌ No'}")
                        if discount_percentage:
                            st.write(f"**Total Discount:** {discount_percentage}%")

                    with col2:
                        st.markdown("**📅 Shipping Info**")
                        st.write(f"**Sent:** {sent_at_fmt}")
                        st.write(f"**Delivered:** {delivered_at_fmt}")
                        if days_held_count is not None:
                            st.write(f"**Days Held:** {days_held_count} day(s)")

                    with col3:
                        st.markdown("**🔄 Return Eligibility**")
                        if eligibility_status == "FINAL SALE":
                            st.error("❌ FINAL SALE — Cannot be returned")
                        elif eligibility_status == "EXPIRED":
                            st.error("⛔ Return period expired")
                        elif eligibility_status == "More than 30% off":
                            st.error("❌ High discount - Cannot be returned")
                        else:
                            st.success("✅ Eligible for return")
                            st.markdown("**Available options:**")
                            for j, option in enumerate(eligibility_options, 1):
                                st.write(f"{j}. {option}")

            st.info("💡 **Tip:** Go to the 'Response Generator' tab to select items and create customer responses.")

        except Exception as e:
            st.error(f"❌ Error loading order details: {str(e)}")
# Replace the form section in Tab 2 with this corrected version:

with tab2:
    st.subheader("📝 Response Generator")
    
    if not st.session_state.current_order_data:
        st.warning("⚠️ Please search and load an order in the 'Order Search & Review' tab first.")
    else:
        # Display order summary
        order_data = st.session_state.current_order_data
        st.success(f"✅ **Order #{order_data['name']}** — {order_data['billing_address']['name']}")
        
        if not st.session_state.item_rows:
            st.warning("⚠️ No items found for this order.")
        else:
            # Create form for item selection and response generation
            with st.form("response_form"):
                st.markdown("### Select Items for Return Processing")
                
                selected_items = []
                
                # Display items with checkboxes for selection
                for i, row in enumerate(st.session_state.item_rows):
                    # Calculate eligibility (same logic as tab 1)
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
                    discount_percentage = sales['percentage'].get(row['sku'], 0)
                    eligibility_status, status_icon, eligibility_options = get_eligibility_options(
                        row["is_final_sale"], days_held_count, has_discount, discount_percentage, st.session_state.order_count
                    )

                    # Checkbox for item selection
                    is_selected = st.checkbox(
                        f"{status_icon} {row['item']['name']} (Qty: {row['item']['quantity']}) - {eligibility_status}",
                        key=f"select_{row['line_id']}"
                    )
                    
                    if is_selected:
                        selected_items.append({
                            'line_id': row['line_id'],
                            'name': row['item']['name'],
                            'quantity': row['item']['quantity'],
                            'eligibility_status': eligibility_status,
                            'options': eligibility_options if eligibility_status == "ELIGIBLE" else []
                        })

                # Submit button (ONLY form submit button allowed in forms)
                st.markdown("---")
                submitted = st.form_submit_button("📧 Generate Customer Response", type="primary", use_container_width=True)
            
            # MOVED OUTSIDE THE FORM - Handle form submission and display response
            if submitted:
                if not selected_items:
                    st.error("❌ Please select at least one item to generate a response.")
                else:
                    with st.spinner("Generating customer response..."):
                        response_text = generate_customer_response(
                            st.session_state.current_order_data, 
                            selected_items
                        )
                        # Store response in session state
                        st.session_state.generated_response = response_text
                        st.session_state.response_generated = True
            
            # Display generated response if it exists (OUTSIDE THE FORM)
            if hasattr(st.session_state, 'response_generated') and st.session_state.response_generated:
                st.markdown("---")
                st.markdown("### 📧 Generated Customer Response")
                
                # Copy button - NOW OUTSIDE THE FORM
                col1, col2 = st.columns([1, 0.1])
                with col2:
                    if st.button("📋", help="Copy to clipboard", key="copy_response"):
                        st.write("Response ready to copy!")
                
                # Display response as code block
                st.code(st.session_state.generated_response, language=None)
                
                st.success("✅ Response generated successfully!")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("*Returns Portal Pro v4.0*")
with col2:
    if st.session_state.current_order_data:
        st.markdown(f"*Order: {st.session_state.current_order_data['name']}*")
with col3:
    st.markdown(f"*Last updated: {datetime.datetime.now().strftime('%H:%M')}*")
