import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.schemas.conversation import (
    ConversationDetail,
    ConversationMessage,
    ConversationSummary,
)


class ConversationStore:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or (
            Path(__file__).resolve().parents[2]
            / "data"
            / "conversations"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _path(self, conversation_id: str) -> Path:
        try:
            safe_id = str(UUID(conversation_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid conversation ID") from exc

        return self.data_dir / f"{safe_id}.json"

    def _read(self, conversation_id: str) -> dict | None:
        path = self._path(conversation_id)
        if not path.is_file():
            return None

        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        path = self._path(data["id"])
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def create(self, title: str) -> ConversationSummary:
        now = self._now()
        data = {
            "id": str(uuid4()),
            "title": title.strip() or "New conversation",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "messages": [],
        }
        self._write(data)
        return self._summary(data)

    def list_all(self) -> list[ConversationSummary]:
        conversations = []

        for path in self.data_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                conversations.append(self._summary(data))
            except (OSError, ValueError, KeyError, TypeError):
                continue

        return sorted(
            conversations,
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def get(self, conversation_id: str) -> ConversationDetail | None:
        data = self._read(conversation_id)
        if data is None:
            return None

        return ConversationDetail(
            **self._summary(data).model_dump(),
            messages=[
                ConversationMessage.model_validate(message)
                for message in data["messages"]
            ],
        )

    def append_exchange(
        self,
        conversation_id: str,
        user_content: str,
        assistant_content: str,
    ) -> ConversationDetail | None:
        data = self._read(conversation_id)
        if data is None:
            return None

        now = self._now()
        data["messages"].extend(
            [
                {
                    "role": "user",
                    "content": user_content,
                    "created_at": now.isoformat(),
                },
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "created_at": self._now().isoformat(),
                },
            ]
        )
        data["updated_at"] = self._now().isoformat()

        if not any(
            message["role"] == "user"
            for message in data["messages"][:-2]
        ):
            data["title"] = user_content[:60].strip() or "New conversation"

        self._write(data)
        return self.get(conversation_id)

    def delete(self, conversation_id: str) -> bool:
        path = self._path(conversation_id)
        if not path.is_file():
            return False

        path.unlink()
        return True

    @staticmethod
    def _summary(data: dict) -> ConversationSummary:
        return ConversationSummary(
            id=data["id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            message_count=len(data["messages"]),
        )


def get_conversation_store() -> ConversationStore:
    return ConversationStore()
