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
    raise ValueError("BOT_TOKEN não definido")

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
        if not GIST_TOKEN or not GIST_ID:
            logger.warning("GIST_TOKEN ou GIST_ID não definidos. Usando armazenamento local.")
            problemas_store = []
            return
            
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
        if not GIST_TOKEN or not GIST_ID:
            logger.warning("GIST_TOKEN ou GIST_ID não definidos. Salvando localmente.")
            return True
            
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

    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
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
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, txt, parse_mode="Markdown")
    await send_menu(update, context)


# ---------- Registrar via comando (opcional) ----------
async def registrar_command(update, context):
    chat_id = update.effective_chat.id
    botoes = []
    for cat in CATEGORIAS:
        botoes.append([InlineKeyboardButton(cat, callback_data=f"cat:{cat}")])
    botoes.append([InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")])
    await context.bot.send_message(
        chat_id=chat_id, 
        text="📝 Qual categoria do problema?", 
        reply_markup=InlineKeyboardMarkup(botoes)
    )
    return CATEGORIA


# ---------- Menu callback (botões principais) ----------
async def menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data == "registrar":
        botoes = []
        for cat in CATEGORIAS:
            botoes.append([InlineKeyboardButton(cat, callback_data=f"cat:{cat}")])
        botoes.append([InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")])
        await context.bot.send_message(
            chat_id=chat_id, 
            text="📝 Qual categoria do problema?", 
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return CATEGORIA

    elif data == "listar":
        if not problemas_store:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
            await context.bot.send_message(
                chat_id, 
                "📋 Nenhum problema registrado ainda.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            problemas_ordenados = sorted(problemas_store, key=lambda x: x.get("created_at", ""), reverse=True)
            for i, p in enumerate(problemas_ordenados, 1):
                texto = (
                    f"*{i}. {p.get('categoria','-')}*\n"
                    f"📝 *Título:* {p.get('titulo','-')}\n"
                    f"📄 *Descrição:* {p.get('descricao','1-')}\n"
                    f"📍 *Local:* {p.get('descricao_local','-')}\n"
                    f"📅 *Criado:* {p.get('created_at_formatted','-')}\n"
                    f"📊 *Status:* {format_status(p.get('status',''))}\n"
                )
                if p.get("photo_file_id"):
                    try:
                        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                        await context.bot.send_photo(
                            chat_id=chat_id, 
                            photo=p["photo_file_id"], 
                            caption=texto, 
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logger.warning("Erro ao enviar foto no listar (fallback texto): %s", e)
                        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                        await context.bot.send_message(
                            chat_id=chat_id, 
                            text=texto, 
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                else:
                    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                    await context.bot.send_message(
                        chat_id=chat_id, 
                        text=texto, 
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
        return ConversationHandler.END

    elif data == "delete_menu":
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
        await context.bot.send_message(
            chat_id=chat_id, 
            text="🔐 Digite a senha de administrador:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DELETE_PASSWORD

    elif data == "ajuda":
        await ajuda(update, context)
        return ConversationHandler.END

    elif data == "voltar_menu":
        await send_menu(update, context)
        return ConversationHandler.END

    return ConversationHandler.END


# =========================
# Registrar flow handlers
# =========================
async def escolher_categoria(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    
    if data == "voltar_menu":
        await send_menu(update, context)
        return ConversationHandler.END
    
    categoria = data.replace("cat:", "")
    context.user_data["problema"] = {"categoria": categoria, "status": STATUS_PENDENTE}
    
    keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_categoria")]]
    await context.bot.send_message(
        chat_id, 
        "📝 *Forneça um título para o problema:*\nEx: \"Poste de luz quebrado na Rua X\"", 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TITULO


async def receber_titulo(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "voltar_categoria":
            # Voltar para escolha de categoria
            botoes = []
            for cat in CATEGORIAS:
                botoes.append([InlineKeyboardButton(cat, callback_data=f"cat:{cat}")])
            botoes.append([InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")])
            await context.bot.send_message(
                query.message.chat.id, 
                "📝 Qual categoria do problema?", 
                reply_markup=InlineKeyboardMarkup(botoes)
            )
            return CATEGORIA
    
    titulo = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    
    if len(titulo) < 3:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_categoria")]]
        await update.message.reply_text(
            "⚠️ Título muito curto. Informe algo mais descritivo.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TITULO
    if len(titulo) > 100:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_categoria")]]
        await update.message.reply_text(
            "⚠️ Título muito longo. Max 100 caracteres.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TITULO
    
    context.user_data["problema"]["titulo"] = titulo
    
    keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_titulo")]]
    await context.bot.send_message(
        chat_id, 
        "📝 *Agora, descreva o problema com detalhes:*", 
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESCRICAO


async def receber_descricao(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "voltar_titulo":
            # Voltar para título
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_categoria")]]
            await context.bot.send_message(
                query.message.chat.id, 
                "📝 *Forneça um título para o problema:*\nEx: \"Poste de luz quebrado na Rua X\"", 
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return TITULO
    
    descricao = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    
    if len(descricao) < 10:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_titulo")]]
        await update.message.reply_text(
            "⚠️ Descrição muito curta. Informe mais detalhes.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DESCRICAO
    
    context.user_data["problema"]["descricao"] = descricao

    keyboard = [
        [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
         InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_descricao")]
    ]
    await context.bot.send_message(
        chat_id, 
        "📸 *Deseja enviar uma foto do problema?*", 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PHOTO


async def photo_choice(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "skip_file":
        context.user_data["problema"]["photo_file_id"] = None
        
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_foto")]]
        await context.bot.send_message(
            chat_id, 
            "📍 *Onde fica o problema?* Forneça endereço ou referência.", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LOCATION

    elif query.data == "add_file":
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_descricao")]]
        await context.bot.send_message(
            chat_id, 
            "📸 *Envie a foto agora.* Por favor, envie uma foto clara do problema.", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PHOTO
    
    elif query.data == "voltar_descricao":
        # Voltar para descrição
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_titulo")]]
        await context.bot.send_message(
            chat_id, 
            "📝 *Agora, descreva o problema com detalhes:*", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DESCRICAO
    
    elif query.data == "voltar_foto":
        # Voltar para escolha de foto
        keyboard = [
            [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
             InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_descricao")]
        ]
        await context.bot.send_message(
            chat_id, 
            "📸 *Deseja enviar uma foto do problema?*", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PHOTO


async def receber_foto(update, context):
    chat_id = update.effective_chat.id

    # se foto
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data["problema"]["photo_file_id"] = file.file_id

        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_foto")]]
        await context.bot.send_message(
            chat_id, 
            "✅ *Foto recebida!* Agora informe o local.", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_apos_foto")]]
        await context.bot.send_message(
            chat_id, 
            "📍 *Onde fica o problema?* Forneça endereço ou referência.", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LOCATION

    # se texto (erro) -> reapresenta aviso + botões
    keyboard = [
        [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
         InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_descricao")]
    ]
    await context.bot.send_message(
        chat_id, 
        "⚠️ *Por favor, envie uma foto* ou clique em *Pular*.", 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PHOTO


async def receber_local(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "voltar_apos_foto" or data == "voltar_foto":
            # Voltar para escolha de foto
            keyboard = [
                [InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
                 InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")],
                [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_descricao")]
            ]
            await context.bot.send_message(
                query.message.chat.id, 
                "📸 *Deseja enviar uma foto do problema?*", 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return PHOTO
    
    chat_id = update.effective_chat.id
    descricao_local = (update.message.text or "").strip()
    
    if len(descricao_local) < 5:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_foto")]]
        await update.message.reply_text(
            "⚠️ Local muito vago. Informe ponto de referência mais específico.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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

    # Enviar foto separadamente (se houver)
    if problema.get("photo_file_id"):
        try:
            await context.bot.send_photo(
                chat_id=chat_id, 
                photo=problema["photo_file_id"],
                caption="📸 *Foto do problema enviada*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning("Erro ao enviar foto no preview: %s", e)

    # Mensagem com os dados
    msg = "📋 *CONFIRME OS DADOS DO PROBLEMA*\n\n"
    msg += f"📁 *Categoria:* {problema.get('categoria','-')}\n"
    msg += f"📝 *Título:* {problema.get('titulo','-')}\n"
    
    # Limitar descrição se muito longa
    descricao = problema.get('descricao','-')
    if len(descricao) > 100:
        descricao = descricao[:97] + "..."
    msg += f"📄 *Descrição:* {descricao}\n"
    
    msg += f"📍 *Local:* {problema.get('descricao_local','-')}\n"
    msg += f"📅 *Data:* {problema.get('created_at_formatted','-')}\n"
    msg += f"📊 *Status:* {format_status(problema.get('status',''))}\n"
    msg += f"📷 *Foto anexada:* {'✅ Sim' if problema.get('photo_file_id') else '❌ Não'}\n\n"
    msg += "*Tudo correto?*"

    keyboard = [
        [InlineKeyboardButton("✅ SIM, CONFIRMAR", callback_data="confirm_save"),
         InlineKeyboardButton("❌ NÃO, CANCELAR", callback_data="cancel_save")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_local")]
    ]

    await context.bot.send_message(
        chat_id=chat_id, 
        text=msg, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirmar_registro(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

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
    
    elif query.data == "voltar_local":
        # Voltar para local
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_foto")]]
        await context.bot.send_message(
            chat_id, 
            "📍 *Onde fica o problema?* Forneça endereço ou referência.", 
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return LOCATION

    return ConversationHandler.END


# =========================
# Delete flow handlers - CORRIGIDO
# =========================
async def deletar_command(update, context):
    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
    await update.message.reply_text(
        "🔐 Digite a senha de administrador:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_PASSWORD


async def deletar_password(update, context):
    # Verificar se é callback de voltar
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "voltar_menu":
            await send_menu(update, context)
            return ConversationHandler.END
        return DELETE_PASSWORD
    
    # Se for mensagem de texto (senha)
    senha = (update.message.text or "").strip()
    if senha != ADMIN_PASSWORD:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
        await update.message.reply_text(
            "❌ Senha incorreta.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    global problemas_store
    if not problemas_store:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
        await update.message.reply_text(
            "📭 Nenhum registro para excluir.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    # Criar botões com os registros
    botoes = []
    for p in problemas_store:
        titulo = p.get("titulo", "Sem título")
        # Limitar tamanho do título se muito longo
        if len(titulo) > 30:
            titulo = titulo[:27] + "..."
        botoes.append([InlineKeyboardButton(titulo, callback_data=f"del:{p['id']}")])
    
    botoes.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_senha")])

    await update.message.reply_text(
        "🗑 *Selecione o registro que deseja excluir:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(botoes)
    )
    return DELETE_CHOOSE


async def deletar_escolha(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "voltar_senha":
        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
        await context.bot.send_message(
            query.message.chat.id,
            "🔐 Digite a senha de administrador:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DELETE_PASSWORD
    
    # Extrair ID do registro
    if query.data.startswith("del:"):
        reg_id = query.data.split(":")[1]
        context.user_data["delete_id"] = reg_id

        keyboard = [
            [InlineKeyboardButton("✅ Sim", callback_data="delconf:yes"),
             InlineKeyboardButton("❌ Não", callback_data="delconf:no")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_escolha")]
        ]
        
        await query.message.reply_text(
            "⚠ Tem certeza que deseja apagar?\nIsso *não poderá ser desfeito!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DELETE_CONFIRM
    
    return DELETE_CHOOSE


async def deletar_confirmar(update, context):
    query = update.callback_query
    await query.answer()
    
    global problemas_store

    if query.data == "delconf:no" or query.data == "voltar_escolha":
        # Voltar para escolha de registro
        botoes = []
        for p in problemas_store:
            titulo = p.get("titulo", "Sem título")
            if len(titulo) > 30:
                titulo = titulo[:27] + "..."
            botoes.append([InlineKeyboardButton(titulo, callback_data=f"del:{p['id']}")])
        
        botoes.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_senha")])
        
        await query.message.reply_text(
            "🗑 *Selecione o registro que deseja excluir:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return DELETE_CHOOSE

    elif query.data == "delconf:yes":
        reg_id = context.user_data.get("delete_id")
        if not reg_id:
            await query.message.reply_text("❌ Erro interno.")
            await send_menu(update, context)
            return ConversationHandler.END

        problemas_store = [p for p in problemas_store if p["id"] != reg_id]
        save_to_gist()

        await query.message.reply_text("🗑 Registro excluído com sucesso!")
        await send_menu(update, context)
        return ConversationHandler.END

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
# Handler para registro de problemas
registrar_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(menu_callback, pattern="^registrar$"),
        CommandHandler("registrar", registrar_command)
    ],
    states={
        CATEGORIA: [
            CallbackQueryHandler(escolher_categoria, pattern="^cat:"),
            CallbackQueryHandler(menu_callback, pattern="^voltar_menu$")
        ],
        TITULO: [
            CallbackQueryHandler(receber_titulo, pattern="^voltar_categoria$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_titulo)
        ],
        DESCRICAO: [
            CallbackQueryHandler(receber_descricao, pattern="^voltar_titulo$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)
        ],
        PHOTO: [
            CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file|voltar_descricao|voltar_foto)$"),
            MessageHandler(filters.PHOTO, receber_foto),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_foto)
        ],
        LOCATION: [
            CallbackQueryHandler(receber_local, pattern="^(voltar_apos_foto|voltar_foto)$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_local)
        ],
        CONFIRMACAO: [CallbackQueryHandler(confirmar_registro, pattern="^(confirm_save|cancel_save|voltar_local)$")]
    },
    fallbacks=[],
    per_message=False,
    per_chat=True,
    per_user=True
)

# Handler para deletar registros - CORRIGIDO
async def start_delete_from_menu(update, context):
    """Handler especial para iniciar deleção do menu"""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    
    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
    await context.bot.send_message(
        chat_id=chat_id, 
        text="🔐 Digite a senha de administrador:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_PASSWORD

deletar_handler = ConversationHandler(
    entry_points=[
        CommandHandler("deletar", deletar_command),
        CallbackQueryHandler(start_delete_from_menu, pattern="^delete_menu$")
    ],
    states={
        DELETE_PASSWORD: [
            CallbackQueryHandler(deletar_password, pattern="^voltar_menu$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, deletar_password)
        ],
        DELETE_CHOOSE: [
            CallbackQueryHandler(deletar_escolha, pattern="^(del:|voltar_senha)$")
        ],
        DELETE_CONFIRM: [
            CallbackQueryHandler(deletar_confirmar, pattern="^(delconf:yes|delconf:no|voltar_escolha)$")
        ]
    },
    fallbacks=[],
    per_message=False,
    per_chat=True,
    per_user=True
)

# Handler para outros callbacks do menu
async def handle_menu_actions(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "listar":
        if not problemas_store:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
            await context.bot.send_message(
                query.message.chat.id,
                "📋 Nenhum problema registrado ainda.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
                        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                        await context.bot.send_photo(
                            chat_id=query.message.chat.id, 
                            photo=p["photo_file_id"], 
                            caption=texto, 
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    except Exception as e:
                        logger.warning("Erro ao enviar foto no listar (fallback texto): %s", e)
                        keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                        await query.message.reply_text(
                            texto, 
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                else:
                    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao menu", callback_data="voltar_menu")]]
                    await query.message.reply_text(
                        texto, 
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
    
    elif data == "ajuda":
        await ajuda(update, context)
    
    elif data == "voltar_menu":
        await send_menu(update, context)


# ---------- App init ----------
def main():
    load_from_gist()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers básicos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    
    # Handlers de conversação
    app.add_handler(registrar_handler)
    app.add_handler(deletar_handler)
    
    # Handler para listar, ajuda e voltar
    app.add_handler(CallbackQueryHandler(handle_menu_actions, pattern="^(listar|ajuda|voltar_menu)$"))
    
    # Handler para menu automático
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))
    
    # Handler de erros
    app.add_error_handler(error_handler)

    # Configurar para funcionar no Render
    if os.environ.get('RENDER'):
        # Usar webhook no Render
        port = int(os.environ.get('PORT', 8443))
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
        
        logger.info(f"Starting webhook on port {port}")
        logger.info(f"Webhook URL: {webhook_url}")
        
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        # Localmente, usar polling
        logger.info("Starting with polling (local environment)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
