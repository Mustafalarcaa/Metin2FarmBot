from keep_alive import keep_alive
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from collections import defaultdict
from datetime import datetime
import os

TOKEN = os.getenv("TOKEN")
GUILD_ID = 786207061310046288
ADMIN_ROLE_ID = 1162483008532656289
EFSANE_ROLE_ID = 1383517464335351848

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect('kivrik.db')
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS sets (id INTEGER PRIMARY KEY AUTOINCREMENT, oda TEXT, katilanlar TEXT, kivrik_sayisi INTEGER, tarih TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS oyuncular (isim TEXT PRIMARY KEY, toplam_kivrik REAL)")
conn.commit()

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'{bot.user} olarak giriş yaptı.')

def is_admin(interaction):
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

def is_efsane(interaction):
    return any(role.id == EFSANE_ROLE_ID for role in interaction.user.roles)

@bot.tree.command(name="ekle", description="Ses kanalındaki oyuncularla kıvrık kaydı yap", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(oda="Oda adı", kivrik="Toplanan kıvrık sayısı")
async def ekle(interaction, oda: str, kivrik: int):
    if not is_efsane(interaction):
        await interaction.response.send_message("Bu komutu kullanamazsın.", ephemeral=True)
        return

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("Bir ses kanalında olman gerekiyor.", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    members = channel.members
    katilanlar = ", ".join([member.display_name for member in members])
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("INSERT INTO sets (oda, katilanlar, kivrik_sayisi, tarih) VALUES (?, ?, ?, ?)",
              (oda, katilanlar, kivrik, tarih))
    conn.commit()

    oyuncular = [member.display_name for member in members]
    pay = kivrik / len(oyuncular)

    for oyuncu in oyuncular:
        c.execute("INSERT INTO oyuncular (isim, toplam_kivrik) VALUES (?, ?) ON CONFLICT(isim) DO UPDATE SET toplam_kivrik = toplam_kivrik + ?",
                  (oyuncu, pay, pay))
    conn.commit()

    embed = discord.Embed(title="✅ Kayıt Eklendi",
                          description=f"Oda: {oda}\nKatılanlar: {katilanlar}\nKıvrık: {kivrik}",
                          color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kıvrık", description="Toplam toplanan kıvrık miktarını gösterir", guild=discord.Object(id=GUILD_ID))
async def kivrik(interaction):
    if not is_efsane(interaction):
        await interaction.response.send_message("Bu komutu kullanamazsın.", ephemeral=True)
        return

    c.execute("SELECT katilanlar, kivrik_sayisi FROM sets")
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("Kayıt yok.")
        return

    kivrik_toplam = 0
    for katilanlar, kivrik in rows:
        oyuncular = [isim.strip() for isim in katilanlar.split(",")]
        kivrik_toplam += int(kivrik)

    embed = discord.Embed(title="📦 Toplam Kıvrık", color=discord.Color.gold())
    embed.add_field(name="Bu haftaki toplam:", value=f"{kivrik_toplam} kıvrık", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rapor", description="Katılım raporu: kim kaç set geldi", guild=discord.Object(id=GUILD_ID))
async def rapor(interaction):
    if not is_efsane(interaction):
        await interaction.response.send_message("Bu komutu kullanamazsın.", ephemeral=True)
        return

    c.execute("SELECT katilanlar, kivrik_sayisi FROM sets")
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("Kayıt yok.")
        return

    set_sayilari = defaultdict(int)
    for katilanlar, _ in rows:
        oyuncular = [isim.strip() for isim in katilanlar.split(",")]
        for oyuncu in oyuncular:
            set_sayilari[oyuncu] += 1

    embed = discord.Embed(title="📋 Haftalık Katılım Raporu", color=discord.Color.blurple())
    for oyuncu, adet in sorted(set_sayilari.items(), key=lambda x: -x[1]):
        embed.add_field(name=oyuncu, value=f"{adet} set", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sifirla", description="Tüm verileri sıfırla ve yedekle", guild=discord.Object(id=GUILD_ID))
async def sifirla(interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Yetkin yok!", ephemeral=True)
        return

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    with open(f"yedek_{now}.txt", "w", encoding="utf-8") as f:
        for row in c.execute("SELECT * FROM sets"):
            f.write(str(row) + "\n")

    c.execute("DELETE FROM sets")
    c.execute("DELETE FROM oyuncular")
    conn.commit()

    await interaction.response.send_message("Tüm veriler sıfırlandı ve yedeklendi ✅")

keep_alive()
bot.run(TOKEN)
