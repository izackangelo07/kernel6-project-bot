import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Pega o token do ambiente
TOKEN = os.environ.get("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Olá {update.effective_user.first_name}, eu sou seu bot!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponíveis:\n/start - iniciar o bot\n/help - ajuda")

async def main():
    # Cria a aplicação do bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Adiciona handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    print("Bot rodando...")
    # Run polling de forma assíncrona
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
