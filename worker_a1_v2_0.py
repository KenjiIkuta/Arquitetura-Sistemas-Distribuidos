import socket
import json
import time
import random

# ============================================================
# CONFIGURAÇÕES DO WORKER
# ============================================================

HOST = "127.0.0.1"
PORT = 8000

WORKER_UUID = "W-123"

# Deixe como None para Worker local.
# Para simular Worker emprestado, use algo como "Master_B".
ORIGINAL_SERVER_UUID = "Master_B"

SOCKET_TIMEOUT = 5
MAX_CYCLES = 10
CYCLE_INTERVAL = 5

# Probabilidade de sucesso da simulação
SUCCESS_RATE = 0.8


# ============================================================
# FUNÇÕES AUXILIARES DE MENSAGERIA
# ============================================================

def send_json_line(stream, payload):
    """
    Envia um dict como JSON terminado com '\n'.
    """
    message = json.dumps(payload) + "\n"
    stream.write(message.encode("utf-8"))
    stream.flush()


def recv_json_line(stream):
    """
    Lê uma linha do stream e converte para dict.

    Retorna:
        dict -> JSON válido
        None -> conexão encerrada
    """
    line = stream.readline()

    if not line:
        return None

    return json.loads(line.decode("utf-8"))


# ============================================================
# PAYLOADS DO WORKER
# ============================================================

def montar_payload_apresentacao():
    """
    Monta o payload de apresentação do Worker.

    Formato:
    {
        "WORKER": "ALIVE",
        "WORKER_UUID": "..."
    }

    Campo opcional:
    {
        "SERVER_UUID": "..."
    }
    apenas se o worker for emprestado.
    """
    payload = {
        "WORKER": "ALIVE",
        "WORKER_UUID": WORKER_UUID
    }

    if ORIGINAL_SERVER_UUID is not None:
        payload["SERVER_UUID"] = ORIGINAL_SERVER_UUID

    return payload


def montar_payload_status(status):
    """
    Monta o payload final de status do Worker.

    Formato:
    {
        "STATUS": "OK" ou "NOK",
        "TASK": "QUERY",
        "WORKER_UUID": "..."
    }
    """
    return {
        "STATUS": status,
        "TASK": "QUERY",
        "WORKER_UUID": WORKER_UUID
    }


# ============================================================
# VALIDAÇÕES DAS RESPOSTAS DO MASTER
# ============================================================

def validar_resposta_tarefa(payload):
    """
    O Master pode responder com:
    1) {"TASK": "QUERY", "USER": "..."}
    2) {"TASK": "NO_TASK"}
    """
    if not isinstance(payload, dict):
        return False, "Payload não é um objeto JSON."

    if "TASK" not in payload:
        return False, "Campo obrigatório ausente: TASK."

    task = payload["TASK"]

    if task == "NO_TASK":
        return True, None

    if task == "QUERY":
        if "USER" not in payload:
            return False, "QUERY recebida sem campo USER."
        if not isinstance(payload["USER"], str) or not payload["USER"].strip():
            return False, "Campo USER inválido."
        return True, None

    return False, f"TASK inválida recebida do Master: {task}"


def validar_ack(payload):
    """
    Valida o ACK final do Master.

    Esperado:
    {
        "STATUS": "ACK",
        "WORKER_UUID": "..."
    }
    """
    if not isinstance(payload, dict):
        return False, "Payload não é um objeto JSON."

    if payload.get("STATUS") != "ACK":
        return False, "Campo STATUS diferente de ACK."

    if payload.get("WORKER_UUID") != WORKER_UUID:
        return False, "ACK recebido para outro WORKER_UUID."

    return True, None


# ============================================================
# SIMULAÇÃO DE PROCESSAMENTO
# ============================================================

def processar_tarefa(task_payload):
    """
    Simula o processamento da tarefa recebida.

    O enunciado permite usar algo simples como sleep ou cálculo.
    Aqui usamos sleep aleatório e devolvemos OK/NOK.
    """
    task = task_payload.get("TASK")
    user = task_payload.get("USER")

    if task != "QUERY":
        print(f"[WORKER] TASK inválida recebida: {task}")
        return "NOK"

    if not isinstance(user, str) or not user.strip():
        print(f"[WORKER] USER inválido recebido: {user}")
        return "NOK"

    print(f"[WORKER] Iniciando processamento para USER={user}")

    processing_time = random.uniform(1.0, 3.0)
    time.sleep(processing_time)

    status = "OK" if random.random() < SUCCESS_RATE else "NOK"

    print(
        f"[WORKER] Processamento concluído para USER={user} "
        f"em {processing_time:.2f}s com STATUS={status}"
    )

    return status


# ============================================================
# CICLO COMPLETO DE EXECUÇÃO
# ============================================================

def executar_ciclo(numero_ciclo):
    """
    Executa um ciclo completo do Worker na Sprint 2:

    1. conecta no Master
    2. envia apresentação
    3. recebe QUERY ou NO_TASK
    4. se houver QUERY, processa
    5. envia status
    6. recebe ACK
    """
    print(f"\n[WORKER] ===== Início do ciclo {numero_ciclo} =====")

    try:
        with socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT) as client:
            client.settimeout(SOCKET_TIMEOUT)

            with client.makefile("rwb") as stream:
                # ------------------------------------------------
                # 1) APRESENTAÇÃO DO WORKER
                # ------------------------------------------------
                presentation_payload = montar_payload_apresentacao()
                send_json_line(stream, presentation_payload)
                print(f"[WORKER] Apresentação enviada: {presentation_payload}")

                # ------------------------------------------------
                # 2) RECEBER TAREFA OU NO_TASK
                # ------------------------------------------------
                task_payload = recv_json_line(stream)

                if task_payload is None:
                    print("[WORKER] O Master encerrou a conexão sem responder.")
                    return False

                print(f"[WORKER] Resposta do Master: {task_payload}")

                ok, error = validar_resposta_tarefa(task_payload)
                if not ok:
                    print(f"[WORKER] Resposta inválida do Master: {error}")
                    return False

                if task_payload["TASK"] == "NO_TASK":
                    print("[WORKER] Nenhuma tarefa disponível neste ciclo.")
                    print(f"[WORKER] ===== Fim do ciclo {numero_ciclo} =====")
                    return True

                # ------------------------------------------------
                # 3) PROCESSAR TAREFA
                # ------------------------------------------------
                final_status = processar_tarefa(task_payload)

                # ------------------------------------------------
                # 4) ENVIAR STATUS AO MASTER
                # ------------------------------------------------
                status_payload = montar_payload_status(final_status)
                send_json_line(stream, status_payload)
                print(f"[WORKER] Status enviado ao Master: {status_payload}")

                # ------------------------------------------------
                # 5) RECEBER ACK FINAL
                # ------------------------------------------------
                ack_payload = recv_json_line(stream)

                if ack_payload is None:
                    print("[WORKER] O Master não enviou ACK.")
                    return False

                print(f"[WORKER] ACK recebido: {ack_payload}")

                ok, error = validar_ack(ack_payload)
                if not ok:
                    print(f"[WORKER] ACK inválido: {error}")
                    return False

                print("[WORKER] Ciclo concluído com sucesso.")
                print(f"[WORKER] ===== Fim do ciclo {numero_ciclo} =====")
                return True

    except ConnectionRefusedError:
        print("[WORKER] Conexão recusada: o Master pode estar offline.")
        return False
    except socket.timeout:
        print("[WORKER] Timeout aguardando resposta do Master.")
        return False
    except json.JSONDecodeError:
        print("[WORKER] JSON inválido recebido do Master.")
        return False
    except Exception as e:
        print(f"[WORKER] Erro inesperado no ciclo {numero_ciclo}: {e}")
        return False


# ============================================================
# FUNÇÃO PRINCIPAL DO WORKER
# ============================================================

def main():
    print("[WORKER] Iniciando Worker v2")
    print(f"[WORKER] HOST={HOST} PORT={PORT}")
    print(f"[WORKER] WORKER_UUID={WORKER_UUID}")
    print(f"[WORKER] ORIGINAL_SERVER_UUID={ORIGINAL_SERVER_UUID}")
    print(f"[WORKER] SOCKET_TIMEOUT={SOCKET_TIMEOUT}s")
    print(f"[WORKER] MAX_CYCLES={MAX_CYCLES}")
    print(f"[WORKER] CYCLE_INTERVAL={CYCLE_INTERVAL}s")
    print("[WORKER] Pressione Ctrl+C para encerrar.\n")

    try:
        for ciclo in range(1, MAX_CYCLES + 1):
            sucesso = executar_ciclo(ciclo)

            if ciclo < MAX_CYCLES:
                if sucesso:
                    print(f"[WORKER] Aguardando {CYCLE_INTERVAL}s para o próximo ciclo...\n")
                else:
                    print(f"[WORKER] Falha no ciclo. Tentando novamente em {CYCLE_INTERVAL}s...\n")

                time.sleep(CYCLE_INTERVAL)

    except KeyboardInterrupt:
        print("\n[WORKER] Encerramento solicitado pelo terminal.")
    finally:
        print("[WORKER] Worker encerrado com sucesso.")


if __name__ == "__main__":
    main()