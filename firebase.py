import os

import firebase_admin
from firebase_admin import credentials, messaging

_SERVICE_ACCOUNT_PATH = os.environ.get(
    'FIREBASE_SERVICE_ACCOUNT', './firebase-service-account.json'
)

cred = None

if os.path.exists(_SERVICE_ACCOUNT_PATH):
    cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
else:
    # Firebase is stubbed: no service account file present. The server will
    # run, but push-notification endpoints will fail until credentials exist.
    print(
        f"[firebase] Service account '{_SERVICE_ACCOUNT_PATH}' not found; "
        'Firebase disabled.'
    )