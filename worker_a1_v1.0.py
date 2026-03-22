import socket
import json
import time

# ============================================================
# CONFIGURAÇÕES DO WORKER
# ============================================================

# IP e porta do Master ao qual o Worker vai se conectar
HOST = "127.0.0.1"
PORT = 8000

# Identificador lógico do Master esperado no protocolo
SERVER_UUID = "Master_A"

# Tempo máximo de espera em operações de socket
SOCKET_TIMEOUT = 10

# Quantas verificações de heartbeat o Worker fará
# Isso substitui o loop infinito por um número finito de tentativas.
MAX_HEARTBEATS = 10

# Intervalo entre uma tentativa e outra
HEARTBEAT_INTERVAL = 10


# ============================================================
# FUNÇÕES AUXILIARES DE MENSAGERIA
# ============================================================

def send_json_line(conn, payload):
    """
    Envia um dicionário Python como JSON com '\n' ao final.
    """
    mensagem = json.dumps(payload) + "\n"
    conn.sendall(mensagem.encode("utf-8"))


def recv_json_line(conn):
    """
    Lê bytes do socket até encontrar '\n' e converte em dict.

    Retorna:
        dict -> JSON lido com sucesso
        None -> conexão fechada sem mensagem válida
    """
    buffer = b""

    while True:
        # Lê um bloco de bytes do socket
        chunk = conn.recv(1024)

        # Se vier vazio, a conexão foi encerrada
        if not chunk:
            if not buffer:
                return None
            break

        # Acumula os dados no buffer
        buffer += chunk

        # Se encontrou '\n', a mensagem está completa
        if b"\n" in buffer:
            linha, _resto = buffer.split(b"\n", 1)
            return json.loads(linha.decode("utf-8"))


# ============================================================
# LÓGICA DO HEARTBEAT
# ============================================================

def enviar_heartbeat(numero_tentativa):
    """
    Abre conexão com o Master, envia um heartbeat e interpreta a resposta.

    Parâmetro:
        numero_tentativa -> apenas para melhorar os logs

    Retorna:
        True  -> se recebeu ALIVE corretamente
        False -> em caso de falha de rede, timeout ou resposta inesperada
    """
    # Monta o payload exatamente no formato pedido pela sprint
    payload = {
        "SERVER_UUID": SERVER_UUID,
        "TASK": "HEARTBEAT"
    }

    try:
        # Cria a conexão TCP com timeout
        with socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT) as client:
            # Também define timeout para recv()
            client.settimeout(SOCKET_TIMEOUT)

            print(f"[WORKER] Tentativa {numero_tentativa}: conectado ao Master.")

            # Envia o heartbeat
            send_json_line(client, payload)
            print(f"[WORKER] Payload enviado: {payload}")

            # Aguarda a resposta do Master
            resposta = recv_json_line(client)

            # Se não veio nada, considera falha
            if resposta is None:
                print("[WORKER] Nenhuma resposta recebida do Master.")
                return False

            print(f"[WORKER] Resposta recebida: {resposta}")

            # Valida se a resposta segue o protocolo esperado
            if (
                resposta.get("SERVER_UUID") == SERVER_UUID
                and resposta.get("TASK") == "HEARTBEAT"
                and resposta.get("RESPONSE") == "ALIVE"
            ):
                print('[WORKER] Log: Status ALIVE\n')
                return True

            # Se respondeu algo diferente do esperado
            print('[WORKER] Log: resposta inválida recebida do Master\n')
            return False

    except ConnectionRefusedError:
        print('[WORKER] Log: Status OFFLINE - conexão recusada\n')
        return False
    except socket.timeout:
        print('[WORKER] Log: Status OFFLINE - timeout\n')
        return False
    except json.JSONDecodeError:
        print('[WORKER] Log: Status OFFLINE - JSON inválido na resposta\n')
        return False
    except Exception as e:
        print(f'[WORKER] Log: Status OFFLINE - erro inesperado: {e}\n')
        return False


# ============================================================
# FUNÇÃO PRINCIPAL DO WORKER
# ============================================================

def main():
    """
    Executa um número finito de heartbeats.

    O Worker encerra quando:
    1) completa MAX_HEARTBEATS tentativas, ou
    2) o usuário aperta Ctrl+C no terminal.
    """
    print("[WORKER] Iniciando verificação de heartbeat.")
    print(f"[WORKER] Total de tentativas configuradas: {MAX_HEARTBEATS}")
    print(f"[WORKER] Intervalo entre tentativas: {HEARTBEAT_INTERVAL} segundos")
    print("[WORKER] Para encerrar manualmente, pressione Ctrl+C.\n")

    try:
        # Loop finito: faz apenas MAX_HEARTBEATS tentativas
        for tentativa in range(1, MAX_HEARTBEATS + 1):
            sucesso = enviar_heartbeat(tentativa)

            # Se ainda houver tentativas restantes, espera o próximo ciclo
            if tentativa < MAX_HEARTBEATS:
                if sucesso:
                    print(f"[WORKER] Aguardando {HEARTBEAT_INTERVAL}s para o próximo heartbeat...\n")
                else:
                    print(f"[WORKER] Aguardando {HEARTBEAT_INTERVAL}s para tentar novamente...\n")

                time.sleep(HEARTBEAT_INTERVAL)

    except KeyboardInterrupt:
        # Captura Ctrl+C de forma amigável
        print("\n[WORKER] Encerramento solicitado pelo terminal (Ctrl+C).")

    finally:
        print("[WORKER] Worker encerrado com sucesso.")


# Garante que main() só rode quando este arquivo for executado diretamente
if __name__ == "__main__":
    main()