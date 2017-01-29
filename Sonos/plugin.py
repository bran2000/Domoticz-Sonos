#           Sonos Plugin
#
#           Author:     Tester22, 2016
#
"""
<plugin key="Sonos" name="Sonos Players" author="tester22" version="1.0" wikilink="http://www.domoticz.com/wiki/plugins/Sonos.html" externallink="https://sonos.com/">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="Update interval" width="150px" required="true" default="30"/>
        <param field="Mode2" label="Volume bar" width="75px">
            <options>
                <option label="True" value="Volume"/>
                <option label="False" value="Fixed"  default="true" />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import http.client
import xml.etree.ElementTree as ET

# player status
playerState = 0
mediaLevel = 0
mediaDescription = ""
muted = 2
creator = None
title = None

# Domoticz call back functions
def onStart():
    global playerState, mediaLevel
    if Parameters["Mode6"] == "Debug":
        Domoticz.Debugging(1)
    if (len(Devices) == 0):
        Domoticz.Device(Name="Status",  Unit=1, Type=17,  Switchtype=17).Create()
        if Parameters["Mode2"] == "Volume":
            Domoticz.Device(Name="Volume",  Unit=2, Type=244, Subtype=73, Switchtype=7,  Image=8).Create()
        Domoticz.Log("Devices created.")
    elif (Parameters["Mode2"] == "Volume" and 2 not in Devices):
        Domoticz.Device(Name="Volume",  Unit=2, Type=244, Subtype=73, Switchtype=7,  Image=8).Create()
        Domoticz.Log("Volume device created.")
    elif (Parameters["Mode2"] != "Volume" and 2 in Devices):
        Devices[2].Delete()
        Domoticz.Log("Volume device deleted.")
    else:
        if (1 in Devices): playerState = Devices[1].nValue
        if (2 in Devices): mediaLevel = Devices[2].nValue

    if is_number(Parameters["Mode1"]):
        if  int(Parameters["Mode1"]) < 30:
            Domoticz.Log("Update interval set to " + Parameters["Mode1"])
            Domoticz.Heartbeat(int(Parameters["Mode1"]))
        else:
            Domoticz.Heartbeat(30)
    else:
        Domoticz.Heartbeat(30)
    DumpConfigToLog()
    
    return True

def onConnect(Status, Description):
    return True

def onMessage(Data, Status, Extra):
    global playerState, mediaDescription, mediaLevel, muted, creator, title 
    xmltree = ET.fromstring(Data)
    sonosPlayRespone = xmltree.find('.//{urn:schemas-upnp-org:service:AVTransport:1}PlayResponse')
    sonosPauseRespone = xmltree.find('.//{urn:schemas-upnp-org:service:AVTransport:1}PauseResponse')
    sonosVolumeResponse = xmltree.findtext('.//{urn:schemas-upnp-org:service:RenderingControl:1}GetVolumeResponse/CurrentVolume')
    sonosMuteResponse = xmltree.findtext('.//{urn:schemas-upnp-org:service:RenderingControl:1}GetMuteResponse/CurrentMute')
    sonosSetVolumeResponse = xmltree.findtext('.//{urn:schemas-upnp-org:service:RenderingControl:1}SetVolumeResponse')
    sonosState = xmltree.findtext('.//CurrentTransportState')
    metaData = xmltree.findtext('.//TrackMetaData')
    uriMetaData = xmltree.findtext('.//CurrentURIMetaData')
    if sonosPlayRespone != None:
        playerState = 1
        UpdateDevice(1, playerState, mediaDescription)
    elif sonosPauseRespone != None:
        playerState = 0
        mediaDescription = ''
        UpdateDevice(1, playerState, mediaDescription)
    elif sonosVolumeResponse != None:
        mediaLevel = sonosVolumeResponse
        UpdateDevice(2, muted, mediaLevel)
    elif sonosMuteResponse != None:
        if sonosMuteResponse == "1":
            muted = 0
        else:
            muted = 2
        UpdateDevice(2, muted, mediaLevel)
    elif sonosState != None:
        if sonosState == 'PLAYING':
            playerState = 1
        if sonosState == 'PAUSED_PLAYBACK' or sonosState == 'STOPPED':
            playerState = 0
            mediaDescription = ''
        UpdateDevice(1, playerState, mediaDescription)
    elif metaData == "NOT_IMPLEMENTED":
        mediaDescription = "Grouped"
        UpdateDevice(1, playerState, mediaDescription)
    elif metaData != None:
        metaData = ET.fromstring(metaData)
        temp_creator = metaData.findtext('.//{http://purl.org/dc/elements/1.1/}creator')
        temp_title = metaData.findtext('.//{http://purl.org/dc/elements/1.1/}title')

        if temp_creator == None:
           # If creator is None this could be an radiostation.
           temp_title = metaData.findtext('.//{urn:schemas-rinconnetworks-com:metadata-1-0/}streamContent')
           sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetMediaInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetMediaInfo></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#GetMediaInfo', "/MediaRenderer/AVTransport/Control")
           
        if temp_creator != None:
            creator = temp_creator
        if temp_title != None:
            title = temp_title

        mediaDescription = str(creator) + " - " + str(title)
        #mediaDescription = ""
        UpdateDevice(1, playerState, mediaDescription)
        
    elif uriMetaData != None:
        metaData = ET.fromstring(uriMetaData)
        temp_creator = metaData.findtext('.//{http://purl.org/dc/elements/1.1/}title')

        if temp_creator != None:
            creator = temp_creator

        mediaDescription = str(creator) + " - " + str(title)
        #mediaDescription = ""
        UpdateDevice(1, playerState, mediaDescription)
    else:
        Domoticz.Debug(Data)

    return True

def onCommand(Unit, Command, Level, Hue):
    global playerID, mediaLevel
    Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "'")

    Command = Command.strip()
    action, sep, params = Command.partition(' ')
    action = action.capitalize()


    if (Unit == 1):  # Playback control
        if (action == 'On') or (action == 'Play'):
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#Play', "/MediaRenderer/AVTransport/Control")
        elif (action == 'Pause') or (action == 'Off'):
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Pause></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#Pause', "/MediaRenderer/AVTransport/Control")
        elif (action == 'Stop'):
            sendMessage('urn:schemas-upnp-org:service:AVTransport:1#Stop', '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Stop></s:Body></s:Envelope>', "/MediaRenderer/AVTransport/Control")
        elif (action == 'Next'):
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Next xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Next></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#Next', "/MediaRenderer/AVTransport/Control")
        elif (action == 'Previous'):
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Previous xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Previous></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#Previous', "/MediaRenderer/AVTransport/Control")
    if (Unit == 2):  # Volume control
        if (action == 'Set') and ((params.capitalize() == 'Level') or (Command.lower() == 'Volume')):
            mediaLevel = Level
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>' + str(mediaLevel) +  '</DesiredVolume></u:SetVolume></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#SetVolume', "/MediaRenderer/RenderingControl/Control")
            # Send an update request to get updated data from the player
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel></u:GetVolume></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#GetVolume', "/MediaRenderer/RenderingControl/Control")
        elif (action == 'On') or (action == 'Off'):
            if action == 'On':
                DesiredMute = "0"
            else:
                DesiredMute = "1"
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:SetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel><DesiredMute>' + DesiredMute + '</DesiredMute></u:SetMute></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#SetMute', "/MediaRenderer/RenderingControl/Control")
            sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel></u:GetMute></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#GetMute', "/MediaRenderer/RenderingControl/Control")
    return True

def onNotification(Data):
    Domoticz.Log("Notification: " + str(Data))
    return

def onHeartbeat():
    sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetTransportInfo></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo', "/MediaRenderer/AVTransport/Control")
    # Dont upate mediainfo if player is stopped
    if playerState == 1:
        sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Channel>Master</Channel></u:GetPositionInfo></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo', "/MediaRenderer/AVTransport/Control")
    if Parameters["Mode2"] == "Volume":
        sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel></u:GetVolume></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#GetVolume', "/MediaRenderer/RenderingControl/Control")
        sendMessage('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1"><InstanceID>0</InstanceID><Channel>Master</Channel></u:GetMute></s:Body></s:Envelope>', 'urn:schemas-upnp-org:service:RenderingControl:1#GetMute', "/MediaRenderer/RenderingControl/Control")
    return True

def onDisconnect():
    ClearDevices()
    return

def onStop():
    Domoticz.Log("onStop called")
    ClearDevices()
    return True

def sendMessage(data, method, url):
    global mediaDescription, playerState
    conn = http.client.HTTPConnection(Parameters["Address"] + ":1400")
    headers = {"Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": method}
    
    conn.request("POST", url, data, headers)
    response = conn.getresponse()
    conn.close()
    
    if response.status == 200:
        data = response.read().decode("utf-8")
        onMessage(data, "", "")
    return

# Device specific functions
def SyncDevices():
    global playerState, mediaDescription, mediaLevel
    # Make sure that the Domoticz devices are in sync (by definition, the device is connected)
    UpdateDevice(1, playerState, mediaDescription)
    UpdateDevice(2, 2, mediaLevel)
    return

def UpdateDevice(Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
            Devices[Unit].Update(nValue, str(sValue))
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return

def ClearDevices():
    global playerState, playerID, mediaLevel, mediaDescription
    # Stop everything and make sure things are synced
    playerState = 0
    mediaDescription = ""
    SyncDevices()
    return

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
    return

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False