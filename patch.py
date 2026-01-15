import ast
import os
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

LOGGER_METHODS = {"info", "debug", "warning", "error", "success"}


class LoggerSessionPatcher(ast.NodeTransformer):
    def __init__(self):
        self.class_has_session_id = False

    def visit_ClassDef(self, node: ast.ClassDef):
        # Проверяем, есть ли self.session_id в классе
        self.class_has_session_id = self._class_defines_session_id(node)

        if not self.class_has_session_id:
            return node  # ничего не трогаем

        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call):
        """
        Ищем self.logger.<method>(...)
        """
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in LOGGER_METHODS
            and isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "self"
            and node.func.value.attr == "logger"
            and node.args
            and isinstance(node.args[0], ast.JoinedStr)  # f-string
        ):
            original_fstring = node.args[0]

            # Проверяем, что session_id ещё не добавлен
            if self._already_contains_session_id(original_fstring):
                return node

            # Добавляем f"{self.session_id} | " в начало
            new_values = [
                ast.FormattedValue(
                    value=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="session_id",
                        ctx=ast.Load(),
                    ),
                    conversion=-1,
                ),
                ast.Constant(value=" | "),
            ] + original_fstring.values

            node.args[0] = ast.JoinedStr(values=new_values)

        return node

    @staticmethod
    def _already_contains_session_id(fstring: ast.JoinedStr) -> bool:
        for value in fstring.values:
            if (
                isinstance(value, ast.FormattedValue)
                and isinstance(value.value, ast.Attribute)
                and value.value.attr == "session_id"
            ):
                return True
        return False

    @staticmethod
    def _class_defines_session_id(class_node: ast.ClassDef) -> bool:
        for node in ast.walk(class_node):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and target.attr == "session_id"
                    ):
                        return True
        return False


def process_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    patcher = LoggerSessionPatcher()
    new_tree = patcher.visit(tree)
    ast.fix_missing_locations(new_tree)

    new_source = ast.unparse(new_tree)

    if new_source != source:
        path.write_text(new_source, encoding="utf-8")
        logging.info(f"Пропатчен файл: {path}")


def main():
    root = Path("./src/ckr_ai_agent/api")

    logging.info("Старт патча логов с session_id...")
    for py_file in root.rglob("*.py"):
        process_file(py_file)
    logging.info("Патч завершён!")


if __name__ == "__main__":
    main()
