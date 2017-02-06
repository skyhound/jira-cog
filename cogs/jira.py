from discord.ext import commands
from discord.enums import ChannelType
from .utils.dataIO import fileIO
from jira import JIRA
import asyncio
from aiohttp import web

from threading import Thread, Event
import os


class CTimer(Thread):
    def __init__(self, event, func, period):
        Thread.__init__(self)
        self.stopped = event
        self.func = func
        self.period = period

    def run(self):
        while not self.stopped.wait(self.period):
            self.func()


class Settings:

    def __init__(self):
        self._data = fileIO("data/jira/settings.json", "load")
        self.workflow_channel = self._data["workflow_channel"]
        self.workflow_switch = bool(self._data["workflow_channel"])
        self.project_name = self._data["project_name"]
        self.board_name = self._data["board_name"]
        self.jira_local_port = int(self._data["jira_local_port"])


class EchoServer(asyncio.Protocol):

    def data_received(self, data):
        print("HOLY SHIT A WEBHOOK")


class JiraCog:
    _workflow_channel = None
    _workflow_switch = False

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.check_board())
        self.stop_event = Event()
        self.wf_timer = CTimer(self.stop_event, None, 30)
        self.credentials = fileIO("data/jira/credentials.json", "load")
        # self.settings = fileIO("data/jira/settings.json", "load")
        self.settings = Settings()
        self.agile = JIRA(self.credentials["url"], basic_auth=(self.credentials["login"], self.credentials["password"]))
        self.server = self.bot.loop.create_server(web.Server(self.simple_feedback), port=self.settings.jira_local_port, host="127.0.0.1")
        asyncio.ensure_future(self.server, loop=self.bot.loop)

    @commands.command()
    async def listsprint(self):
        output = ""
        project = self.agile.project(self.settings.project_name)
        boards = self.agile.boards(type="scrum")
        tech_board = boards[0]
        for board in boards:
            if board.name == self.settings.board_name:
                tech_board = board
        tech_sprints = self.agile.sprints(tech_board.id, state="active")
        current_tech_sprint = tech_sprints[0]
        for sprint in tech_sprints:
            if sprint.state == "ACTIVE":
                current_tech_sprint = sprint
        all_issues = {"cache": {}, "new": {}}
        new_issues = self.agile.search_issues(
            "(issuetype=story or issuetype=technicaldebt) and sprint=" + str(current_tech_sprint.id))
        story_issues = []
        for issue in new_issues:
            temp = {issue.key: issue}
            all_issues["cache"][issue.key] = issue
            output = output + (issue.key + " " + issue.fields.summary + "   " + str(issue.fields.status)) + "\n"


        if self._workflow_channel is None:
            await self.bot.say("No workflow channel assigned!")
        else:
            await self.bot.send_message(self._workflow_channel, output)

    @commands.command(pass_context=True, no_pm=True)
    async def listchannels(self, ctx):
        result = ""
        server = ctx.message.server
        author = ctx.message.author
        channels_list = self.get_channels(server, "text")
        result = str(len(channels_list)) + " text channels found:\n"
        for channel in channels_list:
            p_res = channel.name
            result = result + str(p_res) + "\n"

        await self.bot.say(result)

    @commands.command(pass_context=True, no_pm=True)
    async def set_workflow_channel(self, p_ctx, p_channel_name):
        result = ""
        server = p_ctx.message.server
        author = p_ctx.message.author
        channels_list = self.get_channels(server, "text")
        result = str(len(channels_list)) + " text channels found:\n"
        for channel in channels_list:
            if channel.name == p_channel_name:
                self._workflow_channel = channel
                await self.bot.say("Channel #" + channel.name + " is set as a workflow channel. Tons of spam incoming!")
                return
        await self.bot.say("No such channel, sry")

    @commands.command(pass_context=True, no_pm=True)
    async def switch_workflow(self, p_ctx):
        if self._workflow_switch:
            self._workflow_switch = False
            self.stop_event.set()
            await self.bot.say("Workflow off.")
        else:
            self._workflow_switch = True
            self.stop_event.clear()
            self.wf_timer = CTimer(self.stop_event, self.start_coroutine, 30)
            self.wf_timer.start()
            await self.bot.say("Workflow on.")

    def get_channels(self, server, channels_type):
        result = []
        if channels_type == "text":
            for channel in server.channels:
                if channel.type == ChannelType.text:
                    result.append(channel)

        elif channels_type == "voice":
            for channel in server.channels:
                if channel.type == ChannelType.voice:
                    result.append(channel)
        elif channels_type == "both":
            for channel in server.channels:
                if channel.type == ChannelType.text or channel.type == ChannelType.voice:
                    result.append(channel)
        return result

    def start_coroutine(self):
        self.bot.loop.create_task(self.check_board())

    async def simple_feedback(self, request):
        print("HOLY SHIT A WEBHOOK")
        await self._simple_feedback()
        return web.Response(text="got it")

    async def _simple_feedback(self):
        if self._workflow_channel is not None:
            await self.bot.send_message(self._workflow_channel, "Got a webhook!")

    async def check_board(self):
        if self._workflow_switch and self._workflow_channel is not None:

            await self.bot.send_message(self._workflow_channel, "Test")


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(JiraCog(bot))


def check_folders():
    folders = ("data", "data/jira/")
    for folder in folders:
        if not os.path.exists(folder):
            print("Creating " + folder + " folder...")
            os.makedirs(folder)


def check_files():
    settings = {"workflow_channel": "test", "project_name": "example", "board_name": "example"}
    credentials = {"login": "admin", "password": "admin", "url": "example.com"}

    if not os.path.isfile("data/jira/settings.json"):
        print("Creating empty settings.json...")
        fileIO("data/jira/settings.json", "save", settings)
    if not os.path.isfile("data/jira/credentials.json"):
        print("Creating empty credentials.json...")
        fileIO("data/jira/credentials.json", "save", credentials)
