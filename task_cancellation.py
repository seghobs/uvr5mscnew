"""Cooperative cancellation for background jobs without stopping the API."""
from contextlib import contextmanager
import functools
import threading


class TaskCancelled(BaseException):
    """Bypass pipeline retry/fallback handlers, but run their finally blocks."""


class TaskCancellation:
    def __init__(self):
        self.lock=threading.RLock()
        self.local=threading.local()
        self.events={}
        self.processes={}
        self.running=set()

    def register(self, identifier):
        with self.lock:self.events.setdefault(identifier,threading.Event())

    def checkpoint(self, identifier=None):
        event=self.events.get(identifier) if identifier is not None else getattr(self.local,'event',None)
        if event is not None and event.is_set():raise TaskCancelled()

    @contextmanager
    def commit(self):
        # A cancellation and a saved result have an unambiguous order.
        with self.lock:
            self.checkpoint()
            yield

    def task(self, function):
        @functools.wraps(function)
        def run(identifier,*args,**kwargs):
            self.register(identifier)
            previous=getattr(self.local,'event',None)
            self.local.event=self.events[identifier]
            with self.lock:self.running.add(identifier)
            try:
                self.checkpoint()
                return function(identifier,*args,**kwargs)
            except TaskCancelled:
                return None
            finally:
                self.local.event=previous
                with self.lock:
                    self.events.pop(identifier,None)
                    self.running.discard(identifier)
                    for process,event in list(self.processes.items()):
                        if process.poll() is not None:self.processes.pop(process,None)
        return run

    def cancel(self, identifiers):
        with self.lock:
            for identifier in identifiers:
                self.register(identifier)
                self.events[identifier].set()
            processes=[p for p,event in self.processes.items() if event.is_set()]
        # Terminate only subprocesses registered by cancelled jobs, never the API.
        for process in processes:
            if process.poll() is None:
                try:
                    import psutil
                    children=psutil.Process(process.pid).children(recursive=True)
                    for child in reversed(children):
                        try:child.kill()
                        except psutil.Error:pass
                    process.kill()
                except (psutil.Error,OSError):pass

    def popen_class(self, base):
        owner=self
        class CancellablePopen(base):
            def __init__(self,*args,**kwargs):
                # Serialize spawn with cancel, so no process can escape the signal.
                with owner.lock:
                    owner.checkpoint()
                    super().__init__(*args,**kwargs)
                    event=getattr(owner.local,'event',None)
                    if event is not None:owner.processes[self]=event

            def wait(self,*args,**kwargs):
                result=super().wait(*args,**kwargs)
                with owner.lock:owner.processes.pop(self,None)
                return result

        return CancellablePopen


task_cancellation=TaskCancellation()
cancellable_task=task_cancellation.task
