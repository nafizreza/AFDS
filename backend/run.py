import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=os.getenv("AFDS_HOST", "127.0.0.1"),
        port=int(os.getenv("AFDS_PORT", "8000")),
        reload=os.getenv("AFDS_RELOAD", "0") == "1",
    )

