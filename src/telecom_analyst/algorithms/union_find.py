"""Union-find com compressão de caminho e união por tamanho."""

from collections import defaultdict
from collections.abc import Hashable, Iterable


class UnionFind[T: Hashable]:
    """Conjuntos disjuntos. Cada operação custa tempo amortizado quase constante."""

    def __init__(self, items: Iterable[T] = ()) -> None:
        self._parent: dict[T, T] = {}
        self._size: dict[T, int] = {}
        for item in items:
            self.add(item)

    def __contains__(self, item: T) -> bool:
        return item in self._parent

    def __len__(self) -> int:
        return len(self._parent)

    def add(self, item: T) -> None:
        if item not in self._parent:
            self._parent[item] = item
            self._size[item] = 1

    def find(self, item: T) -> T:
        """Devolve o representante do conjunto e aponta o caminho direto para ele."""
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        # Iterativo de propósito: grafos reais formam cadeias maiores que o limite de recursão.
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, first: T, second: T) -> bool:
        """Une dois conjuntos, criando os itens novos. Devolve False se já estavam juntos."""
        self.add(first)
        self.add(second)
        first_root, second_root = self.find(first), self.find(second)
        if first_root == second_root:
            return False
        if self._size[first_root] < self._size[second_root]:
            first_root, second_root = second_root, first_root
        self._parent[second_root] = first_root
        self._size[first_root] += self._size[second_root]
        return True

    def connected(self, first: T, second: T) -> bool:
        return self.find(first) == self.find(second)

    def groups(self) -> list[set[T]]:
        members: defaultdict[T, set[T]] = defaultdict(set)
        for item in self._parent:
            members[self.find(item)].add(item)
        return list(members.values())
