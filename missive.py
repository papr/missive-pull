import logging
import pathlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from typing import Dict, Optional, Union

import click
import msgpack
import requests
from dotenv import load_dotenv
from rich.logging import RichHandler
from rich.progress import Progress
from rich.traceback import install

install(show_locals=False, suppress=[click])

CACHE_NAME_CONVERSATIONS = "conversations.msgpack"
CACHE_TEMPLATE_MESSAGES = "messages.{}.msgpack"


try:
    __version__ = version("pull-missive")
except PackageNotFoundError:
    logging.warning("Package is not installed. __version__ won't be available.")
    __version__ = "not available"


def load_converstations(cache_dir: Union[str, pathlib.Path]):
    cache_dir = pathlib.Path(cache_dir)
    cache_file_path = cache_dir / CACHE_NAME_CONVERSATIONS
    return msgpack.unpackb(cache_file_path.read_bytes())


def load_messages(cache_dir: Union[str, pathlib.Path], conversation_id: str):
    cache_dir = pathlib.Path(cache_dir)
    messages_path = cache_dir / CACHE_TEMPLATE_MESSAGES.format(conversation_id)
    return msgpack.unpackb(messages_path.read_bytes())


@dataclass
class Missive:
    api_key: str
    api_base: str = "https://public.missiveapp.com/v1/"

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def conversations(self, inbox_id: str, earliest: float):
        logging.info("Loading latest conversations")
        convos = self._get_conversations_page(inbox_id)
        last_activity = convos[-1]["last_activity_at"]
        while last_activity > earliest:
            logging.info(
                "Loading conversations with activity earlier than "
                f"{datetime.utcfromtimestamp(last_activity)}"
            )
            convos += self._get_conversations_page(inbox_id, until=last_activity)
            last_activity = convos[-1]["last_activity_at"]
        for convo in reversed(convos):
            if convo["last_activity_at"] < earliest:
                del convos[-1]
            if convo["last_activity_at"] >= earliest:
                break
        return convos

    def _get_conversations_page(
        self, inbox_id: str, until: Optional[float] = None, limit: int = 50
    ):
        params: Dict[str, Union[str, int, float]] = {
            "team_all": inbox_id,
            "limit": limit,
        }
        if until is not None:
            params["until"] = until
        resp = requests.get(
            self.api_base + "conversations", params=params, headers=self.headers
        )
        resp.raise_for_status()
        return resp.json()["conversations"]

    def messages(self, conversation_id: str, earliest: float):
        logging.info("Loading newest messages")
        limit = 10
        messages = self._get_messages_page(conversation_id, limit=limit)
        if not messages:
            logging.warning(f"No messages found for conversation {conversation_id}")
            return []
        last_delivered = messages[-1]["delivered_at"]
        while last_delivered > earliest:
            logging.info(
                "Loading messages delivered earlier than "
                f"{datetime.utcfromtimestamp(last_delivered)}"
            )
            messages_page = self._get_messages_page(
                conversation_id, last_delivered, limit=limit
            )
            messages += messages_page
            last_delivered = messages[-1]["delivered_at"]
            if len(messages_page) < limit:
                break  # reached last page
        for msg in reversed(messages):
            if msg["delivered_at"] < earliest:
                del messages[-1]
            if msg["delivered_at"] >= earliest:
                break
        return messages

    def _get_messages_page(
        self, conversation_id: str, until: Optional[float] = None, limit: int = 10
    ):
        params: Dict[str, Union[int, float]] = {"limit": limit}
        if until is not None:
            params["until"] = until
        resp = requests.get(
            self.api_base + f"conversations/{conversation_id}/messages",
            params=params,
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()["messages"]


@click.command()
@click.option("-v", "--verbose", count=True)
@click.option("-i", "--inbox-id", envvar="INBOX_ID", required=True)
@click.option("-key", "--api-key", envvar="MISSIVE_API_KEY", required=True)
@click.option("-until", type=click.DateTime())
@click.option(
    "-delta", type=(int, str), help="Format: <number> <unit: 'weeks' or 'days'>"
)
@click.option(
    "-c",
    "--cache-dir",
    default=pathlib.Path("missive.cache.d"),
    show_default=True,
    type=click.Path(
        writable=True, file_okay=False, dir_okay=True, path_type=pathlib.Path
    ),
    required=True,
)
def pull(
    verbose,
    inbox_id,
    api_key,
    until: Optional[datetime],
    delta,
    cache_dir: pathlib.Path,
):
    _setup_logging(verbose_option_count=verbose)
    logging.debug(f"{until=} {delta=}")
    none_given = until is None and delta is None
    both_given = until is not None and delta is not None
    if none_given or both_given:
        logging.error(
            "Either `-until` xor `-delta` argument required. "
            "See `python missive.py pull --help`."
        )
        raise SystemExit(-1)
    elif until is not None:
        earliest = datetime.timestamp(until)
    elif delta is not None:
        num, unit = delta
        delta = timedelta(**{unit: num})
        logging.debug(f"Going back in time {delta}")
        until = datetime.now() - delta
        earliest = datetime.timestamp(until)
    else:
        raise NotImplementedError

    with Progress() as progress:
        task = progress.add_task("Loading conversations...", total=None)

        missive = Missive(api_key)
        conversations = missive.conversations(inbox_id, earliest=earliest)

        cache_dir.mkdir(exist_ok=True)
        cache_file_path = cache_dir / CACHE_NAME_CONVERSATIONS
        cache_file_path.write_bytes(msgpack.packb(conversations))
        logging.info(
            f"Cached {len(conversations)} conversations to {cache_dir.resolve()}"
        )

        progress.remove_task(task)

        for conv in progress.track(conversations, description="Loading messages..."):
            conv_id = conv["id"]
            messages = missive.messages(conv_id, earliest)
            message_path = cache_dir / CACHE_TEMPLATE_MESSAGES.format(conv_id)
            message_path.write_bytes(msgpack.packb(messages))
            logging.info(f"Cached {len(messages)} messages for conversation {conv_id}")


def _setup_logging(verbose_option_count):
    levels = defaultdict(lambda: "WARNING")
    levels[1] = "INFO"
    levels[2] = "DEBUG"
    logging.basicConfig(
        level=levels[verbose_option_count],
        format="%(message)s",
        handlers=[RichHandler()],
    )


def main():
    """CLI Entrypoint"""
    load_dotenv()
    pull()


if __name__ == "__main__":
    main()
