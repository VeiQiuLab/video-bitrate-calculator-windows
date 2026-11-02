"""运行: python -m unittest -v test_bitrate_core"""
import os
from pathlib import Path
import struct
import tempfile
import unittest

import bitrate_core as bc


class TestCalculator(unittest.TestCase):
    def test_exact_budget(self):
        b = bc.calculate("9:38", "180", "170", "128", "1.5")
        self.assertEqual(b.seconds, 578)
        self.assertEqual(b.video_kbps, 2189)
        self.assertLessEqual(b.estimated_mb, 170)
        self.assertGreater(b.estimated_mb, 169.9)

    def test_multiple_formats(self):
        self.assertEqual(bc.parse_duration("1:09:38"), 4178)
        self.assertEqual(bc.parse_duration("9：38"), 578)
        self.assertEqual(bc.parse_duration("10:30.5"), 630.5)
        self.assertEqual(bc.parse_duration("35"), 35)
        self.assertEqual(bc.format_duration(4178), "1:09:38")

    def test_bad_inputs(self):
        for d in ("", "0", "-10", "1:90", "1:2:99", "NaN", "1:2:3:4"):
            with self.subTest(d=d), self.assertRaises(ValueError):
                bc.parse_duration(d)
        with self.assertRaises(ValueError):
            bc.calculate("9:38", "180", "180", "128", "1.5")
        with self.assertRaises(ValueError):
            bc.calculate("9:38", "180", "170", "128", "NaN")
        with self.assertRaises(ValueError):
            bc.calculate("100:00:00", "180", "170", "128", "1.5")

    def test_codec_bitrates_match(self):
        b = bc.calculate("9:38", "180", "170", "128", "1.5")
        for codec in bc.CODECS:
            p = bc.make_preset(codec, b, "综合（一般游戏）")
            self.assertIn(f"{b.video_kbps} Kbps", p)
            self.assertIn("Average Bitrate", p)
            self.assertIn("2-Pass", p)
            self.assertIn("编码器预设", p)
            self.assertIn("音频：AAC", p)

    def test_long_duration_warns(self):
        b = bc.calculate("60:00", "180", "170", "64", "1.5")
        for codec in bc.CODECS:
            rec, warning = bc.recommend(codec, b.video_kbps)
            self.assertTrue(rec)
            self.assertTrue(warning)

    def test_file_duration_mp4(self):
        def box(typ, payload):
            return struct.pack(">I4s", len(payload)+8, typ) + payload
        # mvhd V0: 4 byte version+flags, 4+4 timestamps, 4 scale, 4 duration.
        mvhd = box(b"mvhd", b"\0"*12 + struct.pack(">II", 1000, 578000))
        mp4 = box(b"ftyp", b"isom"+b"\0"*8) + box(b"mdat", b"abc") + box(b"moov", mvhd)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mock.mp4"
            path.write_bytes(mp4)
            self.assertEqual(bc._mp4_duration(str(path)), 578)

    def test_file_duration_mkv(self):
        def size_vint(n):
            if n >= 127:
                return b"\x40" + bytes([n])
            return bytes([0x80 | n])
        def element(idbytes, payload):
            return idbytes + size_vint(len(payload)) + payload
        scale = element(b"\x2a\xd7\xb1", (1000000).to_bytes(3, "big"))
        duration = element(b"\x44\x89", struct.pack(">d", 578000.0))
        info = element(b"\x15\x49\xa9\x66", scale+duration)
        segment = element(b"\x18\x53\x80\x67", info)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mock.mkv"
            path.write_bytes(segment)
            self.assertEqual(bc._mkv_duration(str(path)), 578)


if __name__ == "__main__":
    unittest.main()
