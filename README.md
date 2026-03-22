# Bot Telegram - Radio Amador Tester

Bot em Python que envia quizzes aleatorios das bases ANATEL via comandos:

- `/eletrica`
- `/legislacao`
- `/operacional`
- `/placar`

Cada resposta recebe correcao automatica (correta/incorreta), e o bot guarda
o placar por usuario (ID do Telegram) e por materia.

## Requisitos

- Python 3.10+

## Instalacao

1. Criar ambiente virtual (opcional, recomendado):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Criar o arquivo `.env` com o token:

```env
TELEGRAM_BOT_TOKEN=SEU_TOKEN_AQUI
```

## Execucao

```powershell
python bot.py
```

O placar e salvo automaticamente em `scoreboard.json`.

## Comandos no Telegram

- `/start` - boas-vindas e instrucoes
- `/help` - ajuda rapida
- `/eletrica` - envia quiz de eletrica
- `/legislacao` - envia quiz de legislacao
- `/operacional` - envia quiz de operacional
- `/placar` - mostra acertos/erros por materia e geral

## Como funciona o placar

- Identificacao por `user_id` do Telegram.
- Contabiliza acertos e erros para:
  - eletrica
  - legislacao
  - operacional
- Tambem calcula o total geral por usuario.
- Persistencia local em `scoreboard.json`.

## Seguranca

- Nao deixe token no codigo-fonte.
- Se um token foi compartilhado publicamente, regenere no BotFather e use o novo token no `.env`.
