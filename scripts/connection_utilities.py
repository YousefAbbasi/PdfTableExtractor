# US Industrial PDF Extraction Web-App

#############
# LIBRARIES #
#############
import os, uuid, sys
from azure.storage.filedatalake import DataLakeServiceClient
from azure.core._match_conditions import MatchConditions
from azure.storage.filedatalake._models import ContentSettings
import streamlit as st
from azure.storage.blob import BlobServiceClient
import asyncio
import pandas as pd
import pyodbc

#######################
# CONNECTION SETTINGS #
#######################


########################
# CONNECTION FUNCTIONS #
########################

## Upload file to ADLS
def UploadPDFtoADLS(pdf_path):
    try:
        # Get blob path:
        path = "uploaded-pdfs/"+pdf_path.split("/")[-1]

        # Get Blob client:
        blob_client = blockblobservice.get_blob_client(container="advancedanalytics-sharedstorage", blob=path)
        
        # Upload to Blob container
        with open(pdf_path, "rb") as data:
            blob_client.upload_blob(data, overwrite = True)

        return True
    
    except Exception as e:
        print(e)
        return False

## Create SQL tables if they don't exist
def CreateTables(df_to_upload, comps_type):
    # Get table info
    table_name = ''.join(comps_type.split())
    column_names = list(df_to_upload.columns.values)

    # Clean up column names:
    for i, name in enumerate(column_names):
        column_names[i] = column_names[i].replace(" ", "_")
        column_names[i] = column_names[i].replace(".", "")
        column_names[i] = column_names[i].replace("(", "")
        column_names[i] = column_names[i].replace(")", "")
        column_names[i] = column_names[i].replace("%", "PERCENT")
        column_names[i] = column_names[i].replace("$", "PRICE")
        column_names[i] = column_names[i].replace("/", "_PER_")

    column_datatypes = ['varchar(100)' for i in range(len(column_names))]

    # Create table
    createTableStatement = f'CREATE TABLE {table_name} ('
    for i in range(len(column_datatypes)):
        createTableStatement = createTableStatement + '\n' + column_names[i] + ' ' + column_datatypes[i] + ','
    createTableStatement = createTableStatement[:-1] + ' );'

    cursor.execute(createTableStatement)

    return True

## Add quotes to string
def AddQuotes(string):
    return_val = "'"+string+"'"
    return return_val

## Upload file to SQL DB
def AppendTableSQLDB(df_to_upload, comps_type):
    # Get table name:
    table = ''.join(comps_type.split())
    
    # Check if table exists, create if not
    if not cursor.tables(table=table, tableType='TABLE').fetchone():
        CreateTables(df_to_upload, comps_type)

    # Get Spark DF from pandas DF
    for index, row in df_to_upload.iterrows():
        # Turn row into comma separated string
        row = row.astype(str)
        row = row.apply(lambda x: AddQuotes(x))
        vals = ','.join(row.fillna(value="None").to_list())

        # Insert into SQL DB
        cursor.execute(f"INSERT INTO {table} values ({vals})")

    return True

def CloseCursor():
    cursor.close()
    return True
