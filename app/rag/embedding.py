import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]")


class HashingEmbedder:
    def __init__(
        self,
        dimensions: int = 64,
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")

        self.dimensions = dimensions

    def embed(
        self,
        text: str,
    ) -> tuple[float, ...]:
        values = [0.0] * self.dimensions

        tokens = TOKEN_PATTERN.findall(text.lower())

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()

            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 == 0 else -1.0

            values[index] += sign

        norm = math.sqrt(sum(value * value for value in values))

        if norm == 0.0:
            return tuple(values)

        return tuple(value / norm for value in values)
