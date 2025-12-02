from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

# ========================
# Configurações
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))

# Inicializa o bot
app = ApplicationBuilder().token(BOT_TOKEN).build()

# ========================
# Comando /start
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bem-vindo!\n\n"
        "Este é um bot simples.\n"
        "Por enquanto, apenas o comando /start está disponível."
    )

# ========================
# Registro do handler
# ========================
app.add_handler(CommandHandler("start", start))

# ========================
# Webhook (Render)
# ========================
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/",
    )
