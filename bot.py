#!/usr/bin/env python3
import discord,asyncio,threading,re,warnings,time,sys,traceback,aiohttp,async_timeout,datetime,random,os,json,io
from PIL import Image, ImageFont, ImageDraw
from colorsys import rgb_to_hsv, hsv_to_rgb
from subprocess import Popen, PIPE
from bs4 import BeautifulSoup
from math import sqrt
from data import *

debug = False

devnull = open(os.devnull, "w")

client = discord.Client()
logoPattern = re.compile(r'src="(https://cdn-eslgaming.akamaized.net/play/eslgfx/gfx/logos/teams/.*?)" id="team_logo_overlay_image"')
warnings.filterwarnings("ignore")

class botCommands:
    async def ping(message):
        await message.channel.send("pong!")

    async def github(message):
        await message.channel.send("https://github.com/mateuszdrwal/labourUnit")

    async def lastseen(message):
        username = message.content.split()[1].lower()
        member = discord.utils.find(lambda n: username in n.name.lower(), guild.members)

        if not member:
            await message.channel.send("member not found")
            return

        if member.status != discord.Status.offline:
            await message.channel.send("member is currently online")
            return

        laston = members.get(member.id)
        await message.channel.send(datetime.datetime.fromtimestamp(laston).strftime("{} was last online %A %b %d at %H:%M CET".format(member.display_name)))

    async def prune(message):
        global guild, members
        if not message.author.guild_permissions.kick_members:
            await message.channel.send("you dont have enough permissions to do that!")
            return

        try:
            days = int(message.content.split(" ")[1])
        except ValueError:
            await message.channel.send("number of days must be an integer")
            return
        except IndexError:
            await message.channel.send("usage: !prune <days>")
            return

        cutoff = time.time() - (60*60*24*days)
        exceptedRoles = [i for i in teams]+["bot"]
        candidates = members.copy()

        while True:
            async with message.channel.typing():
                toPrune = []
                for userId, timestamp in candidates.copy().items():
                    user = client.get_user(userId)
                    if user not in guild.members:
                        members.pop(userId)
                        candidates.pop(userId)
                        print(userId)
                        save()
                        continue
                    member = guild.get_member(userId)
                    if timestamp < cutoff:
                        for role in member.roles:
                            if role.name in exceptedRoles:
                                break
                        else:
                            toPrune.append(member)

                if toPrune == []:
                    await message.channel.send("no members to prune")
                    return

                await message.channel.send("here is the list of members that would be pruned for not being online on discord for %s days:```%s```type the number of the members (space separated) to ignore, \"yes\" to accept or anything else to cancel"%
                                           (days, "\n".join("%s. %s"%(i+1,member.display_name) for i, member in enumerate(toPrune)))
                                           )

            while True:
                response = await client.wait_for("message")
                if response.channel == message.channel and response.author == message.author:
                    break
                await asyncio.sleep(0.1)

            if response.content.startswith("!prune"): return

            userlist = re.findall(r"\d{1,}", response.content)
            userlist = [int(i)-1 for i in userlist]

            if response.content == "yes":
                async with message.channel.typing():
                    for member in toPrune:
                        try:
                            await member.kick(reason="pruning")
                            print("kicked %s"%member.display_name)
                        except discord.errors.Forbidden:
                            pass
                    await message.channel.send("done. kicked %s members"%len(toPrune))
                    return
            elif userlist != []:
                userlist.sort()
                userlist.reverse()
                for num in userlist:
                    if num > len(candidates)-1:
                        continue
                    toPrune.pop(num)
                candidates = {member.id: candidates.get(member.id) for member in toPrune}
                
                await message.channel.send("removed members from prune list")
            else:
                await message.channel.send("canceled.")
                return
            
    async def team(message):
        class teamSubcommands():

            async def create(message, args):
                global teams, teamsCategory
                if not (message.author.guild_permissions.manage_roles and message.author.guild_permissions.manage_channels):
                    await message.channel.send("you dont have enough permissions to do that!")
                    return

                if len(args) <= 2:
                    await message.channel.send("usage: !team create <team name>")
                    return
                    
                if args[-1] == "": args.pop(-1)
                teamname = " ".join(args[1:])

                if teamname.lower() in teams:
                    await message.channel.send("that team already exists!")
                    return

                color = findColor(list(list(i.color.to_rgb()) for i in guild.roles))
                color = discord.Color.from_rgb(color[0],color[1],color[2])
                
                newChannel = await guild.create_text_channel(name="team%s"%teamname.lower().replace(" ",""), category=teamsCategory, reason="creating new team")
                newRole = await guild.create_role(name=teamname.lower(), hoist=True, mentionable=True, colour=color, reason="creating new team")
                            
                teams[teamname.lower()] = {"name": teamname,
                                   "points": 0,
                                   "channelId": newChannel.id,
                                   "roleId": newRole.id
                                   }
                save()

                await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")

            async def remove(message, args):
                global teams, archiveCategory
                if not (message.author.guild_permissions.manage_roles and message.author.guild_permissions.manage_channels):
                    await message.channel.send("you dont have enough permissions to do that!")
                    return

                if len(args) <= 2:
                    await message.channel.send("usage: !team remove <team name>")
                    return
                
                if args[-1] == "": args.pop(-1)
                teamname = " ".join(args[1:])
                
                if teamname.lower() not in teams:
                    await message.channel.send("could not find team \"%s\""%teamname)
                    return

                try:
                    await discord.utils.find(lambda e: e.name == teamname.lower().replace(" ",""), guild.emojis).delete(reason="deleting team")
                except AttributeError:
                    pass
                await get_role(teams[teamname.lower()]["roleId"]).delete(reason="deleting team")
                await client.get_channel(teams[teamname.lower()]["channelId"]).edit(category=archiveCategory, sync_permissions=True,reason="deleting team")
                teams.pop(teamname.lower())
                save()

                await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")
                
            async def eslid(message, args):
                global teams
                if not (discord.utils.find(lambda r: r.name == args[2].lower(), message.author.roles) != None or message.author.guild_permissions.manage_roles):
                    await message.channel.send("you dont have enough permissions to do that!")
                    return

                if len(args) <= 2:
                    await message.channel.send("usage: !team eslid <id> <team name>")
                    return

                if args[2].lower() not in teams:
                    await message.channel.send("could not find team \"%s\""%args[2])
                    return

                try:
                    teams[args[2].lower()]["eslId"] = int(args[1])
                except ValueError:
                    await message.channel.send("id must be numerical")
                    return
                save()    

                await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")

            async def rename(message, args):
                global teams

                teamNames = re.findall((r'"(.*?)" "(.*?)"'), message.content)

                if teamNames == []:
                    await message.channel.send("usage: !team rename \"<new team name>\" \"<old team name>\"\nit's important that the team names are in double quotes")
                    return

                teamNames = teamNames[0]

                if not (discord.utils.find(lambda r: r.name == teamNames[1].lower(), message.author.roles) != None or message.author.guild_permissions.manage_roles):
                    await message.channel.send("you dont have enough permissions to do that!")
                    return

                if teamNames[1].lower() not in teams:
                    await message.channel.send("could not find team \"%s\""%teamNames[1])
                    return

                await client.get_channel(teams[teamNames[1].lower()]["channelId"]).edit(name="team%s"%teamNames[0].lower().replace(" ",""), reason="renaming team")
                await get_role(teams[teamNames[1].lower()]["roleId"]).edit(name=teamNames[0].lower(), reason="renaming team")
                try:
                    await discord.utils.find(lambda e: e.name == teamNames[1].lower().replace(" ","").replace("-",""), guild.emojis).edit(name=teamNames[0].lower().replace(" ","").replace("-",""), reason="renaming team")
                except AttributeError:
                    pass
                
                teams[teamNames[1].lower()]["name"] = teamNames[0]
                teams[teamNames[0].lower()] = teams[teamNames[1].lower()]
                teams.pop(teamNames[1].lower())
                save()

                await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")

            
        args = message.content.split(" ")[1:3] + [" ".join(message.content.split(" ")[3:])]
        method = getattr(teamSubcommands, message.content.split(" ")[1], False)
        if method:
            await method(message, args)
        else:
            await message.channel.send("usage: !team <eslid/rename/create/remove>")
            

def get_role(id):
    global guild
    return discord.utils.find(lambda r: r.id == id, guild.roles)

def save():
    f = open("data.py","w")
    
    f.write("teams = "+str(teams)
            .replace("{", "{\n ")
            .replace(",", ",\n")
            .replace("}", "\n}")
            )
    f.write("\ncups = "+str(cups))
    f.write("\nmembers = "+str(members))
    f.close()

async def eslApi(path):
    raw = await request("https://api.eslgaming.com"+path)
    return json.loads(raw)

async def request(url):
    global http
    while True:
        try:
            with async_timeout.timeout(30):
                async with http.get(url) as response:
                    return await response.text()
        except aiohttp.client_exceptions.ServerDisconnectedError:
            pass
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            raise e

async def requestImage(url):
    global http
    while True:
        try:
            with async_timeout.timeout(30):
                async with http.get(url) as response:
                        return await response.read()
                    
        except aiohttp.client_exceptions.ServerDisconnectedError:
            pass
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            raise e

def findColor(colors):
    try:
        while True:
            colors.pop(colors.index([0,0,0]))
    except ValueError:
        pass

    hsv = []
    for color in colors:
        color = rgb_to_hsv(color[0]/255,color[1]/255,color[2]/255)
        hsv.append(color)

    points = hsv

    points.sort()
    points.append([points[0][0]+1,points[0][1],points[0][2]])

    limit = [0,0.7,0.7]

    bestHueDistance = 0
    for i in range(len(points)-1):
        if points[i+1][0] - points[i][0] > bestHueDistance:
            bestHue = (points[i][0] + points[i+1][0])/2
            bestHueDistance = points[i+1][0] - points[i][0]
            counter = i

    bestPoint = [0,0]
    bestDistance = 0
    longest = sqrt(pow(255,2)+pow(255,2))
    for x in range(int(limit[1]*255),256):
        for y in range(int(limit[2]*255),256):
            closest = sqrt(pow(x-points[counter][1]*255,2)+pow(y-points[counter][2]*255,2))
            potential = sqrt(pow(x-points[counter+1][1]*255,2)+pow(x-points[counter+1][2]*255,2))
            if potential < closest: closest = potential
            if closest > bestDistance:
                bestPoint = [x/255,y/255]
                bestDistance = closest

    result = hsv_to_rgb(bestHue,bestPoint[0],bestPoint[1])

    return [int(result[0]*255),int(result[1]*255),int(result[2]*255)]



async def updater():
    global guild, captains, teams
    await client.wait_until_ready()
    await asyncio.sleep(5)
    while True:

        #update nicknames
        for member in guild.members:

            tmp = teams.copy().items()
            for team, metadata in tmp:
                role = discord.utils.find(lambda r: r.id == metadata["roleId"], member.roles)
                if role == None: continue
                nick = teams.get(role.name,None)
                
                if nick != None:
                    nick = nick["name"]
                    
                    if captains in member.roles:
                        nick += u" \N{FIRE}"

                    proposedNick = member.display_name.split(" | ")[0] + " | " + nick

                    if (member.display_name) == proposedNick:
                        break
                    
                    try:
                        await member.edit(nick=proposedNick, reason="updating user nickname")
                        print("updated %s's nickname"%member.name)
                    except discord.errors.Forbidden:
                        pass
                    except discord.errors.HTTPException:
                        pass
                    
                    break
            else:
                pass
                # proposedNick = member.nick.split(" | ")[0] if member.nick != None else None
                # if member.nick == proposedNick:
                #         continue
                # try:
                #     await member.edit(nick=proposedNick, reason="updating user nickname")
                #     print("updated %s's nickname"%member.name)
                # except discord.errors.Forbidden:
                #     pass

        #update standings
        raw = await request("https://toolbox.tet.io/go4/vrclechoarena_eu/season-1/")
        soup = BeautifulSoup(raw)
        tmp = teams.copy().items()
        for team, metadata in tmp:
            for child in soup.find("tbody").children:
                if team in str(child).lower():
                    entry = child
                    break
            else:
                continue
            teams[team]["points"] = int(entry.contents[3].contents[0])

        #update role and channel order
        roleoffset = 3
        rolecount = len(guild.roles)-1
        teamlist = []
        tmp = teams.copy().items()
        for team, metadata in tmp:
            teamlist.append([metadata["points"], get_role(metadata["roleId"]), client.get_channel(metadata["channelId"])])
        teamlist.sort()
        teamlist.reverse()
        for i, team in enumerate(teamlist):
            await team[1].edit(position=rolecount-i-roleoffset, reason="reordering roles according to current ESL ranking")
            await team[2].edit(position=i+1, reason="reordering channels according to current ESL ranking")
            
        #update emoji's
        tmp = teams.copy().items()
        for team, metadata in tmp:
            team = team.replace(" ","").replace("-","")
            eslId = metadata.get("eslId")
            if eslId == None:
                continue

            raw = await eslApi("/play/v1/teams/%s"%str(eslId))

            try:
                processed = raw["logo"]
            except KeyError:
                continue
                
            if "default.gif" in processed:
                continue
            
            p = Popen(["wget", "-O", "./emojis/%s_new.jpg"%team, processed], stdout=devnull)
            while p.poll() == None:
                await asyncio.sleep(0.5)

            p = Popen(["cmp", "./emojis/%s_new.jpg"%team, "./emojis/%s_old.jpg"%team], stdout=devnull)
            while p.poll() == None:
                await asyncio.sleep(0.5)

            if p.poll() == 0:
                continue

            print("updating :%s: emoji"%team)
            
            e = discord.utils.find(lambda e: e.name == team, guild.emojis)
            if e != None:
                await e.delete(reason="updating team emoji")

            await guild.create_custom_emoji(name=team,image=open("./emojis/%s_new.jpg"%team,"rb").read(), reason="updating team emoji")
            Popen(["sudo", "cp", "./emojis/%s_new.jpg"%team, "./emojis/%s_old.jpg"%team])

        save()
        await asyncio.sleep(1200)

async def cupTask():
    global cupChannel

    await client.wait_until_ready()
    await asyncio.sleep(5)

    while True:

        cups = []
        raw = await eslApi("/play/v1/leagues?types=&states=inProgress,upcoming&skill_levels=&limit.total=8&path=%2Fplay%2Fechoarena%2Feurope%2F&portals=&tags=vrclechoarena-eu-portal&includeHidden=0")
        for cup in raw.values():
            if "cup" not in cup["name"]["full"].lower():
                continue
            cups.append([datetime.datetime.strptime(cup["timeline"]["inProgress"]["begin"].replace(":",""), "%Y-%m-%dT%H%M%S%z").timestamp(),
                         cup["id"]
                         ])
        
        if len(cups) == 0:
            await asyncio.sleep(3600)
            continue
            
        cups.sort()
        cup = cups[0]

        waitTime = cup[0]-time.time()-900
        if waitTime > 0:
            print("waiting %s"%waitTime)
            await asyncio.sleep(waitTime)

            raw = await eslApi("/play/v1/leagues/%s/contestants"%cup[1])
            for team in raw:
                match = discord.utils.find(lambda t: t.get("eslId") == team["id"],teams.values())
                if match == None or team["status"] != "signedUp": continue
                mention = get_role(match["roleId"]).mention
                await client.get_channel(match["channelId"]).send("%s Don't forget to check in! You have 15 minutes left!"%mention)
                print("%s has not checked in, 15min left"%team)

        waitTime = cup[0]-time.time()-180
        if waitTime > 0:
            print("waiting %s"%waitTime)
            await asyncio.sleep(waitTime)

            raw = await eslApi("/play/v1/leagues/%s/contestants"%cup[1])
            for team in raw:
                match = discord.utils.find(lambda t: t.get("eslId") == team["id"],teams.values())
                if match == None or team["status"] != "signedUp": continue
                mention = get_role(match["roleId"]).mention
                await client.get_channel(match["channelId"]).send("%s Don't forget to check in! You have only 3 minutes left! In the case that you wont make it, contact @ESL in the #eu_vr_challenger_league on the echo games server immediately. They should be able to help until the brackets are generated. Hurry!"%mention)
                print("%s has not checked in, 3min left"%team["name"])

        await asyncio.sleep(60)

if not debug:
    @client.event
    async def on_error(event, *args, **kwargs):
        global errorChannel, err, mateuszdrwal
        err = sys.exc_info()
        await errorChannel.send("%s\n```%s\n\n%s```"%(mateuszdrwal.mention,"".join(traceback.format_tb(err[2])),err[1].args[0]))
        
@client.event
async def on_ready():
    global raw, guild, captains, teamsCategory, archiveCategory, generalChannel, errorChannel, mateuszdrwal, http, cupChannel
    print(client.user.name)
    print(client.user.id)
        
    guild = client.get_guild(374854809997803530)
    teamsCategory = client.get_channel(382992149307850758)
    archiveCategory = client.get_channel(382992652871925771)
    generalChannel = client.get_channel(374854809997803532)
    errorChannel = client.get_channel(394112817583882251)
    cupChannel = client.get_channel(402955959112040458)#394112817583882251)
    mateuszdrwal = client.get_user(140504440930041856)

    http = aiohttp.ClientSession()
   
    captains = get_role(386988129816543235)
    
    await client.change_presence(activity=discord.Activity(name='Echo Combat',type=discord.ActivityType.streaming))

@client.event
async def on_member_join(member):
    global guild, generalChannel
    if member.guild != guild:
        return
    await generalChannel.send("welcome :wave:, check out <#415251238301466625> to quickly get started!")

@client.event
async def on_member_update(before, after):
    if (before.status != discord.Status.offline and after.status == discord.Status.offline) or after.status != discord.Status.offline:
        members[after.id] = time.time()
        save()

@client.event
async def on_message(message):
    if message.content.startswith("!"):
        method = getattr(botCommands, message.content.split(" ")[0][1:], False)
        if method:
            await method(message)


async def errorCatcher(task):
    global errorChannel, mateuszdrwal
    try:
        await task
    except Exception as e:
        err = sys.exc_info()
        await errorChannel.send("%s\n```%s\n\n%s```"%(mateuszdrwal.mention,"".join(traceback.format_tb(err[2])),err[1].args[0]))

client.loop.create_task(errorCatcher(updater()))
client.loop.create_task(errorCatcher(cupTask()))

client.run(open("token","r").read())
