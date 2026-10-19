"""Tests for snail_labyrinth.geometry: GE-1 .. GE-8.

Every test cites the spec rule(s) it verifies in its docstring or name.
"""

import unittest

from snail_labyrinth.geometry import (
    apron_cells,
    hub_cells,
    place_fixed_geometry,
    rho,
    spawn_offset,
    spawns,
    start_pad_inward_neighbour,
    start_pad_mask,
)
from snail_labyrinth.tiles import Board, GridPos, TileFlags
from snail_labyrinth.transit import TransitGraph

PRESET_SIZES = (8, 12, 16, 20, 24)


class HubTests(unittest.TestCase):
    """GE-1: the Hub cell set."""

    # From the spec's section 3.5 defaults table.
    EXPECTED_HUB_TOP_LEFT = {8: (3, 3), 12: (5, 5), 16: (7, 7), 20: (9, 9), 24: (11, 11)}

    def test_GE1_hub_matches_defaults_table_for_every_preset_size(self):
        for n, (tx, ty) in self.EXPECTED_HUB_TOP_LEFT.items():
            expected = {
                GridPos(tx, ty),
                GridPos(tx + 1, ty),
                GridPos(tx, ty + 1),
                GridPos(tx + 1, ty + 1),
            }
            self.assertEqual(set(hub_cells(n)), expected, f"N={n}")

    def test_GE1_hub_has_4_cells_for_even_n_and_1_for_odd_n(self):
        for n in PRESET_SIZES:
            self.assertEqual(len(hub_cells(n)), 4, f"N={n}")
        self.assertEqual(len(hub_cells(9)), 1)
        self.assertEqual(hub_cells(9), [GridPos(4, 4)])


class ApronTests(unittest.TestCase):
    """GE-1 / GE-3: orthogonal neighbours of HUB, outside HUB."""

    def test_GE1_apron_has_8_cells_for_even_n(self):
        for n in PRESET_SIZES:
            self.assertEqual(len(apron_cells(n)), 8, f"N={n}")

    def test_GE1_apron_has_4_cells_for_odd_n(self):
        self.assertEqual(len(apron_cells(9)), 4)

    def test_GE1_apron_is_disjoint_from_hub(self):
        for n in PRESET_SIZES:
            self.assertTrue(set(apron_cells(n)).isdisjoint(hub_cells(n)), f"N={n}")

    def test_GE1_apron_cells_are_orthogonally_adjacent_to_some_hub_cell(self):
        for n in PRESET_SIZES:
            hub = set(hub_cells(n))
            for cell in apron_cells(n):
                neighbours = {
                    GridPos(cell.x - 1, cell.y),
                    GridPos(cell.x + 1, cell.y),
                    GridPos(cell.x, cell.y - 1),
                    GridPos(cell.x, cell.y + 1),
                }
                self.assertTrue(neighbours & hub, f"N={n} apron cell {cell}")


class SpawnOffsetTests(unittest.TestCase):
    """GE-5: `m = clamp(round(N/4), 1, N/2 - 2)`."""

    EXPECTED_M = {8: 2, 12: 3, 16: 4, 20: 5, 24: 6}

    def test_GE5_m_matches_defaults_table(self):
        for n, expected_m in self.EXPECTED_M.items():
            self.assertEqual(spawn_offset(n), expected_m, f"N={n}")


class SpawnPositionTests(unittest.TestCase):
    """GE-5: the four spawns S0..S3, one per side."""

    def test_GE5_spawn_formulas(self):
        for n in PRESET_SIZES:
            m = spawn_offset(n)
            s0, s1, s2, s3 = spawns(n)
            self.assertEqual(s0, GridPos(m, 0), f"N={n}")
            self.assertEqual(s1, GridPos(n - 1, m), f"N={n}")
            self.assertEqual(s2, GridPos(n - 1 - m, n - 1), f"N={n}")
            self.assertEqual(s3, GridPos(0, n - 1 - m), f"N={n}")

    def test_GE5_all_four_spawns_distinct(self):
        for n in PRESET_SIZES:
            self.assertEqual(len(set(spawns(n))), 4, f"N={n}")


class SymmetryTests(unittest.TestCase):
    """GE-6: the spawn set is the single C4 orbit of (m, 0)."""

    def test_GE6_rho_maps_each_spawn_to_the_next_slot(self):
        """rho: k -> k+1 (mod 4), for every preset size."""
        for n in PRESET_SIZES:
            s = spawns(n)
            for k in range(4):
                self.assertEqual(rho(s[k], n), s[(k + 1) % 4], f"N={n} k={k}")

    def test_GE6_rho_has_order_4_and_orbit_is_exactly_the_spawn_set(self):
        for n in PRESET_SIZES:
            s0 = spawns(n)[0]
            cur = s0
            orbit = [cur]
            for _ in range(3):
                cur = rho(cur, n)
                orbit.append(cur)
            self.assertEqual(rho(cur, n), s0, f"N={n}: rho^4 != identity")
            self.assertEqual(set(orbit), set(spawns(n)), f"N={n}")
            self.assertEqual(len(set(orbit)), 4, f"N={n}: orbit must be simply transitive")

    def test_GE7_spawns_are_antipodal_in_pairs(self):
        """S0/S2 and S1/S3 are antipodal: point-symmetric about the board
        centre, i.e. S0 + S2 == S1 + S3 == (N-1, N-1)."""
        for n in PRESET_SIZES:
            s0, s1, s2, s3 = spawns(n)
            expected = GridPos(n - 1, n - 1)
            self.assertEqual(GridPos(s0.x + s2.x, s0.y + s2.y), expected, f"N={n}")
            self.assertEqual(GridPos(s1.x + s3.x, s1.y + s3.y), expected, f"N={n}")


class StartPadTests(unittest.TestCase):
    """GE-8: Start Pad mask and the rock-protected inward neighbour."""

    # Cross-checked against TM-3's own TEE table: masks 7/14/13/11 are
    # documented there as missing W/N/E/S respectively.
    EXPECTED_MASK = {0: 14, 1: 13, 2: 11, 3: 7}  # missing N, E, S, W

    def test_GE8_start_pad_is_a_tee_missing_only_the_outward_direction(self):
        for k, expected in self.EXPECTED_MASK.items():
            self.assertEqual(start_pad_mask(k), expected, f"k={k}")

    def test_GE8_start_pad_has_three_legal_first_moves(self):
        for k in range(4):
            self.assertEqual(bin(start_pad_mask(k)).count("1"), 3, f"k={k}")

    def test_GE8_inward_neighbour_is_one_step_into_the_board(self):
        for n in PRESET_SIZES:
            s = spawns(n)
            expected = [
                GridPos(s[0].x, s[0].y + 1),  # S0 (north side): inward is south
                GridPos(s[1].x - 1, s[1].y),  # S1 (east side): inward is west
                GridPos(s[2].x, s[2].y - 1),  # S2 (south side): inward is north
                GridPos(s[3].x + 1, s[3].y),  # S3 (west side): inward is east
            ]
            for k in range(4):
                self.assertEqual(
                    start_pad_inward_neighbour(n, k), expected[k], f"N={n} k={k}"
                )


class PlaceFixedGeometryTests(unittest.TestCase):
    """MG-5: Hub forced to mask 15 + FINISH_LOCKED, Start Pads forced to
    T-Junction + SPAWN_PAD, before any other placement."""

    def test_hub_cells_are_forced_to_mask_15_and_flagged(self):
        board = Board(16)
        place_fixed_geometry(board)
        for cell in hub_cells(16):
            self.assertEqual(board.mask_at(cell), 15)
            self.assertTrue(board.flags_at(cell) & TileFlags.FINISH_LOCKED)

    def test_start_pads_are_forced_and_flagged(self):
        board = Board(16)
        place_fixed_geometry(board)
        for k, pad in enumerate(spawns(16)):
            self.assertEqual(board.mask_at(pad), start_pad_mask(k))
            self.assertTrue(board.flags_at(pad) & TileFlags.SPAWN_PAD)

    def test_inward_neighbours_are_rock_protected(self):
        board = Board(16)
        place_fixed_geometry(board)
        for k in range(4):
            cell = start_pad_inward_neighbour(16, k)
            self.assertTrue(board.flags_at(cell) & TileFlags.ROCK_PROTECTED)


def _carve(board: Board, cells_to_masks: dict) -> None:
    for (x, y), m in cells_to_masks.items():
        board.set_mask(GridPos(x, y), m)


class GeometryReachabilityIntegrationTests(unittest.TestCase):
    """Sanity-check the geometry against TransitGraph before the map
    generator (MG-*) exists to build a full board automatically: a
    hand-carved corridor from each N=8 spawn to the Hub must be solvable in
    G_T, and with nothing but the fixed geometry placed (no corridors at
    all) none of the four spawns can reach the Hub.
    """

    N = 8

    # One explicit route per spawn, hand-carved to connect S[k] to a
    # specific Hub cell through the matching Apron cell. Each mask is
    # chosen so TM-8's mutual-openness rule holds at every step.
    CORRIDORS = {
        (2, 1): 5,  # N|S: straight, below S0
        (2, 2): 5,  # N|S: straight
        (2, 3): 3,  # N|E: elbow into Hub (3,3) via its West Apron cell
        (6, 2): 10,  # E|W: straight, left of S1
        (5, 2): 6,  # E|S: elbow
        (5, 3): 9,  # N|W: elbow into Hub (4,3) via its East Apron cell
        (5, 6): 5,  # N|S: straight, above S2
        (5, 5): 12,  # S|W: elbow
        (4, 5): 3,  # N|E: elbow into Hub (4,4) via its South Apron cell
        (1, 5): 10,  # E|W: straight, right of S3
        (2, 5): 9,  # N|W: elbow
        (2, 4): 6,  # E|S: elbow into Hub (3,4) via its West Apron cell
    }

    def test_hand_carved_corridors_reach_the_hub_from_every_spawn(self):
        board = Board(self.N)
        place_fixed_geometry(board)
        _carve(board, self.CORRIDORS)
        graph = TransitGraph(board)
        hub = hub_cells(self.N)
        for k, pad in enumerate(spawns(self.N)):
            self.assertTrue(
                graph.reachable_to_hub(pad, hub), f"spawn S{k} ({pad}) should reach the Hub"
            )

    def test_fixed_geometry_alone_guarantees_nothing(self):
        """Geometry placement is not the map generator: with no interior
        corridors carved, no spawn should reach the Hub (confirms the
        reachability above is coming from the hand-carved path, not from
        some accidental artefact of the geometry functions)."""
        board = Board(self.N)
        place_fixed_geometry(board)
        graph = TransitGraph(board)
        hub = hub_cells(self.N)
        for k, pad in enumerate(spawns(self.N)):
            self.assertFalse(
                graph.reachable_to_hub(pad, hub), f"spawn S{k} ({pad}) should NOT reach the Hub"
            )


if __name__ == "__main__":
    unittest.main()
