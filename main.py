import discord
from discord.ext import commands
import random
import asyncio
import os
from keep_alive import keep_alive
import json

# Configuration des intents (une seule fois)
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

# IDs des canaux et rôles
LOG_CHANNEL_ID = 1331393513903886429
LOG_TICKET_ID = 1333434654493249587
MUTE_ROLE_ID = 1350466883295641600
ADMIN_ROLE_ID = 1331397374509060258
ROLE_JOIN_ID = 1351476247904911421
GIVEAWAY_WINNER_ROLE_ID = 1350262712696967199

# Liste des mots interdits
MOTS_INTERDITS = [
    "fdp", "tg","pute","enculé"
]

# Dictionnaire global pour les avertissements (un seul système)
warnings = {}

# Dictionnaire pour suivre les giveaways actifs
giveaways = {}

class PersistentViewBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistent_views_added = False

bot = PersistentViewBot(command_prefix="!", intents=intents, case_insensitive=True)
tickets = {}

# Fonction pour journaliser les actions
async def log_action(ctx, action, member, role=None, reason=None):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        if role:
            await log_channel.send(f'**{action}** : {ctx.author.mention} a {action} le rôle {role.name} à {member.mention}.')
        elif reason:
            await log_channel.send(f'**{action}** : {member.mention} ({member.id})\n📌 Raison : {reason}')
        else:
            await log_channel.send(f'**{action}** : {member.mention} ({member.id})')

# Classes pour les vues des tickets
class CloseTicketView(discord.ui.View):
    def __init__(self, creator_id=None):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Fermer le ticket",
                      style=discord.ButtonStyle.danger,
                      custom_id="close_ticket_button")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Vérifier si l'utilisateur a le droit de fermer le ticket
        channel_id = interaction.channel.id

        # Si le ticket est dans notre dictionnaire, vérifier le créateur
        if channel_id in tickets:
            creator_id = tickets[channel_id]["creator_id"]
            if interaction.user.id != creator_id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Tu n'es pas autorisé à fermer ce ticket.",
                    ephemeral=True)
                return
        # Sinon, utiliser le creator_id de la classe ou vérifier les permissions d'admin
        elif self.creator_id is not None and interaction.user.id != self.creator_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Tu n'es pas autorisé à fermer ce ticket.",
                ephemeral=True)
            return

        # Informer que le ticket va être fermé
        await interaction.response.send_message(
            "🔒 Fermeture du ticket en cours...",
            ephemeral=True)

        # Supprimer le ticket du dictionnaire
        if channel_id in tickets:
            del tickets[channel_id]

        # Log de l'action
        log_channel = discord.utils.get(interaction.guild.text_channels, id=LOG_TICKET_ID)
        if log_channel:
            await log_channel.send(
                f"🔒 **Fermeture de ticket**\n**Utilisateur** : {interaction.user.mention} ({interaction.user.id})\n**Ticket fermé** : {interaction.channel.name}."
            )

        # Supprimer le canal
        await interaction.channel.delete()
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔰 Candidature staff",
                      style=discord.ButtonStyle.primary,
                      custom_id="ticket_category_staff")
    async def ticket_button_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "📌 Candidatures")

    @discord.ui.button(label="💡 Besoin d'aide",
                      style=discord.ButtonStyle.primary,
                      custom_id="ticket_category_aide")
    async def ticket_button_aide(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "❓ Aide")

    @discord.ui.button(label="🚫 Demande de deban",
                      style=discord.ButtonStyle.primary,
                      custom_id="ticket_category_deban")
    async def ticket_button_deban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "🚫 Débannissement")
        
    @discord.ui.button(label="🤝 Candidature partenaire",
                      style=discord.ButtonStyle.primary,
                      custom_id="ticket_category_partner")
    async def ticket_button_partner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "🤝 Partenariats")

    async def create_ticket(self, interaction: discord.Interaction,
                           category_name: str):
        user = interaction.user
        guild = interaction.guild

        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            await interaction.response.send_message(
                f"❌ La catégorie `{category_name}` n'existe pas. Contacte un admin !",
                ephemeral=True)
            return

        ticket_name = f"ticket-{user.name}"
        ticket_channel = await guild.create_text_channel(ticket_name,
                                                        category=category)

        # Stocker les informations du ticket dans le dictionnaire global
        tickets[ticket_channel.id] = {
            "creator_id": user.id,
            "creator_name": user.name,
            "channel_id": ticket_channel.id,
            "channel_name": ticket_channel.name,
            "category": category_name,
            "members": [user.id]
        }

        await ticket_channel.set_permissions(guild.default_role,
                                            read_messages=False)
        await ticket_channel.set_permissions(user,
                                            read_messages=True,
                                            send_messages=True)

        log_channel = discord.utils.get(guild.text_channels, id=LOG_TICKET_ID)
        if log_channel:
            await log_channel.send(
                f"🔓 **Ouverture de ticket**\n**Utilisateur** : {user.mention} ({user.id})\n**Ticket créé** : {ticket_channel.mention} dans la catégorie `{category_name}`."
            )
        else:
            print(
                f"❌ Le canal de logs avec l'ID {LOG_TICKET_ID} est introuvable dans le serveur {guild.name}."
            )

        # Créer une instance de la vue de fermeture avec l'ID du créateur
        close_view = CloseTicketView(user.id)

        await ticket_channel.send(
            f"👋 Salut {user.mention}, ton ticket a été créé dans la catégorie `{category_name}`.\nUtilise le bouton ci-dessous pour fermer ce ticket une fois ton problème résolu.",
            view=close_view)
        await interaction.response.send_message(
            f"✅ Ton ticket a été créé : {ticket_channel.mention}",
            ephemeral=True)

# Commandes pour renommer et gérer les membres des tickets
@bot.command(name="renameticket")
async def rename_ticket(ctx, *, nouveau_nom: str):
    """Renomme le ticket actuel."""
    # Vérifier si le canal est un ticket
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
        return

    # Vérifier si le ticket est dans notre dictionnaire
    if ctx.channel.id not in tickets:
        # Si le ticket n'est pas dans le dictionnaire, vérifier les permissions
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission de renommer ce ticket.")
            return
    else:
        # Si le ticket est dans le dictionnaire, vérifier si l'utilisateur est le créateur ou un admin
        if ctx.author.id != tickets[ctx.channel.id]["creator_id"] and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission de renommer ce ticket.")
            return

    # Renommer le canal
    try:
        await ctx.channel.edit(name=f"ticket-{nouveau_nom}")

        # Mettre à jour le dictionnaire si le ticket y est
        if ctx.channel.id in tickets:
            tickets[ctx.channel.id]["channel_name"] = f"ticket-{nouveau_nom}"

        await ctx.send(f"✅ Le ticket a été renommé en `ticket-{nouveau_nom}`.")

        # Log de l'action
        log_channel = discord.utils.get(ctx.guild.text_channels, id=LOG_TICKET_ID)
        if log_channel:
            await log_channel.send(
                f"🔄 **Ticket renommé**\n**Utilisateur** : {ctx.author.mention} ({ctx.author.id})\n**Ticket** : {ctx.channel.mention}\n**Nouveau nom** : `ticket-{nouveau_nom}`"
            )
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de renommer ce canal.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Une erreur s'est produite lors du renommage du canal : {e}")

@bot.command(name="addmember")
async def add_member(ctx, member: discord.Member):
    """Ajoute un membre au ticket actuel."""
    # Vérifier si le canal est un ticket
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
        return

    # Vérifier si le ticket est dans notre dictionnaire
    if ctx.channel.id not in tickets:
        # Si le ticket n'est pas dans le dictionnaire, vérifier les permissions
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission d'ajouter des membres à ce ticket.")
            return
    else:
        # Si le ticket est dans le dictionnaire, vérifier si l'utilisateur est le créateur ou un admin
        if ctx.author.id != tickets[ctx.channel.id]["creator_id"] and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission d'ajouter des membres à ce ticket.")
            return

    # Ajouter le membre au ticket
    try:
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)

        # Mettre à jour le dictionnaire si le ticket y est
        if ctx.channel.id in tickets and member.id not in tickets[ctx.channel.id]["members"]:
            tickets[ctx.channel.id]["members"].append(member.id)

        await ctx.send(f"✅ {member.mention} a été ajouté au ticket.")

        # Log de l'action
        log_channel = discord.utils.get(ctx.guild.text_channels, id=LOG_TICKET_ID)
        if log_channel:
            await log_channel.send(
                f"➕ **Membre ajouté au ticket**\n**Utilisateur** : {ctx.author.mention} ({ctx.author.id})\n**Membre ajouté** : {member.mention} ({member.id})\n**Ticket** : {ctx.channel.mention}"
            )
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de modifier les permissions de ce canal.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Une erreur s'est produite lors de l'ajout du membre : {e}")

@bot.command(name="removemember")
async def remove_member(ctx, member: discord.Member):
    """Retire un membre du ticket actuel."""
    # Vérifier si le canal est un ticket
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
        return

    # Vérifier si le ticket est dans notre dictionnaire
    if ctx.channel.id not in tickets:
        # Si le ticket n'est pas dans le dictionnaire, vérifier les permissions
        if not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission de retirer des membres de ce ticket.")
            return
    else:
        # Si le ticket est dans le dictionnaire, vérifier si l'utilisateur est le créateur ou un admin
        if ctx.author.id != tickets[ctx.channel.id]["creator_id"] and not ctx.author.guild_permissions.manage_channels:
            await ctx.send("❌ Tu n'as pas la permission de retirer des membres de ce ticket.")
            return

        # Vérifier que le membre n'est pas le créateur du ticket
        if member.id == tickets[ctx.channel.id]["creator_id"]:
            await ctx.send("❌ Tu ne peux pas retirer le créateur du ticket.")
            return

    # Vérifier que le membre n'est pas un administrateur
    if member.guild_permissions.administrator and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Tu ne peux pas retirer un administrateur du ticket.")
        return

    # Retirer le membre du ticket
    try:
        await ctx.channel.set_permissions(member, overwrite=None)

        # Mettre à jour le dictionnaire si le ticket y est
        if ctx.channel.id in tickets and member.id in tickets[ctx.channel.id]["members"]:
            tickets[ctx.channel.id]["members"].remove(member.id)

        await ctx.send(f"✅ {member.mention} a été retiré du ticket.")

        # Log de l'action
        log_channel = discord.utils.get(ctx.guild.text_channels, id=LOG_TICKET_ID)
        if log_channel:
            await log_channel.send(
                f"➖ **Membre retiré du ticket**\n**Utilisateur** : {ctx.author.mention} ({ctx.author.id})\n**Membre retiré** : {member.mention} ({member.id})\n**Ticket** : {ctx.channel.mention}"
            )
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de modifier les permissions de ce canal.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Une erreur s'est produite lors du retrait du membre : {e}")

@bot.command(name="listtickets")
async def list_tickets(ctx):
    """Liste tous les tickets actifs."""
    # Vérifier les permissions
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    if not tickets:
        await ctx.send("📝 Aucun ticket actif pour le moment.")
        return

    # Créer un embed pour afficher les tickets
    embed = discord.Embed(
        title="📝 Liste des tickets actifs",
        color=discord.Color.blue(),
        description=f"Il y a actuellement {len(tickets)} ticket(s) actif(s)."
    )

    for ticket_id, ticket_info in tickets.items():
        creator = ctx.guild.get_member(ticket_info["creator_id"])
        creator_name = creator.name if creator else ticket_info["creator_name"]

        # Obtenir les noms des membres
        members = []
        for member_id in ticket_info["members"]:
            member = ctx.guild.get_member(member_id)
            if member:
                members.append(member.name)

        members_str = ", ".join(members) if members else "Aucun"

        # Ajouter un champ pour ce ticket
        embed.add_field(
            name=f"🎫 {ticket_info['channel_name']}",
            value=f"**Créateur:** {creator_name}\n"
                  f"**Catégorie:** {ticket_info['category']}\n"
                  f"**Membres:** {members_str}\n"
                  f"**Lien:** <#{ticket_id}>",
            inline=False
        )

    await ctx.send(embed=embed)

class Ticket:
    def __init__(self, id_ticket, nom, membres=None):
        self.id_ticket = id_ticket
        self.nom = nom
        self.membres = membres if membres else []

    def rename_ticket(self, nouveau_nom):
        """Renomme le ticket."""
        self.nom = nouveau_nom
        print(f"Le ticket {self.id_ticket} a été renommé en '{self.nom}'.")

    def ajouter_membre(self, membre):
        """Ajoute un membre au ticket."""
        if membre not in self.membres:
            self.membres.append(membre)
            print(f"{membre} a été ajouté au ticket {self.id_ticket}.")
        else:
            print(f"{membre} est déjà membre du ticket {self.id_ticket}.")

    def retirer_membre(self, membre):
        """Retire un membre du ticket."""
        if membre in self.membres:
            self.membres.remove(membre)
            print(f"{membre} a été retiré du ticket {self.id_ticket}.")
        else:
            print(f"{membre} n'est pas membre du ticket {self.id_ticket}.")

# Exemple d'utilisation
ticket1 = Ticket(1, "Bug Interface", ["Alice", "Bob"])
ticket1.rename_ticket("Correction Interface")
ticket1.ajouter_membre("Charlie")
ticket1.retirer_membre("Alice")

# Événements du bot
@bot.event
async def on_ready():
    print(f"{bot.user.name} est connecté !")

    # Afficher toutes les commandes enregistrées pour le débogage
    commands_list = [command.name for command in bot.commands]
    print(f"Commandes enregistrées: {', '.join(commands_list)}")

    if not bot.persistent_views_added:
        # Ajouter la vue des tickets
        bot.add_view(TicketView())

        # Ajouter une vue générique pour les boutons de fermeture
        # Utiliser None comme creator_id pour que les admins puissent toujours fermer
        bot.add_view(CloseTicketView(None))

        bot.persistent_views_added = True

        # Rechercher les canaux de ticket existants et les ajouter au dictionnaire
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.name.startswith("ticket-"):
                    # Essayer de trouver le créateur du ticket
                    creator_id = None
                    creator_name = "Inconnu"
                    members = []

                    # Vérifier les permissions pour trouver le créateur et les membres
                    for target, permissions in channel.overwrites.items():
                        if isinstance(target, discord.Member) and permissions.read_messages:
                            if creator_id is None:
                                creator_id = target.id
                                creator_name = target.name
                            members.append(target.id)

                    # Ajouter le ticket au dictionnaire
                    if creator_id:
                        tickets[channel.id] = {
                            "creator_id": creator_id,
                            "creator_name": creator_name,
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "category": channel.category.name if channel.category else "Sans catégorie",
                            "members": members
                        }
                        print(f"Ticket existant trouvé et ajouté : {channel.name}")

    # Rechercher les canaux de support pour les tickets
    for guild in bot.guilds:
        support_channel = discord.utils.get(guild.text_channels, name="ticket-support")
        if support_channel:
            has_ticket_message = False
            async for message in support_channel.history(limit=100):
                if message.author == bot.user and "Choisis une catégorie pour ton ticket" in message.content:
                    has_ticket_message = True
                    # S'assurer que la vue est attachée au message
                    bot.add_view(TicketView(), message_id=message.id)
                    print(f"Message de ticket déjà présent dans {guild.name}")
                    break

            if not has_ticket_message:
                view = TicketView()
                await support_channel.send(
                    "📝 **Choisis une catégorie pour ton ticket :**", view=view)
                print(f"Message de ticket créé dans {guild.name}")

@bot.event
async def on_member_join(member):
    """Attribue un rôle à un utilisateur lorsqu'il rejoint le serveur."""
    role = discord.utils.get(member.guild.roles, id=ROLE_JOIN_ID)
    if role:
        try:
            await member.add_roles(role)
            print(f"Le rôle {role.name} a été attribué à {member.name}.")
        except discord.Forbidden:
            print(f"Erreur : Le bot n'a pas la permission d'attribuer ce rôle.")
        except Exception as e:
            print(f"Erreur inconnue : {e}")

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return

    # Vérifier si la réaction est pour un giveaway
    for giveaway_id, giveaway_data in list(giveaways.items()):
        if reaction.message.id == giveaway_id and str(reaction.emoji) == "🎉":
            giveaway_data["participants"].add(user)
            print(f"{user.name} a participé au giveaway.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Vérifier si l'utilisateur a le rôle administrateur
    admin_role = discord.utils.get(message.author.roles, id=ADMIN_ROLE_ID)
    is_admin = admin_role is not None

    # Vérification des mots interdits
    for mot in MOTS_INTERDITS:
        if mot in message.content.lower():
            # Supprimer le message pour tout le monde (y compris les admins)
            try:
                await message.delete()
            except discord.errors.NotFound:
                # Le message a déjà été supprimé ou n'existe plus
                print(f"Message introuvable lors de la tentative de suppression.")
                pass
            except discord.errors.Forbidden:
                # Le bot n'a pas la permission de supprimer le message
                print(f"Permission refusée lors de la tentative de suppression d'un message.")
                pass
            except Exception as e:
                # Autre erreur
                print(f"Erreur lors de la suppression du message: {e}")
                pass

            # Appliquer les avertissements seulement pour les non-administrateurs
            if not is_admin:
                if message.author.id not in warnings:
                    warnings[message.author.id] = 0

                warnings[message.author.id] += 1

                await message.channel.send(f"{message.author.mention}, attention ! Ce mot est interdit. Avertissement {warnings[message.author.id]}/3")

                if warnings[message.author.id] >= 3:
                    try:
                        await message.author.kick(reason="Trop d'avertissements pour langage inapproprié.")
                        await message.channel.send(f"{message.author.mention} a été expulsé pour non-respect des règles.")
                    except discord.errors.Forbidden:
                        await message.channel.send(f"Je n'ai pas la permission d'expulser {message.author.mention}.")
                        print(f"Permission refusée lors de la tentative d'expulsion de {message.author.name}.")
                    except Exception as e:
                        print(f"Erreur lors de l'expulsion de {message.author.name}: {e}")

                # Ne pas traiter les commandes si un mot interdit a été détecté pour les non-admins
                return

            # Pour les admins, on continue le traitement des commandes après suppression du message
            break
    
    # Permettre le traitement des commandes
    await bot.process_commands(message)

# Commandes générales
@bot.command()
async def hello(ctx):
    role = discord.utils.get(ctx.author.roles, id=ADMIN_ROLE_ID)
    if role is None:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return
    await ctx.send(
        "Salut ! Je suis là pour t'aider. Utilise !commands pour voir toutes les commandes."
    )

@bot.command()
async def commands(ctx):
    role = discord.utils.get(ctx.author.roles, id=ADMIN_ROLE_ID)
    if role is None:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    command_list = (
         "**📜 Liste des commandes disponibles :**\n\n"
        "🎉 **Général :**\n"
        "➡️ `!hello` - Le bot répond avec un message sympa.\n"
        "➡️ `!commands` - Affiche cette liste de commandes.\n"
        "➡️ `!ticket` - Crée un message de création de ticket dans le canal `ticket-support`.\n"
        "➡️ `!giveaway <temps en secondes> <prix>` - Crée un giveaway.\n\n"
        "🛠 **Modération :**\n"
        "➡️ `!mute @utilisateur [temps en minutes] [raison]` - Mute un utilisateur.\n"
        "➡️ `!unmute @utilisateur` - Unmute un utilisateur.\n"
        "➡️ `!kick @utilisateur [raison]` - Expulse un utilisateur du serveur.\n"
        "➡️ `!ban @utilisateur [raison]` - Bannit un utilisateur du serveur.\n"
        "➡️ `!unban @utilisateur [raison]` - Débannit un utilisateur du serveur.\n"
        "➡️ `!warn @utilisateur [raison]` - Avertit un utilisateur.\n"
        "➡️ `!giveaway <temps en secondes> <prix>` - Lance un giveaway.\n\n"
        "📑 **Gestion des tickets :**\n"
        "➡️ `!ticket` - Crée un message de création de ticket dans le canal `ticket-support`.\n"
        "➡️ `!renameticket <nouveau_nom>` - Renomme un ticket.\n"
        "➡️ `!addmember @utilisateur` - Ajoute un membre au ticket.\n"
        "➡️ `!removemember @utilisateur` - Retire un membre du ticket.\n"
        "➡️ `!listtickets` - Affiche la liste des tickets actifs.\n\n"
        "🎭 **Gestion des rôles et mots interdits :**\n"
        "➡️ `!addrole @utilisateur @rôle` - Ajoute un rôle à un utilisateur.\n"
        "➡️ `!removerole @utilisateur @rôle` - Retire un rôle à un utilisateur.\n"
        "➡️ `!addword <mot>` - Ajoute un mot interdit à la liste.\n"
        "➡️ `!removeword <mot>` - Supprime un mot interdit de la liste.\n"
        "➡️ `!listwords` - Affiche la liste des mots interdits.\n"  
    )
    await ctx.send(command_list)

@bot.command()
async def ticket(ctx):
    role = discord.utils.get(ctx.author.roles, id=ADMIN_ROLE_ID)
    if role is None:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    support_channel = discord.utils.get(ctx.guild.text_channels,
                                      name="ticket-support")
    if not support_channel:
        await ctx.send(
            "❌ Aucun canal 'ticket-support' trouvé. Créez ce canal avant d'utiliser cette commande."
        )
        return

    view = TicketView()
    await support_channel.send("📝 **Choisis une catégorie pour ton ticket :**",
                              view=view)
    await ctx.send(
        f"✅ Message de création de ticket ajouté dans {support_channel.mention}"
    )

@bot.command()
async def giveaway(ctx, time: int, *, prize: str):
    role = discord.utils.get(ctx.author.roles, id=ADMIN_ROLE_ID)
    if role is None:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    # Vérifier s'il y a déjà un giveaway en cours
    if any(giveaways):
        await ctx.send("❌ Un giveaway est déjà en cours !")
        return

    giveaway_msg = await ctx.send(f"🎉 **GIVEAWAY** 🎉\n"
                                  f"🏆 Prix : {prize}\n"
                                  f"🕒 Temps restant : {time} secondes.\n"
                                  f"Réagis avec 🎉 pour participer !")

    await giveaway_msg.add_reaction("🎉")

    # Stocker les informations du giveaway avec l'ID du message comme clé
    giveaways[giveaway_msg.id] = {
        "prize": prize,
        "time": time,
        "message": giveaway_msg,
        "participants": set()
    }

    # Compte à rebours du giveaway
    remaining_time = time
    while remaining_time > 0:
        remaining_time -= 1
        await asyncio.sleep(1)
        if remaining_time % 10 == 0 or remaining_time <= 5:
            await giveaway_msg.edit(content=f"🎉 **GIVEAWAY** 🎉\n"
                                    f"🏆 Prix : {prize}\n"
                                    f"🕒 Temps restant : {remaining_time} secondes.\n"
                                    f"Réagis avec 🎉 pour participer !")

    # Vérifier s'il y a des participants et choisir un gagnant
    current_giveaway = giveaways.get(giveaway_msg.id)
    if current_giveaway and current_giveaway["participants"]:
        winner = random.choice(list(current_giveaway["participants"]))
        await giveaway_msg.edit(
            content=f"🎉 **GIVEAWAY TERMINÉ !** 🎉\n"
            f"🏆 **Le gagnant est {winner.mention} !** 🎊\n    "
            f"🎁 Prix remporté : {prize}")

        # Ajout et retrait de rôles au gagnant
        role_to_remove = discord.utils.get(winner.guild.roles,
                                         id=ROLE_JOIN_ID)
        role_to_add = discord.utils.get(winner.guild.roles,
                                      id=GIVEAWAY_WINNER_ROLE_ID)

        if role_to_remove and role_to_add:
            try:
                await winner.remove_roles(role_to_remove)
                await winner.add_roles(role_to_add)
                print(
                    f"Le rôle {role_to_remove.name} a été retiré et {role_to_add.name} ajouté à {winner.name}."
                )
            except discord.Forbidden:
                print(
                    f"Erreur : Le bot n'a pas la permission de modifier les rôles de {winner.name}."
                )
            except Exception as e:
                print(
                    f"Erreur inconnue lors de la modification des rôles : {e}")
    else:
        await giveaway_msg.edit(
            content=f"🎉 **GIVEAWAY TERMINÉ !** 🎉\n"
            f"Aucun participant pour le giveaway de **{prize}**.\n"
            f"Le giveaway est annulé.")

    # Supprimer les informations du giveaway
    if giveaway_msg.id in giveaways:
        del giveaways[giveaway_msg.id]


# Commandes de modération
@bot.command()
async def mute(ctx,
              member: discord.Member,
              time: int = None,
              *,
              reason: str = "Aucune raison spécifiée"):
    """Mute un utilisateur et lui attribue le rôle mute."""
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas mute un administrateur.")
        return

    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return
                  
    mute_role = discord.utils.get(ctx.guild.roles, id=MUTE_ROLE_ID)
    if not mute_role:
        await ctx.send("❌ Le rôle mute est introuvable.")
        return

    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"🔇 {member.mention} a été mute. Raison : {reason}")

    # Log de l'action
    await log_action(ctx, "Mute", member, reason=f"{reason} | Temps: {'Infini' if time is None else f'{time} minutes'}")

    # Si un temps est donné, unmute après expiration
    if time:
        await asyncio.sleep(time * 60)
        if mute_role in member.roles:  # Vérifier si le membre a toujours le rôle mute
            await member.remove_roles(mute_role, reason="Fin du mute")
            await ctx.send(f"🔊 {member.mention} a été unmute.")
            await log_action(ctx, "Unmute automatique", member)

@bot.command()
async def unmute(ctx, member: discord.Member):
    """Unmute un utilisateur et lui retire le rôle mute."""
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas unmute un administrateur.")
        return

    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    mute_role = discord.utils.get(ctx.guild.roles, id=MUTE_ROLE_ID)
    if not mute_role:
        await ctx.send("❌ Le rôle mute est introuvable.")
        return

    if mute_role not in member.roles:
        await ctx.send(f"❌ {member.mention} n'est pas mute.")
        return

    await member.remove_roles(mute_role, reason="Unmute manuel")
    await ctx.send(f"🔊 {member.mention} a été unmute.")
    await log_action(ctx, "Unmute manuel", member)

@bot.command()
async def kick(ctx,
              member: discord.Member,
              *,
              reason: str = "Aucune raison spécifiée"):
    """Expulse un utilisateur du serveur."""
# Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas unmute un administrateur.")
        return
                  
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas expulser un administrateur.")
        return

    if not ctx.author.guild_permissions.kick_members:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} a été expulsé. Raison : {reason}")
    await log_action(ctx, "Kick", member, reason=reason)

@bot.command()
async def ban(ctx,
             member: discord.Member,
             *,
             reason: str = "Aucune raison spécifiée"):
    """Bannit un utilisateur du serveur."""
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas unmute un administrateur.")
        return
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas bannir un administrateur.")
        return

    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    await member.ban(reason=reason)
    await ctx.send(f"🚫 {member.mention} a été banni. Raison : {reason}")
    await log_action(ctx, "Ban", member, reason=reason)

@bot.command()
async def unban(ctx,
               member: discord.User,
               *,
               reason: str = "Aucune raison spécifiée"):
    """Débannit un utilisateur du serveur."""
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas unmute un administrateur.")
        return
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    # Vérifier si l'utilisateur est banni
    try:
        ban_entry = await ctx.guild.fetch_ban(member)
    except discord.NotFound:
        await ctx.send(f"❌ {member.name} n'est pas banni.")
        return

    await ctx.guild.unban(member, reason=reason)
    await ctx.send(f"✅ {member.mention} a été débanni. Raison : {reason}")
    await log_action(ctx, "Unban", member, reason=reason)

@bot.command()
async def warn(ctx,
              member: discord.Member,
              *,
              reason: str = "Aucune raison spécifiée"):
    """Ajoute un avertissement à un utilisateur."""
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas unmute un administrateur.")
        return
    # Vérifier si le membre a le rôle administrateur
    admin_role = discord.utils.get(member.guild.roles, id=ADMIN_ROLE_ID)
    if admin_role in member.roles:
        await ctx.send("❌ Tu ne peux pas avertir un administrateur.")
        return

    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return
        
    # Initialiser les avertissements si nécessaire
    if member.id not in warnings:
        warnings[member.id] = 0

    warnings[member.id] += 1

    await ctx.send(f"⚠️ {member.mention} a été averti. Raison : {reason}\n"
                   f"Avertissements actuels : {warnings[member.id]}")
    
    await log_action(ctx, "Avertissement", member, 
                   reason=f"{reason} | Total: {warnings[member.id]}")

    # Action en fonction du nombre d'avertissements
    if warnings[member.id] >= 3:
        await member.kick(reason="Nombre d'avertissements trop élevé.")
        await ctx.send(
            f"❌ {member.mention} a été kické pour avoir atteint 3 avertissements."
        )
        await log_action(ctx, "Kick automatique", member, 
                       reason=f"A atteint {warnings[member.id]} avertissements")
        warnings[member.id] = 0


# Commandes de gestion des rôles
@bot.command()
async def addrole(ctx, member: discord.Member, role: discord.Role):
    """Ajoute un rôle à un utilisateur."""
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Vous n'avez pas la permission de gérer les rôles.")
        return
    
    if role in member.roles:
        await ctx.send(f'{member.mention} a déjà le rôle {role.name}.')
    else:
        await member.add_roles(role)
        await ctx.send(f'Le rôle {role.name} a été ajouté à {member.mention}.')
        await log_action(ctx, "ajouté", member, role)

@bot.command()
async def removerole(ctx, member: discord.Member, role: discord.Role):
    """Retire un rôle à un utilisateur."""
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Vous n'avez pas la permission de gérer les rôles.")
        return

    if role not in member.roles:
        await ctx.send(f"{member.mention} n'a pas le rôle {role.name}.")
    else:
        await member.remove_roles(role)
        await ctx.send(f'Le rôle {role.name} a été retiré de {member.mention}.')
        await log_action(ctx, "retiré", member, role)

# Commandes de gestion des mots interdits
@bot.command()
async def addword(ctx, *, word: str):
    """Ajoute un mot à la liste des mots interdits."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    if word.lower() not in MOTS_INTERDITS:
        MOTS_INTERDITS.append(word.lower())
        await ctx.send(f"Le mot `{word}` a été ajouté à la liste des interdictions.")
    else:
        await ctx.send(f"Le mot `{word}` est déjà dans la liste.")

@bot.command()
async def removeword(ctx, *, word: str):
    """Retire un mot de la liste des mots interdits."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    if word.lower() in MOTS_INTERDITS:
        MOTS_INTERDITS.remove(word.lower())
        await ctx.send(f"Le mot `{word}` a été retiré de la liste des interdictions.")
    else:
        await ctx.send(f"Le mot `{word}` n'est pas dans la liste.")

@bot.command()
async def listwords(ctx):
    """Affiche la liste des mots interdits."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return
        
    await ctx.send(f"Liste des mots interdits: {', '.join(MOTS_INTERDITS)}")

# Lancement du bot
keep_alive()
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
