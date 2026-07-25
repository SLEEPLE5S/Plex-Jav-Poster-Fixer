from io import BytesIO
import os
from tempfile import NamedTemporaryFile
import tkinter as tk
from tkinter import Event
from typing import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from PIL import Image, ImageTk
import requests
from plexapi.server import PlexServer
from plexapi.video import Movie
from plexapi.library import MovieSection
from dotenv import load_dotenv

load_dotenv()

with open("completed.json", "r") as f:
    completed = json.load(f)

def update_completed(data: dict):
    with open("completed.json", "w") as f:
        json.dump(data, f, indent = 4)

def get_plex_items() -> list[Movie]:
    PLEX_TOKEN = os.getenv("PLEX_TOKEN")
    
    plex = PlexServer("http://192.168.0.103:32400", PLEX_TOKEN)
    library: MovieSection = plex.library.section("JAV")

    return library.all()

def get_poster(title: str) -> BytesIO | None:
    TPDB_TOKEN = os.getenv("TPDB_TOKEN")
    
    r = requests.get(
        url = "https://api.theporndb.net/jav",
        params = {
            "parse": title
        },
        headers = {
            "Authorization": f"Bearer {TPDB_TOKEN}"
        }
    )

    try:
        r = r.json()["data"][0]
        background = r["background"]["full"]
    except IndexError:
        return None
    
    if not background:
        return None
    
    with requests.get(url = background, stream = True) as r:
        r.raise_for_status()
        
        return BytesIO(r.content)

def crop_poster(poster: BytesIO) -> Image.Image:
    image = Image.open(poster)
    
    width, height = image.size
    target_ratio = 2 / 3
    current_ratio = width / height
    if current_ratio <= target_ratio:
        os.abort()

    target_width = round(height * target_ratio)
    image = image.crop(
        (
            max(0, width - target_width - 18),
            0,
            width,
            height
        )
    )
    
    return image

def upload(item: Movie, image: Image.Image):
    with NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
        temp_path = temp.name
        
    image.convert("RGB").save(temp_path, format="JPEG")
    item.uploadPoster(filepath = temp_path)

    os.remove(temp_path)
    
def review_images(
    items: Iterable[tuple[Image.Image, Movie]]
) -> None:
    items = list(items)
    index = 0
    
    root = tk.Tk()
    root.title("Poster Review")
    
    image_label = tk.Label(root)
    image_label.pack()
    
    title_label = tk.Label(root)
    title_label.pack()
    
    def show_current() -> None:
        nonlocal index

        if index >= len(items):
            root.destroy()
            return
        
        image, item = items[index]
        
        photo = ImageTk.PhotoImage(image)
        
        image_label.configure(image = photo)
        image_label.image = photo

        title_label.configure(
            text=f"{index + 1}/{len(items)} - {item.title}\n"
                 "ENTER = Upload | S = Skip | ESC = Quit"
        )
    
    def handle_key(event: tk.Event) -> None:
        nonlocal index

        if index >= len(items):
            return

        image, item = items[index]

        if event.keysym == "Return":
            print(f"Uploading: {item.title}")

            upload(item, image)
            completed["items"].append(item.title)
            update_completed(completed)

            index += 1
            show_current()

        elif event.keysym.lower() == "s":
            print(f"Skipping: {item.title}")

            index += 1
            show_current()

        elif event.keysym == "Escape":
            root.destroy()
        
    root.bind("<Key>", handle_key)
    root.focus_force()

    show_current()
    root.mainloop()

def handle_item(item: Movie) -> tuple[Image.Image, Movie] | None:
    poster = get_poster(item.title)
    if not poster: return None
    poster = crop_poster(poster)
    
    return (poster, item)

items = []
index = 1
with ThreadPoolExecutor(20) as executor:
    plex_items = get_plex_items()
    
    futures = [
        executor.submit(handle_item, item)
        for item in plex_items
        if item.title not in completed["items"]
    ]
    
    for future in as_completed(futures):
        try:
            result = future.result()
        
        except Exception as e:
            continue
        
        if not result: continue
        
        image, item = result
        items.append((image, item))
        print(f"{f'{index}/{len(plex_items)}':<15} Completed")
        index += 1

review_images(items)