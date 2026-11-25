#!/usr/bin/env python3
"""Configure an ephemeral checkout, without logging credentials."""
import json
import os
import re
from pathlib import Path

def configure(root, env):
    app_id = env.get('YORU_API_ID', '')
    app_hash = env.get('YORU_API_HASH', '')
    if not re.fullmatch(r'[1-9][0-9]{0,9}', app_id) or int(app_id) > 2147483647:
        raise ValueError('Set a valid YORU_API_ID secret')
    if not re.fullmatch(r'[a-fA-F0-9]{32}', app_hash):
        raise ValueError('Set a valid YORU_API_HASH secret')
    try:
        firebase = json.loads(env.get('YORU_FIREBASE_JSON', ''))
        packages = {c['client_info']['android_client_info']['package_name'] for c in firebase['client']}
    except (ValueError, KeyError, TypeError):
        raise ValueError('Invalid YORU_FIREBASE_JSON secret') from None
    required = {'org.yorugram.messenger.web', 'org.telegram.messenger'}
    if not required.issubset(packages):
        raise ValueError('Firebase must contain both the standalone package and the upstream library namespace')
    props = root / 'gradle.properties'
    if 'APP_PACKAGE=org.yorugram.messenger' not in props.read_text().splitlines():
        raise ValueError('YoruGram application ID missing')
    src = root / 'TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java'
    code = src.read_text()
    for pattern, replacement in [
        (r'(public static int APP_ID = )\d+;', r'\g<1>'+app_id+';'),
        (r'(public static String APP_HASH = )"[^"]*";', r'\g<1>"'+app_hash+'";')
    ]:
        code, count = re.subn(pattern, replacement, code)
        if count != 1:
            raise ValueError('Unexpected BuildVars structure')
    src.write_text(code)
    for module in ('TMessagesProj', 'TMessagesProj_AppStandalone'):
        (root / module / 'google-services.json').write_text(json.dumps(firebase))

if __name__ == '__main__':
    try:
        configure(Path.cwd(), os.environ)
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from None
    print('Build configuration prepared.')
