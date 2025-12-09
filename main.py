# main.py
import os
import json
import logging
from datetime import datetime, timedelta
import uuid
import requests

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

# ---------- Config logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------- Env vars ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")
GIST_FILENAME = os.getenv("GIST_FILENAME", "registros.json")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN não definido")
if not GIST_TOKEN:
    logger.error("GIST_TOKEN não definido")
if not GIST_ID:
    logger.error("GIST_ID não definido")

# ---------- Conversation states ----------
CATEGORIA, TITULO, DESCRICAO, PHOTO, LOCATION, CONFIRMACAO = range(6)
DELETE_PASSWORD, DELETE_CHOOSE, DELETE_CONFIRM = range(6, 9)

# ---------- Constants ----------
STATUS_PENDENTE = "pendente"
ADMIN_PASSWORD = "12345678"

CATEGORIAS = [
    "Iluminação pública",
    "Limpeza urbana",
    "Buraco na rua",
    "Áreas verdes / Praças",
    "Escola / Creche",
    "Segurança",
    "Outro"
]

# ---------- Store ----------
problemas_store = []

# ---------- Gist ----------
GIST_API_BASE = "https://api.github.com/gists"

def gist_headers():
    return {"Authorization": f"token {GIST_TOKEN}", "Accept": "application/vnd.github+json"}

def load_from_gist():
    global problemas_store
    try:
        resp = requests.get(f"{GIST_API_BASE}/{GIST_ID}", headers=gist_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        files = data.get("files", {})
        if GIST_FILENAME in files:
            raw = files[GIST_FILENAME].get("content", "[]")
            try:
                problemas_store = json.loads(raw)
                logger.info("Dados carregados do gist com sucesso (%d registros)", len(problemas_store))
            except Exception as e:
                logger.error("Erro ao desserializar conteúdo do gist: %s", e)
                problemas_store = []
        else:
            problemas_store = []
            save_to_gist()
    except Exception as e:
        logger.warning("Não foi possível carregar Gist: %s", e)
        problemas_store = []

def save_to_gist():
    try:
        content = json.dumps(problemas_store, ensure_ascii=False, indent=2)
        payload = {"files": {GIST_FILENAME: {"content": content}}}
        resp = requests.patch(f"{GIST_API_BASE}/{GIST_ID}", headers=gist_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Gist atualizado com sucesso")
        return True
    except Exception as e:
        logger.error("Erro ao atualizar gist: %s", e)
        return False


# ---------- Util ----------
def get_brasilia_time():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

def get_uuid():
    return str(uuid.uuid4())

def format_status(status):
    mapa = {
        "pendente": "⏳ Pendente",
        "aprovado": "✅ Aprovado",
        "em_analise": "🔍 Em análise",
        "rejeitado": "❌ Rejeitado"
    }
    return mapa.get(status, status)


# ---------- Menu ----------
async def send_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📝 Registrar problema", callback_data="registrar")],
        [InlineKeyboardButton("📋 Listar registros", callback_data="listar")],
        [InlineKeyboardButton("🗑 Deletar registros", callback_data="delete_menu")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="ajuda")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # get chat safely
    chat = None
    if update.message and update.message.chat:
        chat = update.message.chat
    elif update.callback_query and update.callback_query.message:
        chat = update.callback_query.message.chat

    if chat:
        await context.bot.send_message(
            chat_id=chat.id,
            text="👋 *Bem-vindo ao Kernel6 Project!*\nEscolha uma opção:",
            parse_mode="Markdown",
            reply_markup=markup
        )


# ---------- START ----------
async def start(update, context):
    await send_menu(update, context)


# ---------- AJUDA ----------
async def ajuda(update, context):
    txt = (
        "🤖 *Ajuda*\n\n"
        "/start - Menu\n"
        "/registrar - Registrar problema (também pelo botão)\n"
        "/listar - Listar registros\n"
        "/deletar - Excluir registro (senha)"
    )
    if update.message:
        await update.message.reply_text(txt, parse_mode="Markdown")
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(txt, parse_mode="Markdown")
    await send_menu(update, context)


# ---------- Registrar via comando (opcional) ----------
async def registrar_command(update, context):
    chat_id = update.effective_chat.id
    botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIAS]
    await context.bot.send_message(chat_id=chat_id, text="📝 Qual categoria do problema?", reply_markup=InlineKeyboardMarkup(botoes))
    return CATEGORIA


# ---------- Menu callback (botões principais) ----------
async def menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat = query.message.chat
    chat_id = chat.id

    if data == "registrar":
        # send category buttons
        botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIAS]
        await context.bot.send_message(chat_id=chat_id, text="📝 Qual categoria do problema?", reply_markup=InlineKeyboardMarkup(botoes))
        return CATEGORIA

    elif data == "listar":
        if not problemas_store:
            await context.bot.send_message(chat_id, "📋 Nenhum problema registrado ainda.")
        else:
            problemas_ordenados = sorted(problemas_store, key=lambda x: x.get("created_at", ""), reverse=True)
            for i, p in enumerate(problemas_ordenados, 1):
                texto = (
                    f"*{i}. {p.get('categoria','-')}*\n"
                    f"📝 *Título:* {p.get('titulo','-')}\n"
                    f"📄 *Descrição:* {p.get('descricao','-')}\n"
                    f"📍 *Local:* {p.get('descricao_local','-')}\n"
                    f"📅 *Criado:* {p.get('created_at_formatted','-')}\n"
                    f"📊 *Status:* {format_status(p.get('status',''))}\n"
                )
                if p.get("photo_file_id"):
                    try:
                        await context.bot.send_photo(chat_id=chat_id, photo=p["photo_file_id"], caption=texto, parse_mode="Markdown")
                    except Exception as e:
                        logger.warning("Erro ao enviar foto no listar (fallback texto): %s", e)
                        await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        await send_menu(update, context)
        return ConversationHandler.END

    elif data == "delete_menu":
        # start delete flow via callback
        # ask for password (use same handler as deletar_command)
        await context.bot.send_message(chat_id=chat_id, text="🔐 Digite a senha de administrador:")
        return DELETE_PASSWORD

    elif data == "ajuda":
        await ajuda(update, context)
        return ConversationHandler.END

    return ConversationHandler.END


# =========================
# Registrar flow handlers
# =========================
async def escolher_categoria(update, context):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    categoria = query.data.replace("cat:", "")
    context.user_data["problema"] = {"categoria": categoria, "status": STATUS_PENDENTE}
    await context.bot.send_message(chat.id, "📝 *Forneça um título para o problema:*\nEx: \"Poste de luz quebrado na Rua X\"", parse_mode="Markdown")
    return TITULO


async def receber_titulo(update, context):
    titulo = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    if len(titulo) < 3:
        await update.message.reply_text("⚠️ Título muito curto. Informe algo mais descritivo.")
        return TITULO
    if len(titulo) > 100:
        await update.message.reply_text("⚠️ Título muito longo. Max 100 caracteres.")
        return TITULO
    context.user_data["problema"]["titulo"] = titulo
    await context.bot.send_message(chat_id, "📝 *Agora, descreva o problema com detalhes:*", parse_mode="Markdown")
    return DESCRICAO


async def receber_descricao(update, context):
    descricao = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    if len(descricao) < 10:
        await update.message.reply_text("⚠️ Descrição muito curta. Informe mais detalhes.")
        return DESCRICAO
    context.user_data["problema"]["descricao"] = descricao

    keyboard = [
        [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
         InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")]
    ]
    await context.bot.send_message(chat_id, "📸 *Deseja enviar uma foto do problema?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return PHOTO


async def photo_choice(update, context):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    chat_id = chat.id

    if query.data == "skip_file":
        context.user_data["problema"]["photo_file_id"] = None
        await context.bot.send_message(chat_id, "📍 *Onde fica o problema?* Forneça endereço ou referência.", parse_mode="Markdown")
        return LOCATION

    if query.data == "add_file":
        await context.bot.send_message(chat_id, "📸 *Envie a foto agora.* Por favor, envie uma foto clara do problema.", parse_mode="Markdown")
        return PHOTO


async def receber_foto(update, context):
    chat_id = update.effective_chat.id

    # se foto
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data["problema"]["photo_file_id"] = file.file_id

        await context.bot.send_message(chat_id, "✅ *Foto recebida!* Agora informe o local.", parse_mode="Markdown")
        await context.bot.send_message(chat_id, "📍 *Onde fica o problema?* Forneça endereço ou referência.", parse_mode="Markdown")
        return LOCATION

    # se texto (erro) -> reapresenta aviso + botões
    keyboard = [
        [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
         InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")]
    ]
    await context.bot.send_message(chat_id, "⚠️ *Por favor, envie uma foto* ou clique em *Pular*.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return PHOTO


async def receber_local(update, context):
    chat_id = update.effective_chat.id
    descricao_local = (update.message.text or "").strip()
    if len(descricao_local) < 5:
        await update.message.reply_text("⚠️ Local muito vago. Informe ponto de referência mais específico.")
        return LOCATION

    problema = context.user_data["problema"]
    problema["descricao_local"] = descricao_local
    created_at = get_brasilia_time()
    created_at_formatted = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    problema.update({
        "id": get_uuid(),
        "user_id": update.effective_user.id,
        "chat_id": chat_id,
        "latitude": None,
        "longitude": None,
        "created_at": created_at,
        "created_at_formatted": created_at_formatted,
        "updated_at": created_at
    })

    await mostrar_preview_problema(update, context)
    return CONFIRMACAO


async def mostrar_preview_problema(update, context):
    problema = context.user_data["problema"]
    chat_id = update.effective_chat.id

    msg = "📋 *Confirme os dados do problema:*\n\n"
    msg += f"📁 *Categoria:* {problema.get('categoria','-')}\n"
    msg += f"📝 *Título:* {problema.get('titulo','-')}\n"
    msg += f"📄 *Descrição:* {problema.get('descricao','-')}\n"
    msg += f"📍 *Local:* {problema.get('descricao_local','-')}\n"
    msg += f"📅 *Data:* {problema.get('created_at_formatted','-')}\n"
    msg += f"📊 *Status:* {format_status(problema.get('status',''))}\n"
    msg += f"📷 *Foto:* {'✅ Sim' if problema.get('photo_file_id') else '❌ Não'}\n\n"
    msg += "*Tudo correto?*"

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save"),
         InlineKeyboardButton("❌ Cancelar", callback_data="cancel_save")]
    ]

    if problema.get("photo_file_id"):
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=problema["photo_file_id"], caption=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        except Exception as e:
            logger.warning("Falha ao enviar foto no preview: %s", e)

    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def confirmar_registro(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id if query.message else (update.effective_chat.id if update.effective_chat else None)

    if query.data == "confirm_save":
        problema = context.user_data.get("problema")
        if not problema:
            await context.bot.send_message(chat_id, "❌ Nenhum problema encontrado para salvar.")
            await send_menu(update, context)
            return ConversationHandler.END

        problemas_store.append(problema)
        ok = save_to_gist()
        if not ok:
            await context.bot.send_message(chat_id, "❌ Erro ao salvar no Gist. Tente novamente mais tarde.")
            return ConversationHandler.END

        await context.bot.send_message(chat_id, "✅ *Problema registrado com sucesso!*", parse_mode="Markdown")
        context.user_data.pop("problema", None)
        await send_menu(update, context)
        return ConversationHandler.END

    elif query.data == "cancel_save":
        context.user_data.pop("problema", None)
        await context.bot.send_message(chat_id, "❌ *Registro cancelado.*", parse_mode="Markdown")
        await send_menu(update, context)
        return ConversationHandler.END

    return ConversationHandler.END


# =========================
# Delete flow handlers
# =========================
async def deletar_command(update, context):
    await update.message.reply_text("🔐 Digite a senha de administrador:")
    return DELETE_PASSWORD


async def deletar_password(update, context):
    senha = (update.message.text or "").strip()
    if senha != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Senha incorreta.")
        return ConversationHandler.END

    if not problemas_store:
        await update.message.reply_text("📭 Nenhum registro para excluir.")
        return ConversationHandler.END

    botoes = [
        [InlineKeyboardButton(p.get("titulo", "Sem título"), callback_data=f"del:{p['id']}")]
        for p in problemas_store
    ]

    await update.message.reply_text(
        "🗑 *Selecione o registro que deseja excluir:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(botoes)
    )
    return DELETE_CHOOSE


async def deletar_escolha(update, context):
    query = update.callback_query
    await query.answer()

    reg_id = query.data.split(":")[1]
    context.user_data["delete_id"] = reg_id

    await query.message.reply_text(
        "⚠ Tem certeza que deseja apagar?\nIsso *não poderá ser desfeito!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sim", callback_data="delconf:yes"),
             InlineKeyboardButton("❌ Não", callback_data="delconf:no")]
        ])
    )
    return DELETE_CONFIRM


async def deletar_confirmar(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "delconf:no":
        await query.message.reply_text("❌ Ação cancelada.")
        await send_menu(update, context)
        return ConversationHandler.END

    reg_id = context.user_data.get("delete_id")
    if not reg_id:
        await query.message.reply_text("❌ Erro interno.")
        return ConversationHandler.END

    global problemas_store
    problemas_store = [p for p in problemas_store if p["id"] != reg_id]
    save_to_gist()

    await query.message.reply_text("🗑 Registro excluído com sucesso!")
    await send_menu(update, context)
    return ConversationHandler.END


# =========================
# Extra handlers
# =========================
async def auto_menu(update, context):
    if update.message and update.message.text and update.message.text.startswith("/"):
        return
    await send_menu(update, context)


async def error_handler(update, context):
    logger.error("Erro: %s", context.error, exc_info=context.error)


# ---------- Conversation handler config ----------
registrar_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(menu_callback, pattern="^(registrar|listar|delete_menu|ajuda)$"),
                  CommandHandler("registrar", registrar_command)],
    states={
        CATEGORIA: [CallbackQueryHandler(escolher_categoria, pattern="^cat:")],
        TITULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_titulo)],
        DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
        PHOTO: [
            CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file)$"),
            MessageHandler(filters.PHOTO, receber_foto),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_foto)
        ],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_local)],
        CONFIRMACAO: [CallbackQueryHandler(confirmar_registro, pattern="^(confirm_save|cancel_save)$")]
    },
    fallbacks=[]
)

deletar_handler = ConversationHandler(
    entry_points=[CommandHandler("deletar", deletar_command),
                  CallbackQueryHandler(lambda u, c: c.data == "delete_menu", pattern="^delete_menu$")],
    states={
        DELETE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, deletar_password)],
        DELETE_CHOOSE: [CallbackQueryHandler(deletar_escolha, pattern="^del:")],
        DELETE_CONFIRM: [CallbackQueryHandler(deletar_confirmar, pattern="^delconf:")]
    },
    fallbacks=[]
)


# ---------- App init ----------
def main():
    load_from_gist()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(registrar_handler)

    app.add_handler(deletar_handler)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))

    app.add_error_handler(error_handler)

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path="",
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/"
    )


if __name__ == "__main__":
    main()
