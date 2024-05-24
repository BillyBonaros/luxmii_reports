import pandas as pd
import numpy as np

admin_api_token='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'

api_key='e6f3f85adba0bb34acfa99cf671ca3e2'

API_secret_key='43f68fb4fe472dab25739e4f83649365'


import pandas as pd
import numpy as np
import re
import requests


def get_all_orders():
    last=0
    orders=pd.DataFrame()
    while True:
#         url = f"https://{apikey}:{password}@{hostname}/admin/api/{version}/{resource}.json?limit=250&fulfillment_status=unfulfilled&since_id={last}"
#         response = requests.request("GET", url)
        
        
        url = f"https://luxmii.com/admin/api/2024-04/orders.json?limit=250&fulfillment_status=unfulfilled&since_id={last}"

        payload={}
        headers = {
          'Content-Type': 'application/json',
          'X-Shopify-Access-Token': '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'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        
        
        df=pd.DataFrame(response.json()['orders'])
        orders=pd.concat([orders,df])
        last=df['id'].iloc[-1]
        if len(df)<250:
            break
    return(orders)



df=get_all_orders()

df['list_items']=df['line_items'].apply(lambda x:[{'name':i['name'],'id':i['id'],'quantity':i['quantity']} for i in x] )

s=df[['name','id','list_items']].explode('list_items')

s.reset_index(inplace=True,drop=True)

s['product_name']=s['list_items'].apply(lambda x:x['name'])
s['item_id']=s['list_items'].apply(lambda x:x['id'])
s['quantity']=s['list_items'].apply(lambda x:x['quantity'])

s.drop('list_items',axis=1,inplace=True)






def get_item_location(order_id):
    url = f"https://luxmii.com/admin/api/2024-04/orders/{order_id}/fulfillment_orders.json"

    payload={}
    headers = {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': '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'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    
    z=pd.DataFrame((response.json()['fulfillment_orders']))

    z['list_items']=z['line_items'].apply(lambda x:[ i['line_item_id'] for i in x])
    z['location']=z['assigned_location'].apply(lambda x: x['country_code'])
    z=z[['list_items','location']].explode('list_items')
    z.columns=['item_id','location']
    z=z.drop_duplicates().reset_index(drop=True)
    return(z)

# locs=pd.DataFrame()
# for order_id in list(s['id'].unique()):
#     locs=pd.concat([locs,get_item_location(order_id)])

# data=s.merge(locs,on='item_id',how='left')
data=s.copy()


# data=data[data['location']!='AU']

# data=data.sort_values('name')

data.to_excel('WorkBook3.xlsx')


import smtplib
from email.mime.text import MIMEText
# MIMEMultipart send emails with both text content and attachments.
from email.mime.multipart import MIMEMultipart
# MIMEText for creating body of the email message.
from email.mime.text import MIMEText
# MIMEApplication attaching application-specific data (like CSV files) to email messages.
from email.mime.application import MIMEApplication

subject = "Email Subject"
body = "This is the body of the text message"
sender = "luxmii.agent@gmail.com"
recipients = ["billybonaros@gmail.com"]
password = "czue irol jdfh eeua"
path_to_file = 'WorkBook3.xlsx'
body_part = MIMEText(body)



def send_email(subject, body, sender, recipients, password):
    msg= MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    body_part = MIMEText(body)
    msg.attach(body_part)


        # section 1 to attach file
    with open(path_to_file,'rb') as file:
        # Attach the file with filename to the email
        msg.attach(MIMEApplication(file.read(), Name="example.xlsx"))

    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())
    print("Message sent!")


send_email(subject, body, sender, recipients, password)

