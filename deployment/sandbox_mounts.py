"""Remove personal-data bind mounts without deleting host data or named volumes."""
from pathlib import PurePosixPath

DATA = PurePosixPath('/opt/alfie/data')
CODE = (DATA / 'skills', DATA / 'scripts')


def restricted_mounts(volumes):
    result = []
    for volume in volumes:
        if isinstance(volume, str):
            parts = volume.split(':')
            if len(parts) < 2:
                raise ValueError('Explicit sandbox mount source and target required')
            source, target = parts[:2]
        elif isinstance(volume, dict):
            source, target = volume.get('source', ''), volume.get('target', '')
        else:
            raise ValueError('Unsupported sandbox mount')
        if not isinstance(source, str) or not isinstance(target, str) or not source or not target:
            raise ValueError('Explicit sandbox mount source and target required')
        path, destination = PurePosixPath(source), PurePosixPath(target)
        if '..' in path.parts or '..' in destination.parts:
            raise ValueError('Noncanonical sandbox mount')
        if path in DATA.parents:
            raise ValueError('Sandbox mount exposes a parent of private data')
        code = any(path == allowed or allowed in path.parents for allowed in CODE)
        private = (path == DATA or DATA in path.parents) and not code
        private = private or destination in (PurePosixPath('/opt/data'), PurePosixPath('/shared'))
        private = private or any(str(destination) == p or str(destination).startswith(p + '/')
                                 for p in ('/opt/data/shared', '/opt/data/security'))
        private = private or path.suffix in ('.db', '.sqlite', '.sqlite3')
        private = private or path.name in ('.env', 'auth.json', 'google_token.json',
                                          'google_client_secret.json', 'docker.sock')
        if private:
            continue
        if code:
            if isinstance(volume, str):
                # Preserve mount options apart from writable access.
                options = [x for x in (parts[2].split(',') if len(parts) > 2 else [])
                           if x not in ('rw', 'ro')]
                volume = source + ':' + target + ':' + ','.join(['ro', *options])
            else:
                volume = dict(volume, read_only=True)
        result.append(volume)
    return result
