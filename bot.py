import os
import logging
import asyncio
import httpx
import base64
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
 
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)
 
EDIT_PROMPT = (
    "Transform this 3D furniture render into a photorealistic interior photo. "
    "Keep EXACTLY the same layout, furniture positions, colors, materials as in the original image. "
    "Make all surfaces photorealistic: wood grain, matte/gloss finishes, metal, glass, stone, fabric. "
    "Realistic backwall/backsplash with correct scale and texture. "
    "Chrome/metal hardware with natural reflections. "
    "All built-in elements and appliances look like real branded products. "
    "Natural daylight from window with soft shadows. "
    "Warm LED strip lighting if present in original. "
    "Realistic ambient light, no harsh overexposure. "
    "Same angle and perspective as original. 24-28mm focal length, eye level. "
    "Add minimal tasteful decor if appropriate. "
    "Ultra photorealistic, looks like professional interior photography for premium furniture catalog. "
    "Same furniture and layout, just photorealistic."
)
 
async def edit_with_gpt4o(image_bytes: bytearray) -> bytes:
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"image": ("image.png", bytes(image_bytes), "image/png")},
            data={
                "model": "gpt-image-1",
                "prompt": EDIT_PROMPT,
                "n": "1",
                "size": "1536x1024",
                "quality": "medium"
            }
        )
        data = response.json()
        logger.info(f"Response: {list(data.keys())}")
        if "error" in data:
            raise Exception(f"Ошибка: {data['error']['message']}")
        item = data["data"][0]
        if "b64_json" in item:
            return base64.b64decode(item["b64_json"])
        elif "url" in item:
            img_resp = await client.get(item["url"])
            return img_resp.content
        else:
            raise Exception(f"Неизвестный формат: {list(item.keys())}")
 
async def process_image(update: Update, image_bytes: bytearray, msg):
    await msg.edit_text("Генерирую фотореалистичную версию... Подожди 2-3 минуты!")
    image_data = await edit_with_gpt4o(image_bytes)
    await msg.edit_text("Готово!")
    await update.message.reply_photo(
        photo=io.BytesIO(image_data),
        caption="Фотореалистичный рендер готов!"
    )
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь рендер из Pro100.\n\n"
        "ИИ сделает фотореалистичную версию.\n\n"
        "Просто отправь фото - результат через 2-3 минуты."
    )
 
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Получил рендер, обрабатываю...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        await process_image(update, image_bytes, msg)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await msg.edit_text(f"Ошибка: {str(e)}\n\nПопробуй ещё раз.")
 
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        msg = await update.message.reply_text("Получил файл, обрабатываю...")
        try:
            file = await context.bot.get_file(doc.file_id)
            image_bytes = await file.download_as_bytearray()
            await process_image(update, image_bytes, msg)
        except Exception as e:
            await msg.edit_text(f"Ошибка: {str(e)}")
    else:
        await update.message.reply_text("Отправь изображение PNG или JPG.")
 
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    logger.info("Бот запущен!")
    app.run_polling()
 
if __name__ == "__main__":
    main()
