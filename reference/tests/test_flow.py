"""Tests for snail_labyrinth.flow -- the generic max-flow primitive MG-7's
vertex-disjoint-route check is built on. These tests are about the flow
primitive itself, on hand-built graphs; MG-7-specific behaviour (cell
exemption, direction-aware node splitting) is covered in test_routes.py.
"""

import unittest

from snail_labyrinth.flow import FlowNetwork

SOURCE = "S"
SINK = "T"


class FlowNetworkTests(unittest.TestCase):
    def test_two_parallel_disjoint_paths_give_flow_two(self):
        net = FlowNetwork()
        net.add_edge(SOURCE, "A", 1)
        net.add_edge("A", SINK, 1)
        net.add_edge(SOURCE, "B", 1)
        net.add_edge("B", SINK, 1)
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 2)

    def test_single_path_gives_flow_one_even_when_target_is_two(self):
        """The target is a ceiling, not a guarantee -- a network with a true
        max-flow of 1 must report 1, not silently claim 2."""
        net = FlowNetwork()
        net.add_edge(SOURCE, "X", 1)
        net.add_edge("X", SINK, 1)
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 1)

    def test_no_path_gives_flow_zero(self):
        net = FlowNetwork()
        net.add_edge(SOURCE, "X", 1)
        # X is never connected to SINK.
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 0)

    def test_shared_bottleneck_caps_flow_even_with_multiple_predecessors(self):
        """Two distinct predecessor edges both feeding into a single
        capacity-1 bottleneck must still cap total flow at 1 -- this is the
        exact shape MG-7's cell-arrival bottleneck relies on."""
        net = FlowNetwork()
        net.add_edge(SOURCE, "P1", 1)
        net.add_edge(SOURCE, "P2", 1)
        net.add_edge("P1", "BOTTLENECK_IN", 1)
        net.add_edge("P2", "BOTTLENECK_IN", 1)
        net.add_edge("BOTTLENECK_IN", "BOTTLENECK_OUT", 1)  # the cap
        net.add_edge("BOTTLENECK_OUT", SINK, 1)
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 1)

    def test_diamond_with_shared_middle_cell_caps_at_one(self):
        """SOURCE -> M -> SINK is the only route; even though M has two
        *edges* in (from two different upstream branches merged before M),
        the true max-flow is 1, not 2, because there is only one path to
        SINK in the first place."""
        net = FlowNetwork()
        net.add_edge(SOURCE, "A", 1)
        net.add_edge(SOURCE, "B", 1)
        net.add_edge("A", "M", 1)
        net.add_edge("B", "M", 1)
        net.add_edge("M", SINK, 1)
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 1)

    def test_add_edge_accumulates_capacity_between_the_same_pair(self):
        net = FlowNetwork()
        net.add_edge(SOURCE, "A", 1)
        net.add_edge(SOURCE, "A", 1)  # same pair again
        net.add_edge("A", SINK, 2)
        self.assertEqual(net.max_flow_at_least(SOURCE, SINK, 2), 2)

    def test_source_equals_sink_is_trivially_satisfied(self):
        net = FlowNetwork()
        # No edges needed; source==sink is a degenerate case that must not
        # loop, raise, or attempt to compute a bottleneck over zero edges.
        self.assertEqual(net.max_flow_at_least(SOURCE, SOURCE, 2), 2)

    def test_negative_capacity_rejected(self):
        net = FlowNetwork()
        with self.assertRaises(ValueError):
            net.add_edge(SOURCE, SINK, -1)


if __name__ == "__main__":
    unittest.main()
