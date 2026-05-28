
import os
import logging
import asyncio
import httpx
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
 
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)
 
ANALYSIS_PROMPT = """Analyze this 3D kitchen render from PRO100 software in detail.
Describe precisely:
1. Exact cabinet layout, positions and dimensions
2. All facade colors, materials and finishes
3. Appliances positions (oven, hob, hood, fridge)
4. Hardware (handles, hinges) style and color
5. Countertop material and color
6. Backsplash style
7. Room dimensions and camera angle
8. Any unique design elements
 
Return ONLY a detailed description in English, 200 words max."""
 
DALLE_PROMPT_TEMPLATE = """Photorealistic kitchen visualization based on this layout: {description}
 
Requirements:
- Fully preserve the original layout, cabinet positions, facades and appliances from the source image
- Realistic backsplash (tile) with correct scale
- Metal hardware with soft reflections (handles, hinges, appliances)
- Built-in appliances look real (oven, hob, hood)
 
Lighting:
- Natural daylight from window
- Soft LED underlighting of work zone under upper cabinets
- Realistic shadows and reflections
- Global illumination, no overexposure or flat lighting
 
Camera:
- 24-30mm focal length
- Correct perspective without distortion
- Camera at human eye level
- Sharp geometry without distortion
 
Detail:
- Sharp edges, gaps between facades
- Slight surface imperfection (microtexture)
- Neat but "lived-in" kitchen (minimal decor)
 
Final result:
- Maximum photorealism
- Modern, premium look
- Image looks like a photo from a premium kitchen showroom
- Ultra quality, photorealistic render"""
 
async def analyze_with_gpt4(image_base64: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                        {"type": "text", "text": ANALYSIS_PROMPT}
                    ]
                }]
            }
        )
        data = response.json()
        logger.info(f"GPT4 response: {data}")
        if "error" in data:
            raise Exception(f"GPT-4o ошибка: {data['error']['message']}")
        return data["choices"][0]["message"]["content"]
 
async def generate_with_dalle(description: str) -> str:
    prompt = DALLE_PROMPT_TEMPLATE.format(description=description)
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
            }
        )
        data = response.json()
        logger.info(f"DALLE response: {data}")
        if "error" in data:
            raise Exception(f"DALL-E ошибка: {data['error']['message']}")
        return data["data"][0]["url"]
 
async def process_image(update: Update, image_bytes: bytearray, msg):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    await msg.edit_text("🔍 GPT-4o анализирует планировку кухни...")
    description = await analyze_with_gpt4(image_base64)
    logger.info(f"Описание: {description}")
    await msg.edit_text("🎨 DALL-E 3 генерирует фотореалистичную версию... (~30 сек)")
    image_url = await generate_with_dalle(description)
    await msg.edit_text("✅ Готово!")
    await update.message.reply_photo(
        photo=image_url,
        caption="🏠 Фотореалистичный рендер кухни готов!"
    )
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь рендер кухни из Pro100.\n\n"
        "🔍 GPT-4o проанализирует планировку\n"
        "🎨 DALL-E 3 создаст фотореалистичную версию\n\n"
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
