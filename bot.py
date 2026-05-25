import os
import logging
import asyncio
import httpx
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
REPLICATE_TOKEN = os.environ["REPLICATE_API_TOKEN"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

async def generate_realistic(image_base64: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.replicate.com/v1/models/stability-ai/stable-diffusion-img2img/predictions",
            headers={
                "Authorization": f"Bearer {REPLICATE_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "input": {
                    "image": f"data:image/jpeg;base64,{image_base64}",
                    "prompt": "photorealistic kitchen interior, professional photography, 8k resolution, natural lighting, realistic wood cabinets, realistic countertops, same room layout and furniture positions",
                    "negative_prompt": "cartoon, 3d render, cgi, illustration, drawing, blurry, low quality, deformed",
                    "guidance_scale": 12,
                    "num_inference_steps": 50,
                    "strength": 0.45,
                    "scheduler": "DPMSolverMultistep"
                }
            }
        )
        prediction = response.json()
        logger.info(f"Response: {prediction}")
        prediction_id = prediction.get("id")

        if not prediction_id:
            raise Exception(f"Ошибка запуска: {prediction}")

        for _ in range(60):
            await asyncio.sleep(3)
            async with httpx.AsyncClient(timeout=30) as poll_client:
                poll = await poll_client.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers={"Authorization": f"Bearer {REPLICATE_TOKEN}"}
                )
                result = poll.json()
                status = result.get("status")
                logger.info(f"Status: {status}")

                if status == "succeeded":
                    output = result.get("output")
                    return output[0] if isinstance(output, list) else output
                elif status == "failed":
                    raise Exception(f"Ошибка: {result.get('error')}")

        raise Exception("Превышено время ожидания")

async def process_image(update: Update, image_bytes: bytearray, msg):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    await msg.edit_text("🎨 Делаю фотореалистичным... (~60 сек)")
    image_url = await generate_realistic(image_base64)
    await msg.edit_text("✅ Готово!")
    await update.message.reply_photo(
        photo=image_url,
        caption="🏠 Фотореалистичный рендер готов!"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь рендер из Pro100 — сделаю фотореалистичным.\n\n"
        "📤 Отправь фото — результат через ~60 секунд."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Получил рендер, обрабатываю...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        await process_image(update, image_bytes, msg)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await msg.edit_text(f"❌ Ошибка: {str(e)}\n\nПопробуй ещё раз.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        msg = await update.message.reply_text("⏳ Получил файл, обрабатываю...")
        try:
            file = await context.bot.get_file(doc.file_id)
            image_bytes = await file.download_as_bytearray()
            await process_image(update, image_bytes, msg)
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка: {str(e)}")
    else:
        await update.message.reply_text("⚠️ Отправь изображение PNG или JPG.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
    
