def wrapper(*args, **kwargs):
  if args and isinstance(args[0], str) and self._enrich:
      msg = self._enrich(args[0])
      args = (msg, *args[1:])
  
  if self._enrich:
      # только для prod-использования
      logger = self._logger
      if hasattr(logger, "opt"):
          logger = logger.opt(depth=2)
      return getattr(logger, name)(*args, **kwargs)
  else:
      # для тестов, чтобы mock_logger видел вызовы напрямую
      return attr(*args, **kwargs)
