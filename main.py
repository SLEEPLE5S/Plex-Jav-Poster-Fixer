from io import BytesIO
import os
from tempfile import NamedTemporaryFile

from PIL import Image
import requests
from plexapi.server import PlexServer
from plexapi.video import Movie
from dotenv import load_dotenv

load_dotenv()
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
TPDB_TOKEN = os.getenv("TPDB_TOKEN")

ITEM_NAME = input("Item Name: ")

if not PLEX_TOKEN:
    os.abort()

plex = PlexServer("http://192.168.0.103:32400", PLEX_TOKEN)
library = plex.library.section("JAV")
item: Movie = library.get(ITEM_NAME)

if not isinstance(item, Movie):
    os.abort()

r = requests.get(
    url = "https://api.theporndb.net/jav",
    params = {
        "parse": ITEM_NAME
    },
    headers = {
        "Authorization": f"Bearer {TPDB_TOKEN}"
    }
)

r = r.json()["data"][0]
background = r["background"]["full"]

with requests.get(url = background, stream = True) as r:
    r.raise_for_status()
    
    image_bytes = BytesIO(r.content)

image = Image.open(image_bytes)

width, height = image.size
target_ratio = 2 / 3
current_ratio = width / height
if current_ratio <= target_ratio:
    os.abort()

target_width = round(height * target_ratio)
image = image.crop(
    (width - target_width, 0, width, height)
)
image.show()

upload = input("Upload? ")

if upload != "1":
    os.abort()

with NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
    temp_path = temp.name

try:
    image.convert("RGB").save(temp_path, format="JPEG")
    item.uploadPoster(filepath = temp_path)
finally:
    os.remove(temp_path)