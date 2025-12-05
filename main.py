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
import json
import logging
from datetime import datetime, timedelta
import uuid

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))

# Estados do ConversationHandler
CATEGORIA, DESCRICAO, PHOTO, LOCATION, CONFIRMACAO = range(5)

# Constantes
DB_FILE = "problemas.json"
STATUS_PENDENTE = "pendente"

# Categorias disponíveis
CATEGORIAS = [
    "Iluminação pública",
    "Limpeza urbana",
    "Buraco na rua",
    "Áreas verdes / Praças",
    "Escola / Creche",
    "Segurança",
    "Outro"
]

# Banco de dados persistente
if os.path.exists(DB_FILE):
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        problemas_store = json.load(f)
else:
    problemas_store = []


# ============================================================
# FUNÇÕES DE PERSISTÊNCIA
# ============================================================
def save_data():
    """Salva dados no arquivo JSON"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(problemas_store, f, ensure_ascii=False, indent=2)
        logger.info("Dados salvos com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")


def get_brasilia_time():
    """Retorna o horário de Brasília (UTC-3)"""
    utc_now = datetime.utcnow()
    brasilia_time = utc_now - timedelta(hours=3)
    return brasilia_time.strftime("%Y-%m-%d %H:%M:%S")


def get_uuid():
    """Gera um UUID no formato da tabela"""
    return str(uuid.uuid4())


def format_status(status):
    """Formata o status para exibição"""
    status_map = {
        "pendente": "⏳ Pendente",
        "aprovado": "✅ Aprovado",
        "em_analise": "🔍 Em análise",
        "rejeitado": "❌ Rejeitado"
    }
    return status_map.get(status, status)


# ============================================================
# 🧩 MENU PRINCIPAL — SEMPRE NOVA MENSAGEM
# ============================================================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Registrar problema", callback_data="registrar")],
        [InlineKeyboardButton("📋 Listar registros", callback_data="listar")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="ajuda")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat = update.effective_chat

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


# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)


# ============================================================
# /ajuda - NOVO COMANDO
# ============================================================
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *Como usar o Kernel6 Project:*

📝 *Registrar problema:*
- Use /start ou escreva qualquer mensagem
- Selecione "Registrar problema" no menu
- Siga as instruções passo a passo

📋 *Ver todos os registros:*
- Selecione "Listar registros" no menu

⚡ *Comandos disponíveis:*
/start - Menu principal
/ajuda - Esta mensagem
/registrar - Iniciar novo registro (também disponível no menu)

⚠️ *Dicas:*
- Forneça descrições detalhadas
- Envie fotos quando possível
- Informe o local exato
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")
    await send_menu(update, context)


# ============================================================
# /registrar - COMANDO DIRETO PARA REGISTRAR
# ============================================================
async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
              for cat in CATEGORIAS]

    await context.bot.send_message(
        chat_id=chat_id,
        text="📝 Qual categoria do problema?",
        reply_markup=InlineKeyboardMarkup(botoes)
    )
    
    # Setar o estado manualmente
    context.user_data["in_conversation"] = True
    return CATEGORIA


# ============================================================
# MENU AUTOMÁTICO SEM COMANDO
# ============================================================
async def auto_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_menu(update, context)


# ============================================================
# CALLBACKS DO MENU (SEM APAGAR MENSAGENS)
# ============================================================
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    # -----------------------------
    # iniciar registro
    # -----------------------------
    if query.data == "registrar":
        botoes = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
                  for cat in CATEGORIAS]

        await context.bot.send_message(
            chat_id=chat_id,
            text="📝 Qual categoria do problema?",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return CATEGORIA

    # -----------------------------
    # listar registros — TODOS OS REGISTROS
    # -----------------------------
    elif query.data == "listar":
        if not problemas_store:
            await context.bot.send_message(chat_id, "📋 Nenhum problema registrado ainda.")
        else:
            # Ordenar por data mais recente primeiro
            problemas_ordenados = sorted(problemas_store, 
                                        key=lambda x: x.get('created_at', ''), 
                                        reverse=True)
            
            msg = "📋 *Todos os Problemas Registrados:*\n\n"
            for i, p in enumerate(problemas_ordenados, 1):
                msg += f"*{i}. {p['categoria']}*\n"
                msg += f"📝 *Título:* {p['titulo']}\n"
                msg += f"📍 *Local:* {p['descricao_local']}\n"
                msg += f"📅 *Criado:* {p.get('created_at_formatted', p.get('created_at', ''))}\n"
                msg += f"📊 *Status:* {format_status(p['status'])}\n\n"

            await context.bot.send_message(chat_id, msg, parse_mode="Markdown")

        await send_menu(update, context)
        return ConversationHandler.END
    
    # -----------------------------
    # ajuda via botão
    # -----------------------------
    elif query.data == "ajuda":
        help_text = """
🤖 *Como usar o Kernel6 Project:*

📝 *Registrar problema:*
- Use /start ou escreva qualquer mensagem
- Selecione "Registrar problema" no menu
- Siga as instruções passo a passo

📋 *Ver todos os registros:*
- Selecione "Listar registros" no menu

⚡ *Comandos disponíveis:*
/start - Menu principal
/ajuda - Esta mensagem
/registrar - Iniciar novo registro

⚠️ *Dicas:*
- Forneça descrições detalhadas
- Envie fotos quando possível
- Informe o local exato
"""
        await query.edit_message_text(help_text, parse_mode="Markdown")
        await send_menu(update, context)


# ============================================================
# ETAPA 1 — CATEGORIA
# ============================================================
async def escolher_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    categoria = query.data.replace("cat:", "")
    context.user_data["problema"] = {
        "categoria": categoria,
        "status": STATUS_PENDENTE  # Sempre pendente inicialmente
    }

    await context.bot.send_message(
        chat_id, 
        "📝 *Forneça um título para o problema:*\n\n"
        "Seja claro e objetivo. Exemplo:\n"
        "\"Poste de luz quebrado na Rua das Flores\"",
        parse_mode="Markdown"
    )
    return DESCRICAO


# ============================================================
# ETAPA 2 — DESCRIÇÃO (TÍTULO + DESCRIÇÃO)
# ============================================================
async def receber_titulo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    titulo = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Validação do título
    if len(titulo) < 3:
        await update.message.reply_text(
            "⚠️ Título muito curto. Por favor, forneça um título mais descritivo.\n"
            "Exemplo: \"Poste de luz quebrado na Rua das Flores\""
        )
        return DESCRICAO
    
    if len(titulo) > 100:
        await update.message.reply_text(
            "⚠️ Título muito longo. Limite de 100 caracteres.\n"
            "Por favor, resuma o título."
        )
        return DESCRICAO
    
    context.user_data["problema"]["titulo"] = titulo

    await context.bot.send_message(
        chat_id,
        "📝 *Agora, descreva o problema com detalhes:*\n\n"
        "Inclua informações relevantes como:\n"
        "- Gravidade do problema\n"
        "- Há quanto tempo existe\n"
        "- Impacto na comunidade\n"
        "- Qualquer detalhe adicional",
        parse_mode="Markdown"
    )
    return DESCRICAO


async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Validação da descrição
    if len(descricao) < 10:
        await update.message.reply_text(
            "⚠️ Descrição muito curta. Por favor, forneça mais detalhes.\n"
            "Descreva o problema com mais informações."
        )
        return DESCRICAO
    
    if len(descricao) > 1000:
        await update.message.reply_text(
            "⚠️ Descrição muito longa. Limite de 1000 caracteres.\n"
            "Por favor, resuma a informação."
        )
        return DESCRICAO
    
    context.user_data["problema"]["descricao"] = descricao

    keyboard = [
        [
            InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
            InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")
        ]
    ]

    await context.bot.send_message(
        chat_id,
        "📸 *Deseja enviar uma foto do problema?*\n\n"
        "Uma foto ajuda muito na identificação e análise!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PHOTO


# ============================================================
# ETAPA 3 — FOTO
# ============================================================
async def photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "skip_file":
        context.user_data["problema"]["photo_file_id"] = None
        await context.bot.send_message(
            chat_id,
            "📍 *Onde fica o problema?*\n\n"
            "Forneça o endereço ou ponto de referência. Exemplo:\n"
            "\"Esquina da Rua das Flores com Avenida Principal, número 123\"",
            parse_mode="Markdown"
        )
        return LOCATION

    if query.data == "add_file":
        await context.bot.send_message(
            chat_id,
            "📸 *Envie a foto agora.*\n\n"
            "Por favor, envie uma foto clara do problema.",
            parse_mode="Markdown"
        )
        return PHOTO


async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        context.user_data["problema"]["photo_file_id"] = file.file_id

        await context.bot.send_message(
            chat_id,
            "✅ *Foto recebida!*\n\n"
            "📍 *Agora, onde fica o problema?*\n\n"
            "Forneça o endereço ou ponto de referência.",
            parse_mode="Markdown"
        )
        return LOCATION

    keyboard = [
        [
            InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
            InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")
        ]
    ]

    await context.bot.send_message(
        chat_id,
        "⚠️ *Por favor, envie uma foto* ou clique em *Pular*.\n\n"
        "A foto deve ser clara e mostrar o problema.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PHOTO


# ============================================================
# ETAPA 4 — LOCAL (DESCRIÇÃO DO LOCAL)
# ============================================================
async def receber_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    descricao_local = update.message.text.strip()
    
    # Validação do local
    if len(descricao_local) < 5:
        await update.message.reply_text(
            "⚠️ Local muito vago. Por favor, forneça um endereço ou ponto de referência mais específico.\n"
            "Exemplo: \"Esquina da Rua das Flores com Avenida Principal, número 123\""
        )
        return LOCATION
    
    context.user_data["problema"]["descricao_local"] = descricao_local
    
    # Adicionar metadados
    created_at = get_brasilia_time()
    created_at_formatted = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    
    context.user_data["problema"].update({
        "id": get_uuid(),  # UUID no formato da tabela
        "user_id": update.effective_user.id,
        "chat_id": chat_id,
        "latitude": None,
        "longitude": None,
        "created_at": created_at,
        "created_at_formatted": created_at_formatted,
        "updated_at": created_at
    })
    
    # Mostrar preview e confirmar
    await mostrar_preview_problema(update, context)
    return CONFIRMACAO


# ============================================================
# PREVIEW E CONFIRMAÇÃO
# ============================================================
async def mostrar_preview_problema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    problema = context.user_data["problema"]
    chat_id = update.effective_chat.id
    
    msg = "📋 *Confirme os dados do problema:*\n\n"
    msg += f"📁 *Categoria:* {problema['categoria']}\n"
    msg += f"📝 *Título:* {problema['titulo']}\n"
    msg += f"📄 *Descrição:* {problema['descricao']}\n"
    msg += f"📍 *Local:* {problema['descricao_local']}\n"
    msg += f"📅 *Data:* {problema['created_at_formatted']}\n"
    msg += f"📊 *Status:* {format_status(problema['status'])}\n"
    msg += f"📷 *Foto:* {'✅ Sim' if problema.get('photo_file_id') else '❌ Não'}\n\n"
    msg += "*Tudo correto?*"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_save"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_save")
        ]
    ]
    
    if problema.get('photo_file_id'):
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=problema['photo_file_id'],
                caption=msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        except:
            pass  # Se falhar, enviar apenas texto
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirmar_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if query.data == "confirm_save":
        problema = context.user_data["problema"]
        
        # Salvar no armazenamento
        problemas_store.append(problema)
        save_data()
        
        await query.edit_message_text(
            f"✅ *Problema registrado com sucesso!*\n\n"
            f"O problema foi registrado e está *{problema['status']}* para análise.\n"
            f"Você pode ver todos os registros na listagem.",
            parse_mode="Markdown"
        )
        
        # Limpar dados temporários
        context.user_data.pop("problema", None)
        
        await send_menu(update, context)
        return ConversationHandler.END
    
    elif query.data == "cancel_save":
        context.user_data.pop("problema", None)
        await query.edit_message_text(
            "❌ *Registro cancelado.*\n\n"
            "Os dados não foram salvos.",
            parse_mode="Markdown"
        )
        await send_menu(update, context)
        return ConversationHandler.END


# ============================================================
# HANDLER DE ERROS
# ============================================================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manipula erros do bot"""
    logger.error(f"Erro: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Ocorreu um erro. Por favor, tente novamente ou use /start",
                parse_mode="Markdown"
            )
            await send_menu(update, context)
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de erro: {e}")


# ============================================================
# HANDLER PRINCIPAL DE REGISTRO
# ============================================================
registrar_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(menu_callback, pattern="^(registrar|listar|ajuda)$"),
        CommandHandler("registrar", registrar)
    ],

    states={
        CATEGORIA: [CallbackQueryHandler(escolher_categoria, pattern="^cat:")],
        DESCRICAO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_titulo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)
        ],
        PHOTO: [
            CallbackQueryHandler(photo_choice, pattern="^(add_file|skip_file)$"),
            MessageHandler(filters.PHOTO, receber_foto),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receber_foto)
        ],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_local)],
        CONFIRMACAO: [CallbackQueryHandler(confirmar_registro, pattern="^(confirm_save|cancel_save)$")],
    },

    fallbacks=[]
)


# ============================================================
# APP / WEBHOOK
# ============================================================
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Adicionar handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ajuda", ajuda))
app.add_handler(CommandHandler("registrar", registrar))
app.add_handler(registrar_handler)

# qualquer texto → abre menu
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))

# Handler de erros
app.add_error_handler(error_handler)

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/",
    )
