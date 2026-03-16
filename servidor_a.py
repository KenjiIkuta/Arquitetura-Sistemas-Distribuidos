import socket
import json

# Endereço e porta onde o Servidor A vai ficar escutando
HOST = "127.0.0.1"
PORT = 8000

# UUID fixo do servidor, como pedido no payload
SERVER_UUID = "123e4567-e89b-12d3-a456-426614174000"

# Cria o socket TCP/IP
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Permite reutilizar a porta sem precisar esperar tanto tempo
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    # Associa o socket ao IP e porta
    servidor.bind((HOST, PORT))

    # Coloca o servidor em modo de escuta
    servidor.listen(1)
    print(f"Servidor A escutando em {HOST}:{PORT}")

    # Aceita uma conexão de um cliente (Worker A1)
    conexao, endereco = servidor.accept()
    print(f"Conexão aceita de {endereco}")

    # Usa o socket retornado pela conexão aceita
    with conexao:
        # Recebe até 1024 bytes
        dados = conexao.recv(1024)

        # Verifica se realmente chegou algo
        if dados:
            # Converte os bytes recebidos para string e depois para dicionário Python
            payload_recebido = json.loads(dados.decode("utf-8"))
            print(f"Payload recebido do Worker A1: {payload_recebido}")

            # Verifica se o payload está no formato esperado
            if (
                payload_recebido.get("SERVER_UUID") == SERVER_UUID
                and payload_recebido.get("TASK") == "HEARTBEAT"
            ):
                # Se o heartbeat estiver correto, responde ALIVE
                resposta = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK": "HEARTBEAT",
                    "RESPONSE": "ALIVE"
                }
            else:
                # Caso venha algo diferente do esperado
                resposta = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK": payload_recebido.get("TASK", "UNKNOWN"),
                    "RESPONSE": "INVALID_REQUEST"
                }

            # Serializa o dicionário para JSON e envia ao Worker A1
            conexao.sendall(json.dumps(resposta).encode("utf-8"))
            print(f"Resposta enviada ao Worker A1: {resposta}")

finally:
    # Fecha o socket principal do servidor
    servidor.close()
    print("Servidor A encerrado.")