import base64
import io
import json
import os
import time
from typing import List

import httpx
import pillow_avif
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
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
JPG_BACKGROUND_COLOR = (0, 0, 0)
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


def image_has_transparent_area(image_obj: Image.Image) -> bool:
    has_alpha = image_obj.mode in ("RGBA", "LA") or (
        image_obj.mode == "P" and "transparency" in image_obj.info
    )
    if not has_alpha:
        return False

    alpha_channel = image_obj.convert("RGBA").getchannel("A")
    min_alpha, _ = alpha_channel.getextrema()
    return min_alpha < 255


def convert_to_jpg_ready_image(image_obj: Image.Image) -> Image.Image:
    if not image_has_transparent_area(image_obj):
        return image_obj.convert("RGB")

    rgba_image = image_obj.convert("RGBA")
    background_image = Image.new(
        "RGBA", rgba_image.size, JPG_BACKGROUND_COLOR + (255,)
    )
    background_image.alpha_composite(rgba_image)
    return background_image.convert("RGB")


def build_progress_event(event_name: str, data: dict) -> str:
    return json.dumps({"event": event_name, **data}, ensure_ascii=False) + "\n"


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

    async def convert_stream():
        converted_data = []
        total_files = len(files)

        for file_index, upload_file in enumerate(files):
            original_filename = upload_file.filename or "image"
            yield build_progress_event(
                "progress",
                {
                    "currentFile": original_filename,
                    "currentProgress": 0,
                    "totalProgress": (file_index / total_files) * 100,
                },
            )

            file_bytes = await upload_file.read()
            if len(file_bytes) > MAX_UPLOAD_FILE_SIZE:
                yield build_progress_event(
                    "error",
                    {
                        "message": f"파일 {original_filename}의 크기가 너무 큽니다. 최대 업로드 크기는 {MAX_UPLOAD_FILE_SIZE // (1024*1024)}MB입니다."
                    },
                )
                return

            try:
                with Image.open(io.BytesIO(file_bytes)) as image_obj:
                    image_obj = convert_to_jpg_ready_image(image_obj)
                    yield build_progress_event(
                        "progress",
                        {
                            "currentFile": original_filename,
                            "currentProgress": 50,
                            "totalProgress": ((file_index + 0.5) / total_files) * 100,
                        },
                    )
                    output_buffer = io.BytesIO()
                    image_obj.save(output_buffer, format="JPEG", quality=quality)
            except Exception as exc:
                yield build_progress_event(
                    "error",
                    {"message": f"Failed to process file {original_filename}: {exc}"},
                )
                return

            output_buffer.seek(0)
            base64_encoded = base64.b64encode(output_buffer.read()).decode("utf-8")
            filename_base = (
                original_filename.rsplit(".", 1)[0]
                if "." in original_filename
                else original_filename
            )
            converted_data.append(
                {"filename": f"{filename_base}.jpg", "data": base64_encoded}
            )
            yield build_progress_event(
                "progress",
                {
                    "currentFile": original_filename,
                    "currentProgress": 100,
                    "totalProgress": ((file_index + 1) / total_files) * 100,
                },
            )

        yield build_progress_event("complete", {"images": converted_data})

    return StreamingResponse(convert_stream(), media_type="application/x-ndjson")
