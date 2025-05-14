import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import os
from pypdf import PdfReader
import re
from pathlib import Path
import shutil

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Please login first.")
    st.stop()

st.title('Luxmii Order Extractor - PDF Rename')

with st.form(key='my_form'):
    file_uploaded = st.file_uploader("Upload")
    submit_button=st.form_submit_button('Submit')

    
    


if submit_button:
    my_dir = "extracted"
    with zipfile.ZipFile(file_uploaded, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            if zip_info.is_dir():
                continue
            zip_info.filename = os.path.basename(zip_info.filename)
            zip_ref.extract(zip_info, my_dir)

    files=os.listdir('extracted')

        
    files=[i for i in files if 'pdf' in i]
    files=[i for i in os.listdir('extracted') if not i.startswith('.')]
    orders=[]
    for i in files:
        inp=f"{my_dir}/{i}"
        
        reader = PdfReader(inp)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        try:
            out=re.findall('Order No.:\n\#*(\d+)',text)[0]
            os.rename(inp, f'{my_dir}/{out}.pdf')
            orders.append(out)
        except:
            continue
    
    st.write(','.join(orders))

    fp_zip = Path("output.zip")
    path_to_archive = Path(f"./{my_dir}")

    with zipfile.ZipFile(fp_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fp in path_to_archive.glob("**/*"):
            zipf.write(fp, arcname=fp.relative_to(path_to_archive))

    shutil.rmtree(f'{my_dir}')

    with open("output.zip", "rb") as fp:
        btn = st.download_button(
            label="Download ZIP",
            data=fp,
            file_name="output.zip",
            mime="application/zip"
        )