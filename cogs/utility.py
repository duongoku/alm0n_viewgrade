import shutil
import os

from cogs.utils import viewgrade
from discord import File
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_invitation(self):
        return f'https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot'

    @commands.command(
        aliases=['h'],
        brief='Show this help',
        usage='to show this help'
    )
    async def help(self, ctx, *args):
        p = self.bot.command_prefix
        msg = ''
        if len(args) > 0:
            cmd = self.bot.get_command(args[0])
            if cmd is None:
                msg = f'{msg}Couldn\'t find any command matched the commang you searched for'
            else:
                msg = f'{msg}Command: `{p}{cmd.name}`'

                if len(cmd.aliases) > 0:
                    msg = f'{msg} - you can also call `{p}{cmd.aliases[0]}`'
                    if len(cmd.aliases) > 1:
                        for i in range(1, len(cmd.aliases)):
                            msg = f'{msg} or `{p}{cmd.aliases[i]}`'
                    msg = f'{msg}\n\nUsage: `{p}{cmd.aliases[0]}` {cmd.usage}'
                else:
                    msg = f'{msg}\n\nUsage: `{p}{cmd.name}` {cmd.usage}'
        else:
            cogs = self.bot.cogs

            for cog in cogs:
                msg = f'{msg}__**{cog}**__:\n'
                cmds = cogs.get(cog).get_commands()
                for cmd in cmds:
                    msg = f'{msg}\t*{cmd.name}* - {cmd.brief}\n'

            msg = f'{msg}\nFor more details about each command, call `help command`'
        await ctx.send(msg)
        return

    @commands.command(
        brief='PING PONG',
        usage='to get pong'
    )
    async def ping(self, ctx):
        await ctx.send('pong')
        return

    @commands.command(
        brief='Get this bot\'s invitation url',
        usage='to get this bot\'s invitation url'
    )
    async def invite(self, ctx):
        await ctx.send(self.get_invitation())
        return

    @commands.command(
        aliases=['gvg'],
        brief='Get details about a course on viewgrade',
        usage='`course id` to get grade summary of a course'
    )
    async def getviewgrade(self, ctx, *args):
        if shutil.which('pdfinfo') is None or shutil.which('pdftoppm') is None or shutil.which('pdftocairo') is None:
            await ctx.send("This feature is currently unavailable!")
            return
        if len(args) < 1:
            await ctx.send("Missing course id!")
            return
        course_id = args[0]
        if len(course_id) != 7:
            await ctx.send("Invalid course id!")
            return
        await ctx.send("Please wait for a few minutes ...")

        course = viewgrade.get_course(course_id)

        s = ""

        if course is None:
            s = "Couldn't find anything related to the course <:cheems:721790695928758302>"
            await ctx.send(s)
            return

        print(course)

        for lecturer in course:
            ltr = course[lecturer]
            s += f"Lecturer: {lecturer}\n"
            s += f"\t\tCourse: {ltr['course']}\n"
            s += f"\t\tScore: {ltr['final_scores']}\n"
            s += f"\t\tCoverage: {round(ltr['extracted']/ltr['total']*100, 2)}%\n"

        viewgrade.make_plot(course)

        await ctx.send(s)
        await ctx.send(file=File(f"{os.getenv('TEMPDIR')}/plot.png"))
        return
