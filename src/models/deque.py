
from typing import Generic, TypeVar, Iterable, Iterator, overload

T = TypeVar("T")


class _Node(Generic[T]):
    """Một nút trong danh sách liên kết kép."""

    def __init__(self, value: T) -> None:
        self.value = value
        self.prev: _Node[T] | None = None
        self.next: _Node[T] | None = None


class Deque(Generic[T]):
    """Deque tự cài đặt bằng danh sách liên kết kép."""

    def __init__(self, values: Iterable[T] = ()) -> None:
        self._head: _Node[T] | None = None
        self._tail: _Node[T] | None = None
        self._size = 0

        for value in values:
            self.append(value)

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[T]:
        current = self._head
        while current is not None:
            yield current.value
            current = current.next

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[T, ...]: ...

    def __getitem__(self, index: int | slice) -> T | tuple[T, ...]:
        if isinstance(index, slice):
            return tuple(self)[index]

        if index < 0:
            index += self._size

        if index < 0 or index >= self._size:
            raise IndexError("Deque index out of range")

        # Duyệt từ đầu hoặc cuối, tùy vị trí gần hơn.
        if index <= self._size // 2:
            current = self._head
            for _ in range(index):
                current = current.next  # type: ignore[union-attr]
        else:
            current = self._tail
            for _ in range(self._size - 1 - index):
                current = current.prev  # type: ignore[union-attr]

        return current.value  # type: ignore[union-attr]

    def append(self, value: T) -> None:
        """Thêm phần tử vào cuối."""
        node = _Node(value)

        if self._tail is None:
            self._head = self._tail = node
        else:
            node.prev = self._tail
            self._tail.next = node
            self._tail = node

        self._size += 1

    def appendleft(self, value: T) -> None:
        """Thêm phần tử vào đầu."""
        node = _Node(value)

        if self._head is None:
            self._head = self._tail = node
        else:
            node.next = self._head
            self._head.prev = node
            self._head = node

        self._size += 1

    def pop(self) -> T:
        """Xóa và trả về phần tử cuối."""
        if self._tail is None:
            raise IndexError("pop from an empty deque")

        node = self._tail
        self._tail = node.prev

        if self._tail is None:
            self._head = None
        else:
            self._tail.next = None

        self._size -= 1
        return node.value

    def popleft(self) -> T:
        """Xóa và trả về phần tử đầu."""
        if self._head is None:
            raise IndexError("pop from an empty deque")

        node = self._head
        self._head = node.next

        if self._head is None:
            self._tail = None
        else:
            self._head.prev = None

        self._size -= 1
        return node.value

    def clear(self) -> None:
        """Xóa toàn bộ phần tử."""
        self._head = None
        self._tail = None
        self._size = 0
