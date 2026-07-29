#!/usr/bin/env python

"""
Original script from:  https://github.com/cedadev/opendap-python-example/blob/master/remote_nc_with_token.py
(downloaded 10.07.2026)
remote_nc_with_token.py
===================
Python script for downloading a NetCDF file remotely from the CEDA archive.
You will be prompted to provide your CEDA username and password the first time the script is run and
again if the token cached from a previous attempt has expired.
"""
#% Import modules
from requests.models import Response
from typing import Any
import json
import os
import requests
import shutil
from base64 import b64encode
from datetime import datetime, timezone
from getpass import getpass
import xarray as xr
from pathlib import Path

# %% Sort out token

# URL for the CEDA Token API service
TOKEN_URL = "https://services-beta.ceda.ac.uk/api/token/create/"
# Location on the filesystem to store a cached download token
TOKEN_CACHE: str = os.path.expanduser(path=os.path.join("~", ".cedatoken"))


def load_cached_token():
    """
    Read the token back out from its cache file.
    Returns a tuple containing the token and its expiry timestamp
    """
    # Read the token back out from its cache file
    try:
        with open(file=TOKEN_CACHE, mode="r") as cache_file:
            data: Any = json.loads(cache_file.read())

            token: Any = data.get("access_token")
            expires: datetime = datetime.strptime(data.get("expires"), "%Y-%m-%dT%H:%M:%S.%f%z")
            return token, expires

    except FileNotFoundError:
        return None, None


def get_token():
    """Fetches a download token, either from a cache file or
     from the token API using CEDA login credentials.

    Returns an active download token
    """

    # Check the cache file to see if we already have an active token
    token, expires = load_cached_token()

    # If no token has been cached or the token has expired, we get a new one
    now: datetime = datetime.now(tz=timezone.utc)
    if not token or expires < now:

        if not token:
            print(f"No previous token found at {TOKEN_CACHE}. ", end="")
        else:
            print(f"Token at {TOKEN_CACHE} has expired. ", end="")
        print("Generating a fresh token...")

        print("Please provide your CEDA username: ", end="")
        username: str = input()
        password: str = getpass(prompt="CEDA user password: ")

        credentials: str = b64encode(s=f"{username}:{password}".encode("utf-8")).decode(
            encoding="ascii"
        )
        headers: dict[str, str] = {
            "Authorization": f"Basic {credentials}",
        }
        response: Response = requests.request("POST", TOKEN_URL, headers=headers)
        if response.status_code == 200:

            # The token endpoint returns JSON
            response_data: Any = json.loads(response.text)
            token: Any = response_data["access_token"]

            # Store the JSON data in the cache file for future use
            with open(file=TOKEN_CACHE, mode="w") as cache_file:
                cache_file.write(response.text)

        else:
            print("Failed to generate token, check your username and password.")

    else:
        print(f"Found existing token at {TOKEN_CACHE}, skipping authentication.")

    return token, expires



# %% Download routine

def download_dataset(url:str,save_loc:Path,download_token=None):
    # isolate just the file name for saving
    filename: str= Path(url).name
    # headers should carry the download token so CEDA
    # knows who we are
    headers: dict = {"Authorization": f"Bearer {download_token}"} if download_token else {}
    try:
        with requests.Session() as session:
            with session.get(url, headers=headers, stream=True) as response:
                response.raise_for_status()
                # Use shutil to copy the stream directly to the file
                with open(file=save_loc/filename, mode='wb') as f:
                    shutil.copyfileobj(fsrc=response.raw, fdst=f)
        return True
    ## catch some exception types with specific messages, generic at end. 
    except requests.exceptions.RequestException as e:
        print(f"Network/Request error while downloading {filename}: {e}")
    except IOError as e:
        print(f"File system error while saving {filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return False 


# %% Entry point function
def get_file(url:str,var_id:str,save_loc):
    "Download file located at provided url"
    token, expires = get_token()
    if token:
        print(f"Fetching information about variable '{var_id}' using data URL: '{url}'")
        if token:
            print((f"Using download token '{token[:2]}...{token[-2:]}' for authentication."
                f" Token expires at: {expires}."))
        else:
            print("No DOWNLOAD_TOKEN found in environment.")

        # download and save
        # this will return a True/False flag depending on 
        # if error was raised (False = Error raised)
        return download_dataset(url, save_loc, download_token=token)
    else:
        print("Aborting since we don't have a token.")