# PdfTableExtractor
How this app works:

You upload one or more pdf files. The app finds pages that are relevant based on some criteria. The user then selects the page they like. The app converts that page into a canvas. The user then draws a rectangle around the relevant tables existing on that page. The code then extracts the information from that table and uploads it to a sql database.


Main file: app.py
helper files: connection_utilities.py , extraction_utilities.py
