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
GIST_ID = os.getenv("GIST_ID")  # ex: a4884557...
GIST_FILENAME = os.getenv("GIST_FILENAME", "registros.json")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN não definido")
if not GIST_TOKEN:
    logger.error("GIST_TOKEN não definido")
if not GIST_ID:
    logger.error("GIST_ID não definido")

# ---------- Conversation states ----------
CATEGORIA, TITULO, DESCRICAO, PHOTO, LOCATION, CONFIRMACAO = range(6)

# ---------- Constants ----------
STATUS_PENDENTE = "pendente"

CATEGORIAS = [
    "Iluminação pública",
    "Limpeza urbana",
    "Buraco na rua",
    "Áreas verdes / Praças",
    "Escola / Creche",
    "Segurança",
    "Outro"
]

# ---------- In-memory store (mirror of gist) ----------
problemas_store = []

# ---------- Gist API helpers ----------
GIST_API_BASE = "https://api.github.com/gists"


def gist_headers():
    return {"Authorization": f"token {GIST_TOKEN}", "Accept": "application/vnd.github+json"}


def load_from_gist():
    """Carrega o conteúdo JSON do arquivo especificado dentro do gist."""
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
            # arquivo não encontrado no gist — criar com []
            problemas_store = []
            save_to_gist()  # cria o arquivo no gist
    except Exception as e:
        logger.error("Erro ao carregar gist: %s", e)
        problemas_store = []


def save_to_gist():
    """Salva (patch) o arquivo JSON dentro do gist (substitui o conteúdo do arquivo)."""
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


# ---------- Utilitários ----------
def get_brasilia_time():
    utc_now = datetime.utcnow()
    brasilia_time = utc_now - timedelta(hours=3)
    return brasilia_time.strftime("%Y-%m-%d %H:%M:%S")


def get_uuid():
    return str(uuid.uuid4())


def format_status(status):
    status_map = {
        "pendente": "⏳ Pendente",
        "aprovado": "✅ Aprovado",
        "em_analise": "🔍 Em análise",
        "rejeitado": "❌ Rejeitado"
    }
    return status_map.get(status, status)


# ---------- Menu (sempre envia nova mensagem) ----------
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Registrar problema", callback_data="registrar")],
        [InlineKeyboardButton("📋 Listar registros", callback_data="listar")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="ajuda")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat = update.effective_chat
    if not chat and update.callback_query and update.callback_query.message:
        chat = update.callback_query.message.chat

    if chat:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "👋 *Bem-vindo ao Kernel6 Project!*\n"
                "Ajude a melhorar nossa comunidade...\n\n"
                "Escolha uma opção:"
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)


# ---------- /ajuda ----------
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Como usar o Kernel6 Project:*\n\n"
        "📝 *Registrar problema:*\n"
        "- Use /start ou escreva qualquer mensagem\n"
        "- Selecione \"Registrar problema\" no menu\n\n"
        "📋 *Ver todos os registros:*\n"
        "- Selecione \"Listar registros\" no menu\n\n"
        "⚡ *Comandos:*\n"
        "/start - Menu\n"
        "/ajuda - Ajuda\n"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(help_text, parse_mode="Markdown")
    await send_menu(update, context)


# ---------- /registrar (direto) ----------
async def registrar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIAS]
    await context.bot.send_message(chat_id=chat_id, text="📝 Qual categoria do problema?", reply_markup=InlineKeyboardMarkup(botoes))
    return CATEGORIA


# ---------- Auto menu for any text (except commands) ----------
async def auto_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text and update.message.text.startswith("/"):
        return
    await send_menu(update, context)


# ---------- Menu callbacks ----------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    chat_id = chat.id

    if query.data == "registrar":
        botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIAS]
        await context.bot.send_message(chat_id=chat_id, text="📝 Qual categoria do problema?", reply_markup=InlineKeyboardMarkup(botoes))
        return CATEGORIA

    elif query.data == "listar":
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
                # se tiver foto, manda photo com caption; se não, envia texto
                if p.get("photo_file_id"):
                    try:
                        await context.bot.send_photo(chat_id=chat_id, photo=p["photo_file_id"], caption=texto, parse_mode="Markdown")
                    except Exception as e:
                        logger.warning("Erro ao enviar photo (fallback para texto): %s", e)
                        await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

        await send_menu(update, context)
        return ConversationHandler.END

    elif query.data == "ajuda":
        await ajuda(update, context)
        return ConversationHandler.END

    return ConversationHandler.END


# ---------- Etapa Categoria ----------
async def escolher_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    categoria = query.data.replace("cat:", "")
    context.user_data["problema"] = {"categoria": categoria, "status": STATUS_PENDENTE}
    await context.bot.send_message(chat.id, "📝 *Forneça um título para o problema:*\nEx: \"Poste de luz quebrado na Rua X\"", parse_mode="Markdown")
    return TITULO


# ---------- Etapa Título ----------
async def receber_titulo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# ---------- Etapa Descrição ----------
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    if len(descricao) < 10:
        await update.message.reply_text("⚠️ Descrição muito curta. Informe mais detalhes.")
        return DESCRICAO
    context.user_data["problema"]["descricao"] = descricao

    keyboard = [[InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"), InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")]]
    await context.bot.send_message(chat_id, "📸 *Deseja enviar uma foto do problema?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return PHOTO


# ---------- Etapa Foto (corrigida) ----------
async def photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # se foto
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data["problema"]["photo_file_id"] = file.file_id

        await context.bot.send_message(chat_id, "✅ *Foto recebida!* Agora informe o local.", parse_mode="Markdown")
        await context.bot.send_message(chat_id, "📍 *Onde fica o problema?* Forneça endereço ou referência.", parse_mode="Markdown")
        return LOCATION

    # se texto (erro) -> reapresenta aviso + botões
    keyboard = [[InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"), InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")]]
    await context.bot.send_message(chat_id, "⚠️ *Por favor, envie uma foto* ou clique em *Pular*.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return PHOTO


# ---------- Etapa Local ----------
async def receber_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Mostrar preview e confirmação
    await mostrar_preview_problema(update, context)
    return CONFIRMACAO


# ---------- Mostrar preview (não editar mensagem de mídia) ----------
async def mostrar_preview_problema(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    keyboard = [[InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save"), InlineKeyboardButton("❌ Cancelar", callback_data="cancel_save")]]

    # se tiver foto, envia a foto com legenda (não editaremos essa mensagem depois)
    if problema.get("photo_file_id"):
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=problema["photo_file_id"], caption=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        except Exception as e:
            logger.warning("Falha ao enviar foto no preview: %s", e)

    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------- Confirmar / Cancelar (NÃO editar mensagens de mídia) ----------
async def confirmar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id if query.message else (update.effective_chat.id if update.effective_chat else None)

    if query.data == "confirm_save":
        problema = context.user_data.get("problema")
        if not problema:
            await context.bot.send_message(chat_id, "❌ Nenhum problema encontrado para salvar.")
            await send_menu(update, context)
            return ConversationHandler.END

        # salvar em memória e Gist
        problemas_store.append(problema)
        ok = save_to_gist()
        if not ok:
            await context.bot.send_message(chat_id, "❌ Erro ao salvar no Gist. Tente novamente mais tarde.")
            return ConversationHandler.END

        # confirmar sem editar
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


# ---------- Error handler ----------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Erro: %s", context.error, exc_info=context.error)
    try:
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_message(chat_id, "❌ Ocorreu um erro. Tente novamente ou use /start")
            await send_menu(update, context)
    except Exception as e:
        logger.error("Erro ao notificar usuário: %s", e)


# ---------- Conversation handler config ----------
registrar_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(menu_callback, pattern="^(registrar|listar|ajuda)$"), CommandHandler("registrar", registrar_command)],
    states={
        CATEGORIA: [CallbackQueryHandler(escolher_categoria, pattern="^cat:")],
        TITULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_titulo)],
        DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
        PHOTO: [CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file)$"), MessageHandler(filters.PHOTO, receber_foto), MessageHandler(filters.TEXT & ~filters.COMMAND, receber_foto)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_local)],
        CONFIRMACAO: [CallbackQueryHandler(confirmar_registro, pattern="^(confirm_save|cancel_save)$")]
    },
    fallbacks=[]
)


# ---------- App init ----------
def main():
    # carregar do gist ao iniciar
    load_from_gist()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("registrar", registrar_command))
    app.add_handler(registrar_handler)
    # qualquer texto → mostra menu
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))
    app.add_error_handler(error_handler)

    # webhook run (Render)
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path="",
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/"
    )


if __name__ == "__main__":
    main()
