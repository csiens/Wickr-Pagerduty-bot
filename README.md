# **WickrIO Pagerduty bot**
## **WickrIO Pagerduty bot installation instructions**
### Step 1: Create, configure, and run a WickrIO Web Interface Integration using these instructions.  

https://wickrinc.github.io/wickrio-docs/#existing-integrations-web-interface-integration

### Step 2 : Create, configure, and run a WickrIO Pagerduty bot using this command.  

```sudo docker run -e APISERVERIP="172.17.0.2" -e APISERVERPORT="4001" -e BOTAPIKEY="pagerdutybot" -e BOTSECRET=$(echo -n 'password'|base64) --name pagerdutybot -d -ti --restart=always csiens/wickrio-pagerduty-bot:0.1```

**IMPORTANT!!! Customize the following Docker command variables before running the command!!!**  
>`APISERVERIP` IP address where the WickrIO Web Interface is running. Can be FQDN or IP.  
`APISERVERPORT` Port number used when configuring the WickrIO Web Interface.  
`BOTAPIKEY` ApiKey used when configuring the WickrIO Web Interface.  
`BOTSECRET` Base64 encoded password used when configuring the WickrIO Web Interface.  
`CALLBACKIP` **Optional** If not specified the bot will self discover its IP. Can be FQDN or IP.  
`LISTEN_PORT` **Optional** If not specified the bot will default to `80`.  

If you are running the WickrIO Web Interface and the WickrIO Pagerduty bot on the same Docker host you can use the WickrIO Web Interface container name instead of the IP address in the `APISERVERIP` variable.  Run this command to create a Docker network and join both containers to that network. Replace `webinterface` with the name of the container where the WickrIO Web Interface is running.

`sudo docker network create pagerduty-network ; sudo docker network connect pagerduty-network pagerdutybot ; sudo docker network connect pagerduty-network webinterface ; sudo docker restart pagerdutybot`

### Step 3: Add a Pagerduty webhook  
The WickrIO Pagerduty bot will receive incoming incidents from Pagerduty through a webhook. You will need a static public IP address that you can Port Forward 1 port to the internal Pagerduty bot container's port 80. Configure the same webhook URL for each service you would like to receive incidents for using these instructions. 
https://support.pagerduty.com/docs/webhooks#add-a-webhook  
The Pagerduty webhook URL should look like this.  
>`http://yoursite-or-ip-address.com:80/incidents`

### Step 4: Configure the Pagerduty Api Access Token
The WickrIO Pagerduty bot requires an Api Access Token. Please visit https://support.pagerduty.com/docs/generating-api-keys#generating-a-general-access-rest-api-key to create one. You can set the Pagerduty Api Access Token with the /secret command.  
>`/secret PagerdutyApiAccessToken`

### Step 5: Add a Wickr User to the Alert List  
The WickrIO Pagerduty Bot receives incoming incidents and forwards them to Wickr users on the Alert List. You must add at least one Wickr user to the Alert List. Add your username to the Alert List with the `/alert add` command. The Pagerduty bot will also forward incidents to all of the Wickr rooms that the bot is in. 
>`/alert add`


## **WickrIO Pagerduty bot commands**  

`/help` Returns a list of commands.  

`/services` Returns a list of Pagerduty service names, service IDs, and service oncalls.  
 
`/maint` Takes a Pagerduty service ID, duration in minutes, and an optional description and creates a maintenance window. You may create a maintenance window for all services by passing `all` in place of a service ID. Passing no arguments will return a list of Pagerduty services.
>`/maint serviceID 5 Server upgrade`  
>`/maint all 5 Server upgrade`

`/incidents` Returns a list of unresolved Pagerduty incidents.  

`/trigger` Takes a Pagerduty service ID and an optional description and will trigger a new Pagerduty incident. Passing no arguments will return a list of Pagerduty services.
>`/trigger serviceID Server is down!`  

`/ack` Takes a Pagerduty incident ID and an optional description and will acknowledge an existing Pagerduty incident. Passing no arguments will return a list of unresolved Pagerduty incidents.
>`/ack serviceID Working on it`   

`/snooze` Takes a Pagerduty incident ID, a duration in minutes, and an optional description and will snooze an existing Pagerduty incident. Passing no arguments will return a list of unresolved Pagerduty incidents.
>`/snooze serviceID 60 I will get to this ASAP!`   

`/resolve` Takes a Pagerduty incident ID and an optional description and will resolve an unresolved Pagerduty incident. Passing no arguments will return a list of unresolved Pagerduty incidents.
>`/resolve incidentID The cable was unplugged!`  

`/alert` This command will add and remove your username to the Alert List. Passing no arguments will return the Alert List usernames.
>`/alert` Returns the Alert List usernames.  
>`/alert add` Adds your username to the Alert List.  
>`/alert del` Removes your username from the Alert List.  
  
`/secret` Takes a Pagerduty Api Access Token and saves it.
>`/secret PagerdutyApiAccessToken`

## **Customizing the WickrIO Pagerduty bot**

If you would like to customize the WickrIO Pagerduty bot you can edit the `WickrIOPagerdutyBot.py` file in your editor or IDE of choice. Once you have completed your changes you can use the included `WickrIOPagerdutyBot.packer.json` file and Packer.io to create the container image and push it to Github. You will need to edit the `repository`, `login_username`, and `login_password` keys in the `post-processors` section of the `WickrIOPagerdutyBot.packer.json` file. If your code changes require new python modules make sure to include them in the `pip install flask requests` portion of the shell command in the `provisioners` section of the `WickrIOPagerdutyBot.packer.json` file. 

Build and push the container with the following command.

`sudo packer build WickrIOPagerdutyBot.packer.json`