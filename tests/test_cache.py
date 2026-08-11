import time
import unittest

from backend.cache import TTLCache, query_cache, ttl_cached


class TTLCacheTests(unittest.TestCase):
    def tearDown(self):
        query_cache.clear()

    def test_cache_returns_defensive_copies(self):
        cache = TTLCache()
        original = {"players": [{"name": "A"}]}
        cache.set(("season",), original, 10)

        found, cached = cache.get(("season",))
        cached["players"][0]["name"] = "changed"
        found_again, cached_again = cache.get(("season",))

        self.assertTrue(found and found_again)
        self.assertEqual(cached_again["players"][0]["name"], "A")

    def test_expired_entry_is_a_miss(self):
        cache = TTLCache()
        cache.set(("player",), [1], 0.01)
        time.sleep(0.02)
        self.assertEqual(cache.get(("player",)), (False, None))

    def test_decorator_keys_by_arguments(self):
        calls = []

        @ttl_cached(10)
        def load(season):
            calls.append(season)
            return {"season": season}

        self.assertEqual(load("2025"), {"season": "2025"})
        self.assertEqual(load("2025"), {"season": "2025"})
        self.assertEqual(load("2026"), {"season": "2026"})
        self.assertEqual(calls, ["2025", "2026"])


if __name__ == "__main__":
    unittest.main()
