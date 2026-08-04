# ============================================================
#  run_api.py — Start the FastAPI server
#  Command: python run_api.py
#  Docs:    http://127.0.0.1:8000/docs
# ============================================================

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host     = "0.0.0.0",
        port     = 8000,
        reload   = True,    # auto-restart on code changes
        log_level= "info",
    )