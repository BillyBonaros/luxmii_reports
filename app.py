import streamlit as st
import pandas as pd
import numpy as np
import re
import requests
import os
import smtplib
from email.mime.text import MIMEText
# MIMEMultipart send emails with both text content and attachments.
from email.mime.multipart import MIMEMultipart
# MIMEText for creating body of the email message.
from email.mime.text import MIMEText
# MIMEApplication attaching application-specific data (like CSV files) to email messages.
from email.mime.application import MIMEApplication
st.set_page_config(layout='wide')
# key= st.secrets["shopify_key"]
key = os.environ['shopify_key']


st.title("Luxmii Production Management Report")

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




def get_all_orders():
    last=0
    orders=pd.DataFrame()
    while True:        
        url = f"https://luxmii.com/admin/api/2024-04/orders.json?limit=250&fulfillment_status=unfulfilled&since_id={last}"

        payload={}
        headers = {
          'Content-Type': 'application/json',
          'X-Shopify-Access-Token': key
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        
        
        df=pd.DataFrame(response.json()['orders'])
        orders=pd.concat([orders,df])
        last=df['id'].iloc[-1]
        if len(df)<250:
            break
    return(orders)

def get_item_location(order_id):
    url = f"https://luxmii.com/admin/api/2024-04/orders/{order_id}/fulfillment_orders.json"

    payload={}
    headers = {
      'Content-Type': 'application/json',
      'X-Shopify-Access-Token': key
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    
    z=pd.DataFrame((response.json()['fulfillment_orders']))

    z['list_items']=z['line_items'].apply(lambda x:[ i['line_item_id'] for i in x])
    z['location']=z['assigned_location'].apply(lambda x: x['country_code'])
    z=z[['list_items','location']].explode('list_items')
    z.columns=['item_id','location']
    z=z.drop_duplicates().reset_index(drop=True)
    return(z)



def get_the_data():
    df=get_all_orders()
    df['list_items']=df['line_items'].apply(lambda x:[{'name':i['name'],'id':i['id'],'quantity':i['quantity']} for i in x] )
    s=df[['name','id','list_items','created_at']].explode('list_items')
    s.reset_index(inplace=True,drop=True)
    s['product_name']=s['list_items'].apply(lambda x:x['name'])
    s['item_id']=s['list_items'].apply(lambda x:x['id'])
    s['quantity']=s['list_items'].apply(lambda x:x['quantity'])
    s.drop('list_items',axis=1,inplace=True)

    locs=pd.DataFrame()
    for order_id in list(s['id'].unique()):
        locs=pd.concat([locs,get_item_location(order_id)])

    data=s.merge(locs,on='item_id',how='left')
    data=data[data['location']!='AU']


    #remove_fullfiled items
    d=df[df['fulfillments'].apply(lambda x: len(x)>0)]
    ff=list(d['fulfillments'].apply(lambda x: [[z['id'] for z in i['line_items']] for i in x]).explode().explode())
    data=data[~data['item_id'].isin(ff)]


    tab1=data.sort_values('name')
    tab2=data.groupby('product_name').agg({'quantity':'sum','name':list})
    tab2['name']=tab2['name'].apply(lambda x: ', '.join(x))
    tab2=tab2.rename(columns={'name':'order_numbers'})
    tab2['check']=False
    tab2['notes']=np.nan
    tab1['check']=False
    tab1['notes']=np.nan
    tab1=tab1.drop(['id','item_id','location'],axis=1)
    tab1=tab1[['name', 'product_name', 'quantity','check','notes','created_at']]
    tab1=tab1.rename(columns={'name':'order'})
    return(tab1, tab2)
col1, col2, col3,col4, col5 = st.columns(5)

update_button=col1.button("Update the Data")
save_button=col2.button("Save")

if update_button:
    with st.spinner('Wait for it...'):

        # df1,df2=get_the_data()

        a,b=get_the_data()
        df1=pd.read_csv('tab1.csv',dtype={'notes':str})
        df2=pd.read_csv('tab2.csv',dtype={'notes':str})

        df1=a.merge(df1[['order','product_name','notes']],on=['order','product_name'],how='left')
        df1['notes']=df1['notes_y'].combine_first(df1['notes_x'])
        df1=df1[['order', 'product_name', 'quantity', 'check',  'notes', 'created_at']]

        b.reset_index(inplace=True)
        df2=b.merge(df2[['product_name','notes']],on='product_name',how='left')
        df2['notes']=df2['notes_y'].combine_first(df2['notes_x'])
        df2=df2[['product_name','quantity','order_numbers','check','notes']]

        df1.to_csv('tab1.csv',index=False)
        df2.to_csv('tab2.csv',index=False)
        st.success('Done!')


tab1, tab2 = st.tabs(["All Data", "Aggregated Items"])
df1=pd.read_csv('tab1.csv',dtype={'notes':str})
df2=pd.read_csv('tab2.csv',dtype={'notes':str})

with tab1:
    edited_df1 = st.data_editor(df1, num_rows="fixed", use_container_width=True )
with tab2:
    edited_df2= st.data_editor(df2, num_rows="fixed", use_container_width=True )
    
if save_button:
    edited_df1.to_csv('tab1.csv',index=False)
    edited_df2.to_csv('tab2.csv',index=False)
    
