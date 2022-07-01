# Oxford US Industrial PDF Extraction Web-App

#############
# LIBRARIES #
#############

import os
import glob
import tabula
import streamlit as st
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, DataReturnMode
import random
import PyPDF2
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
import pdfplumber
from io import StringIO
import re
# import camelot
import fitz
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import numpy as np
from PyPDF2 import PdfFileReader
import pandas as pd
from PIL import Image
import time


######################
# COLUMN HEADER DICT #
######################

# Determines mapping for "structure_data" function

lease_comps_dict = {
"ADDRESS": ["ADDRESS", "BUILDING", "PROPERTY"],
"MARKET": ["MARKET", "CITY", "TOWN", "SUBMARKET"],
"YEAR BUILT": ["YEAR BUILT"],
"BLDG. CONFIG": ["CONFIG"],
"CLEAR HEIGHT (FT)": ["CLEAR"],
"BLDG. DEPTH (FT)": ["DEPTH"],
"TRAILER PARKING": ["TRAILER", "PARKING"],
"LANDLORD": ["LANDLORD"],
"TENANT NAME": ["TENANT"],
"BUILDING SQUARE FOOTAGE": ["BLDG SF"],
"LEASED SQUARE FOOTAGE": ["LEASED SF", "SQUARE", "FEET", "FOOTAGE", "SIZE"],
"LEASE START DATE": ["LCD", "DATE", "LEASE START", "COMMENCEMENT"],
"TERM (MONTHS)": ["TERM"],
"FREE RENT (MONTHS)": ["FREE RENT"],
"STARTING NNN RATE (PSF/YR)": ["STARTING", "NNN", "RENTAL"],
"ESCALATIONS": ["ESCALATIONS", "ESC", "INCREASES"],
"TENANT IMPROVEMENTS (PSF)": ["TI", "TENANT IMPROVEMENTS", "IMPROVEMENTS"],
"LEASE TYPE": ["LEASE TYPE"]
}

sales_comps_dict = {
"ADDRESS": ["ADDRESS", "BUILDING", "PROPERTY"],  
"MARKET": ["MARKET", "CITY", "TOWN", "SUBMARKET"],
"YEAR BUILT": ["YEAR BUILT", "YR BUILT"],
"BLDG. CONFIG": ["CONFIG"],
"CLEAR HEIGHT (FT)": ["CLEAR"],
"SELLER": ["SELLER"],
"BUYER": ["BUYER"],
"SALE DATE": ["SALES DATE", "SALE DATE", "DATE"],
"OCCUPANCY": ["OCCUPANCY"],
"WALT (YRS)": ["WALT"],
"SQUARE FOOTAGE": ["(?<!P)SF", "SQUARE", "FOOTAGE", ""],
"SALE PRICE": ["SALES PRICE((?<! PSF)|(?<! PLSF)|(?<! (PSF))|(?<! (PLSF)))", "SALE PRICE"],
"SALE PRICE PSF": ["SPSF", "PSF"],
"CAP RATE WITH NO VACANCY DEDUCT": ["CAP RATE", "CAP RATE W/ NO"],
"CAP RATE WITH 5% VACANCY DEDUCT": ["CAP RATE W/ 5%"],
"BROKER": ["BROKER"]
}

land_sales_comps_dict = {
"ADDRESS": ["ADDRESS", "BUILDING", "PROPERTY"],
"MARKET": ["MARKET", "CITY", "TOWN", "SUBMARKET"],
"SELLER": ["SELLER"],
"BUYER": ["BUYER"],
"SALE DATE": ["SALES DATE", "SALE DATE"],
"LAND AREA (ACRES)": ["ACRES", "AREA"],
"SALE PRICE": ["SALES PRICE((?<! PSF)|(?<! PLSF)|(?<! (PSF))|(?<! (PLSF)))", "SALE PRICE"],
"SALE PRICE PSF": ["PLSF", "PRICE PER", "PSF"],
"BUILDABLE SQUARE FOOTAGE": ["BUILDABLE", "LAND SF", "SQUARE"],
"RAW LAND (BLDG $/SF)": ["RAW"],
"LAND IMPROVEMENTS TO PAD READY (BLDG $/SF)": ["IMPROVEMENTS", "PAD"],
"TOTAL LAND (BLDG $/SF)": ["TOTAL"]
}
#SALES PRICE(?! \(PSF\))(?! PSF)(?! PLSF)(?! \(PLSF\))
##################
# HELPER CLASSES #
##################

class Page:

    def __init__(self, pdf_path, page_number, library_option, comp_type):

        # PDF and page info
        self.PDF_Path = pdf_path
        self.Page_Number = page_number
        self.Comp_Type = comp_type
        
        # Library option is given to start
        self.Library_Option = library_option
        
        # Extraction parameter names and details for sliders
        # {"Param Name": [Min, Max, Step]}
        self.Extraction_Parameters = []
        self.Determine_Extraction_Params()

        # Extraction parameter values
        self.Extraction_Parameter_Values = {}
        
        # Table coordinates
        self.Table_Coordinates = []

        # Table list
        self.Tables = []

    ## Extraction parameter input values
    def Determine_Extraction_Params(self):

        # if self.Library_Option == "Camelot":
        #     table_settings = {
        #     "Edge Tolerance": [0, 1000, 10],
        #     "Row Tolerance": [0, 100, 1],
        #     # "Line Scale": [0, 100, 1],
        #     }

        if self.Library_Option == "PDF Plumber":
            table_settings = {
            "Snap Tolerance": [0.0, 10.0, 0.1],
            "Join Tolerance": [0.0, 10.0, 0.1],
            "Edge Minimum Length": [0.0, 10.0, 0.1],
            "Text Tolerance": [0.0, 10.0, 0.1],
            "Intersection Tolerance": [0.0, 10.0, 0.1],
            "Vertical Strategy": ["Lines", "Text"],
            "Horizontal Strategy": ["Lines", "Text"]
            }

        elif self.Library_Option == "Tabula":
            table_settings = {}

        self.Extraction_Parameters = table_settings
        
        return True
    
    ## Collect extraction parameter values input by user
    def Get_Extraction_Param_Vals(self, vals):

        # if self.Library_Option == "Camelot":
        #     table_settings_vals = {
        #     "edge_tol": vals["Edge Tolerance"],
        #     "row_tol": vals["Row Tolerance"]
        #     # "line_scale": vals["Line Scale"],
        #     }
            

        if self.Library_Option == "PDF Plumber":

            table_settings_vals = {
            "vertical_strategy": vals["Vertical Strategy"], 
            "horizontal_strategy": vals["Horizontal Strategy"],
            "snap_tolerance": vals["Snap Tolerance"],
            "join_tolerance": vals["Join Tolerance"],
            "edge_min_length": vals["Edge Minimum Length"],
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "keep_blank_chars": True,
            "text_tolerance": vals["Text Tolerance"],
            "intersection_tolerance": vals["Intersection Tolerance"],
            }

        elif self.Library_Option == "Tabula":
            table_settings_vals = {}
        
        self.Extraction_Parameter_Values = table_settings_vals

        return True

    ## Get coordinate data from bounding box and scale to PDF
    def Populate_Table_Coordinates(self, image_data):
        pdf = pdfplumber.open(self.PDF_Path)
        p = pdf.pages[self.Page_Number]

        if np.nonzero(image_data)[0].size != 0:

            min_x = np.amin(np.nonzero(image_data)[1])
            max_x = np.amax(np.nonzero(image_data)[1])
            min_y = np.amin(np.nonzero(image_data)[0])
            max_y = np.amax(np.nonzero(image_data)[0])

            x_ratio = p.width / image_data.shape[1]
            y_ratio = p.height / image_data.shape[0]

            new_min_x = round(min_x * x_ratio)
            new_max_x = round(max_x * x_ratio)
            new_min_y = round(min_y * y_ratio)
            new_max_y = round(max_y * y_ratio)

            # Return accurate coordinates
            coords = [new_min_x, new_min_y, new_max_x, new_max_y]
        
        else:
            coords = []
        
        self.Table_Coordinates = coords

        return True

    ## Get image of PDF page cropped according to bounding box
    def Get_Cropped_Image(self):
        PDF = fitz.open(self.PDF_Path)
        PDF_page = PDF.loadPage(self.Page_Number)  # number of page
        PDF_page.set_cropbox(fitz.Rect(self.Table_Coordinates[0], self.Table_Coordinates[1], self.Table_Coordinates[2],
        self.Table_Coordinates[3]))
        pix = PDF_page.get_pixmap()
        st.image(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        return True

    ## Extraction functions
    def Extract_Tables_From_PDF_Page_PDF_Plumber(self):

        pdf = pdfplumber.open(self.PDF_Path)
        p = pdf.pages[self.Page_Number]
        p = p.crop(self.Table_Coordinates)
        
        tables = p.extract_tables(self.Extraction_Parameter_Values)
        pd_tables = []
        
        for table in tables:
            pd_tables.append(pd.DataFrame(table[1::],columns=table[0]))
        
        self.Tables = pd_tables

        return True

    def Extract_Tables_From_PDF_Page_Tabula(self):
        tables = tabula.read_pdf(self.PDF_Path, stream = True, pages = self.Page_Number)
        pd_tables = []
        
        for table in tables:
            pd_tables.append(table)
        
        self.Tables = pd_tables

        return True

    # def Extract_Tables_From_PDF_Page_Camelot(self):
    #     tables = camelot.read_pdf(self.PDF_Path, flavor='stream', table_areas = [','.join([str(i) for i in self.Table_Coordinates])], 
    #     edge_tol = self.Extraction_Parameter_Values['edge_tol'], row_tol = self.Extraction_Parameter_Values['row_tol'] # , 
    #     # line_scale = self.Extraction_Parameter_Values['line_scale']
    #     )
    #     pd_tables = []
        
    #     for table in tables:
    #         pd_tables.append(table.df)
        
    #     self.Tables = pd_tables

    #     return True

    def Extract_Tables_From_PDF_Page(self):

        # if self.Library_Option == "Camelot":
        #     self.Extract_Tables_From_PDF_Page_Camelot()

        if self.Library_Option == "PDF Plumber":
            self.Extract_Tables_From_PDF_Page_PDF_Plumber()

        elif self.Library_Option == "Tabula":
            self.Extract_Tables_From_PDF_Page_Tabula()
        
        return True

####################
# HELPER FUNCTIONS #
####################

## Creates page title
def p_title(title):
    st.markdown(f'<h3 style="text-align: left; color:#35495A; font-size:32px;">{title}</h3>', unsafe_allow_html=True)

## Translates image data to byte data to display with markdown
def img_to_bytes(img_path):
    img_bytes = Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded

## Saves uploaded PDF files to 'tempDir' and returns the pathname 
def save_uploadedfile(uploadedfile):
    try:
        os.mkdir("tempDir")
    except:
        pass
    #tempDir_contents = str(glob.glob("tempDir/*"))
    with open(os.path.join("tempDir",uploadedfile.name),"wb") as f: 
        f.write(uploadedfile.getbuffer())
    return os.path.join("tempDir", uploadedfile.name)

## Function for displaying editable canvas
def display_page_as_canvas(pdf_path, page):
    # Get original page coordinates
    input1 = PdfFileReader(open(pdf_path, 'rb'))
    pdf_coordinates = input1.getPage(0).mediaBox

    # Get image from PDF
    PDF = fitz.open(pdf_path)
    PDF_page = PDF.loadPage(page)  # number of page
    pix = PDF_page.get_pixmap()

    # Get canvas drawing
    coordinates = st_canvas(
    fill_color="rgba(255, 165, 0, 0)",
    stroke_width=5,
    stroke_color="rgba(255, 0, 0, 1)",
    background_image=Image.frombytes("RGB", [pix.width, pix.height], pix.samples),
    update_streamlit=True,
    drawing_mode="rect",
    point_display_radius=0,
    key="canvas",
    height = round(float(pdf_coordinates[3])),
    width = round(float(pdf_coordinates[2]))
    )

    # Return the coordinates of the bounding box
    return coordinates.image_data

def get_extraction_param_values(page):


    return_settings = {}

    for param in page.Extraction_Parameters.keys():
        if param == "Text Tolerance":
            return_settings[param] = 9.0
        elif param == "Snap Tolerance":
            return_settings[param] = 5.0
        else:
            return_settings[param] = 0
    
    for param in page.Extraction_Parameters:
        if param == "Vertical Strategy":
            val = st.radio(param, page.Extraction_Parameters[param], horizontal = True)
            st.markdown("**Vertical Strategy:** Whether columns in the table are separated by lines, or simply aligned by text with blank space in between.")
            return_settings[param] = val.lower()
        elif param == "Horizontal Strategy":
            val = st.radio(param, page.Extraction_Parameters[param], horizontal = True)
            st.markdown("**Horizontal Strategy:** Whether rows in the table are separated by lines, or simply aligned by text with blank space in between.")
            return_settings[param] = val.lower()
    
    with st.expander(f"See advanced extraction parameters"):
        for param in page.Extraction_Parameters:
            if param == "Text Tolerance":
                val = st.slider(param, min_value = page.Extraction_Parameters[param][0], 
                max_value = page.Extraction_Parameters[param][1], step = page.Extraction_Parameters[param][2], value = 9.0)
                st.markdown("**Text Tolerance:** When the text strategy searches for words, it will expect the individual letters in each word to be no more than text_tolerance pixels apart.")
                return_settings[param] = val
            elif param == "Snap Tolerance":
                val = st.slider(param, min_value = page.Extraction_Parameters[param][0], 
                max_value = page.Extraction_Parameters[param][1], step = page.Extraction_Parameters[param][2], value = 5.0)
                st.markdown("**Snap Tolerance:** Parallel lines within snap_tolerance pixels will be 'snapped' to the same horizontal or vertical position.")
                return_settings[param] = val
            elif param == "Join Tolerance":
                val = st.slider(param, min_value = page.Extraction_Parameters[param][0], 
                max_value = page.Extraction_Parameters[param][1], step = page.Extraction_Parameters[param][2])
                st.markdown("**Join Tolerance:** Line segments on the same infinite line, and whose ends are within join_tolerance of one another, will be 'joined' into a single line segment.")
                return_settings[param] = val
            elif param == "Edge Minimum Length":
                val = st.slider(param, min_value = page.Extraction_Parameters[param][0], 
                max_value = page.Extraction_Parameters[param][1], step = page.Extraction_Parameters[param][2])
                st.markdown("**Edge Minimum Length:** Edges shorter than edge_min_length will be discarded before attempting to reconstruct the table.")
                return_settings[param] = val
            elif param == "Intersection Tolerance":
                val = st.slider(param, min_value = page.Extraction_Parameters[param][0], 
                max_value = page.Extraction_Parameters[param][1], step = page.Extraction_Parameters[param][2])
                st.markdown("**Intersection Tolerance:** When combining edges into cells, orthogonal edges must be within intersection_tolerance pixels to be considered intersecting.")
                return_settings[param] = val
    
    return return_settings

## Displays data as an editable AgGrid table
def display_tables(tables):

    data = tables[0]

    gb = GridOptionsBuilder.from_dataframe(data)
    gb.configure_default_column(editable=True)
    # gb.configure_pagination(paginationAutoPageSize=True) #Add pagination
    gb.configure_side_bar() #Add a sidebar
    gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren="Group checkbox select children")
    gridOptions = gb.build()

    grid_response = AgGrid(
        data,
        gridOptions=gridOptions,
        data_return_mode='FILTERED_AND_SORTED', 
        update_mode='MODEL_CHANGED', 
        fit_columns_on_grid_load=True,
        theme='blue', #Add theme color to the table
        enable_enterprise_modules=True,
        height=500, 
        width='100%',
        reload_data=False
    )

    data = pd.DataFrame(grid_response['selected_rows']) #Pass the selected rows to a new dataframe df
    
    return data

## Returns a random key (when multiple instances of one widget is required)
def key_generator():
    return random.randint(1, 10000000)

## Function for structuring data into standard format
def structure_data(df, comps_type):
    # Get rid of "Unnamed" columns:
    for col in df.columns:
        if "UNNAMED" in col.upper():
            df = df.drop(columns=[col])
    
    # Uppercase column names
    df.columns = df.columns.str.upper()

    # Process land sales comps
    if comps_type == "Land Sales Comps":
        for col in df.columns:
            for key in land_sales_comps_dict.keys():
                if any(term in col for term in land_sales_comps_dict[key]):
                    df = df.rename(columns={col: key})
        
        for key in land_sales_comps_dict.keys():
            if key not in df.columns:
                df[key] = None
    
    # Process sales comps
    elif comps_type == "Sales Comps":
        for col in df.columns:
            for key in sales_comps_dict.keys():
                if any(term in col for term in sales_comps_dict[key]):
                    df = df.rename(columns={col: key})
        
        for key in sales_comps_dict.keys():
            if key not in df.columns:
                df[key] = None
        
    # Process lease comps
    elif comps_type == "Lease Comps":
        for col in df.columns:
            for key in lease_comps_dict.keys():
                if any(re.search(term, col) for term in lease_comps_dict[key]):
                    df = df.rename(columns={col: key})
        
        for key in lease_comps_dict.keys():
            if key not in df.columns:
                df[key] = None
    
    # Alphebetize columns
    df = df.reindex(sorted(df.columns), axis=1)
    
    return df
