import json
import socket
import threading
import time


# ============================================================
# CONFIGURACOES DO MASTER V2
# ============================================================

TCP_HOST = "127.0.0.1"
TCP_PORT = 8000
TCP_ADVERTISED_HOST = TCP_HOST

# Broadcast em loopback para facilitar a simulacao local.
DISCOVERY_TARGET = "127.255.255.255"
DISCOVERY_BIND_HOST = ""
DISCOVERY_PORT = 50000

SERVER_UUID = "MASTER_1"

SOCKET_TIMEOUT = 5
SERVER_RUN_SECONDS = 180
MAX_CONNECTIONS = 20
BACKLOG = 10

TASK_DISCOVER = "DISCOVER_MASTER"
TASK_DISCOVERY_RESPONSE = "DISCOVERY_RESPONSE"
TASK_ELECTION_CONFIRM = "ELECTION_CONFIRM"
TASK_HEARTBEAT = "HEARTBEAT"
STATUS_ACK = "ACK"
RESPONSE_ALIVE = "ALIVE"
RESPONSE_INVALID = "INVALID_REQUEST"


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

def send_json_line(stream, payload):
    message = json.dumps(payload) + "\n"
    stream.write(message.encode("utf-8"))
    stream.flush()


def recv_json_line(stream):
    line = stream.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


def validar_confirmacao_eleicao(payload):
    if not isinstance(payload, dict):
        return False, "Payload nao e um objeto JSON."

    if payload.get("TASK") != TASK_ELECTION_CONFIRM:
        return False, "TASK invalida. Esperado: ELECTION_CONFIRM."

    if payload.get("SERVER_UUID") != SERVER_UUID:
        return False, "SERVER_UUID invalido para confirmacao de eleicao."

    worker_uuid = payload.get("WORKER_UUID")
    if not isinstance(worker_uuid, str) or not worker_uuid.strip():
        return False, "WORKER_UUID deve ser string nao vazia."

    return True, None


def validar_heartbeat(payload):
    if not isinstance(payload, dict):
        return False, "Payload nao e um objeto JSON."

    if payload.get("SERVER_UUID") != SERVER_UUID:
        return False, "SERVER_UUID invalido para heartbeat."

    if payload.get("TASK") != TASK_HEARTBEAT:
        return False, "TASK invalida. Esperado: HEARTBEAT."

    return True, None


# ============================================================
# DESCOBERTA UDP
# ============================================================

def responder_descoberta(stop_event):
    udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        udp_server.bind((DISCOVERY_BIND_HOST, DISCOVERY_PORT))
        udp_server.settimeout(1)

        print(
            f"[MASTER] Discovery UDP ativo em {DISCOVERY_BIND_HOST or '0.0.0.0'}:{DISCOVERY_PORT}"
        )

        while not stop_event.is_set():
            try:
                raw_data, addr = udp_server.recvfrom(4096)
            except socket.timeout:
                continue

            try:
                payload = json.loads(raw_data.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[MASTER] Discovery UDP invalido recebido de {addr}.")
                continue

            if payload.get("TASK") != TASK_DISCOVER:
                print(f"[MASTER] Discovery UDP ignorado de {addr}: {payload}")
                continue

            response = {
                "TASK": TASK_DISCOVERY_RESPONSE,
                "SERVER_UUID": SERVER_UUID,
                "TCP_HOST": TCP_ADVERTISED_HOST,
                "TCP_PORT": TCP_PORT,
            }

            udp_server.sendto(json.dumps(response).encode("utf-8"), addr)
            print(f"[MASTER] Resposta UDP enviada para {addr}: {response}")

    except Exception as error:
        if not stop_event.is_set():
            print(f"[MASTER] Erro no discovery UDP: {error}")
    finally:
        udp_server.close()


# ============================================================
# ATENDIMENTO TCP
# ============================================================

def atender_conexao_tcp(conn, addr):
    print(f"\n[MASTER] Conexao TCP aceita de {addr}")

    with conn:
        conn.settimeout(SOCKET_TIMEOUT)

        try:
            with conn.makefile("rwb") as stream:
                first_payload = recv_json_line(stream)

                if first_payload is None:
                    print(f"[MASTER] Conexao TCP encerrada sem payload inicial de {addr}.")
                    return

                task = first_payload.get("TASK")

                if task == TASK_ELECTION_CONFIRM:
                    ok, error = validar_confirmacao_eleicao(first_payload)
                    if not ok:
                        print(f"[MASTER] Confirmacao de eleicao invalida: {error}")
                        return

                    ack_payload = {
                        "STATUS": STATUS_ACK,
                        "SERVER_UUID": SERVER_UUID,
                    }
                    send_json_line(stream, ack_payload)
                    print(f"[MASTER] ACK de eleicao enviado para {addr}: {ack_payload}")
                    return

                if task == TASK_HEARTBEAT:
                    ok, error = validar_heartbeat(first_payload)
                    if not ok:
                        print(f"[MASTER] Heartbeat invalido: {error}")
                        response = {
                            "SERVER_UUID": SERVER_UUID,
                            "TASK": task if task is not None else "UNKNOWN",
                            "RESPONSE": RESPONSE_INVALID,
                        }
                        send_json_line(stream, response)
                        return

                    response = {
                        "SERVER_UUID": SERVER_UUID,
                        "TASK": TASK_HEARTBEAT,
                        "RESPONSE": RESPONSE_ALIVE,
                    }
                    send_json_line(stream, response)
                    print(f"[MASTER] Heartbeat respondido para {addr}: {response}")
                    return

                response = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK": task if task is not None else "UNKNOWN",
                    "RESPONSE": RESPONSE_INVALID,
                }
                send_json_line(stream, response)
                print(f"[MASTER] Payload TCP invalido de {addr}: {first_payload}")

        except socket.timeout:
            print(f"[MASTER] Timeout atendendo conexao TCP de {addr}.")
        except json.JSONDecodeError:
            print(f"[MASTER] JSON invalido recebido de {addr}.")
        except Exception as error:
            print(f"[MASTER] Erro inesperado ao atender {addr}: {error}")


# ============================================================
# FUNCAO PRINCIPAL
# ============================================================

def main():
    threads = []
    stop_event = threading.Event()

    discovery_thread = threading.Thread(
        target=responder_descoberta,
        args=(stop_event,),
        daemon=True,
    )
    discovery_thread.start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((TCP_HOST, TCP_PORT))
        server.listen(BACKLOG)
        server.settimeout(1)

        print(f"[MASTER] Escutando TCP em {TCP_HOST}:{TCP_PORT}")
        print(f"[MASTER] SERVER_UUID={SERVER_UUID}")
        print(f"[MASTER] DISCOVERY_TARGET={DISCOVERY_TARGET}:{DISCOVERY_PORT}")
        print(f"[MASTER] SOCKET_TIMEOUT={SOCKET_TIMEOUT}s")
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
                thread = threading.Thread(target=atender_conexao_tcp, args=(conn, addr))
                thread.start()
                threads.append(thread)

                accepted_connections += 1
                print(f"[MASTER] Conexoes TCP aceitas: {accepted_connections}/{MAX_CONNECTIONS}")
            except socket.timeout:
                continue

    except KeyboardInterrupt:
        print("\n[MASTER] Encerramento solicitado pelo terminal.")
    except Exception as error:
        print(f"[MASTER] Erro no servidor TCP: {error}")
    finally:
        stop_event.set()
        server.close()

        for thread in threads:
            thread.join()

        discovery_thread.join(timeout=2)
        print("[MASTER] Servidor encerrado com sucesso.")


if __name__ == "__main__":
    main()