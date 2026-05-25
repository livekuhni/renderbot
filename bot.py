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

SYSTEM_PROMPT = """You are an expert interior designer and architectural photographer. 
Analyze the 3D render from Pro100 furniture design software and create a detailed prompt 
for DALL-E 3 to generate a photorealistic version of the EXACT SAME room.

Your prompt must:
1. Describe the exact room layout, furniture positions and configuration
2. Describe every piece of furniture with exact colors and materials
3. Specify realistic lighting (natural daylight, shadows)
4. Include photorealistic materials (wood grain, fabric texture, metal, glass)  
5. Mention professional interior photography style, 8k resolution
6. Keep the SAME viewpoint/angle as the original render

Return ONLY the prompt text in English, 150-200 words. Nothing else."""

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
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                        }
                    ]
                }]
            }
        )
        data = response.json()
        logger.info(f"GPT response: {data}")
        return data["choices"][0]["message"]["content"]

async def generate_with_dalle(prompt: str) -> str:
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
                "style": "natural"
            }
        )
        data = response.json()
        logger.info(f"DALL-E response: {data}")
        return data["data"][0]["url"]

async def process_image(update: Update, image_bytes: bytearray, msg):
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    await msg.edit_text("🔍 Анализирую рендер...")
    prompt = await analyze_with_gpt4(image_base64)
    logger.info(f"Промпт: {prompt}")
    
    await msg.edit_text("🎨 Генерирую фотореалистичную версию... (~30 сек)")
    image_url = await generate_with_dalle(prompt)
    
    await msg.edit_text("✅ Готово!")
    await update.message.reply_photo(
        photo=image_url,
        caption="🏠 Фотореалистичный рендер готов!"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь рендер из Pro100 — GPT-4o проанализирует его и DALL-E создаст фотореалистичную версию.\n\n"
        "📤 Отправь фото — результат через ~40 секунд."
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
