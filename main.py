import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# Config via .env
# =========================
def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v.strip()

def _env_int(name: str, default: int | None = None) -> int | None:
    v = _env(name, None)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        raise ValueError(f"Env var {name} must be an integer (got {v!r})")

def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    v = _env(name, None)
    if v is None:
        return default or []
    # comma-separated list
    return [x.strip() for x in v.split(",") if x.strip()]

TOKEN = _env("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN in .env")

SERVER_NAME = _env("SERVER_NAME", "Your Discord Server")
BRAND_ICON_URL = _env("BRAND_ICON_URL", "")  # optional
BRAND_THUMB_URL = _env("BRAND_THUMB_URL", BRAND_ICON_URL)  # optional

# Category IDs for each ticket type
CATEGORY_IDS = {
    "suporte": _env_int("CATEGORY_SUPORTE_ID"),
    "denúncia": _env_int("CATEGORY_DENUNCIA_ID"),
    "financeiro": _env_int("CATEGORY_FINANCEIRO_ID"),
    "roleplay": _env_int("CATEGORY_ROLEPLAY_ID"),
}

ARCHIVE_CATEGORY_ID = _env_int("ARCHIVE_CATEGORY_ID")

# Role names that can view each ticket type (comma-separated in .env)
SUPORTE_ROLES = _env_list("SUPORTE_ROLES", ["Support", "Moderator", "Admin"])
DENUNCIA_ROLES = _env_list("DENUNCIA_ROLES", ["Moderator", "Admin"])
FINANCEIRO_ROLES = _env_list("FINANCEIRO_ROLES", ["Admin"])
ROLEPLAY_ROLES = _env_list("ROLEPLAY_ROLES", ["Roleplay Team", "Admin"])

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ticket_counters = {"suporte": 0, "denúncia": 0, "financeiro": 0, "roleplay": 0}

COUNTERS_FILE = _env("COUNTERS_FILE", "ticket_counters.json")


def save_ticket_counters():
    try:
        with open(COUNTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(ticket_counters, f, indent=4, ensure_ascii=False)
        print(f"Contadores salvos: {ticket_counters}")
    except Exception as e:
        print(f"Erro ao salvar contadores: {e}")


def load_ticket_counters():
    global ticket_counters
    try:
        if os.path.exists(COUNTERS_FILE):
            with open(COUNTERS_FILE, "r", encoding="utf-8") as f:
                loaded_counters = json.load(f)
                print(f"Contadores carregados do arquivo: {loaded_counters}")
                ticket_counters.update(loaded_counters)
                print(f"Contadores atualizados: {ticket_counters}")
        else:
            print("Arquivo de contadores não encontrado, criando novo...")
            save_ticket_counters()
    except Exception as e:
        print(f"Erro ao carregar contadores: {e}")
        save_ticket_counters()


async def get_roles_by_names(guild: discord.Guild, role_names: list[str]):
    roles = []
    for role_name in role_names:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            roles.append(role)
    return roles


def brand_footer(text: str) -> dict:
    # Helper to keep branding configurable
    if BRAND_ICON_URL:
        return {"text": text, "icon_url": BRAND_ICON_URL}
    return {"text": text}


def brand_thumbnail(embed: discord.Embed):
    if BRAND_THUMB_URL:
        embed.set_thumbnail(url=BRAND_THUMB_URL)


async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str, user: discord.Member):
    guild = interaction.guild

    category_id = CATEGORY_IDS.get(ticket_type.lower())
    if not category_id:
        return None

    category = guild.get_channel(category_id)
    if not category:
        return None

    ticket_counters[ticket_type.lower()] += 1
    ticket_number = ticket_counters[ticket_type.lower()]

    save_ticket_counters()

    print(f"Criando ticket {ticket_type} #{ticket_number}")

    channel_name = f"{ticket_type.lower()}-{ticket_number}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    if ticket_type.lower() == "suporte":
        roles_with_access = await get_roles_by_names(guild, SUPORTE_ROLES)
    elif ticket_type.lower() == "denúncia":
        roles_with_access = await get_roles_by_names(guild, DENUNCIA_ROLES)
    elif ticket_type.lower() == "roleplay":
        roles_with_access = await get_roles_by_names(guild, ROLEPLAY_ROLES)
    elif ticket_type.lower() == "financeiro":
        roles_with_access = await get_roles_by_names(guild, FINANCEIRO_ROLES)
    else:
        roles_with_access = []

    for role in roles_with_access:
        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    bot_member = guild.get_member(bot.user.id)
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    ticket_channel = await category.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"Ticket de {ticket_type} - {user.display_name}",
    )

    return ticket_channel


async def create_ticket_embed(ticket_type: str, user: discord.Member, description: str | None = None):
    colors = {
        "Suporte": 0x3498DB,
        "Denúncia": 0xE74C3C,
        "Financeiro": 0x2ECC71,
        "Roleplay": 0x9B59B6,
    }

    descriptions = {
        "Suporte": "🔧 **Atendimento de Suporte**\nNossa equipe irá ajudar com dúvidas e problemas técnicos.",
        "Denúncia": "🚨 **Central de Denúncias**\nRelate situações que violem regras e diretrizes.",
        "Financeiro": "💰 **Departamento Financeiro**\nAtendimento sobre pagamentos, reembolsos e doações.",
        "Roleplay": "🎭 **Equipe Roleplay**\nSolicitações, histórias, personagens e assuntos de RP.",
    }

    embed = discord.Embed(
        title=f"🎫 {ticket_type.upper()} - {SERVER_NAME}",
        description=descriptions.get(ticket_type, ""),
        color=colors.get(ticket_type, 0x3498DB),
        timestamp=datetime.datetime.utcnow(),
    )

    embed.add_field(
        name="👤 **INFORMAÇÕES DO SOLICITANTE**",
        value=(
            f"• **Usuário:** {user.mention}\n"
            f"• **ID:** `{user.id}`\n"
            f"• **Conta criada:** {discord.utils.format_dt(user.created_at, 'R')}"
        ),
        inline=False,
    )

    embed.add_field(
        name="📋 **DETALHES DO TICKET**",
        value=(
            f"• **Tipo:** {ticket_type}\n"
            f"• **Status:** 🟢 **Aberto**\n"
            f"• **Criado em:** {discord.utils.format_dt(datetime.datetime.now(), 'F')}"
        ),
        inline=True,
    )

    priorities = {"Suporte": "🟡 Média", "Denúncia": "🔴 Alta", "Financeiro": "🟢 Normal", "Roleplay": "🟣 Especial"}

    embed.add_field(
        name="⚡ **INFORMAÇÕES DO ATENDIMENTO**",
        value=(
            f"• **Prioridade:** {priorities.get(ticket_type, '🟡 Média')}\n"
            f"• **Setor:** {ticket_type}\n"
            f"• **Ticket ID:** `{ticket_counters[ticket_type.lower()]}`"
        ),
        inline=True,
    )

    if description:
        embed.add_field(name="📝 **DESCRIÇÃO DA SOLICITAÇÃO**", value=f"```{description}```", inline=False)

    embed.add_field(
        name="💡 **PRÓXIMOS PASSOS**",
        value=(
            "• Aguarde a equipe responder\n"
            "• Mantenha educação e paciência\n"
            "• Envie informações adicionais se solicitado\n"
            "• Evite marcar a equipe desnecessariamente"
        ),
        inline=False,
    )

    embed.set_footer(**brand_footer(f"{SERVER_NAME} | Sistema de Tickets"))
    brand_thumbnail(embed)
    embed.set_thumbnail(url=user.display_avatar.url)

    return embed


class TicketMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 Suporte", style=discord.ButtonStyle.primary, custom_id="persistent:ticket_support")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket_creation(interaction, "Suporte")

    @discord.ui.button(label="🚨 Denúncia", style=discord.ButtonStyle.danger, custom_id="persistent:ticket_report")
    async def report_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket_creation(interaction, "Denúncia")

    @discord.ui.button(label="🎭 Roleplay", style=discord.ButtonStyle.secondary, custom_id="persistent:ticket_roleplay")
    async def roleplay_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket_creation(interaction, "Roleplay")

    @discord.ui.button(label="💰 Financeiro", style=discord.ButtonStyle.success, custom_id="persistent:ticket_financial")
    async def financial_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_ticket_creation(interaction, "Financeiro")

    async def handle_ticket_creation(self, interaction: discord.Interaction, ticket_type: str):
        guild = interaction.guild
        user = interaction.user

        category_id = CATEGORY_IDS.get(ticket_type.lower())
        if not category_id:
            await interaction.response.send_message("❌ Categoria não configurada (env).", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        if not category:
            await interaction.response.send_message("❌ Categoria não encontrada.", ephemeral=True)
            return

        for channel in category.channels:
            if user in channel.members:
                embed = discord.Embed(
                    title=f"🎫 **TICKET JÁ ABERTO - {SERVER_NAME}**",
                    description=f"Olá {user.mention}, você já possui um ticket deste tipo em andamento.",
                    color=0xF39C12,
                    timestamp=datetime.datetime.utcnow(),
                )
                embed.add_field(
                    name="📋 **TICKET ATUAL**",
                    value=(
                        f"• **Canal:** {channel.mention}\n"
                        f"• **Tipo:** {ticket_type}\n"
                        f"• **Status:** 🟡 **Em Andamento**\n"
                        f"• **Aberto há:** {discord.utils.format_dt(channel.created_at, 'R')}"
                    ),
                    inline=False,
                )
                embed.set_footer(**brand_footer(f"{SERVER_NAME} | Sistema de Tickets"))
                brand_thumbnail(embed)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        modal = TicketModal(ticket_type)
        await interaction.response.send_modal(modal)


class TicketModal(discord.ui.Modal, title="Abrir Ticket"):
    def __init__(self, ticket_type: str):
        super().__init__()
        self.ticket_type = ticket_type
        self.description = discord.ui.TextInput(
            label="Descrição",
            placeholder="Descreva o motivo do ticket...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        ticket_channel = await create_ticket_channel(interaction, self.ticket_type, interaction.user)
        if not ticket_channel:
            await interaction.followup.send("❌ Erro ao criar ticket.", ephemeral=True)
            return

        embed = await create_ticket_embed(self.ticket_type, interaction.user, self.description.value)
        view = TicketControlView()

        if self.ticket_type.lower() == "suporte":
            roles = await get_roles_by_names(interaction.guild, SUPORTE_ROLES)
        elif self.ticket_type.lower() == "denúncia":
            roles = await get_roles_by_names(interaction.guild, DENUNCIA_ROLES)
        elif self.ticket_type.lower() == "roleplay":
            roles = await get_roles_by_names(interaction.guild, ROLEPLAY_ROLES)
        elif self.ticket_type.lower() == "financeiro":
            roles = await get_roles_by_names(interaction.guild, FINANCEIRO_ROLES)
        else:
            roles = []

        mention = " ".join(role.mention for role in roles if role)

        await ticket_channel.send(content=f"{interaction.user.mention} {mention}".strip(), embed=embed, view=view)

        confirm_embed = discord.Embed(
            title="✅ **TICKET CRIADO!**",
            description=f"Seu ticket de **{self.ticket_type}** foi criado e a equipe foi notificada.",
            color=0x2ECC71,
            timestamp=datetime.datetime.utcnow(),
        )

        confirm_embed.add_field(
            name="📋 **DETALHES**",
            value=(
                f"• **Canal:** {ticket_channel.mention}\n"
                f"• **Tipo:** {self.ticket_type}\n"
                f"• **Número:** `{ticket_counters[self.ticket_type.lower()]}`"
            ),
            inline=False,
        )

        confirm_embed.set_footer(**brand_footer(SERVER_NAME))
        brand_thumbnail(confirm_embed)

        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger, custom_id="persistent:close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_permission(interaction):
            embed = discord.Embed(
                title="❌ **ACESSO NEGADO**",
                description="Você não possui permissão para fechar este ticket.",
                color=0xE74C3C,
                timestamp=datetime.datetime.utcnow(),
            )
            embed.set_footer(**brand_footer(SERVER_NAME))
            brand_thumbnail(embed)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="🔒 **CONFIRMAR FECHAMENTO**",
            description="Você está prestes a fechar e arquivar este ticket. Esta ação é **irreversível**.",
            color=0xE74C3C,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(**brand_footer(SERVER_NAME))
        brand_thumbnail(embed)

        view = ConfirmCloseView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📋 Transcript", style=discord.ButtonStyle.secondary, custom_id="persistent:transcript")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 **TRANSCRIPT SOLICITADO**",
            description="(Placeholder) Aqui você pode implementar geração de transcript (TXT/PDF).",
            color=0x3498DB,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(**brand_footer(SERVER_NAME))
        brand_thumbnail(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def has_permission(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        channel = interaction.channel

        if user.guild_permissions.administrator:
            return True

        user_roles = [role.name for role in user.roles]
        channel_name = channel.name.lower()

        if channel_name.startswith("suporte-"):
            return any(role in user_roles for role in SUPORTE_ROLES)
        elif channel_name.startswith("denúncia-"):
            return any(role in user_roles for role in DENUNCIA_ROLES)
        elif channel_name.startswith("roleplay-"):
            return any(role in user_roles for role in ROLEPLAY_ROLES)
        elif channel_name.startswith("financeiro-"):
            return any(role in user_roles for role in FINANCEIRO_ROLES)

        return False


class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    def get_ticket_type(self, channel_name: str) -> str:
        if channel_name.startswith("suporte-"):
            return "Suporte"
        elif channel_name.startswith("denúncia-"):
            return "Denúncia"
        elif channel_name.startswith("financeiro-"):
            return "Financeiro"
        elif channel_name.startswith("roleplay-"):
            return "Roleplay"
        elif channel_name.startswith("arquivado-"):
            return "Arquivado"
        return "Desconhecido"

    async def get_ticket_opener(self, channel: discord.TextChannel):
        async for message in channel.history(limit=10, oldest_first=True):
            if message.author.bot and message.mentions:
                return message.mentions[0]
        return None

    async def get_ticket_duration(self, channel: discord.TextChannel) -> str:
        try:
            creation_time = channel.created_at
            now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            duration = now - creation_time

            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        except Exception:
            return "Não calculada"

    @discord.ui.button(label="✅ Confirmar Fechamento", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild

        close_embed = discord.Embed(
            title=f"🔒 **TICKET FECHADO - {SERVER_NAME}**",
            description="Este ticket foi encerrado e arquivado.",
            color=0xE74C3C,
            timestamp=datetime.datetime.utcnow(),
        )
        close_embed.set_footer(**brand_footer(SERVER_NAME))
        brand_thumbnail(close_embed)
        await interaction.response.send_message(embed=close_embed)

        opener = await self.get_ticket_opener(channel)
        closer = interaction.user
        duration = await self.get_ticket_duration(channel)

        await self.archive_ticket(channel, guild, opener, closer, duration)

        try:
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            pass

        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ **AÇÃO CANCELADA**",
            description="O ticket permanecerá aberto.",
            color=0x95A5A6,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(**brand_footer(SERVER_NAME))
        brand_thumbnail(embed)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        except discord.errors.NotFound:
            pass

        self.stop()

    async def archive_ticket(self, channel: discord.TextChannel, guild: discord.Guild, opener, closer, duration: str):
        if not ARCHIVE_CATEGORY_ID:
            # If not configured, just lock the channel and rename it.
            await channel.edit(name=f"arquivado-{channel.name}")
            await channel.set_permissions(guild.default_role, send_messages=False, read_messages=False)
            return

        try:
            archive_category = guild.get_channel(ARCHIVE_CATEGORY_ID)
            if archive_category:
                await channel.edit(category=archive_category, sync_permissions=True)

            new_name = f"arquivado-{channel.name}"
            if not new_name.startswith("arquivado-"):
                await channel.edit(name=new_name)

            staff_roles = await get_roles_by_names(
                guild, SUPORTE_ROLES + DENUNCIA_ROLES + FINANCEIRO_ROLES + ROLEPLAY_ROLES
            )

            for member in channel.members:
                if member.bot:
                    continue
                is_staff = any(role in member.roles for role in staff_roles) or member.guild_permissions.administrator
                if not is_staff and member != opener:
                    await channel.set_permissions(member, read_messages=False, send_messages=False)

            await channel.set_permissions(guild.default_role, send_messages=False)

        except Exception as e:
            print(f"Erro ao arquivar ticket: {e}")


@bot.tree.command(name="ticket", description="Cria o menu de tickets")
@app_commands.default_permissions(administrator=True)
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"🎫 **SISTEMA DE TICKETS - {SERVER_NAME}**",
        description="Selecione abaixo o tipo de atendimento desejado.",
        color=0x9B59B6,
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_footer(**brand_footer(SERVER_NAME))
    brand_thumbnail(embed)

    view = TicketMenuView()
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="config", description="Mostra configurações")
@app_commands.default_permissions(administrator=True)
async def config(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=f"⚙️ **CONFIG - {SERVER_NAME}**",
        description="Configurações atuais do sistema de tickets",
        color=0xF39C12,
        timestamp=datetime.datetime.utcnow(),
    )

    cats_info = []
    for ticket_type, cat_id in CATEGORY_IDS.items():
        if not cat_id:
            cats_info.append(f"• **{ticket_type.title()}:** ❌ Não configurada (env)")
            continue
        cat = guild.get_channel(cat_id)
        status = "✅ Operacional" if cat else "❌ Não encontrada"
        cats_info.append(f"• **{ticket_type.title()}:** {status} | `{cat_id}`")

    embed.add_field(name="📁 **CATEGORIAS**", value="\n".join(cats_info), inline=False)
    embed.add_field(
        name="📊 **CONTADORES**",
        value="\n".join([f"• **{k.title()}:** `{v}`" for k, v in ticket_counters.items()]),
        inline=False,
    )

    embed.set_footer(**brand_footer(SERVER_NAME))
    brand_thumbnail(embed)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="add", description="Adiciona membro ao ticket")
async def add(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if not any(channel.name.startswith(prefix) for prefix in ["suporte-", "denúncia-", "financeiro-", "roleplay-"]):
        await interaction.response.send_message("❌ Use em um ticket.", ephemeral=True)
        return
    await channel.set_permissions(member, read_messages=True, send_messages=True)
    await interaction.response.send_message(f"✅ {member.mention} adicionado.")


@bot.tree.command(name="remove", description="Remove membro do ticket")
async def remove(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if not any(channel.name.startswith(prefix) for prefix in ["suporte-", "denúncia-", "financeiro-", "roleplay-"]):
        await interaction.response.send_message("❌ Use em um ticket.", ephemeral=True)
        return
    await channel.set_permissions(member, read_messages=False, send_messages=False)
    await interaction.response.send_message(f"✅ {member.mention} removido.")


@bot.tree.command(name="test", description="Testa o bot")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot funcionando!", ephemeral=True)


def setup_persistent_views():
    bot.add_view(TicketMenuView())
    bot.add_view(TicketControlView())


@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} conectado!")
    setup_persistent_views()

    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

    activity = discord.Activity(type=discord.ActivityType.watching, name=_env("PRESENCE_TEXT", "seus tickets 👀"))
    await bot.change_presence(activity=activity, status=discord.Status.online)


load_ticket_counters()

if __name__ == "__main__":
    bot.run(TOKEN)
