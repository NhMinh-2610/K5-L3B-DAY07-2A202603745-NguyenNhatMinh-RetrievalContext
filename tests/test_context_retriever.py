import unittest
from src.context_retriever import make_groups


class NeighborTests(unittest.TestCase):
    def test_groups_complete_broken_sentences_without_crossing_scope(self):
        chunks = [{"id": str(i), "source_id": "s", "source": "url", "page": page, "text": text,
                   "metadata": {"section": section, "page_char_start": i*10}}
                  for i, (page, section, text) in enumerate([(1,"1","Before"),(1,"1","Subject"),
                                                            (1,"1","Continuation"),(1,"2","Other section"),
                                                            (2,"1","Other page")])]
        group = make_groups(chunks)["1"]
        self.assertEqual(group["text"], "Before\nSubject\nContinuation")
        self.assertEqual(group["metadata"]["source_chunk_ids"], ["0", "1", "2"])
        self.assertNotIn("Other", group["text"])

    def test_group_ids_follow_content_members_and_are_stable(self):
        chunk = {"id":"a", "source_id":"s", "page":1,"text":"Evidence","metadata":{}}
        self.assertEqual(make_groups([chunk])["a"]["id"], make_groups([chunk])["a"]["id"])

    def test_unbounded_expansion_is_rejected(self):
        with self.assertRaises(ValueError):
            make_groups([], radius=10)
