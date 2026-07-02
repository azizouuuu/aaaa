import uvicorn

from . import config

uvicorn.run("app.main:app", host="127.0.0.1", port=config.PORT)
