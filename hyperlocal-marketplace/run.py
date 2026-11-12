"""Start the prototype:  python run.py   then open http://127.0.0.1:8000"""
import threading
import webbrowser

import uvicorn

HOST, PORT = "127.0.0.1", 8000

if __name__ == "__main__":
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")
