"""Persists pending chat-message deletions across bot restarts.

PTB's JobQueue lives in memory, so a restart drops any scheduled deletion.
Entries are mirrored to a small JSON file and replayed on startup.
"""
import json
import logging
import os
import threading
import time

from telegram.error import BadRequest

from .. import PROJECT_ROOT

logger = logging.getLogger(__name__)

PENDING_DELETIONS_PATH = os.path.join(PROJECT_ROOT, "pending_deletions.json")
_LOCK = threading.Lock()


def _load():
    try:
        with open(PENDING_DELETIONS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return [item for item in data if isinstance(item, dict)]
    except (OSError, ValueError):
        return []


def _save(items):
    temp_path = f"{PENDING_DELETIONS_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(items, handle)
    os.replace(temp_path, PENDING_DELETIONS_PATH)


def _track(chat_id, message_id, delete_at):
    with _LOCK:
        items = [
            item for item in _load()
            if not (item.get("chat_id") == chat_id and item.get("message_id") == message_id)
        ]
        items.append({
            "chat_id": chat_id,
            "message_id": message_id,
            "delete_at": delete_at,
        })
        _save(items)


def _untrack(chat_id, message_id):
    with _LOCK:
        items = _load()
        kept = [
            item for item in items
            if not (item.get("chat_id") == chat_id and item.get("message_id") == message_id)
        ]
        if len(kept) != len(items):
            _save(kept)


async def _delete_message_job(context):
    job = context.job
    if not job:
        return
    chat_id = job.data.get("chat_id")
    message_id = job.data.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BadRequest:
        pass
    except Exception as exc:
        logger.warning("Could not delete message %s/%s: %s", chat_id, message_id, exc)
        return
    _untrack(chat_id, message_id)


def schedule_message_deletion(job_queue, chat_id, message_id, delay_seconds=1200):
    delete_at = time.time() + delay_seconds
    _track(chat_id, message_id, delete_at)
    if job_queue is None:
        logger.error("JobQueue unavailable: message %s/%s will not be auto-deleted.", chat_id, message_id)
        return
    job_queue.run_once(
        _delete_message_job,
        when=delay_seconds,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"message_delete:{chat_id}:{message_id}",
    )


async def restore_pending_deletions(application):
    items = _load()
    if not items:
        return
    now = time.time()
    for item in items:
        chat_id = item.get("chat_id")
        message_id = item.get("message_id")
        if not chat_id or not message_id:
            continue
        remaining = float(item.get("delete_at", 0)) - now
        if remaining <= 0:
            try:
                await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest:
                pass
            except Exception as exc:
                logger.warning("Could not delete restored message %s/%s: %s", chat_id, message_id, exc)
                continue
            _untrack(chat_id, message_id)
            continue
        if application.job_queue is None:
            continue
        application.job_queue.run_once(
            _delete_message_job,
            when=remaining,
            data={"chat_id": chat_id, "message_id": message_id},
            name=f"message_delete:{chat_id}:{message_id}",
        )
    logger.info("Restored %d pending message deletion(s).", len(items))
