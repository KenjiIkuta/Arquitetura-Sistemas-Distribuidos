# ASD - P2P com Balanceamento de Carga Dinâmico

Implementação em Python puro, usando `socket`, `threading`, JSON e delimitador `\n`.

Este projeto cobre as Sprints 01, 02 e 03:

- Sprint 01: Heartbeat Worker ↔ Master.
- Sprint 02: Apresentação do Worker, fila de tarefas, QUERY/NO_TASK, STATUS e ACK.
- Sprint 03: Negociação Master-to-Master, empréstimo de Workers, registro temporário e devolução.

## Estrutura

```txt
asd_p2p_sprint3/
├── master.py
├── worker.py
├── README.md
└── TEST_PLAN.md
```

## Requisitos

- Python 3.10 ou superior.
- Não precisa instalar biblioteca externa.

## Como rodar a demonstração completa

Abra 4 terminais na pasta do projeto.

### Terminal 1 — Master B, vizinho com Workers disponíveis

```bash
python master.py --master-id B --host 127.0.0.1 --port 8001 --capacity 10 --release-threshold 3 --seed-tasks 0 --neighbor A=127.0.0.1:8000
```

### Terminal 2 — Master A, saturado e solicitando ajuda

```bash
python master.py --master-id A --host 127.0.0.1 --port 8000 --capacity 3 --release-threshold 1 --seed-tasks 12 --neighbor B=127.0.0.1:8001
```

### Terminal 3 — Worker B1, Worker local do Master B

```bash
python worker.py --worker-id B1 --master-id B --master-address 127.0.0.1:8001 --command-port 9101
```

### Terminal 4 — Worker B2, Worker local do Master B

```bash
python worker.py --worker-id B2 --master-id B --master-address 127.0.0.1:8001 --command-port 9102
```

Opcionalmente, abra um quinto terminal para um Worker local do Master A:

```bash
python worker.py --worker-id A1 --master-id A --master-address 127.0.0.1:8000 --command-port 9001
```

## Fluxo esperado na demo

1. O Master A inicia com 12 tarefas e capacidade 3.
2. O monitor do Master A detecta saturação.
3. O Master A envia `request_help` para o Master B.
4. O Master B avalia sua carga e seus Workers ociosos.
5. O Master B responde `response_accepted` com `worker_details`.
6. O Master B envia `command_redirect` para B1/B2.
7. B1/B2 se desconectam logicamente do Master B e conectam no Master A.
8. B1/B2 enviam `register_temporary_worker` para o Master A.
9. B1/B2 passam a executar tarefas do Master A usando o protocolo da Sprint 02.
10. Quando a fila do Master A cai abaixo do `release_threshold`, o Master A envia `command_release`.
11. O Master A envia `notify_worker_returned` ao Master B.
12. B1/B2 voltam ao Master B.

## Payloads implementados

### Sprint 01 — Heartbeat

Worker → Master:

```json
{
  "SERVER_UUID": "A",
  "TASK": "HEARTBEAT"
}
```

Master → Worker:

```json
{
  "SERVER_UUID": "A",
  "TASK": "HEARTBEAT",
  "RESPONSE": "ALIVE"
}
```

### Sprint 02 — Apresentação local

Worker → Master:

```json
{
  "WORKER": "ALIVE",
  "WORKER_UUID": "W-123"
}
```

Master → Worker, com tarefa:

```json
{
  "TASK": "QUERY",
  "USER": "USER-A-001"
}
```

Master → Worker, sem tarefa:

```json
{
  "TASK": "NO_TASK"
}
```

Worker → Master, status:

```json
{
  "STATUS": "OK",
  "TASK": "QUERY",
  "WORKER_UUID": "W-123"
}
```

Master → Worker, confirmação:

```json
{
  "STATUS": "ACK",
  "WORKER_UUID": "W-123"
}
```

### Sprint 02 — Apresentação emprestada

Worker → Master temporário:

```json
{
  "WORKER": "ALIVE",
  "WORKER_UUID": "B1",
  "SERVER_UUID": "B"
}
```

O projeto também envia campos extras tolerados pelo strict parsing:

```json
{
  "WORKER_HOST": "127.0.0.1",
  "WORKER_PORT": 9101
}
```

Esses campos ajudam o Master a enviar comandos diretamente ao Worker, mas não quebram o protocolo porque campos desconhecidos devem ser ignorados.

### Sprint 03 — request_help

Master A → Master B:

```json
{
  "type": "request_help",
  "request_id": "uuid-v4",
  "payload": {
    "master_id": "A",
    "current_load": 12,
    "capacity": 3,
    "workers_needed": 3
  }
}
```

O projeto também envia o campo extra `master_address` para facilitar a simulação local:

```json
{
  "master_address": "127.0.0.1:8000"
}
```

### Sprint 03 — response_accepted

Master B → Master A:

```json
{
  "type": "response_accepted",
  "request_id": "mesmo-uuid-do-request-help",
  "payload": {
    "workers_offered": 2,
    "worker_details": [
      { "id": "B1", "address": "127.0.0.1:9101" },
      { "id": "B2", "address": "127.0.0.1:9102" }
    ]
  }
}
```

### Sprint 03 — response_rejected

Master B → Master A:

```json
{
  "type": "response_rejected",
  "request_id": "mesmo-uuid-do-request-help",
  "payload": {
    "reason": "high_load"
  }
}
```

### Sprint 03 — command_redirect

Master B → Worker B1:

```json
{
  "type": "command_redirect",
  "request_id": "uuid-v4",
  "payload": {
    "new_master_address": "127.0.0.1:8000"
  }
}
```

### Sprint 03 — register_temporary_worker

Worker B1 → Master A:

```json
{
  "type": "register_temporary_worker",
  "request_id": "uuid-v4",
  "payload": {
    "worker_id": "B1",
    "original_master_address": "127.0.0.1:8001"
  }
}
```

O projeto também envia `original_master_id` e `worker_address` como campos extras tolerados.

### Sprint 03 — command_release

Master A → Worker B1:

```json
{
  "type": "command_release",
  "request_id": "uuid-v4",
  "payload": {
    "original_master_address": "127.0.0.1:8001"
  }
}
```

### Sprint 03 — notify_worker_returned

Master A → Master B:

```json
{
  "type": "notify_worker_returned",
  "request_id": "uuid-v4",
  "payload": {
    "worker_id": "B1"
  }
}
```

## Observações importantes

- Todas as mensagens JSON são finalizadas com `\n`.
- O Master usa threads para atender múltiplas conexões.
- A fila de tarefas é `queue.Queue`, thread-safe.
- O estado compartilhado dos Workers é protegido com `threading.RLock`.
- Mensagens com `type` desconhecido são logadas e ignoradas.
- Campos desconhecidos são tolerados.
- Campos obrigatórios ausentes geram log de erro sem derrubar o processo.
- O Worker temporário volta ao Master original se perder conexão com o Master temporário.

## Encerramento

Use `Ctrl+C` nos terminais para encerrar Masters e Workers.
