import subprocess, sys, os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BACKEND_DIR, "web_backend.log")


def main():
    # Detached + no-window: API runs independently of this launcher / the .bat window.
    # Output (uvicorn logs) redirected to web_backend.log for diagnostics.
    with open(LOG_PATH, "w", encoding="utf-8") as logf:
        subprocess.Popen(
            [sys.executable, "api_main.py", "--lan"],
            cwd=BACKEND_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            creationflags=0x00000008 | 0x08000000,  # DETACHED_PROCESS | CREATE_NO_WINDOW
        )
    print("API launched (detached). See web/backend/web_backend.log")


if __name__ == "__main__":
    main()
