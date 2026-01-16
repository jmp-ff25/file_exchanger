import ast
import pathlib
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TARGET_DIR = pathlib.Path("./src/ckr_ai_agent/api")
LOGGER_METHODS = {"info", "debug", "warning", "error", "success"}


class SessionIdLoggerPatcher(ast.NodeTransformer):
    def __init__(self):
        self.class_has_session_id = False
        self.file_modified = False

    # ---------- helpers ----------

    @staticmethod
    def is_self_attr(node, attr_name: str) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr == attr_name
        )

    # ---------- class-level ----------

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_has_session_id = self._detect_session_id(node)

        if not self.class_has_session_id:
            return node  # вообще не трогаем класс

        self.generic_visit(node)
        return node

    def _detect_session_id(self, class_node: ast.ClassDef) -> bool:
        """
        Проверяем, что в классе реально существует self.session_id:
        - либо присваивается в __init__
        - либо объявлен как attribute где-то ещё
        """
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef):
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if self.is_self_attr(target, "session_id"):
                                return True
        return False

    # ---------- call-level ----------

    def visit_Call(self, node: ast.Call):
        """
        Ищем self.logger.<level>(...)
        """
        if not self.class_has_session_id:
            return node

        if not isinstance(node.func, ast.Attribute):
            return node

        if node.func.attr not in LOGGER_METHODS:
            return node

        logger_obj = node.func.value
        if not (
            isinstance(logger_obj, ast.Attribute)
            and isinstance(logger_obj.value, ast.Name)
            and logger_obj.value.id == "self"
            and logger_obj.attr == "logger"
        ):
            return node

        if not node.args:
            return node

        first_arg = node.args[0]

        # если session_id уже есть — не трогаем
        if self._contains_session_id(first_arg):
            return node

        # модифицируем
        new_arg = self._prepend_session_id(first_arg)
        node.args[0] = new_arg
        self.file_modified = True

        return node

    # ---------- string handling ----------

    @staticmethod
    def _contains_session_id(node) -> bool:
        return (
            isinstance(node, ast.JoinedStr)
            and any(
                isinstance(v, ast.FormattedValue)
                and isinstance(v.value, ast.Attribute)
                and isinstance(v.value.value, ast.Name)
                and v.value.value.id == "self"
                and v.value.attr == "session_id"
                for v in node.values
            )
        )

    @staticmethod
    def _prepend_session_id(node):
        prefix = ast.JoinedStr(values=[
            ast.FormattedValue(
                value=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="session_id",
                    ctx=ast.Load(),
                ),
                conversion=-1,
            ),
            ast.Constant(value=" | "),
        ])

        if isinstance(node, ast.JoinedStr):
            return ast.JoinedStr(values=prefix.values + node.values)

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return ast.JoinedStr(values=prefix.values + [node])

        # всё остальное (редкий кейс)
        return ast.JoinedStr(values=prefix.values + [
            ast.FormattedValue(value=node, conversion=-1)
        ])


def process_file(path: pathlib.Path):
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    patcher = SessionIdLoggerPatcher()
    patcher.visit(tree)

    if not patcher.file_modified:
        return  # 🔴 КЛЮЧЕВО: файл вообще не трогаем

    new_source = ast.unparse(tree)
    path.write_text(new_source, encoding="utf-8")
    logging.info(f"patched: {path}")


def main():
    for file in TARGET_DIR.rglob("*.py"):
        process_file(file)


if __name__ == "__main__":
    main()
