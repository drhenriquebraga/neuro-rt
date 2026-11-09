"""Own one worker and all descendants before its scientific entrypoint starts."""
import os
import signal
import subprocess
import time
from pathlib import Path
from .execution_errors import ProcessTreeUnconfirmed


class ManagedProcess:
    def __init__(self, command, *, cwd, env, stdout):
        self._job = None
        self._closed = False
        self.process = None
        payload = list(command[1:])
        interpreter_flags = ['-B', '-u']
        # These fixed interpreter switches belong to the real interpreter,
        # before child_entry waits for ownership; they are not worker argv.
        while payload and payload[0] in ('-I', '-B', '-u'):
            flag = payload.pop(0)
            if flag not in interpreter_flags:
                interpreter_flags.append(flag)
        if os.name == 'nt': self._create_job()
        wrapped = [command[0], *interpreter_flags, str(Path(__file__).with_name('child_entry.py')),
                   '--', *payload]
        try:
            self.process = subprocess.Popen(wrapped, cwd=cwd, env=env, stdout=stdout,
                stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt')
            if self._job is not None:
                if not self._kernel.AssignProcessToJobObject(self._job, int(self.process._handle)):
                    raise OSError('Não foi possível vincular o motor à árvore privada.')
            # The worker cannot start any child before this acknowledgement.
            self.process.stdin.write(b'NEURO_RT_READY\n')
            self.process.stdin.flush(); self.process.stdin.close()
        except BaseException:
            try:
                if self.process is not None:
                    self.process.kill(); self.process.wait(timeout=10)
                self.close()
            except BaseException as error:
                # Preserve ownership even when construction/handshake failed.
                raise ProcessTreeUnconfirmed('Encerramento da árvore não confirmado.', process=self) from error
            raise

    def _create_job(self):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [('PerProcessUserTimeLimit', c.c_int64), ('PerJobUserTimeLimit', c.c_int64),
                ('LimitFlags', w.DWORD), ('MinimumWorkingSetSize', c.c_size_t),
                ('MaximumWorkingSetSize', c.c_size_t), ('ActiveProcessLimit', w.DWORD),
                ('Affinity', c.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]
        class IO(c.Structure):
            _fields_ = [(name, c.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
        class Extended(c.Structure):
            _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', IO),
                ('ProcessMemoryLimit', c.c_size_t), ('JobMemoryLimit', c.c_size_t),
                ('PeakProcessMemoryUsed', c.c_size_t), ('PeakJobMemoryUsed', c.c_size_t)]
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.AssignProcessToJobObject.restype = w.BOOL
        kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        kernel.TerminateJobObject.restype = w.BOOL
        kernel.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
        kernel.QueryInformationJobObject.restype = w.BOOL
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.CloseHandle.restype = w.BOOL
        self._kernel = kernel
        self._job = kernel.CreateJobObjectW(None, None)
        if not self._job: raise c.WinError(c.get_last_error())
        limits = Extended(); limits.BasicLimitInformation.LimitFlags = 0x2000
        if not kernel.SetInformationJobObject(self._job, 9, c.byref(limits), c.sizeof(limits)):
            kernel.CloseHandle(self._job); self._job = None
            raise c.WinError(c.get_last_error())

    @property
    def pid(self): return self.process.pid
    @property
    def returncode(self): return self.process.returncode
    def poll(self): return self.process.poll()
    def wait(self, timeout=None): return self.process.wait(timeout=timeout)

    def active_count(self):
        if self._job is None: return 0 if self._closed else int(self.poll() is None)
        import ctypes as c
        from ctypes import wintypes as w
        class Accounting(c.Structure):
            _fields_ = [(name, c.c_int64) for name in ('TotalUserTime', 'TotalKernelTime',
                'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [
                (name, w.DWORD) for name in ('TotalPageFaultCount', 'TotalProcesses',
                                           'ActiveProcesses', 'TotalTerminatedProcesses')]
        info = Accounting()
        if not self._kernel.QueryInformationJobObject(self._job, 1, c.byref(info), c.sizeof(info), None):
            raise c.WinError(c.get_last_error())
        return int(info.ActiveProcesses)

    def terminate_tree(self):
        if self._closed: return
        if self._job is not None:
            if not self._kernel.TerminateJobObject(self._job, 1):
                raise OSError('Não foi possível encerrar a árvore privada do motor.')
        elif self.process is not None:
            try: os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        if self.process is not None: self.process.wait(timeout=10)
        deadline = time.monotonic() + 10
        while self.active_count():
            if time.monotonic() >= deadline:
                raise RuntimeError('A árvore privada ainda possui processos ativos.')
            time.sleep(.02)

    def close(self):
        if self._closed: return
        if self.process is not None: self.terminate_tree()
        if self._job is not None:
            self._kernel.CloseHandle(self._job); self._job = None
        self._closed = True
