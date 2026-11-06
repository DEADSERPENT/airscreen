from airscreen_sender.negotiate import negotiate

TV4K = {"video": {"modes": [{"w": 3840, "h": 2160, "fps": 30}, {"w": 1920, "h": 1080, "fps": 60}]},
        "display": {"w": 3840, "h": 2160, "refresh": 60}, "net": {"type": "ethernet", "link_mbps": 1000}}


def test_1080p_source_gets_1080p60():
    c = negotiate(TV4K, 1920, 1080, 60)
    assert (c.width, c.height, c.fps) == (1920, 1080, 60)
    assert 15_000 <= c.bitrate_kbps <= 25_000


def test_1440p_source_not_upscaled_resolution_first():
    c = negotiate(TV4K, 2560, 1440, 165)
    assert (c.width, c.height, c.fps) == (2560, 1440, 30)


def test_pipe_limits_fps_and_says_so():
    caps = dict(TV4K, video={"modes": [{"w": 3840, "h": 2160, "fps": 60}]})
    c = negotiate(caps, 2560, 1440, 60)
    assert 30 <= c.fps <= 40 and any("pipe" in n for n in c.notes)


def test_decoder_limits_resolution():
    caps = {"video": {"modes": [{"w": 1920, "h": 1080, "fps": 30}]}, "display": {"w": 3840, "h": 2160, "refresh": 60}}
    c = negotiate(caps, 2560, 1440, 60)
    assert (c.width, c.height, c.fps) == (1920, 1080, 30)


def test_slow_wifi_is_conservative():
    caps = dict(TV4K, net={"type": "wifi", "link_mbps": 144})
    c = negotiate(caps, 2560, 1440, 60)
    assert (c.width, c.height, c.fps) == (1920, 1080, 30)       # never 1440p40 over a 2.4 GHz link
    assert c.bitrate_kbps <= 15_000 and any("Wi-Fi" in n for n in c.notes)


def test_slow_link_caps_bitrate():
    caps = dict(TV4K, net={"type": "ethernet", "link_mbps": 30})
    c = negotiate(caps, 1920, 1080, 60)
    assert c.bitrate_kbps == 12_000 and any("link" in n for n in c.notes)


def test_missing_caps_fall_back_safely():
    c = negotiate(None, 1920, 1080, 60)
    assert (c.width, c.height, c.fps) == (1920, 1080, 30) and c.notes
