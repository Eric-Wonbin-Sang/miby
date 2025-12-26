from adb_shell.adb_device import AdbDeviceTcp, AdbDeviceUsb
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

# Load the public and private keys
# adbkey = 'path/to/adbkey'
# with open(adbkey) as f:
#     priv = f.read()
# with open(adbkey + '.pub') as f:
#      pub = f.read()
# signer = PythonRSASigner(pub, priv)

device2 = AdbDeviceUsb()
# device2.connect(rsa_keys=[signer], auth_timeout_s=0.1)
device2.connect(auth_timeout_s=0.1)
response2 = device2.shell('echo TEST2')
print("Response2:", response2)
