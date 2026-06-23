import ast
import sys
import os
import json
import argparse
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Issue:
    path: str
    line: int
    kind: str  # function | class | variable | import | argument
    name: str

    def __str__(self):
        return f"{self.path}:{self.line}: неиспользуемый {self.kind} '{self.name}'"


@dataclass
class FileSymbols:
    """Что объявлено и что используется в одном файле."""
    path: str
    defined_funcs: dict[str, int] = field(default_factory=dict)    # name -> line
    defined_classes: dict[str, int] = field(default_factory=dict)
    defined_vars: dict[str, int] = field(default_factory=dict)
    imports: dict[str, int] = field(default_factory=dict)           # alias -> line
    used_names: set[str] = field(default_factory=set)


class SymbolCollector(ast.NodeVisitor):
    def __init__(self, path: str):
        self.path = path
        self.syms = FileSymbols(path=path)
        self._scope_stack: list[str] = []  # имена функций/классов для отслеживания вложенности

    # ── объявления ────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # верхнеуровневые функции и методы верхнеуровневых классов
        if len(self._scope_stack) <= 1:
            self.syms.defined_funcs[node.name] = node.lineno
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        if not self._scope_stack:
            self.syms.defined_classes[node.name] = node.lineno
        self._scope_stack.append(node.name)
        # базовые классы — это использование
        for base in node.bases:
            self._collect_used(base)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Assign(self, node: ast.Assign):
        # только простые присваивания на уровне модуля
        if not self._scope_stack:
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    self.syms.defined_vars[target.id] = node.lineno
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.syms.imports[name] = node.lineno

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self.syms.imports[name] = node.lineno

    # ── использования ─────────────────────────────────────────────────────────

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.syms.used_names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute):
        self._collect_used(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        self._collect_used(node.func)
        for arg in node.args:
            self._collect_used(arg)
        for kw in node.keywords:
            self._collect_used(kw.value)

    def _collect_used(self, node):
        if isinstance(node, ast.Name):
            self.syms.used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            self._collect_used(node.value)


def collect_symbols(path: str) -> FileSymbols | None:
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        return None
    collector = SymbolCollector(path)
    collector.visit(tree)
    return collector.syms


def find_issues(all_syms: list[FileSymbols]) -> list[Issue]:
    # глобально используемые имена (любой файл)
    all_used: set[str] = set()
    for s in all_syms:
        all_used |= s.used_names

    # имена из __all__ тоже считаем использованными
    issues: list[Issue] = []

    for s in all_syms:
        for name, line in s.defined_funcs.items():
            if name.startswith("_") or name in ("__init__", "__new__", "__str__",
                                                  "__repr__", "__eq__", "__hash__",
                                                  "__len__", "__iter__", "__next__"):
                continue
            if name not in all_used:
                issues.append(Issue(s.path, line, "функция", name))

        for name, line in s.defined_classes.items():
            if name.startswith("_"):
                continue
            if name not in all_used:
                issues.append(Issue(s.path, line, "класс", name))

        for name, line in s.defined_vars.items():
            if name in ("__version__", "__author__", "__all__", "__doc__"):
                continue
            if name not in all_used:
                issues.append(Issue(s.path, line, "переменная", name))

        for name, line in s.imports.items():
            if name not in all_used:
                issues.append(Issue(s.path, line, "импорт", name))

    return sorted(issues, key=lambda i: (i.path, i.line))


def collect_files(targets: list[str], ignores: list[str]) -> list[str]:
    result = []
    for target in targets:
        p = Path(target)
        if p.is_file() and p.suffix == ".py":
            result.append(str(p))
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                rel = str(f)
                skip = any(fnmatch.fnmatch(f.name, pat) for pat in ignores)
                skip = skip or any(fnmatch.fnmatch(str(f), pat) for pat in ignores)
                # пропускаем виртуальные окружения и кэши
                parts = f.parts
                if any(part in (".venv", "venv", "__pycache__", ".git", "node_modules",
                                "dist", "build", ".eggs") for part in parts):
                    continue
                if not skip:
                    result.append(rel)
    return result


def main():
    parser = argparse.ArgumentParser(
        prog="deadcode",
        description="Находит неиспользуемый Python-код через AST-анализ",
    )
    parser.add_argument("targets", nargs="*", default=["."], metavar="путь",
                        help="Файлы или директории для проверки (по умолчанию: .)")
    parser.add_argument("--ignore", action="append", default=[], metavar="паттерн",
                        help="Glob-паттерны для исключения (можно повторять)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Формат вывода")
    parser.add_argument("--warn-only", action="store_true",
                        help="Выходить с кодом 0 даже при наличии проблем")
    args = parser.parse_args()

    files = collect_files(args.targets, args.ignore)
    if not files:
        print("Файлы для проверки не найдены.")
        sys.exit(0)

    all_syms = [s for f in files if (s := collect_symbols(f)) is not None]
    issues = find_issues(all_syms)

    if args.format == "json":
        data = [{"path": i.path, "line": i.line, "kind": i.kind, "name": i.name}
                for i in issues]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for issue in issues:
            print(issue)
        if issues:
            n = len(issues)
            f = len({i.path for i in issues})
            print(f"\nИтого: {n} {'проблема' if n == 1 else 'проблем'} в {f} файлах")
        else:
            print(f"Проверено {len(files)} файлов — проблем не найдено.")

    if issues and not args.warn_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
