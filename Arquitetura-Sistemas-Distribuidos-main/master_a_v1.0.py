import socket
import json
import threading
import time

# ============================================================
# CONFIGURAÇÕES DO MASTER
# ============================================================

# IP e porta onde o Master ficará escutando
HOST = "127.0.0.1"
PORT = 8000

# Identificador lógico do Master no protocolo
SERVER_UUID = "Master_A"

# Tempo máximo de espera em operações de socket
SOCKET_TIMEOUT = 10

# Quantas conexões o Master aceitará antes de encerrar sozinho
# Isso evita loop infinito.
MAX_CONNECTIONS = 10

# Tempo máximo de vida do servidor em segundos.
# Mesmo que ninguém conecte, ele encerra sozinho ao final desse tempo.
SERVER_RUN_SECONDS = 100

# Quantidade de conexões pendentes na fila do listen()
BACKLOG = 10


# ============================================================
# FUNÇÕES AUXILIARES DE MENSAGERIA
# ============================================================

def send_json_line(conn, payload):
    """
    Envia um dicionário Python como JSON, acrescentando '\n' no final.

    Por que isso é importante?
    Porque TCP é um stream de bytes. Sem um delimitador, o receptor
    não sabe exatamente onde uma mensagem termina e a próxima começa.
    """
    mensagem = json.dumps(payload) + "\n"
    conn.sendall(mensagem.encode("utf-8"))


def recv_json_line(conn):
    """
    Lê dados do socket até encontrar o delimitador '\n'.

    Retorna:
        dict -> quando consegue ler e converter o JSON corretamente
        None -> quando a conexão é fechada sem enviar nada
    """
    buffer = b""

    while True:
        # Lê um pedaço de bytes do socket
        chunk = conn.recv(1024)

        # Se chunk vier vazio, significa que a conexão foi encerrada
        if not chunk:
            if not buffer:
                return None
            break

        # Acumula os bytes recebidos
        buffer += chunk

        # Quando encontrar '\n', temos uma mensagem completa
        if b"\n" in buffer:
            linha, _resto = buffer.split(b"\n", 1)
            return json.loads(linha.decode("utf-8"))


# ============================================================
# LÓGICA DE ATENDIMENTO DO MASTER
# ============================================================

def atender_worker(conn, addr):
    """
    Trata uma única conexão recebida do Worker.

    Esta função roda em uma thread separada.
    Assim, o Master consegue atender uma conexão sem bloquear
    o fluxo principal de aceitação de novas conexões.
    """
    print(f"[MASTER] Conexão aceita de {addr}")

    # O bloco with fecha a conexão automaticamente ao final
    with conn:
        # Define timeout para não ficar esperando eternamente por dados
        conn.settimeout(SOCKET_TIMEOUT)

        try:
            # Recebe a mensagem JSON completa
            payload_recebido = recv_json_line(conn)

            # Se nada foi recebido, apenas encerra esse atendimento
            if payload_recebido is None:
                print(f"[MASTER] Nenhum dado recebido de {addr}.")
                return

            print(f"[MASTER] Payload recebido: {payload_recebido}")

            # Extrai os campos importantes do JSON
            server_uuid = payload_recebido.get("SERVER_UUID")
            task = payload_recebido.get("TASK")

            # Valida se a mensagem segue o protocolo esperado
            if server_uuid == SERVER_UUID and task == "HEARTBEAT":
                resposta = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK": "HEARTBEAT",
                    "RESPONSE": "ALIVE"
                }
            else:
                # Resposta defensiva para payload inválido
                resposta = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK": task if task is not None else "UNKNOWN",
                    "RESPONSE": "INVALID_REQUEST"
                }

            # Envia a resposta ao Worker
            send_json_line(conn, resposta)
            print(f"[MASTER] Resposta enviada: {resposta}")

        except socket.timeout:
            print(f"[MASTER] Timeout aguardando dados de {addr}.")
        except json.JSONDecodeError:
            print(f"[MASTER] JSON inválido recebido de {addr}.")
        except Exception as e:
            print(f"[MASTER] Erro inesperado ao atender {addr}: {e}")


# ============================================================
# FUNÇÃO PRINCIPAL DO MASTER
# ============================================================

def main():
    """
    Inicializa o servidor TCP do Master.

    Esta versão NÃO usa loop infinito.
    O servidor encerra quando:
    1) atinge MAX_CONNECTIONS, ou
    2) passa de SERVER_RUN_SECONDS, ou
    3) o usuário aperta Ctrl+C no terminal.
    """
    # Lista para guardar as threads criadas, permitindo join() no final
    threads = []

    # Cria o socket TCP/IP
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Permite reutilizar a porta rapidamente após encerrar o programa
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Associa o socket ao IP e porta configurados
        server.bind((HOST, PORT))

        # Coloca o socket em modo de escuta
        server.listen(BACKLOG)

        # Define timeout no accept() para que o servidor possa:
        # - verificar tempo de execução
        # - responder a Ctrl+C com mais suavidade
        server.settimeout(1)

        print(f"[MASTER] Escutando em {HOST}:{PORT}")
        print(f"[MASTER] Vai aceitar até {MAX_CONNECTIONS} conexões.")
        print(f"[MASTER] Tempo máximo de execução: {SERVER_RUN_SECONDS} segundos.")
        print("[MASTER] Para encerrar manualmente, pressione Ctrl+C.\n")

        # Conta quantas conexões já foram tratadas
        conexoes_aceitas = 0

        # Marca quando o servidor começou
        inicio = time.time()

        # Loop finito: termina por limite de conexões ou tempo
        while conexoes_aceitas < MAX_CONNECTIONS and (time.time() - inicio) < SERVER_RUN_SECONDS:
            try:
                # Aguarda uma nova conexão
                conn, addr = server.accept()

                # Cria uma thread para atender esse Worker sem bloquear o main
                thread = threading.Thread(
                    target=atender_worker,
                    args=(conn, addr)
                )
                thread.start()

                # Guarda a thread para esperar seu término no encerramento
                threads.append(thread)

                # Atualiza o contador de conexões aceitas
                conexoes_aceitas += 1
                print(f"[MASTER] Conexões tratadas: {conexoes_aceitas}/{MAX_CONNECTIONS}\n")

            except socket.timeout:
                # Timeout curto só para o loop voltar e checar tempo limite
                continue

    except KeyboardInterrupt:
        # Captura Ctrl+C e encerra o servidor de forma amigável
        print("\n[MASTER] Encerramento solicitado pelo terminal (Ctrl+C).")

    except Exception as e:
        print(f"[MASTER] Erro no servidor: {e}")

    finally:
        # Fecha o socket principal do servidor
        server.close()

        # Espera as threads terminarem
        for thread in threads:
            thread.join()

        print("[MASTER] Servidor encerrado com sucesso.")


# Garante que main() só rode quando este arquivo for executado diretamente
if __name__ == "__main__":
    main()