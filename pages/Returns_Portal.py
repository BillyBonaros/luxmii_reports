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
import os
import requests
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from requests.exceptions import RequestException

# Disable SSL warnings and load environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()
API_KEY = os.getenv("shopify_key")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Shopify API Headers
HEADERS = {
    'Content-Type': 'application/json',
    'X-Shopify-Access-Token': API_KEY
}

def get_shopify_data(order_id, max_retries=3):
    url = f"https://luxmii.com/admin/api/2024-10/orders/{order_id}.json"
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, verify=False)
            response.raise_for_status()
            return response.json()["order"]
        except RequestException:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)

def get_item_status(order_id, max_retries=3):
    url = f"https://luxmii.com/admin/api/2024-04/orders/{order_id}/fulfillment_orders.json"
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, verify=False)
            response.raise_for_status()
            fulfillment_orders = response.json()["fulfillment_orders"]
            status_map = {}
            for fo in fulfillment_orders:
                for item in fo["line_items"]:
                    status_map[item["line_item_id"]] = fo["status"]
            return status_map
        except RequestException:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)

def get_order_count(customer_id):
    url = f"https://luxmii.com/admin/api/2024-04/customers/{customer_id}.json"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    return response.json()['customer']['orders_count']

def get_variant_prices(variant_id):
    url = f"https://luxmii.com/admin/api/2024-04/variants/{variant_id}.json"
    try:
        response = requests.get(url, headers=HEADERS, verify=False)
        response.raise_for_status()
        variant = response.json()["variant"]
        price = float(variant.get("price", 0))
        compare_at_price = float(variant["compare_at_price"]) if variant.get("compare_at_price") else 0
        return price, compare_at_price
    except Exception as e:
        print(f"Error fetching variant {variant_id}: {e}")
        return None, None

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

def get_days_held(delivered_at):
    if not delivered_at:
        return None
    delivered_dt = datetime.fromisoformat(delivered_at)
    now = datetime.now(timezone.utc).astimezone(delivered_dt.tzinfo)
    return (now - delivered_dt).days

def get_eligibility(is_final_sale, days_held, discount_pct, has_discount, order_count):
    if is_final_sale:
        return "FINAL SALE", ["Cannot be returned"]
    if days_held is not None and days_held > 30:
        return "EXPIRED", ["Store credit (-$20 USD label)"]
    if discount_pct > 20:
        return "More than 20% off", ["Store credit (-$20 USD label)",
                                      "Item exchange (-$20 USD label)",
                                      "Alteration subsidy: 10% refund + $20 USD gift voucher"]
    if order_count == 1:
        return "ELIGIBLE", [
            "120% store credit + free returns",
            "Item exchange (-$20 USD label)",
            "Refund (-$30 USD label)",
            "Alteration subsidy: 10% refund + $20 USD gift voucher"
        ]
    elif has_discount:
        return "ELIGIBLE", [
            "Store credit (-$20 USD label)",
            "Item exchange (-$20 USD label)",
            "Alteration subsidy: 10% refund + $20 USD gift voucher",
            "Discretionary Refunds: We reserve the right to approve a refund outside of our standard policy if, in our judgment, it is appropriate to do so."
        ]
    else:
        return "ELIGIBLE", [
            "120% store credit + free returns",
            "Item exchange (-$20 USD label)",
            "Refund (-$30 USD label)",
            "Alteration subsidy: 10% refund + $20 USD gift voucher"
        ]

def process_order_items(order, statuses, order_count):
    results = []
    fulfillments = order.get("fulfillments", [])
    refunds = order.get("refunds", [])

    for item in order['line_items']:
        # if  (item['fulfillment_status']!='fulfilled')&(item['current_quantity']>0):
        if  item['current_quantity']>0:

            item_id = item['id']
            quantity = item['quantity']
            
            # Get the actual price paid per item (this is already after all discounts)
            price_per_item = float(item['price'])
            

            pm = item["price_set"]["presentment_money"]
            amount = pm["amount"]
            currency = pm["currency_code"]
            actual_paid= str(amount)+' '+currency
            qty = item["quantity"]
            # Total discount for this line in customer's currency
            line_discount = sum([float(i['amount_set']['presentment_money']['amount']) for i in item['discount_allocations']])
            # Gross line (unit * qty) in customer's currency
            line_gross = (amount * qty)
            line_net = (float(line_gross) - float(line_discount))
            line_net= str(line_net)+' '+currency




            # Get discount allocations from the item (these are additional discounts like coupon codes)
            discount_allocs = item.get("discount_allocations", [])
            total_discount_amount = sum(float(d['amount']) for d in discount_allocs)
            
            # Calculate discount percentage ONLY from the discount allocations in the order data
            discount_percentage = 0
            if quantity > 0 and total_discount_amount > 0:
                # Calculate percentage based on the discount amount vs original item price
                original_item_price = price_per_item / quantity
                discount_percentage = round((total_discount_amount / quantity / original_item_price) * 100, 2)
            
            # Get variant information ONLY for the indicator
            variant_id = item.get("variant_id")
            variant_price, compare_at_price = get_variant_prices(variant_id)
            
            # Check if there's a variant discount (compare_at_price exists and is higher than current variant price)
            has_variant_discount = compare_at_price is not None and variant_price is not None and compare_at_price > variant_price
            
            # Determine discount sources
            discount_sources = []
            has_order_discount = len(order.get("discount_codes", [])) > 0
            has_item_discount = total_discount_amount > 0
            
            if has_variant_discount:
                discount_sources.append("Variant Sale Price")
            if has_item_discount:
                discount_sources.append("Item Discount Allocation")
            if has_order_discount:
                discount_sources.append("Order Discount Code")
                
            discount_source_text = ", ".join(discount_sources) if discount_sources else "None"

            # Check fulfillment / delivery
            delivered_at = None
            for f in fulfillments:
                for f_item in f.get("line_items", []):
                    if f_item['id'] == item_id and f.get("shipment_status") == "delivered":
                        delivered_at = f.get("updated_at")
            days_held = get_days_held(delivered_at)

            # Other checks
            is_final_sale = any(p['value'] == "Final Sale" for p in item.get("properties", []))
            has_discount = bool(order.get("discount_codes"))

            # Was item returned
            was_returned = any(
                item_id == refund_line_item.get("line_item_id")
                for refund in refunds
                for refund_line_item in refund.get("refund_line_items", [])
            )

            # Eligibility logic
            eligibility_status, return_options = get_eligibility(
                is_final_sale, days_held, discount_percentage, has_discount, order_count
            )

            return_code_map = {
                "FINAL SALE": "RS-FINAL",
                "EXPIRED": "RS-30",
                "More than 20% off": "RS-DISCOUNT",
                "ELIGIBLE": "RS-OK"
            }
            return_code = return_code_map.get(eligibility_status, "RS-UNK")

            return_label = "RETURNED" if was_returned else eligibility_status

            if compare_at_price!=0:
                variant_dic=(float(variant_price)/float(compare_at_price)) -1
            else:
                variant_dic=0
            results.append({
                "name": item["name"],
                "sku": item["sku"],
                "line_item_id":item['id'],
                "quantity": quantity,
                "paid_price": round(price_per_item, 2),
                "discount_amount": round(total_discount_amount / quantity, 2) if quantity > 0 else 0,
                "discount_percentage": discount_percentage,
                "discount_sources": discount_source_text,
                "has_variant_discount": has_variant_discount,
                "status": statuses.get(item_id, "Unknown"),
                "was_returned": was_returned,
                "return_label": return_label,
                "return_code": return_code,
                "eligibility_status": eligibility_status,
                "return_options": return_options,
                "days_held": days_held,
                "variant_discount": round(variant_dic,2)*100,
                "actual_paid":actual_paid,
                "line_net":line_net
            })

    return results


# Initialize session state
if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []
if 'current_order_data' not in st.session_state:
    st.session_state.current_order_data = None
if 'item_rows' not in st.session_state:
    st.session_state.item_rows = []
if 'order_count' not in st.session_state:
    st.session_state.order_count = 0

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
    .discount-alert {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        padding: 0.5rem;
        border-radius: 4px;
        margin: 0.5rem 0;
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

# Search section
st.subheader("🔍 Order Search")

col1, col2 = st.columns([1, 3])
with col1:
    search_method = st.selectbox("Search by", ["Order ID", "Email", "Order Name"])
with col2:
    query_input = st.text_input(
        f"Enter {search_method}", 
        placeholder=f"Type your {search_method.lower()} here and press Enter...",
        key="search_input",
        help="Press Enter to search"
    )

selected_order_id = None

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
            customer_id = order_data['customer']['id']
            order_count = get_order_count(customer_id)
            results = process_order_items(order=order_data, statuses=status_map, order_count=order_count)

            # Store order data in session state
            st.session_state.current_order_data = order_data

        st.session_state.order_count = order_count

        line_items = order_data.get("line_items", [])
        fulfillments = order_data.get("fulfillments", [])
        discounts = order_data.get("discount_codes", [])
        discount_codes = ", ".join([d['code'] for d in discounts]) if discounts else "None"

        # Enhanced order header with discount codes
        st.markdown("---")
        st.subheader("📋 Order Details")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success(f"✅ **Order #{order_data['name']}** — {order_data['email']}")
            st.success(f"[View Order](https://admin.shopify.com/store/luxmii-au/orders/{order_data['id']})")

            
            customer_status = "🟢 First-time Customer" if order_count == 1 else f"🔵 Returning Customer - {order_count} orders"
            st.write(f"**Customer:** {order_data['billing_address']['name']} - {customer_status}")
            st.write(f"**Country:** {order_data['billing_address']['country']}")
            st.write(f"**Total:** {order_data['total_price_set']['presentment_money']['amount']} {order_data['total_price_set']['presentment_money']['currency_code']}")
            
            # Show discount codes applied
            if discount_codes != "None":
                st.write(f"**💰 Discount Codes Applied:** `{discount_codes}`")
            else:
                st.write("**💰 Discount Codes Applied:** None")
                
            if order_data['tags']:
                st.write(f"**Tags:** {order_data['tags']}")
        
        with col2:
            st.metric("Order Count", order_count)
            st.metric("Items", len(line_items))

        # Process items for display
        st.markdown("---")
        st.subheader("📦 Items Review")
        
        # Store item rows in session state for use in tab 2
        st.session_state.results = results

        # Display items with improved discount information

        for item in results:
            #here we can add filters based on status
            # if (status_map[item["line_item_id"]]!='closed')&(status_map[item["line_item_id"]]!='on_hold'):
            if True:
                col1, col2, col3 = st.columns([2, 2, 3])

                # --- Column 1: Item details ---
                with col1:
                    st.markdown("**📋 Item Details**")
                    st.write(f"**Name:** {item['name']}")
                    st.write(f"**SKU:** `{item['sku']}`")
                    st.write(f"**Quantity:** {item['quantity']}")
                    # st.write(f"**Paid Price:** ${item['paid_price']:.2f}")
                    st.write(f"**Paid Price:** {item['line_net']}")
                    
                    # Show discount information from order data only
                    if item['discount_amount'] > 0:
                        st.write(f"**💰 Discount Amount:** ${item['discount_amount']:.2f}")
                        st.write(f"**💰 Discount Percentage:** {item['discount_percentage']}%")
                        # st.write(f"**💰 Discount Source:** {item['discount_sources']}")
                    else:
                        st.write("**💰 Discount:** None")
                    
                    # Show variant discount indicator (independent of order discounts)
                    if item['has_variant_discount']:
                                        # --- Column 2: Shipping info ---
                        with col2:
                            st.markdown("**📅 More Info**")
                            # st.write("**Sent:** Not available")
                            # st.write("**Delivered:** Not available")
                            if item['days_held'] is not None:
                                st.write(f"**Days Held:** {item['days_held']} day(s)")
                                st.write(f"**Status:** `{item['status']}`")
                                st.write(f"**Was Returned:** {'✅ Yes' if item['was_returned'] else '❌ No'}")

                            else:
                                st.write("**Days Held:** Not provided")
                                st.write(f"**Status:** `{item['status']}`")
                                st.write(f"**Was Returned:** {'✅ Yes' if item['was_returned'] else '❌ No'}")
                        with col3:
                                st.markdown(f'<div class="discount-alert">🏷️ <strong>THIS ITEM HAS VARIANT DISCOUNT - {item["variant_discount"]}%. PLEASE CHECK MANUALY</strong></div>', unsafe_allow_html=True)

                    else:

                        # --- Column 2: Shipping info ---
                        with col2:
                            st.markdown("**📅 More Info**")
                            # st.write("**Sent:** Not available")
                            # st.write("**Delivered:** Not available")
                            if item['days_held'] is not None:
                                st.write(f"**Days Held:** {item['days_held']} day(s)")
                                st.write(f"**Status:** `{item['status']}`")
                                st.write(f"**Was Returned:** {'✅ Yes' if item['was_returned'] else '❌ No'}")

                            else:
                                st.write("**Days Held:** Not provided")
                                st.write(f"**Status:** `{item['status']}`")
                                st.write(f"**Was Returned:** {'✅ Yes' if item['was_returned'] else '❌ No'}")
                        # --- Column 3: Return eligibility ---
                        with col3:
                            st.markdown("**🔄 Return Eligibility**")
                            if item['eligibility_status'] == "FINAL SALE":
                                st.error("❌ FINAL SALE — Cannot be returned")
                            elif item['eligibility_status'] == "EXPIRED":
                                st.error("⛔ Return period expired")
                                st.markdown("**Available options:**")
                                for idx, option in enumerate(item['return_options'], start=1):
                                    st.write(f"{idx}. {option}")
                            # elif item['discount_percentage'] > 20:
                            #     st.error(f"❌ High discount ({item['discount_percentage']}%) - Cannot be returned")
                            else:
                                st.success("✅ Eligible for return")
                                st.markdown("**Available options:**")
                                for idx, option in enumerate(item['return_options'], start=1):
                                    st.write(f"{idx}. {option}")
                st.markdown("---")

    except Exception as e:
        st.error(f"❌ Error loading order details: {str(e)}")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("*Returns Portal Pro v4.1*")
with col2:
    if st.session_state.current_order_data:
        st.markdown(f"*Order: {st.session_state.current_order_data['name']}*")
with col3:
    st.markdown(f"*Last updated: {datetime.now().strftime('%H:%M')}*")
