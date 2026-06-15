# Protocolo de Testes — P2P com Balanceamento de Carga
**Prof. Michel Junio Ferreira Rosa — Arquitetura de Sistemas Distribuídos**
**Apresentação: 15/06/2026 | Prova: 22/06/2026**

---

## ÍNDICE

- [PARTE 1 — Testes Locais (rodar em casa)](#parte-1)
  - [Pré-requisitos](#pre-requisitos)
  - [Teste Automatizado](#teste-automatizado)
  - [Teste Manual Interativo (5 terminais)](#teste-manual)
  - [Verificar métricas no dashboard](#verificar-dashboard-local)
- [PARTE 2 — Dia da Apresentação na Faculdade](#parte-2)
  - [Noite anterior: checklist de preparação](#noite-anterior)
  - [Chegando na faculdade](#chegando-na-faculdade)
  - [Descobrir IPs e coordenar com os grupos](#coordenar-grupos)
  - [Configurar firewall](#firewall)
  - [Subir o sistema com IPs reais](#subir-sistema-real)
  - [Verificar dashboard do professor](#dashboard-professor)
  - [O que demonstrar para o professor](#o-que-demonstrar)
  - [Resolução de problemas no dia](#troubleshooting)

---

<a name="parte-1"></a>
# PARTE 1 — Testes Locais

<a name="pre-requisitos"></a>
## Pré-requisitos

### 1.1 Verificar versão do Python
Abra um terminal (PowerShell) e execute:
```
python --version
```
**Esperado:** Python 3.10 ou superior. Se for menor, baixe em https://python.org

### 1.2 Instalar dependências
Na pasta do projeto:
```
pip install -r requirements.txt
```
**Esperado:**
```
Requirement already satisfied: psutil>=5.9.0 ...
```

### 1.3 Verificar que o psutil está funcionando
```
python -c "import psutil; print('psutil OK -', psutil.__version__)"
```
**Esperado:** `psutil OK - 7.x.x` (qualquer versão >= 5.9)

---

<a name="teste-automatizado"></a>
## Teste Automatizado (recomendado como primeiro passo)

Este comando sobe os processos, executa todos os testes das 4 Sprints e encerra tudo sozinho.

```
python test_local.py
```

### O que esperar ver (em ~30 segundos):

```
==================================================
  Testes de Integracao - Sistemas Distribuidos
==================================================

Iniciando subprocessos...
  Aguardando Master A (:18000)... OK
  Aguardando Master B (:18001)... OK

Sprint 01 - Heartbeat
  PASS  Sprint 01 - Heartbeat ALIVE [Master A]
  PASS  Sprint 01 - Heartbeat ALIVE [Master B]

Sprint 02 - Ciclo de Tarefas
  PASS  Sprint 02 - NO_TASK com fila vazia [Master B sem tarefas]
  PASS  Sprint 02 - Ciclo QUERY -> STATUS OK -> ACK
  PASS  Sprint 02 - Ciclo QUERY -> STATUS NOK -> ACK (tarefa com falha)

Sprint 03 - Negociacao M2M
  PASS  Sprint 03 - request_help -> rejected (high_load)
  PASS  Sprint 03 - register_temporary_worker -> ACK
  PASS  Sprint 03 - notify_worker_returned -> ACK
  PASS  Sprint 03 - tipo desconhecido ignorado (sem crash)
  PASS  Sprint 03 - request_help -> response_accepted (worker disponivel no Master B)

Bonus - Worker real (processo filho)
  PASS  Bonus - Worker real completa tarefa no Master A

Sprint 04 - Supervisor de Metricas
       (aguardando 12 s para cobrir ao menos 1 ciclo de metricas...)
  PASS  Sprint 04 - Supervisor de metricas nao derruba o Master apos 12 s

==================================================
  Resultado Final
==================================================
  12/12 testes passaram.
```

> **ATENÇÃO:** A mensagem `Falha ao enviar metricas: ...` nos logs é NORMAL se você
> não estiver conectado à internet — o master continua funcionando.
> O teste verifica apenas que o processo não cai.

---

<a name="teste-manual"></a>
## Teste Manual Interativo — 5 Terminais

Este teste mostra visualmente o fluxo completo funcionando nos logs.
Abra **5 janelas de PowerShell/Terminal** na pasta do projeto.

---

### TERMINAL 1 — Master B (auxiliar, workers disponíveis)

```
python master.py --master-id B --host 127.0.0.1 --port 8001 --capacity 10 --release-threshold 3 --seed-tasks 0 --neighbor A=127.0.0.1:8000
```

**Esperar ver:**
```
[HH:MM:SS][MASTER B] Escutando TCP em 127.0.0.1:8001
[HH:MM:SS][MASTER B] capacity=10 release_threshold=3
[HH:MM:SS][MASTER B] tasks_iniciais=0
[HH:MM:SS][MASTER B] vizinhos=['A']
```

---

### TERMINAL 2 — Master A (saturado, com muitas tarefas)

```
python master.py --master-id A --host 127.0.0.1 --port 8000 --capacity 3 --release-threshold 1 --seed-tasks 20 --neighbor B=127.0.0.1:8001
```

**Esperar ver:**
```
[HH:MM:SS][MASTER A] Escutando TCP em 127.0.0.1:8000
[HH:MM:SS][MASTER A] tasks_iniciais=20
```
Logo depois (em ~2-3s):
```
[HH:MM:SS][MASTER A] SATURACAO detectada: current_load=20 capacity=3 workers_needed=5
[HH:MM:SS][MASTER A] Enviando request_help para B@127.0.0.1:8001
```
E no Terminal 1 (Master B):
```
[HH:MM:SS][MASTER B] M2M/TYPE recebido type=request_help ...
[HH:MM:SS][MASTER B] Pedido recusado: reason=no_workers_available
```
*(Normal — Master B ainda não tem workers)*

---

### TERMINAL 3 — Worker B1 (pertence ao Master B)

```
python worker.py --worker-id B1 --master-id B --master-address 127.0.0.1:8001 --command-port 9101
```

**Esperar ver:**
```
[HH:MM:SS][WORKER B1] Servidor de comandos ativo em 127.0.0.1:9101
[HH:MM:SS][WORKER B1] Conectado ao Master atual B@127.0.0.1:8001
[HH:MM:SS][WORKER B1] Heartbeat enviado
[HH:MM:SS][WORKER B1] Status ALIVE recebido
[HH:MM:SS][WORKER B1] Master informou fila vazia: {'TASK': 'NO_TASK'}
```

---

### TERMINAL 4 — Worker B2 (pertence ao Master B)

```
python worker.py --worker-id B2 --master-id B --master-address 127.0.0.1:8001 --command-port 9102
```

**Esperar ver o mesmo que B1.**

---

### TERMINAL 5 — Worker A1 (pertence ao Master A — opcional mas recomendado)

```
python worker.py --worker-id A1 --master-id A --master-address 127.0.0.1:8000 --command-port 9001
```

---

### Sequência de eventos que você deve observar (Sprint 3 em ação):

**Passo 1 — Master A detecta saturação e pede ajuda:**
```
# Terminal 2 (Master A):
[HH:MM:SS][MASTER A] SATURACAO detectada: current_load=20 capacity=3 workers_needed=5
[HH:MM:SS][MASTER A] Enviando request_help para B@127.0.0.1:8001
```

**Passo 2 — Master B aceita e redireciona B1 e B2:**
```
# Terminal 1 (Master B):
[HH:MM:SS][MASTER B] Pedido aceito para Master A: ...
[HH:MM:SS][MASTER B] Comando enviado diretamente ao Worker B1: {"type": "command_redirect", ...}
[HH:MM:SS][MASTER B] Comando enviado diretamente ao Worker B2: {"type": "command_redirect", ...}
```

**Passo 3 — B1 e B2 se redirecionam para o Master A:**
```
# Terminal 3 (Worker B1):
[HH:MM:SS][WORKER B1] Redirecionado para Master A@127.0.0.1:8000
[HH:MM:SS][WORKER B1] register_temporary_worker enviado

# Terminal 4 (Worker B2):
[HH:MM:SS][WORKER B2] Redirecionado para Master A@127.0.0.1:8000
[HH:MM:SS][WORKER B2] register_temporary_worker enviado
```

**Passo 4 — B1 e B2 processam tarefas do Master A:**
```
# Terminal 3 (Worker B1):
[HH:MM:SS][WORKER B1] Processando QUERY para USER=USER-A-001 por X.XXs
[HH:MM:SS][WORKER B1] STATUS enviado: {'STATUS': 'OK', 'TASK': 'QUERY', 'WORKER_UUID': 'B1'}
[HH:MM:SS][WORKER B1] ACK final recebido

# Terminal 2 (Master A):
[HH:MM:SS][MASTER A] STATUS OK recebido de B1 (EMPRESTADO) para tarefa USER-A-001; ACK enviado.
```

**Passo 5 — Quando a fila normaliza, B1 e B2 voltam ao Master B:**
```
# Terminal 2 (Master A):
[HH:MM:SS][MASTER A] Carga normalizada: current_load=1 <= release_threshold=1
[HH:MM:SS][MASTER A] notify_worker_returned enviado para 127.0.0.1:8001

# Terminal 3 (Worker B1):
[HH:MM:SS][WORKER B1] Liberado para retornar ao Master original B@127.0.0.1:8001

# Terminal 2 (Master A) — cada 10s:
[HH:MM:SS][MASTER A] Metricas enviadas para nuted-ia.dev:443
  (ou "Falha ao enviar metricas" se sem internet — é normal)
```

---

<a name="verificar-dashboard-local"></a>
## Verificar métricas no Dashboard (com internet)

Se tiver conexão com a internet, verifique se as métricas chegam:

1. Deixe o master rodando por 10-15 segundos
2. Abra no browser: **https://nuted-ia.dev/supervisor/dashboard/**
3. Procure pelo `server_uuid` que você usou (ex: `A` ou `B`)

> **Nota:** O ID que aparece no dashboard é o valor de `--master-id`.
> No dia da apresentação, use o ID do seu grupo (ex: `GRUPO26`).

---

<a name="parte-2"></a>
# PARTE 2 — Dia da Apresentação na Faculdade

---

<a name="noite-anterior"></a>
## Noite Anterior — Checklist de Preparação

Execute tudo isso **em casa, antes de sair**, para garantir que não há surpresas:

- [ ] `python test_local.py` → deve mostrar **12/12 testes passaram**
- [ ] Testar o teste manual dos 5 terminais pelo menos uma vez
- [ ] Abrir https://nuted-ia.dev/supervisor/dashboard/ e confirmar que o site carrega
- [ ] Decidir o **master-id do seu grupo** (ex: `GRUPO26`) — use esse mesmo ID no dia
- [ ] Anotar os comandos de firewall (seção abaixo) em um papel ou bloco de notas
- [ ] Copiar o projeto para um pen drive de backup
- [ ] Verificar se tem Python instalado no notebook que vai levar

**Comandos para testar a conexão com o dashboard:**
```
# Teste de conectividade TLS (em casa)
python -c "
import ssl, socket, json
from datetime import datetime, timezone

payload = json.dumps({
    'server_uuid': 'GRUPO26-TESTE',
    'hostname': 'GRUPO26-TESTE.farm.local',
    'role': 'master',
    'task': 'performance_report',
    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'message_id': 'test-123',
    'payload_version': 'sprint4-monitor',
    'performance': {
        'system': {'uptime_seconds': 1, 'load_average_1m': 0.0, 'load_average_5m': 0.0,
                   'cpu': {'usage_percent': 0.0, 'count_logical': 1, 'count_physical': 1},
                   'memory': {'total_mb': 8192, 'available_mb': 4096, 'percent_used': 50.0, 'memory_used': 4096},
                   'disk': {'total_gb': 100.0, 'free_gb': 50.0, 'percent_used': 50.0}},
        'farm_state': {
            'workers': {'total_registered': 0, 'workers_utilization': 0, 'workers_alive': 0,
                        'workers_idle': 0, 'workers_borrowed': 0, 'workers_received': 0,
                        'workers_failed': 0, 'workers_home': 0, 'workers_available_capacity': 0,
                        'borrowed_workers': []},
            'tasks': {'tasks_pending': 0, 'tasks_running': 0, 'tasks_completed': 0, 'tasks_failed': 0, 'oldest_task_age_s': 0}},
        'config_thresholds': {'max_task': 10, 'warn_cpu_percent': 85, 'warn_memory_percent': 85, 'release_task': 3},
        'neighbors': []}
}) + '\n'

ctx = ssl.create_default_context()
with socket.create_connection(('nuted-ia.dev', 443), timeout=5) as s:
    with ctx.wrap_socket(s, server_hostname='nuted-ia.dev') as tls:
        tls.sendall(payload.encode('utf-8'))
print('OK - payload enviado com sucesso!')
"
```
**Esperado:** `OK - payload enviado com sucesso!`
Se aparecer erro SSL ou timeout, anote para resolver na faculdade.

---

<a name="chegando-na-faculdade"></a>
## Chegando na Faculdade

### Passo 1 — Conectar na rede da faculdade

Conecte no WiFi da faculdade. **Todos os grupos devem estar na mesma rede.**

### Passo 2 — Descobrir seu IP

Abra PowerShell e execute:
```
ipconfig
```

Procure a seção **"Adaptador de Rede sem Fio Wi-Fi"** (ou similar) e anote o **Endereço IPv4**:
```
Adaptador de Rede sem Fio Wi-Fi:
   Endereço IPv4. . . . . . . .  : 192.168.1.42   <-- ESTE AQUI
   Máscara de Sub-rede . . . . . : 255.255.255.0
   Gateway Padrão. . . . . . . . : 192.168.1.1
```

> **Dica:** Se aparecerem múltiplos IPs, use o que começa com `192.168.x.x` ou `10.x.x.x`.
> Evite IPs que começam com `169.254` (são auto-atribuídos — sem rede).

### Passo 3 — Testar conectividade com o dashboard

```
python -c "import socket; s=socket.create_connection(('nuted-ia.dev',443),5); print('Conectado ao dashboard!'); s.close()"
```
**Esperado:** `Conectado ao dashboard!`
Se falhar: a rede da faculdade pode bloquear. Tente hotspot do celular.

---

<a name="coordenar-grupos"></a>
## Coordenar com os Outros Grupos

Antes de rodar o sistema, o grupo todo precisa combinar:

### Tabela de configuração do dia (preencha no papel/WhatsApp do grupo)

| Grupo | master-id | IP | Porta Master | Portas Workers |
|-------|-----------|-----|-------------|----------------|
| **Seu grupo** | `GRUPO26` | `192.168.1.???` | `8000` | `9001`, `9002` |
| Grupo B | `GRUPO??` | `192.168.1.???` | `8000` | `9001`, `9002` |
| Professor | `michel_1` | `192.168.1.???` | `8000` | — |

> **Regra:** Cada grupo usa as mesmas portas na própria máquina (não conflita com outras máquinas).
> Apenas a **porta Master** precisa ser combinada se for diferente.

### Verificar se consegue alcançar o Master de outro grupo

```
# Substitua o IP pelo IP do outro grupo
python -c "import socket; s=socket.create_connection(('192.168.1.55',8000),3); print('Conectado ao grupo!'); s.close()"
```
**Esperado:** `Conectado ao grupo!`
Se falhar: ver seção de firewall abaixo.

---

<a name="firewall"></a>
## Configurar Firewall do Windows

Este passo **é obrigatório** para que outros grupos consigam se conectar à sua máquina.

### Opção A — Adicionar regra específica (mais seguro)

Execute como **Administrador**:
```
netsh advfirewall firewall add rule name="SD-P2P-Master" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="SD-P2P-Workers" dir=in action=allow protocol=TCP localport=9001-9010
```

### Opção B — Desativar firewall para redes privadas (mais fácil)

Execute como **Administrador**:
```
netsh advfirewall set privateprofile state off
```
> **Lembrete:** Reativar depois: `netsh advfirewall set privateprofile state on`

### Verificar se a regra funcionou

Peça para outro colega tentar conectar no seu IP e porta 8000 com o comando de verificação acima.

---

<a name="subir-sistema-real"></a>
## Subir o Sistema com IPs Reais

Substitua os valores abaixo pelos dados reais combinados com os outros grupos.

**Exemplo:** Seu IP é `192.168.1.42`, outro grupo está em `192.168.1.55`.

---

### TERMINAL 1 — Seu Master

```
python master.py --master-id GRUPO26 --host 192.168.1.42 --port 8000 --capacity 5 --release-threshold 2 --seed-tasks 20 --neighbor GRUPO27=192.168.1.55:8000
```

> - `--master-id GRUPO26` → ID que aparece no dashboard (combine com o grupo)
> - `--host 192.168.1.42` → SEU IP na rede da faculdade
> - `--neighbor GRUPO27=192.168.1.55:8000` → repita para cada grupo vizinho

**Se tiver 3 vizinhos:**
```
python master.py --master-id GRUPO26 --host 192.168.1.42 --port 8000 --capacity 5 --release-threshold 2 --seed-tasks 30 --neighbor GRUPO27=192.168.1.55:8000 --neighbor GRUPO28=192.168.1.60:8000 --neighbor michel_1=192.168.1.10:8000
```

**Esperado:**
```
[HH:MM:SS][MASTER GRUPO26] Escutando TCP em 192.168.1.42:8000
[HH:MM:SS][MASTER GRUPO26] vizinhos=['GRUPO27', 'GRUPO28', 'michel_1']
```
Logo depois (a cada 10s):
```
[HH:MM:SS][MASTER GRUPO26] Metricas enviadas para nuted-ia.dev:443
```

---

### TERMINAL 2 — Seu Worker W1

```
python worker.py --worker-id GRUPO26-W1 --master-id GRUPO26 --master-address 192.168.1.42:8000 --command-port 9001 --advertised-host 192.168.1.42
```

> **CRÍTICO:** `--advertised-host 192.168.1.42` é obrigatório na rede real.
> Sem ele, o worker anuncia `127.0.0.1` como seu endereço — outros masters
> não conseguirão enviar comandos de redirecionamento.

**Esperado:**
```
[HH:MM:SS][WORKER GRUPO26-W1] Servidor de comandos ativo em 192.168.1.42:9001
[HH:MM:SS][WORKER GRUPO26-W1] Conectado ao Master atual GRUPO26@192.168.1.42:8000
```

---

### TERMINAL 3 — Seu Worker W2

```
python worker.py --worker-id GRUPO26-W2 --master-id GRUPO26 --master-address 192.168.1.42:8000 --command-port 9002 --advertised-host 192.168.1.42
```

---

### TERMINAL 4 — (Opcional) Worker W3 para mais carga

```
python worker.py --worker-id GRUPO26-W3 --master-id GRUPO26 --master-address 192.168.1.42:8000 --command-port 9003 --advertised-host 192.168.1.42
```

---

<a name="dashboard-professor"></a>
## Verificar Dashboard do Professor

Com o Master rodando e enviando métricas:

1. Abra no browser: **https://nuted-ia.dev/supervisor/dashboard/**
2. Procure o card com o nome `GRUPO26` (ou seu master-id)
3. Verifique se os dados estão aparecendo e atualizando a cada ~10 segundos

### O que deve aparecer no dashboard:
- Nome do nó (`server_uuid`)
- CPU, memória, disco em tempo real
- Contagem de workers (total, ociosos, emprestados)
- Tarefas pendentes, executando, concluídas
- Lista de vizinhos

### Forçar envio imediato (para verificar no dashboard):

O master envia métricas automaticamente a cada 10 segundos. Se quiser ver aparecer mais rápido, reinicie o master — ele envia a primeira métrica dentro dos primeiros 10 segundos.

---

<a name="o-que-demonstrar"></a>
## O Que Demonstrar para o Professor

### Sequência recomendada de demonstração

**[~1 min] Apresentação do sistema rodando:**
- Mostrar os terminais com Master e Workers ativos
- Mostrar o dashboard com o nó do grupo aparecendo

**[~2 min] Sprint 1 — Heartbeat (nos logs):**
- Apontar no terminal do Worker as linhas:
  ```
  [WORKER W1] Heartbeat enviado
  [WORKER W1] Status ALIVE recebido
  ```

**[~2 min] Sprint 2 — Ciclo de tarefas (nos logs):**
- Apontar as linhas de QUERY, STATUS OK e ACK nos terminais de Worker e Master

**[~3 min] Sprint 3 — Balanceamento M2M (o mais importante):**
- Mostrar o Master saturado pedindo ajuda:
  ```
  [MASTER GRUPO26] SATURACAO detectada: current_load=20 capacity=5
  [MASTER GRUPO26] Enviando request_help para GRUPO27@192.168.1.55:8000
  ```
- Mostrar o outro grupo aceitando e redirecionando workers
- Mostrar workers executando tarefas do seu master
- Mostrar a devolução quando a fila normaliza

**[~1 min] Sprint 4 — Dashboard:**
- Mostrar no browser o dashboard sendo atualizado em tempo real
- Mostrar os campos: CPU, workers, tarefas

### Como provocar saturação manualmente (para demo):

Se o master já processou todas as tarefas, reinicie com mais tarefas:
```
# Ctrl+C no terminal do Master e rode de novo com mais seed-tasks:
python master.py --master-id GRUPO26 --host 192.168.1.42 --port 8000 --capacity 3 --release-threshold 1 --seed-tasks 50 --neighbor GRUPO27=192.168.1.55:8000
```

Com `capacity=3` e `seed-tasks=50`, a saturação é quase imediata.

---

<a name="troubleshooting"></a>
## Resolução de Problemas no Dia

### Problema: "ConnectionRefusedError" ao conectar no master do outro grupo
**Causa:** Firewall bloqueando.
**Solução:**
```
# Na máquina que está sendo recusada, execute como Administrador:
netsh advfirewall set privateprofile state off
```

---

### Problema: Workers não recebem comando_redirect (não se movem para outro master)
**Causa:** `--advertised-host` não foi configurado com o IP real.
**Solução:** Reiniciar o worker com `--advertised-host 192.168.1.SEU_IP`

---

### Problema: Não aparece no dashboard do professor
**Causas possíveis:**
1. Rede da faculdade bloqueia saída para porta 443
2. O master-id está diferente do que você acha

**Teste:**
```
python -c "import socket; s=socket.create_connection(('nuted-ia.dev',443),5); print('OK'); s.close()"
```
Se falhar: use hotspot do celular para o notebook.

---

### Problema: Porta já em uso ("Address already in use")
**Causa:** Processo anterior não foi encerrado.
**Solução:**
```
# Encontrar e matar o processo na porta 8000:
netstat -ano | findstr :8000
taskkill /PID <numero_do_PID> /F
```

---

### Problema: Workers ficam em loop tentando reconectar
**Causa:** O master caiu ou ainda não está no ar.
**Solução:** Verifique se o terminal do master está ativo. Reinicie o master primeiro, depois os workers.

---

### Problema: "No module named 'psutil'"
**Solução:**
```
pip install psutil
```

---

### Plano B — Se a rede da faculdade não funcionar

Se a interoperabilidade entre máquinas não funcionar, você ainda pode demonstrar tudo localmente com 2 Masters e Workers no mesmo notebook:

```
# Terminal 1 — Master B (auxiliar)
python master.py --master-id B --host 127.0.0.1 --port 8001 --capacity 10 --release-threshold 3 --seed-tasks 0 --neighbor A=127.0.0.1:8000

# Terminal 2 — Master A (saturado)
python master.py --master-id A --host 127.0.0.1 --port 8000 --capacity 3 --release-threshold 1 --seed-tasks 30 --neighbor B=127.0.0.1:8001

# Terminal 3 — Worker B1
python worker.py --worker-id B1 --master-id B --master-address 127.0.0.1:8001 --command-port 9101

# Terminal 4 — Worker B2
python worker.py --worker-id B2 --master-id B --master-address 127.0.0.1:8001 --command-port 9102

# Terminal 5 — Worker A1
python worker.py --worker-id A1 --master-id A --master-address 127.0.0.1:8000 --command-port 9001
```

O protocolo é idêntico — só muda que tudo roda na mesma máquina.

---

## Resumo Rápido — Comandos do Dia (recorte e cole)

```
# 1. Descobrir seu IP:
ipconfig

# 2. Firewall (PowerShell como Admin):
netsh advfirewall set privateprofile state off

# 3. Master (substituir SEU_IP e IP_DO_VIZINHO):
python master.py --master-id GRUPO26 --host SEU_IP --port 8000 --capacity 5 --release-threshold 2 --seed-tasks 30 --neighbor VIZINHO=IP_DO_VIZINHO:8000

# 4. Worker 1:
python worker.py --worker-id GRUPO26-W1 --master-id GRUPO26 --master-address SEU_IP:8000 --command-port 9001 --advertised-host SEU_IP

# 5. Worker 2:
python worker.py --worker-id GRUPO26-W2 --master-id GRUPO26 --master-address SEU_IP:8000 --command-port 9002 --advertised-host SEU_IP

# 6. Dashboard (browser):
# https://nuted-ia.dev/supervisor/dashboard/

# 7. Testar conectividade com outro grupo:
python -c "import socket; s=socket.create_connection(('IP_DO_VIZINHO',8000),3); print('OK'); s.close()"
```
