"""
DSA (Data Structures & Algorithms) Utilities for Lumina IQ

This module contains optimized data structures for:
1. Caching - LRU Cache for embeddings/responses
2. Deduplication - Bloom Filter for chunk deduplication
3. Priority Queue - For job scheduling
4. Trie - For autocomplete suggestions

These can be integrated for production optimization.
"""

from typing import Dict, List, Any, Optional, Callable
from collections import OrderedDict
import hashlib
import asyncio


# =============================================================================
# 1. LRU CACHE - For Embedding/Response Caching
# =============================================================================


class LRUCache:
    """
    Least Recently Used Cache with O(1) operations.

    Perfect for caching:
    - Embedding results (avoid recomputing same chunks)
    - LLM responses (for identical queries)
    - Search results

    DSA: HashMap + Doubly Linked List (via OrderedDict)
    Time: O(1) get/put
    Space: O(capacity)

    Example:
        cache = LRUCache(capacity=1000)
        cache.put("chunk_hash", embedding_vector)
        result = cache.get("chunk_hash")  # Returns embedding or None
    """

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get item, moving to end (most recently used)"""
        if key not in self.cache:
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1
        return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        """Add item, evicting LRU if at capacity"""
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = value
            return

        if len(self.cache) >= self.capacity:
            # Remove oldest (first item)
            self.cache.popitem(last=False)

        self.cache[key] = value

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self.cache),
            "capacity": self.capacity,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2%}",
        }

    def clear(self) -> None:
        """Clear the cache"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0


class AsyncLRUCache(LRUCache):
    """Thread-safe async version of LRU Cache"""

    def __init__(self, capacity: int = 1000):
        super().__init__(capacity)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return super().get(key)

    async def put(self, key: str, value: Any) -> None:
        async with self._lock:
            super().put(key, value)


# =============================================================================
# 2. BLOOM FILTER - For Chunk Deduplication
# =============================================================================


class BloomFilter:
    """
    Probabilistic set membership with no false negatives.

    Perfect for:
    - Detecting duplicate chunks before embedding
    - Checking if document already processed
    - Quick membership tests

    DSA: Bit array + multiple hash functions
    Time: O(k) where k = number of hash functions
    Space: O(m) bits where m = array size

    False Positive Rate ≈ (1 - e^(-kn/m))^k

    Example:
        bloom = BloomFilter(expected_items=10000, fp_rate=0.01)
        bloom.add("chunk_text_here")
        if bloom.contains("chunk_text_here"):
            print("Probably seen this chunk!")
    """

    def __init__(self, expected_items: int = 10000, fp_rate: float = 0.01):
        import math

        # Calculate optimal size and hash functions
        self.size = self._optimal_size(expected_items, fp_rate)
        self.num_hashes = self._optimal_hashes(self.size, expected_items)

        # Bit array (using bytearray for efficiency)
        self.bit_array = bytearray((self.size + 7) // 8)
        self.count = 0

    def _optimal_size(self, n: int, p: float) -> int:
        """Calculate optimal bit array size"""
        import math

        return int(-n * math.log(p) / (math.log(2) ** 2))

    def _optimal_hashes(self, m: int, n: int) -> int:
        """Calculate optimal number of hash functions"""
        import math

        return max(1, int(m / n * math.log(2)))

    def _hashes(self, item: str) -> List[int]:
        """Generate k hash values for an item"""
        hashes = []
        for i in range(self.num_hashes):
            # Use SHA256 with different seeds
            h = hashlib.sha256(f"{i}:{item}".encode()).hexdigest()
            hashes.append(int(h, 16) % self.size)
        return hashes

    def add(self, item: str) -> None:
        """Add item to filter"""
        for pos in self._hashes(item):
            byte_pos = pos // 8
            bit_pos = pos % 8
            self.bit_array[byte_pos] |= 1 << bit_pos
        self.count += 1

    def contains(self, item: str) -> bool:
        """Check if item might be in filter (no false negatives)"""
        for pos in self._hashes(item):
            byte_pos = pos // 8
            bit_pos = pos % 8
            if not (self.bit_array[byte_pos] & (1 << bit_pos)):
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get filter statistics"""
        import math

        # Estimate current false positive rate
        bits_set = sum(bin(byte).count("1") for byte in self.bit_array)
        fill_rate = bits_set / self.size
        fp_rate = fill_rate**self.num_hashes

        return {
            "size_bits": self.size,
            "num_hashes": self.num_hashes,
            "items_added": self.count,
            "fill_rate": f"{fill_rate:.2%}",
            "estimated_fp_rate": f"{fp_rate:.4%}",
        }


# =============================================================================
# 3. PRIORITY QUEUE - For Job Scheduling
# =============================================================================


class PriorityQueue:
    """
    Min-heap priority queue for job scheduling.

    Perfect for:
    - Processing urgent documents first
    - Fair scheduling across users
    - Rate limit aware scheduling

    DSA: Binary Heap
    Time: O(log n) push/pop
    Space: O(n)

    Example:
        pq = PriorityQueue()
        pq.push(priority=1, item={"doc_id": "123", "user": "A"})
        pq.push(priority=3, item={"doc_id": "456", "user": "B"})
        next_job = pq.pop()  # Returns doc 123 (lower priority = higher urgency)
    """

    def __init__(self):
        import heapq

        self._heap: List[tuple] = []
        self._counter = 0  # Tie-breaker for equal priorities

    def push(self, priority: int, item: Any) -> None:
        """Add item with priority (lower = more urgent)"""
        import heapq

        heapq.heappush(self._heap, (priority, self._counter, item))
        self._counter += 1

    def pop(self) -> Optional[Any]:
        """Remove and return highest priority (lowest number) item"""
        import heapq

        if not self._heap:
            return None
        _, _, item = heapq.heappop(self._heap)
        return item

    def peek(self) -> Optional[Any]:
        """View highest priority item without removing"""
        if not self._heap:
            return None
        return self._heap[0][2]

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0


class AsyncPriorityQueue(PriorityQueue):
    """Thread-safe async priority queue"""

    def __init__(self):
        super().__init__()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    async def push(self, priority: int, item: Any) -> None:
        async with self._lock:
            super().push(priority, item)
            self._not_empty.set()

    async def pop(self, timeout: Optional[float] = None) -> Optional[Any]:
        """Pop with optional timeout"""
        try:
            if timeout:
                await asyncio.wait_for(self._not_empty.wait(), timeout)
            else:
                await self._not_empty.wait()
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            item = super().pop()
            if self.is_empty():
                self._not_empty.clear()
            return item


# =============================================================================
# 4. TRIE - For Autocomplete/Topic Suggestions
# =============================================================================


class TrieNode:
    """Node in a Trie"""

    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end: bool = False
        self.data: Any = None  # Store additional data at leaf
        self.count: int = 0  # Frequency for ranking


class Trie:
    """
    Prefix tree for fast autocomplete suggestions.

    Perfect for:
    - Topic autocomplete
    - Search query suggestions
    - Document name completion

    DSA: Trie (Prefix Tree)
    Time: O(m) insert/search where m = word length
    Space: O(alphabet_size * m * n) for n words

    Example:
        trie = Trie()
        trie.insert("machine learning", data={"count": 10})
        trie.insert("machine vision", data={"count": 5})
        suggestions = trie.autocomplete("mach")  # Returns both
    """

    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, data: Any = None) -> None:
        """Insert word into trie"""
        word = word.lower()
        node = self.root

        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.is_end = True
        node.data = data
        node.count += 1

    def search(self, word: str) -> Optional[Any]:
        """Search for exact word"""
        word = word.lower()
        node = self._find_node(word)

        if node and node.is_end:
            return node.data
        return None

    def starts_with(self, prefix: str) -> bool:
        """Check if any word starts with prefix"""
        return self._find_node(prefix.lower()) is not None

    def autocomplete(self, prefix: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get autocomplete suggestions for prefix"""
        prefix = prefix.lower()
        node = self._find_node(prefix)

        if not node:
            return []

        # DFS to find all words with this prefix
        results = []
        self._dfs_collect(node, prefix, results)

        # Sort by count (frequency) and return top results
        results.sort(key=lambda x: -x["count"])
        return results[:limit]

    def _find_node(self, prefix: str) -> Optional[TrieNode]:
        """Find node for given prefix"""
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def _dfs_collect(self, node: TrieNode, current: str, results: List) -> None:
        """DFS to collect all words from node"""
        if node.is_end:
            results.append({"word": current, "data": node.data, "count": node.count})

        for char, child in node.children.items():
            self._dfs_collect(child, current + char, results)


# =============================================================================
# 5. CONSISTENT HASHING - For Distributed Load Balancing
# =============================================================================


class ConsistentHash:
    """
    Consistent hashing for distributing load across workers.

    Perfect for:
    - Distributing embedding jobs across multiple workers
    - Load balancing in multi-instance deployments
    - Cache sharding

    DSA: Hash Ring with Virtual Nodes
    Time: O(log n) for lookup
    Space: O(n * replicas)

    Example:
        ch = ConsistentHash(["worker1", "worker2", "worker3"])
        worker = ch.get_node("document_id_123")  # Consistently maps to same worker
    """

    def __init__(self, nodes: List[str] = None, replicas: int = 100):
        import bisect

        self.replicas = replicas
        self.ring: Dict[int, str] = {}
        self.sorted_keys: List[int] = []

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        """Hash function"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str) -> None:
        """Add a node to the ring"""
        import bisect

        for i in range(self.replicas):
            virtual_key = self._hash(f"{node}:{i}")
            self.ring[virtual_key] = node
            bisect.insort(self.sorted_keys, virtual_key)

    def remove_node(self, node: str) -> None:
        """Remove a node from the ring"""
        for i in range(self.replicas):
            virtual_key = self._hash(f"{node}:{i}")
            if virtual_key in self.ring:
                del self.ring[virtual_key]
                self.sorted_keys.remove(virtual_key)

    def get_node(self, key: str) -> Optional[str]:
        """Get the node responsible for this key"""
        import bisect

        if not self.ring:
            return None

        hash_key = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, hash_key)

        if idx == len(self.sorted_keys):
            idx = 0

        return self.ring[self.sorted_keys[idx]]


# =============================================================================
# UTILITY: Hash function for chunks
# =============================================================================


def hash_chunk(text: str) -> str:
    """
    Create a hash of a text chunk for caching/deduplication.

    Uses SHA256 truncated to 16 chars for reasonable uniqueness
    while being storage efficient.
    """
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_embedding_cache: Optional[AsyncLRUCache] = None
_chunk_bloom: Optional[BloomFilter] = None
_topic_trie: Optional[Trie] = None


def get_embedding_cache(capacity: int = 5000) -> AsyncLRUCache:
    """Get global embedding cache"""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = AsyncLRUCache(capacity)
    return _embedding_cache


def get_chunk_bloom(expected_items: int = 100000) -> BloomFilter:
    """Get global chunk deduplication bloom filter"""
    global _chunk_bloom
    if _chunk_bloom is None:
        _chunk_bloom = BloomFilter(expected_items=expected_items, fp_rate=0.001)
    return _chunk_bloom


def get_topic_trie() -> Trie:
    """Get global topic autocomplete trie"""
    global _topic_trie
    if _topic_trie is None:
        _topic_trie = Trie()
    return _topic_trie
