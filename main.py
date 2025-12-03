from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler, 
    ConversationHandler,
    ContextTypes, 
    filters
)
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))

# Estados do ConversationHandler
CATEGORIA, DESCRICAO, PHOTO, LOCATION = range(4)

# Banco de dados simples em memória
user_data_store = {}


# ============================================================
# 🧩 MENU PRINCIPAL (mostrado sempre)
# ============================================================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Registrar problema", callback_data="registrar")],
        [InlineKeyboardButton("📋 Listar registros", callback_data="listar")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "👋 *Bem-vindo ao Kernel6 Project!*\n"
            "Ajude a melhorar nossa comunidade...\n\n"
            "Escolha uma opção:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "👋 *Bem-vindo ao Kernel6 Project!*\n"
            "Ajude a melhorar nossa comunidade...\n\n"
            "Escolha uma opção:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)


# ============================================================
# MENU AUTOMÁTICO SEM COMANDO
# ============================================================
async def auto_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)


# ============================================================
# CALLBACKS DO MENU
# ============================================================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # -----------------------------
    # iniciar registro
    # -----------------------------
    if query.data == "registrar":
        categorias = [
            "Iluminação pública",
            "Limpeza urbana",
            "Buraco na rua",
            "Áreas verdes / Praças",
            "Escola / Creche",
            "Segurança",
            "Outro"
        ]

        botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
                  for cat in categorias]

        await query.edit_message_text(
            "📝 Qual categoria do registro?",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return CATEGORIA

    # -----------------------------
    # listar registros
    # -----------------------------
    elif query.data == "listar":
        chat_id = query.message.chat_id
        registros = user_data_store.get(chat_id, [])

        if not registros:
            await query.edit_message_text("📋 Nenhum registro encontrado.")
        else:
            msg = "📋 *Registros:*\n\n"
            for i, r in enumerate(registros, 1):
                msg += f"{i}. Categoria: {r['categoria']}\n"
                msg += f"   Descrição: {r['descricao']}\n"
                msg += f"   Local: {r['local']}\n\n"

            await query.edit_message_text(msg, parse_mode="Markdown")

        # voltar para o menu
        await send_menu(update, context)
        return ConversationHandler.END


# ============================================================
# ETAPA 1 — CATEGORIA
# ============================================================
async def escolher_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    categoria = query.data.replace("cat:", "")
    context.user_data["registro"] = {"categoria": categoria}

    await query.edit_message_text("Descreva o problema.")
    return DESCRICAO


# ============================================================
# ETAPA 2 — DESCRIÇÃO
# ============================================================
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["registro"]["descricao"] = update.message.text

    keyboard = [
        [
            InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
            InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")
        ]
    ]

    await update.message.reply_text(
        "Deseja enviar uma foto?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PHOTO


# ============================================================
# ETAPA 3 — FOTO
# ============================================================
async def photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "skip_file":
        context.user_data["registro"]["photo_file_id"] = None
        await query.edit_message_text("Onde fica o problema?")
        return LOCATION

    if query.data == "add_file":
        await query.edit_message_text("📷 Envie a foto agora.")
        return PHOTO


async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # recebeu foto = ok
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data["registro"]["photo_file_id"] = file.file_id

        await update.message.reply_text("Onde fica o problema?")
        return LOCATION

    # enviaram texto = erro
    await update.message.reply_text(
        "⚠️ Por favor, envie *uma foto* ou clique em *Pular*.",
        parse_mode="Markdown"
    )
    return PHOTO


# ============================================================
# ETAPA 4 — LOCAL
# ============================================================
async def receber_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    local = update.message.text
    context.user_data["registro"]["local"] = local

    chat_id = update.effective_chat.id

    if chat_id not in user_data_store:
        user_data_store[chat_id] = []

    user_data_store[chat_id].append(context.user_data["registro"])

    await update.message.reply_text("✅ Registro salvo com sucesso!")

    # volta ao menu
    await send_menu(update, context)
    return ConversationHandler.END


# ============================================================
# HANDLER PRINCIPAL DE REGISTRO
# ============================================================
registrar_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(menu_callback, pattern="^(registrar|listar)$")],

    states={
        CATEGORIA: [CallbackQueryHandler(escolher_categoria, pattern="^cat:")],
        DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
        PHOTO: [
            CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file)$"),
            MessageHandler(filters.PHOTO, receber_foto),
            MessageHandler(filters.TEXT, receber_foto)
        ],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_local)],
    },

    fallbacks=[]
)


# ============================================================
# APP / WEBHOOK
# ============================================================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(registrar_handler)

# qualquer "oi", "bom dia", etc → abre menu
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))

app.add_handler(CallbackQueryHandler(menu_callback))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/",
    )
