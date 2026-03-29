import QtQuick 2.9
import MuseScore 3.0

MuseScore {
    menuPath:      "Plugins.Maestro"
    description:   "AI composition command interface for MuseScore 4."
    version:       "6.0"
    pluginType:    "dialog"
    requiresScore: false

    width:  620
    height: 780

    property string statusMsg: "Ready"
    property int tpq: 480  // ticks per quarter note

    // =====================================================================
    //  CORE API
    // =====================================================================

    function note(pitch, duration, dots, staffIdx, voice, tick) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        c.rewindToTick(tick || 0)
        var d = dur(duration, dots)
        c.setDuration(d[0], d[1])
        c.addNote(resolvePitch(pitch))
    }

    function rest(duration, dots, staffIdx, voice, tick) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        c.rewindToTick(tick || 0)
        var d = dur(duration, dots)
        c.setDuration(d[0], d[1])
        c.addRest()
    }

    function chord(pitches, duration, dots, staffIdx, voice, tick) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        var t = tick || 0
        c.rewindToTick(t)
        var d = dur(duration, dots)
        c.setDuration(d[0], d[1])
        c.addNote(resolvePitch(pitches[0]))
        for (var i = 1; i < pitches.length; i++) {
            c.rewindToTick(t)
            c.addNote(resolvePitch(pitches[i]), true)
        }
    }

    function timeSig(numerator, denominator, tick) {
        var c = curScore.newCursor()
        c.staffIdx = 0; c.voice = 0; c.rewindToTick(tick || 0)
        var ts = newElement(Element.TIMESIG)
        ts.timesig = fraction(numerator, denominator)
        c.add(ts)
    }

    function keySig(key, tick, staffIdx) {
        var c = curScore.newCursor()
        var t = tick || 0
        if (staffIdx !== undefined && staffIdx !== null) {
            // Apply to specific staff only
            c.staffIdx = staffIdx; c.voice = 0; c.rewindToTick(t)
            var ks = newElement(Element.KEYSIG)
            ks.concertKey = key
            c.add(ks)
        } else {
            // Apply to all staves
            for (var s = 0; s < curScore.nstaves; s++) {
                c.staffIdx = s; c.voice = 0; c.rewindToTick(t)
                var ks2 = newElement(Element.KEYSIG)
                ks2.concertKey = key
                c.add(ks2)
            }
        }
    }

    function tempo(bpm, label, tick) {
        var c = curScore.newCursor()
        c.staffIdx = 0; c.voice = 0; c.rewindToTick(tick || 0)
        var t = newElement(Element.TEMPO_TEXT)
        t.tempo = bpm / 60.0
        t.tempoFollowText = false
        t.text = label || ("q = " + bpm)
        c.add(t)
    }

    function dynamic(dyn, tick, staffIdx) {
        var symMap = {
            "pppppp": "<sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym>",
            "ppppp":  "<sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym>",
            "pppp":   "<sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym>",
            "ppp":    "<sym>dynamicPiano</sym><sym>dynamicPiano</sym><sym>dynamicPiano</sym>",
            "pp":     "<sym>dynamicPiano</sym><sym>dynamicPiano</sym>",
            "p":      "<sym>dynamicPiano</sym>",
            "mp":     "<sym>dynamicMezzo</sym><sym>dynamicPiano</sym>",
            "mf":     "<sym>dynamicMezzo</sym><sym>dynamicForte</sym>",
            "f":      "<sym>dynamicForte</sym>",
            "ff":     "<sym>dynamicForte</sym><sym>dynamicForte</sym>",
            "fff":    "<sym>dynamicForte</sym><sym>dynamicForte</sym><sym>dynamicForte</sym>",
            "ffff":   "<sym>dynamicForte</sym><sym>dynamicForte</sym><sym>dynamicForte</sym><sym>dynamicForte</sym>",
            "sfz":    "<sym>dynamicSforzando</sym><sym>dynamicForte</sym><sym>dynamicZ</sym>",
            "sf":     "<sym>dynamicSforzando</sym><sym>dynamicForte</sym>",
            "fp":     "<sym>dynamicForte</sym><sym>dynamicPiano</sym>",
            "fz":     "<sym>dynamicForte</sym><sym>dynamicZ</sym>",
            "sfp":    "<sym>dynamicSforzando</sym><sym>dynamicForte</sym><sym>dynamicPiano</sym>",
            "rfz":    "<sym>dynamicRinforzando</sym><sym>dynamicForte</sym><sym>dynamicZ</sym>"
        }
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = 0; c.rewindToTick(tick || 0)
        var d = newElement(Element.DYNAMIC)
        d.text = symMap[dyn] || dyn
        c.add(d)
    }

    function text(str, tick, staffIdx) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = 0; c.rewindToTick(tick || 0)
        var t = newElement(Element.STAFF_TEXT)
        t.text = str
        c.add(t)
    }

    function rehearsal(label, tick) {
        var c = curScore.newCursor()
        c.staffIdx = 0; c.voice = 0; c.rewindToTick(tick || 0)
        var r = newElement(Element.REHEARSAL_MARK)
        r.text = label
        c.add(r)
    }

    function fermata(tick, staffIdx, voice) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        c.rewindToTick(tick || 0)
        var f = newElement(Element.FERMATA)
        c.add(f)
    }

    function lyrics(syllable, tick, staffIdx, voice, verse) {
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        c.rewindToTick(tick || 0)
        var l = newElement(Element.LYRICS)
        l.text = syllable
        if (verse) l.verse = verse
        c.add(l)
    }

    // ── articulation(symbol, tick, staffIdx, voice) ──────────────────
    // Adds an articulation to the note/chord at the given tick.
    // symbol: "staccato","accent","tenuto","marcato","staccatissimo",
    //         "accentStaccato","marcatoStaccato","tenutoStaccato","tenutoAccent"
    // NOTE: cursor must be on a chord (not a rest) for this to work.
    function articulation(symbol, tick, staffIdx, voice) {
        var symMap = {
            "staccato":         SymId.articStaccatoAbove,
            "accent":           SymId.articAccentAbove,
            "tenuto":           SymId.articTenutoAbove,
            "marcato":          SymId.articMarcatoAbove,
            "staccatissimo":    SymId.articStaccatissimoAbove,
            "accentStaccato":   SymId.articAccentStaccatoAbove,
            "marcatoStaccato":  SymId.articMarcatoStaccatoAbove,
            "tenutoStaccato":   SymId.articTenutoStaccatoAbove,
            "tenutoAccent":     SymId.articTenutoAccentAbove
        }
        var c = curScore.newCursor()
        c.staffIdx = staffIdx || 0; c.voice = voice || 0
        c.rewindToTick(tick || 0)
        var art = newElement(Element.ARTICULATION)
        art.symbol = symMap[symbol] || SymId.articStaccatoAbove
        c.add(art)
    }

    function addInstrument(instrumentId) {
        curScore.appendPart(instrumentId)
    }

    function appendMeasures(count) {
        curScore.appendMeasures(count)
    }

    function startRepeat(measureIndex) {
        var c = curScore.newCursor()
        c.staffIdx = 0; c.voice = 0
        c.rewind(Cursor.SCORE_START)
        for (var i = 0; i < (measureIndex || 0); i++) c.nextMeasure()
        c.measure.repeatStart = true
    }

    function endRepeat(measureIndex) {
        var c = curScore.newCursor()
        c.staffIdx = 0; c.voice = 0
        c.rewind(Cursor.SCORE_START)
        for (var i = 0; i < (measureIndex || 0); i++) c.nextMeasure()
        c.measure.repeatEnd = true
    }

    function clearScore() {
        if (!curScore) return 0

        // Step 1: Remove all annotations (dynamics, tempo, text, etc.)
        var annotations = []
        var seg = curScore.firstSegment
        while (seg) {
            if (seg.annotations) {
                for (var a = seg.annotations.length - 1; a >= 0; a--)
                    annotations.push(seg.annotations[a])
            }
            seg = seg.next
        }

        // Step 2: Remove all chords (turns them into rests)
        var chords = []
        var cursor = curScore.newCursor()
        for (var s = 0; s < curScore.nstaves; s++) {
            for (var v = 0; v < 4; v++) {
                cursor.staffIdx = s; cursor.voice = v
                cursor.rewind(Cursor.SCORE_START)
                while (cursor.segment) {
                    var el = cursor.element
                    if (el && el.type === Element.CHORD) chords.push(el)
                    cursor.next()
                }
            }
        }

        curScore.startCmd()
        for (var i = annotations.length - 1; i >= 0; i--) {
            try { removeElement(annotations[i]) } catch(e) {}
        }
        for (var j = chords.length - 1; j >= 0; j--) {
            try { removeElement(chords[j]) } catch(e) {}
        }
        curScore.endCmd()

        // Step 3: Remove all measures except the last one
        // (MuseScore requires at least 1 measure to exist)
        var removed = 0
        curScore.startCmd()
        while (curScore.nmeasures > 1) {
            var m = curScore.firstMeasure
            if (!m) break
            try {
                removeElement(m)
                removed++
            } catch(e) { break }
        }
        curScore.endCmd()

        return chords.length + annotations.length + removed
    }

    function readScore() {
        var cursor = curScore.newCursor()
        var notes = 0; var rests = 0
        for (var s = 0; s < curScore.nstaves; s++) {
            for (var v = 0; v < 4; v++) {
                cursor.staffIdx = s; cursor.voice = v
                cursor.rewind(Cursor.SCORE_START)
                while (cursor.segment) {
                    var el = cursor.element
                    if (el) {
                        if (el.type === Element.CHORD) notes++
                        else if (el.type === Element.REST) rests++
                    }
                    cursor.next()
                }
            }
        }
        return { notes: notes, rests: rests }
    }

    // ── Helpers ─────────────────────────────────────────────────────────
    function dur(name, dots) {
        var map = {"whole":[1,1],"half":[1,2],"quarter":[1,4],"eighth":[1,8],
                   "16th":[1,16],"32nd":[1,32],"64th":[1,64]}
        var b = map[name] || [1,4]
        if (!dots || dots === 0) return b
        var n = b[0] * (Math.pow(2, dots+1) - 1)
        var d = b[1] * Math.pow(2, dots)
        return [n, d]
    }

    function resolvePitch(p) {
        if (typeof p === "number") return p
        var noteMap = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
        var m = p.match(/^([A-Ga-g])(#{0,2}|b{0,2})(\d+)$/)
        if (!m) return 60
        var pitch = noteMap[m[1].toUpperCase()] + (parseInt(m[3]) + 1) * 12
        for (var i = 0; i < m[2].length; i++)
            pitch += (m[2][i] === '#') ? 1 : -1
        return pitch
    }

    // =====================================================================
    //  UI — helper to make buttons
    // =====================================================================

    function makeStatus(msg) { statusMsg = msg }

    // =====================================================================
    //  UI
    // =====================================================================

    Rectangle {
        x: 0; y: 0; width: 620; height: 780; color: "#1e1e2e"

        Flickable {
            x: 0; y: 0; width: 620; height: 780
            contentWidth: 620; contentHeight: 1150
            clip: true

            // Title
            Text { x:0; y:10; width:620; horizontalAlignment:Text.AlignHCenter
                   text:"Maestro v6"; color:"#cdd6f4"; font.pixelSize:22; font.bold:true }

            // ── Status bar ──
            Rectangle { x:20; y:40; width:580; height:36; radius:5; color:"#2a2a3e"
                Text { x:10; y:4; width:560; height:28; text:statusMsg; color:"#a6adc8"
                       font.pixelSize:11; wrapMode:Text.Wrap; elide:Text.ElideRight }}

            // ── Core: Clear / Read / +Measures ──
            Text { x:20; y:86; text:"CORE"; color:"#f38ba8"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:102; width:90; height:30; radius:4; color:z1.pressed?"#5a1010":"#7a2020"
                Text{anchors.centerIn:parent;text:"Clear All";color:"#fff";font.pixelSize:10;font.bold:true}
                MouseArea{id:z1;anchors.fill:parent;onClicked:{if(!curScore)return;var n=clearScore();statusMsg="Cleared "+n+" elements"}}}
            Rectangle { x:116; y:102; width:90; height:30; radius:4; color:z2.pressed?"#1a3a5a":"#2a5a8a"
                Text{anchors.centerIn:parent;text:"Read Score";color:"#fff";font.pixelSize:10;font.bold:true}
                MouseArea{id:z2;anchors.fill:parent;onClicked:{if(!curScore)return;var r=readScore();statusMsg=curScore.nmeasures+" meas | "+r.notes+" notes | "+r.rests+" rests"}}}
            Rectangle { x:212; y:102; width:90; height:30; radius:4; color:z3.pressed?"#105a10":"#207a20"
                Text{anchors.centerIn:parent;text:"+4 Measures";color:"#fff";font.pixelSize:10;font.bold:true}
                MouseArea{id:z3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();appendMeasures(4);curScore.endCmd();statusMsg="Appended 4 measures"}}}
            Rectangle { x:308; y:102; width:90; height:30; radius:4; color:z4.pressed?"#105a10":"#207a20"
                Text{anchors.centerIn:parent;text:"+8 Measures";color:"#fff";font.pixelSize:10;font.bold:true}
                MouseArea{id:z4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();appendMeasures(8);curScore.endCmd();statusMsg="Appended 8 measures"}}}

            // ── note() ──
            Text { x:20; y:142; text:"note(pitch, duration, dots, staff, voice, tick)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:158; width:100; height:30; radius:4; color:n1.pressed?"#0a3a0a":"#1a5a1a"
                Text{anchors.centerIn:parent;text:"C4 quarter";color:"#fff";font.pixelSize:10}
                MouseArea{id:n1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();note("C4","quarter");curScore.endCmd();statusMsg="note('C4','quarter')"}}}
            Rectangle { x:126; y:158; width:100; height:30; radius:4; color:n2.pressed?"#0a3a0a":"#1a5a1a"
                Text{anchors.centerIn:parent;text:"E5 half";color:"#fff";font.pixelSize:10}
                MouseArea{id:n2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();note("E5","half");curScore.endCmd();statusMsg="note('E5','half')"}}}
            Rectangle { x:232; y:158; width:100; height:30; radius:4; color:n3.pressed?"#0a3a0a":"#1a5a1a"
                Text{anchors.centerIn:parent;text:"F#4 eighth";color:"#fff";font.pixelSize:10}
                MouseArea{id:n3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();note("F#4","eighth");curScore.endCmd();statusMsg="note('F#4','eighth')"}}}
            Rectangle { x:338; y:158; width:100; height:30; radius:4; color:n4.pressed?"#0a3a0a":"#1a5a1a"
                Text{anchors.centerIn:parent;text:"Bb3 whole";color:"#fff";font.pixelSize:10}
                MouseArea{id:n4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();note("Bb3","whole");curScore.endCmd();statusMsg="note('Bb3','whole')"}}}
            Rectangle { x:444; y:158; width:100; height:30; radius:4; color:n5.pressed?"#0a3a0a":"#1a5a1a"
                Text{anchors.centerIn:parent;text:"G4 dotted q";color:"#fff";font.pixelSize:10}
                MouseArea{id:n5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();note("G4","quarter",1);curScore.endCmd();statusMsg="note('G4','quarter',1)"}}}

            // ── rest() ──
            Text { x:20; y:198; text:"rest(duration, dots, staff, voice, tick)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:214; width:100; height:30; radius:4; color:r1.pressed?"#2a2a4a":"#3a3a6a"
                Text{anchors.centerIn:parent;text:"quarter rest";color:"#fff";font.pixelSize:10}
                MouseArea{id:r1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();rest("quarter");curScore.endCmd();statusMsg="rest('quarter')"}}}
            Rectangle { x:126; y:214; width:100; height:30; radius:4; color:r2.pressed?"#2a2a4a":"#3a3a6a"
                Text{anchors.centerIn:parent;text:"half rest";color:"#fff";font.pixelSize:10}
                MouseArea{id:r2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();rest("half");curScore.endCmd();statusMsg="rest('half')"}}}
            Rectangle { x:232; y:214; width:100; height:30; radius:4; color:r3.pressed?"#2a2a4a":"#3a3a6a"
                Text{anchors.centerIn:parent;text:"whole rest";color:"#fff";font.pixelSize:10}
                MouseArea{id:r3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();rest("whole");curScore.endCmd();statusMsg="rest('whole')"}}}
            Rectangle { x:338; y:214; width:100; height:30; radius:4; color:r4.pressed?"#2a2a4a":"#3a3a6a"
                Text{anchors.centerIn:parent;text:"eighth rest";color:"#fff";font.pixelSize:10}
                MouseArea{id:r4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();rest("eighth");curScore.endCmd();statusMsg="rest('eighth')"}}}

            // ── chord() ──
            Text { x:20; y:254; text:"chord(pitches[], duration, dots, staff, voice, tick)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:270; width:110; height:30; radius:4; color:ch1.pressed?"#3a2a0a":"#5a4a1a"
                Text{anchors.centerIn:parent;text:"C maj (CEG)";color:"#fff";font.pixelSize:10}
                MouseArea{id:ch1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();chord(["C4","E4","G4"],"half");curScore.endCmd();statusMsg="chord(['C4','E4','G4'],'half')"}}}
            Rectangle { x:136; y:270; width:110; height:30; radius:4; color:ch2.pressed?"#3a2a0a":"#5a4a1a"
                Text{anchors.centerIn:parent;text:"D min (DFA)";color:"#fff";font.pixelSize:10}
                MouseArea{id:ch2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();chord(["D4","F4","A4"],"half");curScore.endCmd();statusMsg="chord(['D4','F4','A4'],'half')"}}}
            Rectangle { x:252; y:270; width:110; height:30; radius:4; color:ch3.pressed?"#3a2a0a":"#5a4a1a"
                Text{anchors.centerIn:parent;text:"G7 (GBDF)";color:"#fff";font.pixelSize:10}
                MouseArea{id:ch3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();chord(["G3","B3","D4","F4"],"whole");curScore.endCmd();statusMsg="chord(['G3','B3','D4','F4'],'whole')"}}}
            Rectangle { x:368; y:270; width:130; height:30; radius:4; color:ch4.pressed?"#3a2a0a":"#5a4a1a"
                Text{anchors.centerIn:parent;text:"F#min (F#AC#)";color:"#fff";font.pixelSize:10}
                MouseArea{id:ch4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();chord(["F#4","A4","C#5"],"quarter");curScore.endCmd();statusMsg="chord(['F#4','A4','C#5'],'quarter')"}}}

            // ── addInstrument() ──
            Text { x:20; y:310; text:"addInstrument(instrumentId)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:326; width:90; height:30; radius:4; color:i1.pressed?"#3a1a4a":"#5a2a7a"
                Text{anchors.centerIn:parent;text:"Violin";color:"#fff";font.pixelSize:10}
                MouseArea{id:i1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();try{addInstrument("violin");statusMsg="addInstrument('violin')"}catch(e){statusMsg="Failed: "+e};curScore.endCmd()}}}
            Rectangle { x:116; y:326; width:90; height:30; radius:4; color:i2.pressed?"#3a1a4a":"#5a2a7a"
                Text{anchors.centerIn:parent;text:"Flute";color:"#fff";font.pixelSize:10}
                MouseArea{id:i2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();try{addInstrument("flute");statusMsg="addInstrument('flute')"}catch(e){statusMsg="Failed: "+e};curScore.endCmd()}}}
            Rectangle { x:212; y:326; width:90; height:30; radius:4; color:i3.pressed?"#3a1a4a":"#5a2a7a"
                Text{anchors.centerIn:parent;text:"Piano";color:"#fff";font.pixelSize:10}
                MouseArea{id:i3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();try{addInstrument("piano");statusMsg="addInstrument('piano')"}catch(e){statusMsg="Failed: "+e};curScore.endCmd()}}}
            Rectangle { x:308; y:326; width:90; height:30; radius:4; color:i4.pressed?"#3a1a4a":"#5a2a7a"
                Text{anchors.centerIn:parent;text:"Cello";color:"#fff";font.pixelSize:10}
                MouseArea{id:i4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();try{addInstrument("violoncello");statusMsg="addInstrument('violoncello')"}catch(e){statusMsg="Failed: "+e};curScore.endCmd()}}}
            Rectangle { x:404; y:326; width:90; height:30; radius:4; color:i5.pressed?"#3a1a4a":"#5a2a7a"
                Text{anchors.centerIn:parent;text:"Trumpet";color:"#fff";font.pixelSize:10}
                MouseArea{id:i5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();try{addInstrument("trumpet");statusMsg="addInstrument('trumpet')"}catch(e){statusMsg="Failed: "+e};curScore.endCmd()}}}

            // ── timeSig() ──
            Text { x:20; y:366; text:"timeSig(numerator, denominator, tick)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:382; width:80; height:30; radius:4; color:t1.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"4/4";color:"#fff";font.pixelSize:10}
                MouseArea{id:t1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(4,4);curScore.endCmd();statusMsg="timeSig(4,4)"}}}
            Rectangle { x:106; y:382; width:80; height:30; radius:4; color:t2.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"3/4";color:"#fff";font.pixelSize:10}
                MouseArea{id:t2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(3,4);curScore.endCmd();statusMsg="timeSig(3,4)"}}}
            Rectangle { x:192; y:382; width:80; height:30; radius:4; color:t3.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"6/8";color:"#fff";font.pixelSize:10}
                MouseArea{id:t3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(6,8);curScore.endCmd();statusMsg="timeSig(6,8)"}}}
            Rectangle { x:278; y:382; width:80; height:30; radius:4; color:t4.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"2/4";color:"#fff";font.pixelSize:10}
                MouseArea{id:t4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(2,4);curScore.endCmd();statusMsg="timeSig(2,4)"}}}
            Rectangle { x:364; y:382; width:80; height:30; radius:4; color:t5.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"5/4";color:"#fff";font.pixelSize:10}
                MouseArea{id:t5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(5,4);curScore.endCmd();statusMsg="timeSig(5,4)"}}}
            Rectangle { x:450; y:382; width:80; height:30; radius:4; color:t6.pressed?"#1a3a3a":"#2a5a5a"
                Text{anchors.centerIn:parent;text:"7/8";color:"#fff";font.pixelSize:10}
                MouseArea{id:t6;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();timeSig(7,8);curScore.endCmd();statusMsg="timeSig(7,8)"}}}

            // ── keySig() ──
            Text { x:20; y:422; text:"keySig(key, tick, staff)  — sharps+, flats-"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:438; width:80; height:30; radius:4; color:k1.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"C (0)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(0);curScore.endCmd();statusMsg="keySig(0) — C major"}}}
            Rectangle { x:106; y:438; width:80; height:30; radius:4; color:k2.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"G (1)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(1);curScore.endCmd();statusMsg="keySig(1) — G major"}}}
            Rectangle { x:192; y:438; width:80; height:30; radius:4; color:k3.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"D (2)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(2);curScore.endCmd();statusMsg="keySig(2) — D major"}}}
            Rectangle { x:278; y:438; width:80; height:30; radius:4; color:k4.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"A (3)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(3);curScore.endCmd();statusMsg="keySig(3) — A major"}}}
            Rectangle { x:364; y:438; width:80; height:30; radius:4; color:k5.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"F (-1)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(-1);curScore.endCmd();statusMsg="keySig(-1) — F major"}}}
            Rectangle { x:450; y:438; width:80; height:30; radius:4; color:k6.pressed?"#3a2a1a":"#5a4a2a"
                Text{anchors.centerIn:parent;text:"Bb (-2)";color:"#fff";font.pixelSize:10}
                MouseArea{id:k6;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();keySig(-2);curScore.endCmd();statusMsg="keySig(-2) — Bb major"}}}

            // ── tempo() ──
            Text { x:20; y:478; text:"tempo(bpm, label, tick)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:494; width:100; height:30; radius:4; color:tp1.pressed?"#1a2a3a":"#2a4a6a"
                Text{anchors.centerIn:parent;text:"Largo 60";color:"#fff";font.pixelSize:10}
                MouseArea{id:tp1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();tempo(60,"Largo");curScore.endCmd();statusMsg="tempo(60,'Largo')"}}}
            Rectangle { x:126; y:494; width:100; height:30; radius:4; color:tp2.pressed?"#1a2a3a":"#2a4a6a"
                Text{anchors.centerIn:parent;text:"Andante 80";color:"#fff";font.pixelSize:10}
                MouseArea{id:tp2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();tempo(80,"Andante");curScore.endCmd();statusMsg="tempo(80,'Andante')"}}}
            Rectangle { x:232; y:494; width:100; height:30; radius:4; color:tp3.pressed?"#1a2a3a":"#2a4a6a"
                Text{anchors.centerIn:parent;text:"Allegro 120";color:"#fff";font.pixelSize:10}
                MouseArea{id:tp3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();tempo(120,"Allegro");curScore.endCmd();statusMsg="tempo(120,'Allegro')"}}}
            Rectangle { x:338; y:494; width:100; height:30; radius:4; color:tp4.pressed?"#1a2a3a":"#2a4a6a"
                Text{anchors.centerIn:parent;text:"Presto 180";color:"#fff";font.pixelSize:10}
                MouseArea{id:tp4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();tempo(180,"Presto");curScore.endCmd();statusMsg="tempo(180,'Presto')"}}}

            // ── text() ──
            Text { x:20; y:534; text:"text(str, tick, staff)  rehearsal()  dynamic()  fermata()  lyrics()"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:550; width:80; height:30; radius:4; color:tx1.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"\"pizz.\"";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();text("pizz.",0);curScore.endCmd();statusMsg="text('pizz.')"}}}
            Rectangle { x:106; y:550; width:80; height:30; radius:4; color:tx2.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"\"arco\"";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();text("arco",0);curScore.endCmd();statusMsg="text('arco')"}}}
            Rectangle { x:192; y:550; width:80; height:30; radius:4; color:tx3.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"Reh. A";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();rehearsal("A",0);curScore.endCmd();statusMsg="rehearsal('A')"}}}
            Rectangle { x:278; y:550; width:80; height:30; radius:4; color:tx4.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"dyn: ff";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();dynamic("ff",0);curScore.endCmd();statusMsg="dynamic('ff')"}}}
            Rectangle { x:364; y:550; width:80; height:30; radius:4; color:tx5.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"dyn: pp";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();dynamic("pp",0);curScore.endCmd();statusMsg="dynamic('pp')"}}}
            Rectangle { x:450; y:550; width:80; height:30; radius:4; color:tx6.pressed?"#2a2a3a":"#3a3a5a"
                Text{anchors.centerIn:parent;text:"fermata";color:"#fff";font.pixelSize:10}
                MouseArea{id:tx6;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();fermata(0);curScore.endCmd();statusMsg="fermata()"}}}

            // ── startRepeat() / endRepeat() ──
            Text { x:20; y:590; text:"startRepeat(measure)  endRepeat(measure)"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:606; width:120; height:30; radius:4; color:rp1.pressed?"#3a3a1a":"#5a5a2a"
                Text{anchors.centerIn:parent;text:"startRepeat(0)";color:"#fff";font.pixelSize:10}
                MouseArea{id:rp1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();startRepeat(0);curScore.endCmd();statusMsg="startRepeat(0) — meas 1"}}}
            Rectangle { x:146; y:606; width:120; height:30; radius:4; color:rp2.pressed?"#3a3a1a":"#5a5a2a"
                Text{anchors.centerIn:parent;text:"endRepeat(1)";color:"#fff";font.pixelSize:10}
                MouseArea{id:rp2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();endRepeat(1);curScore.endCmd();statusMsg="endRepeat(1) — meas 2"}}}
            Rectangle { x:272; y:606; width:120; height:30; radius:4; color:rp3.pressed?"#3a3a1a":"#5a5a2a"
                Text{anchors.centerIn:parent;text:"endRepeat(3)";color:"#fff";font.pixelSize:10}
                MouseArea{id:rp3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();endRepeat(3);curScore.endCmd();statusMsg="endRepeat(3) — meas 4"}}}
            Rectangle { x:398; y:606; width:130; height:30; radius:4; color:rp4.pressed?"#3a3a1a":"#5a5a2a"
                Text{anchors.centerIn:parent;text:"start(0)+end(3)";color:"#fff";font.pixelSize:10}
                MouseArea{id:rp4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();startRepeat(0);endRepeat(3);curScore.endCmd();statusMsg="Repeat meas 1-4"}}}

            // ── articulation() ──
            Text { x:20; y:646; text:"articulation(symbol, tick, staff, voice)  — add to note at tick 0"; color:"#89b4fa"; font.pixelSize:11; font.bold:true }
            Rectangle { x:20; y:662; width:90; height:30; radius:4; color:ar1.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Staccato";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar1;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("staccato",0);curScore.endCmd();statusMsg="articulation('staccato')"}}}
            Rectangle { x:116; y:662; width:90; height:30; radius:4; color:ar2.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Accent";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar2;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("accent",0);curScore.endCmd();statusMsg="articulation('accent')"}}}
            Rectangle { x:212; y:662; width:90; height:30; radius:4; color:ar3.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Tenuto";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar3;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("tenuto",0);curScore.endCmd();statusMsg="articulation('tenuto')"}}}
            Rectangle { x:308; y:662; width:90; height:30; radius:4; color:ar4.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Marcato";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar4;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("marcato",0);curScore.endCmd();statusMsg="articulation('marcato')"}}}
            Rectangle { x:404; y:662; width:110; height:30; radius:4; color:ar5.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Staccatissimo";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar5;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("staccatissimo",0);curScore.endCmd();statusMsg="articulation('staccatissimo')"}}}
            Rectangle { x:20; y:698; width:110; height:30; radius:4; color:ar6.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Accent+Stacc";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar6;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("accentStaccato",0);curScore.endCmd();statusMsg="articulation('accentStaccato')"}}}
            Rectangle { x:136; y:698; width:120; height:30; radius:4; color:ar7.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Marcato+Stacc";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar7;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("marcatoStaccato",0);curScore.endCmd();statusMsg="articulation('marcatoStaccato')"}}}
            Rectangle { x:262; y:698; width:120; height:30; radius:4; color:ar8.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Tenuto+Stacc";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar8;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("tenutoStaccato",0);curScore.endCmd();statusMsg="articulation('tenutoStaccato')"}}}
            Rectangle { x:388; y:698; width:120; height:30; radius:4; color:ar9.pressed?"#2a3a2a":"#3a5a3a"
                Text{anchors.centerIn:parent;text:"Tenuto+Accent";color:"#fff";font.pixelSize:10}
                MouseArea{id:ar9;anchors.fill:parent;onClicked:{if(!curScore)return;curScore.startCmd();articulation("tenutoAccent",0);curScore.endCmd();statusMsg="articulation('tenutoAccent')"}}}

            // ── Multi-Measure Demos ──
            Text { x:20; y:742; text:"MULTI-MEASURE DEMOS  (needs 8+ measures)"; color:"#f38ba8"; font.pixelSize:11; font.bold:true }

            // Demo 1: melody across 4 measures with dynamics + tempo
            Rectangle { x:20; y:758; width:170; height:30; radius:4; color:dm1.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"4-Bar Melody + Marks";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm1;anchors.fill:parent;onClicked:{
                    if(!curScore)return; curScore.startCmd()
                    var t=tpq; // 480
                    // Measure 1: C D E F
                    note("C4","quarter",0,0,0,0); note("D4","quarter",0,0,0,t)
                    note("E4","quarter",0,0,0,t*2); note("F4","quarter",0,0,0,t*3)
                    // Measure 2: G A B C5
                    note("G4","quarter",0,0,0,t*4); note("A4","quarter",0,0,0,t*5)
                    note("B4","quarter",0,0,0,t*6); note("C5","quarter",0,0,0,t*7)
                    // Measure 3: half notes
                    note("D5","half",0,0,0,t*8); note("E5","half",0,0,0,t*10)
                    // Measure 4: whole note
                    note("C5","whole",0,0,0,t*12)
                    // Markings across measures
                    tempo(100,"Andante",0); dynamic("mp",0); dynamic("f",t*8)
                    rehearsal("A",0); rehearsal("B",t*8)
                    text("legato",0); text("cresc.",t*4)
                    curScore.endCmd(); statusMsg="4-bar melody + tempo, dynamics, rehearsals, text"
                }}}

            // Demo 2: chord progression across measures with key change
            Rectangle { x:196; y:758; width:170; height:30; radius:4; color:dm2.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"Chords + Key Change";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm2;anchors.fill:parent;onClicked:{
                    if(!curScore)return; curScore.startCmd()
                    var m=tpq*4; // measure length in 4/4
                    // Key of G major
                    keySig(1,0)
                    // Measure 1: G major chord
                    chord(["G3","B3","D4"],"whole",0,0,0,0)
                    // Measure 2: C major chord
                    chord(["C4","E4","G4"],"whole",0,0,0,m)
                    // Measure 3: key change to D major + D chord
                    keySig(2,m*2)
                    chord(["D4","F#4","A4"],"whole",0,0,0,m*2)
                    // Measure 4: G major chord
                    chord(["G3","B3","D4"],"whole",0,0,0,m*3)
                    dynamic("mf",0); dynamic("ff",m*2)
                    curScore.endCmd(); statusMsg="Chord progression with key change at measure 3"
                }}}

            // Demo 3: mixed rhythms + articulations across measures
            Rectangle { x:372; y:758; width:170; height:30; radius:4; color:dm3.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"Rhythms + Artics";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm3;anchors.fill:parent;onClicked:{
                    if(!curScore)return; curScore.startCmd()
                    var t=tpq
                    // Measure 1: quarter notes with staccato
                    note("E4","quarter",0,0,0,0); note("E4","quarter",0,0,0,t)
                    note("F4","quarter",0,0,0,t*2); note("G4","quarter",0,0,0,t*3)
                    articulation("staccato",0); articulation("staccato",t)
                    articulation("staccato",t*2); articulation("staccato",t*3)
                    // Measure 2: eighth notes
                    note("A4","eighth",0,0,0,t*4); note("B4","eighth",0,0,0,t*4.5)
                    note("C5","eighth",0,0,0,t*5); note("B4","eighth",0,0,0,t*5.5)
                    note("A4","quarter",0,0,0,t*6); note("G4","quarter",0,0,0,t*7)
                    articulation("accent",t*6); articulation("accent",t*7)
                    // Measure 3: dotted half + quarter with fermata
                    note("F4","half",1,0,0,t*8); note("E4","quarter",0,0,0,t*11)
                    fermata(t*8)
                    // Measure 4: whole rest (already empty)
                    dynamic("p",0); dynamic("mf",t*4); dynamic("pp",t*8)
                    curScore.endCmd(); statusMsg="Mixed rhythms + staccato, accent, fermata across 3 measures"
                }}}

            // Demo 4: time sig + repeats across measures
            Rectangle { x:20; y:794; width:170; height:30; radius:4; color:dm4.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"TimeSig + Repeats";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm4;anchors.fill:parent;onClicked:{
                    if(!curScore)return; curScore.startCmd()
                    // Set 3/4 time
                    timeSig(3,4,0)
                    var m=tpq*3; // measure = 3 beats in 3/4
                    // Waltz pattern across 4 measures
                    note("C4","half",0,0,0,0); note("G3","quarter",0,0,0,tpq*2)
                    note("E4","half",0,0,0,m); note("G3","quarter",0,0,0,m+tpq*2)
                    note("F4","half",0,0,0,m*2); note("A3","quarter",0,0,0,m*2+tpq*2)
                    note("E4","half",1,0,0,m*3)
                    // Repeat measures 1-4
                    startRepeat(0); endRepeat(3)
                    tempo(90,"Waltz",0)
                    curScore.endCmd(); statusMsg="3/4 waltz with repeat bars"
                }}}

            // Demo 5: multi-staff (needs 2+ instruments)
            Rectangle { x:196; y:794; width:170; height:30; radius:4; color:dm5.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"Multi-Staff Demo";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm5;anchors.fill:parent;onClicked:{
                    if(!curScore||curScore.nstaves<2){statusMsg="Need 2+ instruments! Add one first.";return}
                    curScore.startCmd()
                    var t=tpq
                    // Staff 0: melody
                    note("E5","quarter",0,0,0,0); note("D5","quarter",0,0,0,t)
                    note("C5","quarter",0,0,0,t*2); note("D5","quarter",0,0,0,t*3)
                    note("E5","half",0,0,0,t*4); note("C5","half",0,0,0,t*6)
                    // Staff 1: accompaniment
                    chord(["C3","E3","G3"],"half",0,1,0,0)
                    chord(["C3","E3","G3"],"half",0,1,0,t*2)
                    chord(["G2","B2","D3"],"half",0,1,0,t*4)
                    chord(["C3","E3","G3"],"half",0,1,0,t*6)
                    // Markings
                    dynamic("mf",0,0); dynamic("mp",0,1)
                    text("melody",0,0); text("accomp.",0,1)
                    curScore.endCmd(); statusMsg="Melody on staff 1, chords on staff 2"
                }}}

            // Demo 6: full 8-bar piece
            Rectangle { x:372; y:794; width:170; height:30; radius:4; color:dm6.pressed?"#2a1a3a":"#4a2a6a"
                Text{anchors.centerIn:parent;text:"8-Bar Piece";color:"#fff";font.pixelSize:10}
                MouseArea{id:dm6;anchors.fill:parent;onClicked:{
                    if(!curScore)return; curScore.startCmd()
                    var t=tpq; var m=t*4
                    keySig(1,0); tempo(110,"Moderato",0); dynamic("mp",0)
                    // m1: G4 A4 B4 A4
                    note("G4","quarter",0,0,0,0); note("A4","quarter",0,0,0,t)
                    note("B4","quarter",0,0,0,t*2); note("A4","quarter",0,0,0,t*3)
                    // m2: B4 C5 D5 rest
                    note("B4","quarter",0,0,0,m); note("C5","quarter",0,0,0,m+t)
                    note("D5","quarter",0,0,0,m+t*2); rest("quarter",0,0,0,m+t*3)
                    // m3: D5 C5 B4 A4
                    note("D5","quarter",0,0,0,m*2); note("C5","quarter",0,0,0,m*2+t)
                    note("B4","quarter",0,0,0,m*2+t*2); note("A4","quarter",0,0,0,m*2+t*3)
                    dynamic("mf",m*2)
                    // m4: G4 whole
                    note("G4","whole",0,0,0,m*3)
                    fermata(m*3)
                    // m5-8: repeat with variation
                    note("G4","quarter",0,0,0,m*4); note("B4","quarter",0,0,0,m*4+t)
                    note("D5","quarter",0,0,0,m*4+t*2); note("B4","quarter",0,0,0,m*4+t*3)
                    dynamic("f",m*4); rehearsal("B",m*4)
                    note("C5","half",0,0,0,m*5); note("A4","half",0,0,0,m*5+t*2)
                    note("B4","half",0,0,0,m*6); note("G4","half",0,0,0,m*6+t*2)
                    note("G4","whole",0,0,0,m*7)
                    fermata(m*7); dynamic("p",m*7)
                    curScore.endCmd(); statusMsg="8-bar piece in G major with dynamics, tempo, fermatas"
                }}}

            // ── API Reference ──
            Text { x:20; y:838; width:580; color:"#585b70"; font.pixelSize:10; lineHeight:1.4
                text:"API Reference:\n" +
                     "  note(pitch, dur, dots, staff, voice, tick)     chord(pitches[], dur, dots, staff, voice, tick)\n" +
                     "  rest(dur, dots, staff, voice, tick)            dynamic(text, tick, staff)\n" +
                     "  tempo(bpm, label, tick)                        text(str, tick, staff)\n" +
                     "  rehearsal(label, tick)                         fermata(tick, staff, voice)\n" +
                     "  lyrics(syllable, tick, staff, voice, verse)    timeSig(num, denom, tick)\n" +
                     "  keySig(key, tick, staff)                       addInstrument(id)\n" +
                     "  appendMeasures(count)                          clearScore()  readScore()\n" +
                     "  startRepeat(measureIdx)                        endRepeat(measureIdx)\n" +
                     "  articulation(symbol, tick, staff, voice)\n\n" +
                     "articulations: 'staccato','accent','tenuto','marcato','staccatissimo',\n" +
                     "  'accentStaccato','marcatoStaccato','tenutoStaccato','tenutoAccent'\n" +
                     "pitch: MIDI (60) or string ('C4','F#5','Bb3')   key: sharps+, flats- (2=D, -3=Eb)\n" +
                     "dur: 'whole','half','quarter','eighth','16th','32nd','64th'\n\n" +
                     "NOT supported (MS4 crashes): slurs, hairpins, ottava, pedal, trill, volta,\n" +
                     "  chord symbols, barline creation" }
        }
    }

    onRun: {}
}
