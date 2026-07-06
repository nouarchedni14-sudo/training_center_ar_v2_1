from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


class TraineesMigrationGraphTests(TestCase):
    """Sanity checks to keep the trainees migration graph healthy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = MigrationLoader(connection, ignore_no_migrations=True)

    def test_trainees_migrations_have_no_conflicts(self):
        conflicts = self.loader.detect_conflicts()
        self.assertNotIn("trainees", conflicts, f"Unexpected trainees migration conflicts: {conflicts.get('trainees')}")

    def test_trainees_leaf_node_is_the_expected_merge(self):
        leaf_nodes = [node for node in self.loader.graph.leaf_nodes() if node[0] == "trainees"]
        self.assertEqual(
            leaf_nodes,
            [("trainees", "0042_merge_20260409_1444")],
            f"Unexpected trainees leaf nodes: {leaf_nodes}",
        )

    def test_forward_plan_reaches_known_merge_points(self):
        plan = self.loader.graph.forwards_plan(("trainees", "0042_merge_20260409_1444"))
        plan_set = set(plan)
        expected_nodes = {
            ("trainees", "0015_merge_20260211_2045"),
            ("trainees", "0017_merge_20260215_1525"),
            ("trainees", "0019_merge_20260218_1325"),
            ("trainees", "0027_merge_20260319_0214"),
            ("trainees", "0041_cleanup_access_and_delete_legacy_log"),
            ("trainees", "0042_merge_20260409_1444"),
        }
        self.assertTrue(expected_nodes.issubset(plan_set), "Known merge points are missing from the trainees migration plan.")
