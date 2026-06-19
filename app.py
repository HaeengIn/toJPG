import base64
import io
import os
import time
from typing import List

import httpx
import pillow_avif
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from PIL import Image
from dotenv import load_dotenv

from templates_config import templates

load_dotenv()

BASE_DIR = os.path.dirname(__file__)
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-please")
MAX_UPLOAD_FILES = 200
MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CAPTCHA_VALID_SECONDS = 60 * 60
if not TURNSTILE_SITE_KEY or not TURNSTILE_SECRET_KEY:
    raise RuntimeError(
        "TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY must be set in the environment."
    )

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        request=request, context={"sitekey": TURNSTILE_SITE_KEY}, name="index.html"
    )


@app.post("/convert")
async def process_images(
    request: Request,
    files: List[UploadFile],
    quality: int = Form(70),
    cf_turnstile_response: str | None = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No images were uploaded.")

    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"최대 업로드 개수는 {MAX_UPLOAD_FILES}개입니다. 선택한 파일 수: {len(files)}",
        )

    session = request.session
    verified_at = session.get("captcha_verified_at")
    if verified_at is None or time.time() - verified_at > CAPTCHA_VALID_SECONDS:
        if not cf_turnstile_response:
            raise HTTPException(status_code=400, detail="Captcha verification failed.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            verify_response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": cf_turnstile_response,
                },
            )
            verify_response.raise_for_status()
            verify_result = verify_response.json()
            if not verify_result.get("success"):
                raise HTTPException(
                    status_code=400, detail="Captcha verification failed."
                )

        session["captcha_verified_at"] = int(time.time())

    converted_data = []
    for upload_file in files:
        file_bytes = await upload_file.read()
        if len(file_bytes) > MAX_UPLOAD_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"파일 {upload_file.filename}의 크기가 너무 큽니다. 최대 업로드 크기는 {MAX_UPLOAD_FILE_SIZE // (1024*1024)}MB입니다.",
            )

        try:
            with Image.open(io.BytesIO(file_bytes)) as image_obj:
                image_obj = image_obj.convert("RGB")
                output_buffer = io.BytesIO()
                image_obj.save(output_buffer, format="JPEG", quality=quality)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process file {upload_file.filename}: {exc}",
            )

        output_buffer.seek(0)
        base64_encoded = base64.b64encode(output_buffer.read()).decode("utf-8")
        filename_base = (
            upload_file.filename.rsplit(".", 1)[0]  # type: ignore
            if "." in upload_file.filename  # type: ignore
            else upload_file.filename
        )
        converted_data.append(
            {"filename": f"{filename_base}.jpg", "data": base64_encoded}
        )

    return {"images": converted_data}
