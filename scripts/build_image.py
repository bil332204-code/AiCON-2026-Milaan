"""Build the integrated app while preserving configured proxy routing and TLS trust."""
import os
import socket
import ssl
import subprocess
from urllib.parse import urlsplit

args=['docker','build']
proxy=urlsplit(os.environ.get('HTTPS_PROXY',''))
if proxy.hostname:
    # Docker builder DNS may not know the managed environment's proxy hostname.
    address=socket.getaddrinfo(proxy.hostname,None,socket.AF_INET)[0][4][0]
    args+=['--add-host',f'{proxy.hostname}:{address}']
    for name in ['HTTPS_PROXY','HTTP_PROXY','NO_PROXY']:
        if name in os.environ:args+=['--build-arg',name]
bundle=ssl.get_default_verify_paths().cafile
if bundle and os.path.isfile(bundle):args+=['--secret',f'id=build_ca,src={bundle}']
args+=['-t',os.getenv('MILAAN_SMOKE_IMAGE','milaan-v3-review:local'),'.']
raise SystemExit(subprocess.run(args).returncode)
