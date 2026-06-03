from mangum import Mangum

from web.app import app

# AWS Lambda entrypoint (Function URL events). Mangum adapts ASGI <-> Lambda.
handler = Mangum(app, lifespan="off")
