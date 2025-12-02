from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))

# ========================
# Estados do formulário
# ========================
CATEGORY, DESCRIPTION, PHOTO, LOCATION = range(4)

# Memória temporária de registros por chat
user_data_store = {}

# ========================
# Função que envia o menu
# ========================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="👋 Olá! Escolha uma opção:"):
    keyboard = [
        [InlineKeyboardButton("Registrar", callback_data="registrar")],
        [InlineKeyboardButton("Listar registros", callback_data="listar")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

# ========================
# /start
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context, "👋 Bem-vindo! Escolha uma opção:")

# ========================
# Callback dos botões
# ========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "registrar":
        await query.edit_message_text("📝 Qual categoria do registro?")
        return CATEGORY
    elif query.data == "listar":
        chat_id = query.message.chat_id
        registros = user_data_store.get(chat_id, [])
        if not registros:
            await query.edit_message_text("📋 Nenhum registro encontrado.")
        else:
            msg = "📋 Registros:\n\n"
            for i, r in enumerate(registros, 1):
                msg += f"{i}. Categoria: {r['categoria']}\n   Descrição: {r['descricao']}\n   Local: {r['local']}\n\n"
            await query.edit_message_text(msg)
        return ConversationHandler.END

# ========================
# Etapas do formulário
# ========================
async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registro'] = {}
    context.user_data['registro']['categoria'] = update.message.text
    await update.message.reply_text("✏️ Qual a descrição?")
    return DESCRIPTION

async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registro']['descricao'] = update.message.text
    await update.message.reply_text("📷 Envie uma foto (ou digite /skip se não quiser enviar).")
    return PHOTO

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data['registro']['photo_file_id'] = file.file_id
    await update.message.reply_text("📍 Onde ocorreu?")
    return LOCATION

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registro']['photo_file_id'] = None
    await update.message.reply_text("📍 Onde ocorreu?")
    return LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.user_data['registro']['local'] = update.message.text

    if chat_id not in user_data_store:
        user_data_store[chat_id] = []
    user_data_store[chat_id].append(context.user_data['registro'])

    await update.message.reply_text("✅ Registro salvo com sucesso!")
    context.user_data.clear()
    # Volta ao menu
    await send_menu(update, context)
    return ConversationHandler.END

# ========================
# Conversação
# ========================
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_callback)],
    states={
        CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_category)],
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        PHOTO: [
            MessageHandler(filters.PHOTO, ask_photo),
            CommandHandler("skip", skip_photo)
        ],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
    },
    fallbacks=[CommandHandler("skip", skip_photo)]
)

# ========================
# Responde qualquer texto com menu
# ========================
async def any_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context, "👋 Olá! Escolha uma opção:")

# ========================
# Registro do bot
# ========================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(button_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_text))  # qualquer mensagem exibe menu

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
