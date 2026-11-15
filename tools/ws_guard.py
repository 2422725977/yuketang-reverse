
p="applibs/libapp.so"
data=open(p,"rb").read()
addrs={"WSConnector::send":0x91e988,"WSConnector::connect":0xc15220,"WSConnector::WSConnector":0xc15134,
"ReceiverProcesser::process":0x142515c,"RemoteControlProcesser::process":0x143a028,
"_ReceiverClassPageState::_connectSocket":0xc15048,"_ReceiverClassPageState::_reConnectSocket":0xd3bfd0,
"WSConnector::_scheduleReconnect":0xc19190,"WSConnector::_tryReconnectAfterDelay":0xc191f8,
"WSConnector::_teardownChannel":0xc1905c,"WSConnector::pauseProcessing":0xc534c0,"WSConnector::resumeProcessing":0xfade34,
"_ReceiverClassPageState::_postLessonCheckin":0xc196cc,"WssLocationCheckinSignin.fromMap":0x143c72c}
for k,v in addrs.items():
    b=data[v:v+12]
    print("%-44s 0x%08x  %s  guard=[%s, %s]" % (k,v," ".join("%02x"%x for x in b), b[0:4].hex(), b[8:12].hex()))
