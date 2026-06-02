# Plano de Testes - ASD P2P Sprint 01, 02 e 03

## CT-S1-01 — Heartbeat com Master ativo

**Passos:**
1. Iniciar um Master.
2. Iniciar um Worker apontando para esse Master.

**Esperado:**
- Worker envia `{"SERVER_UUID":"...","TASK":"HEARTBEAT"}`.
- Master responde `{"SERVER_UUID":"...","TASK":"HEARTBEAT","RESPONSE":"ALIVE"}`.
- Worker imprime `Status ALIVE recebido`.

## CT-S2-01 — Worker local recebe tarefa

**Passos:**
1. Iniciar Master A com `--seed-tasks 3`.
2. Iniciar Worker A1 conectado ao Master A.

**Esperado:**
- Worker envia apresentação local com `WORKER=ALIVE` e `WORKER_UUID`.
- Master entrega `TASK=QUERY`.
- Worker processa e envia `STATUS=OK`.
- Master responde `STATUS=ACK`.

## CT-S2-02 — Fila vazia

**Passos:**
1. Iniciar Master B com `--seed-tasks 0`.
2. Iniciar Worker B1 conectado ao Master B.

**Esperado:**
- Master responde `{"TASK":"NO_TASK"}`.
- Worker continua tentando em ciclos sem travar.

## CT-S3-01 — Pedido de ajuda aceito

**Passos:**
1. Iniciar Master B com capacidade alta e sem tarefas.
2. Iniciar Workers B1 e B2 conectados ao Master B.
3. Iniciar Master A com `--seed-tasks 12 --capacity 3 --neighbor B=127.0.0.1:8001`.

**Esperado:**
- Master A detecta saturação.
- Master A envia `request_help`.
- Master B responde `response_accepted` com o mesmo `request_id`.
- Master B envia `command_redirect` para B1/B2.

## CT-S3-02 — Registro de Worker emprestado

**Passos:**
1. Executar CT-S3-01.

**Esperado:**
- B1/B2 conectam no Master A.
- B1/B2 enviam `register_temporary_worker`.
- Master A registra Workers como emprestados.
- Nas apresentações seguintes, B1/B2 enviam `SERVER_UUID=B`.

## CT-S3-03 — Tarefa executada por Worker emprestado

**Passos:**
1. Executar CT-S3-01 e CT-S3-02.

**Esperado:**
- Master A entrega `QUERY` a B1/B2.
- B1/B2 enviam `STATUS=OK`.
- Master A envia `ACK`.
- Log do Master A indica Worker `EMPRESTADO`.

## CT-S3-04 — Devolução do Worker

**Passos:**
1. Executar fluxo completo até a fila do Master A cair abaixo do `release_threshold`.

**Esperado:**
- Master A envia `command_release`.
- Master A envia `notify_worker_returned` ao Master B.
- B1/B2 voltam ao Master B.

## CT-S3-05 — Tipo desconhecido

**Passos:**
Enviar manualmente uma mensagem tipada desconhecida para um Master:

```python
import socket, json
s = socket.create_connection(("127.0.0.1", 8000))
s.sendall((json.dumps({"type":"unknown_type","request_id":"1","payload":{}})+"\n").encode())
s.close()
```

**Esperado:**
- Master registra o tipo desconhecido no log.
- Processo continua funcionando.

## CT-S3-06 — Timeout de negociação

**Passos:**
1. Iniciar Master A com vizinho inexistente: `--neighbor B=127.0.0.1:8999`.
2. Usar `--seed-tasks` maior que `--capacity`.

**Esperado:**
- Master A tenta `request_help`.
- Conexão falha ou timeout.
- Master A registra falha e continua rodando.
