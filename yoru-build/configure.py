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
        project_number = firebase['project_info']['project_number']
        clients = [c for c in firebase['client'] if
                   c['client_info']['android_client_info']['package_name'] == 'org.yorugram.messenger.web']
    except (ValueError, KeyError, TypeError):
        raise ValueError('Invalid YORU_FIREBASE_JSON secret') from None
    if len(clients) != 1:
        raise ValueError('Firebase must contain exactly one client for org.yorugram.messenger.web')
    try:
        client = clients[0]
        required_values = (
            project_number,
            client['client_info']['mobilesdk_app_id'],
            client['api_key'][0]['current_key'],
        )
        if not all(isinstance(value, str) and value for value in required_values):
            raise ValueError()
    except (IndexError, KeyError, TypeError, ValueError):
        raise ValueError('Incomplete Firebase configuration for org.yorugram.messenger.web') from None
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
    services = root / 'TMessagesProj_AppStandalone/src/afatDebug/google-services.json'
    services.parent.mkdir(parents=True, exist_ok=True)
    services.write_text(json.dumps(firebase), encoding='utf-8')
    src.write_text(code, encoding='utf-8')

if __name__ == '__main__':
    try:
        configure(Path.cwd(), os.environ)
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from None
    print('Build configuration prepared.')
