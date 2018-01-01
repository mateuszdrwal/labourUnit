import discord,asyncio,threading,urllib3,re,warnings,time,sys,traceback
from colorsys import rgb_to_hsv, hsv_to_rgb
from math import sqrt
from subprocess import Popen
from data import *

debug = False

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
    f.write("\ncups = "+str(cups))
    f.write("\nmembers = "+str(members))
    f.close()

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
        for user in guild.members:

            tmp = teams.copy().items()
            for team, metadata in tmp:
                role = discord.utils.find(lambda r: r.name == team,user.roles)
                if role == None: continue
                nick = teams.get(role.name,None)
                
                if nick != None:
                    nick = nick["name"]
                    
                    if captains in user.roles:
                        nick += u" \N{FIRE}"

                    proposedNick = user.nick.split(" | ")[0] + " | " + nick if user.nick != None else user.name.split(" | ")[0] + " | " + nick

                    if (user.nick if user.nick != None else user.name) == proposedNick:
                        break
                    
                    try:
                        await user.edit(nick=proposedNick, reason="updating user nickname")
                        print("updated %s's nickname"%user.name)
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
                    print("updated %s's nickname"%user.name)
                except discord.errors.Forbidden:
                    pass

        #update standings
        raw = http.request("GET", "https://toolbox.tet.io/go4/vrclechoarena_eu/season-1/").data #refactor, non-async aka blocking
        processed = re.findall(scoreboardPattern, str(raw.lower()))
        tmp = teams.copy().items()
        for team, metadata in tmp:
            entry = discord.utils.find(lambda e: metadata["name"].lower() in e[1], processed)
            if entry == None:
                continue
            teams[team]["points"] = int(entry[0])

        #update role and channel order
        roleoffset = 2
        rolecount = len(guild.roles)-1
        teamlist = []
        tmp = teams.copy().items()
        for team, metadata in tmp:
            teamlist.append([metadata["points"], discord.utils.find(lambda r: r.name == team, guild.roles), client.get_channel(metadata["channelId"])])
        teamlist.sort()
        teamlist.reverse()
        for i, team in enumerate(teamlist):
            await team[1].edit(position=rolecount-i-roleoffset, reason="reordering roles according to current ESL ranking")
            await team[2].edit(position=i+1, reason="reordering channels according to current ESL ranking")
            
        #update emoji's
        tmp = teams.copy().items()
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

if not debug:
    @client.event
    async def on_error(event, *args, **kwargs):
        global errorChannel, err, mateuszdrwal
        err = sys.exc_info()
        await errorChannel.send("%s\n```%s\n\n%s```"%(mateuszdrwal.mention,"".join(traceback.format_tb(err[2])),err[1].args[0]))

@client.event
async def on_ready():
    global guild, captains, teamsCategory, archiveCategory, generalChannel, errorChannel, mateuszdrwal
    print(client.user.name)
    print(client.user.id)
    
    guild = client.get_guild(374854809997803530)
    teamsCategory = client.get_channel(382992149307850758)
    archiveCategory = client.get_channel(382992652871925771)
    generalChannel = client.get_channel(393889024961544192)
    errorChannel = client.get_channel(394112817583882251)
    mateuszdrwal = client.get_user(140504440930041856)
    captains = discord.utils.find(lambda r: r.name == "captains",guild.roles)
    
    await client.change_presence(game=discord.Game(name='Echo Combat',type=1))

@client.event
async def on_member_join(member):
    global guild, generalChannel
    await generalChannel.send(":wave:")#"Welcome %s to the champions server!\nAre you searching for a team?"%member.mention)
##    while True:
##        response = await client.wait_for("message")
##        if response.channel == generalChannel and response.author == member:
##            break
##    if "yes" in response.content.lower():
##        await generalChannel.send("Great! I'll give you the appropriate roles then. Good luck!")
##        await member.edit(roles=member.roles+[discord.utils.find(lambda r: r.name == "searching for team", guild.roles)])

@client.event
async def on_member_update(before, after):
    if before.status != discord.Status.offline and after.status == discord.Status.offline:
        members[after.id] = time.time()
        save()

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

            if args[-1] == "": args.pop(-1)
            teamname = " ".join(args[1:])

            color = findColor(list(list(i.color.to_rgb()) for i in guild.roles))
            color = discord.Color.from_rgb(color[0],color[1],color[2])
            
            newChannel = await guild.create_text_channel(name="team%s"%teamname.lower().replace(" ",""), category=teamsCategory, reason="creating new team")
            newRole = await guild.create_role(name=teamname.lower(), hoist=True, mentionable=True, colour=color, reason="creating new team")
            await newChannel.set_permissions(newRole, manage_roles=True, manage_channels=True)
            
            teams[teamname.lower()] = {"name": teamname,
                               "points": 0,
                               "channelId": newChannel.id
                               }
            save()
            await response.delete()
            await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")
            return


        elif args[0] == "remove":
            
            if not (message.author.guild_permissions.manage_roles and message.author.guild_permissions.manage_channels):
                await response.edit(content="you dont have enough permissions to do that!")
                return

            if args[-1] == "": args.pop(-1)
            teamname = " ".join(args[1:])
            
            if teamname.lower() not in teams:
                await response.edit(content="could not find team \"%s\""%teamname)
                return

            await discord.utils.find(lambda r: r.name == teamname.lower(), guild.roles).delete(reason="deleting team")
            await client.get_channel(teams[teamname.lower()]["channelId"]).edit(category=archiveCategory, reason="deleting team")
            teams.pop(teamname.lower())
            save()
            
            await response.delete()
            await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")
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
            await response.delete()
            await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")
            
            
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
            await discord.utils.find(lambda r: r.name == teamNames[1].lower(), guild.roles).edit(name=teamNames[0].lower(), reason="renaming team")
            try:
                await discord.utils.find(lambda e: e.name == teamNames[1].lower().replace(" ",""), guild.emojis).edit(name=teamNames[0].lower().replace(" ",""), reason="renaming team")
            except AttributeError:

                pass
            teams[teamNames[1].lower()]["name"] = teamNames[0]
            teams[teamNames[0].lower()] = teams[teamNames[1].lower()]
            teams.pop(teamNames[1].lower())
            save()

            await response.delete()
            await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")
            
        else:
            await response.edit(content="unknown parameter to !team \"%s\""%args[0])

    elif message.content.startswith("!addcup "):
        if not message.author.guild_permissions.manage_roles:
            await response.edit(content="you dont have enough permissions to do that!")
            return
        
        url = message.content.split(" ")[1]
        raw = http.request("GET", url).data
        
        
        save()
        await message.add_reaction(u"\N{WHITE HEAVY CHECK MARK}")

    elif message.content.startswith("!prune"):
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
        exceptedRoles = [i for i in teams]
        candidates = members.copy()

        while True:
            async with message.channel.typing():
                toPrune = []
                for memberId, timestamp in candidates.items():
                    user = client.get_user(memberId)
                    if user not in guild.members:
                        members.pop(memberId)
                        canndidates.pop(memberId)
                        save()
                        continue
                    user = guild.get_member(memberId)
                    if timestamp < cutoff:
                        for role in user.roles:
                            if role.name in exceptedRoles:
                                break
                        else:
                            toPrune.append(user)

                if toPrune == []:
                    await message.channel.send("no members to prune")
                    return

                await message.channel.send("here is the list of members that would be pruned for not being online on discord for %s days:```%s```type the number of the members (space separated) to ignore, \"yes\" to accept or anything else to cancel"%
                                           (days, "\n".join("%s. %s"%(i+1,user.display_name) for i, user in enumerate(toPrune)))
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
                    for user in toPrune:
                        await user.kick(reason="pruning")
                        try:
                            print("kicked %s"%user.display_name)
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
                candidates = {user.id: candidates.get(user.id) for user in toPrune}
                
                await message.channel.send("removed members from prune list")
            else:
                await message.channel.send("canceled.")
                return
                
            
client.loop.create_task(updater())

client.run(open("token","r").read())
