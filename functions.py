import requests
import re
import http.client
import json
import datetime
import time
import pandas as pd
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Accessing keys from .env
SHOPIFY_TOKEN = os.getenv("SHOPIFY_TOKEN")
INVOICEEXPRESS_KEY = os.getenv("INVOICEEXPRESS_KEY")

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

def transform_datetime_obs(input_datetime):
    try:
        # Split the input string to extract the date part
        date_part = input_datetime.split('T')[0]

        # Reformat the date part to DD/MM/YYYY
        year, month, day = date_part.split('-')
        formatted_date_dd_mm_yyyy = f"{day}/{month}/{year}"

        # Reformat the date part to 'DD Month YYYY'
        from datetime import datetime
        dt_object = datetime.strptime(date_part, '%Y-%m-%d')
        formatted_date_dd_month_yyyy = dt_object.strftime('%d %B %Y')

        return formatted_date_dd_month_yyyy
    except Exception as e:
        return f"Invalid input format: {e}"



def transform_datetime(input_datetime):
    try:
        # Split the input string to extract the date part
        date_part = input_datetime.split('T')[0]

        # Reformat the date part to DD/MM/YYYY
        year, month, day = date_part.split('-')
        formatted_date = f"{day}/{month}/{year}"

        return formatted_date
    except Exception as e:
        return f"Invalid input format: {e}"

import copy
import re


def transform_to_second_format(first_json):


    rate = get_exchange_rate()



    country=first_json['shipping_address']["country"]
    if country=='United Kingdom':
        observations=f'Product origin: Portugal\nThe exporter of the products covered by this document declares that, except where otherwise clearly indicated, these products are of Portuguese preferential origin.\nLisbon, {str(datetime.datetime.today().strftime("%d %B %Y"))
}, Hanse Pty Ltd'
        country='UK'
        
    else:
        observations='Product origin: Portugal'
        country=first_json['shipping_address']["country"]
    
    address_parts = [
        first_json['shipping_address'].get("address1"),
        first_json['shipping_address'].get("address2"),
        first_json['shipping_address'].get("province_code")
    ]
    
    # Filter out None values and join them with a space
    address = ' '.join(part for part in address_parts if part is not None)


    
    second_json = {
        "invoice": {
            "date": str(datetime.datetime.today().strftime('%d/%m/%Y')),
            "due_date": str(datetime.datetime.today().strftime('%d/%m/%Y')),
            "reference": re.sub('#','',first_json['name']),
            "observations": observations,
            'tax_exemption_reason':'M05',
            "retention": None,
            "tax_exemption": "M05",
            "sequence_id": "LuxmiiSequence",
            "manual_sequence_number": None,
            "client": {
                "name": first_json['shipping_address']["name"],
                "code": re.sub('#','',first_json['name']),
                "email": None,
                "address": address,
                "city": first_json['shipping_address']["city"],
                "postal_code": first_json['shipping_address']["zip"],
                "country": country,
                "fiscal_id": None,
                "website": None,
                "phone": None,
                "fax": None,
                "language": None
            },
            "items": []
        }
    }
    
    for item in first_json['line_items']:
        #remove fullfilled items
        if (item['fulfillment_status']!='fulfilled')&(item['current_quantity']>0):
            if len(item["discount_allocations"])>0:
                ammount_disc=sum([float(i['amount']) for i in item["discount_allocations"]])
                ammount_disc=round(ammount_disc*rate*0.3,2)
                    
                second_item = {
                    "name": item["name"],
                    "description": item["sku"],
                    "unit_price": round(rate*float(item["price"])*0.3,2),
                    "quantity": item["quantity"],
                    "unit": None,
                    "discount": round((ammount_disc/round(rate*float(item["price"])*0.3,2))*100,2),
                    "discount_amount": round(ammount_disc,2)
                }
                second_json["invoice"]["items"].append(second_item)
            else:
                        
                second_item = {
                    "name": item["name"],
                    "description": item["sku"],
                    "unit_price": round(rate*float(item["price"])*0.3,2),
                    "quantity": item["quantity"],
                    "unit": None,
                    "discount": None,
                    "discount_amount": None
                }
                second_json["invoice"]["items"].append(second_item)
        
    return second_json




def create_invoice(order_id):
    # Initialize variables for retry mechanism
    max_retries = 5
    retry_delay = 1  # Initial delay in seconds
    attempt = 0
    
    url = f"https://luxmii.com/admin/api/2024-10/orders/{order_id}.json"
    
    payload={}
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': SHOPIFY_TOKEN
    }
    
    # Retry loop for Shopify API
    while attempt < max_retries:
        try:
            response = requests.request("GET", url, headers=headers, data=payload)
            response.raise_for_status()  # Raises an exception for 4XX/5XX status codes
            data = response.json()
            break  # If successful, exit the retry loop
            
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            attempt += 1
            if attempt == max_retries:
                raise Exception(f"Failed to fetch Shopify order after {max_retries} attempts: {str(e)}")
            
            print(f"Attempt {attempt} failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
    
    z = data['order']
    
    # Rest of your original function remains the same
    conn = http.client.HTTPSConnection("intervwovenunipes.app.invoicexpress.com")
    payload = json.dumps(transform_to_second_format(z))
    
    headers = {
        'accept': "application/json",
        'content-type': "application/json"
    }
    
    api_key = INVOICEEXPRESS_KEY
    endpoint = f"/invoices.json?api_key={api_key}"
    
    conn.request("POST", endpoint, payload, headers)
    
    response = conn.getresponse()
    data = response.read()
    return(data)