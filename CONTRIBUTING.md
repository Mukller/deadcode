# Contributing

## Как помочь

Принимаю PR с:
- Новыми типами анализа (декораторы, `__all__`, dataclass поля)
- Улучшением форматов вывода (SARIF, GitHub annotations)
- Ускорением на больших кодовых базах
- Исправлением false positive

## Как делать

```bash
git clone https://github.com/Mukller/deadcode
cd deadcode
pip install -e ".[dev]"
deadcode .
```

## Стиль

- `ruff format` и `ruff check`
- Только стандартная библиотека + `ast`
- Анализ через visitor-паттерн (`ast.NodeVisitor`)
