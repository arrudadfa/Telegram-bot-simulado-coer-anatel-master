import json
import logging
import os
import random
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import Poll, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent
DATASETS = {
    "eletrica": BASE_DIR / "anatel-eletrica.json",
    "legislacao": BASE_DIR / "anatel-legislacao.json",
    "operacional": BASE_DIR / "anatel-operacional.json",
}
SCOREBOARD_PATH = BASE_DIR / "scoreboard.json"
MAX_POLL_QUESTION_LEN = 300
MAX_POLL_OPTION_LEN = 100


def load_questions(file_path: Path) -> list[dict[str, Any]]:
    """Load and validate question list from JSON file."""
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Formato invalido em {file_path.name}: esperado lista.")
    return [q for q in data if isinstance(q, dict) and not q.get("anulada", False)]


def pick_random_question(category: str, question_bank: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    questions = question_bank.get(category, [])
    if not questions:
        return None
    return random.choice(questions)


def parse_quiz_data(question: dict[str, Any]) -> tuple[str, list[str], int]:
    enunciado = sanitize_text(str(question.get("enunciado", "")).strip(), MAX_POLL_QUESTION_LEN)
    alternativas = question.get("alternativas", [])
    options: list[str] = []
    correct_option_id = -1

    if isinstance(alternativas, list):
        used_options: set[str] = set()
        for idx, alt in enumerate(alternativas):
            if not isinstance(alt, dict):
                continue
            texto = sanitize_text(str(alt.get("texto", "")).strip(), MAX_POLL_OPTION_LEN)
            texto = ensure_unique_option(texto, used_options)
            if texto:
                options.append(texto)
                used_options.add(texto)
                if bool(alt.get("correta", False)):
                    correct_option_id = len(options) - 1

    return enunciado, options, correct_option_id


def sanitize_text(text: str, max_len: int) -> str:
    """Normalize whitespace and clamp text to Telegram limits."""
    compact = " ".join(text.split())
    if len(compact) <= max_len:
        return compact
    # Reserve one char for ellipsis.
    return compact[: max_len - 1].rstrip() + "…"


def ensure_unique_option(option: str, used: set[str]) -> str:
    """Telegram poll options should be unique after truncation."""
    if not option:
        return option
    if option not in used:
        return option

    base = option
    counter = 2
    while True:
        suffix = f" ({counter})"
        allowed = MAX_POLL_OPTION_LEN - len(suffix)
        candidate = sanitize_text(base, allowed) + suffix
        if candidate not in used:
            return candidate
        counter += 1


def empty_subject_score() -> dict[str, int]:
    return {"acertos": 0, "erros": 0, "total": 0}


def make_empty_user_score(nome: str = "") -> dict[str, Any]:
    return {
        "nome": nome,
        "materias": {
            "eletrica": empty_subject_score(),
            "legislacao": empty_subject_score(),
            "operacional": empty_subject_score(),
        },
        "geral": empty_subject_score(),
    }


def load_scoreboard(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Falha ao carregar scoreboard (%s). Recriando vazio.", exc)
    return {}


def save_scoreboard(path: Path, scoreboard: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(scoreboard, f, ensure_ascii=False, indent=2)


def get_user_score(scoreboard: dict[str, Any], user_id: int, name: str = "") -> dict[str, Any]:
    key = str(user_id)
    if key not in scoreboard or not isinstance(scoreboard[key], dict):
        scoreboard[key] = make_empty_user_score(name)
    if name:
        scoreboard[key]["nome"] = name
    return scoreboard[key]


def update_score(scoreboard: dict[str, Any], user_id: int, name: str, category: str, correct: bool) -> dict[str, Any]:
    user_data = get_user_score(scoreboard, user_id, name)
    subject = user_data["materias"].setdefault(category, empty_subject_score())
    overall = user_data.setdefault("geral", empty_subject_score())

    subject["total"] += 1
    overall["total"] += 1
    if correct:
        subject["acertos"] += 1
        overall["acertos"] += 1
    else:
        subject["erros"] += 1
        overall["erros"] += 1
    return user_data


def format_score_message(user_data: dict[str, Any]) -> str:
    materias = user_data.get("materias", {})
    geral = user_data.get("geral", empty_subject_score())
    return (
        "Seu placar:\n"
        f"- Eletrica: {materias.get('eletrica', empty_subject_score())['acertos']} acertos / "
        f"{materias.get('eletrica', empty_subject_score())['erros']} erros\n"
        f"- Legislacao: {materias.get('legislacao', empty_subject_score())['acertos']} acertos / "
        f"{materias.get('legislacao', empty_subject_score())['erros']} erros\n"
        f"- Operacional: {materias.get('operacional', empty_subject_score())['acertos']} acertos / "
        f"{materias.get('operacional', empty_subject_score())['erros']} erros\n"
        f"- Geral: {geral['acertos']} acertos / {geral['erros']} erros (total {geral['total']})"
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Ola! Sou o Radio Amador Tester.\n\n"
        "Use um dos comandos abaixo para receber um quiz aleatorio:\n"
        "/eletrica\n"
        "/legislacao\n"
        "/operacional\n"
        "/placar\n\n"
        "Ao responder, eu te digo se acertou e atualizo seu placar."
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Comandos disponiveis:\n"
        "/eletrica - envia quiz de Eletrica\n"
        "/legislacao - envia quiz de Legislacao\n"
        "/operacional - envia quiz de Operacional\n"
        "/placar - mostra seu desempenho por materia\n"
        "/help - mostra esta ajuda"
    )
    await update.message.reply_text(text)


def make_category_handler(category: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        question_bank = context.application.bot_data["question_bank"]
        question = pick_random_question(category, question_bank)
        if question is None:
            await update.message.reply_text(
                f"Nao consegui carregar questoes de {category} agora. Tente novamente em alguns segundos."
            )
            return

        question_number = question.get("numero", "N/A")
        title, options, correct_option_id = parse_quiz_data(question)
        if not title or len(options) < 2 or correct_option_id < 0:
            await update.message.reply_text(
                "A questao sorteada esta incompleta. Tente novamente para receber outra."
            )
            return

        poll_message = await update.message.reply_poll(
            question=f"[{category.capitalize()} #{question_number}] {title}",
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_option_id,
            is_anonymous=False,
        )

        active_polls = context.application.bot_data.setdefault("active_polls", {})
        active_polls[poll_message.poll.id] = {
            "user_id": update.effective_user.id if update.effective_user else 0,
            "category": category,
            "correct_option_id": correct_option_id,
            "processed": False,
        }

    return handler


async def placar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    scoreboard = context.application.bot_data["scoreboard"]
    user_data = get_user_score(scoreboard, user.id, user.full_name)
    await update.message.reply_text(format_score_message(user_data))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Excecao ao processar update %s", update, exc_info=context.error)


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = update.poll_answer
    if answer is None:
        return

    active_polls = context.application.bot_data.get("active_polls", {})
    poll_data = active_polls.get(answer.poll_id)
    if not isinstance(poll_data, dict):
        logger.warning("poll_id desconhecido: %s", answer.poll_id)
        return

    if poll_data.get("processed", False):
        return

    expected_user_id = int(poll_data.get("user_id", 0))
    if expected_user_id and answer.user.id != expected_user_id:
        return

    chosen_options = list(answer.option_ids or [])
    if not chosen_options:
        return

    chosen = chosen_options[0]
    correct_option_id = int(poll_data.get("correct_option_id", -1))
    category = str(poll_data.get("category", "desconhecida"))
    is_correct = chosen == correct_option_id
    poll_data["processed"] = True

    scoreboard = context.application.bot_data["scoreboard"]
    user_name = answer.user.full_name or answer.user.username or ""
    user_data = update_score(scoreboard, answer.user.id, user_name, category, is_correct)
    save_scoreboard(SCOREBOARD_PATH, scoreboard)

    feedback = "✅ Correta!" if is_correct else "❌ Incorreta!"
    subject_score = user_data["materias"][category]
    await context.bot.send_message(
        chat_id=answer.user.id,
        text=(
            f"{feedback}\n"
            f"Materia: {category.capitalize()}\n"
            f"Nesta materia: {subject_score['acertos']} acertos / {subject_score['erros']} erros\n"
            f"Geral: {user_data['geral']['acertos']} acertos / {user_data['geral']['erros']} erros"
        ),
    )


def build_app(token: str) -> Application:
    question_bank: dict[str, list[dict[str, Any]]] = {}
    for category, path in DATASETS.items():
        question_bank[category] = load_questions(path)
        logger.info("Carregadas %d questoes de %s", len(question_bank[category]), category)

    app = Application.builder().token(token).build()
    app.bot_data["question_bank"] = question_bank
    app.bot_data["active_polls"] = {}
    app.bot_data["scoreboard"] = load_scoreboard(SCOREBOARD_PATH)

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("placar", placar_cmd))
    app.add_handler(CommandHandler("eletrica", make_category_handler("eletrica")))
    app.add_handler(CommandHandler("legislacao", make_category_handler("legislacao")))
    app.add_handler(CommandHandler("operacional", make_category_handler("operacional")))
    app.add_handler(PollAnswerHandler(poll_answer_handler))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Variavel TELEGRAM_BOT_TOKEN nao definida. Configure no ambiente antes de executar."
        )

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    port = int(os.getenv("PORT", "8080"))

    app = build_app(token)

    if webhook_url:
        logger.info("Bot iniciado em modo webhook: %s", webhook_url)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}",
        )
    else:
        logger.info("Bot iniciado em modo polling (desenvolvimento local).")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
