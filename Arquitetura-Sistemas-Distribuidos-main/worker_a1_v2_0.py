import json
import re
import socket
import time


# ============================================================
# CONFIGURACOES DO WORKER V2
# ============================================================

DISCOVERY_TARGET = "127.255.255.255"
DISCOVERY_PORT = 50000
DISCOVERY_TIMEOUT = 3

SOCKET_TIMEOUT = 5
MAX_HEARTBEATS = 10
HEARTBEAT_INTERVAL = 10

WORKER_UUID = "W-123"

TASK_DISCOVER = "DISCOVER_MASTER"
TASK_DISCOVERY_RESPONSE = "DISCOVERY_RESPONSE"
TASK_ELECTION_CONFIRM = "ELECTION_CONFIRM"
TASK_HEARTBEAT = "HEARTBEAT"
STATUS_ACK = "ACK"
RESPONSE_ALIVE = "ALIVE"


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


def natural_master_key(server_uuid):
    match = re.match(r"^(.*?)(\d+)$", server_uuid)
    if match:
        prefix, suffix = match.groups()
        return prefix, int(suffix)
    return server_uuid, -1


def validar_resposta_descoberta(payload):
    if not isinstance(payload, dict):
        return False, "Payload nao e um objeto JSON."

    if payload.get("TASK") != TASK_DISCOVERY_RESPONSE:
        return False, "TASK invalida na descoberta."

    server_uuid = payload.get("SERVER_UUID")
    tcp_host = payload.get("TCP_HOST")
    tcp_port = payload.get("TCP_PORT")

    if not isinstance(server_uuid, str) or not server_uuid.strip():
        return False, "SERVER_UUID invalido na descoberta."

    if not isinstance(tcp_host, str) or not tcp_host.strip():
        return False, "TCP_HOST invalido na descoberta."

    if not isinstance(tcp_port, int) or tcp_port <= 0:
        return False, "TCP_PORT invalido na descoberta."

    return True, None


def validar_ack_eleicao(payload, expected_server_uuid):
    if not isinstance(payload, dict):
        return False, "Payload nao e um objeto JSON."

    if payload.get("STATUS") != STATUS_ACK:
        return False, "STATUS invalido no ACK de eleicao."

    if payload.get("SERVER_UUID") != expected_server_uuid:
        return False, "SERVER_UUID invalido no ACK de eleicao."

    return True, None


def validar_resposta_heartbeat(payload, expected_server_uuid):
    if not isinstance(payload, dict):
        return False, "Payload nao e um objeto JSON."

    if payload.get("SERVER_UUID") != expected_server_uuid:
        return False, "SERVER_UUID invalido na resposta de heartbeat."

    if payload.get("TASK") != TASK_HEARTBEAT:
        return False, "TASK invalida na resposta de heartbeat."

    if payload.get("RESPONSE") != RESPONSE_ALIVE:
        return False, "RESPONSE invalido na resposta de heartbeat."

    return True, None


# ============================================================
# DESCOBERTA E ELEICAO
# ============================================================

def descobrir_masters():
    payload = {
        "TASK": TASK_DISCOVER,
        "WORKER_UUID": WORKER_UUID,
    }

    discovered = {}

    udp_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        udp_client.bind(("", 0))
        udp_client.settimeout(DISCOVERY_TIMEOUT)

        udp_client.sendto(json.dumps(payload).encode("utf-8"), (DISCOVERY_TARGET, DISCOVERY_PORT))
        print(f"[WORKER] Pacote de descoberta UDP enviado: {payload}")

        deadline = time.time() + DISCOVERY_TIMEOUT
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            udp_client.settimeout(remaining)

            try:
                raw_data, addr = udp_client.recvfrom(4096)
            except socket.timeout:
                break

            try:
                response = json.loads(raw_data.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[WORKER] Resposta UDP invalida ignorada de {addr}.")
                continue

            ok, error = validar_resposta_descoberta(response)
            if not ok:
                print(f"[WORKER] Resposta de descoberta ignorada de {addr}: {error}")
                continue

            discovered[response["SERVER_UUID"]] = response
            print(f"[WORKER] Master descoberto via UDP: {response}")

    finally:
        udp_client.close()

    return list(discovered.values())


def eleger_master(discovered_masters):
    if not discovered_masters:
        return None

    elected = min(discovered_masters, key=lambda item: natural_master_key(item["SERVER_UUID"]))
    print(f"[WORKER] Master eleito: {elected}")
    return elected


# ============================================================
# HANDSHAKE TCP
# ============================================================

def confirmar_eleicao(master_info):
    payload = {
        "TASK": TASK_ELECTION_CONFIRM,
        "WORKER_UUID": WORKER_UUID,
        "SERVER_UUID": master_info["SERVER_UUID"],
    }

    try:
        with socket.create_connection(
            (master_info["TCP_HOST"], master_info["TCP_PORT"]),
            timeout=SOCKET_TIMEOUT,
        ) as client:
            client.settimeout(SOCKET_TIMEOUT)

            with client.makefile("rwb") as stream:
                send_json_line(stream, payload)
                print(f"[WORKER] Confirmacao de eleicao enviada: {payload}")

                ack_payload = recv_json_line(stream)
                if ack_payload is None:
                    print("[WORKER] O Master nao enviou ACK de eleicao.")
                    return False

                print(f"[WORKER] ACK de eleicao recebido: {ack_payload}")

                ok, error = validar_ack_eleicao(ack_payload, master_info["SERVER_UUID"])
                if not ok:
                    print(f"[WORKER] ACK de eleicao invalido: {error}")
                    return False

                return True

    except ConnectionRefusedError:
        print("[WORKER] Conexao TCP recusada na confirmacao de eleicao.")
        return False
    except socket.timeout:
        print("[WORKER] Timeout na confirmacao de eleicao.")
        return False
    except json.JSONDecodeError:
        print("[WORKER] JSON invalido recebido no ACK de eleicao.")
        return False
    except Exception as error:
        print(f"[WORKER] Erro inesperado na confirmacao de eleicao: {error}")
        return False


# ============================================================
# LOOP DE HEARTBEAT
# ============================================================

def enviar_heartbeat(master_info, numero_tentativa):
    payload = {
        "SERVER_UUID": master_info["SERVER_UUID"],
        "TASK": TASK_HEARTBEAT,
    }

    try:
        with socket.create_connection(
            (master_info["TCP_HOST"], master_info["TCP_PORT"]),
            timeout=SOCKET_TIMEOUT,
        ) as client:
            client.settimeout(SOCKET_TIMEOUT)

            with client.makefile("rwb") as stream:
                print(f"[WORKER] Tentativa {numero_tentativa}: conectado ao Master eleito.")
                send_json_line(stream, payload)
                print(f"[WORKER] Heartbeat enviado: {payload}")

                response = recv_json_line(stream)
                if response is None:
                    print("[WORKER] Nenhuma resposta recebida no heartbeat.")
                    return False

                print(f"[WORKER] Resposta de heartbeat recebida: {response}")

                ok, error = validar_resposta_heartbeat(response, master_info["SERVER_UUID"])
                if not ok:
                    print(f"[WORKER] Resposta de heartbeat invalida: {error}")
                    return False

                print("[WORKER] Log: Status ALIVE\n")
                return True

    except ConnectionRefusedError:
        print("[WORKER] Log: Status OFFLINE - conexao recusada\n")
        return False
    except socket.timeout:
        print("[WORKER] Log: Status OFFLINE - timeout\n")
        return False
    except json.JSONDecodeError:
        print("[WORKER] Log: Status OFFLINE - JSON invalido\n")
        return False
    except Exception as error:
        print(f"[WORKER] Log: Status OFFLINE - erro inesperado: {error}\n")
        return False


# ============================================================
# FUNCAO PRINCIPAL
# ============================================================

def main():
    print("[WORKER] Iniciando Worker v2")
    print(f"[WORKER] WORKER_UUID={WORKER_UUID}")
    print(f"[WORKER] DISCOVERY_TARGET={DISCOVERY_TARGET}:{DISCOVERY_PORT}")
    print(f"[WORKER] DISCOVERY_TIMEOUT={DISCOVERY_TIMEOUT}s")
    print(f"[WORKER] SOCKET_TIMEOUT={SOCKET_TIMEOUT}s")
    print(f"[WORKER] MAX_HEARTBEATS={MAX_HEARTBEATS}")
    print(f"[WORKER] HEARTBEAT_INTERVAL={HEARTBEAT_INTERVAL}s")
    print("[WORKER] Pressione Ctrl+C para encerrar.\n")

    try:
        discovered_masters = descobrir_masters()
        if not discovered_masters:
            print("[WORKER] Nenhum Master foi descoberto via UDP.")
            return

        elected_master = eleger_master(discovered_masters)
        if elected_master is None:
            print("[WORKER] Falha ao eleger um Master.")
            return

        if not confirmar_eleicao(elected_master):
            print("[WORKER] Falha no handshake TCP inicial com o Master eleito.")
            return

        print("[WORKER] Handshake inicial concluido com sucesso. Iniciando loop de heartbeat.\n")

        for tentativa in range(1, MAX_HEARTBEATS + 1):
            sucesso = enviar_heartbeat(elected_master, tentativa)

            if tentativa < MAX_HEARTBEATS:
                if sucesso:
                    print(
                        f"[WORKER] Aguardando {HEARTBEAT_INTERVAL}s para o proximo heartbeat...\n"
                    )
                else:
                    print(
                        f"[WORKER] Aguardando {HEARTBEAT_INTERVAL}s para tentar novamente...\n"
                    )

                time.sleep(HEARTBEAT_INTERVAL)

    except KeyboardInterrupt:
        print("\n[WORKER] Encerramento solicitado pelo terminal.")
    finally:
        print("[WORKER] Worker encerrado com sucesso.")


if __name__ == "__main__":
    main()