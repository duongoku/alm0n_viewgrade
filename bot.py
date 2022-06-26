import discord
import dotenv
import os

from cogs.utility import Utility
from discord.ext import commands

dotenv.load_dotenv()


class alm0n(commands.Bot):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        print(f"Prefix is '{self.command_prefix}'")
        print(f"Invitation URL: {self.get_cog('Utility').get_invitation()}")


def run():
    try:
        os.mkdir(os.getenv("TEMPDIR"))
    except FileExistsError as error:
        print(error)

    try:
        os.mkdir(os.getenv("CACHEDIR"))
    except FileExistsError as error:
        print(error)

    prefix = "~" if os.getenv("Path") else ";"
    intents = discord.Intents.all()
    activity = discord.Game(name=f"{prefix}help")

    bot = alm0n(
        intents=intents, command_prefix=prefix, activity=activity, help_command=None
    )

    bot.add_cog(Utility(bot))

    bot.run(os.getenv("DISCORD_BOT_TOKEN"))

    print("Bot is down!")


if __name__ == "__main__":
    run()
