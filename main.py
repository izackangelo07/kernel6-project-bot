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
# Menu inicial
# ========================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="👋 Olá! Escolha uma opção:"):
    keyboard = [
        [InlineKeyboardButton("Registrar", callback_data="registrar")],
        [InlineKeyboardButton("Listar registros", callback_data="listar")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

# ========================
# /start
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bem-vindo ao Kernel6 Project!\n"
        "Ajude a melhorar nossa comunidade...\n"
        "Escolha uma opção:"
    )
    await send_menu(update, context)

# ========================
# Callback do menu principal
# ========================
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "registrar":
        # Botões de categoria
        keyboard = [
            [InlineKeyboardButton("Iluminação pública", callback_data="Iluminação pública")],
            [InlineKeyboardButton("Limpeza urbana", callback_data="Limpeza urbana")],
            [InlineKeyboardButton("Buraco na rua", callback_data="Buraco na rua")],
            [InlineKeyboardButton("Áreas verdes / Praças", callback_data="Áreas verdes / Praças")],
            [InlineKeyboardButton("Escola / Creche", callback_data="Escola / Creche")],
            [InlineKeyboardButton("Segurança", callback_data="Segurança")],
            [InlineKeyboardButton("Outro", callback_data="Outro")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📝 Qual categoria do registro?", reply_markup=reply_markup)
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
# Formulário
# ========================
async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['registro'] = {}
    context.user_data['registro']['categoria'] = query.data
    await query.edit_message_text("Descreva o problema.")
    return DESCRIPTION

async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registro']['descricao'] = update.message.text
    # Botões para foto
    keyboard = [
        [InlineKeyboardButton("Adicionar arquivo", callback_data="add_file")],
        [InlineKeyboardButton("Pular", callback_data="skip_file")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📷 Deseja adicionar uma foto?", reply_markup=reply_markup)
    return PHOTO

async def photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "skip_file":
        context.user_data['registro']['photo_file_id'] = None
        await query.edit_message_text("Onde fica o problema?")
        return LOCATION
    elif query.data == "add_file":
        await query.edit_message_text("📷 Envie a foto agora.")
        return PHOTO

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data['registro']['photo_file_id'] = file.file_id
        await update.message.reply_text("Onde fica o problema?")
        return LOCATION
    else:
        await update.message.reply_text("Por favor, envie uma foto válida ou clique em 'Pular'.")
        return PHOTO

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.user_data['registro']['local'] = update.message.text

    if chat_id not in user_data_store:
        user_data_store[chat_id] = []
    user_data_store[chat_id].append(context.user_data['registro'])

    await update.message.reply_text("✅ Registro salvo com sucesso!")
    context.user_data.clear()
    await send_menu(update, context)
    return ConversationHandler.END

# ========================
# Conversação
# ========================
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(main_menu_callback, pattern="^(registrar|listar)$")],
    states={
        CATEGORY: [CallbackQueryHandler(ask_category)],  # botões categoria
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        PHOTO: [
            CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file)$"),
            MessageHandler(filters.PHOTO, ask_photo)
        ],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
    },
    fallbacks=[]
)

# ========================
# Qualquer texto exibe menu
# ========================
async def any_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)

# ========================
# Registro do bot
# ========================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_text))

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
