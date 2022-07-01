# Oxford US Industrial PDF Extraction Web-App

#############
# LIBRARIES #
#############

import os
import glob
import filecmp
import base64
import streamlit as st
#import camelot
import time
from io import StringIO
import joblib
from tabulate import tabulate
import tabula
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, DataReturnMode
import pandas as pd
from ast import literal_eval
#from functions import pdf_converter
from PyPDF2 import PdfFileReader
from extraction_utilities import Page, display_page_as_canvas, get_extraction_param_values, display_tables, key_generator, p_title, img_to_bytes, save_uploadedfile, structure_data
from connection_utilities import AppendTableSQLDB, UploadPDFtoADLS, CloseCursor
import numpy as np
import datetime
import pdfplumber
import re
import xlsxwriter

###############
# PAGE SET UP #
###############
## Configure page and add title
st.set_page_config(page_title="US Industrial PDF Extractor", 
                   page_icon=":factory:",
                   layout="wide",
                   initial_sidebar_state="expanded"
                   )

p_title("US Industrial PDF Data Extraction Tool")

## Set state variables (remain static with page upload)
if 'complete_files' not in st.session_state:
    st.session_state.complete_files = [] # Captures the list of files that have been successfully extracted, verified, and sent to the SQL server

if 'initial_files' not in st.session_state:
    st.session_state.initial_files = [] # Captures the list of files initially uploaded

if 'complete_comps_types' not in st.session_state:
    st.session_state.complete_comps_types = [] # Captures the list of comps types already assessed within a document

if 'initial_comps_types' not in st.session_state:
    st.session_state.initial_comps_types = [] # Captures the list of initial comps types in a document

if 'complete_pages' not in st.session_state:
    st.session_state.complete_pages = [] # Captures the list of pages already assessed within a document

if 'initial_pages' not in st.session_state:
    st.session_state.initial_pages = [] # Captures the list of pages initially to be assessed

if 'page' not in st.session_state:
    st.session_state.page = None # Captures information and methods related to current page

if 'coordinates_obtained' not in st.session_state:
    st.session_state.coordinates_obtained = False # Determines whether or not user has selected bounding box

if 'coordinates_key' not in st.session_state:
    st.session_state.coordinates_key = key_generator() # Get key for bounding box submit button

if 'submit_key' not in st.session_state:
    st.session_state.submit_key = key_generator() # Get key for table submit button

if 'skip_key' not in st.session_state:
    st.session_state.skip_key = key_generator() # Get key for "skip page" button

if 'file_counter' not in st.session_state:
    st.session_state.file_counter=0

if 'buffer' not in st.session_state:
    st.session_state.buffer=None

###########
# functions #
###########

def func1(PDF_Path,progress_bar_placeholder):

    Comp_Types = ["Lease Comps", "Sales Comps", "Land Sales Comps"]
    Comp_Strings = ["lease((?<!d)(?=s| |$))", "(?<!land) sale(?=s| |$)", "land sale(?=s| |$)"]
    Lease_Comps_PageList = []
    Sales_Comps_PageList = []
    LandSales_Comps_PageList = []
    pdf = pdfplumber.open(PDF_Path)
    num_pages = len(pdf.pages)
    file_processing_bar_init = 0
    file_processing_bar = progress_bar_placeholder.progress(file_processing_bar_init)
    file_processing_placeholder = st.empty()
        
    for i in range(0, num_pages):
        file_processing_bar.progress(file_processing_bar_init)
        file_processing_bar_init += (1/num_pages)
        text = pdf.pages[i].extract_text()
        text = text.lower()

        for string,types in zip(Comp_Strings,Comp_Types):
            file_processing_placeholder.markdown(f"<em style='text-align: left; color: #d1d1d1; font-size:20px;'>\
            Now searching page {i}/{num_pages} for {types} of {PDF_Path}...</em>", unsafe_allow_html=True)
            time.sleep(.1)
            if re.search(string, text) and re.search("(comp(?=s| |$))|(comparable(?=s| |$))", text):
                if types=="Lease Comps":
                    Lease_Comps_PageList.append(i)
                if types=="Sales Comps":
                    Sales_Comps_PageList.append(i)
                if types=="LandSales Comps":
                    LandSales_Comps_PageList.append(i)
    
    if len(Lease_Comps_PageList) == 0:
            Comp_Types.remove("Lease Comps")
    
    if len(Sales_Comps_PageList) == 0:
            Comp_Types.remove("Sales Comps")

    if len(LandSales_Comps_PageList) == 0:
            Comp_Types.remove("Land Sales Comps")

    file_processing_placeholder.markdown("")
    return Comp_Types,Lease_Comps_PageList,Sales_Comps_PageList,LandSales_Comps_PageList
    

    

###########
# SIDEBAR #
###########

## Get PDF files to extract

progress_bar_placeholder = st.empty()
if not st.session_state.initial_files:
    st.sidebar.image("images/OxfordLogo.png", use_column_width=True)
    files = st.sidebar.file_uploader('Upload your file here',type=['pdf'], accept_multiple_files=True, key='testuploader')
    st.session_state.initial_files = files
    file_loading_bar_init = 0
    file_loading_bar = progress_bar_placeholder.progress(file_loading_bar_init)
    with st.spinner('Saving...'):
        # Save file names and paths
        st.session_state.f_paths = []
        st.session_state.f_names = []

        # Instantiate progress bar for file upload
        file_loading_bar_init = 0
        file_loading_bar = progress_bar_placeholder.progress(file_loading_bar_init)

        # Save each file
        for file in files:
            file_loading_bar.progress(file_loading_bar_init + 1/len(files))
            st.session_state.f_paths.append(save_uploadedfile(file))
            st.session_state.f_names.append(file.name)
            temp0,temp1,temp2,temp3=func1(st.session_state.f_paths[-1], progress_bar_placeholder)
            if temp0!=[]:
                st.session_state.initial_comps_types.append(temp0)
                st.session_state.initial_pages.append([temp1,temp2,temp3])
                st.session_state.complete_comps_types.append([])
                st.session_state.complete_pages.append([[]]*len(temp0))
            else:
                st.warning(f'warning: "{file.name}" did not include any comparables info in it. The file was discarded.')
                st.session_state.f_paths.remove(st.session_state.f_paths[-1])
                st.session_state.f_names.remove(file.name)


#Remove any files that have already been extracted, verified, and sent to the SQL server
for file in st.session_state.initial_files:
    if file in st.session_state.complete_files:
        try:
            st.session_state.f_paths.remove(st.session_state.f_paths[st.session_state.f_names.index(file.name)])
            st.session_state.f_names.remove(file.name)
            st.session_state.file_counter+=1
        except:
            pass
    if len(st.session_state.f_names)==0:
        st.success("Page skipped; All files have now been successfully processed.")

        


#############
# MAIN PAGE #
#############

## Main functionality if statement
if len(st.session_state.f_names) !=0:

    st.sidebar.write('** {} files have been uploaded successfuly**'.format(len(st.session_state.f_names)))
    # PDF is selected
    nav = st.sidebar.radio('Choose Uploaded PDF to Display',st.session_state.f_names)
    pdf_index=st.session_state.f_names.index(nav)
    path = st.session_state.f_paths[pdf_index]
    pdf_index+=st.session_state.file_counter

    progress_bar_placeholder.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Select category of \
    comparable and page to verify.</h3>", unsafe_allow_html=True)
    
    # Display comps selection relevant to PDF
    comps_to_display = []
    for comp in st.session_state.initial_comps_types[pdf_index]:
        if comp not in st.session_state.complete_comps_types[pdf_index]:
            comps_to_display.append(comp)
    comps_type = st.selectbox("Comps Type", comps_to_display)

    comps_index=st.session_state.initial_comps_types[pdf_index].index(comps_type)


    # Select page
    pages_to_display = []
    for page in st.session_state.initial_pages[pdf_index][comps_index]:
        if page not in st.session_state.complete_pages[pdf_index][comps_index]:
            pages_to_display.append(page + 1)
    page_number = st.radio("Page to Analyze", pages_to_display, horizontal=True,key=909)
    page_number = page_number - 1


    st.markdown('___')


    # Select which package to use
    # package = st.radio("Select package", ["PDF Plumber", "Camelot", "Tabula"], horizontal=True)

    # Define page
    if st.session_state.page==None or st.session_state.buffer!=[pdf_index,comps_index,page_number] :
        st.session_state.page = Page(path, page_number, "PDF Plumber", comps_type)
        st.session_state.buffer=[pdf_index,comps_index,page_number]
        st.session_state.coordinates_obtained = False
    # Necessary for run
    #if not st.session_state.page.Page_Number:
    st.session_state.page.Page_Number = page_number

    # Check if a bounding box has been selected
    if not st.session_state.coordinates_obtained:

        st.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Select bounding box.</h3>",
        unsafe_allow_html=True)

        st.info("Use your mouse to click and drag a bounding box over the table you would like to select. If this page \
        does not have a desired table, select 'Skip Page'. When done drawing bounding box, press 'Submit'.")
        
        # Get coordinates
        image_data = display_page_as_canvas(path, page_number)

        # If skip page has been selected, go through the process of checking remaining pages/comps types/PDFs
        if st.button("Skip Page", key = st.session_state.skip_key):
            # Since page has been completed, remove session state page information
            st.session_state.complete_pages[pdf_index][comps_index]=st.session_state.complete_pages[pdf_index][comps_index]+[st.session_state.page.Page_Number]
            st.session_state.coordinates_obtained = False
            st.session_state.page=None

            if len(st.session_state.complete_pages[pdf_index][comps_index]) == len(st.session_state.initial_pages[pdf_index][comps_index]):
                # All pages of comp have been verified
                st.session_state.complete_comps_types[pdf_index]=st.session_state.complete_comps_types[pdf_index]+[comps_type]

                # Check to see if there are other comps to be verified in file.
                if len(st.session_state.complete_comps_types[pdf_index]) == len(st.session_state.initial_comps_types[pdf_index]):
                    st.session_state.complete_files.append(st.session_state.initial_files[pdf_index])


                    if len(st.session_state.complete_files) == len(st.session_state.initial_files):
                        st.success("Page skipped; All files have now been \
                        successfully processed.")
                        time.sleep(1)

                        # Close SQL connection
                        #CloseCursor()

                    else:
                        st.success("Page skipped; all pages in the file have been processed. Select one of the other files \
                        from the list on the left sidebar to continue processing")
                else:
                    st.success("All pages for selected comparables category have been processed. Select one of the \
                    other comparables categories from the dropdown menu at the top of the page to continue editing.")      
            else:
                # There are still pages to verify.
                st.success("Page skipped. Select one of the other pages from the list at the top of the page to continue \
                editing.")
        else:
            
            # Check if a bounding box has been drawn
            if np.nonzero(image_data)[0].size != 0:

                # Populate coordinate data
                st.session_state.page.Populate_Table_Coordinates(image_data)

                # Check if "Submit" button has been pressed
                if st.button("Submit", key=st.session_state.coordinates_key):
                    st.session_state.coordinates_obtained = True
                    time.sleep(0.5)
                else: 
                    time.sleep(0.5)

    else:
        # Show PDF in markdown format
        f = open(path, "rb")
        input1 = PdfFileReader(open(path, 'rb'))
        pdf_coordinates = input1.getPage(0).mediaBox
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="{round(float(pdf_coordinates[2])*0.7)}" \
        height="{round(float(pdf_coordinates[3])*0.7)}" type="application/pdf">' 
        st.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Selected PDF</h3>",
        unsafe_allow_html=True)
        st.markdown(pdf_display, unsafe_allow_html=True)
        f.close()
        
        st.markdown('___')
        
        # Get extraction parameter values
        st.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Select extraction parameters.</h3>",
        unsafe_allow_html=True)
        st.info("These extraction parameters can be modified to change the way the PDF extractor processes the table. The parameteres are described below.")
        st.session_state.page.Get_Extraction_Param_Vals(get_extraction_param_values(st.session_state.page))
        
        # Get tables

        st.session_state.page.Extract_Tables_From_PDF_Page()
        
        st.markdown('___')

        submit_placeholder = st.empty()

        # Check if edited table has been submitted
        if submit_placeholder.button("Submit", key=st.session_state.submit_key):
            
            # When extraction/verification has been completed for a selected file   
            data= pd.read_excel("tempDir/"+nav.split(".")[0]+"_VERIFIED"+".xlsx",engine='openpyxl')
            submit_placeholder.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Extracted Data</h3>",
            unsafe_allow_html=True)

            #st.markdown("<h3 style='text-align: left; color: #35495A; font-size:20px;'>Raw Extracted Data</h3>"
            #, unsafe_allow_html=True)
            #st.dataframe(data)

            # Get data into standard format
            processed_data = structure_data(data, comps_type)

            # Send to SQL DB
            AppendTableSQLDB(processed_data, comps_type)

            # Display submitted data
            st.markdown("<h3 style='text-align: left; color: #35495A; font-size:20px;'>Processed Extracted \
            Data</h3>", unsafe_allow_html=True)
            st.dataframe(processed_data)

            # Since page has been completed, remove session state page information
            st.session_state.complete_pages[pdf_index][comps_index]=st.session_state.complete_pages[pdf_index][comps_index]+[st.session_state.page.Page_Number]
            st.session_state.coordinates_obtained = False
            st.session_state.page=None

            if len(st.session_state.complete_pages[pdf_index][comps_index]) == len(st.session_state.initial_pages[pdf_index][comps_index]):
                # All pages of comp have been verified
                st.session_state.complete_comps_types[pdf_index]=st.session_state.complete_comps_types[pdf_index]+[comps_type]

                # Check to see if there are other comps to be verified in file.
                if len(st.session_state.complete_comps_types[pdf_index]) == len(st.session_state.initial_comps_types[pdf_index]):
                    st.session_state.complete_files.append(st.session_state.initial_files[pdf_index])


                    if len(st.session_state.complete_files) == len(st.session_state.initial_files):
                        st.success("Page skipped; All files have now been \
                        successfully processed.")
                        time.sleep(3)

                        # Close SQL connection
                        #CloseCursor()

                    else:
                        st.success("File extraction, verification, and upload complete. Select one of the other files from \
                        the list on the left sidebar to continue processing")
                else:
                    st.success("All pages for selected comparables category have been processed. Select one of the \
                    other comparables categories from the dropdown menu at the top of the page to continue editing.")      
            else:
                # There are still pages to verify.
                st.success("Page extraction, verification, and upload complete. Select one of the other pages from the list \
                at the top of the page to continue editing.")
        else:
            
            # Selected file is still in the extraction / verification stage
            data = st.session_state.page.Tables
            
            st.markdown("<h3 style='text-align: left; color: #35495A; font-size:28px;'>Verify Extracted Data</h3>",
            unsafe_allow_html=True)
            st.info("Using the checkboxes on the left side of the 'Raw Extracted Data' table, select the rows you would like \
            to send to the SQL database. Cells may be edited by double clicking and pressing 'Enter' when done. The output \
            to the SQL table will be displayed in the 'Processed Extracted Data' table below. Press the 'Submit' button \
            above when complete.")

            # Display extracted table
            try:
                # Display editable AgGrid table with raw data
                st.markdown("<h3 style='text-align: left; color: #35495A; font-size:20px;'>Raw Extracted Data</h3>"
                , unsafe_allow_html=True)
                data = display_tables(data) #display data as an editable grid

                # Show what the data will look like when processed into standard format
                st.markdown("<h3 style='text-align: left; color: #35495A; font-size:20px;'>Processed Extracted \
                Data</h3>", unsafe_allow_html=True)
                processed_data = structure_data(data, comps_type)
                st.dataframe(processed_data)
                st.write(str(datetime.datetime.now()))
                
                # Save edited data to temporary table
                writer = pd.ExcelWriter("tempDir/"+nav.split(".")[0]+"_VERIFIED"+".xlsx", engine='xlsxwriter')
                data.to_excel(writer, sheet_name='0')
                writer.save()
                time.sleep(1)


            # If the PDF extraction tool doesn't recognize a table / throws up an error
            except:
                st.error("Table unrecognized. Try changing the extraction parameters (e.g. Vertical and Horizontal strategy).")

else:
    
    # Landing page (when files have not yet been uploaded)
    cols = st.columns(3)
    cols[1].image("images/OxfordIndustrial.jpg")
    st.markdown("<h3 style='text-align: center; color: grey; font-size:20px;'>Upload a property memo to extract comps analysis information!</h3>", unsafe_allow_html=True)
    st.markdown('___')
    st.write('Upload PDFs using the dynamic upload tool at the top of the sidebar on the left side of the page.')

