import socket
import json

# Endereço e porta do Servidor A
HOST = "127.0.0.1"
PORT = 8000

# UUID do servidor que o Worker A1 quer verificar
SERVER_UUID = "123e4567-e89b-12d3-a456-426614174000"

# Payload do heartbeat pedido no enunciado
payload_heartbeat = {
    "SERVER_UUID": SERVER_UUID,
    "TASK": "HEARTBEAT"
}

# Cria o socket TCP/IP do cliente
worker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    # Conecta ao Servidor A
    worker.connect((HOST, PORT))
    print("Worker A1 conectado ao Servidor A.")

    # Converte o dicionário para JSON e envia ao servidor
    worker.sendall(json.dumps(payload_heartbeat).encode("utf-8"))
    print(f"Heartbeat enviado ao Servidor A: {payload_heartbeat}")

    # Recebe a resposta do servidor
    resposta = worker.recv(1024)

    # Verifica se recebeu algo
    if resposta:
        # Converte os bytes recebidos para dicionário Python
        resposta_json = json.loads(resposta.decode("utf-8"))
        print(f"Resposta recebida do Servidor A: {resposta_json}")

        # Verifica se o servidor respondeu corretamente
        if resposta_json.get("RESPONSE") == "ALIVE":
            print("Servidor A está ativo.")
        else:
            print("Servidor A respondeu de forma inválida.")

finally:
    # Fecha o socket do cliente
    worker.close()
    print("Worker A1 encerrado.")