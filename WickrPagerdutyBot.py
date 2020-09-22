#!/usr/bin/env python3
# Python Imports
from flask import Flask, request
import requests
import json
import os
from subprocess import Popen, PIPE, STDOUT
from datetime import datetime  
from datetime import timedelta
import uuid  
import redis


# Global Variables set from Container environment variables
botapiserverip = os.getenv('APISERVERIP')
botapiserverport = os.getenv('APISERVERPORT')
botapikey = os.getenv('BOTAPIKEY')
botsecret = os.getenv('BOTSECRET')


# Setup Redis db connection
db = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)


# Start application and env setup function
def startApp():
    app = Flask(__name__)
    botSetCallbackURL()
    return app


# Bot callback url function
def botSetCallbackURL():
    botHeaders = {'Accept': '*/*', 'Content-Type': 'application/json', 'Authorization': 'Basic {botsecret}'.format(botsecret=botsecret)}
    botWebInterfaceURL = "http://{botapiserverip}:{botapiserverport}/WickrIO/V1/Apps/{botapikey}".format(botapiserverip=botapiserverip, \
        botapiserverport=botapiserverport, botapikey=botapikey)
    botCallbackIPCmd = "ip route get 1 | awk '{print $7}' | tr -d '\\n'"
    botCallbackIPProcess = Popen(botCallbackIPCmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    botCallbackIPOutput = botCallbackIPProcess.stdout.read()
    botCallbackIP = os.getenv('CALLBACKIP') if os.getenv('CALLBACKIP') is not None else str(botCallbackIPOutput)[2:-1]
    botCallbackPort = os.getenv('LISTEN_PORT')
    botCallbackURL = "http://{botCallbackIP}:{botCallbackPort}/callback".format(botCallbackIP=botCallbackIP, botCallbackPort=botCallbackPort)
    botCallbackPayload = {'callbackurl': '{botCallbackURL}'.format(botCallbackURL=botCallbackURL)}
    botMsgRecvCallbackURL = botWebInterfaceURL + "/MsgRecvCallback"
    try:
        setMsgRecvCallback = requests.post(botMsgRecvCallbackURL, headers=botHeaders, params=botCallbackPayload)
        print("Setting Callback URL")
        getMsgRecvCallback = requests.get(botMsgRecvCallbackURL, headers=botHeaders)
        callbackStatus = "Callback POST Response :", setMsgRecvCallback.text, " Callback GET Response :", getMsgRecvCallback.text
        print(callbackStatus)
        return setMsgRecvCallback.text
    except Exception as e: 
        print("Error setting Callback URL!!!", e)
        return e


# Flask app object
application = startApp()


# Pagerduty send message function   # TODO parse Pagerduty error messages https://developer.pagerduty.com/docs/rest-api-v2/errors/ 
def pdSendMsg(method, url, pdHeaders, payload):
    try:
        sendMessage = requests.request(method=method, url=url, headers=pdHeaders, data=json.dumps(payload))
    except requests.exceptions.RequestException as e:
        error = str(e)
        errorMsg = {
            'error': {
                'error': 'Error communicating with the Pagerduty API:',
                'message': '{error}'.format(error=error)
            }
        }
        return json.dumps(errorMsg)
    print('Status Code: {code}'.format(code=sendMessage.status_code))
    print(sendMessage.text)
    return sendMessage.json()


# Pagerduty snooze incident function
def pdSnoozeIncident(incidentID, duration, description, email):
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"
    pdHeaders['From'] = email
    pdEndpoint = "/incidents/{incidentID}/snooze".format(incidentID=incidentID)
    url = pdURL + pdEndpoint
    payload = {
        'content': description,
        'duration': 60 * duration,
    }
    method = "POST"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty update incident function
def pdUpdateIncident(incidentID, incidentStatus, incidentSummary, email):
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"
    pdHeaders['From'] = email
    pdEndpoint = "/incidents/{incidentID}".format(incidentID=incidentID)
    url = pdURL + pdEndpoint
    payload = {
        'incident': {
            'type': "incident",
            'summary': incidentSummary,
            'status': incidentStatus,
            'escalation_level': 1,
            'assigned_to_user': "",
            'escalation_policy': ""
        }
    }
    method = "PUT"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty trigger incident function
def pdTriggerIncident(serviceID, description, email):
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"    
    pdHeaders['From'] = email
    pdEndpoint = "/incidents"
    url = pdURL + pdEndpoint
    incidentKey = str(uuid.uuid4().hex)
    payload = {
        "incident": {
            "type": "incident",
            "title": "{description}".format(description=description),
            "service": {
                "id": serviceID,
                "type": "service_reference"
            },
            "incident_key": incidentKey,
            "body": {
                "type": "incident_body",
                "details": "{description}".format(description=description)
            }
          }
        }
    method = "POST"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty create maintenance window function
def pdCreateMaintenanceWindow(startTime, endTime, description, serviceID, email):
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"
    pdHeaders['From'] = email
    payload = {
        'maintenance_window': {
            'start_time': startTime,
            'end_time': endTime,
            'description': description,
            'services': [{
                'id': serviceID,
                'type': 'service_reference'
            }],
            'teams': [],
            'type': 'maintenance_window'
        }
    }
    pdEndpoint = "/maintenance_windows"
    url = pdURL + pdEndpoint
    method = "POST"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty list services function
def pdListServices():
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    payload = {
        'team_ids[]': [],
        'time_zone': 'UTC',
        'sort_by': 'name',
        'query': '',
        'include[]': []
        }
    pdURL = "https://api.pagerduty.com"
    pdEndpoint = "/services"
    url = pdURL + pdEndpoint
    method = "GET"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty list incidents function
def pdListIncidents():
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"
    payload = {}
    pdEndpoint = '/incidents?statuses%5B%5D=triggered&statuses%5B%5D=acknowledged'
    url = pdURL + pdEndpoint
    method = "GET"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Pagerduty get escalation policy function
def pdGetEscalationPolicy(serviceID):
    pdSecret = db.get('pdSecret')
    pdHeaders = {'Accept': 'application/vnd.pagerduty+json;version=2', 'Content-type': 'application/json', 'Authorization': \
        'Token token={token}'.format(token=pdSecret)}
    pdURL = "https://api.pagerduty.com"
    payload = {
        'include[]': []
    }
    pdEndpoint = "/escalation_policies/{serviceID}".format(serviceID=serviceID)
    url = pdURL + pdEndpoint
    method = "GET"
    sendMessage = pdSendMsg(method, url, pdHeaders, payload)
    return sendMessage


# Bot send direct message function
def botSendMsg(sender, retMessage):
    if len(sender) == 64:
        botSendVgroupID(sender, retMessage)
    botHeaders = {'Accept': '*/*', 'Content-Type': 'application/json', 'Authorization': 'Basic {botsecret}'.format(botsecret=botsecret)}
    botWebInterfaceURL = "http://{botapiserverip}:{botapiserverport}/WickrIO/V1/Apps/{botapikey}".format(botapiserverip=botapiserverip, \
        botapiserverport=botapiserverport, botapikey=botapikey)
    data = {
    "message": retMessage,
    "users": [
        {"name": sender}
    ]  
    }
    try:
        sendMessage = requests.post(botWebInterfaceURL + "/Messages", headers=botHeaders, data=json.dumps(data))
    except Exception as e:
        print("Error sending message: ", e)
        return "Error 500", e
    return sendMessage


# Bot send vgroupid message function
def botSendVgroupID(vgroupid, retMessage):
    botHeaders = {'Accept': '*/*', 'Content-Type': 'application/json', 'Authorization': 'Basic {botsecret}'.format(botsecret=botsecret)}
    botWebInterfaceURL = "http://{botapiserverip}:{botapiserverport}/WickrIO/V1/Apps/{botapikey}".format(botapiserverip=botapiserverip, \
        botapiserverport=botapiserverport, botapikey=botapikey)
    data = {
    "message": retMessage,
    "vgroupid": vgroupid
    }
    try:
        sendMessage = requests.post(botWebInterfaceURL + "/Messages", headers=botHeaders, data=json.dumps(data))
    except Exception as e:
        print("Error sending message: ", e)
        return "Error 500"
    return sendMessage.text


# Bot get rooms function
def botGetRooms():
    botHeaders = {'Accept': '*/*', 'Content-Type': 'application/json', 'Authorization': 'Basic {botsecret}'.format(botsecret=botsecret)}
    botWebInterfaceURL = "http://{botapiserverip}:{botapiserverport}/WickrIO/V1/Apps/{botapikey}".format(botapiserverip=botapiserverip, \
        botapiserverport=botapiserverport, botapikey=botapikey)
    rooms = requests.get(botWebInterfaceURL + "/Rooms", headers=botHeaders)
    return rooms.json()
    

# Bot help command function
def botHelpCmd(sender):
    retMessage = '''
Welcome to the WickrIO Pagerduty bot!\n
Valid commands are:\n
/services  `List Services and the associated Oncalls`\n
/incidents  `List unresolved Incidents`\n
/maint  `Set a Maintenance Window for one Service or for all Services`\n
/trigger  `Trigger an Incident for a Service.`\n
/ack  `Acknowledge an Incident.`\n
/snooze  `Snooze an Acknowledged Incident.`\n
/resolve  `Resolve an Incident.`\n
/alert  `Add yourself, Remove yourself, or display the Incident Alert list.`'''
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)


# Bot services command function
def botServicesCmd(sender, botCmdErrorMessage):
    pdServices = pdListServices()
    if "error" in pdServices:
        print(pdServices['error']['message'])
        retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=pdServices['error']['message'], \
        errorErrors=str(pdServices['error']['errors']).strip("[]'"))
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return
    serviceDetails = ""
    for service in pdServices['services']:
        escPol = pdGetEscalationPolicy(service['escalation_policy']['id'])
        if "error" in escPol:
            retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=escPol['error']['message'], \
            errorErrors=str(escPol['error']['errors']).strip("[]'"))
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
            return
        print(escPol['escalation_policy']['escalation_rules'][0]['targets'][0]['summary'])
        targets = escPol['escalation_policy']['escalation_rules'][0]['targets']
        serviceOncalls = ""
        for target in targets:
            serviceOncalls = serviceOncalls + str(target['summary']) + ", " if target['type'] == "user_reference" else serviceOncalls
        serviceOncalls = serviceOncalls[:-2]
        serviceDetails = serviceDetails + "Service name: {name}\nService id: {serviceID}\nService oncalls: \
{serviceOncalls} \n\n".format(name=service['name'],serviceID=service['id'], serviceOncalls=serviceOncalls)
    retMessage = botCmdErrorMessage + serviceDetails[:-3]
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return


# Bot incidents command function
def botIncidentsCmd(sender, botCmdErrorMessage):
    rawPdIncidents = pdListIncidents()
    if str(rawPdIncidents)[2:7] == "error":  
        print(rawPdIncidents['error']['message'])
        retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=rawPdIncidents['error']['message'], \
        errorErrors=str(rawPdIncidents['error']['errors']).strip("[]'"))
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    pdIncidents = ""
    for incident in rawPdIncidents['incidents']:
        pdIncidents = pdIncidents + "Incident ID: {incidentID}\nIncident status: {incidentStatus}\nIncident description: \
{incidentName} \n\n".format(incidentID = incident['id'], incidentStatus = incident['status'], incidentName = incident['description'])
    pdIncidents = "There are no unresolved Incidents. " if pdIncidents == "" else pdIncidents[:-3]
    retMessage = botCmdErrorMessage + pdIncidents
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot resolve command function
def botResolveCmd(command, sender):
    incidentSummary = "Incident Resolved by WickrIO Pagerduty bot."
    try:
        incidentID = command[1]
        incidentSummary = command[2:]
        incidentStatus = "resolved"
        email = sender
    except (IndexError, ValueError):
        botCmdErrorMessage = "Missing an argument, please retry with this format.\n/resolve incidentID description\nThe description is \
optional.\n\nCurrent unresolved Incidents:\n\n"
        reply = botIncidentsCmd(sender, botCmdErrorMessage)
        return reply
    pdUpdate = pdUpdateIncident(incidentID, incidentStatus, incidentSummary, email)
    if "incident" in pdUpdate:
        retMessage = "Incident Update was successful."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    retMessage = "Error: {errorMessage}".format(errorMessage=pdUpdate['error']['message'].strip("[]'"))
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot maint command function
def botMaintCmd(command, sender):
    description = "Maintenance Window created by the WickrIO Pagerduty bot."
    try:
        serviceID = command[1] if len(command[1]) == 7 else ""
        duration = int(command[2]) if int(command[2]) in range(1441) else ""
        description = command[3:]
        email = sender
    except (IndexError, ValueError):
        botCmdErrorMessage = "Argument error, please retry with this format.\n/maint serviceID duration description\nTo set a Maintenance \
Window for all Services use `all` for the `serviceID`.\nDuration is in minutes.\nThe description is optional.\n\nCurrent Services:\n\n"
        reply = botServicesCmd(sender, botCmdErrorMessage)
        return reply
    startTime = datetime.utcnow()
    endTime = startTime + timedelta(minutes=int(duration))
    if str(serviceID) == "all":
        pdServices = pdListServices()
        if "error" in pdServices:
            print(pdServices['error']['message'])
            retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=pdServices['error']['message'], \
                errorErrors=str(pdServices['error']['errors']).strip("[]'"))
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
            return reply
        serviceIDs = []
        for service in pdServices['services']:
            serviceIDs.append(service['id'])
        print(serviceIDs)
        for serviceID in serviceIDs:
            maintWindow = pdCreateMaintenanceWindow(startTime.isoformat(), endTime.isoformat(), description, serviceID, email)
            print(maintWindow)
            if "maintenance_window" in maintWindow:
                retMessage = "Maintenance Window creation successful."
                reply = botSendMsg(sender, retMessage)
                print("Bot Api Response was :", reply)
            print(maintWindow['error']['message'])
            retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=maintWindow['error']['message'], \
                errorErrors=str(maintWindow['error']['errors']).strip("[]'"))
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
        return reply
    maintWindow = pdCreateMaintenanceWindow(startTime.isoformat(), endTime.isoformat(), description, serviceID, email)
    print(maintWindow)
    if "maintenance_window" in maintWindow:
        retMessage = "Maintenance Window creation successful."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    print(maintWindow['error']['message'])
    retMessage = "Error: {errorMessage}: {errorErrors}".format(errorMessage=maintWindow['error']['message'], \
        errorErrors=str(maintWindow['error']['errors']).strip("[]'"))
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot alert command function
def botPdAlertListCmd(command, sender):
    pdAlertList = db.lrange('pdAlertList', 0, -1) if db.exists('pdAlertList') else []
    print(pdAlertList)
    try:
        pdAlertCmd = command[1]
    except (IndexError, ValueError):
        retMessage = "Pagerduty alert list: " + str(pdAlertList) + "\n\nUse /alert add to add yourself to the alert list.\nUse \
/alert del to remove yourself from the alert list."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return
    else:
        if len(sender) == 64:
            retMessage = "You cannot add a room to the Alert List. The Pagerduty bot will automatically send Incoming Pagerduty \
Alerts to any room it is in. To add a user to the Alert List message the Pagerduty bot 1:1."
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
            return
        if pdAlertCmd == "add":
            db.lpush('pdAlertList', "{sender}".format(sender=sender))
            db.save()
            pdAlertList = db.lrange('pdAlertList', 0, -1)
            retMessage = "Pagerduty alert list updated: " + str(pdAlertList)
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
            return
        if command[1] == "del":
            db.lrem('pdAlertList', 0, "{sender}".format(sender=sender))
            db.save()
            pdAlertList = db.lrange('pdAlertList', 0, -1)
            retMessage = "Pagerduty alert list updated: " + str(pdAlertList)
            reply = botSendMsg(sender, retMessage)
            print("Bot Api Response was :", reply)
            return
    

# Bot trigger command function
def botTriggerCmd(command, sender):
    description = ""
    try:
        serviceID = command[1]
        description = " ".join(command[2:])
        print("description", description)
        email = sender
    except (IndexError, ValueError):
        botCmdErrorMessage = "Missing an argument, please retry with this format.\n/trigger serviceID description\nThe description is \
optional.\n\nCurrent Services:\n\n"
        reply = botServicesCmd(sender, botCmdErrorMessage)
        return reply
    description = description if description != "" else "Incident Triggered by WickrIO Pagerduty bot."
    pdTrigger = pdTriggerIncident(serviceID, description, email)
    if "incident" in pdTrigger:
        retMessage = "Incident Trigger creation successful."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    retMessage = "Error: {errorMessage}".format(errorMessage=pdTrigger['error']['message'].strip("[]'"))
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot ack command function
def botAckCmd(command, sender):
    incidentSummary = "Incident Acknowledged by WickrIO Pagerduty bot."
    try:
        incidentID = command[1]
        incidentSummary = command[2:]
        incidentStatus = "acknowledged"
        email = sender
    except (IndexError, ValueError):
        botCmdErrorMessage = "Missing an argument, please retry with this format.\n/ack incidentID description\nThe description is \
optional.\n\nCurrent unresolved Incidents:\n\n"
        reply = botIncidentsCmd(sender, botCmdErrorMessage)
        return reply
    pdUpdate = pdUpdateIncident(incidentID, incidentStatus, incidentSummary, email)
    if "incident" in pdUpdate:
        retMessage = "Incident Update was successful."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    retMessage = "Error: {errorMessage}".format(errorMessage=pdUpdate['error']['message'].strip("[]'"))
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot snooze command function
def botSnoozeCmd(command, sender):
    description = "Incident Snoozed by WickrIO Pagerduty bot."
    try:
        incidentID = command[1] if len(command[1]) == 7 else ""
        duration = int(command[2]) if int(command[2]) in range(1441) else ""
        description = command[3:]
        email = sender
    except (IndexError, ValueError):
        botCmdErrorMessage = "Missing an argument, please retry with this format.\n/snooze incidentID description\nThe description is \
optional.\n\nCurrent unresolved Incidents:\n\n"
        reply = botIncidentsCmd(sender, botCmdErrorMessage)
        return reply
    pdSnooze = pdSnoozeIncident(incidentID, duration, description, email)
    if "incident" in pdSnooze:
        retMessage = "Incident Snooze was successful."
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    retMessage = "Error: {errorMessage}".format(errorMessage=pdSnooze['error']['message'].strip("[]'"))
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


def botPdSecretCmd(command, sender):
    try:
        pdSecret = command[1]
    except (IndexError, ValueError):
        retMessage = "Argument error, please retry with the following format:\n\n/secret PagerdutyApiAccessToken"
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
        return reply
    db.set('pdSecret', '{pdSecret}'.format(pdSecret=pdSecret))
    db.save()
    retMessage = "Pagerduty Api Access Token added!\nThe Alert List must contain at least one user.\nAdd your username with:\n/alert add"
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return reply


# Bot other message function
def botOther(sender):
    retMessage = "Unknown command! Please use the /help command to list commands."
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    print("Unknown command.")
    return reply


def botProcessCmd(command, sender, botCmdErrorMessage):
    # Help command
    if command[0] == "/help":
        botHelpCmd(sender)
        return "OK 200"
    # Create Maintenance Window command
    if command[0] == "/maint":
        botMaintCmd(command, sender)
        return "OK 200"
    # List Services command
    if command[0] == "/services":
        botServicesCmd(sender, botCmdErrorMessage)
        return "OK 200"
    # List Incidents command
    if command[0] == "/incidents":
        botIncidentsCmd(sender, botCmdErrorMessage)
        return "OK 200"
    # Set Pagerduty Alert command
    if command[0] == "/alert":
        botPdAlertListCmd(command, sender)
        return "OK 200"
    # Pagerduty Trigger command
    if command[0] == "/trigger":
        botTriggerCmd(command, sender)
        return "OK 200"
    # Pagerduty Resolve command
    if command[0] == "/resolve":
        botResolveCmd(command, sender)
        return "OK 200"
    # Pagerduty Ack command
    if command[0] == "/ack":
        botAckCmd(command, sender)
        return "OK 200"
    # Pagerduty Snooze command
    if command[0] == "/snooze":
        botSnoozeCmd(command, sender)
        return "OK 200"
    # Pagerduty Secret command
    if command[0] == "/secret":
        botPdSecretCmd(command, sender)
        return "OK 200"
    # Any other commands are replied to with a help message
    botOther(sender)
    return "OK 200"



# Incidents route where incoming Pagerduty messages are received and processed
@application.route('/incidents', methods=['POST'])
def newPdIncident():
    newPdIncident = request.get_json()
    print("New Incoming Pagerduty Incident: ", newPdIncident)
    pdIncident = json.dumps(newPdIncident['messages'][0]['incident']['id']).strip("\"")
    pdIncidentEvent = json.dumps(newPdIncident['messages'][0]['event']).strip("\"")
    pdIncidentStatus = json.dumps(newPdIncident['messages'][0]['incident']['status']).strip("\"")
    pdIncidentServiceID = json.dumps(newPdIncident['messages'][0]['incident']['service']['id']).strip("\"")
    pdIncidentServiceName = json.dumps(newPdIncident['messages'][0]['incident']['service']['name']).strip("\"")
    try:
        pdIncidentDesc = json.dumps(newPdIncident['messages'][0]['log_entries'][0]['channel']['details']).strip("\"")
    except KeyError:
        pass
    pdIncidentDesc = json.dumps(newPdIncident['messages'][0]['incident']['title']).strip("\"")
    retMessage = "Pagerduty Incident ID: {pdIncident}\n Incident Type: {pdIncidentEvent}\nIncident Status: {pdIncidentStatus}\nService ID: \
{pdIncidentServiceID}\nService Name: {pdIncidentServiceName}\nIncident Description: {pdIncidentDesc}".format(pdIncident=pdIncident, \
            pdIncidentEvent=pdIncidentEvent, pdIncidentStatus=pdIncidentStatus, pdIncidentServiceID=pdIncidentServiceID, \
                pdIncidentServiceName=pdIncidentServiceName, pdIncidentDesc=pdIncidentDesc)
    pdAlertList = db.lrange('pdAlertList', 0, -1)
    for pdUser in pdAlertList:
        sender = str(pdUser).strip("[]'")
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply)
    rooms = botGetRooms()
    for room in rooms['rooms']:
        vgroupid = room['vgroupid']
        reply = botSendVgroupID(vgroupid, retMessage)
        print("Bot Api Response was :", reply)  
    return "OK 200"


# Callback route where incoming Wickr messages are received and processed
@application.route('/callback', methods=['POST'])
def getNewMessage():
    newMessage = request.get_json()
    print("New Incoming Message: ", newMessage)
    if str(newMessage)[2:9] != "message":
        print("Control/Call/File Message.")
        return "OK 200"
    command = list(newMessage['message'].split())
    print("Command = ", command)
    botCmdErrorMessage = ""
    sender = newMessage['sender']
    print(sender)
    if db.exists('pdSecret') == True:
        if db.exists('pdAlertList') == True:
            if "@" in command[0]:
                sender = newMessage['vgroupid']
                command[0] = command[0].split("@")[0]
            print(command[0])
            botProcessCmd(command, sender, botCmdErrorMessage)
            return "OK 200"
        # Set Pagerduty Alert command
        if command[0] == "/alert":
            botPdAlertListCmd(command, sender)
            return "OK 200"
        retMessage = "The Pagerduty Alert list is empty. Please add at least one user with:\n/alert add"
        reply = botSendMsg(sender, retMessage)
        print("Bot Api Response was :", reply) 
        return "OK 200"
    # Pagerduty Secret command
    if command[0] == "/secret":
        botPdSecretCmd(command, sender)
        return "OK 200"
    retMessage = "The Pagerduty Api Access Token is not set. Please add it with:\n/secret PagerdutyApiAccessToken"
    reply = botSendMsg(sender, retMessage)
    print("Bot Api Response was :", reply)
    return "OK 200"


if __name__ == "__main__":
    application.run(host='0.0.0.0', port=os.getenv('LISTEN_PORT'), debug=True)