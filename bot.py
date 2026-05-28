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
 
EDIT_PROMPT = """Based on the uploaded PRO100 image, create a photorealistic visualization of the kitchen, fully preserving the dimensions, layout, facades, appliance placement and modules.
 
Materials and furniture:
- Realistic kitchen facades with correct textures and finishes
- Correct countertop texture and realistic backsplash with proper scale
- Metal hardware with soft reflections (handles, hinges, appliances)
- Built-in appliances look real (oven, hob, hood)
- Handles must be EXACTLY in the same position and EXACTLY the same shape as in the original image
 
Lighting:
- Natural daylight from window
- Soft LED underlighting of work zone under upper cabinets (if present in original)
- Realistic shadows and reflections
- Global illumination, no overexposure or flat lighting
 
Camera:
- 24-30mm focal length
- Correct perspective without distortion or tilt
- Camera at human eye level
- Sharp geometry without distortions
 
Detail:
- Sharp edges, visible gaps between facades
- Slight surface imperfection (microtexture)
- Neat but lived-in kitchen (add tasteful decor: small plant, fruit bowl, or cutting board)
 
Final:
- Maximum photorealism
- Modern, premium expensive look
- Image looks like a photo from a premium kitchen showroom
- Ultra quality, photorealistic render
- IMPORTANT: Keep EXACTLY the same layout, cabinet count, colors and proportions as the original"""
 
async def edit_with_gpt4o(image_bytes: bytearray) -> bytes:
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={
                "image": ("image.png", bytes(image_bytes), "image/png"),
            },
            data={
                "model": "gpt-image-1",
                "prompt": EDIT_PROMPT,
                "n": "1",
                "size": "1024x1024",
                "quality": "high"
            }
        )
        data = response.json()
        logger.info(f"Edit response: {data}")
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
    await msg.edit_text("🎨 GPT-4o делает фотореалистичную версию...
⏳ Это занимает 2-3 минуты, пожалуйста подожди!")
    image_data = await edit_with_gpt4o(image_bytes)
    await msg.edit_text("✅ Готово!")
    await update.message.reply_photo(
        photo=io.BytesIO(image_data),
        caption="🏠 Фотореалистичный рендер кухни готов!"
    )
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь рендер кухни из Pro100.\n\n"
        "🎨 GPT-4o сделает фотореалистичную версию сохранив планировку\n\n"
        "📤 Просто отправь фото — результат через ~40 секунд."
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
