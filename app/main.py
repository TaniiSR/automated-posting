from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.platforms.registry import all_platforms
from app.schemas import PostingRequest, PostingResponse
from app.services.posting_service import PostingService

app = FastAPI(
    title="Automated Posting",
    description="Publishes one short message with a CTA link to several platforms.",
)


def get_service() -> PostingService:
    return PostingService(all_platforms())


@app.post("/posting", response_model=PostingResponse)
async def posting(
    request: PostingRequest, service: PostingService = Depends(get_service)
) -> PostingResponse:
    return await service.publish(request.message, request.url)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part != "body"]
        message = error["msg"].removeprefix("Value error, ")
        errors.append({"field": ".".join(location) or "body", "message": message})
    return JSONResponse(status_code=422, content={"success": False, "errors": errors})
