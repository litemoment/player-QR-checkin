import streamlit as st
import extra_streamlit_components as stx
import gspread
# from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime, timedelta
import qrcode
from PIL import Image
import io
import urllib.parse
from urllib.parse import urlparse

# Set the page configuration at the very start
st.set_page_config(page_title="Game Schedule Viewer", layout="wide")

def is_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_manager():
    return stx.CookieManager()

# Initialize the cookie manager
cookie_manager = get_manager()

spreadsheet_filename = "NCCSF QR Check-in"
page_title = spreadsheet_filename
page_url = "http://player-qr-checkin-nccsf.streamlit.app"

# Google Sheets setup
@st.cache_resource
def init_connection():
    # Create a connection object.
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
                "https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"
            ],
    )
    client = gspread.authorize(creds)
    return client

def get_sheets(client):
    spreadsheet = client.open(spreadsheet_filename)
    return [sheet.title for sheet in spreadsheet.worksheets()]

def get_data(client, sheet_name):
    sheet = client.open(spreadsheet_filename).worksheet(sheet_name)
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def update_description(sheet_name, row, new_description):
    client = init_connection()
    sheet = client.open(spreadsheet_filename).worksheet(sheet_name)
    sheet.update_cell(row+2, 1, new_description)  # Assuming "Wrist Band" is in column 1

# Authentication functions
def verify_credentials(username, password):
    correct_username = st.secrets["checkin_username"]
    correct_password = st.secrets["checkin_password"]
    return username == correct_username and password == correct_password

def is_authenticated():
    # auth_time = cookie_manager.get_cookie("last_login_time")
    auth_time = cookie_manager.get("last_login_time")
    if auth_time:
        last_login_time = datetime.fromisoformat(auth_time)
        if (datetime.now() - last_login_time) < timedelta(hours=24):
            return True
    return False

def set_authenticated():
    # cookie_manager.set_cookie(name="last_login_time", value=datetime.now().isoformat(), max_age=86400)  # 24 hours
    cookie_manager.set("last_login_time", datetime.now().isoformat(), max_age=86400)  # 24 hours

# Predefined color pairs as a dictionary
color_pairs = {
    "Black on White": ("#000000", "#FFFFFF"),
    "Purple on Gold": ("#800080", "#FFD700"),
    "Teal on Coral": ("#008080", "#FF6B6B"),
    "Orange on Navy": ("#FFA500", "#000080"),
    "Magenta on Lime": ("#FF00FF", "#00FF00"),
    "Turquoise on Salmon": ("#40E0D0", "#FA8072"),
    "Indigo on Peach": ("#4B0082", "#FFDAB9"),
    "Crimson on Lavender": ("#DC143C", "#E6E6FA"),
    "Olive on Slate": ("#808000", "#708090"),
    "Amber on Midnight": ("#FFBF00", "#191970"),
    "Plum on Khaki": ("#DDA0DD", "#F0E68C")
}

def generate_qr_code(url, fill_color, bg_color):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=bg_color)
    return img


# Check for query parameters
params = st.query_params
checkin = 'checkin' in params

# st.write("Current query_params:", params)

# Handle authentication
if checkin:
    if not is_authenticated():
        # with st.sidebar:
        st.info("Authentication Required for Check-in")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if verify_credentials(username, password):
                set_authenticated()
                st.success("Logged in successfully.")
            else:
                st.error("Incorrect username or password.")
    # is_authenticated
    else:
        client = init_connection()
        if 'teamname' in params and 'playerid' in params:
            selected_sheet = params['teamname']
            player_id = int(params['playerid']) - 1
            data = get_data(client, selected_sheet)
            if not data.empty and 0 <= player_id < len(data):
                selected_row = data.iloc[player_id]
                st.write(f"Selected Player Details for {selected_sheet}, Player ID {player_id + 1}:")
                st.json(selected_row.to_dict())
                # editable col
                description = st.text_area("Edit Wrist Band Detail", value=selected_row["Wrist Band"])
                if st.button("Update Wrist Band"):
                    update_description(selected_sheet, player_id, description)
                    st.success("Wrist Band updated successfully!")
                    data = get_data(client, selected_sheet)
                    selected_row = data.iloc[player_id]
                    st.write("Updated Player Details:")
                    st.json(selected_row.to_dict())
            else:
                st.error("No data available or invalid player ID.")

else:
    # team, player selection and show QR
    st.title(page_title)
    client = init_connection()
    sheet_names = get_sheets(client)
    selected_sheet = st.selectbox("Select a team", sheet_names)

    data = get_data(client, selected_sheet)
    if not data.empty:
        options = [f"{row['Player Name']}" for index, row in data.iterrows()]
        default_index = len(data) - 1
        choice = st.selectbox("Select a player:", options, index=default_index)
        selected_row_index = options.index(choice)
        selected_row = data.iloc[selected_row_index]
        st.write("Selected Player Details:")
        st.json(selected_row.to_dict())

    if selected_row['Player'] is not None:

        # Get the path from the query parameters
        # path_uri = params['/'][0] if '/' in params else None
        #
        # st.write("Current request URI:", path_uri, params)
        
        # Get the URL input from the user
        checkin_url = f"{page_url}?checkin&teamname={urllib.parse.quote(selected_sheet)}&playerid={selected_row['Player']}"

        # url = st.text_input("Enter the URL to generate a QR code:", value=checkin_url)
        url = checkin_url

        # Allow the user to choose a color pair
        # color_pair = st.selectbox("Select a color pair:", list(color_pairs.keys()))

        # Add a button to generate the QR code and download it
        if st.button("Generate QR Code for Check-in") and url:
            try:
                fill_color, bg_color = color_pairs["Black on White"]
                qr_img = generate_qr_code(url, fill_color, bg_color)
            
                # Save the PIL Image to a BytesIO buffer and convert it to bytes
                img_buffer = io.BytesIO()
                qr_img.save(img_buffer, format="PNG")
                img_bytes = img_buffer.getvalue()
                
                # Split the page into two columns
                col1, col2 = st.columns(2)

                # Display an image in the first column using half of the column width
                with col1:
                    # st.write("Player's photo not found")
                    # Check if the input looks like a URL
                    if is_url(selected_row['Photo URL']):
                        st.image(selected_row['Photo URL'], caption="Player Photo", use_column_width=True)
                    else:
                        st.write("Player's photo not found")

                # Continue adding content to the second column
                with col2:
                    st.image(img_bytes, caption="Generated QR Code", use_column_width=True)
        
                # Add a download button
                # st.download_button(
                #     label="Download QR Code",
                #     data=img_bytes,
                #     key="qr_code_download",
                #     file_name="qr_code.png",
                #     mime="image/png",
                # )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
