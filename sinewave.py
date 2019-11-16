#!/usr/bin/env python

import synthesizer as s
import numpy as np

if __name__ == "__main__":
    player = s.Player()
    player.open_stream()
    synthesizer = s.Synthesizer(osc1_waveform=s.Waveform.sine, osc1_volume=1.0, use_osc2=False)
    list2=[i for i in range(200,8000,100)]
    for a in list2:
        player.play_wave(synthesizer.generate_constant_wave(a,0.5))

