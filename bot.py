import discord,asyncio,threading,urllib3,re,warnings
from data import *
from subprocess import Popen

client = discord.Client()
http = urllib3.PoolManager()
scoreboardPattern = re.compile(r"<tr>.*?<td>.*?</td>.*?<td>(\d{1,5})</td>.*?<td><.*? target.*?>(.*?)</a></td>.*?</tr>")
logoPattern = re.compile(r'src="(https://cdn-eslgaming.akamaized.net/play/eslgfx/gfx/logos/teams/.*?)" id="team_logo_overlay_image"')
warnings.filterwarnings("ignore")

def save():
    f = open("data.py","w")
    
    f.write("teams = "+str(teams)
            .replace("{", "{\n ")
            .replace(",", ",\n")
            .replace("}", "\n}")
            )
    f.close()


async def updater():
    global guild, captains, teams
    await client.wait_until_ready()
    await asyncio.sleep(5)
    while True:

        #update nicknames
        for user in guild.members:

            tmp = teams.items()
            for team, metadata in tmp:
                role = discord.utils.find(lambda r: r.name == team,user.roles)
                if role == None: continue
                nick = teams.get(role.name,None)
                
                if nick != None:
                    nick = nick["name"]
                    
                    if captains in user.roles:
                        nick += u" \N{FIRE}"

                    proposedNick = user.nick.split(" | ")[0] + " | " + nick if user.nick != None else user.name + " | " + nick
                    if user.nick == proposedNick:
                        break
                    #print(proposedNick,user.nick)
                    try:
                        await user.edit(nick=proposedNick, reason="updating user nickname")
                        print("updating %s's nickname"%user.name)
                    except discord.errors.Forbidden:
                        pass
                    except discord.errors.HTTPException:
                        pass
                    
                    break
            else:
                proposedNick = user.nick.split(" | ")[0] if user.nick != None else None
                if user.nick == proposedNick:
                        continue
                try:
                    await user.edit(nick=proposedNick, reason="updating user nickname")
                    print("updating %s's nickname"%user.name)
                except discord.errors.Forbidden:
                    pass

        #update standings
        raw = http.request("GET", "https://toolbox.tet.io/go4/vrclechoarena_eu/season-1/").data #refactor, non-async aka blocking
        processed = re.findall(scoreboardPattern, str(raw.lower()))
        for team, metadata in teams.items():
            entry = discord.utils.find(lambda e: metadata["name"].lower() in e[1], processed)
            if entry == None:
                continue
            teams[team]["points"] = int(entry[0])

        #update emoji's
        tmp = teams.items()
        for team, metadata in tmp:
            team = team.replace(" ","")
            eslId = metadata.get("eslId")
            if eslId == None:
                continue
            
            raw = http.request("GET", "https://play.eslgaming.com/team/%s"%str(eslId)).data #refactor, non-async aka blocking
            processed = re.findall(logoPattern,str(raw))[0]
            if "default.gif" in processed:
                continue
            
            p = Popen(["sudo", "wget", "-O", "./emojis/%s_new.jpg"%team, processed])
            while p.poll() == None:
                await asyncio.sleep(0.5)

            p = Popen(["sudo", "cmp", "./emojis/%s_new.jpg"%team, "./emojis/%s_old.jpg"%team])
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
        await asyncio.sleep(600)

@client.event
async def on_ready():
    global guild, captains, teamsCategory, archiveCategory
    print(client.user.name)
    print(client.user.id)
    
    guild = client.get_guild(374854809997803530)
    teamsCategory = client.get_channel(382992149307850758)
    archiveCategory = client.get_channel(382992652871925771)
    captains = discord.utils.find(lambda r: r.name == "captains",guild.roles)
    
    await client.change_presence(game=discord.Game(name='Echo Combat',type=1))

@client.event
async def on_message(message):
    global debug, guild, teamsCategory, teams, archiveCategory
    debug = message
    
    if message.content == "!github":
        await message.channel.send("https://github.com/mateuszdrwal/labourUnit")

    elif message.content == "!ping":
        await message.channel.send("pong!")

    elif message.content.startswith("!team"):
        args = message.content.split(" ")[1:3] + [" ".join(message.content.split(" ")[3:])]

        if len(args) <= 2:
            if args[0] == "eslid":
                await message.channel.send("usage: !team eslid <id> <team name>")
            elif args[0] == "name":
                await message.channel.send("usage: !team rename \"<new team name>\" \"<old team name>\"\nit's important that the team names are in double quotes")
            elif args[0] == "create":
                await message.channel.send("usage: !team create <team name>")
            elif args[0] == "remove":
                await message.channel.send("usage: !team remove <team name>")
            else:
                await message.channel.send("usage: !team <eslid/rename/create/remove> <value> <team name>")
            return

        response = await message.channel.send("processing...")

        if args[0] == "create":
            # 1. create channel
            # 2. create role
            # 3. set channel permissions for role
            # 4. add team name, points and channel id to teams dict
            # suggestion: set role color as far away as possible from other colors
            
            if not (message.author.guild_permissions.manage_roles and message.author.guild_permissions.manage_channels):
                await response.edit(content="you dont have enough permissions to do that!")
                return

            teamname = " ".join(args[1:])
            
            newChannel = await guild.create_text_channel(name="team%s"%teamname.lower().replace(" ",""), category=teamsCategory, reason="creating new team")
            newRole = await guild.create_role(name=teamname.lower(), reason="creating new team")
            await newChannel.set_permissions(newRole, manage_roles=True, manage_channels=True)
            
            teams[teamname.lower()] = {"name": teamname,
                               "points": 0,
                               "channelId": newChannel.id
                               }
            save()
            await response.edit(content="created team \"%s\""%teamname)
            return

        elif args[0] == "remove":
            
            if not (message.author.guild_permissions.manage_roles and message.author.guild_permissions.manage_channels):
                await response.edit(content="you dont have enough permissions to do that!")
                return
            
            teamname = " ".join(args[1:])
            
            if teamname.lower() not in teams:
                await response.edit(content="could not find team \"%s\""%teamname)
                return

            await discord.utils.find(lambda r: r.name == teamname.lower(), guild.roles).delete(reason="deleting team")
            await client.get_channel(teams[teamname.lower()]["channelId"]).edit(category=archiveCategory, reason="deleting team")
            teams.pop(teamname.lower())
            save()
            
            await response.edit(content="removed team \"%s\""%teamname)
            return

        if args[2] == "" and args[0] in "eslid rename":
            await response.edit(content="command \"!team %s\" requires 2 parameters"%args[0])
            return
        
        if args[0] == "eslid":
            
            if not (discord.utils.find(lambda r: r.name == args[2].lower(), message.author.roles) != None or message.author.guild_permissions.manage_roles):
                await response.edit(content="you dont have enough permissions to do that!")
                return

            if args[2].lower() not in teams:
                await response.edit(content="could not find team \"%s\""%args[2])
                return

            try:
                teams[args[2].lower()]["eslId"] = int(args[1])
            except ValueError:
                await response.edit(content="id must be numerical")
                return
            
            save()    
            await response.edit(content="set %s's esl team id to %s"%(args[2], args[1]))
            
        elif args[0] == "rename":
            teamNames = re.findall((r'"(.*?)" "(.*?)"'), message.content)

            if teamNames == []:
                await response.edit(content="usage: !team rename \"<new team name>\" \"<old team name>\"\nit's important that the team names are in double quotes")
                return

            teamNames = teamNames[0]

            if not (discord.utils.find(lambda r: r.name == teamNames[1].lower(), message.author.roles) != None or message.author.guild_permissions.manage_roles):
                await response.edit(content="you dont have enough permissions to do that!")
                return

            if teamNames[1].lower() not in teams:
                await response.edit(content="could not find team \"%s\""%teamNames[1])
                return

            await client.get_channel(teams[teamNames[1].lower()]["channelId"]).edit(name="team%s"%teamNames[0].lower().replace(" ",""), reason="renaming team")
            #await discord.utils.find(lambda r: r.name == teamNames[1].lower(), guild.roles).edit(name=teamNames[0].lower(), reason="renaming team")
            try:
                await discord.utils.find(lambda e: e.name == teamNames[1].lower().replace(" ",""), guild.emojis).edit(name=teamNames[0].lower().replace(" ",""), reason="renaming team")
            except AttributeError:
                pass
            teams[teamNames[1].lower()]["name"] = teamNames[0]
            teams[teamNames[0].lower()] = teams[teamNames[1].lower()]
            teams.pop(teamNames[1].lower())
            save()

            await response.edit(content="renamed team \"%s\" to \"%s\""%(teamNames[1], teamNames[0]))

        else:
            await response.edit(content="unknown parameter to !team \"%s\""%args[0])

client.loop.create_task(updater())

client.run(open("token","r").read())
