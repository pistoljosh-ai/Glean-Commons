import math
import struct
import wave

rate = 24000
beat = .4375
chords = [(45,52,55,59),(41,48,52,55),(48,55,59,62),(43,50,53,57)]
melody = [0,2,1,3,2,1,3,1]
freq = lambda note: 440*2**((note-69)/12)
def write_score(path, duration):
    frames = bytearray()
    for i in range(duration*rate):
        t = i/rate
        step = int(t/beat)
        elapsed = t-step*beat
        chord = chords[(step//8)%4]
        note = freq(chord[melody[step%8]]+12)
        env = min(1,elapsed/.022)*math.exp(-elapsed*8)
        pluck = .14*env*(math.sin(math.tau*note*elapsed)+.22*math.sin(math.tau*note*2*elapsed))
        bar = t%(beat*8)
        pad = .038*min(1,bar/.22,(beat*8-bar)/.3)*sum(math.sin(math.tau*freq(n)*t) for n in chord[:3])
        kick = .09*math.exp(-elapsed*23)*math.sin(math.tau*(52*elapsed+2*(1-math.exp(-elapsed*22)))) if step%4==0 else 0
        fade = max(0,min(1,t/.6,(duration-t)/1.7))
        frames.extend(struct.pack("<h",int(32767*fade*(pluck+pad+kick))))
    with wave.open(str(path),"wb") as out:
        out.setparams((1,2,rate,0,"NONE","not compressed"))
        out.writeframes(frames)
