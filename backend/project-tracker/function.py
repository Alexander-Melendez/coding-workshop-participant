"""AWS Lambda entry point.

Terraform deploys every folder under backend/ with `function.handler`
(infra/locals.tf), so the FastAPI app is wrapped here with Mangum, which
turns Lambda events into normal HTTP requests for FastAPI.
"""

from mangum import Mangum

from app import app

handler = Mangum(app, lifespan="off")
