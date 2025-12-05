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
from datetime import datetime
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
MAX_REGISTROS_POR_USUARIO = 10
DB_FILE = "registros.json"

# Banco de dados persistente
if os.path.exists(DB_FILE):
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        user_data_store = json.load(f)
else:
    user_data_store = {}


# ============================================================
# FUNÇÕES DE PERSISTÊNCIA
# ============================================================
def save_data():
    """Salva dados no arquivo JSON"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data_store, f, ensure_ascii=False, indent=2)
        logger.info("Dados salvos com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")


# ============================================================
# 🧩 MENU PRINCIPAL — SEMPRE NOVA MENSAGEM
# ============================================================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Registrar problema", callback_data="registrar")],
        [InlineKeyboardButton("📋 Listar registros", callback_data="listar")],
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
- Selecione "Registrar problema"
- Siga as instruções passo a passo

📋 *Ver seus registros:*
- Selecione "Listar registros" no menu

⚡ *Comandos disponíveis:*
/start - Menu principal
/ajuda - Esta mensagem

⚠️ *Dicas:*
- Forneça descrições detalhadas
- Envie fotos quando possível
- Informe o local exato
- Limite de 10 registros por usuário
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")
    await send_menu(update, context)


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
        # Verificar limite de registros (MELHORIA 4)
        if str(chat_id) in user_data_store and len(user_data_store[str(chat_id)]) >= MAX_REGISTROS_POR_USUARIO:
            await query.edit_message_text(
                f"⚠️ Você atingiu o limite de {MAX_REGISTROS_POR_USUARIO} registros.\n"
                "Não é possível criar novos registros no momento."
            )
            await send_menu(update, context)
            return ConversationHandler.END
        
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

        await context.bot.send_message(
            chat_id=chat_id,
            text="📝 Qual categoria do registro?",
            reply_markup=InlineKeyboardMarkup(botoes)
        )
        return CATEGORIA

    # -----------------------------
    # listar registros — NÃO APAGA
    # -----------------------------
    elif query.data == "listar":
        registros = user_data_store.get(str(chat_id), [])

        if not registros:
            await context.bot.send_message(chat_id, "📋 Nenhum registro encontrado.")
        else:
            msg = "📋 *Registros:*\n\n"
            for i, r in enumerate(registros, 1):
                msg += f"{i}. *{r['categoria']}*\n"
                msg += f"   📝 {r['descricao']}\n"
                msg += f"   📍 {r['local']}\n"
                msg += f"   📅 {r.get('data', 'Data não registrada')}\n"
                msg += f"   🆔 ID: {r.get('id', 'N/A')}\n\n"

            await context.bot.send_message(chat_id, msg, parse_mode="Markdown")

        await send_menu(update, context)
        return ConversationHandler.END


# ============================================================
# ETAPA 1 — CATEGORIA
# ============================================================
async def escolher_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    categoria = query.data.replace("cat:", "")
    context.user_data["registro"] = {"categoria": categoria}

    await context.bot.send_message(
        chat_id, 
        "📝 *Descreva o problema:*\n\n"
        "Seja específico e detalhado. Exemplo:\n"
        "\"Poste de luz quebrado na esquina da Rua A com B\"",
        parse_mode="Markdown"
    )
    return DESCRICAO


# ============================================================
# ETAPA 2 — DESCRIÇÃO (COM VALIDAÇÃO) - MELHORIA 1
# ============================================================
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Validação (MELHORIA 1)
    if len(descricao) < 5:
        await update.message.reply_text(
            "⚠️ Descrição muito curta. Por favor, forneça mais detalhes.\n"
            "Exemplo: \"Poste de luz quebrado na esquina da Rua A com B\""
        )
        return DESCRICAO
    
    if len(descricao) > 1000:
        await update.message.reply_text(
            "⚠️ Descrição muito longa. Limite de 1000 caracteres.\n"
            "Por favor, resuma a informação."
        )
        return DESCRICAO
    
    context.user_data["registro"]["descricao"] = descricao

    keyboard = [
        [
            InlineKeyboardButton("📷 Adicionar foto", callback_data="add_file"),
            InlineKeyboardButton("⏭️ Pular", callback_data="skip_file")
        ]
    ]

    await context.bot.send_message(
        chat_id,
        "📸 *Deseja enviar uma foto?*\n\n"
        "Uma foto ajuda muito na identificação do problema!",
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
        context.user_data["registro"]["photo_file_id"] = None
        await context.bot.send_message(
            chat_id,
            "📍 *Onde fica o problema?*\n\n"
            "Forneça o endereço ou ponto de referência. Exemplo:\n"
            "\"Esquina da Rua das Flores com Avenida Principal, próximo ao mercado\"",
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
        context.user_data["registro"]["photo_file_id"] = file.file_id

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
# ETAPA 4 — LOCAL (COM VALIDAÇÃO) - PARTE DA MELHORIA 1
# ============================================================
async def receber_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    local = update.message.text.strip()
    
    # Validação (MELHORIA 1)
    if len(local) < 5:
        await update.message.reply_text(
            "⚠️ Local muito vago. Por favor, forneça um endereço ou ponto de referência mais específico.\n"
            "Exemplo: \"Esquina da Rua das Flores com Avenida Principal\""
        )
        return LOCATION
    
    context.user_data["registro"]["local"] = local
    
    # Adicionar metadados (MELHORIA 5)
    context.user_data["registro"]["id"] = str(uuid.uuid4())[:8]
    context.user_data["registro"]["data"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    context.user_data["registro"]["user_id"] = update.effective_user.id
    
    # Mostrar preview e confirmar (MELHORIA 3)
    await mostrar_preview_registro(update, context)
    return CONFIRMACAO


# ============================================================
# PREVIEW E CONFIRMAÇÃO - MELHORIA 3
# ============================================================
async def mostrar_preview_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registro = context.user_data["registro"]
    chat_id = update.effective_chat.id
    
    msg = "📋 *Confirme os dados do registro:*\n\n"
    msg += f"📁 *Categoria:* {registro['categoria']}\n"
    msg += f"📝 *Descrição:* {registro['descricao']}\n"
    msg += f"📍 *Local:* {registro['local']}\n"
    msg += f"📅 *Data:* {registro['data']}\n"
    msg += f"🆔 *ID:* {registro['id']}\n"
    msg += f"📷 *Foto:* {'✅ Sim' if registro.get('photo_file_id') else '❌ Não'}\n\n"
    msg += "Tudo correto?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar e salvar", callback_data="confirm_save"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_save")
        ]
    ]
    
    if registro.get('photo_file_id'):
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=registro['photo_file_id'],
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
        registro = context.user_data["registro"]
        
        # Salvar no armazenamento (MELHORIA 2)
        if str(chat_id) not in user_data_store:
            user_data_store[str(chat_id)] = []
        
        user_data_store[str(chat_id)].append(registro)
        save_data()  # Persistência em JSON
        
        await query.edit_message_text(
            f"✅ *Registro salvo com sucesso!*\n\n"
            f"📋 ID do registro: {registro['id']}\n"
            f"📅 Data: {registro['data']}\n"
            f"📊 Total de registros: {len(user_data_store[str(chat_id)])}",
            parse_mode="Markdown"
        )
        
        # Limpar dados temporários
        context.user_data.pop("registro", None)
        
        await send_menu(update, context)
        return ConversationHandler.END
    
    elif query.data == "cancel_save":
        context.user_data.pop("registro", None)
        await query.edit_message_text(
            "❌ *Registro cancelado.*\n\n"
            "Os dados não foram salvos.",
            parse_mode="Markdown"
        )
        await send_menu(update, context)
        return ConversationHandler.END


# ============================================================
# HANDLER DE ERROS - MELHORIA 8
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
    entry_points=[CallbackQueryHandler(menu_callback, pattern="^(registrar|listar)$")],

    states={
        CATEGORIA: [CallbackQueryHandler(escolher_categoria, pattern="^cat:")],
        DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
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
app.add_handler(CommandHandler("ajuda", ajuda))  # MELHORIA 9
app.add_handler(registrar_handler)

# qualquer texto → abre menu
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_menu))

# Handler de erros (MELHORIA 8)
app.add_error_handler(error_handler)

if __name__ == "__main__":
    print("🤖 Bot iniciado com as melhorias solicitadas!")
    print("✅ Melhorias implementadas:")
    print("   1. ✅ Validação de dados (descrição e local)")
    print("   2. ✅ Persistência com JSON")
    print("   3. ✅ Preview antes de salvar")
    print("   4. ✅ Limite de registros por usuário (10)")
    print("   5. ✅ Timestamps e IDs únicos")
    print("   8. ✅ Handler de erros")
    print("   9. ✅ /ajuda com instruções")
    print("  10. ✅ Backup manual (salvamento em arquivo)")
    print("❌ Removido: /meusregistros e limpar registros")
    print("❌ Removido: Agendamento automático (não compatível com Render)")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/",
    )
