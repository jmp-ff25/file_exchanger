import re
from typing import Callable, Optional, Any


# Используется ТОЛЬКО для проверки:
# "уже есть ли session_id в начале сообщения"
SESSION_ID_IN_MSG_RE = re.compile(r"^[a-zA-Z0-9-]{3,}\s*\|\s*")


class LoggerProxy:
    def __init__(
        self,
        logger: Any,
        owner: object | None = None,
        session_id: Optional[str] = None,
        session_id_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self._logger = logger
        self._owner = owner
        self._explicit_session_id = session_id
        self._session_id_provider = session_id_provider

    # -------------------------
    # Session ID resolution
    # -------------------------

    def _resolve_session_id(self) -> Optional[str]:
        # 1. Явно переданный session_id (middleware)
        if self._explicit_session_id:
            return self._explicit_session_id

        # 2. session_id_provider (middleware / функции)
        if self._session_id_provider:
            try:
                return self._session_id_provider()
            except Exception:
                return None

        # 3. owner.session_id (ТОЛЬКО если атрибут так называется)
        if self._owner and hasattr(self._owner, "session_id"):
            return getattr(self._owner, "session_id")

        # 4. Никакой эвристики по vars(owner)
        return None

    # -------------------------
    # Message enrichment
    # -------------------------

    def _enrich(self, msg: str) -> str:
        if not isinstance(msg, str):
            return msg

        session_id = self._resolve_session_id()
        if not session_id:
            return msg

        # Если session_id уже есть в начале сообщения — ничего не делаем
        if SESSION_ID_IN_MSG_RE.match(msg):
            return msg

        return f"{session_id} | {msg}"

    # -------------------------
    # Proxy mechanics
    # -------------------------

    def __getattr__(self, name: str):
        attr = getattr(self._logger, name)

        # Пробрасываем не-callable атрибуты напрямую
        if not callable(attr):
            return attr

        def wrapper(*args, **kwargs):
            if args and isinstance(args[0], str):
                args = (self._enrich(args[0]),) + args[1:]

            # ВАЖНО:
            # - не меняем logger
            # - не используем opt()
            # - не ломаем mock
            return attr(*args, **kwargs)

        return wrapper
