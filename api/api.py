import json
import os

from fastapi import FastAPI, HTTPException

app = FastAPI()
DATA_DIR = "/app/data"


@app.get("/")
def read_root():
    return {"status": "ok", "service": "bvk-scraper-api"}


@app.get("/latest")
def get_latest():
    file_path = os.path.join(DATA_DIR, "latest.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="latest.json not found")

    try:
        with open(file_path) as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=500, detail="Error decoding latest.json") from err


@app.get("/history")
def get_history():
    file_path = os.path.join(DATA_DIR, "history.json")
    if not os.path.exists(file_path):
        return []  # Return empty list if no history yet

    try:
        with open(file_path) as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=500, detail="Error decoding history.json") from err


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
