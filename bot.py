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
            .replace("{", "{\n")
            .replace(",", ",\n")
            .replace("}", "\n}")
            )
    f.close()


async def updater():
    await client.wait_until_ready()

    guild = client.get_guild(374854809997803530)
    captains = discord.utils.find(lambda r: r.name == "captains",guild.roles)
    
    while True:

        #update nicknames
        for user in guild.members:
            
            for team in teams:
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
        for team, metadata in teams.items():
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
    print(client.user.name)
    print(client.user.id)
    await client.change_presence(game=discord.Game(name='Echo Combat',type=1))

@client.event
async def on_message(message):
    global debug
    debug = message
    
    if message.content == "!github":
        await message.channel.send("https://github.com/mateuszdrwal/labourUnit")

    elif message.content == "!ping":
        await message.channel.send("pong!")

    elif message.content.startswith("!team"):
        args = message.split(" ")[1:4] + " ".join(message.split(" ")[4:])

        if len(args) == 1:
            await message.channel.send("usage: !team <eslid/channelid/name/create> <value> <team name>")
            return

        if len(args) == 2:
            if args[0] == "eslid":
                await message.channel.send("usage: !team eslid <id> <team name>")
            elif args[0] == "channelid":
                await message.channel.send("usage: !team channelid <id> <team name>")
            elif args[0] == "name":
                await message.channel.send("usage: !team name \"<new team name>\" <old team name>")
            elif args[0] == "create":
                await message.channel.send("usage: !team create <team name>")
            else:
                await message.channel.send("usage: !team <eslid/channelid/name/create> <value> <team name>")
            return

        if args[0] == "create":
            
            teams[args[1:].lower()] = {"name": args[1:]}
        


client.loop.create_task(updater())

client.run(open("token","r").read())
