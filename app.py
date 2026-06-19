import os
import io
import base64
import httpx
import pillow_avif
from PIL import Image
from typing import List
from fastapi import FastAPI, Request, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from templates_config import templates
from dotenv import load_dotenv

load_dotenv()

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def render_home(request: Request):
    return templates.TemplateResponse(
        request=request, context={"sitekey": TURNSTILE_SITE_KEY}, name="index.html"
    )


@app.post("/convert")
async def process_images(
    files: List[UploadFile],
    quality: int = Form(70),
    cf_turnstile_response: str = Form(...),
):
    async with httpx.AsyncClient() as client:
        verify_response = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": cf_turnstile_response},
        )
        verify_result = verify_response.json()
        if not verify_result.get("success"):
            raise HTTPException(status_code=400, detail="Captcha verification failed")

    converted_data = []

    for file_item in files:
        file_content = await file_item.read()
        image_obj = Image.open(io.BytesIO(file_content))

        if image_obj.mode in ("RGBA", "P", "LA"):
            image_obj = image_obj.convert("RGB")
        else:
            image_obj = image_obj.convert("RGB")

        output_buffer = io.BytesIO()
        image_obj.save(output_buffer, format="JPEG", quality=quality)
        output_buffer.seek(0)

        base64_encoded = base64.b64encode(output_buffer.read()).decode("utf-8")

        filename_parts = file_item.filename.rsplit(".", 1)  # type: ignore
        new_filename = (
            f"{filename_parts[0]}.jpg"
            if len(filename_parts) > 1
            else f"{file_item.filename}.jpg"
        )

        converted_data.append({"filename": new_filename, "data": base64_encoded})

    return {"images": converted_data}
