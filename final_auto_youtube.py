import os
import io
import random
import pickle
import datetime
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.auth.transport.requests import Request

# ================= CONFIG =================

DRIVE_FOLDER_ID = "1IyuR4KTZVJX80LsJlIxeJgKWe1EZFrNP"
UPLOADED_FOLDER_NAME = "Uploaded"
TIMEZONE_OFFSET = "+05:30"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive"
]

BEST_TIMINGS = {
    0: ["12:45", "20:15"],
    1: ["13:10", "21:05"],
    2: ["11:55", "20:40"],
    3: ["12:30", "21:20"],
    4: ["13:00", "21:45"],
    5: ["11:30", "22:15"],
    6: ["12:15", "20:50"],
}

# ===========================================


def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")


def authenticate():
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return creds


def get_services(creds):
    drive = build("drive", "v3", credentials=creds)
    youtube = build("youtube", "v3", credentials=creds)
    return drive, youtube


def get_uploaded_folder(drive):
    query = f"name='{UPLOADED_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder'"
    results = drive.files().list(q=query, fields="files(id,name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    folder = drive.files().create(
        body={
            "name": UPLOADED_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder"
        }
    ).execute()

    return folder["id"]


def get_all_videos(drive):
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType contains 'video/'"
    results = drive.files().list(q=query, fields="files(id,name)").execute()
    return results.get("files", [])


def download_video(drive, file_id, file_name):
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.close()


def move_to_uploaded(drive, file_id, uploaded_folder_id):
    file = drive.files().get(fileId=file_id, fields="parents").execute()
    parents = file.get("parents", [])

    if isinstance(parents, list):
        previous_parents = ",".join(parents)
    else:
        previous_parents = ""

    drive.files().update(
        fileId=file_id,
        addParents=uploaded_folder_id,
        removeParents=previous_parents
    ).execute()


def schedule_time(slot_time):
    now = datetime.datetime.now()
    hour, minute = map(int, slot_time.split(":"))

    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if scheduled <= now:
        scheduled += datetime.timedelta(days=1)

    return scheduled.isoformat() + TIMEZONE_OFFSET


def generate_title():
    hooks = [
        "🔥 This Hook Will Blow Up #shorts",
        "Stop Scrolling After This 😈 #shorts",
        "This Hook Changes Everything 🚀 #shorts",
        "Viral Hook You Need Today 🔥 #shorts",
        "This Opening Gets Views 😤 #shorts"
    ]
    return random.choice(hooks)


def upload_video(youtube, file_path, publish_time):
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": generate_title(),
                "description": "Daily high-retention hook content 🚀\n\n#shorts #viral #hooks",
                "tags": ["shorts", "viral", "hooks"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_time
            }
        },
        media_body=MediaFileUpload(file_path, resumable=True)
    )

    response = request.execute()
    return response["id"]


def main():
    try:
        log("Starting automation...")

        creds = authenticate()
        drive, youtube = get_services(creds)
        uploaded_folder_id = get_uploaded_folder(drive)

        today_index = datetime.datetime.now().weekday()
        slots = BEST_TIMINGS[today_index]

        all_videos = get_all_videos(drive)

        if len(all_videos) < len(slots):
            raise Exception("Not enough videos in Drive folder.")

        random.shuffle(all_videos)
        selected_videos = all_videos[:len(slots)]

        for slot, video in zip(slots, selected_videos):
            file_id = video["id"]
            file_name = video["name"]

            log(f"Selected: {file_name}")

            download_video(drive, file_id, file_name)

            publish_time = schedule_time(slot)
            video_id = upload_video(youtube, file_name, publish_time)

            log(f"Scheduled Video ID: {video_id} at {publish_time}")

            move_to_uploaded(drive, file_id, uploaded_folder_id)
            os.remove(file_name)

        log("✅ All videos scheduled successfully.")

    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
