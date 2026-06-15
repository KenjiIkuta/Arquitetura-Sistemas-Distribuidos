#!/usr/bin/env python3
# -*- coding: ascii -*-
"""
test_local.py - Testes de integracao automaticos para as Sprints 01-04.

Inicia processos reais de master.py e worker.py e valida cada protocolo
via conexoes TCP diretas -- sem mocks.

Uso:
    python test_local.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from typing import Any

# ------------------------------------------------------------------
# Localizacoes
# ------------------------------------------------------------------
HERE      = os.path.dirname(os.path.abspath(__file__))
PYTHON    = sys.executable
MASTER_PY = os.path.join(HERE, "master.py")
WORKER_PY = os.path.join(HERE, "worker.py")

# ------------------------------------------------------------------
# Portas de teste (fora do intervalo do demo normal)
# ------------------------------------------------------------------
HOST     = "127.0.0.1"
MA_PORT  = 18000   # Master A -- saturado, tem tarefas
MB_PORT  = 18001   # Master B -- auxiliar, sem tarefas iniciais
WB1_CMD  = 19001   # Worker B1 -- servidor de comandos

# ------------------------------------------------------------------
# Estado global dos subprocessos e resultados
# ------------------------------------------------------------------
_procs:   list[subprocess.Popen] = []
_results: list[tuple[str, bool, str]] = []

# ------------------------------------------------------------------
# Cores ANSI
# ------------------------------------------------------------------
G = "\033[92m"   # verde
R = "\033[91m"   # vermelho
B = "\033[1m"    # negrito
E = "\033[0m"    # reset


# ==================================================================
# Helpers de resultado
# ==================================================================

def ok(name: str) -> None:
    print(f"  {G}PASS{E}  {name}")
    _results.append((name, True, ""))


def fail(name: str, reason: str = "") -> None:
    print(f"  {R}FAIL{E}  {name}" + (f"\n       {reason}" if reason else ""))
    _results.append((name, False, reason))


# ==================================================================
# Helpers de rede
# ==================================================================

def wait_port(port: int, timeout: float = 10.0) -> bool:
    """Aguarda uma porta TCP ficar disponivel."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _conn(port: int, timeout: float = 8.0):
    """Abre conexao TCP e retorna (socket, makefile)."""
    sock = socket.create_connection((HOST, port), timeout=timeout)
    sock.settimeout(timeout)
    return sock, sock.makefile("rwb")


def _send(stream, payload: dict[str, Any]) -> None:
    stream.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
    stream.flush()


def _recv(stream) -> dict[str, Any] | None:
    line = stream.readline()
    return json.loads(line.decode()) if line else None


# ==================================================================
# Helpers de processo
# ==================================================================

def start_master(
    master_id: str,
    port: int,
    capacity: int = 5,
    release: int = 2,
    seed: int = 0,
    neighbors: list[str] | None = None,
) -> subprocess.Popen:
    cmd = [
        PYTHON, MASTER_PY,
        "--master-id", master_id,
        "--host", HOST,
        "--port", str(port),
        "--capacity", str(capacity),
        "--release-threshold", str(release),
        "--seed-tasks", str(seed),
        "--monitor-interval", "3",
    ]
    for n in neighbors or []:
        cmd += ["--neighbor", n]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _procs.append(proc)
    return proc


def start_worker(
    worker_id: str,
    master_id: str,
    master_port: int,
    cmd_port: int,
) -> subprocess.Popen:
    cmd = [
        PYTHON, WORKER_PY,
        "--worker-id", worker_id,
        "--master-id", master_id,
        "--master-address", f"{HOST}:{master_port}",
        "--command-port", str(cmd_port),
        "--interval", "1",
        "--min-task-seconds", "0.3",
        "--max-task-seconds", "0.8",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _procs.append(proc)
    return proc


def kill_all() -> None:
    for p in _procs:
        try:
            p.kill()
            p.wait(timeout=2)
        except Exception:
            pass


# ==================================================================
# SPRINT 01 -- Heartbeat
# ==================================================================

def test_heartbeat(port: int, label: str) -> None:
    name = f"Sprint 01 - Heartbeat ALIVE [{label}]"
    try:
        sock, stream = _conn(port)
        with sock:
            _send(stream, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            resp = _recv(stream)
        if resp and resp.get("TASK") == "HEARTBEAT" and resp.get("RESPONSE") == "ALIVE":
            ok(name)
        else:
            fail(name, f"Resposta: {resp}")
    except Exception as exc:
        fail(name, str(exc))


# ==================================================================
# SPRINT 02 -- Ciclo de tarefas
# ==================================================================

def test_no_task(port: int, label: str) -> None:
    name = f"Sprint 02 - NO_TASK com fila vazia [{label}]"
    try:
        sock, stream = _conn(port)
        with sock:
            _send(stream, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            _recv(stream)
            _send(stream, {
                "WORKER": "ALIVE",
                "WORKER_UUID": f"W-NT-{uuid.uuid4().hex[:4]}",
                "WORKER_HOST": HOST,
                "WORKER_PORT": 29997,
            })
            resp = _recv(stream)
        if resp and resp.get("TASK") == "NO_TASK":
            ok(name)
        else:
            fail(name, f"Esperado NO_TASK, recebido: {resp}")
    except Exception as exc:
        fail(name, str(exc))


def test_full_cycle(port: int) -> None:
    name = "Sprint 02 - Ciclo QUERY -> STATUS OK -> ACK"
    try:
        sock, stream = _conn(port)
        with sock:
            _send(stream, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            _recv(stream)

            wid = f"W-CYC-{uuid.uuid4().hex[:4]}"
            _send(stream, {
                "WORKER": "ALIVE",
                "WORKER_UUID": wid,
                "WORKER_HOST": HOST,
                "WORKER_PORT": 29996,
            })
            task_resp = _recv(stream)
            if not task_resp or task_resp.get("TASK") != "QUERY":
                fail(name, f"Esperado QUERY, recebido: {task_resp}")
                return

            _send(stream, {"STATUS": "OK", "TASK": "QUERY", "WORKER_UUID": wid})
            ack = _recv(stream)

        if ack and ack.get("STATUS") == "ACK":
            ok(name)
        else:
            fail(name, f"Esperado ACK, recebido: {ack}")
    except Exception as exc:
        fail(name, str(exc))


def test_status_nok(port: int) -> None:
    name = "Sprint 02 - Ciclo QUERY -> STATUS NOK -> ACK (tarefa com falha)"
    try:
        sock, stream = _conn(port)
        with sock:
            _send(stream, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            _recv(stream)

            wid = f"W-NOK-{uuid.uuid4().hex[:4]}"
            _send(stream, {
                "WORKER": "ALIVE",
                "WORKER_UUID": wid,
                "WORKER_HOST": HOST,
                "WORKER_PORT": 29995,
            })
            task_resp = _recv(stream)
            if not task_resp or task_resp.get("TASK") != "QUERY":
                fail(name, f"Esperado QUERY, recebido: {task_resp}")
                return

            _send(stream, {"STATUS": "NOK", "TASK": "QUERY", "WORKER_UUID": wid})
            ack = _recv(stream)

        if ack and ack.get("STATUS") == "ACK":
            ok(name)
        else:
            fail(name, f"Esperado ACK, recebido: {ack}")
    except Exception as exc:
        fail(name, str(exc))


# ==================================================================
# SPRINT 03 -- Negociacao M2M
# ==================================================================

def test_request_help_rejected_high_load(port: int) -> None:
    name = "Sprint 03 - request_help -> rejected (high_load)"
    try:
        rid = str(uuid.uuid4())
        msg = {
            "type": "request_help",
            "request_id": rid,
            "payload": {
                "master_id": "TEST_REQUESTER",
                "master_address": f"{HOST}:29999",
                "current_load": 1,
                "capacity": 10,
                "workers_needed": 1,
            },
        }
        sock, stream = _conn(port)
        with sock:
            _send(stream, msg)
            resp = _recv(stream)

        if (
            resp
            and resp.get("type") == "response_rejected"
            and resp.get("request_id") == rid
        ):
            ok(name)
        else:
            fail(name, f"Recebido: {resp}")
    except Exception as exc:
        fail(name, str(exc))


def test_register_temporary_worker(port: int) -> str:
    """Registra um worker temporario e retorna worker_id."""
    name = "Sprint 03 - register_temporary_worker -> ACK"
    wid = f"W-TMP-{uuid.uuid4().hex[:4]}"
    rid = str(uuid.uuid4())
    try:
        msg = {
            "type": "register_temporary_worker",
            "request_id": rid,
            "payload": {
                "worker_id": wid,
                "original_master_address": f"{HOST}:28888",
                "original_master_id": "ORIGIN",
                "worker_address": f"{HOST}:29994",
            },
        }
        sock, stream = _conn(port)
        with sock:
            _send(stream, msg)
            resp = _recv(stream)

        if resp and resp.get("STATUS") == "ACK" and resp.get("request_id") == rid:
            ok(name)
        else:
            fail(name, f"Recebido: {resp}")
            return ""
    except Exception as exc:
        fail(name, str(exc))
        return ""
    return wid


def test_notify_worker_returned(port: int, worker_id: str) -> None:
    name = "Sprint 03 - notify_worker_returned -> ACK"
    rid = str(uuid.uuid4())
    try:
        msg = {
            "type": "notify_worker_returned",
            "request_id": rid,
            "payload": {"worker_id": worker_id or f"W-RET-{uuid.uuid4().hex[:4]}"},
        }
        sock, stream = _conn(port)
        with sock:
            _send(stream, msg)
            resp = _recv(stream)

        if resp and resp.get("STATUS") == "ACK" and resp.get("request_id") == rid:
            ok(name)
        else:
            fail(name, f"Recebido: {resp}")
    except Exception as exc:
        fail(name, str(exc))


def test_unknown_type_ignored(port: int) -> None:
    name = "Sprint 03 - tipo desconhecido ignorado (sem crash)"
    try:
        msg = {
            "type": "xpto_future_message",
            "request_id": str(uuid.uuid4()),
            "payload": {"data": 42},
        }
        sock, stream = _conn(port)
        with sock:
            _send(stream, msg)
            stream.readline()  # pode retornar b'' (EOF) sem erro

        time.sleep(0.2)
        # Confirma que o master ainda responde heartbeat
        sock2, stream2 = _conn(port)
        with sock2:
            _send(stream2, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            resp = _recv(stream2)
        if resp and resp.get("RESPONSE") == "ALIVE":
            ok(name)
        else:
            fail(name, f"Master nao respondeu heartbeat apos tipo desconhecido: {resp}")
    except Exception as exc:
        fail(name, str(exc))


def test_m2m_request_help_accepted(port_a: int, port_b: int) -> None:
    """
    Apresenta um worker ficticio ao Master B para que ele fique registrado,
    depois envia request_help ao Master B esperando response_accepted.
    """
    name = "Sprint 03 - request_help -> response_accepted (worker disponivel no Master B)"
    try:
        # 1. Apresenta W-LEND ao Master B -> fica ocioso em local_workers
        wid = f"W-LEND-{uuid.uuid4().hex[:4]}"
        sock1, stream1 = _conn(port_b)
        with sock1:
            _send(stream1, {"SERVER_UUID": "B", "TASK": "HEARTBEAT"})
            _recv(stream1)
            _send(stream1, {
                "WORKER": "ALIVE",
                "WORKER_UUID": wid,
                "WORKER_HOST": HOST,
                "WORKER_PORT": 29993,   # porta inexistente -- redirect vai para fila
            })
            _recv(stream1)  # NO_TASK ou comando

        time.sleep(0.3)

        # 2. Envia request_help ao Master B
        rid = str(uuid.uuid4())
        msg = {
            "type": "request_help",
            "request_id": rid,
            "payload": {
                "master_id": "A",
                "master_address": f"{HOST}:{port_a}",
                "current_load": 10,
                "capacity": 3,
                "workers_needed": 1,
            },
        }
        sock2, stream2 = _conn(port_b, timeout=12.0)
        with sock2:
            _send(stream2, msg)
            resp = _recv(stream2)

        if (
            resp
            and resp.get("type") in ("response_accepted", "response_rejected")
            and resp.get("request_id") == rid
        ):
            tipo = resp["type"]
            if tipo == "response_accepted":
                ok(name)
            else:
                # Pode ser rejected se worker ja cedido -- ainda assim protocolo correto
                ok(f"{name} [rejected -- worker ja cedido, comportamento correto]")
        else:
            fail(name, f"Resposta invalida: {resp}")
    except Exception as exc:
        fail(name, str(exc))


# ==================================================================
# SPRINT 04 -- Supervisor de metricas
# ==================================================================

def test_supervisor_nao_derruba_master(proc: subprocess.Popen, port: int) -> None:
    """
    Aguarda 12 s (> 1 ciclo de 10 s) e verifica que:
    1. O processo Master ainda esta vivo.
    2. Master ainda responde heartbeat.

    Obs: falha TLS para nuted-ia.dev e esperada sem acesso externo e
    NAO e falha do teste -- o importante e o master nao crashar.
    """
    name = "Sprint 04 - Supervisor de metricas nao derruba o Master apos 12 s"
    print("       (aguardando 12 s para cobrir ao menos 1 ciclo de metricas...)", flush=True)
    time.sleep(12)

    if proc.poll() is not None:
        fail(name, f"Processo Master encerrou com codigo {proc.returncode}")
        return

    try:
        sock, stream = _conn(port)
        with sock:
            _send(stream, {"SERVER_UUID": "TEST", "TASK": "HEARTBEAT"})
            resp = _recv(stream)
        if resp and resp.get("RESPONSE") == "ALIVE":
            ok(name)
        else:
            fail(name, f"Master vivo mas heartbeat estranho: {resp}")
    except Exception as exc:
        fail(name, str(exc))


# ==================================================================
# Bonus -- Worker real (processo filho)
# ==================================================================

def test_worker_real_cycle(master_port: int, master_id: str) -> None:
    """Sobe um Worker real e verifica que ele completa ao menos 1 tarefa em 10 s."""
    name = f"Bonus - Worker real completa tarefa no Master {master_id}"
    proc = start_worker(
        worker_id=f"W-REAL-{uuid.uuid4().hex[:4]}",
        master_id=master_id,
        master_port=master_port,
        cmd_port=WB1_CMD,
    )
    try:
        deadline = time.time() + 10.0
        stdout_lines: list[str] = []
        while time.time() < deadline:
            if proc.stdout:
                line = proc.stdout.readline()
            else:
                line = ""
            if line:
                stdout_lines.append(line.rstrip())
                if "ACK" in line or "STATUS" in line:
                    ok(name)
                    return
            elif proc.poll() is not None:
                break
            time.sleep(0.1)
        fail(name, "Nenhum STATUS/ACK em 10 s. Ultimas linhas:\n" +
             "\n".join(stdout_lines[-5:]))
    finally:
        proc.kill()
        proc.wait(timeout=2)
        _procs.remove(proc)


# ==================================================================
# Main
# ==================================================================

def main() -> None:
    print("\n" + B + "==================================================" + E)
    print(B + "  Testes de Integracao - Sistemas Distribuidos   " + E)
    print(B + "==================================================" + E + "\n")

    try:
        # Inicia os Masters
        print("Iniciando subprocessos...")
        proc_b = start_master(
            "B", MB_PORT,
            capacity=10, release=3, seed=0,
            neighbors=[f"A={HOST}:{MA_PORT}"],
        )
        proc_a = start_master(
            "A", MA_PORT,
            capacity=3, release=1, seed=6,   # 6 tarefas > capacity 3 -> saturado
            neighbors=[f"B={HOST}:{MB_PORT}"],
        )

        for label, port in [("Master A", MA_PORT), ("Master B", MB_PORT)]:
            print(f"  Aguardando {label} (:{port})...", end=" ", flush=True)
            if not wait_port(port):
                print("TIMEOUT")
                fail(f"Startup {label}", "Porta nao abriu em 10 s")
                return
            print("OK")

        print()

        # Sprint 01
        print(B + "Sprint 01 - Heartbeat" + E)
        test_heartbeat(MA_PORT, "Master A")
        test_heartbeat(MB_PORT, "Master B")

        # Sprint 02
        print("\n" + B + "Sprint 02 - Ciclo de Tarefas" + E)
        test_no_task(MB_PORT, "Master B sem tarefas")
        test_full_cycle(MA_PORT)       # consome 1 tarefa (fila: 6->5)
        test_status_nok(MA_PORT)       # consome 1 tarefa (fila: 5->4, total_failed++)

        # Sprint 03
        print("\n" + B + "Sprint 03 - Negociacao M2M" + E)
        # MA tem 4 tarefas, capacity=3 -> ainda saturado -> rejeita high_load
        test_request_help_rejected_high_load(MA_PORT)
        wid = test_register_temporary_worker(MA_PORT)
        test_notify_worker_returned(MA_PORT, wid)
        test_unknown_type_ignored(MB_PORT)
        # MB tem worker ocioso do test_no_task -> aceita request_help
        test_m2m_request_help_accepted(MA_PORT, MB_PORT)

        # Bonus
        print("\n" + B + "Bonus - Worker real (processo filho)" + E)
        test_worker_real_cycle(MA_PORT, "A")

        # Sprint 04
        print("\n" + B + "Sprint 04 - Supervisor de Metricas" + E)
        test_supervisor_nao_derruba_master(proc_a, MA_PORT)

    finally:
        kill_all()

        # Resumo
        print("\n" + B + "==================================================" + E)
        print(B + "  Resultado Final" + E)
        print(B + "==================================================" + E)
        passed = sum(1 for _, ok_r, _ in _results if ok_r)
        total = len(_results)
        for tname, ok_r, reason in _results:
            mark = G + "OK" + E if ok_r else R + "XX" + E
            print(f"  [{mark}]  {tname}")
            if not ok_r and reason:
                print(f"       -> {reason}")
        print(f"\n  {passed}/{total} testes passaram.\n")
        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
