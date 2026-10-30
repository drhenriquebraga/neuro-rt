"""Neuro coordinator client of the host's single station queue.

The host owns cards, persistence, ordering and the heavy-work lease. A caller
must stop and reap its own child processes before finishing an active ticket.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import threading


class QueueCancelled(RuntimeError):
    pass


class QueueFinished(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueTicket:
    id: str
    request_id: str
    study_id: str
    reference: str


class QueueLease:
    def __init__(self, bridge, ticket):
        self.bridge = bridge
        self.ticket = ticket
        self._finished = False

    def __enter__(self):
        return self

    def finish(self, outcome='completed'):
        if not self._finished:
            self.bridge.finish(self.ticket, outcome)
            self._finished = True

    def __exit__(self, exc_type, exc, traceback):
        if not self._finished:
            outcome = ('cancelled' if self.bridge.cancelled(self.ticket)
                       else 'failed' if exc_type else 'completed')
            self.finish(outcome)
        return False


class QueueBridge:
    def __init__(self, host_queue=None, *, cancel_callback=None, poll_interval=0.05):
        if host_queue is None:
            import radai_queue_state as host_queue
        self.host = host_queue
        self.cancel_callback = cancel_callback
        self.poll_interval = max(0.005, float(poll_interval))
        self._lock = threading.RLock()
        self._signals = {}
        self._tickets = {}
        self._closed = False

    def enqueue_study(self, request_id, study_item):
        item = study_item.to_dict() if hasattr(study_item, 'to_dict') else dict(study_item)
        study_id, reference = item.get('study_id'), item.get('reference')
        if not isinstance(request_id, str) or not request_id or not study_id or not reference:
            raise ValueError('request_id, study_id e reference são obrigatórios')
        # Only digests cross into the shared queue; paths/bindings stay in Service.
        key = hashlib.sha256((request_id + '\0' + str(study_id)).encode()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps(item, sort_keys=True,
                                                allow_nan=False).encode()).hexdigest()
        with self._lock:
            if self._closed:
                raise RuntimeError('conexão com a fila encerrada')
            card = self.host.enqueue_neuro(key, fingerprint)
            ticket = QueueTicket(card['id'], request_id, str(study_id), str(reference))
            self._tickets[ticket.id] = ticket
            self._signals.setdefault(ticket.id, threading.Event())
            self.host.bind_neuro_cancel(ticket.id, lambda: self._on_cancel(ticket))
            return ticket

    def _on_cancel(self, ticket):
        with self._lock:
            signal = self._signals.get(ticket.id)
            if signal is not None:
                signal.set()
            external = getattr(signal, '_neuro_external', None)
        if hasattr(external, 'set'):
            external.set()
        if self.cancel_callback:
            self.cancel_callback(ticket)

    @staticmethod
    def _is_set(signal):
        return bool(signal.is_set() if hasattr(signal, 'is_set')
                    else signal() if callable(signal) else signal)

    def cancelled(self, ticket):
        card = self.host.cartao(ticket.id)
        return bool(not card or card.get('neuro_cancel')
                    or card.get('estado') == 'cancelado')

    def await_turn(self, ticket, cancel_signal=None):
        with self._lock:
            signal = self._signals.setdefault(ticket.id, threading.Event())
            signal._neuro_external = cancel_signal
        while True:
            if self._closed or signal.is_set() or self._is_set(cancel_signal):
                self.cancel(ticket)
                raise QueueCancelled('item Neuro cancelado')
            card = self.host.cartao(ticket.id)
            if not card or card.get('estado') == 'cancelado' or card.get('neuro_cancel'):
                raise QueueCancelled('item Neuro cancelado')
            if card.get('estado') in ('pronto', 'parcial', 'falhou'):
                raise QueueFinished('item Neuro já finalizado')
            if self.host.try_neuro_turn(ticket.id):
                if signal.is_set() or self._is_set(cancel_signal) or self.cancelled(ticket):
                    self.cancel(ticket)
                    self.finish(ticket, 'cancelled')
                    raise QueueCancelled('item Neuro cancelado antes do início')
                return QueueLease(self, ticket)
            signal.wait(self.poll_interval)

    def report(self, ticket, progress):
        value = progress if isinstance(progress, dict) else {}
        stage = value.get('stage', value.get('status'))
        if stage in ('completed', 'empty', 'partial', 'failed', 'interrupted', 'cancelled'):
            stage = 'running'  # Only finish() releases the item and its lease.
        safe = {}
        if stage in ('queued', 'preparing', 'running', 'restoring', 'exporting', 'visualizing'):
            safe['stage'] = stage
        fraction = value.get('fraction')
        if type(fraction) in (int, float) and math.isfinite(fraction) and 0 <= fraction <= 1:
            safe['fraction'] = float(fraction)
        return self.host.report_neuro(ticket.id, safe)

    def finish(self, ticket, outcome):
        result = self.host.finish_neuro(ticket.id, outcome)
        self.host.bind_neuro_cancel(ticket.id, None)
        return result

    def cancel(self, ticket):
        return self.host.cancel_neuro(ticket.id)

    def close(self):
        with self._lock:
            self._closed = True
            tickets = list(self._tickets.values())
        for ticket in tickets:
            self.cancel(ticket)

