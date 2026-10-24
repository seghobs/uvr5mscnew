"""Watch saved source content; debounce edits and reuse the safe restart pipeline."""
from contextlib import contextmanager
import os
from pathlib import Path
import time
from studio_build import ROOT,fingerprint,manifest


class QuietChanges:
    def __init__(self,digest,quiet=15):
        self.last=digest;self.attempted=digest;self.changed_at=0;self.quiet=quiet

    def ready(self,digest,now):
        if digest!=self.last:
            self.last=digest;self.changed_at=now
        return digest!=self.attempted and now-self.changed_at>=self.quiet


@contextmanager
def singleton():
    folder=ROOT/'.runtime';folder.mkdir(exist_ok=True)
    with (folder/'source-watch.lock').open('a+b') as handle:
        handle.write(b'0');handle.flush();handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            yield False;return
        try:yield True
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)


def watch():
    import service_control as service
    import studio_restart as restart
    with singleton() as owner:
        if not owner:return
        baseline=manifest().get('digest') or fingerprint()
        changes=QuietChanges(baseline)
        absent=0
        print('Kod izleyici acik: 15 saniye sabit kalan kaynaklar otomatik derlenir.',flush=True)
        while not (ROOT/'.runtime/uninstalling').exists():
            time.sleep(2)
            current=restart.status()
            active=current.get('phase') not in ('idle','completed','failed')
            if not service.frontend_running() and not active:
                absent+=2
                if absent>=90:return
            else:absent=0
            try:
                digest=fingerprint()
                ready=changes.ready(digest,time.monotonic())
            except (OSError,ValueError):continue
            if absent or active or not ready:continue
            if manifest().get('digest')==digest:
                changes.attempted=digest;continue
            # Failure is retried only after another source edit, never in a loop.
            changes.attempted=digest
            result=restart.request(automatic=True)
            print('Otomatik derleme: '+result.get('id',''),flush=True)


if __name__=='__main__':watch()
