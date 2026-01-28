import re
from typing import Callable, Optional


SESSION_ID_RE = re.compile(r"\b[a-zA-Z0-9]{16,}\b")


class LoggerProxy:
    def __init__(
        self,
        logger,
        owner: object | None = None,
        session_id: Optional[str] = None,
        session_id_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self._logger = logger
        self._owner = owner
        self._explicit_session_id = session_id
        self._session_id_provider = session_id_provider

    def _resolve_session_id(self) -> Optional[str]:
        if self._explicit_session_id:
            return self._explicit_session_id

        if self._session_id_provider:
            return self._session_id_provider()

        if self._owner:
            for attr in vars(self._owner).values():
                if isinstance(attr, str) and SESSION_ID_RE.match(attr):
                    return attr

        return None

    def _enrich(self, msg: str) -> str:
        session_id = self._resolve_session_id()

        if not session_id:
            return msg

        if session_id in msg:
            return msg

        return f"{session_id} | {msg}"

    def __getattr__(self, name: str):
        attr = getattr(self._logger, name)

        if not callable(attr):
            return attr

        def wrapper(*args, **kwargs):
            if args and isinstance(args[0], str):
                args = (self._enrich(args[0]),) + args[1:]

            # 🔴 ВАЖНО:
            # никакого logger.opt()
            # никакой подмены объекта
            return attr(*args, **kwargs)

        return wrapper
