"""Generates the SUPPORTED_DISTRIBUTIONS constant from the sweeps schema."""

import collections
import json
import ssl
import typing
import urllib.request

SCHEMA_URL = (
    "https://raw.githubusercontent.com/wandb/sweeps/master/src/sweeps/config/schema.json"
)

ORDER_HINTS = {
    "a": 0,
    "b": 1,
    "min": 0,
    "max": 1,
    "mu": 0,
    "sigma": 1,
    "q": 2,
    "value": 0,
    "values": 0,
    "probabilities": 1,
}


def load_schema() -> dict[str, typing.Any]:
    context = ssl.create_default_context()
    with urllib.request.urlopen(SCHEMA_URL, context=context) as response:
        return json.load(response)


def resolve_ref(
    ref: str,
    schema: dict[str, typing.Any],
) -> typing.Any:
    if not ref.startswith("#/"):
        return None
    target: typing.Any = schema
    for part in ref[2:].split("/"):
        clean = part.replace("~1", "/").replace("~0", "~")
        target = target[clean]
    return target


def record_properties(
    mapping: dict[str, dict[str, tuple[int, int]]],
    dist: str,
    keys: list[str],
) -> None:
    slots = mapping[dist]
    for key in keys:
        if key == "distribution":
            continue
        if key not in slots:
            slots[key] = (ORDER_HINTS.get(key, 5), len(slots))


def walk(
    node: typing.Any,
    schema: dict[str, typing.Any],
    mapping: dict[str, dict[str, tuple[int, int]]],
    seen: set[int],
) -> None:
    if isinstance(node, dict):
        node_id = id(node)
        if node_id in seen:
            return
        seen.add(node_id)
        ref = node.get("$ref")
        if isinstance(ref, str):
            resolved = resolve_ref(ref, schema)
            if resolved is not None:
                walk(resolved, schema, mapping, seen)
        properties = node.get("properties")
        if isinstance(properties, dict):
            distribution_spec = properties.get("distribution")
            distributions: list[str] = []
            if isinstance(distribution_spec, dict):
                enum_values = distribution_spec.get("enum")
                if isinstance(enum_values, list):
                    distributions.extend(enum_values)
                const_value = distribution_spec.get("const")
                if const_value is not None:
                    distributions.append(const_value)
            keys = list(properties.keys())
            for dist in distributions:
                record_properties(mapping, dist, keys)

        for combinator in ("anyOf", "allOf", "oneOf"):
            options = node.get(combinator)
            if isinstance(options, list):
                for option in options:
                    walk(option, schema, mapping, seen)
    elif isinstance(node, list):
        for item in node:
            walk(item, schema, mapping, seen)


def sorted_keys(
    raw: dict[str, tuple[int, int]],
) -> list[str]:
    return [name for name, _ in sorted(raw.items(), key=lambda item: (item[1][0], item[0]))]


def main() -> None:
    schema = load_schema()
    mapping: dict[str, dict[str, tuple[int, int]]] = collections.defaultdict(dict)
    seen: set[int] = set()
    for definition in schema.get("definitions", {}).values():
        walk(definition, schema, mapping, seen)
    print("SUPPORTED_DISTRIBUTIONS = {")
    for dist in sorted(mapping):
        keys = ", ".join(f"\"{key}\"" for key in sorted_keys(mapping[dist]))
        print(f"    \"{dist}\": [{keys}],")
    print("}")


if __name__ == "__main__":
    main()
