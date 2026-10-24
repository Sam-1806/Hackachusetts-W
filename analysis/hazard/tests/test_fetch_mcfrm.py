import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "fetch_mcfrm.py"
SPEC = importlib.util.spec_from_file_location("fetch_mcfrm", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ring = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]

    def test_clip_ring_to_bbox(self) -> None:
        clipped = MODULE.clip_ring_to_bbox(self.ring, (1, 1, 3, 3))
        self.assertEqual(clipped[0], clipped[-1])
        self.assertAlmostEqual(abs(MODULE.signed_area(clipped)), 4.0)

    def test_line_polygon_overlap(self) -> None:
        self.assertTrue(MODULE.line_intersects_polygon([[-1, 2], [5, 2]], [self.ring]))
        self.assertFalse(MODULE.line_intersects_polygon([[-2, -2], [-1, -1]], [self.ring]))

    def test_hole_is_not_flooded(self) -> None:
        hole = [[1, 1], [1, 3], [3, 3], [3, 1], [1, 1]]
        self.assertTrue(MODULE.point_in_polygon([0.5, 0.5], [self.ring, hole]))
        self.assertFalse(MODULE.point_in_polygon([2, 2], [self.ring, hole]))

    def test_exposure_retains_unknown_depth_and_passability(self) -> None:
        extent = {
            "features": [{"geometry": {"type": "Polygon", "coordinates": [self.ring]}}]
        }
        roads = {
            "graph_version": "test-v1",
            "features": [
                {
                    "properties": {"road_id": "r1"},
                    "geometry": {"type": "LineString", "coordinates": [[-1, 2], [5, 2]]},
                }
            ],
        }
        result = MODULE.build_exposure(extent, roads, "test fixture")
        road = result["affected_roads"][0]
        self.assertEqual(road["exposure"], "exposed")
        self.assertIsNone(road["depth_m"])
        self.assertEqual(road["passability"], "unknown")

    def test_road_manifest_wrapper_is_supported(self) -> None:
        extent = {
            "features": [{"geometry": {"type": "Polygon", "coordinates": [self.ring]}}]
        }
        manifest = {
            "graph_version": "canonical-test-v1",
            "roads": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {"road_id": "canonical:r1"},
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[-1, 2], [5, 2]],
                        },
                    }
                ],
            },
        }
        result = MODULE.build_exposure(extent, manifest, "test manifest")
        self.assertEqual(result["graph_version"], "canonical-test-v1")
        self.assertEqual(result["affected_roads"][0]["road_id"], "canonical:r1")


if __name__ == "__main__":
    unittest.main()
