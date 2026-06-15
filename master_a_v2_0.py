import socket
import json
import threading
import time
from collections import deque

# ============================================================
# CONFIGURAÇÕES DO MASTER
# ============================================================

HOST = "127.0.0.1"
PORT = 8000
SERVER_UUID = "Master_A"

# Timeout máximo sugerido no enunciado da Sprint 2
SOCKET_TIMEOUT = 5

# Controles de execução do servidor
MAX_CONNECTIONS = 20
SERVER_RUN_SECONDS = 180
BACKLOG = 10

# ============================================================
# FILA DE TAREFAS
# ============================================================
# Simulação simples de uma fila de tarefas pendentes.
# Cada tarefa segue o formato definido no PDF:
# {"TASK": "QUERY", "USER": "string"}

TASK_QUEUE = deque([
    {"TASK": "QUERY", "USER": "Michel"},
    {"TASK": "QUERY", "USER": "Julia"},
    {"TASK": "QUERY", "USER": "Ana"},
    {"TASK": "QUERY", "USER": "Carlos"},
])

# Como o Master atende vários Workers em paralelo,
# a fila precisa de proteção contra acesso concorrente.
QUEUE_LOCK = threading.Lock()

# ============================================================
# FUNÇÕES AUXILIARES DE MENSAGERIA
# ============================================================

def send_json_line(stream, payload):
    """
    Envia um dicionário Python como JSON terminado com '\n'.

    Usamos stream (arquivo do socket) porque a leitura por linha
    funciona muito bem com o protocolo delimitado por newline.
    """
    message = json.dumps(payload) + "\n"
    stream.write(message.encode("utf-8"))
    stream.flush()


def recv_json_line(stream):
    """
    Lê uma linha do stream e converte em dicionário Python.

    Retorna:
        dict -> JSON válido
        None -> conexão fechada
    """
    line = stream.readline()

    if not line:
        return None

    return json.loads(line.decode("utf-8"))


# ============================================================
# VALIDAÇÕES DE PROTOCOLO
# ============================================================

def validar_apresentacao_worker(payload):
    """
    Valida o payload inicial de apresentação do Worker.

    Formato esperado:
    {
        "WORKER": "ALIVE",
        "WORKER_UUID": "..."
    }

    Campo opcional:
        "SERVER_UUID": "..."
    """
    if not isinstance(payload, dict):
        return False, "Payload não é um objeto JSON."

    if "WORKER" not in payload:
        return False, "Campo obrigatório ausente: WORKER."

    if "WORKER_UUID" not in payload:
        return False, "Campo obrigatório ausente: WORKER_UUID."

    if payload["WORKER"] != "ALIVE":
        return False, "Valor inválido para WORKER. Esperado: ALIVE."

    if not isinstance(payload["WORKER_UUID"], str) or not payload["WORKER_UUID"].strip():
        return False, "WORKER_UUID deve ser string não vazia."

    # Campos extras são ignorados.
    return True, None


def validar_status_report(payload):
    """
    Valida o payload final enviado pelo Worker após o processamento.

    Formato esperado:
    {
        "STATUS": "OK" ou "NOK",
        "TASK": "QUERY",
        "WORKER_UUID": "..."
    }
    """
    if not isinstance(payload, dict):
        return False, "Payload não é um objeto JSON."

    required_fields = ["STATUS", "TASK", "WORKER_UUID"]
    for field in required_fields:
        if field not in payload:
            return False, f"Campo obrigatório ausente: {field}."

    if payload["STATUS"] not in {"OK", "NOK"}:
        return False, "STATUS inválido. Esperado: OK ou NOK."

    if payload["TASK"] != "QUERY":
        return False, "TASK inválida no status. Esperado: QUERY."

    if not isinstance(payload["WORKER_UUID"], str) or not payload["WORKER_UUID"].strip():
        return False, "WORKER_UUID deve ser string não vazia."

    return True, None


# ============================================================
# REGRAS DE NEGÓCIO
# ============================================================

def obter_proxima_tarefa():
    """
    Retira a próxima tarefa da fila, se houver.
    """
    with QUEUE_LOCK:
        if TASK_QUEUE:
            return TASK_QUEUE.popleft()
        return None


def registrar_resultado(worker_uuid, worker_tipo, origem, task, user, status):
    """
    Gera o log final do processamento.
    """
    if worker_tipo == "emprestado":
        print(
            f"[MASTER] Worker EMPRESTADO {worker_uuid} "
            f"(origem={origem}) concluiu TASK={task} USER={user} STATUS={status}"
        )
    else:
        print(
            f"[MASTER] Worker LOCAL {worker_uuid} "
            f"concluiu TASK={task} USER={user} STATUS={status}"
        )


# ============================================================
# ATENDIMENTO DE UMA CONEXÃO
# ============================================================

def atender_worker(conn, addr):
    """
    Trata um ciclo completo de comunicação da Sprint 2.

    Fluxo:
    1. Worker se apresenta
    2. Master envia QUERY ou NO_TASK
    3. Se houve QUERY, Worker processa e devolve status
    4. Master envia ACK
    """
    print(f"\n[MASTER] Conexão aceita de {addr}")

    with conn:
        conn.settimeout(SOCKET_TIMEOUT)

        try:
            with conn.makefile("rwb") as stream:
                # ------------------------------------------------
                # 1) RECEBER APRESENTAÇÃO
                # ------------------------------------------------
                first_payload = recv_json_line(stream)

                if first_payload is None:
                    print("[MASTER] Conexão encerrada antes da apresentação do Worker.")
                    return

                print(f"[MASTER] Payload de apresentação recebido: {first_payload}")

                ok, error = validar_apresentacao_worker(first_payload)
                if not ok:
                    print(f"[MASTER] Apresentação inválida: {error}")
                    return

                worker_uuid = first_payload["WORKER_UUID"]
                origem = first_payload.get("SERVER_UUID")

                # Se veio SERVER_UUID e ele for diferente deste Master,
                # então o Worker é considerado emprestado.
                if origem and origem != SERVER_UUID:
                    worker_tipo = "emprestado"
                else:
                    worker_tipo = "local"

                print(
                    f"[MASTER] Worker identificado: "
                    f"uuid={worker_uuid}, tipo={worker_tipo}, origem={origem}"
                )

                # ------------------------------------------------
                # 2) ENTREGAR TAREFA OU INFORMAR FILA VAZIA
                # ------------------------------------------------
                task_payload = obter_proxima_tarefa()

                if task_payload is None:
                    resposta = {"TASK": "NO_TASK"}
                    send_json_line(stream, resposta)
                    print(f"[MASTER] Fila vazia. Enviado para {worker_uuid}: {resposta}")
                    return

                send_json_line(stream, task_payload)
                print(f"[MASTER] Tarefa enviada para {worker_uuid}: {task_payload}")

                # ------------------------------------------------
                # 3) RECEBER STATUS FINAL DO WORKER
                # ------------------------------------------------
                report_payload = recv_json_line(stream)

                if report_payload is None:
                    print(f"[MASTER] Worker {worker_uuid} desconectou antes de enviar status.")
                    return

                print(f"[MASTER] Status recebido de {worker_uuid}: {report_payload}")

                ok, error = validar_status_report(report_payload)
                if not ok:
                    print(f"[MASTER] Status inválido de {worker_uuid}: {error}")
                    return

                # Confere se o status veio do mesmo Worker que se apresentou
                if report_payload["WORKER_UUID"] != worker_uuid:
                    print(
                        f"[MASTER] Inconsistência de WORKER_UUID: "
                        f"apresentação={worker_uuid}, status={report_payload['WORKER_UUID']}"
                    )
                    return

                # Confere se a tarefa reportada bate com a entregue
                if report_payload["TASK"] != task_payload["TASK"]:
                    print(
                        f"[MASTER] Inconsistência de TASK: "
                        f"esperado={task_payload['TASK']}, recebido={report_payload['TASK']}"
                    )
                    return

                status_final = report_payload["STATUS"]

                registrar_resultado(
                    worker_uuid=worker_uuid,
                    worker_tipo=worker_tipo,
                    origem=origem,
                    task=task_payload["TASK"],
                    user=task_payload.get("USER"),
                    status=status_final
                )

                # ------------------------------------------------
                # 4) ENVIAR ACK FINAL
                # ------------------------------------------------
                ack_payload = {
                    "STATUS": "ACK",
                    "WORKER_UUID": worker_uuid
                }

                send_json_line(stream, ack_payload)
                print(f"[MASTER] ACK enviado para {worker_uuid}: {ack_payload}")

        except socket.timeout:
            print(f"[MASTER] Timeout atendendo conexão de {addr}.")
        except json.JSONDecodeError:
            print(f"[MASTER] JSON inválido recebido de {addr}.")
        except Exception as e:
            print(f"[MASTER] Erro inesperado ao atender {addr}: {e}")


# ============================================================
# FUNÇÃO PRINCIPAL DO MASTER
# ============================================================

def main():
    threads = []

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((HOST, PORT))
        server.listen(BACKLOG)
        server.settimeout(1)

        print(f"[MASTER] Escutando em {HOST}:{PORT}")
        print(f"[MASTER] SERVER_UUID={SERVER_UUID}")
        print(f"[MASTER] SOCKET_TIMEOUT={SOCKET_TIMEOUT}s")
        print(f"[MASTER] Tarefas iniciais na fila={len(TASK_QUEUE)}")
        print(f"[MASTER] MAX_CONNECTIONS={MAX_CONNECTIONS}")
        print(f"[MASTER] SERVER_RUN_SECONDS={SERVER_RUN_SECONDS}")
        print("[MASTER] Pressione Ctrl+C para encerrar.\n")

        accepted_connections = 0
        start_time = time.time()

        while (
            accepted_connections < MAX_CONNECTIONS
            and (time.time() - start_time) < SERVER_RUN_SECONDS
        ):
            try:
                conn, addr = server.accept()

                thread = threading.Thread(target=atender_worker, args=(conn, addr))
                thread.start()
                threads.append(thread)

                accepted_connections += 1
                print(f"[MASTER] Conexões aceitas: {accepted_connections}/{MAX_CONNECTIONS}")

            except socket.timeout:
                continue

    except KeyboardInterrupt:
        print("\n[MASTER] Encerramento solicitado pelo terminal.")
    except Exception as e:
        print(f"[MASTER] Erro no servidor: {e}")
    finally:
        server.close()

        for thread in threads:
            thread.join()

        print("[MASTER] Servidor encerrado com sucesso.")


if __name__ == "__main__":
    main()