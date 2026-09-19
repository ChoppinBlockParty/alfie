"""Operator-only encrypted backup transfer. Not registered as an agent tool.

Run in the gateway with its existing narrow Drive credentials. Configuration and receipts
contain account identifiers: pipe stdout only to private files, never repository artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, '/opt/alfie-google/scripts')


def folders(service, name, parent=None):
    query = "trashed=false and mimeType='application/vnd.google-apps.folder' and name='" + name + "'"
    if parent:
        query += " and '" + parent + "' in parents"
    result = service.files().list(q=query, fields='files(id,parents),nextPageToken', pageSize=100).execute()
    if result.get('nextPageToken'):
        raise ValueError('Ambiguous destination')
    return result.get('files', [])


def configure(service):
    roots = folders(service, 'Alfie')
    if len(roots) != 1:
        raise ValueError('Expected exactly one accessible owner-approved Alfie folder')
    parent = roots[0]['id']
    children = folders(service, 'backup', parent)
    if len(children) > 1:
        raise ValueError('Ambiguous backup folder')
    folder = children[0] if children else service.files().create(
        body={'name': 'backup', 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent]},
        fields='id').execute()
    return {'parent': parent, 'folder': folder['id'], 'version': 1}


def validate_destination(service, config):
    item = service.files().get(fileId=config['folder'], fields='id,name,mimeType,parents,trashed').execute()
    if item.get('trashed') or item.get('name') != 'backup' or config['parent'] not in item.get('parents', []) \
            or item.get('mimeType') != 'application/vnd.google-apps.folder':
        raise ValueError('Pinned backup destination changed')


def digest(path, algorithm):
    h = hashlib.new(algorithm)
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def upload(service, config, path):
    from googleapiclient.http import MediaFileUpload
    validate_destination(service, config)
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix != '.cms':
        raise ValueError('Only encrypted CMS backup artifacts may be transferred')
    # Bounded format sanity check, not cryptographic verification. Input comes only from
    # the trusted operator encryptor; authenticity is verified on the recovery Mac.
    # CMS authEnvelopedData and AES-256-GCM DER OIDs are present in its envelope header.
    with path.open('rb') as stream:
        header = stream.read(4096)
    if bytes.fromhex('060b2a864886f70d0109100117') not in header \
            or bytes.fromhex('060960864801650304012e') not in header:
        raise ValueError('Not an authenticated encrypted backup')
    sha = digest(path, 'sha256')
    # A content-addressed name makes an uncertain create reconcilable. Never overwrite/delete.
    name = 'backup-' + sha + '.cms'
    query = "trashed=false and name='" + name + "' and '" + config['folder'] + "' in parents"
    existing = service.files().list(q=query, fields='files(id,size,md5Checksum),nextPageToken', pageSize=100).execute()
    if existing.get('nextPageToken') or len(existing.get('files', [])) > 1:
        raise ValueError('Ambiguous existing upload; reconcile privately')
    items = existing.get('files', [])
    if items:
        item = items[0]
    else:
        media = MediaFileUpload(str(path), mimetype='application/octet-stream', resumable=True, chunksize=8 * 1024 * 1024)
        request = service.files().create(body={'name': name, 'parents': [config['folder']]},
                                         media_body=media, fields='id,size,md5Checksum')
        item = None
        while item is None:
            _, item = request.next_chunk(num_retries=0)
    if int(item.get('size', -1)) != path.stat().st_size or item.get('md5Checksum') != digest(path, 'md5'):
        raise ValueError('Uploaded artifact integrity mismatch')
    return {'file': item['id'], 'folder': config['folder'], 'sha256': sha, 'size': path.stat().st_size}


def download(service, config, receipt, destination):
    from googleapiclient.http import MediaIoBaseDownload
    validate_destination(service, config)
    if receipt['folder'] != config['folder']:
        raise ValueError('Receipt destination mismatch')
    item = service.files().get(fileId=receipt['file'], fields='parents,size,trashed').execute()
    if item.get('trashed') or config['folder'] not in item.get('parents', []) or int(item['size']) != receipt['size']:
        raise ValueError('Remote backup changed')
    destination = Path(destination)
    with destination.open('xb') as stream:
        downloader = MediaIoBaseDownload(stream, service.files().get_media(fileId=receipt['file']), chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=0)
    if digest(destination, 'sha256') != receipt['sha256']:
        raise ValueError('Downloaded backup digest mismatch')
    return {'verified': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'upload', 'download'))
    parser.add_argument('--config')
    parser.add_argument('--file')
    parser.add_argument('--receipt')
    args = parser.parse_args()
    import google_api
    try:
        service = google_api.build_service('drive', 'v3')
        if args.action == 'configure':
            result = configure(service)
        else:
            config = json.loads(Path(args.config).read_text())
            result = upload(service, config, args.file) if args.action == 'upload' else download(
                service, config, json.loads(Path(args.receipt).read_text()), args.file)
        print(json.dumps(result, sort_keys=True))
    except Exception:
        raise SystemExit('Backup transfer failed; reconcile privately before retrying') from None
