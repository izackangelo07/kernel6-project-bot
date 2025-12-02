import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Pega o token do ambiente seguro
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Olá {update.effective_user.first_name}, eu sou seu bot!")

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponíveis:\n/start - iniciar o bot\n/help - ajuda")

# Inicializa o bot
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    print("Bot rodando...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
